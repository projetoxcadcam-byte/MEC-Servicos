from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Request, Response
from backend.app.api.rotas.relatorio_periodo import Banco, Busca, Data
from backend.app.schemas.painel_administrativo import FiltroPainel
from backend.app.schemas.relatorio_empresas import AgrupamentoEmpresas, ConsultaEmpresas
from backend.app.services.relatorio_empresas import ServicoRelatorioEmpresas

roteador = APIRouter(tags=["relatório por cliente e fornecedor"])
EmpresaID = Annotated[int | None, Query(gt=0)]


def conferir_repetidos(request):
    if any(len(request.query_params.getlist(campo)) > 1 for campo in ("agrupamento", "empresa_id",
            "data_inicial", "data_final", "filtro", "busca", "deslocamento", "deslocamento_itens", "limite")):
        raise HTTPException(422, detail="filtro_empresas_invalido")


@roteador.get("/administracao/relatorios/empresas", response_model=ConsultaEmpresas)
def consultar(request: Request, banco: Banco, response: Response,
              agrupamento: Annotated[AgrupamentoEmpresas, Query()] = "clientes",
              data_inicial: Data = "", data_final: Data = "", filtro: Annotated[FiltroPainel, Query()] = "todas",
              busca: Busca = "", empresa_id: EmpresaID = None,
              deslocamento: Annotated[int, Query(ge=0)] = 0, deslocamento_itens: Annotated[int, Query(ge=0)] = 0,
              limite: Annotated[int, Query(ge=1, le=100)] = 20):
    conferir_repetidos(request)
    response.headers["Cache-Control"] = "no-store"
    return ServicoRelatorioEmpresas(banco).consultar(request.state.usuario_acesso, agrupamento,
        data_inicial, data_final, filtro, busca, empresa_id, deslocamento, deslocamento_itens, limite)


@roteador.get("/administracao/relatorios/empresas/csv")
def exportar(request: Request, banco: Banco, agrupamento: Annotated[AgrupamentoEmpresas, Query()] = "clientes",
             data_inicial: Data = "", data_final: Data = "", filtro: Annotated[FiltroPainel, Query()] = "todas",
             busca: Busca = "", empresa_id: EmpresaID = None):
    conferir_repetidos(request)
    conteudo = ServicoRelatorioEmpresas(banco).exportar(request.state.usuario_acesso, agrupamento,
        data_inicial, data_final, filtro, busca, empresa_id)
    return Response(conteudo, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="MEC_SERVICOS_RELATORIO_EMPRESAS.csv"', "Cache-Control": "no-store"})
