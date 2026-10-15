from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.painel_administrativo import FiltroPainel
from backend.app.schemas.relatorio_empresas import ItemEmpresa
from backend.app.schemas.resumo_gerencial import ResumoGerencial


class FiltrosComparativo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a_inicial: str
    a_final: str
    b_inicial: str
    b_final: str
    filtro: FiltroPainel
    busca: str
    periodo: Literal["a", "b"] | None = None


class ResumoPeriodoComparativo(ResumoGerencial):
    data_inicial: str
    data_final: str


class MedidaComparativa(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str
    descricao: str
    tipo: Literal["quantidade", "valor"]
    valor_a: Decimal
    valor_b: Decimal
    diferenca: Decimal
    variacao_percentual: Decimal | None


class ConsultaComparativo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filtros: FiltrosComparativo
    resumo_a: ResumoPeriodoComparativo
    resumo_b: ResumoPeriodoComparativo
    medidas: list[MedidaComparativa]
    periodos_sobrepostos: bool
    contratacoes_em_ambos: int = Field(ge=0)
    itens: list[ItemEmpresa]
    total: int = Field(ge=0)
    deslocamento: int = Field(ge=0)
    limite: int = Field(ge=1, le=100)
    gerado_em: str
