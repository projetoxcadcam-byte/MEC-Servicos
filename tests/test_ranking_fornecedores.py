
from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.material import Material
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.principal import app


@pytest.fixture()
def ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)

    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = substituir_banco
    try:
        with TestClient(app) as test_client:
            yield test_client, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_fornecedor(
    SessaoTeste: sessionmaker,
    *,
    sufixo: str,
    razao_social: str,
    notas: list[int],
) -> int:
    banco = SessaoTeste()
    cliente = Empresa(
        razao_social=f"Cliente D15 {sufixo}",
        documento=f"D15-CLIENTE-{sufixo}",
        tipo_empresa="cliente",
    )
    fornecedor = Empresa(
        razao_social=razao_social,
        documento=f"D15-FORNECEDOR-{sufixo}",
        tipo_empresa="fornecedor",
    )
    processo = ProcessoFabricacao(
        codigo=f"usinagem_cnc_d15_{sufixo}",
        nome=f"Usinagem CNC D15 {sufixo}",
        descricao="Usinagem D15.",
    )
    material = Material(
        codigo=f"aluminio_6061_d15_{sufixo}",
        nome=f"Aluminio 6061 D15 {sufixo}",
        familia="Aluminio",
        especificacao="Liga D15.",
    )
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()

    for indice, nota in enumerate(notas, start=1):
        solicitacao = SolicitacaoServico(
            empresa_cliente_id=cliente.id,
            processo_id=processo.id,
            material_id=material.id,
            dimensao_x_maxima_mm=100,
            dimensao_y_maxima_mm=100,
            dimensao_z_maxima_mm=100,
            tolerancia_requerida_mm=0.02,
            quantidade=5,
            observacoes=f"Solicitacao D15 {sufixo}-{indice}.",
            status="aberta",
        )
        banco.add(solicitacao)
        banco.commit()

        cotacao = CotacaoFornecedor(
            solicitacao_id=solicitacao.id,
            empresa_fornecedora_id=fornecedor.id,
            valor_total=Decimal("5000.00"),
            prazo_dias=10,
            validade_dias=10,
            observacoes=f"Cotacao D15 {sufixo}-{indice}.",
            status="aceita",
            decidida_por_empresa_id=cliente.id,
        )
        banco.add(cotacao)
        banco.commit()

        contratacao = ContratacaoServico(
            solicitacao_id=solicitacao.id,
            cotacao_id=cotacao.id,
            empresa_cliente_id=cliente.id,
            empresa_fornecedora_id=fornecedor.id,
            valor_total=Decimal("5000.00"),
            prazo_dias=10,
            observacoes=f"Contratacao D15 {sufixo}-{indice}.",
            status="encerrada",
        )
        banco.add(contratacao)
        banco.commit()

        ordem = OrdemServico(
            contratacao_id=contratacao.id,
            solicitacao_id=solicitacao.id,
            cotacao_id=cotacao.id,
            empresa_cliente_id=cliente.id,
            empresa_fornecedora_id=fornecedor.id,
            processo_id=processo.id,
            material_id=material.id,
            quantidade=5,
            valor_total=Decimal("5000.00"),
            prazo_dias=10,
            status="concluida",
        )
        banco.add(ordem)
        banco.commit()

        avaliacao = AvaliacaoOficina(
            contratacao_id=contratacao.id,
            ordem_servico_id=ordem.id,
            empresa_cliente_id=cliente.id,
            empresa_fornecedora_id=fornecedor.id,
            nota=nota,
        )
        banco.add(avaliacao)
        banco.commit()

    banco.refresh(fornecedor)
    fornecedor_id = fornecedor.id
    banco.close()
    return fornecedor_id


