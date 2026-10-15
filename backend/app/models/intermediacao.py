from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class CicloIntermediacao(Base):
    __tablename__ = "ciclos_intermediacao"
    __table_args__ = (
        UniqueConstraint("ordem_servico_id", name="uq_ciclo_intermediacao_ordem"),
        CheckConstraint("versao > 0", name="ck_ciclo_intermediacao_versao"),
        CheckConstraint("status IN ('aguardando_material','material_recebido','material_encaminhado',"
                        "'coleta_solicitada','pecas_recebidas','em_avaliacao','retrabalho',"
                        "'retrabalho_encaminhado','aprovado_para_entrega','entregue_cliente','cancelado')",
                        name="ck_ciclo_intermediacao_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ordem_servico_id: Mapped[int] = mapped_column(ForeignKey("ordens_servico.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ultima_etapa_coleta_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criado_em: Mapped[str] = mapped_column(String(40), nullable=False)
    atualizado_em: Mapped[str] = mapped_column(String(40), nullable=False)


class EventoIntermediacao(Base):
    __tablename__ = "eventos_intermediacao"
    __table_args__ = (UniqueConstraint("ciclo_id", "versao", name="uq_evento_intermediacao_versao"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos_intermediacao.id", ondelete="RESTRICT"), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    acao: Mapped[str] = mapped_column(String(40), nullable=False)
    status_anterior: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status_resultante: Mapped[str] = mapped_column(String(40), nullable=False)
    usuario_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    administrador_nome: Mapped[str] = mapped_column(String(120), nullable=False)
    registro_interno: Mapped[str] = mapped_column(Text, nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parecer_tecnico: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantidade_conferida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[str] = mapped_column(String(40), nullable=False)
