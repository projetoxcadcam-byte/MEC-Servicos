from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.documentacao_cotacao import ArquivoDocumentacao


class SolicitacaoComercial(BaseModel):
    id: int
    empresa_cliente_id: int
    cliente: str
    processo: str
    material: str
    dimensao_x_maxima_mm: Decimal
    dimensao_y_maxima_mm: Decimal
    dimensao_z_maxima_mm: Decimal
    tolerancia_requerida_mm: Decimal
    quantidade: int
    observacoes: str | None
    status: str
    criada_em: str
    cotacoes_total: int
    cotacoes_aceitas: int
    arquivos_ativos: int
    contratacao_id: int | None


class CotacaoComercial(BaseModel):
    id: int
    solicitacao_id: int
    empresa_cliente_id: int
    cliente: str
    empresa_fornecedora_id: int
    fornecedor: str
    processo: str
    material: str
    valor_total: Decimal
    prazo_dias: int
    validade_dias: int
    observacoes: str | None
    status: str
    status_registrado: str
    criada_em: str
    vence_em: str
    encerrada_em: str | None
    contratacao_id: int | None
    pode_decidir: bool
    preco_cliente_estado: str | None = None
    pode_aceitar: bool = True


class EventoDecisaoComercial(BaseModel):
    id: int
    solicitacao_id: int
    cotacao_id: int
    acao: str
    administrador_nome: str
    registro_interno: str
    criado_em: str
    cotacoes_recusadas: list[int]
    cotacoes_expiradas: list[int]


class DetalheSolicitacaoComercial(BaseModel):
    solicitacao: SolicitacaoComercial
    cotacoes: list[CotacaoComercial]
    arquivos: list[ArquivoDocumentacao]
    historico: list[EventoDecisaoComercial]
    versao: str


class PaginaSolicitacoesComerciais(BaseModel):
    itens: list[SolicitacaoComercial]
    total: int
    deslocamento: int
    limite: int


class PaginaCotacoesComerciais(BaseModel):
    itens: list[CotacaoComercial]
    total: int
    deslocamento: int
    limite: int


class DecisaoComercial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acao: Literal["aceitar", "recusar"]
    versao: str = Field(pattern=r"^[0-9a-f]{64}$")
    registro_interno: str = Field(min_length=3, max_length=2000)
    chave_operacao: UUID


class ResultadoDecisaoComercial(BaseModel):
    evento_id: int
    solicitacao_id: int
    cotacao_id: int
    status: str
    administrador_nome: str
    criado_em: str
    cotacoes_recusadas: list[int]
    cotacoes_expiradas: list[int]
