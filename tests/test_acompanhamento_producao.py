
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


def preparar_ordem(SessaoTeste: sessionmaker) -> tuple[int, int, int]:
    banco = SessaoTeste()

    cliente = Empresa(
        razao_social="Cliente D10",
        documento="D10-CLIENTE-001",
        tipo_empresa="cliente",
    )
    fornecedor = Empresa(
        razao_social="Fornecedor D10",
        documento="D10-FORNECEDOR-001",
        tipo_empresa="fornecedor",
    )
    processo = ProcessoFabricacao(
        codigo="usinagem_cnc_d10",
        nome="Usinagem CNC D10",
        descricao="Usinagem D10.",
    )
    material = Material(
        codigo="aluminio_6061_d10",
        nome="Aluminio 6061 D10",
        familia="Aluminio",
        especificacao="Liga D10.",
    )
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()
    for item in (cliente, fornecedor, processo, material):
        banco.refresh(item)

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=100,
        dimensao_y_maxima_mm=100,
        dimensao_z_maxima_mm=100,
        tolerancia_requerida_mm=0.02,
        quantidade=5,
        observacoes="Solicitacao D10.",
        status="aberta",
    )
    banco.add(solicitacao)
    banco.commit()
    banco.refresh(solicitacao)

    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"),
        prazo_dias=10,
        validade_dias=10,
        observacoes="Cotacao D10.",
        status="aceita",
        decidida_por_empresa_id=cliente.id,
    )
    banco.add(cotacao)
    banco.commit()
    banco.refresh(cotacao)

    contratacao = ContratacaoServico(
        solicitacao_id=solicitacao.id,
        cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"),
        prazo_dias=10,
        observacoes="Contratacao D10.",
        status="ativa",
    )
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)

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
        status="em_execucao",
    )
    banco.add(ordem)
    banco.commit()
    banco.refresh(ordem)

    ids = (cliente.id, fornecedor.id, ordem.id)
    banco.close()
    return ids


def test_registrar_etapa_e_listar_historico(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "etapa": "aguardando_material",
            "observacoes": "Material em compra.",
        },
    )
    assert resposta.status_code == 201
    assert resposta.json()["etapa"] == "aguardando_material"

    resposta = cliente_http.get(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
    )
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_acompanhamento_retorna_etapa_atual(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)

    for etapa in ("aguardando_material", "em_usinagem"):
        resposta = cliente_http.post(
            f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
            json={
                "empresa_fornecedora_id": fornecedor_id,
                "etapa": etapa,
            },
        )
        assert resposta.status_code == 201

    resposta = cliente_http.get(
        f"/api/v1/ordens-servico/{ordem_id}/acompanhamento-producao",
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["etapa_atual"] == "em_usinagem"
    assert len(corpo["historico"]) == 2


def test_fornecedor_incorreto_nao_pode_atualizar(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id + 1000,
            "etapa": "em_usinagem",
        },
    )
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "empresa_nao_e_fornecedora_da_ordem_servico"


def test_etapa_invalida_e_rejeitada(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "etapa": "etapa_inexistente",
        },
    )
    assert resposta.status_code == 422


def test_ordem_concluida_nao_recebe_nova_etapa(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)

    banco = SessaoTeste()
    ordem = banco.get(OrdemServico, ordem_id)
    ordem.status = "concluida"
    banco.commit()
    banco.close()

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "etapa": "pronto_para_envio",
        },
    )
    assert resposta.status_code == 409
