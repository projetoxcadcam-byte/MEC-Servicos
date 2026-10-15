from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.painel_administrativo import FiltroPainel, IndicadoresPainel
from backend.app.schemas.relatorio_empresas import ItemEmpresa


class FiltrosGerencial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ano: int = Field(ge=1, le=9999)
    filtro: FiltroPainel
    busca: str
    mes: int | None = Field(default=None, ge=1, le=12)


class ResumoGerencial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    indicadores: IndicadoresPainel
    valor_contratado: Decimal
    em_andamento: int = Field(ge=0)
    contratacoes_com_pendencias: int = Field(ge=0)
    pendencias_operacionais: int = Field(ge=0)
    pendencias_financeiras: int = Field(ge=0)
    pendencias_conferencia: int = Field(ge=0)


class MesGerencial(ResumoGerencial):
    mes: int = Field(ge=1, le=12)
    data_inicial: str
    data_final: str


class ConsultaGerencial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filtros: FiltrosGerencial
    resumo_ano: ResumoGerencial
    meses: list[MesGerencial]
    resumo_mes: MesGerencial | None
    itens: list[ItemEmpresa]
    total: int = Field(ge=0)
    deslocamento: int = Field(ge=0)
    limite: int = Field(ge=1, le=100)
    gerado_em: str
