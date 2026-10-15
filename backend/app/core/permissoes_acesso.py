from __future__ import annotations

import hmac
import json
import os
import re
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, COOKIE_SESSAO, UsuarioAcesso
from backend.app.core.modo_teste_local import adaptar_usuario_teste
from backend.app.database.sessao import obter_banco
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.empresa import Empresa
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.intermediacao import proteger_ciclo_legado
from backend.app.services.financeiro_administrativo import proteger_financeiro_legado

SessaoBanco = Annotated[Session, Depends(obter_banco)]


def armazenamento(request: Request) -> ArmazenamentoAcesso:
    padrao = Path(__file__).resolve().parents[3] / "data/mec_acessos.db"
    caminho = getattr(request.app.state, "caminho_acessos", None) or os.environ.get("MEC_ACESSOS_DB") or padrao
    return ArmazenamentoAcesso(Path(caminho))


def verificar_origem(request: Request) -> None:
    origem = request.headers.get("origin")
    if not origem:
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, detail="origem_nao_autorizada")
        return
    mesma_origem = origem.rstrip("/") == str(request.base_url).rstrip("/")
    locais = origem.rstrip("/") in {"http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"}
    servidor_local = request.url.hostname in {"localhost", "127.0.0.1", "testserver"}
    configuradas = {item.strip().rstrip("/") for item in os.environ.get("MEC_ORIGENS_PERMITIDAS", "").split(",") if item.strip()}
    if origem == "null" or not (mesma_origem or (locais and servidor_local) or origem.rstrip("/") in configuradas):
        raise HTTPException(403, detail="origem_nao_autorizada")


def identificar_usuario(request: Request, banco: Session) -> UsuarioAcesso:
    token = request.cookies.get(COOKIE_SESSAO)
    usuario = armazenamento(request).obter_sessao(token)
    usuario = adaptar_usuario_teste(request, usuario, token)
    if usuario.perfil != "admin":
        empresa = banco.get(Empresa, usuario.empresa_id)
        if empresa is None or empresa.tipo_empresa not in {usuario.perfil, "ambos"}:
            raise HTTPException(403, detail="vinculo_empresa_nao_autorizado")
    request.state.usuario_acesso = usuario
    if usuario.perfil=='fornecedor' and re.search(r'/portal-fornecedor/(?:contratacoes|ordens-servico|producao|entregas)(?:/|$)',request.url.path):
        from sqlalchemy import text
        from backend.app.services.precos_portais import mapa_portal
        conexao=banco.connection()
        if conexao.dialect.name=='sqlite' and not conexao.connection.driver_connection.in_transaction:
            banco.execute(text('BEGIN' if request.method in {'GET','HEAD'} else 'BEGIN IMMEDIATE'))
        request.state.custos_fornecedor=mapa_portal(banco,usuario)
    return usuario


def verificar_csrf(request: Request, usuario: UsuarioAcesso) -> None:
    verificar_origem(request)
    recebido = request.headers.get("x-mec-csrf", "")
    if not recebido or not hmac.compare_digest(recebido.encode("utf-8"), usuario.csrf.encode("utf-8")):
        raise HTTPException(403, detail="sessao_alterada_entre_novamente")


def inteiro(valor) -> int | None:
    if type(valor) is int and valor > 0:
        return valor
    if isinstance(valor, str) and re.fullmatch(r"[1-9]\d{0,12}", valor):
        return int(valor)
    return None


async def vincular_parametros(request: Request, usuario: UsuarioAcesso, exigir_query: bool = False) -> None:
    campo = "empresa_cliente_id" if usuario.perfil == "cliente" else "empresa_fornecedora_id"
    for nome in (campo, "empresa_id"):
        valores = request.query_params.getlist(nome)
        if valores and (len(valores) != 1 or inteiro(valores[0]) != usuario.empresa_id):
            raise HTTPException(403, detail="empresa_diverge_da_sessao")
    if exigir_query and not request.query_params.getlist(campo):
        raise HTTPException(403, detail="empresa_da_sessao_obrigatoria")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and "application/json" in request.headers.get("content-type", ""):
        tamanho = request.headers.get("content-length", "")
        if tamanho.isdigit() and int(tamanho) > 1_000_000:
            raise HTTPException(413, detail="corpo_requisicao_muito_grande")
        corpo = await request.body()
        if len(corpo) > 1_000_000:
            raise HTTPException(413, detail="corpo_requisicao_muito_grande")
        try:
            dados = json.loads(corpo)
        except (ValueError, UnicodeError):
            raise HTTPException(422, detail="corpo_json_invalido") from None
        if not isinstance(dados, dict):
            raise HTTPException(422, detail="corpo_json_invalido")
        for nome in (campo, "empresa_id"):
            if nome in dados and inteiro(dados[nome]) != usuario.empresa_id:
                raise HTTPException(403, detail="empresa_diverge_da_sessao")
        if any(nome in dados for nome in ("role", "perfil", "usuario_id")):
            raise HTTPException(403, detail="perfil_e_usuario_definidos_pelo_servidor")


def solicitacao_propria(banco: Session, solicitacao_id: int, usuario: UsuarioAcesso) -> None:
    item = banco.get(SolicitacaoServico, solicitacao_id)
    if item is None or item.empresa_cliente_id != usuario.empresa_id:
        raise HTTPException(404, detail="solicitacao_nao_encontrada")


