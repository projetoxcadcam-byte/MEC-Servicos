
from __future__ import annotations

from backend.app.repositories.ranking_fornecedor import RepositorioRankingFornecedores
from backend.app.schemas.ranking_fornecedor import (
    RankingFornecedorItem,
    RankingFornecedoresResposta,
)


class ServicoRankingFornecedores:
    def __init__(self, banco) -> None:
        self.repositorio = RepositorioRankingFornecedores(banco)

    def obter_ranking(self) -> RankingFornecedoresResposta:
        dados = self.repositorio.listar()
        itens = [
            RankingFornecedorItem(
                posicao=posicao,
                empresa_id=empresa.id,
                razao_social=empresa.razao_social,
                quantidade_avaliacoes=quantidade,
                media_nota=round(media, 2) if media is not None else None,
            )
            for posicao, (empresa, quantidade, media) in enumerate(dados, start=1)
        ]
        return RankingFornecedoresResposta(
            total_fornecedores=len(itens),
            fornecedores_avaliados=sum(
                1 for item in itens if item.quantidade_avaliacoes > 0
            ),
            itens=itens,
        )
