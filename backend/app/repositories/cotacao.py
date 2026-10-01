from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.cotacao import CotacaoFornecedor


class RepositorioCotacao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, cotacao: CotacaoFornecedor) -> CotacaoFornecedor:
        self.banco.add(cotacao)
        self.banco.commit()
        self.banco.refresh(cotacao)
        return cotacao

    def buscar(
        self,
        solicitacao_id: int,
        cotacao_id: int,
    ) -> CotacaoFornecedor | None:
        consulta = select(CotacaoFornecedor).where(
            CotacaoFornecedor.id == cotacao_id,
            CotacaoFornecedor.solicitacao_id == solicitacao_id,
        )
        return self.banco.scalar(consulta)

    def listar_por_solicitacao(
        self,
        solicitacao_id: int,
    ) -> list[CotacaoFornecedor]:
        consulta = (
            select(CotacaoFornecedor)
            .where(CotacaoFornecedor.solicitacao_id == solicitacao_id)
            .order_by(CotacaoFornecedor.id)
        )
        return list(self.banco.scalars(consulta).all())

    def listar_pendentes(
        self,
        solicitacao_id: int,
    ) -> list[CotacaoFornecedor]:
        consulta = (
            select(CotacaoFornecedor)
            .where(
                CotacaoFornecedor.solicitacao_id == solicitacao_id,
                CotacaoFornecedor.status == "enviada",
            )
            .order_by(CotacaoFornecedor.id)
        )
        return list(self.banco.scalars(consulta).all())

    def listar_aceitas(
        self,
        solicitacao_id: int,
    ) -> list[CotacaoFornecedor]:
        consulta = (
            select(CotacaoFornecedor)
            .where(
                CotacaoFornecedor.solicitacao_id == solicitacao_id,
                CotacaoFornecedor.status == "aceita",
            )
            .order_by(CotacaoFornecedor.id)
        )
        return list(self.banco.scalars(consulta).all())
