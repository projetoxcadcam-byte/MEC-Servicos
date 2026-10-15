from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.app.schemas.empresa import EmpresaCriacao
from backend.app.schemas.capacidade import CapacidadeCriacao


class SelecaoOperacoes(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    operacoes: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("operacoes")
    @classmethod
    def codigos_validos(cls, valores):
        if any(not 1 <= len(v) <= 60 or any(ord(c) < 32 for c in v) for v in valores):
            raise ValueError("codigo_operacao_invalido")
        if len(valores) != len(set(valores)): raise ValueError("operacao_repetida")
        return valores


class EmpresaComOperacoesCriacao(EmpresaCriacao, SelecaoOperacoes):
    @model_validator(mode="after")
    def coerencia_tipo(self):
        if self.tipo_empresa.value == "cliente" and self.operacoes:
            raise ValueError("cliente_nao_declara_operacoes_de_fornecedor")
        if self.tipo_empresa.value in {"fornecedor", "ambos"} and not self.operacoes:
            raise ValueError("selecione_ao_menos_uma_operacao")
        return self


class OperacoesEmpresaAtualizacao(SelecaoOperacoes):
    versao: str = Field(pattern=r"^[a-f0-9]{64}$")


class CapacidadeEmpresaRegistro(CapacidadeCriacao):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao: str = Field(pattern=r"^[a-f0-9]{64}$")


class MaterialEmpresaVinculo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    versao: str = Field(pattern=r"^[a-f0-9]{64}$")
    material_id: int | None = Field(default=None, gt=0, strict=True)
    codigo_catalogo: str | None = Field(default=None, min_length=2, max_length=60)
    novo_material: str | None = Field(default=None, min_length=2, max_length=160)

    @field_validator("novo_material")
    @classmethod
    def nome_valido(cls, valor):
        if valor is not None:
            if any(ord(c) < 32 or ord(c) == 127 for c in valor):
                raise ValueError("nome_material_invalido")
            valor = " ".join(valor.split())
            if len(valor) < 2: raise ValueError("nome_material_invalido")
        return valor

    @model_validator(mode="after")
    def uma_escolha(self):
        if sum(v is not None for v in (self.material_id, self.codigo_catalogo, self.novo_material)) != 1:
            raise ValueError("escolha_um_material")
        return self
