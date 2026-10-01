from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SolicitacaoServicoCriacao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    processo_id: int = Field(gt=0)
    material_id: int = Field(gt=0)
    dimensao_x_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    dimensao_y_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    dimensao_z_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    tolerancia_requerida_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    quantidade: int = Field(gt=0, le=10_000_000)
    observacoes: str | None = Field(default=None, max_length=5000)


class SolicitacaoServicoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_cliente_id: int
    processo_id: int
    material_id: int
    dimensao_x_maxima_mm: Decimal
    dimensao_y_maxima_mm: Decimal
    dimensao_z_maxima_mm: Decimal
    tolerancia_requerida_mm: Decimal
    quantidade: int
    observacoes: str | None
    status: str
    criada_em: datetime


class FornecedorCompativelLeitura(BaseModel):
    empresa_id: int
    razao_social: str
    tipo_empresa: str
    capacidade_id: int
    processo_id: int
    material_id: int
    dimensao_x_maxima_mm: Decimal
    dimensao_y_maxima_mm: Decimal
    dimensao_z_maxima_mm: Decimal
    tolerancia_minima_mm: Decimal
