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
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.principal import app


@pytest.fixture()
def ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessaoTeste = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = substituir_banco
    try:
        with TestClient(app) as cliente_http:
            yield cliente_http, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_ordem(SessaoTeste: sessionmaker) -> tuple[int, int, int, int]:
    banco = SessaoTeste()
    cliente = Empresa(razao_social="Cliente D11", documento="D11-CLIENTE-001", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social="Fornecedor D11", documento="D11-FORNECEDOR-001", tipo_empresa="fornecedor")
    processo = ProcessoFabricacao(codigo="usinagem_cnc_d11", nome="Usinagem CNC D11", descricao="Usinagem D11.")
    material = Material(codigo="aluminio_6061_d11", nome="Aluminio 6061 D11", familia="Aluminio", especificacao="Liga D11.")
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()
    for item in (cliente, fornecedor, processo, material):
        banco.refresh(item)
    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id, processo_id=processo.id, material_id=material.id,
        dimensao_x_maxima_mm=100, dimensao_y_maxima_mm=100, dimensao_z_maxima_mm=100,
        tolerancia_requerida_mm=0.02, quantidade=5, observacoes="Solicitacao D11.", status="aberta",
    )
    banco.add(solicitacao); banco.commit(); banco.refresh(solicitacao)
    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id, empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"), prazo_dias=10, validade_dias=10,
        observacoes="Cotacao D11.", status="aceita", decidida_por_empresa_id=cliente.id,
    )
    banco.add(cotacao); banco.commit(); banco.refresh(cotacao)
    contratacao = ContratacaoServico(
        solicitacao_id=solicitacao.id, cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id, empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"), prazo_dias=10,
        observacoes="Contratacao D11.", status="ativa",
    )
    banco.add(contratacao); banco.commit(); banco.refresh(contratacao)
    ordem = OrdemServico(
        contratacao_id=contratacao.id, solicitacao_id=solicitacao.id, cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id, empresa_fornecedora_id=fornecedor.id,
        processo_id=processo.id, material_id=material.id, quantidade=5,
        valor_total=Decimal("5000.00"), prazo_dias=10, status="em_execucao",
    )
    banco.add(ordem); banco.commit(); banco.refresh(ordem)
    etapa = EtapaProducao(
        ordem_servico_id=ordem.id, empresa_fornecedora_id=fornecedor.id,
        etapa="pronto_para_envio", observacoes="Produção D11 pronta.",
    )
    banco.add(etapa); banco.commit()
    ids = (cliente.id, fornecedor.id, ordem.id, contratacao.id)
    banco.close()
    return ids


def test_registrar_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert resposta.status_code == 201
    assert resposta.json()["status"] == "entregue"


def test_obter_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.get(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}")
    assert resposta.status_code == 200
    assert resposta.json()["id"] == entrega_id


def test_fornecedor_incorreto_nao_pode_registrar_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id + 1000})
    assert resposta.status_code == 403


def test_cliente_incorreto_nao_pode_aceitar(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id + 1000})
    assert resposta.status_code == 403


def test_cliente_incorreto_nao_pode_recusar(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/recusar", json={"empresa_cliente_id": cliente_id + 1000, "motivo": "Motivo D11."})
    assert resposta.status_code == 403


def test_aceitar_entrega_conclui_ordem_e_contratacao(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, contratacao_id = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id})
    assert resposta.status_code == 200
    banco = SessaoTeste()
    ordem = banco.get(OrdemServico, ordem_id)
    contratacao = banco.get(ContratacaoServico, contratacao_id)
    assert ordem.status == "concluida"
    assert contratacao.status == "encerrada"
    banco.close()


def test_recusar_entrega_exige_motivo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/recusar", json={"empresa_cliente_id": cliente_id})
    assert resposta.status_code == 422


def test_nao_permite_duas_entregas_pendentes(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    primeira = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert primeira.status_code == 201
    segunda = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert segunda.status_code == 409


def test_entrega_aceita_nao_pode_ser_aceita_novamente(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    primeira = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id})
    assert primeira.status_code == 200
    segunda = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id})
    assert segunda.status_code == 409


def test_ordem_concluida_nao_recebe_nova_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    banco = SessaoTeste(); ordem = banco.get(OrdemServico, ordem_id); ordem.status = "concluida"; banco.commit(); banco.close()
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert resposta.status_code == 409


def test_ordem_sem_pronto_para_envio_nao_pode_receber_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    banco = SessaoTeste()
    etapa = banco.query(EtapaProducao).filter(EtapaProducao.ordem_servico_id == ordem_id).first()
    etapa.etapa = "em_usinagem"; banco.commit(); banco.close()
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert resposta.status_code == 409


def test_recusar_entrega_permite_nova_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    primeira = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = primeira.json()["id"]
    recusada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/recusar", json={"empresa_cliente_id": cliente_id, "motivo": "Peça não atende ao desenho."})
    assert recusada.status_code == 200
    segunda = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert segunda.status_code == 201
