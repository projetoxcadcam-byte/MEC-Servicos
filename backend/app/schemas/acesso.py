from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DadosEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    senha: str = Field(min_length=1, max_length=128)


class DadosSenha(BaseModel):
    model_config = ConfigDict(extra="forbid")
    senha_atual: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=12, max_length=128)


class DadosUsuario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    perfil: Literal["admin", "cliente", "fornecedor"]
    empresa_id: int | None = Field(default=None, gt=0)
    senha: str = Field(min_length=12, max_length=128)


class DadosAtivo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ativo: bool


class DadosRedefinicao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nova_senha: str = Field(min_length=12, max_length=128)
