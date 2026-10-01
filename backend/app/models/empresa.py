from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class Empresa(Base):
    __tablename__ = "empresas"
    __table_args__ = (
        CheckConstraint(
            "tipo_empresa IN ('cliente', 'fornecedor', 'ambos')",
            name="ck_empresas_tipo_empresa",
        ),
        CheckConstraint(
            "avaliacao IS NULL OR (avaliacao >= 0 AND avaliacao <= 5)",
            name="ck_empresas_avaliacao",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    razao_social: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    documento: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True
    )
    tipo_empresa: Mapped[str] = mapped_column(String(16), nullable=False)
    avaliacao: Mapped[float | None] = mapped_column(Float, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"Empresa(id={self.id!r}, razao_social={self.razao_social!r}, "
            f"documento={self.documento!r}, tipo_empresa={self.tipo_empresa!r})"
        )
