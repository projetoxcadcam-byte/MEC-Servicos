from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Request, Response
from backend.app.api.rotas.relatorio_periodo import Banco, Busca, Data
from backend.app.schemas.central_pendencias import AreaFila, ConsultaPendencias
from backend.app.schemas.painel_administrativo import FiltroPainel
from backend.app.services.central_pendencias import ServicoCentralPendencias

roteador = APIRouter(tags=["central de pendências administrativas"])
Acao = Annotated[str, Query(max_length=70)]


def conferir_repetidos(request):
    if any(len(request.query_params.getlist(c)) > 1 for c in
           ("data_inicial", "data_final", "filtro", "busca", "area", "acao", "deslocamento", "limite")):
        raise HTTPException(422, detail="filtro_pendencias_invalido")


@roteador.get("/administracao/pendencias", response_model=ConsultaPendencias)
def consultar(request: Request, banco: Banco, response: Response, data_inicial: Data = "", data_final: Data = "",
              filtro: Annotated[FiltroPainel, Query()] = "todas", busca: Busca = "",
              area: Annotated[AreaFila, Query()] = "todas", acao: Acao = "",
              deslocamento: Annotated[int, Query(ge=0)] = 0, limite: Annotated[int, Query(ge=1, le=100)] = 20):
    conferir_repetidos(request); response.headers["Cache-Control"] = "no-store"
    return ServicoCentralPendencias(banco).consultar(request.state.usuario_acesso,
        data_inicial, data_final, filtro, busca, area, acao, deslocamento, limite)


@roteador.get("/administracao/pendencias/csv")
def exportar(request: Request, banco: Banco, data_inicial: Data = "", data_final: Data = "",
             filtro: Annotated[FiltroPainel, Query()] = "todas", busca: Busca = "",
             area: Annotated[AreaFila, Query()] = "todas", acao: Acao = ""):
    conferir_repetidos(request)
    conteudo = ServicoCentralPendencias(banco).exportar(request.state.usuario_acesso, data_inicial, data_final, filtro, busca, area, acao)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="MEC_SERVICOS_CENTRAL_PENDENCIAS.csv"', "Cache-Control": "no-store"})
