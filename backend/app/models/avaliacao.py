
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class AvaliacaoOficina(Base):
    __tablename__ = "avaliacoes_oficina"
    __table_args__ = (
        UniqueConstraint(
            "contratacao_id",
            name="uq_avaliacao_oficina_contratacao",
        ),
        CheckConstraint(
            "nota >= 1 AND nota <= 5",
            name="ck_avaliacao_oficina_nota",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contratacao_id: Mapped[int] = mapped_column(
        ForeignKey("contratacoes_servico.id"),
        nullable=False,
        index=True,
    )
    ordem_servico_id: Mapped[int] = mapped_column(
        ForeignKey("ordens_servico.id"),
        nullable=False,
        index=True,
    )
    empresa_cliente_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id"),
        nullable=False,
        index=True,
    )
    empresa_fornecedora_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id"),
        nullable=False,
        index=True,
    )
    nota: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
