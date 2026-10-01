from __future__ import annotations
from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base

class MaterialFornecedor(Base):
    __tablename__ = "materiais_fornecedor"
    __table_args__ = (UniqueConstraint("empresa_id", "material_id", name="uq_material_fornecedor"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id", ondelete="RESTRICT"), nullable=False, index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
