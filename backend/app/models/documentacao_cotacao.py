from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class LiberacaoArquivoCotacao(Base):
    __tablename__ = "liberacoes_arquivos_cotacao"
    __table_args__ = (CheckConstraint("versao > 0", name="ck_liberacao_arquivo_versao"),)
    arquivo_id: Mapped[int] = mapped_column(ForeignKey("arquivos_tecnicos.id", ondelete="RESTRICT"), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    atualizado_em: Mapped[str] = mapped_column(String(32), nullable=False)


class EventoArquivoCotacao(Base):
    __tablename__ = "eventos_arquivos_cotacao"
    __table_args__ = (
        UniqueConstraint("arquivo_id", "versao", name="uq_evento_arquivo_versao"),
        CheckConstraint("versao > 0", name="ck_evento_arquivo_versao"),
        CheckConstraint("acao IN ('liberar','bloquear')", name="ck_evento_arquivo_acao"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arquivo_id: Mapped[int] = mapped_column(ForeignKey("arquivos_tecnicos.id", ondelete="RESTRICT"), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(16), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text, nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    criado_em: Mapped[str] = mapped_column(String(32), nullable=False)
