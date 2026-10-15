"""D46: notas administrativas e autoria das novas notas de clientes.

As avaliações de clientes continuam na tabela D14, sem cópia ou conversão.
Os usuários pertencem ao banco de acesso; os identificadores são auditoria,
não chaves estrangeiras entre os dois bancos.
"""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class AutoriaAvaliacaoCliente(Base):
    __tablename__ = "autorias_avaliacoes_cliente"
    __table_args__ = (
        UniqueConstraint("chave_operacao", name="uq_autoria_avaliacao_operacao"),
        CheckConstraint("usuario_id > 0", name="ck_autoria_avaliacao_usuario"),
    )
    avaliacao_id: Mapped[int] = mapped_column(ForeignKey("avaliacoes_oficina.id", ondelete="RESTRICT"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_autor: Mapped[str] = mapped_column(String(120), nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36), nullable=False)
    resumo_operacao: Mapped[str] = mapped_column(String(64), nullable=False)


class AvaliacaoAdministrativa(Base):
    __tablename__ = "avaliacoes_administrativas"
    __table_args__ = (
        UniqueConstraint("contratacao_id", name="uq_avaliacao_admin_contratacao"),
        UniqueConstraint("chave_operacao", name="uq_avaliacao_admin_operacao"),
        CheckConstraint("nota >= 1 AND nota <= 5", name="ck_avaliacao_admin_nota"),
        CheckConstraint("usuario_id > 0", name="ck_avaliacao_admin_usuario"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"), nullable=False, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(ForeignKey("ordens_servico.id", ondelete="RESTRICT"), nullable=False, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False)
    empresa_fornecedora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True)
    nota: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[str] = mapped_column(String(40), nullable=False)
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_autor: Mapped[str] = mapped_column(String(120), nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36), nullable=False)
    resumo_operacao: Mapped[str] = mapped_column(String(64), nullable=False)
