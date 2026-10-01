from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.arquivo_tecnico import ArquivoTecnico


class RepositorioArquivoTecnico:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, arquivo: ArquivoTecnico) -> ArquivoTecnico:
        self.banco.add(arquivo)
        self.banco.commit()
        self.banco.refresh(arquivo)
        return arquivo

    def obter_ativo_por_id(self, arquivo_id: int) -> ArquivoTecnico | None:
        return self.banco.scalar(
            select(ArquivoTecnico).where(
                ArquivoTecnico.id == arquivo_id,
                ArquivoTecnico.ativo.is_(True),
            )
        )

    def listar_ativos_por_solicitacao(
        self,
        solicitacao_id: int,
    ) -> list[ArquivoTecnico]:
        return list(
            self.banco.scalars(
                select(ArquivoTecnico)
                .where(
                    ArquivoTecnico.solicitacao_id == solicitacao_id,
                    ArquivoTecnico.ativo.is_(True),
                )
                .order_by(
                    ArquivoTecnico.criado_em.desc(),
                    ArquivoTecnico.id.desc(),
                )
            )
        )

    def salvar(self, arquivo: ArquivoTecnico) -> ArquivoTecnico:
        self.banco.add(arquivo)
        self.banco.commit()
        self.banco.refresh(arquivo)
        return arquivo
