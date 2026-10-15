from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class PreparacaoPdfCotacao(Base):
    __tablename__ = "preparacoes_pdf_cotacao"
    __table_args__ = (
        UniqueConstraint("arquivo_id", "versao", name="uq_preparacao_pdf_versao"),
        CheckConstraint("versao > 0 AND tamanho_bytes > 0", name="ck_preparacao_pdf_valores"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arquivo_id: Mapped[int] = mapped_column(ForeignKey("arquivos_tecnicos.id", ondelete="RESTRICT"), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_original: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caminho_arquivo: Mapped[str] = mapped_column(Text, nullable=False)
    configuracao_json: Mapped[str] = mapped_column(Text, nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text, nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    criado_em: Mapped[str] = mapped_column(String(32), nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    pedido_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class PublicacaoPdfCotacao(Base):
    __tablename__ = "publicacoes_pdf_cotacao"
    __table_args__ = (
        UniqueConstraint("arquivo_id", "versao_liberacao", name="uq_publicacao_pdf_versao"),
        CheckConstraint("versao_liberacao > 0", name="ck_publicacao_pdf_versao"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arquivo_id: Mapped[int] = mapped_column(ForeignKey("arquivos_tecnicos.id", ondelete="RESTRICT"), nullable=False, index=True)
    preparacao_id: Mapped[int] = mapped_column(ForeignKey("preparacoes_pdf_cotacao.id", ondelete="RESTRICT"), nullable=False)
    evento_id: Mapped[int] = mapped_column(ForeignKey("eventos_arquivos_cotacao.id", ondelete="RESTRICT"), nullable=False, unique=True)
    versao_liberacao: Mapped[int] = mapped_column(Integer, nullable=False)

