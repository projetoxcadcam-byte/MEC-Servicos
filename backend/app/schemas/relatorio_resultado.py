"""Retrato reservado do resultado e das despesas da administração."""
from typing import Annotated, Literal
from pydantic import BaseModel, Field

Dinheiro = Annotated[str, Field(pattern=r'^-?\d+\.\d{2}$')]
ID = Annotated[int, Field(gt=0)]

class ValoresResultado(BaseModel):
    venda_cliente: Dinheiro
    custo_fornecedor: Dinheiro
    ganho_bruto_previsto: Dinheiro
    despesas_previstas: Dinheiro
    resultado_previsto: Dinheiro
    ganho_bruto_confirmado: Dinheiro
    despesas_pagas: Dinheiro
    resultado_apos_despesas: Dinheiro
    resultado_liquidado_apos_despesas: Dinheiro

class ContratacaoResultado(ValoresResultado):
    contratacao_id: ID
    ordem_servico_id: ID | None
    cliente: str
    fornecedor: str
    criada_em: str
    liquidado: bool
    situacao: str

class DespesaResultado(BaseModel):
    id: ID
    contratacao_id: ID
    categoria: Literal['coleta', 'transporte', 'frete', 'embalagem', 'inspecao', 'outros']
    descricao: str
    valor: Dinheiro
    paga_em: str
    status: Literal['confirmada', 'estornada']
    referencia: str
    registro_interno: str
    administrador_nome: str
    criada_em: str
    estornada_em: str | None
    motivo_estorno: str | None
    referencia_estorno: str | None

class RelatorioResultado(BaseModel):
    contexto: str
    inicio: str
    fim: str
    base_periodo: Literal['criacao_contratacao_utc']
    gerado_em: str
    versao: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    total: Annotated[int, Field(ge=0)]
    liquidadas: Annotated[int, Field(ge=0)]
    totais: ValoresResultado
    itens: list[ContratacaoResultado]
    despesas: list[DespesaResultado]
    despesas_confirmadas: Annotated[int, Field(ge=0)]
    despesas_estornadas: Annotated[int, Field(ge=0)]
    valor_estornado: Dinheiro
