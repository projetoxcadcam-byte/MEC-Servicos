from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.painel_perfis import PainelPerfisLeitura
from backend.app.services.painel_perfis import ServicoPainelPerfis

roteador = APIRouter(tags=["painel-dos-portais"])
Banco = Annotated[Session, Depends(obter_banco)]
Empresa = Annotated[int, Query(gt=0)]


def consultar(perfil, empresa, request, response, banco):
    usuario = request.state.usuario_acesso
    if usuario.perfil != perfil or usuario.empresa_id != empresa:
        raise HTTPException(403, detail="perfil_ou_empresa_diverge_da_sessao")
    s = ServicoPainelPerfis(banco, usuario)
    recebido = request.headers.get("x-mec-painel-contexto")
    if recebido is not None and recebido != s.contexto():
        raise HTTPException(409, detail="contexto_painel_alterado")
    response.headers["Cache-Control"] = "no-store"
    return s.consultar()


@roteador.get("/portal-cliente/painel", response_model=PainelPerfisLeitura)
def cliente(request: Request, response: Response, banco: Banco, empresa_cliente_id: Empresa):
    return consultar("cliente", empresa_cliente_id, request, response, banco)


@roteador.get("/portal-fornecedor/painel", response_model=PainelPerfisLeitura)
def fornecedor(request: Request, response: Response, banco: Banco, empresa_fornecedora_id: Empresa):
    return consultar("fornecedor", empresa_fornecedora_id, request, response, banco)
