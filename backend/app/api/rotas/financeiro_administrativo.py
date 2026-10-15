from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.financeiro_administrativo import (
    ConsultaFinanceiroPortal, DetalheFinanceiro, InicioFinanceiro, PaginaFinanceiro, PaginaFinanceiroPortal, RegistroFinanceiro,
)
from backend.app.services.financeiro_administrativo import ServicoFinanceiroAdministrativo

roteador = APIRouter(tags=["financeiro administrativo"])
Banco = Annotated[Session, Depends(obter_banco)]
Id = Annotated[int, Path(gt=0)]
EmpresaId = Annotated[int, Query(gt=0)]
Deslocamento = Annotated[int, Query(ge=0)]
Limite = Annotated[int, Query(ge=1, le=100)]
ADMIN = "/administracao/financeiro"


@roteador.get(ADMIN + "/contratacoes", response_model=PaginaFinanceiro)
def listar(request: Request, banco: Banco, deslocamento: Deslocamento = 0, limite: Limite = 20):
    return ServicoFinanceiroAdministrativo(banco).listar(request.state.usuario_acesso, deslocamento, limite)


@roteador.get(ADMIN + "/contratacoes/{contratacao_id}", response_model=DetalheFinanceiro)
def obter(contratacao_id: Id, request: Request, banco: Banco):
    return ServicoFinanceiroAdministrativo(banco).obter(contratacao_id, request.state.usuario_acesso)


@roteador.post(ADMIN + "/contratacoes/{contratacao_id}/iniciar", response_model=DetalheFinanceiro, status_code=201)
def iniciar(contratacao_id: Id, dados: InicioFinanceiro, request: Request, banco: Banco):
    return ServicoFinanceiroAdministrativo(banco).iniciar(contratacao_id, dados, request.state.usuario_acesso)


@roteador.post(ADMIN + "/contratacoes/{contratacao_id}/eventos", response_model=DetalheFinanceiro, status_code=201)
def registrar(contratacao_id: Id, dados: RegistroFinanceiro, request: Request, banco: Banco):
    return ServicoFinanceiroAdministrativo(banco).registrar(contratacao_id, dados, request.state.usuario_acesso)


@roteador.get("/portal-cliente/financeiro", response_model=PaginaFinanceiroPortal)
def listar_cliente(empresa_cliente_id: EmpresaId, request: Request, banco: Banco, deslocamento: Deslocamento = 0, limite: Limite = 20):
    return ServicoFinanceiroAdministrativo(banco).listar_portal(request.state.usuario_acesso, "cliente", empresa_cliente_id, deslocamento, limite)


@roteador.get("/portal-cliente/financeiro/{contratacao_id}", response_model=ConsultaFinanceiroPortal)
def cliente(contratacao_id: Id, empresa_cliente_id: EmpresaId, request: Request, banco: Banco):
    return ServicoFinanceiroAdministrativo(banco).consultar_portal(contratacao_id, request.state.usuario_acesso, "cliente", empresa_cliente_id)


@roteador.get("/portal-fornecedor/financeiro", response_model=PaginaFinanceiroPortal)
def listar_fornecedor(empresa_fornecedora_id: EmpresaId, request: Request, banco: Banco, deslocamento: Deslocamento = 0, limite: Limite = 20):
    return ServicoFinanceiroAdministrativo(banco).listar_portal(request.state.usuario_acesso, "fornecedor", empresa_fornecedora_id, deslocamento, limite)


@roteador.get("/portal-fornecedor/financeiro/{contratacao_id}", response_model=ConsultaFinanceiroPortal)
def fornecedor(contratacao_id: Id, empresa_fornecedora_id: EmpresaId, request: Request, banco: Banco):
    return ServicoFinanceiroAdministrativo(banco).consultar_portal(contratacao_id, request.state.usuario_acesso, "fornecedor", empresa_fornecedora_id)
