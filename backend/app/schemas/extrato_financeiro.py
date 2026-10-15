from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel

FiltroExtrato = Literal["todos", "recebimentos", "repasses", "estornos"]
TipoMovimentoExtrato = Literal["recebimento", "repasse", "estorno_recebimento", "estorno_repasse"]


class FiltrosExtrato(BaseModel):
    data_inicial: str | None
    data_final: str | None
    tipo: FiltroExtrato
    busca: str
    contratacao_id: int | None


class ItemExtrato(BaseModel):
    tipo: TipoMovimentoExtrato
    movimento_id: int
    contratacao_id: int
    ordem_servico_id: int | None
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    cliente: str
    fornecedor: str
    financeiro_status: Literal["sem_controle", "aberto", "encerrado"]
    situacao_atual: Literal["confirmado", "estornado"]
    data_utc: str
    data_original_utc: str
    estornado_em_utc: str | None
    forma_pagamento: str
    valor: Decimal
    efeito_liquido: Decimal


class ResumoExtrato(BaseModel):
    recebimentos_brutos: Decimal
    estornos_recebimentos: Decimal
    recebimentos_liquidos: Decimal
    repasses_brutos: Decimal
    estornos_repasses: Decimal
    repasses_liquidos: Decimal
    entradas: Decimal
    saidas: Decimal
    resultado_periodo: Decimal
    total_movimentos: int
    total_contratacoes: int


class ConsultaExtrato(BaseModel):
    filtros: FiltrosExtrato
    resumo: ResumoExtrato
    itens: list[ItemExtrato]
    total: int
    deslocamento: int
    limite: int
    gerado_em: str