def preparar_fornecedor_sem_avaliacao(
    SessaoTeste: sessionmaker,
    *,
    sufixo: str,
    razao_social: str,
) -> int:
    banco = SessaoTeste()
    fornecedor = Empresa(
        razao_social=razao_social,
        documento=f"D15-FORNECEDOR-{sufixo}",
        tipo_empresa="fornecedor",
    )
    banco.add(fornecedor)
    banco.commit()
    banco.refresh(fornecedor)
    fornecedor_id = fornecedor.id
    banco.close()
    return fornecedor_id


def test_ranking_ordena_por_media_e_quantidade(ambiente):
    cliente_http, SessaoTeste = ambiente
    preparar_fornecedor(
        SessaoTeste,
        sufixo="A",
        razao_social="Fornecedor Alfa D15",
        notas=[5, 5],
    )
    preparar_fornecedor(
        SessaoTeste,
        sufixo="B",
        razao_social="Fornecedor Beta D15",
        notas=[4, 4, 4],
    )

    resposta = cliente_http.get("/api/v1/fornecedores/ranking")
    assert resposta.status_code == 200
    itens = resposta.json()["itens"]
    assert [item["razao_social"] for item in itens[:2]] == [
        "Fornecedor Alfa D15",
        "Fornecedor Beta D15",
    ]
    assert itens[0]["media_nota"] == 5.0
    assert itens[0]["quantidade_avaliacoes"] == 2
    assert itens[0]["posicao"] == 1
    assert itens[1]["posicao"] == 2


def test_quantidade_de_avaliacoes_desempata_media_igual(ambiente):
    cliente_http, SessaoTeste = ambiente
    preparar_fornecedor(
        SessaoTeste,
        sufixo="C",
        razao_social="Fornecedor Gama D15",
        notas=[5],
    )
    preparar_fornecedor(
        SessaoTeste,
        sufixo="D",
        razao_social="Fornecedor Delta D15",
        notas=[5, 5, 5],
    )

    itens = cliente_http.get("/api/v1/fornecedores/ranking").json()["itens"]
    assert itens[0]["razao_social"] == "Fornecedor Delta D15"
    assert itens[1]["razao_social"] == "Fornecedor Gama D15"
    assert itens[0]["media_nota"] == itens[1]["media_nota"] == 5.0
    assert itens[0]["quantidade_avaliacoes"] == 3
    assert itens[1]["quantidade_avaliacoes"] == 1


def test_fornecedor_sem_avaliacao_fica_apos_avaliados(ambiente):
    cliente_http, SessaoTeste = ambiente
    preparar_fornecedor(
        SessaoTeste,
        sufixo="E",
        razao_social="Fornecedor Epsilon D15",
        notas=[3],
    )
    preparar_fornecedor_sem_avaliacao(
        SessaoTeste,
        sufixo="F",
        razao_social="Fornecedor Zeta D15",
    )

    resposta = cliente_http.get("/api/v1/fornecedores/ranking")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total_fornecedores"] == 2
    assert corpo["fornecedores_avaliados"] == 1
    assert corpo["itens"][0]["razao_social"] == "Fornecedor Epsilon D15"
    assert corpo["itens"][1]["razao_social"] == "Fornecedor Zeta D15"
    assert corpo["itens"][1]["media_nota"] is None
    assert corpo["itens"][1]["quantidade_avaliacoes"] == 0


def test_ordem_e_deterministica_por_nome(ambiente):
    cliente_http, SessaoTeste = ambiente
    preparar_fornecedor(
        SessaoTeste,
        sufixo="G",
        razao_social="Fornecedor Alpha D15",
        notas=[4],
    )
    preparar_fornecedor(
        SessaoTeste,
        sufixo="H",
        razao_social="Fornecedor Beta D15",
        notas=[4],
    )

    itens = cliente_http.get("/api/v1/fornecedores/ranking").json()["itens"]
    assert [item["razao_social"] for item in itens] == [
        "Fornecedor Alpha D15",
        "Fornecedor Beta D15",
    ]
    assert [item["posicao"] for item in itens] == [1, 2]
