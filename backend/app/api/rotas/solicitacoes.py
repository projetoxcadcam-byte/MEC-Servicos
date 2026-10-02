
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.solicitacao import (
    FornecedorCompativelLeitura,
    SolicitacaoServicoCriacao,
    SolicitacaoServicoLeitura,
)
from backend.app.services.compatibilidade import (
    EmpresaNaoCliente,
    MaterialSolicitacaoNaoEncontrado,
    ProcessoSolicitacaoNaoEncontrado,
    ServicoCompatibilidade,
    SolicitacaoNaoEncontrada,
)

roteador = APIRouter(
    prefix="/solicitacoes-servico",
    tags=["solicitações de serviço"],
)
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "",
    response_model=SolicitacaoServicoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def criar_solicitacao(
    dados: SolicitacaoServicoCriacao,
    banco: SessaoBanco,
) -> SolicitacaoServicoLeitura:
    try:
        solicitacao = ServicoCompatibilidade(banco).criar_solicitacao(dados)
    except EmpresaNaoCliente as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="empresa_nao_e_cliente",
        ) from exc
    except SolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa_cliente_nao_encontrada",
        ) from exc
    except ProcessoSolicitacaoNaoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="processo_nao_encontrado",
        ) from exc
    except MaterialSolicitacaoNaoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="material_nao_encontrado",
        ) from exc

    return SolicitacaoServicoLeitura.model_validate(solicitacao)


@roteador.get(
    "",
    response_model=list[SolicitacaoServicoLeitura],
)
def listar_solicitacoes(
    empresa_cliente_id: int,
    banco: SessaoBanco,
) -> list[SolicitacaoServicoLeitura]:
    empresa = banco.get(Empresa, empresa_cliente_id)

    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa_cliente_nao_encontrada",
        )

    if empresa.tipo_empresa != "cliente":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="empresa_nao_e_cliente",
        )

    itens = banco.scalars(
        select(SolicitacaoServico)
        .where(SolicitacaoServico.empresa_cliente_id == empresa_cliente_id)
        .order_by(
            SolicitacaoServico.criada_em.desc(),
            SolicitacaoServico.id.desc(),
        )
    ).all()

    return [
        SolicitacaoServicoLeitura.model_validate(item)
        for item in itens
    ]


@roteador.get(
    "/{solicitacao_id}",
    response_model=SolicitacaoServicoLeitura,
)
def obter_solicitacao(
    solicitacao_id: int,
    banco: SessaoBanco,
) -> SolicitacaoServicoLeitura:
    try:
        solicitacao = ServicoCompatibilidade(banco).obter_solicitacao(
            solicitacao_id
        )
    except SolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc

    return SolicitacaoServicoLeitura.model_validate(solicitacao)


@roteador.get(
    "/{solicitacao_id}/fornecedores-compativeis",
    response_model=list[FornecedorCompativelLeitura],
)
def listar_fornecedores_compativeis(
    solicitacao_id: int,
    banco: SessaoBanco,
) -> list[FornecedorCompativelLeitura]:
    try:
        itens = ServicoCompatibilidade(banco).listar_fornecedores_compativeis(
            solicitacao_id
        )
    except SolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc

    solicitacao = banco.get(SolicitacaoServico, solicitacao_id)

    if solicitacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        )

    return [
        FornecedorCompativelLeitura(
            empresa_id=empresa.id,
            razao_social=empresa.razao_social,
            tipo_empresa=empresa.tipo_empresa,
            capacidade_id=capacidade.id,
            processo_id=capacidade.processo_id,
            material_id=solicitacao.material_id,
            dimensao_x_maxima_mm=capacidade.dimensao_x_maxima_mm,
            dimensao_y_maxima_mm=capacidade.dimensao_y_maxima_mm,
            dimensao_z_maxima_mm=capacidade.dimensao_z_maxima_mm,
            tolerancia_minima_mm=capacidade.tolerancia_minima_mm,
        )
        for empresa, capacidade in itens
    ]
