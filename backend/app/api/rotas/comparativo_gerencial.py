from __future__ import annotations

from typing import Annotated, Literal
from fastapi import APIRouter, HTTPException, Query, Request, Response
from backend.app.api.rotas.relatorio_periodo import Banco, Busca
from backend.app.schemas.comparativo_gerencial import ConsultaComparativo
from backend.app.schemas.painel_administrativo import FiltroPainel
from backend.app.services.comparativo_gerencial import ServicoComparativoGerencial

roteador = APIRouter(tags=["comparativo gerencial entre períodos"])
Data = Annotated[str | None, Query(max_length=10)]
Periodo = Annotated[Literal["a", "b"] | None, Query()]


def conferir_repetidos(request):
    if any(len(request.query_params.getlist(c)) > 1 for c in
           ("a_inicial", "a_final", "b_inicial", "b_final", "filtro", "busca", "periodo", "deslocamento", "limite")):
        raise HTTPException(422, detail="filtro_comparativo_invalido")


@roteador.get("/administracao/relatorios/comparativo", response_model=ConsultaComparativo)
def consultar(request: Request, banco: Banco, response: Response, a_inicial: Data = None, a_final: Data = None,
              b_inicial: Data = None, b_final: Data = None, filtro: Annotated[FiltroPainel, Query()] = "todas",
              busca: Busca = "", periodo: Periodo = None, deslocamento: Annotated[int, Query(ge=0)] = 0,
              limite: Annotated[int, Query(ge=1, le=100)] = 20):
    conferir_repetidos(request)
    response.headers["Cache-Control"] = "no-store"
    return ServicoComparativoGerencial(banco).consultar(request.state.usuario_acesso,
        a_inicial, a_final, b_inicial, b_final, filtro, busca, periodo, deslocamento, limite)


@roteador.get("/administracao/relatorios/comparativo/csv")
def exportar(request: Request, banco: Banco, a_inicial: Data = None, a_final: Data = None,
             b_inicial: Data = None, b_final: Data = None, filtro: Annotated[FiltroPainel, Query()] = "todas",
             busca: Busca = "", periodo: Periodo = None):
    conferir_repetidos(request)
    conteudo = ServicoComparativoGerencial(banco).exportar(request.state.usuario_acesso,
        a_inicial, a_final, b_inicial, b_final, filtro, busca, periodo)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="MEC_SERVICOS_COMPARATIVO_GERENCIAL.csv"', "Cache-Control": "no-store"})
