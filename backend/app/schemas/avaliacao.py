
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AvaliacaoOficinaCriacao(BaseModel):
    empresa_cliente_id: int
    nota: int = Field(ge=1, le=5)
    comentario: str | None = Field(default=None, max_length=2000)


class AvaliacaoOficinaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contratacao_id: int
    ordem_servico_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    nota: int
    comentario: str | None
    criada_em: datetime


class ReputacaoOficinaResposta(BaseModel):
    empresa_id: int
    quantidade_avaliacoes: int
    media_nota: float | None
