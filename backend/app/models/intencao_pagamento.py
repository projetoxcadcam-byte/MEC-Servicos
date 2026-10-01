from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class IntencaoPagamento(Base):
    __tablename__ = "intencoes_pagamento"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_intencoes_pagamento_idempotency_key"),
        UniqueConstraint("external_payment_id", name="uq_intencoes_pagamento_external_payment_id"),
        CheckConstraint(
            "status IN ('aguardando_pagamento', 'paga', 'falhou', 'cancelada')",
            name="ck_intencoes_pagamento_status",
        ),
        CheckConstraint(
            "forma_pagamento IN ('pix', 'transferencia', 'boleto', 'cartao', 'dinheiro', 'outro')",
            name="ck_intencoes_pagamento_forma",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contratacao_id: Mapped[int] = mapped_column(
        ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    empresa_cliente_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    empresa_fornecedora_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String(20), nullable=False)
    provedor: Mapped[str] = mapped_column(String(40), nullable=False, default="fake", server_default="fake")
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_payment_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="aguardando_pagamento", server_default="aguardando_pagamento", index=True
    )
    pagamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("pagamentos_contratacao.id", ondelete="SET NULL"), nullable=True, index=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    atualizada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    paga_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
