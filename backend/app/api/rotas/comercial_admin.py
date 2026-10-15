from __future__ import annotations

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.comercial_admin import (
    DecisaoComercial, DetalheSolicitacaoComercial, PaginaCotacoesComerciais,
    PaginaSolicitacoesComerciais, ResultadoDecisaoComercial,
)
from backend.app.services.comercial_admin import ServicoComercialAdmin
from backend.app.schemas.comparacao_cotacoes_admin import ComparacaoCotacoesAdmin, EscopoComparacao, OrdenacaoComparacao
from backend.app.services.comparacao_cotacoes_admin import ServicoComparacaoCotacoesAdmin

roteador = APIRouter(prefix="/administracao/comercial", tags=["solicitações e cotações administrativas"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.get("/solicitacoes/{solicitacao_id}/comparacao", response_model=ComparacaoCotacoesAdmin)
def comparar_cotacoes(solicitacao_id: Annotated[int, Path(gt=0)], request: Request, response: Response,
        banco: SessaoBanco, ordenacao: OrdenacaoComparacao = "valor", escopo: EscopoComparacao = "disponiveis",
        deslocamento: int = Query(default=0, ge=0, le=1_000_000), limite: int = Query(default=20, ge=1, le=100)):
    servico = ServicoComparacaoCotacoesAdmin(banco, request.state.usuario_acesso)
    recebido = request.headers.get("x-mec-comercial-contexto")
    if recebido is not None and recebido != servico.contexto():
        raise HTTPException(409, detail="contexto_comercial_alterado")
    response.headers["Cache-Control"] = "no-store"
    return servico.consultar(solicitacao_id, ordenacao, escopo, deslocamento, limite)


@roteador.get("/solicitacoes", response_model=PaginaSolicitacoesComerciais)
def listar_solicitacoes(banco: SessaoBanco, solicitacao_id: int | None = Query(default=None, gt=0),
        status: Literal["aberta", "encerrada", "cancelada"] | None = None,
        deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100)):
    return ServicoComercialAdmin(banco).listar_solicitacoes(solicitacao_id, status, deslocamento, limite)


@roteador.get("/solicitacoes/{solicitacao_id}", response_model=DetalheSolicitacaoComercial)
def obter_solicitacao(solicitacao_id: int, banco: SessaoBanco):
    return ServicoComercialAdmin(banco).detalhe(solicitacao_id)


@roteador.get("/cotacoes", response_model=PaginaCotacoesComerciais)
def listar_cotacoes(banco: SessaoBanco, solicitacao_id: int | None = Query(default=None, gt=0),
        cotacao_id: int | None = Query(default=None, gt=0),
        status: Literal["enviada", "aceita", "recusada", "expirada", "cancelada"] | None = None,
        deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100)):
    return ServicoComercialAdmin(banco).listar_cotacoes(solicitacao_id, cotacao_id, status, deslocamento, limite)


@roteador.post("/solicitacoes/{solicitacao_id}/cotacoes/{cotacao_id}/decisoes", response_model=ResultadoDecisaoComercial)
def registrar_decisao(solicitacao_id: int, cotacao_id: int, dados: DecisaoComercial, banco: SessaoBanco, request: Request):
    return ServicoComercialAdmin(banco).registrar(solicitacao_id, cotacao_id, dados, request.state.usuario_acesso)
