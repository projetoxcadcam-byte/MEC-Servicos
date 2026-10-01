from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class ArquivoTecnico(Base):
    __tablename__ = "arquivos_tecnicos"
    __table_args__ = (
        CheckConstraint(
            "tamanho_bytes >= 0",
            name="ck_arquivos_tecnicos_tamanho",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    solicitacao_id: Mapped[int] = mapped_column(
        ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nome_original: Mapped[str] = mapped_column(String(255), nullable=False)
    extensao: Mapped[str] = mapped_column(String(10), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    caminho_arquivo: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
        index=True,
    )
