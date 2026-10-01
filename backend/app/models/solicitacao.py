from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class SolicitacaoServico(Base):
    __tablename__ = "solicitacoes_servico"
    __table_args__ = (
        CheckConstraint(
            "dimensao_x_maxima_mm > 0",
            name="ck_solicitacoes_dimensao_x",
        ),
        CheckConstraint(
            "dimensao_y_maxima_mm > 0",
            name="ck_solicitacoes_dimensao_y",
        ),
        CheckConstraint(
            "dimensao_z_maxima_mm > 0",
            name="ck_solicitacoes_dimensao_z",
        ),
        CheckConstraint(
            "tolerancia_requerida_mm > 0",
            name="ck_solicitacoes_tolerancia",
        ),
        CheckConstraint(
            "quantidade > 0",
            name="ck_solicitacoes_quantidade",
        ),
        CheckConstraint(
            "status IN ('aberta', 'encerrada', 'cancelada')",
            name="ck_solicitacoes_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    empresa_cliente_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    processo_id: Mapped[int] = mapped_column(
        ForeignKey("processos_fabricacao.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[int] = mapped_column(
        ForeignKey("materiais.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dimensao_x_maxima_mm: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    dimensao_y_maxima_mm: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    dimensao_z_maxima_mm: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )
    tolerancia_requerida_mm: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="aberta",
        server_default="aberta",
    )
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
