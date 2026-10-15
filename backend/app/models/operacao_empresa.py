from __future__ import annotations
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class OperacaoEmpresa(Base):
    __tablename__ = "operacoes_empresa"
    __table_args__ = (
        UniqueConstraint("empresa_id", "processo_id", name="uq_operacao_empresa_processo"),
        CheckConstraint("usuario_admin_id > 0", name="ck_operacao_empresa_admin"),
        CheckConstraint("ativo IN (0, 1)", name="ck_operacao_empresa_ativo"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos_fabricacao.id", ondelete="RESTRICT"), nullable=False, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    usuario_admin_id: Mapped[int] = mapped_column(nullable=False)
    atualizado_em: Mapped[str] = mapped_column(String(32), nullable=False)
