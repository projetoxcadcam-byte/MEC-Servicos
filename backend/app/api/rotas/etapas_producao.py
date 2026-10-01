from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.etapa_producao import (
    AcompanhamentoProducaoLeitura,
    EtapaProducaoCriacao,
    EtapaProducaoLeitura,
)
from backend.app.services.etapa_producao import (
    EmpresaFornecedoraNaoPodeAtualizarProducao,
    OrdemServicoNaoEncontradaParaProducao,
    OrdemServicoNaoPodeAtualizarProducao,
    ServicoEtapaProducao,
)

roteador = APIRouter(tags=["acompanhamento de produção"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "/ordens-servico/{ordem_servico_id}/etapas-producao",
    response_model=EtapaProducaoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def registrar_etapa_producao(
    ordem_servico_id: int,
    dados: EtapaProducaoCriacao,
    banco: SessaoBanco,
) -> EtapaProducaoLeitura:
    try:
        return ServicoEtapaProducao(banco).registrar(
            ordem_servico_id,
            dados,
        )
    except OrdemServicoNaoEncontradaParaProducao as exc:
        raise HTTPException(
            status_code=404,
            detail="ordem_servico_nao_encontrada",
        ) from exc
    except EmpresaFornecedoraNaoPodeAtualizarProducao as exc:
        raise HTTPException(
            status_code=403,
            detail="empresa_nao_e_fornecedora_da_ordem_servico",
        ) from exc
    except OrdemServicoNaoPodeAtualizarProducao as exc:
        raise HTTPException(
            status_code=409,
            detail="ordem_servico_nao_pode_atualizar_producao",
        ) from exc


@roteador.get(
    "/ordens-servico/{ordem_servico_id}/etapas-producao",
    response_model=list[EtapaProducaoLeitura],
)
def listar_etapas_producao(
    ordem_servico_id: int,
    banco: SessaoBanco,
) -> list[EtapaProducaoLeitura]:
    try:
        return ServicoEtapaProducao(banco).listar(ordem_servico_id)
    except OrdemServicoNaoEncontradaParaProducao as exc:
        raise HTTPException(
            status_code=404,
            detail="ordem_servico_nao_encontrada",
        ) from exc


@roteador.get(
    "/ordens-servico/{ordem_servico_id}/acompanhamento-producao",
    response_model=AcompanhamentoProducaoLeitura,
)
def obter_acompanhamento_producao(
    ordem_servico_id: int,
    banco: SessaoBanco,
) -> AcompanhamentoProducaoLeitura:
    try:
        return ServicoEtapaProducao(banco).acompanhamento(
            ordem_servico_id,
        )
    except OrdemServicoNaoEncontradaParaProducao as exc:
        raise HTTPException(
            status_code=404,
            detail="ordem_servico_nao_encontrada",
        ) from exc
