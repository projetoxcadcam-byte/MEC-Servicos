from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.notificacao import MarcarNotificacoesLidas, NotificacaoLeitura, PaginaNotificacoes, ResumoNotificacoes
from backend.app.services.notificacoes import ServicoNotificacoes

roteador = APIRouter(prefix="/notificacoes", tags=["notificacoes"])
Banco = Annotated[Session, Depends(obter_banco)]


def servico(request: Request, banco: Session) -> ServicoNotificacoes:
    usuario = request.state.usuario_acesso
    esperado = f"{usuario.usuario_id}:{usuario.perfil}:{usuario.empresa_id or 0}"
    recebido = request.headers.get("x-mec-notificacoes-contexto")
    # Este cabeçalho apenas detecta uma aba com acesso antigo. Não concede autorização.
    if recebido is not None and recebido != esperado:
        raise HTTPException(409, detail="contexto_notificacoes_alterado")
    return ServicoNotificacoes(banco, usuario)


@roteador.get("", response_model=PaginaNotificacoes)
def listar(request: Request, banco: Banco, antes_id: int | None = Query(default=None, gt=0),
           limite: int = Query(default=20, ge=1, le=50), somente_nao_lidas: bool = False):
    return servico(request, banco).listar(antes_id, limite, somente_nao_lidas)


@roteador.get("/resumo", response_model=ResumoNotificacoes)
def resumo(request: Request, banco: Banco):
    return servico(request, banco).resumo()


@roteador.post("/ler-ate", response_model=ResumoNotificacoes)
def ler_ate(dados: MarcarNotificacoesLidas, request: Request, banco: Banco):
    return servico(request, banco).ler_ate(dados.ate_id)


@roteador.post("/{notificacao_id}/ler", response_model=NotificacaoLeitura)
def ler(notificacao_id: Annotated[int, Path(gt=0)], request: Request, banco: Banco):
    return servico(request, banco).ler(notificacao_id)
