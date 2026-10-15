from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class EventoDecisaoCotacaoAdmin(Base):
    __tablename__ = "eventos_decisoes_cotacao_admin"
    __table_args__ = (
        CheckConstraint("acao IN ('aceitar', 'recusar')", name="ck_decisao_cotacao_admin_acao"),
        CheckConstraint("usuario_admin_id > 0", name="ck_decisao_cotacao_admin_usuario"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"), index=True)
    cotacao_id: Mapped[int] = mapped_column(ForeignKey("cotacoes_fornecedor.id", ondelete="RESTRICT"), index=True)
    acao: Mapped[str] = mapped_column(String(16))
    usuario_admin_id: Mapped[int] = mapped_column(Integer)
    administrador_nome: Mapped[str] = mapped_column(String(200))
    registro_interno: Mapped[str] = mapped_column(Text)
    versao_anterior: Mapped[str] = mapped_column(String(64))
    chave_operacao: Mapped[str] = mapped_column(String(36), unique=True)
    resultado_json: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[str] = mapped_column(String(32))
