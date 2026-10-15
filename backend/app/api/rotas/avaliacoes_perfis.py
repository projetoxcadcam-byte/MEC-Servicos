from __future__ import annotations

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.avaliacao_perfil import RegistrarAvaliacaoPerfil
from backend.app.services.avaliacoes_perfis import ServicoAvaliacoesPerfis

roteador = APIRouter(tags=["avaliacoes-por-perfil"])
Banco = Annotated[Session, Depends(obter_banco)]
Identificador = Annotated[int, Path(gt=0)]


def servico(request, response, banco):
    usuario = request.state.usuario_acesso
    prefixo = "/administracao/" if usuario.perfil == "admin" else f"/portal-{usuario.perfil}/"
    caminho = request.url.path.removeprefix(request.app.state.prefixo_api_acesso)
    if not caminho.startswith(prefixo):
        raise HTTPException(403, detail="perfil_diverge_da_sessao")
    s = ServicoAvaliacoesPerfis(banco, usuario)
    recebido = request.headers.get("x-mec-avaliacoes-contexto")
    if recebido is not None and recebido != s.contexto():
        raise HTTPException(409, detail="contexto_avaliacoes_alterado")
    response.headers["Cache-Control"] = "no-store"
    return s


@roteador.get("/administracao/avaliacoes")
@roteador.get("/portal-cliente/avaliacoes")
@roteador.get("/portal-fornecedor/avaliacoes")
def listar(request: Request, response: Response, banco: Banco,
           contratacao_id: int | None = Query(default=None, gt=0), ordem_servico_id: int | None = Query(default=None, gt=0),
           situacao: Literal["todas", "disponiveis", "avaliadas"] = "todas",
           inicio: int = Query(default=0, ge=0, le=1_000_000), limite: int = Query(default=20, ge=1, le=100)):
    return servico(request, response, banco).listar(contratacao_id, ordem_servico_id, situacao, inicio, limite)


@roteador.get("/administracao/avaliacoes/ranking")
def ranking(request: Request, response: Response, banco: Banco, origem: Literal["cliente", "admin"] = "cliente",
            inicio: int = Query(default=0, ge=0, le=1_000_000), limite: int = Query(default=20, ge=1, le=100),
            busca: str = Query(default="", max_length=160)):
    return servico(request, response, banco).ranking(origem, inicio, limite, busca)


@roteador.get("/administracao/avaliacoes/fornecedores/{empresa_id}/historico")
def historico_fornecedor(empresa_id: Identificador, request: Request, response: Response, banco: Banco,
                         inicio: int = Query(default=0, ge=0, le=1_000_000), limite: int = Query(default=20, ge=1, le=100)):
    return servico(request, response, banco).historico_fornecedor(empresa_id, inicio, limite)


@roteador.get("/administracao/avaliacoes/{contratacao_id}")
@roteador.get("/portal-cliente/avaliacoes/{contratacao_id}")
@roteador.get("/portal-fornecedor/avaliacoes/{contratacao_id}")
def obter(contratacao_id: Identificador, request: Request, response: Response, banco: Banco):
    return servico(request, response, banco).obter(contratacao_id)


@roteador.post("/administracao/avaliacoes/{contratacao_id}", status_code=201)
@roteador.post("/portal-cliente/avaliacoes/{contratacao_id}", status_code=201)
def registrar(contratacao_id: Identificador, dados: RegistrarAvaliacaoPerfil, request: Request, response: Response, banco: Banco):
    return servico(request, response, banco).registrar(contratacao_id, dados)
