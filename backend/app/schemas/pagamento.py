from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PagamentoContratacaoCriacao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    valor: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    forma_pagamento: str = Field(min_length=1, max_length=20)
    observacoes: str | None = Field(default=None, max_length=5000)


class PagamentoContratacaoCancelamento(BaseModel):
    empresa_cliente_id: int = Field(gt=0)


class PagamentoContratacaoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contratacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    valor: Decimal
    forma_pagamento: str
    status: str
    observacoes: str | None
    criada_em: datetime
    paga_em: datetime
    cancelada_em: datetime | None


class ResumoFinanceiroLeitura(BaseModel):
    contratacao_id: int
    valor_contratado: Decimal
    total_pago: Decimal
    saldo: Decimal
    status_pagamento: str
    pagamentos: list[PagamentoContratacaoLeitura]
