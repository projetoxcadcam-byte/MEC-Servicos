from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from backend.app.core.modo_teste_local import criar_sessao_teste, exigir_modo_teste, modo_teste_disponivel, publicar_sessao

from backend.app.core.armazenamento_acesso import COOKIE_SESSAO, DURACAO_SESSAO
from backend.app.core.permissoes_acesso import (
    SessaoBanco, armazenamento, identificar_usuario, verificar_csrf, verificar_origem,
)
from backend.app.models.empresa import Empresa
from backend.app.schemas.acesso import DadosAtivo, DadosEntrada, DadosRedefinicao, DadosSenha, DadosUsuario

roteador = APIRouter(prefix="/autenticacao", tags=["autenticação e contas"])


def caminho_cookie(request: Request):
    return getattr(request.app.state, "prefixo_api_acesso", "/api/v1").rstrip("/")


def cookie_seguro(request: Request) -> bool:
    configurado = os.environ.get("MEC_COOKIE_SEGURO", "").strip().lower()
    return configurado in {"1", "true", "sim"} or request.url.scheme == "https"


def sem_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def usuario_administrador(request, banco, alterar=False):
    usuario = identificar_usuario(request, banco)
    if usuario.perfil != "admin":
        raise HTTPException(403, detail="acao_exclusiva_da_administracao")
    if usuario.deve_alterar_senha:
        raise HTTPException(403, detail="troca_senha_inicial_obrigatoria")
    if alterar:
        verificar_csrf(request, usuario)
    return usuario


@roteador.post("/entrar")
def entrar(dados: DadosEntrada, request: Request, response: Response, banco: SessaoBanco):
    verificar_origem(request)
    servico = armazenamento(request)
    usuario, token = servico.entrar(dados.email, dados.senha, request.client.host if request.client else "sem_endereco",
                                   request.cookies.get(COOKIE_SESSAO))
    if usuario.perfil != "admin":
        empresa = banco.get(Empresa, usuario.empresa_id)
        if empresa is None or empresa.tipo_empresa not in {usuario.perfil, "ambos"}:
            servico.sair(token)
            raise HTTPException(403, detail="vinculo_empresa_nao_autorizado")
    response.set_cookie(COOKIE_SESSAO, token, max_age=DURACAO_SESSAO, path=caminho_cookie(request),
                        httponly=True, secure=cookie_seguro(request), samesite="strict")
    sem_cache(response)
    return {"usuario": usuario.publico(), "csrf": usuario.csrf}


@roteador.get("/sessao")
def sessao(request: Request, response: Response, banco: SessaoBanco):
    usuario = identificar_usuario(request, banco)
    sem_cache(response)
    return publicar_sessao(usuario, request.cookies.get(COOKIE_SESSAO))


@roteador.post("/sair")
def sair(request: Request, response: Response, banco: SessaoBanco):
    usuario = identificar_usuario(request, banco)
    verificar_csrf(request, usuario)
    armazenamento(request).sair(request.cookies.get(COOKIE_SESSAO))
    response.delete_cookie(COOKIE_SESSAO, path=caminho_cookie(request), httponly=True,
                           secure=cookie_seguro(request), samesite="strict")
    sem_cache(response)
    return {"status": "sessao_encerrada"}


@roteador.post("/alterar-senha")
def alterar_senha(dados: DadosSenha, request: Request, response: Response, banco: SessaoBanco):
    usuario = identificar_usuario(request, banco)
    verificar_csrf(request, usuario)
    armazenamento(request).alterar_senha(usuario.usuario_id, dados.senha_atual, dados.nova_senha)
    response.delete_cookie(COOKIE_SESSAO, path=caminho_cookie(request), httponly=True,
                           secure=cookie_seguro(request), samesite="strict")
    sem_cache(response)
    return {"status": "senha_alterada", "entrar_novamente": True}


