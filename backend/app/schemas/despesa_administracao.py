from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class OperacaoDespesa(BaseModel):
    model_config=ConfigDict(extra='forbid')
    versao: str=Field(pattern=r'^[a-f0-9]{64}$')
    chave_operacao: UUID
    registro_interno: str=Field(min_length=3,max_length=2000)
    referencia: str=Field(min_length=3,max_length=200)
    @field_validator('registro_interno','referencia')
    @classmethod
    def texto(cls,v):
        v=v.strip()
        if len(v)<3:raise ValueError('Informe ao menos três caracteres.')
        return v

class RegistroDespesa(OperacaoDespesa):
    categoria: Literal['coleta','transporte','frete','embalagem','inspecao','outros']
    descricao: str=Field(min_length=3,max_length=300)
    valor: Decimal=Field(gt=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    paga_em: date=Field(ge=date(1900,1,1))
    @field_validator('descricao')
    @classmethod
    def descricao_valida(cls,v):
        v=v.strip()
        if len(v)<3:raise ValueError('Informe a descrição da despesa.')
        return v
    @field_validator('paga_em')
    @classmethod
    def data_valida(cls,v):
        if v>datetime.now(timezone.utc).date():raise ValueError('Informe uma despesa já paga, sem data futura.')
        return v

class EstornoDespesa(OperacaoDespesa):
    pass
