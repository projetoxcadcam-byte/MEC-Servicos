from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class ControleFinanceiro(Base):
    __tablename__ = "controles_financeiros_admin"
    __table_args__ = (
        CheckConstraint("valor_contratado_centavos > 0", name="ck_financeiro_valor"),
        CheckConstraint("versao > 0", name="ck_financeiro_versao"),
        CheckConstraint("status IN ('aberto','encerrado')", name="ck_financeiro_status"),
    )
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"), primary_key=True)
    valor_contratado_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[str] = mapped_column(String(40), nullable=False)
    atualizado_em: Mapped[str] = mapped_column(String(40), nullable=False)


class RepasseAdministrativo(Base):
    __tablename__ = "repasses_administrativos"
    __table_args__ = (
        CheckConstraint("valor_centavos > 0", name="ck_repasse_valor"),
        CheckConstraint("status IN ('confirmado','estornado')", name="ck_repasse_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("controles_financeiros_admin.contratacao_id", ondelete="RESTRICT"), nullable=False, index=True)
    valor_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    registrado_em: Mapped[str] = mapped_column(String(40), nullable=False)
    estornado_em: Mapped[str | None] = mapped_column(String(40))


class EventoFinanceiro(Base):
    __tablename__ = "eventos_financeiros_admin"
    __table_args__ = (
        UniqueConstraint("contratacao_id", "versao", name="uq_financeiro_evento_versao"),
        UniqueConstraint("contratacao_id", "chave_operacao", name="uq_financeiro_chave"),
        UniqueConstraint("contratacao_id", "referencia", name="uq_financeiro_referencia"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("controles_financeiros_admin.contratacao_id", ondelete="RESTRICT"), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(32), nullable=False)
    chave_operacao: Mapped[str | None] = mapped_column(String(36))
    resumo_operacao: Mapped[str | None] = mapped_column(String(64))
    pagamento_id: Mapped[int | None] = mapped_column(ForeignKey("pagamentos_contratacao.id", ondelete="RESTRICT"))
    repasse_id: Mapped[int | None] = mapped_column(ForeignKey("repasses_administrativos.id", ondelete="RESTRICT"))
    valor_centavos: Mapped[int | None] = mapped_column(Integer)
    usuario_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text, nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[str] = mapped_column(String(40), nullable=False)
