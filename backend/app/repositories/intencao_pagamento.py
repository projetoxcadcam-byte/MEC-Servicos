from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.intencao_pagamento import IntencaoPagamento
from backend.app.models.evento_gateway_pagamento import EventoGatewayPagamento


class RepositorioIntencaoPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, item: IntencaoPagamento) -> IntencaoPagamento:
        self.banco.add(item)
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def buscar(self, intencao_id: int) -> IntencaoPagamento | None:
        return self.banco.get(IntencaoPagamento, intencao_id)

    def buscar_por_idempotency(self, chave: str) -> IntencaoPagamento | None:
        stmt = select(IntencaoPagamento).where(IntencaoPagamento.idempotency_key == chave)
        return self.banco.scalar(stmt)

    def buscar_por_external_id(self, external_payment_id: str) -> IntencaoPagamento | None:
        stmt = select(IntencaoPagamento).where(IntencaoPagamento.external_payment_id == external_payment_id)
        return self.banco.scalar(stmt)


class RepositorioEventoGatewayPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def buscar(self, provedor: str, evento_id: str) -> EventoGatewayPagamento | None:
        stmt = select(EventoGatewayPagamento).where(
            EventoGatewayPagamento.provedor == provedor,
            EventoGatewayPagamento.evento_id == evento_id,
        )
        return self.banco.scalar(stmt)

    def criar(self, item: EventoGatewayPagamento) -> EventoGatewayPagamento:
        self.banco.add(item)
        self.banco.commit()
        self.banco.refresh(item)
        return item
