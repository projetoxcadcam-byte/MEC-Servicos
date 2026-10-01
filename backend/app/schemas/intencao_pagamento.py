from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IntencaoPagamentoCriacao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    valor: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    forma_pagamento: str = Field(min_length=1, max_length=20)
    observacoes: str | None = Field(default=None, max_length=5000)


class IntencaoPagamentoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contratacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    valor: Decimal
    forma_pagamento: str
    provedor: str
    idempotency_key: str
    external_payment_id: str
    checkout_url: str | None
    status: str
    pagamento_id: int | None
    observacoes: str | None
    criada_em: datetime
    atualizada_em: datetime
    paga_em: datetime | None
    cancelada_em: datetime | None


class WebhookPagamento(BaseModel):
    evento_id: str = Field(min_length=1, max_length=120)
    external_payment_id: str = Field(min_length=1, max_length=120)
    tipo_evento: str = Field(min_length=1, max_length=50)


class WebhookPagamentoLeitura(BaseModel):
    processado: bool
    duplicado: bool
    intencao: IntencaoPagamentoLeitura
