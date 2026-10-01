from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ProcessoCriacao(BaseModel):
    codigo: str = Field(min_length=2, max_length=60)
    nome: str = Field(min_length=2, max_length=160)
    descricao: str | None = Field(default=None, max_length=2000)

class ProcessoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nome: str
    descricao: str | None
    ativo: bool
    criado_em: datetime
