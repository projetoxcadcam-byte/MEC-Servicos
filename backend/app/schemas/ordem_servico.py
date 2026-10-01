from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrdemServicoCriacao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)


class OrdemServicoAcao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    observacoes: str | None = None


class OrdemServicoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contratacao_id: int
    solicitacao_id: int
    cotacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    processo_id: int
    material_id: int
    quantidade: int
    valor_total: Decimal
    prazo_dias: int
    status: str
    observacoes: str | None
    criada_em: datetime
    iniciada_em: datetime | None
    concluida_em: datetime | None
    cancelada_em: datetime | None
