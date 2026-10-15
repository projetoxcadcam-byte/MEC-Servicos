from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Request, Response
from backend.app.api.rotas.relatorio_periodo import Banco, Busca
from backend.app.schemas.extrato_financeiro import ConsultaExtrato, FiltroExtrato
from backend.app.services.extrato_financeiro import ServicoExtratoFinanceiro

roteador = APIRouter(tags=["extrato financeiro por período"])
Data = Annotated[str | None, Query(max_length=10)]
Contratacao = Annotated[int | None, Query(ge=1)]


def conferir_repetidos(request):
    if any(len(request.query_params.getlist(c)) > 1 for c in
           ("data_inicial", "data_final", "tipo", "busca", "contratacao_id", "deslocamento", "limite")):
        raise HTTPException(422, detail="filtro_extrato_invalido")


@roteador.get("/administracao/financeiro/extrato", response_model=ConsultaExtrato)
def consultar(request: Request, banco: Banco, response: Response, data_inicial: Data = None, data_final: Data = None,
              tipo: Annotated[FiltroExtrato, Query()] = "todos", busca: Busca = "", contratacao_id: Contratacao = None,
              deslocamento: Annotated[int, Query(ge=0)] = 0, limite: Annotated[int, Query(ge=1, le=100)] = 20):
    conferir_repetidos(request)
    response.headers["Cache-Control"] = "no-store"
    return ServicoExtratoFinanceiro(banco).consultar(request.state.usuario_acesso,
        data_inicial, data_final, tipo, busca, contratacao_id, deslocamento, limite)


@roteador.get("/administracao/financeiro/extrato/csv")
def exportar(request: Request, banco: Banco, data_inicial: Data = None, data_final: Data = None,
             tipo: Annotated[FiltroExtrato, Query()] = "todos", busca: Busca = "", contratacao_id: Contratacao = None):
    conferir_repetidos(request)
    conteudo = ServicoExtratoFinanceiro(banco).exportar(request.state.usuario_acesso, data_inicial, data_final, tipo, busca, contratacao_id)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="MEC_SERVICOS_EXTRATO_FINANCEIRO.csv"', "Cache-Control": "no-store"})
