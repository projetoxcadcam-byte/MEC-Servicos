from __future__ import annotations

import json

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from backend.app.core.armazenamento_acesso import UsuarioAcesso

CONTATOS = {"email", "e_mail", "telefone", "celular", "whatsapp", "endereco", "documento", "contato"}
TEXTOS_REVISAR = {"observacoes", "motivo", "motivo_recusa", "observacoes_contratacao"}


def dados_portal(valor, usuario: UsuarioAcesso):
    if isinstance(valor, list):
        return [dados_portal(item, usuario) for item in valor]
    if not isinstance(valor, dict):
        return valor
    retorno = {}
    for chave, item in valor.items():
        if chave in CONTATOS or chave in TEXTOS_REVISAR:
            retorno[chave] = None
        elif chave == "cliente_razao_social" and usuario.perfil == "fornecedor":
            empresa = valor.get("empresa_cliente_id")
            retorno[chave] = "Cliente C-" + (str(empresa).zfill(4) if isinstance(empresa, int) else "reservado")
        elif chave == "fornecedor_razao_social" and usuario.perfil == "cliente":
            empresa = valor.get("empresa_fornecedora_id")
            retorno[chave] = "Fornecedor F-" + (str(empresa).zfill(4) if isinstance(empresa, int) else "reservado")
        elif chave == "razao_social":
            retorno[chave] = "Empresa identificada pela administração"
        elif chave in {"descricao", "titulo", "nome_cliente", "nome_fornecedor"}:
            retorno[chave] = "Informação encaminhada pela administração"
        elif chave == "caminho_arquivo":
            retorno[chave] = None
        else:
            retorno[chave] = dados_portal(item, usuario)
    return retorno


async def erro_validacao_acesso(request: Request, erro: RequestValidationError):
    prefixo = getattr(request.app.state, "prefixo_api_acesso", "/api/v1").rstrip("/")
    if request.url.path.startswith(prefixo + "/autenticacao/"):
        # Evita repetir senhas e dados de criação de conta em erros de validação.
        return JSONResponse({"detail": "dados_de_acesso_invalidos"}, status_code=422, headers={"Cache-Control": "no-store"})
    return await request_validation_exception_handler(request, erro)


class PrivacidadePortais:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        inicio = None; partes = []; tamanho = 0; filtrar = False

        async def enviar(mensagem):
            nonlocal inicio, tamanho, filtrar
            usuario = scope.get("state", {}).get("usuario_acesso")
            if mensagem["type"] == "http.response.start":
                headers = list(mensagem.get("headers", []))
                tipo = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                prefixo = getattr(getattr(scope.get("app"), "state", None), "prefixo_api_acesso", "/api/v1").rstrip("/")
                caminho = scope.get("path", "")[len(prefixo):]
                propria_empresa = usuario is not None and caminho == "/empresas/" + str(usuario.empresa_id)
                filtrar = (usuario is not None and usuario.perfil in {"cliente", "fornecedor"}
                           and 200 <= mensagem["status"] < 300 and mensagem["status"] not in {204, 205}
                           and scope.get("method") != "HEAD" and b"application/json" in tipo
                           and not caminho.startswith("/autenticacao/") and not propria_empresa)
                if usuario is not None:
                    headers = [(k, v) for k, v in headers if k.lower() not in {b"cache-control"}]
                    headers += [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
                mensagem = {**mensagem, "headers": headers}
                if filtrar:
                    inicio = mensagem
                    return
            elif mensagem["type"] == "http.response.body" and filtrar:
                corpo = mensagem.get("body", b""); tamanho += len(corpo)
                if tamanho <= 2_000_000:
                    partes.append(corpo)
                else:
                    partes.clear()
                if mensagem.get("more_body", False):
                    return
                try:
                    if tamanho > 2_000_000:
                        raise ValueError("Resposta maior que o limite.")
                    dados = dados_portal(json.loads(b"".join(partes)), usuario)
                    if usuario.perfil=='fornecedor':
                        from backend.app.services.precos_portais import reservar_valores
                        dados=reservar_valores(dados,scope.get('state',{}).get('custos_fornecedor',{}))
                    novo = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    headers = [(k, v) for k, v in inicio["headers"] if k.lower() != b"content-length"]
                    await send({**inicio, "headers": headers + [(b"content-length", str(len(novo)).encode())]})
                    await send({"type": "http.response.body", "body": novo, "more_body": False})
                except (ValueError, TypeError, UnicodeError):
                    resposta = JSONResponse({"detail": "resposta_portal_nao_disponivel"}, status_code=503,
                                             headers={"Cache-Control": "no-store"})
                    await resposta(scope, receive, send)
                return
            await send(mensagem)
        await self.app(scope, receive, enviar)
