from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class PagamentoContratacao(Base):
    __tablename__ = "pagamentos_contratacao"
    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_pagamentos_valor"),
        CheckConstraint(
            "forma_pagamento IN ('pix', 'transferencia', 'boleto', 'cartao', 'dinheiro', 'outro')",
            name="ck_pagamentos_forma",
        ),
        CheckConstraint(
            "status IN ('confirmado', 'cancelado')",
            name="ck_pagamentos_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contratacao_id: Mapped[int] = mapped_column(
        ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"),
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
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="confirmado", server_default="confirmado", index=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    paga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
