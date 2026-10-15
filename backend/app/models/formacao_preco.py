"""Preço ao cliente, custo reservado e histórico da intermediação comercial."""
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class ConfiguracaoPreco(Base):
    __tablename__ = 'configuracao_preco_d60'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[str] = mapped_column(String(100), nullable=False)
    ativada_em: Mapped[str] = mapped_column(String(40), nullable=False)
    segredo_verificacao: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (CheckConstraint('id=1', name='ck_configuracao_preco_id'),)


class FormacaoPreco(Base):
    __tablename__ = 'formacoes_preco_cotacao'
    cotacao_id: Mapped[int] = mapped_column(ForeignKey('cotacoes_fornecedor.id'), primary_key=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey('solicitacoes_servico.id'), nullable=False, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey('empresas.id'), nullable=False, index=True)
    custo_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    modo: Mapped[str] = mapped_column(String(12), nullable=False)
    acrescimo_informado: Mapped[str] = mapped_column(String(32), nullable=False)
    acrescimo_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    preco_cliente_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    despesas_previstas_centavos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    termos_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    estado: Mapped[str] = mapped_column(String(24), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    contratacao_id: Mapped[int | None] = mapped_column(ForeignKey('contratacoes_servico.id'), nullable=True, unique=True)
    atualizado_em: Mapped[str] = mapped_column(String(40), nullable=False)
    __table_args__ = (
        CheckConstraint("modo IN ('percentual','valor')", name='ck_formacao_modo'),
        CheckConstraint("estado IN ('rascunho','publicada','aprovada_cliente','revisao_cliente','recusada_cliente','retirada','contratada')", name='ck_formacao_estado'),
        CheckConstraint('custo_centavos>0 AND acrescimo_centavos>=0 AND preco_cliente_centavos=custo_centavos+acrescimo_centavos AND despesas_previstas_centavos>=0 AND versao>0', name='ck_formacao_valores'),
    )


class EventoFormacaoPreco(Base):
    __tablename__ = 'eventos_formacao_preco'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cotacao_id: Mapped[int] = mapped_column(ForeignKey('cotacoes_fornecedor.id'), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(24), nullable=False)
    usuario_id: Mapped[int] = mapped_column(Integer, nullable=False)
    perfil: Mapped[str] = mapped_column(String(12), nullable=False)
    registro: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[str] = mapped_column(String(40), nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    pedido_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resultado_json: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint('cotacao_id','versao',name='uq_evento_formacao_versao'),)
