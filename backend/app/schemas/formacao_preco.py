from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConferenciaPreco(BaseModel):
    model_config = ConfigDict(extra='forbid')
    modo: Literal['percentual','valor']
    acrescimo: Decimal = Field(ge=0,max_digits=16,decimal_places=4)
    despesas_previstas: Decimal = Field(default=Decimal('0'),ge=0,max_digits=14,decimal_places=2)
    versao: str = Field(pattern=r'^[0-9a-f]{64}$')
    @model_validator(mode='after')
    def conferir(self):
        if self.modo=='percentual' and self.acrescimo>1000:raise ValueError('O percentual deve estar entre zero e 1000.')
        if self.modo=='valor' and self.acrescimo*100 != (self.acrescimo*100).to_integral_value():raise ValueError('O valor em reais deve ter até duas casas decimais.')
        return self


class RegistroPreco(ConferenciaPreco):
    acao: Literal['salvar','publicar','retirar']
    conferencia: str = Field(pattern=r'^[0-9a-f]{64}$')
    registro_interno: str = Field(min_length=3,max_length=2000)
    chave_operacao: UUID


class AnalisePrecoCliente(BaseModel):
    model_config = ConfigDict(extra='forbid')
    empresa_cliente_id: int = Field(gt=0)
    acao: Literal['aprovar','revisar','recusar']
    versao: str = Field(pattern=r'^[0-9a-f]{64}$')
    observacao: str = Field(default='',max_length=2000)
    chave_operacao: UUID
