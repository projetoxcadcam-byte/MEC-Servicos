from __future__ import annotations
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base

class Maquina(Base):
    __tablename__ = "maquinas"
    __table_args__ = (UniqueConstraint("empresa_id", "nome", name="uq_maquina_empresa_nome"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos_fabricacao.id", ondelete="RESTRICT"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    fabricante: Mapped[str | None] = mapped_column(String(160), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(160), nullable=True)
    dimensao_x_maxima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    dimensao_y_maxima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    dimensao_z_maxima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    tolerancia_minima_mm: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
