from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.painel_administrativo import IndicadoresPainel, PendenciaPainel
from backend.app.schemas.relatorio_empresas import ItemEmpresa
from backend.app.schemas.relatorio_periodo import FiltrosPeriodo

AreaFila = Literal["todas", "operacional", "financeira", "conferencia"]


class FiltrosPendencias(FiltrosPeriodo):
    area: AreaFila
    acao: str


class AcaoPendencia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str
    area: Literal["operacional", "financeira", "conferencia"]
    rotulo: str


class ItemPendencia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contratacao: ItemEmpresa
    pendencia: PendenciaPainel
    acao: str
    caminho: str
    destino: Literal["intermediacao", "financeiro", "relatorio"]


class ConsultaPendencias(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filtros: FiltrosPendencias
    catalogo_acoes: list[AcaoPendencia]
    itens: list[ItemPendencia]
    total_pendencias: int = Field(ge=0)
    total_contratacoes: int = Field(ge=0)
    pendencias_operacionais: int = Field(ge=0)
    pendencias_financeiras: int = Field(ge=0)
    pendencias_conferencia: int = Field(ge=0)
    indicadores: IndicadoresPainel
    valor_contratado: Decimal
    deslocamento: int = Field(ge=0)
    limite: int = Field(ge=1, le=100)
    gerado_em: str
