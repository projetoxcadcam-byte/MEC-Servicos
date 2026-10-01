
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.repositories.avaliacao import RepositorioAvaliacaoOficina
from backend.app.schemas.avaliacao import (
    AvaliacaoOficinaCriacao,
    ReputacaoOficinaResposta,
)


class ServicoAvaliacaoOficina:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioAvaliacaoOficina(banco)

    def criar(
        self,
        contratacao_id: int,
        dados: AvaliacaoOficinaCriacao,
    ) -> AvaliacaoOficina:
        contratacao = self.banco.get(ContratacaoServico, contratacao_id)
        if contratacao is None:
            raise HTTPException(
                status_code=404,
                detail="contratacao_nao_encontrada",
            )

        if contratacao.empresa_cliente_id != dados.empresa_cliente_id:
            raise HTTPException(
                status_code=403,
                detail="empresa_nao_e_cliente_da_contratacao",
            )

        ordem = self.banco.scalar(
            select(OrdemServico).where(
                OrdemServico.contratacao_id == contratacao_id
            )
        )
        if ordem is None:
            raise HTTPException(
                status_code=409,
                detail="ordem_servico_nao_encontrada",
            )

        if ordem.empresa_cliente_id != dados.empresa_cliente_id:
            raise HTTPException(
                status_code=403,
                detail="empresa_nao_e_cliente_da_ordem_servico",
            )

        if ordem.empresa_fornecedora_id != contratacao.empresa_fornecedora_id:
            raise HTTPException(
                status_code=409,
                detail="fornecedor_da_ordem_servico_inconsistente",
            )

        if ordem.status != "concluida" and contratacao.status != "encerrada":
            raise HTTPException(
                status_code=409,
                detail="servico_ainda_nao_foi_concluido_e_aceito",
            )

        if self.repositorio.obter_por_contratacao(contratacao_id) is not None:
            raise HTTPException(
                status_code=409,
                detail="avaliacao_ja_registrada_para_contratacao",
            )

        avaliacao = AvaliacaoOficina(
            contratacao_id=contratacao_id,
            ordem_servico_id=ordem.id,
            empresa_cliente_id=dados.empresa_cliente_id,
            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,
            nota=dados.nota,
            comentario=dados.comentario,
        )
        return self.repositorio.criar(avaliacao)

    def obter(self, avaliacao_id: int) -> AvaliacaoOficina:
        item = self.repositorio.obter_por_id(avaliacao_id)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="avaliacao_nao_encontrada",
            )
        return item

    def listar(self, empresa_fornecedora_id: int) -> list[AvaliacaoOficina]:
        return self.repositorio.listar_por_fornecedor(
            empresa_fornecedora_id
        )

    def obter_reputacao(
        self, empresa_fornecedora_id: int
    ) -> ReputacaoOficinaResposta:
        quantidade, media = self.repositorio.reputacao(
            empresa_fornecedora_id
        )
        return ReputacaoOficinaResposta(
            empresa_id=empresa_fornecedora_id,
            quantidade_avaliacoes=quantidade,
            media_nota=(
                round(media, 2) if media is not None else None
            ),
        )
