from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntregaServicoCriacao(BaseModel):
    empresa_fornecedora_id: int = Field(gt=0)
    observacoes: str | None = None


class EntregaServicoDecisao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    motivo: str | None = None

    @field_validator("motivo")
    @classmethod
    def normalizar_motivo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None


class EntregaServicoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem_servico_id: int
    empresa_fornecedora_id: int
    empresa_cliente_id: int
    status: str
    observacoes: str | None
    motivo_recusa: str | None
    criada_em: datetime
    entregue_em: datetime
    aceita_em: datetime | None
    recusada_em: datetime | None
