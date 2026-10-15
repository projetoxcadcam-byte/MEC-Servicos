from sqlalchemy import CheckConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.base import Base


class HistoricoCampoPdf(Base):
    __tablename__ = "historico_campos_pdf"
    __table_args__ = (
        UniqueConstraint("usuario_admin_id", "campo", "chave_valor", name="uq_historico_campo_pdf_valor"),
        CheckConstraint("usuario_admin_id > 0", name="ck_historico_campo_pdf_usuario"),
        Index("ix_historico_campo_pdf_usuario_data", "usuario_admin_id", "atualizado_em"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    campo: Mapped[str] = mapped_column(String(32), nullable=False)
    chave_valor: Mapped[str] = mapped_column(String(64), nullable=False)
    valor: Mapped[str] = mapped_column(String(180), nullable=False)
    atualizado_em: Mapped[str] = mapped_column(String(32), nullable=False)
