from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.ordem_servico import OrdemServicoAcao, OrdemServicoCriacao, OrdemServicoLeitura
from backend.app.services.ordem_servico import (
    ContratacaoNaoAtiva,
    ContratacaoNaoEncontradaParaOS,
    EmpresaNaoPodeOperarOS,
    OrdemServicoDuplicada,
    OrdemServicoNaoEncontrada,
    OrdemServicoNaoPodeSerCancelada,
    OrdemServicoNaoPodeSerConcluida,
    OrdemServicoNaoPodeSerIniciada,
    ServicoOrdemServico,
)

roteador = APIRouter(tags=["ordens de serviço"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post("/contratacoes/{contratacao_id}/ordem-servico", response_model=OrdemServicoLeitura, status_code=status.HTTP_201_CREATED)
def criar_ordem_servico(contratacao_id: int, dados: OrdemServicoCriacao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).criar(contratacao_id, dados)
    except ContratacaoNaoEncontradaParaOS as exc:
        raise HTTPException(status_code=404, detail="contratacao_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_contratacao") from exc
    except ContratacaoNaoAtiva as exc:
        raise HTTPException(status_code=409, detail="contratacao_nao_esta_ativa") from exc
    except OrdemServicoDuplicada as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_ja_cadastrada_para_esta_contratacao") from exc


@roteador.get("/ordens-servico", response_model=list[OrdemServicoLeitura])
def listar_ordens_servico(banco: SessaoBanco) -> list[OrdemServicoLeitura]:
    return ServicoOrdemServico(banco).listar()


@roteador.get("/ordens-servico/{ordem_id}", response_model=OrdemServicoLeitura)
def obter_ordem_servico(ordem_id: int, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).obter(ordem_id)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc


@roteador.post("/ordens-servico/{ordem_id}/iniciar", response_model=OrdemServicoLeitura)
def iniciar_ordem_servico(ordem_id: int, dados: OrdemServicoAcao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).iniciar(ordem_id, dados)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_ordem_servico") from exc
    except OrdemServicoNaoPodeSerIniciada as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_nao_pode_ser_iniciada") from exc


@roteador.post("/ordens-servico/{ordem_id}/concluir", response_model=OrdemServicoLeitura)
def concluir_ordem_servico(ordem_id: int, dados: OrdemServicoAcao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).concluir(ordem_id, dados)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_ordem_servico") from exc
    except OrdemServicoNaoPodeSerConcluida as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_nao_pode_ser_concluida") from exc


@roteador.post("/ordens-servico/{ordem_id}/cancelar", response_model=OrdemServicoLeitura)
def cancelar_ordem_servico(ordem_id: int, dados: OrdemServicoAcao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).cancelar(ordem_id, dados)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_ordem_servico") from exc
    except OrdemServicoNaoPodeSerCancelada as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_nao_pode_ser_cancelada") from exc
