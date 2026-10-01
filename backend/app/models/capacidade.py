from __future__ import annotations
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base

class CapacidadeFornecedor(Base):
    __tablename__ = "capacidades_fornecedor"
    __table_args__ = (UniqueConstraint("empresa_id", "processo_id", name="uq_capacidade_empresa_processo"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos_fabricacao.id", ondelete="RESTRICT"), nullable=False, index=True)
    dimensao_x_maxima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    dimensao_y_maxima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    dimensao_z_maxima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    tolerancia_minima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
