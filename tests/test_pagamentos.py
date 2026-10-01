from __future__ import annotations

from decimal import Decimal

import pytest
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
from backend.app.models.ordem_servico import OrdemServico
from backend.app.principal import app


@pytest.fixture()
def ambiente():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessaoTeste = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    def override():
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = override
    try:
        with TestClient(app) as cliente_http:
            yield cliente_http, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_contratacao(SessaoTeste):
    banco = SessaoTeste()
    cliente = Empresa(razao_social="Cliente D12", documento="D12-CLIENTE-001", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social="Fornecedor D12", documento="D12-FORNECEDOR-001", tipo_empresa="fornecedor")
    processo = ProcessoFabricacao(codigo="usinagem_cnc_d12", nome="Usinagem CNC D12", descricao="Processo D12")
    material = Material(codigo="aluminio_6061_d12", nome="Aluminio 6061 D12", familia="Aluminio", especificacao="Liga 6061")
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()
    for item in (cliente, fornecedor, processo, material):
        banco.refresh(item)

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=Decimal("100"),
        dimensao_y_maxima_mm=Decimal("100"),
        dimensao_z_maxima_mm=Decimal("100"),
        tolerancia_requerida_mm=Decimal("0.0200"),
        quantidade=5,
        observacoes="Solicitacao D12",
        status="aberta",
    )
    banco.add(solicitacao)
    banco.commit()
    banco.refresh(solicitacao)

    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("10000.00"),
        prazo_dias=10,
        validade_dias=10,
        observacoes="Cotacao D12",
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
        valor_total=Decimal("10000.00"),
        prazo_dias=10,
        observacoes="Contratacao D12",
        status="ativa",
    )
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)
    ids = cliente.id, fornecedor.id, contratacao.id
    banco.close()
    return ids


def test_pagamento_integral(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "10000.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 201
    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.status_code == 200
    dados = resumo.json()
    assert dados["total_pago"] == "10000.00"
    assert dados["saldo"] == "0.00"
    assert dados["status_pagamento"] == "pago"


def test_pagamentos_parciais_calculam_saldo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    for valor in ("2500.00", "1500.00"):
        resposta = cliente_http.post(
            f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
            json={"empresa_cliente_id": cliente_id, "valor": valor, "forma_pagamento": "transferencia"},
        )
        assert resposta.status_code == 201
    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.json()["total_pago"] == "4000.00"
    assert resumo.json()["saldo"] == "6000.00"
    assert resumo.json()["status_pagamento"] == "parcial"


def test_nao_permite_pagamento_acima_do_saldo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "10000.01", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "pagamento_acima_do_saldo"


def test_cliente_incorreto_nao_pode_pagar(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id + 1000, "valor": "100.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 403


def test_forma_pagamento_invalida(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "100.00", "forma_pagamento": "cheque"},
    )
    assert resposta.status_code == 422


def test_listar_pagamentos(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "100.00", "forma_pagamento": "pix"},
    )
    resposta = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/pagamentos")
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_cancelamento_reabre_saldo_financeiro(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    criada = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "1000.00", "forma_pagamento": "pix"},
    )
    assert criada.status_code == 201
    pagamento_id = criada.json()["id"]
    cancelada = cliente_http.post(
        f"/api/v1/contratacoes/pagamentos/{pagamento_id}/cancelar",
        json={"empresa_cliente_id": cliente_id},
    )
    assert cancelada.status_code == 200
    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.json()["total_pago"] == "0.00"
    assert resumo.json()["saldo"] == "10000.00"
    assert resumo.json()["status_pagamento"] == "pendente"


def test_contratacao_cancelada_nao_recebe_pagamento(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    banco = SessaoTeste()
    contratacao = banco.get(ContratacaoServico, contratacao_id)
    contratacao.status = "cancelada"
    banco.commit()
    banco.close()
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "100.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 409


def test_pagamento_negativo_rejeitado(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "-1.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 422


def test_pagamento_inexistente(ambiente):
    cliente_http, _ = ambiente
    resposta = cliente_http.get("/api/v1/contratacoes/pagamentos/999999")
    assert resposta.status_code == 404
