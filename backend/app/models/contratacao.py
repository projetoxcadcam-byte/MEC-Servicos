from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class ContratacaoServico(Base):
    __tablename__ = "contratacoes_servico"
    __table_args__ = (
        UniqueConstraint("solicitacao_id", name="uq_contratacao_solicitacao"),
        UniqueConstraint("cotacao_id", name="uq_contratacao_cotacao"),
        CheckConstraint(
            "status IN ('ativa', 'cancelada', 'encerrada')",
            name="ck_contratacoes_status",
        ),
        CheckConstraint("valor_total > 0", name="ck_contratacoes_valor_total"),
        CheckConstraint("prazo_dias > 0", name="ck_contratacoes_prazo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solicitacao_id: Mapped[int] = mapped_column(
        ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cotacao_id: Mapped[int] = mapped_column(
        ForeignKey("cotacoes_fornecedor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    empresa_cliente_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    empresa_fornecedora_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ativa",
        server_default="ativa",
    )
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    cancelada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    encerrada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
