from __future__ import annotations
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base

class Material(Base):
    __tablename__ = "materiais"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    familia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    especificacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
