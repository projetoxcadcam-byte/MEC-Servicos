from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class EtapaProducao(Base):
    __tablename__ = "etapas_producao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(
        ForeignKey("ordens_servico.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    empresa_fornecedora_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id"),
        nullable=False,
        index=True,
    )
    etapa: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
