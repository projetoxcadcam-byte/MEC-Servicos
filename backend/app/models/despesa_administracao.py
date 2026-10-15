"""Despesas pagas da intermediação, reservadas à administração."""
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base

class ConfiguracaoDespesas(Base):
    __tablename__ = 'configuracao_despesas_d61'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[str] = mapped_column(String(100), nullable=False)
    ativada_em: Mapped[str] = mapped_column(String(40), nullable=False)
    __table_args__ = (CheckConstraint('id=1',name='ck_configuracao_despesas_id'),)

class DespesaAdministracao(Base):
    __tablename__ = 'despesas_administracao'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey('contratacoes_servico.id'),nullable=False,index=True)
    categoria: Mapped[str] = mapped_column(String(16),nullable=False)
    descricao: Mapped[str] = mapped_column(String(300),nullable=False)
    valor_centavos: Mapped[int] = mapped_column(Integer,nullable=False)
    paga_em: Mapped[str] = mapped_column(String(10),nullable=False)
    referencia: Mapped[str] = mapped_column(String(200),nullable=False)
    status: Mapped[str] = mapped_column(String(12),nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer,nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120),nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text,nullable=False)
    criada_em: Mapped[str] = mapped_column(String(40),nullable=False)
    estornada_em: Mapped[str|None] = mapped_column(String(40),nullable=True)
    __table_args__ = (
        CheckConstraint("categoria IN ('coleta','transporte','frete','embalagem','inspecao','outros')",name='ck_despesa_categoria'),
        CheckConstraint('valor_centavos>0 AND valor_centavos<=99999999999999',name='ck_despesa_valor'),
        CheckConstraint("(status='confirmada' AND estornada_em IS NULL) OR (status='estornada' AND estornada_em IS NOT NULL)",name='ck_despesa_estado'),
    )

class EventoDespesaAdministracao(Base):
    __tablename__ = 'eventos_despesas_administracao'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey('contratacoes_servico.id'),nullable=False,index=True)
    despesa_id: Mapped[int] = mapped_column(ForeignKey('despesas_administracao.id'),nullable=False,index=True)
    versao: Mapped[int] = mapped_column(Integer,nullable=False)
    acao: Mapped[str] = mapped_column(String(12),nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer,nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120),nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text,nullable=False)
    referencia: Mapped[str] = mapped_column(String(200),nullable=False)
    criado_em: Mapped[str] = mapped_column(String(40),nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36),nullable=False,unique=True)
    pedido_sha256: Mapped[str] = mapped_column(String(64),nullable=False)
    resultado_json: Mapped[str] = mapped_column(Text,nullable=False)
    __table_args__ = (UniqueConstraint('contratacao_id','versao',name='uq_evento_despesa_versao'),CheckConstraint("acao IN ('registrar','estornar') AND versao>0",name='ck_evento_despesa_acao'),)
