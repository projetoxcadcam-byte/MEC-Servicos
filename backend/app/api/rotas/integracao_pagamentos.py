from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.intencao_pagamento import (
    IntencaoPagamentoCriacao,
    IntencaoPagamentoLeitura,
    WebhookPagamento,
    WebhookPagamentoLeitura,
)
from backend.app.services.integracao_pagamento import (
    IntegracaoAssinaturaInvalida,
    IntegracaoContratacaoNaoEncontrada,
    IntegracaoContratacaoNaoPodeReceber,
    IntegracaoEmpresaNaoPodeIniciar,
    IntegracaoEventoInvalido,
    IntegracaoFormaInvalida,
    IntegracaoIdempotencyInvalida,
    IntegracaoIntencaoNaoEncontrada,
    IntegracaoPagamentoNaoPodeSerConfirmado,
    IntegracaoProvedorNaoSuportado,
    IntegracaoValorAcimaDoSaldo,
    ServicoIntegracaoPagamento,
)

roteador = APIRouter(prefix="/pagamentos", tags=["integracao-pagamentos"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "/contratacoes/{contratacao_id}/intencoes",
    response_model=IntencaoPagamentoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def criar_intencao(
    contratacao_id: int,
    dados: IntencaoPagamentoCriacao,
    banco: SessaoBanco,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
):
    try:
        item, duplicado = ServicoIntegracaoPagamento(banco).iniciar(contratacao_id, dados, idempotency_key)
    except IntegracaoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc
    except IntegracaoEmpresaNaoPodeIniciar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except IntegracaoContratacaoNaoPodeReceber as exc:
        raise HTTPException(409, "contratacao_nao_pode_receber_pagamento") from exc
    except IntegracaoFormaInvalida as exc:
        raise HTTPException(422, "forma_pagamento_invalida") from exc
    except IntegracaoValorAcimaDoSaldo as exc:
        raise HTTPException(409, "valor_acima_do_saldo") from exc
    except IntegracaoIdempotencyInvalida as exc:
        raise HTTPException(422, "idempotency_key_invalida") from exc
    if duplicado:
        return item
    return item


@roteador.get("/intencoes/{intencao_id}", response_model=IntencaoPagamentoLeitura)
def obter_intencao(intencao_id: int, banco: SessaoBanco):
    try:
        return ServicoIntegracaoPagamento(banco).obter(intencao_id)
    except IntegracaoIntencaoNaoEncontrada as exc:
        raise HTTPException(404, "intencao_pagamento_nao_encontrada") from exc


@roteador.post("/webhooks/{provedor}", response_model=WebhookPagamentoLeitura)
def receber_webhook(
    provedor: str,
    dados: WebhookPagamento,
    banco: SessaoBanco,
    x_webhook_signature: Annotated[str, Header(alias="X-Webhook-Signature", min_length=64, max_length=128)],
):
    try:
        item, duplicado = ServicoIntegracaoPagamento(banco).webhook(provedor, dados, x_webhook_signature)
    except IntegracaoProvedorNaoSuportado as exc:
        raise HTTPException(422, "provedor_nao_suportado") from exc
    except IntegracaoAssinaturaInvalida as exc:
        raise HTTPException(401, "assinatura_webhook_invalida") from exc
    except IntegracaoEventoInvalido as exc:
        raise HTTPException(422, "evento_gateway_invalido") from exc
    except IntegracaoIntencaoNaoEncontrada as exc:
        raise HTTPException(404, "intencao_pagamento_nao_encontrada") from exc
    except IntegracaoPagamentoNaoPodeSerConfirmado as exc:
        raise HTTPException(409, "intencao_pagamento_nao_pode_ser_confirmada") from exc
    return WebhookPagamentoLeitura(processado=not duplicado, duplicado=duplicado, intencao=item)
