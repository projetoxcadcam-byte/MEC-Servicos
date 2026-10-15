from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class EventoContratacaoAdmin(Base):
    __tablename__ = "eventos_contratacoes_admin"
    __table_args__ = (
        UniqueConstraint("chave_operacao", name="uq_contratacao_admin_chave"),
        CheckConstraint("acao IN ('contratar_e_abrir_os','abrir_os')", name="ck_contratacao_admin_acao"),
        CheckConstraint("usuario_admin_id > 0", name="ck_contratacao_admin_usuario"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"), nullable=False, index=True)
    cotacao_id: Mapped[int] = mapped_column(ForeignKey("cotacoes_fornecedor.id", ondelete="RESTRICT"), nullable=False, index=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"), nullable=False, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(ForeignKey("ordens_servico.id", ondelete="RESTRICT"), nullable=False, index=True)
    acao: Mapped[str] = mapped_column(String(32), nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text, nullable=False)
    observacoes_execucao: Mapped[str | None] = mapped_column(Text)
    versao_anterior: Mapped[str] = mapped_column(String(64), nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36), nullable=False)
    resultado_json: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[str] = mapped_column(String(40), nullable=False)
