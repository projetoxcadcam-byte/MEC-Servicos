from __future__ import annotations

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from backend.app.schemas.operacoes_pdf import OperacaoPdf, OPERACOES_PDF, MAX_OPERACOES_PDF


class CamposCarimbo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    descricao: str = Field(min_length=1, max_length=80)
    codigo_tecnico: str = Field(default="", max_length=30)
    material: str = Field(min_length=1, max_length=50)
    quantidade: int = Field(gt=0, le=1_000_000)
    dureza: str = Field(default="", max_length=40)
    tratamento_termico: str = Field(default="", max_length=60)
    revestimento: str = Field(default="", max_length=60)
    escala: str = Field(min_length=1, max_length=24)
    unidade: str = Field(min_length=1, max_length=16)
    revisao: str = Field(default="", max_length=16)
    tolerancias_gerais: str = Field(default="", max_length=180)
    escopo_servico: Literal["conforme_solicitacao", "desbaste", "acabamento", "peca_completa"] = "conforme_solicitacao"
    sobremetal: str = Field(default="", max_length=80)
    observacoes_servico: str = Field(default="", max_length=180)
    operacoes_servico: list[OperacaoPdf] = Field(default_factory=list, max_length=MAX_OPERACOES_PDF)

    @field_validator("operacoes_servico")
    @classmethod
    def operacoes_distintas(cls, valores):
        if len(valores) != len(set(valores)):
            raise ValueError("operacao_do_servico_repetida")
        # Seleção sem ordem; a sequência deve ser informada nas observações.
        return [codigo for codigo in OPERACOES_PDF if codigo in valores]

    def dados_persistentes(self) -> dict:
        # O pedido antigo mantém o mesmo hash ao ser repetido após a D49.
        # Não acrescenta um escopo retroativo às configurações já existentes.
        dados = self.model_dump(mode="json")
        for nome, padrao in (("escopo_servico", "conforme_solicitacao"),
                             ("sobremetal", ""), ("observacoes_servico", ""),
                             ("operacoes_servico", [])):
            if dados[nome] == padrao:
                del dados[nome]
        return dados

    @field_validator("*", mode="after")
    @classmethod
    def texto_imprimivel(cls, value):
        if isinstance(value, str):
            if any(ord(c) < 32 and c not in "\n\t" for c in value):
                raise ValueError("texto_do_carimbo_invalido")
            try:
                value.encode("cp1252")
            except UnicodeEncodeError:
                raise ValueError("simbolo_do_carimbo_nao_suportado") from None
        return value


class AreaCarimbo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pagina: int = Field(ge=1, le=50)
    x: float = Field(ge=0, lt=1, allow_inf_nan=False)
    y: float = Field(ge=0, lt=1, allow_inf_nan=False)
    largura: float = Field(gt=0, le=1, allow_inf_nan=False)
    altura: float = Field(gt=0, le=1, allow_inf_nan=False)
    campos: CamposCarimbo

    @model_validator(mode="after")
    def dentro_da_pagina(self):
        if self.x + self.largura > 1.00000001 or self.y + self.altura > 1.00000001:
            raise ValueError("area_fora_da_pagina")
        return self


class PrepararPdf(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    versao_liberacao: int = Field(ge=0)
    paginas: list[AreaCarimbo] = Field(min_length=1, max_length=50)
    registro_interno: str = Field(min_length=3, max_length=2000)
    chave_operacao: UUID

    @model_validator(mode="after")
    def paginas_distintas(self):
        if len({p.pagina for p in self.paginas}) != len(self.paginas):
            raise ValueError("pagina_repetida")
        return self


class PreparacaoPdfResposta(BaseModel):
    id: int
    arquivo_id: int
    versao: int
    sha256_original: str
    sha256: str
    tamanho_bytes: int
    criado_em: str
    administrador_nome: str
    registro_interno: str
    paginas: list[AreaCarimbo]

