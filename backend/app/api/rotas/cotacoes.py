from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.cotacao import (
    CotacaoCriacao,
    CotacaoDecisao,
    CotacaoLeitura,
)
from backend.app.services.cotacao import (
    CotacaoDuplicada,
    CotacaoEmpresaNaoFornecedor,
    CotacaoEmpresaNaoEncontrada,
    CotacaoExpirada,
    CotacaoFornecedorIncompativel,
    CotacaoNaoEncontrada,
    CotacaoNaoPendente,
    CotacaoSolicitacaoNaoEncontrada,
    EmpresaNaoPodeDecidir,
    SolicitacaoJaPossuiCotacaoAceita,
    ServicoCotacao,
)

roteador = APIRouter(
    prefix="/solicitacoes-servico",
    tags=["cotações"],
)
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "/{solicitacao_id}/cotacoes",
    response_model=CotacaoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def criar_cotacao(
    solicitacao_id: int,
    dados: CotacaoCriacao,
    banco: SessaoBanco,
) -> CotacaoLeitura:
    try:
        cotacao = ServicoCotacao(banco).criar(solicitacao_id, dados)
    except CotacaoSolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc
    except CotacaoEmpresaNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa_fornecedora_nao_encontrada",
        ) from exc
    except CotacaoEmpresaNaoFornecedor as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="empresa_nao_e_fornecedora",
        ) from exc
    except CotacaoFornecedorIncompativel as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fornecedor_nao_compativel_com_a_solicitacao",
        ) from exc
    except CotacaoDuplicada as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cotacao_ja_cadastrada_para_este_fornecedor",
        ) from exc
    except SolicitacaoJaPossuiCotacaoAceita as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="solicitacao_ja_possui_cotacao_aceita",
        ) from exc

    return CotacaoLeitura.model_validate(cotacao)


@roteador.get(
    "/{solicitacao_id}/cotacoes",
    response_model=list[CotacaoLeitura],
)
def listar_cotacoes(
    solicitacao_id: int,
    banco: SessaoBanco,
) -> list[CotacaoLeitura]:
    try:
        cotacoes = ServicoCotacao(banco).listar(solicitacao_id)
    except CotacaoSolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc

    return [CotacaoLeitura.model_validate(cotacao) for cotacao in cotacoes]


def _processar_decisao(
    acao: str,
    solicitacao_id: int,
    cotacao_id: int,
    dados: CotacaoDecisao,
    banco: Session,
) -> CotacaoLeitura:
    servico = ServicoCotacao(banco)

    try:
        if acao == "aceitar":
            cotacao = servico.aceitar(
                solicitacao_id,
                cotacao_id,
                dados.empresa_cliente_id,
            )
        else:
            cotacao = servico.recusar(
                solicitacao_id,
                cotacao_id,
                dados.empresa_cliente_id,
            )
    except CotacaoSolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc
    except CotacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="cotacao_nao_encontrada",
        ) from exc
    except EmpresaNaoPodeDecidir as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="empresa_nao_e_cliente_da_solicitacao",
        ) from exc
    except CotacaoExpirada as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cotacao_expirada",
        ) from exc
    except CotacaoNaoPendente as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cotacao_nao_esta_pendente",
        ) from exc
    except SolicitacaoJaPossuiCotacaoAceita as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="solicitacao_ja_possui_cotacao_aceita",
        ) from exc

    return CotacaoLeitura.model_validate(cotacao)


@roteador.post(
    "/{solicitacao_id}/cotacoes/{cotacao_id}/aceitar",
    response_model=CotacaoLeitura,
)
def aceitar_cotacao(
    solicitacao_id: int,
    cotacao_id: int,
    dados: CotacaoDecisao,
    banco: SessaoBanco,
) -> CotacaoLeitura:
    return _processar_decisao(
        "aceitar",
        solicitacao_id,
        cotacao_id,
        dados,
        banco,
    )


@roteador.post(
    "/{solicitacao_id}/cotacoes/{cotacao_id}/recusar",
    response_model=CotacaoLeitura,
)
def recusar_cotacao(
    solicitacao_id: int,
    cotacao_id: int,
    dados: CotacaoDecisao,
    banco: SessaoBanco,
) -> CotacaoLeitura:
    return _processar_decisao(
        "recusar",
        solicitacao_id,
        cotacao_id,
        dados,
        banco,
    )
