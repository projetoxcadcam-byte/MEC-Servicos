from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel

OrdenacaoComparacao = Literal["valor", "prazo", "nota_cliente", "nota_admin"]
EscopoComparacao = Literal["disponiveis", "todas"]


class NotasFornecedorComparacao(BaseModel):
    quantidade: int
    media: str | None


class CotacaoComparacaoAdmin(BaseModel):
    cotacao_id: int
    empresa_fornecedora_id: int
    fornecedor: str
    valor_total: Decimal
    prazo_dias: int
    vence_em: str
    status: str
    pode_decidir: bool
    notas_cliente: NotasFornecedorComparacao
    notas_admin: NotasFornecedorComparacao


class ComparacaoCotacoesAdmin(BaseModel):
    contexto: str
    solicitacao_id: int
    versao: str
    consultado_em: str
    ordenacao: OrdenacaoComparacao
    escopo: EscopoComparacao
    total: int
    cotacoes_total: int
    cotacoes_disponiveis: int
    menor_valor_disponivel: Decimal | None
    menor_prazo_disponivel: int | None
    deslocamento: int
    limite: int
    itens: list[CotacaoComparacaoAdmin]
