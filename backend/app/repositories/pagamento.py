from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.pagamento import PagamentoContratacao


class RepositorioPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, pagamento: PagamentoContratacao) -> PagamentoContratacao:
        self.banco.add(pagamento)
        self.banco.commit()
        self.banco.refresh(pagamento)
        return pagamento

    def buscar(self, pagamento_id: int) -> PagamentoContratacao | None:
        return self.banco.get(PagamentoContratacao, pagamento_id)

    def listar_por_contratacao(self, contratacao_id: int) -> list[PagamentoContratacao]:
        stmt = (
            select(PagamentoContratacao)
            .where(PagamentoContratacao.contratacao_id == contratacao_id)
            .order_by(PagamentoContratacao.id)
        )
        return list(self.banco.scalars(stmt).all())
