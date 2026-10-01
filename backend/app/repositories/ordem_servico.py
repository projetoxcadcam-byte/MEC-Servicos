from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.ordem_servico import OrdemServico


class RepositorioOrdemServico:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, ordem: OrdemServico) -> OrdemServico:
        self.banco.add(ordem)
        self.banco.commit()
        self.banco.refresh(ordem)
        return ordem

    def buscar(self, ordem_id: int) -> OrdemServico | None:
        return self.banco.get(OrdemServico, ordem_id)

    def buscar_por_contratacao(self, contratacao_id: int) -> OrdemServico | None:
        stmt = select(OrdemServico).where(OrdemServico.contratacao_id == contratacao_id)
        return self.banco.scalar(stmt)

    def listar(self) -> list[OrdemServico]:
        stmt = select(OrdemServico).order_by(OrdemServico.id)
        return list(self.banco.scalars(stmt).all())
