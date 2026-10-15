from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Request, Response
from backend.app.api.rotas.relatorio_periodo import Banco, Busca
from backend.app.schemas.painel_administrativo import FiltroPainel
from backend.app.schemas.resumo_gerencial import ConsultaGerencial
from backend.app.services.resumo_gerencial import ServicoResumoGerencial

roteador = APIRouter(tags=["resumo gerencial mensal"])
Ano = Annotated[int | None, Query(ge=1, le=9999)]
Mes = Annotated[int | None, Query(ge=1, le=12)]


def conferir_repetidos(request):
    if any(len(request.query_params.getlist(c)) > 1 for c in
           ("ano", "filtro", "busca", "mes", "deslocamento", "limite")):
        raise HTTPException(422, detail="filtro_gerencial_invalido")


@roteador.get("/administracao/relatorios/gerencial", response_model=ConsultaGerencial)
def consultar(request: Request, banco: Banco, response: Response, ano: Ano = None,
              filtro: Annotated[FiltroPainel, Query()] = "todas", busca: Busca = "", mes: Mes = None,
              deslocamento: Annotated[int, Query(ge=0)] = 0, limite: Annotated[int, Query(ge=1, le=100)] = 20):
    conferir_repetidos(request)
    response.headers["Cache-Control"] = "no-store"
    return ServicoResumoGerencial(banco).consultar(request.state.usuario_acesso,
        ano, filtro, busca, mes, deslocamento, limite)


@roteador.get("/administracao/relatorios/gerencial/csv")
def exportar(request: Request, banco: Banco, ano: Ano = None,
             filtro: Annotated[FiltroPainel, Query()] = "todas", busca: Busca = "", mes: Mes = None):
    conferir_repetidos(request)
    conteudo = ServicoResumoGerencial(banco).exportar(request.state.usuario_acesso, ano, filtro, busca, mes)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="MEC_SERVICOS_RESUMO_GERENCIAL_MENSAL.csv"',
        "Cache-Control": "no-store"})
