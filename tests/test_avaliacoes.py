
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


def preparar_servico(
    SessaoTeste: sessionmaker,
    *,
    encerrado: bool = True,
) -> tuple[int, int, int, int]:
    banco = SessaoTeste()

    cliente = Empresa(
        razao_social="Cliente D14",
        documento="D14-CLIENTE-001",
        tipo_empresa="cliente",
    )
    fornecedor = Empresa(
        razao_social="Fornecedor D14",
        documento="D14-FORNECEDOR-001",
        tipo_empresa="fornecedor",
    )
    processo = ProcessoFabricacao(
        codigo="usinagem_cnc_d14",
        nome="Usinagem CNC D14",
        descricao="Usinagem D14.",
    )
    material = Material(
        codigo="aluminio_6061_d14",
        nome="Aluminio 6061 D14",
        familia="Aluminio",
        especificacao="Liga D14.",
    )
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=100,
        dimensao_y_maxima_mm=100,
        dimensao_z_maxima_mm=100,
        tolerancia_requerida_mm=0.02,
        quantidade=5,
        observacoes="Solicitacao D14.",
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
        observacoes="Cotacao D14.",
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
        observacoes="Contratacao D14.",
        status="encerrada" if encerrado else "ativa",
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
        status="concluida" if encerrado else "em_execucao",
    )
    banco.add(ordem)
    banco.commit()

    ids = (cliente.id, fornecedor.id, contratacao.id, ordem.id)
    banco.close()
    return ids


def test_criar_avaliacao_valida(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, contratacao_id, _ = preparar_servico(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
        json={"empresa_cliente_id": cliente_id, "nota": 5, "comentario": "Serviço excelente."},
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["nota"] == 5
    assert corpo["empresa_fornecedora_id"] == fornecedor_id


def test_nota_fora_da_faixa_e_rejeitada(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id, _ = preparar_servico(SessaoTeste)

    for nota in (0, 6):
        resposta = cliente_http.post(
            f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
            json={"empresa_cliente_id": cliente_id, "nota": nota},
        )
        assert resposta.status_code == 422


def test_cliente_incorreto_nao_pode_avaliar(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, _, contratacao_id, _ = preparar_servico(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
        json={"empresa_cliente_id": 999999, "nota": 4},
    )
    assert resposta.status_code == 403


def test_servico_nao_concluido_nao_pode_ser_avaliado(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id, _ = preparar_servico(
        SessaoTeste,
        encerrado=False,
    )

    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
        json={"empresa_cliente_id": cliente_id, "nota": 4},
    )
    assert resposta.status_code == 409


def test_nao_permite_duas_avaliacoes_para_mesma_contratacao(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id, _ = preparar_servico(SessaoTeste)

    primeira = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
        json={"empresa_cliente_id": cliente_id, "nota": 4},
    )
    assert primeira.status_code == 201

    segunda = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
        json={"empresa_cliente_id": cliente_id, "nota": 5},
    )
    assert segunda.status_code == 409


def test_obter_listar_e_reputacao(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, contratacao_id, _ = preparar_servico(SessaoTeste)

    criada = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",
        json={"empresa_cliente_id": cliente_id, "nota": 4, "comentario": "Bom serviço."},
    )
    assert criada.status_code == 201
    avaliacao_id = criada.json()["id"]

    obtida = cliente_http.get(f"/api/v1/avaliacoes/{avaliacao_id}")
    assert obtida.status_code == 200
    assert obtida.json()["id"] == avaliacao_id

    lista = cliente_http.get(
        f"/api/v1/empresas/{fornecedor_id}/avaliacoes"
    )
    assert lista.status_code == 200
    assert len(lista.json()) == 1

    reputacao = cliente_http.get(
        f"/api/v1/empresas/{fornecedor_id}/reputacao"
    )
    assert reputacao.status_code == 200
    assert reputacao.json()["quantidade_avaliacoes"] == 1
    assert reputacao.json()["media_nota"] == 4.0
