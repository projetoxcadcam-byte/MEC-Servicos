from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.etapa_producao import EtapaProducao


class RepositorioEtapaProducao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, item: EtapaProducao) -> EtapaProducao:
        self.banco.add(item)
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def listar_por_ordem(self, ordem_servico_id: int) -> list[EtapaProducao]:
        stmt = (
            select(EtapaProducao)
            .where(EtapaProducao.ordem_servico_id == ordem_servico_id)
            .order_by(EtapaProducao.id)
        )
        return list(self.banco.scalars(stmt).all())

    def atual(self, ordem_servico_id: int) -> EtapaProducao | None:
        stmt = (
            select(EtapaProducao)
            .where(EtapaProducao.ordem_servico_id == ordem_servico_id)
            .order_by(EtapaProducao.id.desc())
            .limit(1)
        )
        return self.banco.scalar(stmt)
