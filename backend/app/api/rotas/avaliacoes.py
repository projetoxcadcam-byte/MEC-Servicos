
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.avaliacao import (
    AvaliacaoOficinaCriacao,
    AvaliacaoOficinaResposta,
    ReputacaoOficinaResposta,
)
from backend.app.services.avaliacao import ServicoAvaliacaoOficina


roteador = APIRouter(tags=["avaliacoes"])


@roteador.post(
    "/contratacoes/{contratacao_id}/avaliacao",
    response_model=AvaliacaoOficinaResposta,
    status_code=status.HTTP_201_CREATED,
)
def criar_avaliacao(
    contratacao_id: int,
    dados: AvaliacaoOficinaCriacao,
    banco: Session = Depends(obter_banco),
) -> AvaliacaoOficinaResposta:
    return ServicoAvaliacaoOficina(banco).criar(
        contratacao_id,
        dados,
    )


@roteador.get(
    "/avaliacoes/{avaliacao_id}",
    response_model=AvaliacaoOficinaResposta,
)
def obter_avaliacao(
    avaliacao_id: int,
    banco: Session = Depends(obter_banco),
) -> AvaliacaoOficinaResposta:
    return ServicoAvaliacaoOficina(banco).obter(avaliacao_id)


@roteador.get(
    "/empresas/{empresa_id}/avaliacoes",
    response_model=list[AvaliacaoOficinaResposta],
)
def listar_avaliacoes(
    empresa_id: int,
    banco: Session = Depends(obter_banco),
) -> list[AvaliacaoOficinaResposta]:
    return ServicoAvaliacaoOficina(banco).listar(empresa_id)


@roteador.get(
    "/empresas/{empresa_id}/reputacao",
    response_model=ReputacaoOficinaResposta,
)
def obter_reputacao(
    empresa_id: int,
    banco: Session = Depends(obter_banco),
) -> ReputacaoOficinaResposta:
    return ServicoAvaliacaoOficina(banco).obter_reputacao(empresa_id)
