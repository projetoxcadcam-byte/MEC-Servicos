from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class EntregaServico(Base):
    __tablename__ = "entregas_servico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(ForeignKey("ordens_servico.id", ondelete="CASCADE"), nullable=False, index=True)
    empresa_fornecedora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="entregue", index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivo_recusa: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    entregue_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    aceita_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recusada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
