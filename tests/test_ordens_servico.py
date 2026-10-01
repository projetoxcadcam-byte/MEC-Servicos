from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import app


def _client() -> tuple[TestClient, Session, object]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessao = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    banco = sessao()
    app.dependency_overrides[obter_banco] = lambda: banco
    return TestClient(app), banco, engine


def _base(banco: Session, sufixo: str):
    cliente = Empresa(razao_social=f"Cliente OS {sufixo}", documento=f"700000000{sufixo}", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social=f"Fornecedor OS {sufixo}", documento=f"800000000{sufixo}", tipo_empresa="fornecedor")
    processo = ProcessoFabricacao(codigo=f"usinagem_cnc_os_{sufixo}", nome="Usinagem CNC", descricao="Processo D9.")
    material = Material(codigo=f"aco_os_{sufixo}", nome="Aço D9", familia="Aço", especificacao="Material D9.")
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()

    solicitacao = SolicitacaoServico(empresa_cliente_id=cliente.id, processo_id=processo.id, material_id=material.id, dimensao_x_maxima_mm=600, dimensao_y_maxima_mm=400, dimensao_z_maxima_mm=300, tolerancia_requerida_mm=0.02, quantidade=10, observacoes="Solicitação D9.", status="aberta")
    banco.add(solicitacao)
    banco.commit()

    cotacao = CotacaoFornecedor(solicitacao_id=solicitacao.id, empresa_fornecedora_id=fornecedor.id, valor_total=Decimal("12500.00"), prazo_dias=15, validade_dias=10, observacoes="Cotação D9.", status="aceita", encerrada_em=datetime.utcnow(), decidida_por_empresa_id=cliente.id)
    banco.add(cotacao)
    banco.commit()

    contratacao = ContratacaoServico(solicitacao_id=solicitacao.id, cotacao_id=cotacao.id, empresa_cliente_id=cliente.id, empresa_fornecedora_id=fornecedor.id, valor_total=Decimal("12500.00"), prazo_dias=15, observacoes="Contratação D9.", status="ativa", criada_em=datetime.utcnow())
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)
    return cliente, fornecedor, contratacao


def _fim(banco, engine):
    app.dependency_overrides.clear()
    banco.close()
    engine.dispose()


def test_criar_ordem_servico_a_partir_de_contratacao():
    http, banco, engine = _client()
    try:
        cliente, fornecedor, contratacao = _base(banco, "41")
        resposta = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        assert resposta.status_code == 201
        dados = resposta.json()
        assert dados["contratacao_id"] == contratacao.id
        assert dados["empresa_fornecedora_id"] == fornecedor.id
        assert dados["status"] == "aberta"
        assert dados["quantidade"] == 10
    finally:
        _fim(banco, engine)


def test_nao_permite_duas_ordens_para_mesma_contratacao():
    http, banco, engine = _client()
    try:
        cliente, _, contratacao = _base(banco, "42")
        primeira = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        segunda = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        assert primeira.status_code == 201
        assert segunda.status_code == 409
        assert segunda.json()["detail"] == "ordem_servico_ja_cadastrada_para_esta_contratacao"
    finally:
        _fim(banco, engine)


def test_iniciar_concluir_e_obter_ordem_servico():
    http, banco, engine = _client()
    try:
        cliente, _, contratacao = _base(banco, "43")
        criada = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        ordem_id = criada.json()["id"]
        iniciada = http.post(f"/api/v1/ordens-servico/{ordem_id}/iniciar", json={"empresa_cliente_id": cliente.id})
        assert iniciada.status_code == 200
        assert iniciada.json()["status"] == "em_execucao"
        concluida = http.post(f"/api/v1/ordens-servico/{ordem_id}/concluir", json={"empresa_cliente_id": cliente.id})
        assert concluida.status_code == 200
        assert concluida.json()["status"] == "concluida"
        obtida = http.get(f"/api/v1/ordens-servico/{ordem_id}")
        assert obtida.status_code == 200
        assert obtida.json()["status"] == "concluida"
    finally:
        _fim(banco, engine)


def test_empresa_incorreta_nao_pode_operar_ordem():
    http, banco, engine = _client()
    try:
        cliente, fornecedor, contratacao = _base(banco, "44")
        criada = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        ordem_id = criada.json()["id"]
        resposta = http.post(f"/api/v1/ordens-servico/{ordem_id}/iniciar", json={"empresa_cliente_id": fornecedor.id})
        assert resposta.status_code == 403
        assert resposta.json()["detail"] == "empresa_nao_e_cliente_da_ordem_servico"
    finally:
        _fim(banco, engine)


def test_cancelar_ordem_servico():
    http, banco, engine = _client()
    try:
        cliente, _, contratacao = _base(banco, "45")
        criada = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        ordem_id = criada.json()["id"]
        cancelada = http.post(f"/api/v1/ordens-servico/{ordem_id}/cancelar", json={"empresa_cliente_id": cliente.id, "observacoes": "Cancelamento D9."})
        assert cancelada.status_code == 200
        assert cancelada.json()["status"] == "cancelada"
        assert cancelada.json()["cancelada_em"] is not None
    finally:
        _fim(banco, engine)
