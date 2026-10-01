
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.ranking_fornecedor import RankingFornecedoresResposta
from backend.app.services.ranking_fornecedor import ServicoRankingFornecedores


roteador = APIRouter(tags=["ranking-fornecedores"])


@roteador.get(
    "/fornecedores/ranking",
    response_model=RankingFornecedoresResposta,
)
def obter_ranking_fornecedores(
    banco: Session = Depends(obter_banco),
) -> RankingFornecedoresResposta:
    return ServicoRankingFornecedores(banco).obter_ranking()
