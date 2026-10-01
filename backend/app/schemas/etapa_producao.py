from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


ETAPAS_PRODUCAO = (
    "aguardando_material",
    "em_usinagem",
    "em_solda_dobra",
    "em_acabamento",
    "pronto_para_envio",
)


class EtapaProducaoCriacao(BaseModel):
    empresa_fornecedora_id: int = Field(gt=0)
    etapa: str
    observacoes: str | None = None

    @field_validator("etapa")
    @classmethod
    def validar_etapa(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if valor not in ETAPAS_PRODUCAO:
            raise ValueError(
                "etapa_invalida; valores permitidos: "
                + ", ".join(ETAPAS_PRODUCAO)
            )
        return valor


class EtapaProducaoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem_servico_id: int
    empresa_fornecedora_id: int
    etapa: str
    observacoes: str | None
    criada_em: datetime


class AcompanhamentoProducaoLeitura(BaseModel):
    ordem_servico_id: int
    etapa_atual: str | None
    historico: list[EtapaProducaoLeitura]
