"""Metas mensais de resultado e alterações auditadas, exclusivas do ADM."""
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base

class ConfiguracaoMetas(Base):
    __tablename__ = 'configuracao_metas_d64'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    revision: Mapped[str] = mapped_column(String(100),nullable=False)
    ativada_em: Mapped[str] = mapped_column(String(40),nullable=False)
    __table_args__ = (CheckConstraint('id=1',name='ck_configuracao_metas_id'),)

class MetaResultado(Base):
    __tablename__ = 'metas_resultado_administracao'
    mes: Mapped[str] = mapped_column(String(7),primary_key=True)
    valor_centavos: Mapped[int] = mapped_column(Integer,nullable=False)
    estado: Mapped[str] = mapped_column(String(12),nullable=False)
    versao: Mapped[int] = mapped_column(Integer,nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer,nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120),nullable=False)
    atualizada_em: Mapped[str] = mapped_column(String(40),nullable=False)
    __table_args__ = (
        CheckConstraint("length(mes)=7 AND substr(mes,5,1)='-' AND CAST(substr(mes,1,4) AS INTEGER) BETWEEN 1900 AND 9998 AND substr(mes,6,2) BETWEEN '01' AND '12' AND CAST(substr(mes,6,2) AS INTEGER) BETWEEN 1 AND 12",name='ck_meta_mes'),
        CheckConstraint('valor_centavos>=0 AND valor_centavos<=99999999999999',name='ck_meta_valor'),
        CheckConstraint("estado IN ('ativa','retirada') AND versao>0 AND usuario_admin_id>0",name='ck_meta_estado'),
    )

class EventoMetaResultado(Base):
    __tablename__ = 'eventos_metas_resultado'
    id: Mapped[int] = mapped_column(Integer,primary_key=True)
    mes: Mapped[str] = mapped_column(ForeignKey('metas_resultado_administracao.mes'),nullable=False,index=True)
    versao: Mapped[int] = mapped_column(Integer,nullable=False)
    acao: Mapped[str] = mapped_column(String(12),nullable=False)
    valor_anterior_centavos: Mapped[int|None] = mapped_column(Integer,nullable=True)
    valor_atual_centavos: Mapped[int|None] = mapped_column(Integer,nullable=True)
    usuario_admin_id: Mapped[int] = mapped_column(Integer,nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120),nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text,nullable=False)
    criado_em: Mapped[str] = mapped_column(String(40),nullable=False)
    chave_operacao: Mapped[str] = mapped_column(String(36),nullable=False,unique=True)
    pedido_sha256: Mapped[str] = mapped_column(String(64),nullable=False)
    resultado_json: Mapped[str] = mapped_column(Text,nullable=False)
    __table_args__ = (
        UniqueConstraint('mes','versao',name='uq_evento_meta_versao'),
        CheckConstraint("versao>0 AND usuario_admin_id>0 AND (valor_anterior_centavos IS NULL OR (valor_anterior_centavos>=0 AND valor_anterior_centavos<=99999999999999)) AND ((acao='definir' AND valor_atual_centavos IS NOT NULL AND valor_atual_centavos>=0 AND valor_atual_centavos<=99999999999999) OR (acao='retirar' AND valor_atual_centavos IS NULL))",name='ck_evento_meta_acao'),
    )
