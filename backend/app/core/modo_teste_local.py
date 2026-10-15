"""Entrada por conta para testes no computador local; desativada por padrão."""
from __future__ import annotations

from dataclasses import replace
import ipaddress
import os
import secrets
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, DURACAO_SESSAO, UsuarioAcesso
from backend.app.core.configuracao import configuracoes

PREFIXO_TOKEN_TESTE = "mec_teste_local_"


def endereco_local(valor: str | None) -> bool:
    if valor == "localhost":
        return True
    try:
        endereco = ipaddress.ip_address(valor or "")
        return endereco.is_loopback or bool(getattr(endereco, "ipv4_mapped", None) and endereco.ipv4_mapped.is_loopback)
    except ValueError:
        return False


def modo_teste_disponivel(request: Request) -> bool:
    habilitado = os.environ.get("MEC_MODO_TESTE_LOCAL", "").strip().lower() in {"1", "true", "sim"}
    ambiente = os.environ.get("MEC_AMBIENTE", configuracoes.ambiente).strip().casefold()
    if not habilitado or ambiente not in {"desenvolvimento", "teste"}:
        return False
    if not request.client or not endereco_local(request.client.host) or not endereco_local(request.url.hostname):
        return False
    if request.headers.get("sec-fetch-site") == "cross-site" or request.headers.get("forwarded"):
        return False
    encaminhados = request.headers.get("x-forwarded-for", "")
    if encaminhados and not all(endereco_local(item.strip()) for item in encaminhados.split(",")):
        return False
    origem = request.headers.get("origin")
    if origem:
        try:
            partes = urlsplit(origem)
            if partes.scheme not in {"http", "https"} or not endereco_local(partes.hostname) or partes.username or partes.password or partes.query or partes.fragment or partes.path not in {"", "/"}:
                return False
            if partes.port is not None and not 1 <= partes.port <= 65535:
                return False
        except ValueError:
            return False
    return True


def exigir_modo_teste(request: Request) -> None:
    if not modo_teste_disponivel(request):
        raise HTTPException(403, detail="modo_teste_local_indisponivel")


def adaptar_usuario_teste(request: Request, usuario: UsuarioAcesso, token: str | None) -> UsuarioAcesso:
    if not token or not token.startswith(PREFIXO_TOKEN_TESTE):
        return usuario
    if not modo_teste_disponivel(request):
        raise HTTPException(401, detail="sessao_teste_local_encerrada")
    # A troca inicial continua registrada na conta. Somente esta sessão de teste
    # usa o portal sem solicitar a senha; o login normal mantém a regra D30.
    return replace(usuario, deve_alterar_senha=False)


def publicar_sessao(usuario: UsuarioAcesso, token: str | None) -> dict:
    publico = usuario.publico()
    if token and token.startswith(PREFIXO_TOKEN_TESTE):
        publico["teste_local"] = True
    return {"usuario": publico, "csrf": usuario.csrf}


def criar_sessao_teste(request: Request, servico: ArmazenamentoAcesso, usuario_id: int, token_anterior: str | None = None):
    exigir_modo_teste(request)
    if request.headers.get("x-mec-teste-local") != "1":
        raise HTTPException(403, detail="entrada_teste_local_nao_confirmada")
    if type(usuario_id) is not int or usuario_id <= 0:
        raise HTTPException(422, detail="dados_de_acesso_invalidos")
    agora = time.time()
    token = PREFIXO_TOKEN_TESTE + secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with servico._conexao() as banco:
        banco.execute("BEGIN IMMEDIATE")
        linha = banco.execute("SELECT * FROM usuarios_acesso WHERE id=? AND ativo=1", (usuario_id,)).fetchone()
        if linha is None:
            raise HTTPException(403, detail="conta_teste_local_indisponivel")
        banco.execute("DELETE FROM sessoes_acesso WHERE expira_em<=?", (agora,))
        if token_anterior:
            banco.execute("DELETE FROM sessoes_acesso WHERE token_hash=?", (servico._hash(token_anterior),))
        banco.execute("INSERT INTO sessoes_acesso VALUES(?,?,?,?)", (servico._hash(token), usuario_id, csrf, agora + DURACAO_SESSAO))
        banco.execute("INSERT INTO auditoria_acesso(usuario_id,acao,recurso,instante) VALUES(?,?,?,?)", (usuario_id, "entrar_teste_local", "sessao_local", agora))
        usuario = replace(servico._usuario(linha, csrf), deve_alterar_senha=False)
    return usuario, token
