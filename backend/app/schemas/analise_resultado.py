"""Análise agrupada, exclusiva da administração."""
from typing import Annotated, Literal
from pydantic import BaseModel, Field
from backend.app.schemas.relatorio_resultado import ContratacaoResultado, ValoresResultado, ID

Quantidade = Annotated[int, Field(ge=0)]

class EmpresaAnalise(BaseModel):
    id: ID
    nome: str

class FiltrosAnalise(BaseModel):
    empresa_cliente_id: ID | None
    empresa_fornecedora_id: ID | None
    liquidacao: Literal['todas', 'liquidadas', 'aguardando']

class GrupoResultado(BaseModel):
    chave: str
    empresa_id: ID | None
    nome: str
    total: Quantidade
    liquidadas: Quantidade
    totais: ValoresResultado

class ContratacaoAnalise(ContratacaoResultado):
    empresa_cliente_id: ID
    empresa_fornecedora_id: ID

class AnaliseResultado(BaseModel):
    contexto: str
    inicio: str
    fim: str
    base_periodo: Literal['criacao_contratacao_utc']
    gerado_em: str
    versao: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    filtros: FiltrosAnalise
    opcoes_clientes: list[EmpresaAnalise]
    opcoes_fornecedores: list[EmpresaAnalise]
    total_periodo: Quantidade
    total: Quantidade
    liquidadas: Quantidade
    totais: ValoresResultado
    meses: list[GrupoResultado]
    clientes: list[GrupoResultado]
    fornecedores: list[GrupoResultado]
    itens: list[ContratacaoAnalise]
