from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

FiltroPainel = Literal["todas", "operacionais", "financeiras", "verificar", "concluidas", "canceladas"]


class PendenciaPainel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str
    area: Literal["operacional", "financeira", "conferencia"]
    descricao: str


class ItemPainel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contratacao_id: int
    solicitacao_id: int
    ordem_servico_id: int | None
    cliente: str
    fornecedor: str
    contratacao_status: str
    ordem_status: str | None
    etapa_administrativa: str | None
    etapa_producao: str | None
    financeiro_status: Literal["sem_controle", "aberto", "encerrado"]
    situacao: Literal["em_andamento", "concluida", "cancelada", "verificar"]
    valor_contratado: Decimal
    total_recebido: Decimal
    total_repassado: Decimal
    saldo_cliente: Decimal
    saldo_fornecedor: Decimal
    disponivel_repasse: Decimal
    entrega_concluida: bool
    atualizado_em: str | None
    pendencias: list[PendenciaPainel]


class IndicadoresPainel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_contratacoes: int = Field(ge=0)
    contratacoes_ativas: int = Field(ge=0)
    acompanhamento_operacional: int = Field(ge=0)
    pendencias_financeiras: int = Field(ge=0)
    para_conferencia: int = Field(ge=0)
    contratacoes_concluidas: int = Field(ge=0)
    contratacoes_canceladas: int = Field(ge=0)
    financeiros_encerrados: int = Field(ge=0)
    controles_abertos: int = Field(ge=0)
    recebimentos_confirmados: Decimal
    repasses_confirmados: Decimal
    saldo_clientes_controles_abertos: Decimal
    saldo_fornecedores_controles_abertos: Decimal
    disponivel_repasses: Decimal


class ConsultaPainel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    indicadores: IndicadoresPainel
    itens: list[ItemPainel]
    total: int = Field(ge=0)
    deslocamento: int = Field(ge=0)
    limite: int = Field(ge=1, le=100)
    filtro: FiltroPainel
    busca: str
    atualizado_em: str
