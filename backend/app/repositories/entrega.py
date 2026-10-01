from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.entrega import EntregaServico


class RepositorioEntrega:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, item: EntregaServico) -> EntregaServico:
        self.banco.add(item)
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def buscar(self, entrega_id: int) -> EntregaServico | None:
        return self.banco.get(EntregaServico, entrega_id)

    def listar_por_ordem(self, ordem_servico_id: int) -> list[EntregaServico]:
        stmt = select(EntregaServico).where(EntregaServico.ordem_servico_id == ordem_servico_id).order_by(EntregaServico.id)
        return list(self.banco.scalars(stmt).all())

    def pendente_por_ordem(self, ordem_servico_id: int) -> EntregaServico | None:
        stmt = (
            select(EntregaServico)
            .where(EntregaServico.ordem_servico_id == ordem_servico_id, EntregaServico.status == "entregue")
            .order_by(EntregaServico.id.desc())
            .limit(1)
        )
        return self.banco.scalar(stmt)
