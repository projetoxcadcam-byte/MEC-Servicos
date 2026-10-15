from __future__ import annotations

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.contratacao_admin import (
    ConfirmacaoContratacaoAdmin, PaginaContratacoesAdmin, PreparacaoContratacaoAdmin, ResultadoContratacaoAdmin,
)
from backend.app.services.contratacao_admin import ServicoContratacaoAdmin

roteador = APIRouter(prefix="/administracao", tags=["contratação administrativa e ordens de serviço"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.get("/contratacoes", response_model=PaginaContratacoesAdmin)
def listar_contratacoes(banco: SessaoBanco, solicitacao_id: int | None = Query(default=None, gt=0),
        contratacao_id: int | None = Query(default=None, gt=0),
        status: Literal["ativa", "encerrada", "cancelada"] | None = None,
        deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100)):
    return ServicoContratacaoAdmin(banco).listar(solicitacao_id=solicitacao_id, contratacao_id=contratacao_id,
        status=status, deslocamento=deslocamento, limite=limite)


@roteador.get("/contratacoes/preparacao/{solicitacao_id}", response_model=PreparacaoContratacaoAdmin)
def preparar(solicitacao_id: int, banco: SessaoBanco):
    return ServicoContratacaoAdmin(banco).preparar(solicitacao_id)


@roteador.post("/contratacoes/preparacao/{solicitacao_id}/confirmar", response_model=ResultadoContratacaoAdmin)
def confirmar(solicitacao_id: int, dados: ConfirmacaoContratacaoAdmin, banco: SessaoBanco, request: Request):
    return ServicoContratacaoAdmin(banco).confirmar(solicitacao_id, dados, request.state.usuario_acesso)


@roteador.get("/contratacoes/{contratacao_id}", response_model=PreparacaoContratacaoAdmin)
def obter_contratacao(contratacao_id: int, banco: SessaoBanco):
    return ServicoContratacaoAdmin(banco).obter_contratacao(contratacao_id)


@roteador.get("/ordens-servico", response_model=PaginaContratacoesAdmin)
def listar_ordens(banco: SessaoBanco, solicitacao_id: int | None = Query(default=None, gt=0),
        contratacao_id: int | None = Query(default=None, gt=0), ordem_servico_id: int | None = Query(default=None, gt=0),
        status: Literal["aberta", "em_execucao", "concluida", "cancelada"] | None = None,
        deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100)):
    return ServicoContratacaoAdmin(banco).listar(ordens=True, solicitacao_id=solicitacao_id,
        contratacao_id=contratacao_id, ordem_servico_id=ordem_servico_id,
        status=status, deslocamento=deslocamento, limite=limite)
