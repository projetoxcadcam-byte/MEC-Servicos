
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.empresa import Empresa


class RepositorioRankingFornecedores:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def listar(self) -> list[tuple[Empresa, int, float | None]]:
        linhas = self.banco.execute(
            select(
                Empresa,
                func.count(AvaliacaoOficina.id),
                func.avg(AvaliacaoOficina.nota),
            )
            .outerjoin(
                AvaliacaoOficina,
                AvaliacaoOficina.empresa_fornecedora_id == Empresa.id,
            )
            .where(Empresa.tipo_empresa == "fornecedor")
            .group_by(Empresa.id)
        ).all()

        dados = [
            (
                empresa,
                int(quantidade or 0),
                float(media) if media is not None else None,
            )
            for empresa, quantidade, media in linhas
        ]

        dados.sort(
            key=lambda item: (
                item[2] is None,
                -(item[2] if item[2] is not None else 0.0),
                -item[1],
                item[0].razao_social.casefold(),
                item[0].id,
            )
        )
        return dados
