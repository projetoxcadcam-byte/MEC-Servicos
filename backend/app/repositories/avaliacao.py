
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.avaliacao import AvaliacaoOficina


class RepositorioAvaliacaoOficina:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def obter_por_id(self, avaliacao_id: int) -> AvaliacaoOficina | None:
        return self.banco.get(AvaliacaoOficina, avaliacao_id)

    def obter_por_contratacao(self, contratacao_id: int) -> AvaliacaoOficina | None:
        return self.banco.scalar(
            select(AvaliacaoOficina).where(
                AvaliacaoOficina.contratacao_id == contratacao_id
            )
        )

    def listar_por_fornecedor(self, empresa_fornecedora_id: int) -> list[AvaliacaoOficina]:
        return list(
            self.banco.scalars(
                select(AvaliacaoOficina)
                .where(
                    AvaliacaoOficina.empresa_fornecedora_id
                    == empresa_fornecedora_id
                )
                .order_by(AvaliacaoOficina.criada_em.desc())
            )
        )

    def criar(self, avaliacao: AvaliacaoOficina) -> AvaliacaoOficina:
        self.banco.add(avaliacao)
        self.banco.commit()
        self.banco.refresh(avaliacao)
        return avaliacao

    def reputacao(
        self, empresa_fornecedora_id: int
    ) -> tuple[int, float | None]:
        quantidade, media = self.banco.execute(
            select(
                func.count(AvaliacaoOficina.id),
                func.avg(AvaliacaoOficina.nota),
            ).where(
                AvaliacaoOficina.empresa_fornecedora_id
                == empresa_fornecedora_id
            )
        ).one()

        return int(quantidade or 0), (
            float(media) if media is not None else None
        )
