from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico


class RepositorioContratacao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, contratacao: ContratacaoServico) -> ContratacaoServico:
        self.banco.add(contratacao)
        self.banco.commit()
        self.banco.refresh(contratacao)
        return contratacao

    def buscar_por_solicitacao(
        self,
        solicitacao_id: int,
    ) -> ContratacaoServico | None:
        consulta = select(ContratacaoServico).where(
            ContratacaoServico.solicitacao_id == solicitacao_id,
        )
        return self.banco.scalar(consulta)
