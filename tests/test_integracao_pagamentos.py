from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.integracoes.pagamento import assinatura_webhook
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import app


@pytest.fixture()
def ambiente():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
    cliente = Empresa(razao_social="Cliente D13", documento="D13-CLIENTE-001", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social="Fornecedor D13", documento="D13-FORNECEDOR-001", tipo_empresa="fornecedor")
    processo = ProcessoFabricacao(codigo="usinagem_cnc_d13", nome="Usinagem CNC D13", descricao="Processo D13")
    material = Material(codigo="aluminio_6061_d13", nome="Aluminio 6061 D13", familia="Aluminio", especificacao="Liga 6061")
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
        observacoes="Solicitacao D13",
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
        observacoes="Cotacao D13",
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
        observacoes="Contratacao D13",
        status="ativa",
    )
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)
    ids = cliente.id, fornecedor.id, contratacao.id
    banco.close()
    return ids


def criar_intencao(cliente_http, contratacao_id, cliente_id, chave="d13-idempotency-001"):
    return cliente_http.post(
        f"/api/v1/pagamentos/contratacoes/{contratacao_id}/intencoes",
        headers={"Idempotency-Key": chave},
        json={"empresa_cliente_id": cliente_id, "valor": "5000.00", "forma_pagamento": "pix"},
    )


def test_criar_intencao_com_gateway_fake(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = criar_intencao(cliente_http, contratacao_id, cliente_id)
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["provedor"] == "fake"
    assert dados["status"] == "aguardando_pagamento"
    assert dados["external_payment_id"]
    assert dados["checkout_url"]


def test_idempotency_nao_cria_duas_intencoes(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    primeira = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-002")
    segunda = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-002")
    assert primeira.status_code == 201
    assert segunda.status_code == 201
    assert segunda.json()["id"] == primeira.json()["id"]


def test_webhook_sucesso_gera_pagamento_no_livro_d12(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-003")
    dados_intencao = intencao.json()
    payload = {
        "evento_id": "evt-d13-003",
        "external_payment_id": dados_intencao["external_payment_id"],
        "tipo_evento": "payment.succeeded",
    }
    assinatura = assinatura_webhook(payload)
    resposta = cliente_http.post(
        "/api/v1/pagamentos/webhooks/fake",
        headers={"X-Webhook-Signature": assinatura},
        json=payload,
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["processado"] is True
    assert corpo["duplicado"] is False
    assert corpo["intencao"]["status"] == "paga"
    assert corpo["intencao"]["pagamento_id"] is not None

    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.status_code == 200
    assert resumo.json()["total_pago"] == "5000.00"
    assert resumo.json()["saldo"] == "5000.00"
    assert resumo.json()["status_pagamento"] == "parcial"


def test_webhook_idempotente_nao_duplica_pagamento(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-004")
    payload = {
        "evento_id": "evt-d13-004",
        "external_payment_id": intencao.json()["external_payment_id"],
        "tipo_evento": "payment.succeeded",
    }
    assinatura = assinatura_webhook(payload)
    primeira = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": assinatura}, json=payload)
    segunda = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": assinatura}, json=payload)
    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["duplicado"] is True
    pagamentos = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/pagamentos")
    assert len(pagamentos.json()) == 1


def test_webhook_assinatura_invalida(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-005")
    payload = {"evento_id": "evt-d13-005", "external_payment_id": intencao.json()["external_payment_id"], "tipo_evento": "payment.succeeded"}
    resposta = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": "0" * 64}, json=payload)
    assert resposta.status_code == 401


def test_webhook_falha_muda_status_sem_criar_pagamento(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-006")
    payload = {"evento_id": "evt-d13-006", "external_payment_id": intencao.json()["external_payment_id"], "tipo_evento": "payment.failed"}
    assinatura = assinatura_webhook(payload)
    resposta = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": assinatura}, json=payload)
    assert resposta.status_code == 200
    assert resposta.json()["intencao"]["status"] == "falhou"
    pagamentos = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/pagamentos")
    assert pagamentos.status_code == 200
    assert pagamentos.json() == []


def test_cliente_incorreto_nao_cria_intencao(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = criar_intencao(cliente_http, contratacao_id, cliente_id + 1000, "d13-idempotency-007")
    assert resposta.status_code == 403


def test_intencao_nao_permite_valor_acima_do_saldo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/pagamentos/contratacoes/{contratacao_id}/intencoes",
        headers={"Idempotency-Key": "d13-idempotency-008"},
        json={"empresa_cliente_id": cliente_id, "valor": "10000.01", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 409
