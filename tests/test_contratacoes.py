from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import app


def _cliente(banco, documento: str) -> Empresa:
    item = Empresa(
        razao_social="Cliente Teste D8",
        documento=documento,
        tipo_empresa="cliente",
    )
    banco.add(item)
    banco.commit()
    banco.refresh(item)
    return item


def _fornecedor(banco, documento: str) -> Empresa:
    item = Empresa(
        razao_social="Fornecedor Teste D8",
        documento=documento,
        tipo_empresa="fornecedor",
    )
    banco.add(item)
    banco.commit()
    banco.refresh(item)
    return item


def _base_cotacao_aceita(banco, sufixo: str):
    cliente = _cliente(banco, f"1000000000{sufixo}1")
    fornecedor = _fornecedor(banco, f"2000000000{sufixo}2")

    processo = ProcessoFabricacao(
        codigo=f"usinagem_cnc_d8_{sufixo}",
        nome="Usinagem CNC D8",
        descricao="Processo D8",
    )
    material = Material(
        codigo=f"aluminio_6061_d8_{sufixo}",
        nome="Aluminio 6061 D8",
        familia="Aluminio",
        especificacao="Liga 6061",
    )
    banco.add_all([processo, material])
    banco.commit()
    banco.refresh(processo)
    banco.refresh(material)

    capacidade = CapacidadeFornecedor(
        empresa_id=fornecedor.id,
        processo_id=processo.id,
        dimensao_x_maxima_mm=Decimal("800"),
        dimensao_y_maxima_mm=Decimal("500"),
        dimensao_z_maxima_mm=Decimal("450"),
        tolerancia_minima_mm=Decimal("0.0200"),
        observacoes="Capacidade D8",
    )
    banco.add(capacidade)
    banco.commit()

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=Decimal("600"),
        dimensao_y_maxima_mm=Decimal("400"),
        dimensao_z_maxima_mm=Decimal("300"),
        tolerancia_requerida_mm=Decimal("0.0200"),
        quantidade=10,
        observacoes="Solicitação D8",
    )
    banco.add(solicitacao)
    banco.commit()
    banco.refresh(solicitacao)

    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("12500.00"),
        prazo_dias=15,
        validade_dias=10,
        observacoes="Cotação aceita D8",
        status="aceita",
        decidida_por_empresa_id=cliente.id,
    )
    banco.add(cotacao)
    banco.commit()
    banco.refresh(cotacao)

    return cliente, fornecedor, solicitacao, cotacao


def _client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    banco = SessionLocal()

    def override_obter_banco():
        yield banco

    app.dependency_overrides[obter_banco] = override_obter_banco
    return TestClient(app), banco, engine


def test_criar_contratacao_a_partir_de_cotacao_aceita():
    cliente_http, banco, engine = _client()
    try:
        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "31")

        resposta = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": cliente.id,
                "observacoes": "Contratação D8",
            },
        )

        assert resposta.status_code == 201
        dados = resposta.json()
        assert dados["status"] == "ativa"
        assert dados["empresa_fornecedora_id"] == fornecedor.id
        assert dados["valor_total"] == "12500.00"
        assert dados["prazo_dias"] == 15

        banco.refresh(solicitacao)
        assert solicitacao.status == "encerrada"
    finally:
        app.dependency_overrides.clear()
        banco.close()
        engine.dispose()


def test_nao_cria_contratacao_de_cotacao_nao_aceita():
    cliente_http, banco, engine = _client()
    try:
        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "32")
        cotacao.status = "enviada"
        banco.commit()

        resposta = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": cliente.id,
            },
        )

        assert resposta.status_code == 409
        assert resposta.json()["detail"] == "cotacao_nao_esta_aceita"
    finally:
        app.dependency_overrides.clear()
        banco.close()
        engine.dispose()


def test_cliente_incorreto_nao_pode_contratar():
    cliente_http, banco, engine = _client()
    try:
        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "33")
        outro_cliente = _cliente(banco, "30000000000134")

        resposta = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": outro_cliente.id,
            },
        )

        assert resposta.status_code == 403
        assert resposta.json()["detail"] == "empresa_nao_e_cliente_da_solicitacao"
        assert banco.query(ContratacaoServico).count() == 0
    finally:
        app.dependency_overrides.clear()
        banco.close()
        engine.dispose()


def test_nao_permite_duas_contratacoes_para_mesma_solicitacao():
    cliente_http, banco, engine = _client()
    try:
        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "34")

        primeira = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": cliente.id,
            },
        )
        assert primeira.status_code == 201

        segunda = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": cliente.id,
            },
        )

        assert segunda.status_code == 409
        assert segunda.json()["detail"] == "contratacao_ja_cadastrada"
    finally:
        app.dependency_overrides.clear()
        banco.close()
        engine.dispose()


def test_obter_contratacao():
    cliente_http, banco, engine = _client()
    try:
        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "35")

        criada = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": cliente.id,
            },
        )
        assert criada.status_code == 201

        resposta = cliente_http.get(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
        )

        assert resposta.status_code == 200
        assert resposta.json()["cotacao_id"] == cotacao.id
    finally:
        app.dependency_overrides.clear()
        banco.close()
        engine.dispose()


def test_cancelar_contratacao():
    cliente_http, banco, engine = _client()
    try:
        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "36")

        criada = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",
            json={
                "cotacao_id": cotacao.id,
                "empresa_cliente_id": cliente.id,
            },
        )
        assert criada.status_code == 201

        cancelada = cliente_http.post(
            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao/cancelar",
            json={"empresa_cliente_id": cliente.id},
        )

        assert cancelada.status_code == 200
        assert cancelada.json()["status"] == "cancelada"
        assert cancelada.json()["cancelada_em"] is not None
    finally:
        app.dependency_overrides.clear()
        banco.close()
        engine.dispose()
