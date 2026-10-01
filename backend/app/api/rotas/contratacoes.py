from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.contratacao import (
    ContratacaoCancelamento,
    ContratacaoCriacao,
    ContratacaoLeitura,
)
from backend.app.services.contratacao import (
    ContratacaoCotacaoNaoAceita,
    ContratacaoCotacaoNaoEncontrada,
    ContratacaoEmpresaNaoPodeContratar,
    ContratacaoJaExiste,
    ContratacaoNaoAtiva,
    ContratacaoNaoEncontrada,
    ContratacaoSolicitacaoNaoEncontrada,
    ContratacaoSolicitacaoNaoAberta,
    ServicoContratacao,
)

roteador = APIRouter(
    prefix="/solicitacoes-servico",
    tags=["contratações"],
)

SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "/{solicitacao_id}/contratacao",
    response_model=ContratacaoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def criar_contratacao(
    solicitacao_id: int,
    dados: ContratacaoCriacao,
    banco: SessaoBanco,
) -> ContratacaoLeitura:
    try:
        contratacao = ServicoContratacao(banco).criar(solicitacao_id, dados)
    except ContratacaoSolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc
    except ContratacaoEmpresaNaoPodeContratar as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="empresa_nao_e_cliente_da_solicitacao",
        ) from exc
    except ContratacaoJaExiste as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="contratacao_ja_cadastrada",
        ) from exc
    except ContratacaoSolicitacaoNaoAberta as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="solicitacao_nao_esta_aberta",
        ) from exc
    except ContratacaoCotacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="cotacao_nao_encontrada",
        ) from exc
    except ContratacaoCotacaoNaoAceita as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cotacao_nao_esta_aceita",
        ) from exc

    return ContratacaoLeitura.model_validate(contratacao)


@roteador.get(
    "/{solicitacao_id}/contratacao",
    response_model=ContratacaoLeitura,
)
def obter_contratacao(
    solicitacao_id: int,
    banco: SessaoBanco,
) -> ContratacaoLeitura:
    try:
        contratacao = ServicoContratacao(banco).obter(solicitacao_id)
    except ContratacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="contratacao_nao_encontrada",
        ) from exc

    return ContratacaoLeitura.model_validate(contratacao)


@roteador.post(
    "/{solicitacao_id}/contratacao/cancelar",
    response_model=ContratacaoLeitura,
)
def cancelar_contratacao(
    solicitacao_id: int,
    dados: ContratacaoCancelamento,
    banco: SessaoBanco,
) -> ContratacaoLeitura:
    try:
        contratacao = ServicoContratacao(banco).cancelar(
            solicitacao_id,
            dados.empresa_cliente_id,
        )
    except ContratacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="contratacao_nao_encontrada",
        ) from exc
    except ContratacaoEmpresaNaoPodeContratar as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="empresa_nao_e_cliente_da_solicitacao",
        ) from exc
    except ContratacaoNaoAtiva as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="contratacao_nao_esta_ativa",
        ) from exc

    return ContratacaoLeitura.model_validate(contratacao)
