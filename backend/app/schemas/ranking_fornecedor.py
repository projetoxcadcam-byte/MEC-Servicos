
from __future__ import annotations

from pydantic import BaseModel


class RankingFornecedorItem(BaseModel):
    posicao: int
    empresa_id: int
    razao_social: str
    quantidade_avaliacoes: int
    media_nota: float | None


class RankingFornecedoresResposta(BaseModel):
    total_fornecedores: int
    fornecedores_avaliados: int
    itens: list[RankingFornecedorItem]
