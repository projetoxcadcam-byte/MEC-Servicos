from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.painel_administrativo import FiltroPainel, IndicadoresPainel, ItemPainel


class FiltrosPeriodo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_inicial: str | None
    data_final: str | None
    filtro: FiltroPainel
    busca: str


class ItemPeriodo(ItemPainel):
    contratada_em: str


class MesPeriodo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mes: str
    total_contratacoes: int = Field(ge=0)
    valor_contratado: Decimal
    recebido_confirmado: Decimal
    repassado_confirmado: Decimal


class ConsultaPeriodo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filtros: FiltrosPeriodo
    indicadores: IndicadoresPainel
    valor_contratado: Decimal
    meses: list[MesPeriodo]
    itens: list[ItemPeriodo]
    total: int = Field(ge=0)
    deslocamento: int = Field(ge=0)
    limite: int = Field(ge=1, le=100)
    gerado_em: str
