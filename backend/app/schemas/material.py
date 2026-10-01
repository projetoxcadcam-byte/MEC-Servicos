from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class MaterialCriacao(BaseModel):
    codigo: str = Field(min_length=2, max_length=60)
    nome: str = Field(min_length=2, max_length=160)
    familia: str | None = Field(default=None, max_length=100)
    especificacao: str | None = Field(default=None, max_length=2000)

class MaterialLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nome: str
    familia: str | None
    especificacao: str | None
    ativo: bool
    criado_em: datetime
