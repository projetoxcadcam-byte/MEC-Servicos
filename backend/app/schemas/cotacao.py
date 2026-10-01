from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CotacaoCriacao(BaseModel):
    empresa_fornecedora_id: int = Field(gt=0)
    valor_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    prazo_dias: int = Field(gt=0, le=3650)
    validade_dias: int = Field(gt=0, le=3650)
    observacoes: str | None = Field(default=None, max_length=5000)


class CotacaoDecisao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)


class CotacaoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitacao_id: int
    empresa_fornecedora_id: int
    valor_total: Decimal
    prazo_dias: int
    validade_dias: int
    observacoes: str | None
    status: str
    criada_em: datetime
    encerrada_em: datetime | None
    decidida_por_empresa_id: int | None
