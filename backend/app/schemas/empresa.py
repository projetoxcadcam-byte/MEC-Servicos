from __future__ import annotations

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TipoEmpresa(str, Enum):
    CLIENTE = "cliente"
    FORNECEDOR = "fornecedor"
    AMBOS = "ambos"


def normalizar_documento(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) not in (11, 14):
        raise ValueError("documento deve conter 11 dígitos (CPF) ou 14 dígitos (CNPJ)")
    return digitos


class EmpresaCriacao(BaseModel):
    razao_social: str = Field(min_length=2, max_length=200)
    documento: str
    tipo_empresa: TipoEmpresa

    @field_validator("razao_social")
    @classmethod
    def limpar_razao_social(cls, valor: str) -> str:
        limpo = " ".join(valor.split())
        if len(limpo) < 2:
            raise ValueError("razão social muito curta")
        return limpo

    @field_validator("documento")
    @classmethod
    def limpar_documento(cls, valor: str) -> str:
        return normalizar_documento(valor)


class EmpresaLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    razao_social: str
    documento: str
    tipo_empresa: TipoEmpresa
    avaliacao: float | None
    criado_em: datetime
    atualizado_em: datetime
