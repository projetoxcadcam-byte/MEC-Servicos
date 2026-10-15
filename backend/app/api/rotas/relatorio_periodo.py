from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.painel_administrativo import FiltroPainel
from backend.app.schemas.relatorio_periodo import ConsultaPeriodo
from backend.app.services.relatorio_periodo import ServicoRelatorioPeriodo

roteador = APIRouter(tags=["relatório por período"])
Banco = Annotated[Session, Depends(obter_banco)]
Data = Annotated[str, Query(max_length=10)]
Busca = Annotated[str, Query(max_length=120)]


def conferir_repetidos(request):
    if any(len(request.query_params.getlist(campo)) > 1 for campo in
           ("data_inicial", "data_final", "filtro", "busca", "deslocamento", "limite")):
        raise HTTPException(422, detail="filtro_periodo_invalido")


@roteador.get("/administracao/relatorios/periodo", response_model=ConsultaPeriodo)
def consultar(request: Request, banco: Banco, data_inicial: Data = "", data_final: Data = "",
              filtro: Annotated[FiltroPainel, Query()] = "todas", busca: Busca = "",
              deslocamento: Annotated[int, Query(ge=0)] = 0, limite: Annotated[int, Query(ge=1, le=100)] = 20):
    conferir_repetidos(request)
    return ServicoRelatorioPeriodo(banco).consultar(request.state.usuario_acesso,
        data_inicial, data_final, filtro, busca, deslocamento, limite)


@roteador.get("/administracao/relatorios/periodo/csv")
def exportar(request: Request, banco: Banco, data_inicial: Data = "", data_final: Data = "",
             filtro: Annotated[FiltroPainel, Query()] = "todas", busca: Busca = ""):
    conferir_repetidos(request)
    conteudo = ServicoRelatorioPeriodo(banco).exportar(request.state.usuario_acesso, data_inicial, data_final, filtro, busca)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="MEC_SERVICOS_RELATORIO_PERIODO.csv"', "Cache-Control": "no-store"})
