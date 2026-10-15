from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.painel_administrativo import IndicadoresPainel
from backend.app.schemas.relatorio_periodo import FiltrosPeriodo, ItemPeriodo

AgrupamentoEmpresas = Literal["clientes", "fornecedores"]


class FiltrosEmpresas(FiltrosPeriodo):
    agrupamento: AgrupamentoEmpresas
    empresa_id: int | None = Field(default=None, gt=0)


class ItemEmpresa(ItemPeriodo):
    empresa_cliente_id: int = Field(gt=0)
    empresa_fornecedora_id: int = Field(gt=0)


class GrupoEmpresa(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empresa_id: int = Field(gt=0)
    empresa: str
    valor_contratado: Decimal
    indicadores: IndicadoresPainel


class ConsultaEmpresas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filtros: FiltrosEmpresas
    indicadores: IndicadoresPainel
    valor_contratado: Decimal
    grupos: list[GrupoEmpresa]
    empresa_selecionada: GrupoEmpresa | None
    itens: list[ItemEmpresa]
    total_empresas: int = Field(ge=0)
    total_contratacoes: int = Field(ge=0)
    deslocamento: int = Field(ge=0)
    deslocamento_itens: int = Field(ge=0)
    limite: int = Field(ge=1, le=100)
    gerado_em: str
