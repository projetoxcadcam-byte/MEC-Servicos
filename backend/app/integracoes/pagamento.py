from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from dataclasses import dataclass

WEBHOOK_SECRET_ENV = "MEC_PAGAMENTO_WEBHOOK_SECRET"
DEFAULT_WEBHOOK_SECRET = "mec-servicos-d13-dev-secret"


@dataclass(frozen=True)
class CobrancaGateway:
    provedor: str
    external_payment_id: str
    checkout_url: str


class GatewayPagamento:
    nome = "base"

    def criar_cobranca(
        self,
        *,
        valor: str,
        forma_pagamento: str,
        idempotency_key: str,
    ) -> CobrancaGateway:
        raise NotImplementedError


class GatewayPagamentoFake(GatewayPagamento):
    nome = "fake"

    def criar_cobranca(
        self,
        *,
        valor: str,
        forma_pagamento: str,
        idempotency_key: str,
    ) -> CobrancaGateway:
        external_payment_id = f"fake_{uuid.uuid4().hex}"
        checkout_url = f"https://fake-gateway.local/checkout/{external_payment_id}"
        return CobrancaGateway(
            provedor=self.nome,
            external_payment_id=external_payment_id,
            checkout_url=checkout_url,
        )


def segredo_webhook() -> bytes:
    return os.getenv(WEBHOOK_SECRET_ENV, DEFAULT_WEBHOOK_SECRET).encode("utf-8")


def assinatura_webhook(payload: dict) -> str:
    corpo = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(segredo_webhook(), corpo, hashlib.sha256).hexdigest()


def validar_assinatura_webhook(payload: dict, assinatura: str) -> bool:
    esperada = assinatura_webhook(payload)
    return hmac.compare_digest(esperada, assinatura)
