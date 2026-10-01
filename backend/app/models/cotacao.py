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


class CotacaoFornecedor(Base):
    __tablename__ = "cotacoes_fornecedor"
    __table_args__ = (
        UniqueConstraint(
            "solicitacao_id",
            "empresa_fornecedora_id",
            name="uq_cotacao_solicitacao_fornecedor",
        ),
        CheckConstraint("valor_total > 0", name="ck_cotacoes_valor_total"),
        CheckConstraint("prazo_dias > 0", name="ck_cotacoes_prazo"),
        CheckConstraint("validade_dias > 0", name="ck_cotacoes_validade"),
        CheckConstraint(
            "status IN ('enviada', 'aceita', 'recusada', 'expirada', 'cancelada')",
            name="ck_cotacoes_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solicitacao_id: Mapped[int] = mapped_column(
        ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"),
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
    validade_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="enviada",
        server_default="enviada",
    )
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    encerrada_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decidida_por_empresa_id: Mapped[int | None] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