@roteador.get("/usuarios")
def usuarios(request: Request, response: Response, banco: SessaoBanco):
    usuario_administrador(request, banco)
    sem_cache(response)
    return armazenamento(request).listar_usuarios()


@roteador.post("/usuarios", status_code=201)
def criar_usuario(dados: DadosUsuario, request: Request, response: Response, banco: SessaoBanco):
    operador = usuario_administrador(request, banco, alterar=True)
    if dados.perfil != "admin":
        empresa = banco.get(Empresa, dados.empresa_id)
        if empresa is None or empresa.tipo_empresa not in {dados.perfil, "ambos"}:
            raise HTTPException(422, detail="vinculo_empresa_invalido")
    servico = armazenamento(request)
    usuario = servico.criar_usuario(dados.nome, dados.email, dados.perfil, dados.empresa_id, dados.senha)
    servico.registrar_acao(operador.usuario_id, "criar_usuario", "usuario/" + str(usuario.usuario_id))
    sem_cache(response)
    return usuario.publico()


@roteador.patch("/usuarios/{usuario_id}/ativo")
def definir_ativo(usuario_id: int, dados: DadosAtivo, request: Request, banco: SessaoBanco):
    operador = usuario_administrador(request, banco, alterar=True)
    servico = armazenamento(request)
    servico.definir_ativo(usuario_id, dados.ativo)
    servico.registrar_acao(operador.usuario_id, "alterar_ativo", "usuario/" + str(usuario_id))
    return {"status": "atualizado"}


@roteador.post("/usuarios/{usuario_id}/redefinir-senha")
def redefinir_senha(usuario_id: int, dados: DadosRedefinicao, request: Request, banco: SessaoBanco):
    operador = usuario_administrador(request, banco, alterar=True)
    servico = armazenamento(request)
    servico.redefinir_senha(usuario_id, dados.nova_senha)
    servico.registrar_acao(operador.usuario_id, "redefinir_senha", "usuario/" + str(usuario_id))
    return {"status": "senha_redefinida", "troca_senha_obrigatoria": True}


class DadosEntradaTesteLocal(BaseModel):
    usuario_id: int = Field(gt=0, strict=True)
    model_config = ConfigDict(extra="forbid")


@roteador.get("/teste-local")
def contas_teste_local(request: Request, response: Response, banco: SessaoBanco):
    sem_cache(response)
    if not modo_teste_disponivel(request):
        return {"ativo": False, "contas": []}
    contas = []
    for conta in armazenamento(request).listar_usuarios():
        if not conta["ativo"]:
            continue
        if conta["role"] != "admin":
            empresa = banco.get(Empresa, conta["empresa_id"])
            if empresa is None or empresa.tipo_empresa not in {conta["role"], "ambos"}:
                continue
        contas.append(conta)
    return {"ativo": True, "contas": contas}


@roteador.post("/teste-local/entrar")
def entrar_teste_local(dados: DadosEntradaTesteLocal, request: Request, response: Response, banco: SessaoBanco):
    exigir_modo_teste(request)
    verificar_origem(request)
    servico = armazenamento(request)
    conta = next((c for c in servico.listar_usuarios() if c["usuario_id"] == dados.usuario_id and c["ativo"]), None)
    if conta is None:
        raise HTTPException(403, detail="conta_teste_local_indisponivel")
    if conta["role"] != "admin":
        empresa = banco.get(Empresa, conta["empresa_id"])
        if empresa is None or empresa.tipo_empresa not in {conta["role"], "ambos"}:
            raise HTTPException(403, detail="vinculo_empresa_nao_autorizado")
    usuario, token = criar_sessao_teste(request, servico, dados.usuario_id, request.cookies.get(COOKIE_SESSAO))
    response.set_cookie(COOKIE_SESSAO, token, max_age=DURACAO_SESSAO, path=caminho_cookie(request),
                        httponly=True, secure=cookie_seguro(request), samesite="strict")
    sem_cache(response)
    return publicar_sessao(usuario, token)