async def autorizar_requisicao(request: Request, banco: SessaoBanco) -> None:
    banco.info.pop("mec_usuario_notificacoes", None)
    prefixo = getattr(request.app.state, "prefixo_api_acesso", "/api/v1").rstrip("/")
    caminho = request.url.path[len(prefixo):] if request.url.path.startswith(prefixo + "/") else request.url.path
    if request.method == "GET" and caminho in {"/saude", "/banco-dados/saude"}:
        return
    usuario = identificar_usuario(request, banco)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        verificar_csrf(request, usuario)
    if usuario.deve_alterar_senha:
        raise HTTPException(403, detail="troca_senha_inicial_obrigatoria")
    banco.info["mec_usuario_notificacoes"] = usuario
    if usuario.perfil == "admin":
        proteger_ciclo_legado(banco, caminho, request.method, usuario)
        proteger_financeiro_legado(banco, caminho, request.method)
        return
    await vincular_parametros(request, usuario)
    if (request.method == "GET" and caminho in {"/notificacoes", "/notificacoes/resumo"}) or (request.method == "POST" and (caminho == "/notificacoes/ler-ate" or re.fullmatch(r"/notificacoes/[1-9]\d*/ler", caminho))):
        return
    if request.method == "GET" and caminho in {"/materiais", "/processos-fabricacao"}:
        return
    empresa = re.fullmatch(r"/empresas/([1-9]\d*)(?:/(capacidades|maquinas|materiais))?", caminho)
    if empresa and int(empresa[1]) == usuario.empresa_id:
        if request.method == "GET" or (usuario.perfil == "fornecedor" and empresa[2] and request.method == "POST"):
            return
    portal = "/portal-" + usuario.perfil + "/"
    if caminho.startswith(portal):
        restante = caminho[len(portal):]
        if request.method == "GET" and re.fullmatch(r"avaliacoes(?:/[1-9]\d*)?", restante):
            return
        if usuario.perfil == "cliente" and request.method == "POST" and re.fullmatch(r"avaliacoes/[1-9]\d*", restante):
            return
        if usuario.perfil == "cliente" and request.method == "POST" and re.fullmatch(r"cotacoes/[1-9]\d*/analise", restante):
            await vincular_parametros(request,usuario,exigir_query=True)
            return
        if usuario.perfil == "fornecedor" and ("/arquivos" in "/" + restante or "/download" in restante):
            lista = re.fullmatch(r"solicitacoes/([1-9]\d*)/arquivos", restante)
            download = re.fullmatch(r"arquivos/([1-9]\d*)/download", restante)
            if request.method == "GET" and (lista or download):
                await vincular_parametros(request, usuario, exigir_query=True)
                from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao
                from backend.app.services.portal_fornecedor import ServicoPortalFornecedor
                arquivo = banco.get(ArquivoTecnico, int(download[1])) if download else None
                if download and arquivo is None:
                    raise HTTPException(403, detail="arquivo_aguarda_liberacao_administrativa")
                solicitacao_id = int(lista[1]) if lista else arquivo.solicitacao_id
                documentos = ServicoDocumentacaoCotacao(banco)
                documentos.exigir_acesso(solicitacao_id, arquivo.id if arquivo else None)
                ServicoPortalFornecedor(banco).validar_acesso_arquivos(solicitacao_id, usuario.empresa_id)
                return
            raise HTTPException(403, detail="arquivo_aguarda_liberacao_administrativa")
        if request.method == "GET":
            leituras = (r"painel", r"(?:contratacoes|ordens-servico|producao|entregas)(?:/[1-9]\d*)?", r"intermediacao/[1-9]\d*", r"financeiro(?:/[1-9]\d*)?",)
            if usuario.perfil == "cliente":
                leituras += (r"cotacoes(?:/[1-9]\d*)?", r"cotacoes-aceitas", r"contratacoes-para-ordem",
                             r"(?:contratacoes|ordens-servico)/[1-9]\d*/arquivos(?:/[1-9]\d*/download)?")
            else:
                leituras += (r"oportunidades", r"cotacoes")
            if any(re.fullmatch(padrao, restante) for padrao in leituras):
                await vincular_parametros(request, usuario, exigir_query=True)
                return
        if usuario.perfil == "fornecedor" and request.method == "POST":
            permitidas = (r"solicitacoes/[1-9]\d*/cotacoes", r"ordens-servico/[1-9]\d*/iniciar", r"producao/[1-9]\d*/etapas")
            if any(re.fullmatch(padrao, restante) for padrao in permitidas):
                proteger_ciclo_legado(banco, caminho, request.method, usuario)
                return
        raise HTTPException(403, detail="acao_exclusiva_da_administracao")
    if usuario.perfil == "cliente":
        if caminho == "/solicitacoes-servico":
            if request.method == "GET":
                await vincular_parametros(request, usuario, exigir_query=True)
                return
            if request.method == "POST":
                return
        solicitacao = re.fullmatch(r"/solicitacoes-servico/([1-9]\d*)(?:/(cotacoes|arquivos-tecnicos))?", caminho)
        if solicitacao:
            solicitacao_propria(banco, int(solicitacao[1]), usuario)
            if request.method == "GET" or (solicitacao[2] == "arquivos-tecnicos" and request.method == "POST"):
                return
        arquivo = re.fullmatch(r"/arquivos-tecnicos/([1-9]\d*)(/download)?", caminho)
        if arquivo and request.method in {"GET", "DELETE"}:
            item = banco.get(ArquivoTecnico, int(arquivo[1]))
            if item is None:
                raise HTTPException(404, detail="arquivo_tecnico_nao_encontrado")
            solicitacao_propria(banco, item.solicitacao_id, usuario)
            if request.method == "GET" or arquivo[2] is None:
                return
    # Rotas legadas e rotas novas não liberadas explicitamente exigem operador.
    raise HTTPException(403, detail="acao_exclusiva_da_administracao")
