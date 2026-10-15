from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Path, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.relatorio_administrativo import RelatorioContratacao
from backend.app.services.relatorio_administrativo import ServicoRelatorioAdministrativo

roteador = APIRouter(tags=["relatório administrativo"])
Banco = Annotated[Session, Depends(obter_banco)]
Identificador = Annotated[int, Path(ge=1, le=9_999_999_999_999)]


@roteador.get("/administracao/relatorios/contratacoes/{contratacao_id}", response_model=RelatorioContratacao)
def consultar(contratacao_id: Identificador, request: Request, banco: Banco):
    return ServicoRelatorioAdministrativo(banco).obter(contratacao_id, request.state.usuario_acesso)


@roteador.get("/administracao/relatorios/contratacoes/{contratacao_id}/csv")
def exportar(contratacao_id: Identificador, request: Request, banco: Banco):
    conteudo = ServicoRelatorioAdministrativo(banco).exportar(contratacao_id, request.state.usuario_acesso)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="MEC_SERVICOS_CONTRATACAO_{contratacao_id}.csv"',
        "Cache-Control": "no-store",
    })
