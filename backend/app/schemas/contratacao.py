from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ContratacaoCriacao(BaseModel):
    cotacao_id: int = Field(gt=0)
    empresa_cliente_id: int = Field(gt=0)
    observacoes: str | None = Field(default=None, max_length=5000)


class ContratacaoCancelamento(BaseModel):
    empresa_cliente_id: int = Field(gt=0)


class ContratacaoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitacao_id: int
    cotacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    valor_total: Decimal
    prazo_dias: int
    observacoes: str | None
    status: str
    criada_em: datetime
    cancelada_em: datetime | None
    encerrada_em: datetime | None
