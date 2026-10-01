from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class EventoGatewayPagamento(Base):
    __tablename__ = "eventos_gateway_pagamento"
    __table_args__ = (
        UniqueConstraint("provedor", "evento_id", name="uq_eventos_gateway_provedor_evento"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provedor: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    evento_id: Mapped[str] = mapped_column(String(120), nullable=False)
    intencao_pagamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("intencoes_pagamento.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_payment_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    tipo_evento: Mapped[str] = mapped_column(String(50), nullable=False)
    status_processamento: Mapped[str] = mapped_column(String(24), nullable=False, default="processado", server_default="processado")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    processado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
