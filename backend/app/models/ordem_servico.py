from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class OrdemServico(Base):
    __tablename__ = "ordens_servico"
    __table_args__ = (
        UniqueConstraint("contratacao_id", name="uq_ordem_servico_contratacao"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("contratacoes_servico.id"), nullable=False, index=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes_servico.id"), nullable=False, index=True)
    cotacao_id: Mapped[int] = mapped_column(ForeignKey("cotacoes_fornecedor.id"), nullable=False, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    empresa_fornecedora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos_fabricacao.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id"), nullable=False, index=True)

    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="aberta", index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
