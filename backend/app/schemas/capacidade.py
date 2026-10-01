from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

class CapacidadeCriacao(BaseModel):
    processo_id: int = Field(gt=0)
    dimensao_x_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    dimensao_y_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    dimensao_z_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    tolerancia_minima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    observacoes: str | None = Field(default=None, max_length=3000)

class CapacidadeLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    empresa_id: int
    processo_id: int
    dimensao_x_maxima_mm: Decimal
    dimensao_y_maxima_mm: Decimal
    dimensao_z_maxima_mm: Decimal
    tolerancia_minima_mm: Decimal
    observacoes: str | None

class MaquinaCriacao(BaseModel):
    processo_id: int = Field(gt=0)
    nome: str = Field(min_length=2, max_length=160)
    fabricante: str | None = Field(default=None, max_length=160)
    modelo: str | None = Field(default=None, max_length=160)
    dimensao_x_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    dimensao_y_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    dimensao_z_maxima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    tolerancia_minima_mm: Decimal = Field(gt=0, max_digits=12, decimal_places=4)

class MaquinaLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    empresa_id: int
    processo_id: int
    nome: str
    fabricante: str | None
    modelo: str | None
    dimensao_x_maxima_mm: Decimal
    dimensao_y_maxima_mm: Decimal
    dimensao_z_maxima_mm: Decimal
    tolerancia_minima_mm: Decimal

class MaterialFornecedorCriacao(BaseModel):
    material_id: int = Field(gt=0)
    observacoes: str | None = Field(default=None, max_length=3000)

class MaterialFornecedorLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    empresa_id: int
    material_id: int
    observacoes: str | None
