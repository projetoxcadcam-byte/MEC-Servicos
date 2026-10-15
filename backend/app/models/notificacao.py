from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class NotificacaoPerfil(Base):
    """Mensagem pública de um evento, dirigida a um perfil de uma empresa."""
    __tablename__ = "notificacoes_perfis"
    __table_args__ = (
        UniqueConstraint("chave_evento", "perfil_destino", "empresa_destino", name="uq_notificacao_evento_destino"),
        CheckConstraint("perfil_destino IN ('admin','cliente','fornecedor')", name="ck_notificacao_perfil"),
        CheckConstraint("perfil_origem IN ('admin','cliente','fornecedor')", name="ck_notificacao_origem"),
        CheckConstraint("(perfil_destino = 'admin' AND empresa_destino = 0) OR "
                        "(perfil_destino IN ('cliente','fornecedor') AND empresa_destino > 0)", name="ck_notificacao_empresa"),
        Index("ix_notificacoes_destino_id", "perfil_destino", "empresa_destino", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chave_evento: Mapped[str] = mapped_column(String(160), nullable=False)
    perfil_destino: Mapped[str] = mapped_column(String(16), nullable=False)
    empresa_destino: Mapped[int] = mapped_column(Integer, nullable=False)
    perfil_origem: Mapped[str] = mapped_column(String(16), nullable=False)
    assunto: Mapped[str] = mapped_column(String(160), nullable=False)
    mensagem: Mapped[str] = mapped_column(String(500), nullable=False)
    destino: Mapped[str] = mapped_column(String(200), nullable=False)
    solicitacao_id: Mapped[int | None] = mapped_column(Integer)
    contratacao_id: Mapped[int | None] = mapped_column(Integer)
    ordem_servico_id: Mapped[int | None] = mapped_column(Integer)
    criada_em: Mapped[str] = mapped_column(String(40), nullable=False)


class LeituraNotificacao(Base):
    """A leitura pertence à conta; outra pessoa da empresa continua com seu aviso."""
    __tablename__ = "leituras_notificacoes"
    __table_args__ = (
        CheckConstraint("usuario_id > 0", name="ck_leitura_usuario"),
        CheckConstraint("perfil IN ('admin','cliente','fornecedor')", name="ck_leitura_perfil"),
        CheckConstraint("(perfil = 'admin' AND empresa_id = 0) OR "
                        "(perfil IN ('cliente','fornecedor') AND empresa_id > 0)", name="ck_leitura_empresa"),
    )
    notificacao_id: Mapped[int] = mapped_column(ForeignKey("notificacoes_perfis.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    perfil: Mapped[str] = mapped_column(String(16), primary_key=True)
    empresa_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lida_em: Mapped[str] = mapped_column(String(40), nullable=False)
