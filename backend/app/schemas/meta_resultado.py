"""Contrato reservado para planejar e acompanhar o resultado mensal."""
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.app.schemas.relatorio_resultado import Dinheiro, ValoresResultado

Mes = Annotated[str,Field(pattern=r'^(?:19\d{2}|[2-9]\d{3})-(?:0[1-9]|1[0-2])$')]
Versao = Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]
Quantidade = Annotated[int,Field(ge=0)]

class OperacaoMeta(BaseModel):
    model_config=ConfigDict(extra='forbid')
    acao: Literal['definir','retirar']
    valor: Decimal|None=Field(None,ge=0,max_digits=14,decimal_places=2,allow_inf_nan=False)
    versao: Versao
    chave_operacao: UUID
    registro_interno: str=Field(min_length=3,max_length=2000)
    @field_validator('registro_interno')
    @classmethod
    def texto(cls,v):
        v=v.strip()
        if len(v)<3:raise ValueError('Informe o motivo da definição, alteração ou retirada da meta.')
        return v
    @model_validator(mode='after')
    def conferir_acao(self):
        if self.acao=='definir' and self.valor is None:raise ValueError('Informe o valor da meta.')
        if self.acao=='retirar' and self.valor is not None:raise ValueError('A retirada não recebe um novo valor.')
        return self

class MetaAtual(BaseModel):
    valor: Dinheiro
    estado: Literal['ativa','retirada']
    administrador_nome: str
    atualizada_em: str

class EventoMeta(BaseModel):
    id: Annotated[int,Field(gt=0)]
    versao: Annotated[int,Field(gt=0)]
    acao: Literal['definir','retirar']
    valor_anterior: Dinheiro|None
    valor_atual: Dinheiro|None
    administrador_nome: str
    registro_interno: str
    criado_em: str

class DetalheMeta(BaseModel):
    contexto: str
    mes: Mes
    versao: Versao
    meta: MetaAtual|None
    total_eventos: Quantidade
    deslocamento: Quantidade
    limite: Annotated[int,Field(gt=0)]
    historico: list[EventoMeta]

class ComparacaoMes(BaseModel):
    mes: Mes
    nome: str
    fase: Literal['encerrado','em_andamento','futuro']
    total: Quantidade
    liquidadas: Quantidade
    totais: ValoresResultado
    meta: Dinheiro|None
    diferenca: Dinheiro|None
    atingimento_percentual: Dinheiro|None
    situacao: Literal['sem_meta','meta_zero','alcancada','abaixo']

class ComparacaoMetas(BaseModel):
    contexto: str
    ano: Annotated[int,Field(ge=1900,le=9998)]
    base_periodo: Literal['criacao_contratacao_utc']
    base_meta: Literal['resultado_liquidado_apos_despesas']
    consulta_em: str
    hoje_utc: str
    versao: Versao
    total: Quantidade
    liquidadas: Quantidade
    totais: ValoresResultado
    meses_com_meta: Quantidade
    meta_total: Dinheiro|None
    realizado_com_meta: Dinheiro
    diferenca_total: Dinheiro|None
    atingimento_total_percentual: Dinheiro|None
    meses: list[ComparacaoMes]
