from __future__ import annotations

from typing import Annotated
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class RegistrarAvaliacaoPerfil(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nota: Annotated[StrictInt, Field(ge=1, le=5)]
    comentario: str | None = Field(default=None, max_length=2000, strict=True)
    versao: str = Field(pattern=r"^[a-f0-9]{64}$", strict=True)
    chave_operacao: UUID

    @field_validator("comentario")
    @classmethod
    def limpar_comentario(cls, valor):
        return valor.strip() or None if valor is not None else None
