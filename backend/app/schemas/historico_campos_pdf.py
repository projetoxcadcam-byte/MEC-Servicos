from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.app.schemas.preparacao_pdf import CamposCarimbo

CampoHistoricoPdf = Literal["descricao", "codigo_tecnico", "material", "quantidade", "dureza",
    "tratamento_termico", "revestimento", "escala", "unidade", "revisao",
    "tolerancias_gerais", "sobremetal", "observacoes_servico"]
LIMITES = {"descricao":80, "codigo_tecnico":30, "material":50, "quantidade":7, "dureza":40,
    "tratamento_termico":60, "revestimento":60, "escala":24, "unidade":16,
    "revisao":16, "tolerancias_gerais":180, "sobremetal":80, "observacoes_servico":180}


class ValorHistoricoPdf(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    campo: CampoHistoricoPdf
    valor: str = Field(min_length=1, max_length=180)

    @model_validator(mode="after")
    def validar_valor(self):
        if len(self.valor) > LIMITES[self.campo]:
            raise ValueError("valor_do_historico_excede_limite")
        CamposCarimbo.texto_imprimivel(self.valor)
        if self.campo == "quantidade":
            if not self.valor.isascii() or not self.valor.isdecimal() or not 1 <= int(self.valor) <= 1_000_000:
                raise ValueError("quantidade_do_historico_invalida")
            self.valor = str(int(self.valor))
        return self


class GuardarHistoricoPdf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    itens: list[ValorHistoricoPdf] = Field(min_length=1, max_length=650)
