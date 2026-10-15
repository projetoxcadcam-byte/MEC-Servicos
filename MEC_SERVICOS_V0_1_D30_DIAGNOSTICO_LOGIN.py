r"""Diagnóstico local de login. Não transmite senhas nem modifica contas.

Execute na raiz do projeto, com o backend e o frontend em execução:
    python .\MEC_SERVICOS_V0_1_D30_DIAGNOSTICO_LOGIN.py
Se o frontend usa outra porta: acrescente --frontend http://localhost:PORTA
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

REVISION = "MEC-SERVICOS-V0.1-D30-DIAGNOSTICO-LOGIN-2026-10-05"
STEM = "MEC_SERVICOS_V0_1_D30_DIAGNOSTICO_LOGIN_RELATORIO"
RELATORIO_FIX2 = "MEC_SERVICOS_V0_1_D30_FIX2_ACESSOS_INICIAIS_RELATORIO.json"
HASHES_LOGIN = {'backend/app/principal.py': 'a3f94cbfc7b0e011babca7032f296c50ed768b9967e37f7be5ba991d41924f99', 'backend/app/schemas/acesso.py': '3e94365b1b588cb4cfe273de69dd8b96bd3543a8ae47549f240d9daa6d58b862', 'frontend/src/auth/AuthContext.tsx': '838f03f499b1374014428e0587d19589058d512ebca0520355b2f28867a9a7a6', 'frontend/src/services/acesso.ts': 'c4c799053bcb9338a55c649a95ae80df45f4b294754c9bb751b0c4e062697ee5', 'frontend/src/pages/auth/LoginPage.tsx': 'ec2f04eb6da751d278e7faeb1f9acae21241bb39cec64f72e5bd9801accc7786'}


def localizar_raiz():
    for raiz in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        if (raiz / "backend/app/principal.py").is_file() and (raiz / "frontend/package.json").is_file():
            return raiz
    raise RuntimeError("Execute na raiz MEC-Servicos.")


def endereco_local(valor):
    p = urlsplit(valor)
    if p.scheme != "http" or p.hostname not in {"localhost", "127.0.0.1", "::1"} or p.username or p.password or p.query or p.fragment or p.path not in {"", "/"}:
        raise ValueError("Informe somente um endereço HTTP local, por exemplo http://localhost:5173.")
    try:
        if p.port is not None and not 1 <= p.port <= 65535:
            raise ValueError()
    except ValueError:
        raise ValueError("Porta local inválida.") from None
    return valor.rstrip("/")


class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def consultar(base, caminho, metodo="GET"):
    # Sem cookies, senhas, proxy externo ou redirecionamento para outro servidor.
    req = Request(base + caminho, data=b"{}" if metodo == "POST" else None,
                  method=metodo, headers={"Accept": "application/json", "Content-Type": "application/json"})
    cliente = build_opener(ProxyHandler({}), SemRedirecionamento())
    try:
        try:
            resposta = cliente.open(req, timeout=3)
        except HTTPError as erro:
            resposta = erro
        with resposta:
            status = resposta.code
            tipo = resposta.headers.get_content_type()
            bruto = resposta.read(1_000_001)
        corpo = {}
        if len(bruto) <= 1_000_000 and tipo == "application/json":
            try:
                corpo = json.loads(bruto)
            except (ValueError, UnicodeError):
                pass
        return {"status": status, "json": tipo == "application/json", "html": tipo == "text/html"}, corpo
    except (OSError, URLError):
        return {"status": None, "conexao": "indisponivel"}, {}


def contrato_login(openapi):
    try:
        rota = openapi["paths"]["/api/v1/autenticacao/entrar"]["post"]
        esquema = rota["requestBody"]["content"]["application/json"]["schema"]
        for _ in range(5):
            if "$ref" not in esquema:
                break
            referencia = esquema["$ref"]
            if not referencia.startswith("#/"):
                return False
            esquema = openapi
            for parte in referencia[2:].split("/"):
                esquema = esquema[parte.replace("~1", "/").replace("~0", "~")]
        propriedades = esquema["properties"]
        return (not any(p.get("required") for p in rota.get("parameters", []))
                and esquema.get("type") == "object" and {"email", "senha"}.issubset(esquema.get("required", []))
                and all(propriedades[n].get("type") == "string" and "default" not in propriedades[n] for n in ("email", "senha")))
    except (KeyError, TypeError, AttributeError):
        return False


def senha_confere(senha, armazenado):
    try:
        algoritmo, repeticoes, sal, esperado = armazenado.split("$")
        numero = int(repeticoes)
        if algoritmo != "pbkdf2_sha256" or not 600_000 <= numero <= 2_000_000 or len(senha) > 128:
            return False
        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), base64.urlsafe_b64decode(sal), numero)
        return hmac.compare_digest(calculado, base64.urlsafe_b64decode(esperado))
    except (ValueError, TypeError, UnicodeError):
        return False


def conferir_credenciais(raiz):
    resultado = {"banco_somente_leitura": True, "perfis": []}
    relatorio = json.loads((raiz / RELATORIO_FIX2).read_text(encoding="utf-8-sig"))
    if relatorio.get("resultado") != "OK":
        raise RuntimeError("O relatório do FIX2 não indica instalação concluída.")
    privado = Path(relatorio.get("credenciais_locais", ""))
    if not privado.is_absolute():
        privado = raiz / privado
    if not privado.resolve().is_relative_to((raiz / "data").resolve()) or not privado.is_file():
        raise RuntimeError("O arquivo de acessos indicado pelo FIX2 não está disponível na pasta data.")
    registros = []; registro = None
    for linha in privado.read_text(encoding="utf-8-sig").splitlines():
        if linha.startswith("PERFIL="):
            registro = {}; registros.append(registro)
        if registro is not None and "=" in linha:
            chave, valor = linha.split("=", 1)
            if chave in {"PERFIL", "EMAIL", "SENHA_INICIAL"}:
                registro[chave] = valor
    banco = raiz / "data/mec_acessos.db"
    if not banco.is_file():
        raise RuntimeError("O banco de acesso local não foi encontrado.")
    with closing(sqlite3.connect(banco.resolve().as_uri() + "?mode=ro", uri=True)) as conexao:
        conexao.execute("PRAGMA query_only=ON")
        for c in registros:
            perfil = c.get("PERFIL")
            if perfil not in {"admin", "cliente", "fornecedor"}:
                continue
            linha = conexao.execute("SELECT perfil,ativo,trocar_senha,senha_hash FROM usuarios_acesso WHERE email=?", (c.get("EMAIL", "").strip().casefold(),)).fetchone()
            resultado["perfis"].append({"perfil": perfil, "conta_encontrada": linha is not None,
                "perfil_confere": bool(linha and linha[0] == perfil), "ativa": bool(linha and linha[1]),
                "troca_inicial_pendente": bool(linha and linha[2]),
                "senha_do_arquivo_confere": bool(linha and senha_confere(c.get("SENHA_INICIAL", ""), linha[3]))})
    # Não devolve e-mails, senhas, hashes de senha ou conteúdo do arquivo privado.
    return resultado


def main():
    parser = argparse.ArgumentParser(description="Conferir o login MEC sem transmitir senhas ou alterar contas.")
    parser.add_argument("--backend", type=endereco_local, default="http://127.0.0.1:8000")
    parser.add_argument("--frontend", type=endereco_local, default="http://localhost:5173")
    args = parser.parse_args()
    print("MEC-Serviços D30 — Diagnóstico local do login")
    print("REVISION=" + REVISION)
    raiz = localizar_raiz()
    dados = {"revision": REVISION, "resultado": "DIAGNOSTICO", "codigo_aplicacao_alterado": False,
             "contas_alteradas": False, "senhas_transmitidas": False, "tentativas_login_realizadas": False}
    try:
        dados["fontes_login_d30_conferem"] = all((raiz / nome).is_file() and hashlib.sha256((raiz / nome).read_bytes()).hexdigest() == valor for nome, valor in HASHES_LOGIN.items())
        print("FONTES_LOGIN_D30_CONFEREM=" + str(dados["fontes_login_d30_conferem"]))
        try:
            dados["acessos_locais"] = conferir_credenciais(raiz)
            for c in dados["acessos_locais"]["perfis"]:
                print("PERFIL=" + c["perfil"] + " | CONTA_ATIVA=" + str(c["ativa"])
                      + " | SENHA_DO_ARQUIVO_CONFERE=" + str(c["senha_do_arquivo_confere"])
                      + " | TROCA_INICIAL_PENDENTE=" + str(c["troca_inicial_pendente"]))
        except (OSError, ValueError, TypeError, sqlite3.Error, RuntimeError):
            dados["acessos_locais"] = {"verificacao": "indisponivel", "orientacao": "Confira o relatório FIX2, o arquivo local indicado e o banco data/mec_acessos.db."}
            print("VERIFICACAO_CREDENCIAIS_LOCAIS=INDISPONIVEL")
        info, openapi = consultar(args.backend, "/openapi.json")
        dados["backend_openapi"] = info
        contrato_ok = info.get("status") == 200 and contrato_login(openapi)
        dados["backend_contrato_login_json_ok"] = contrato_ok
        print("BACKEND_CONTRATO_LOGIN_JSON_OK=" + str(contrato_ok))
        for nome, base in (("backend", args.backend), ("frontend", args.frontend)):
            info, _ = consultar(base, "/api/v1/autenticacao/sessao")
            dados[nome + "_sessao_sem_cookie"] = info
            print(nome.upper() + "_SESSAO_SEM_COOKIE_HTTP=" + str(info.get("status")))
            if contrato_ok:
                # Falta email e senha, ambos obrigatórios: validação rejeita o
                # corpo antes de consultar contas ou registrar tentativa de login.
                info, _ = consultar(base, "/api/v1/autenticacao/entrar", "POST")
                dados[nome + "_validacao_json_vazio"] = info
                print(nome.upper() + "_JSON_VAZIO_HTTP=" + str(info.get("status")))
        info, _ = consultar(args.frontend, "/login")
        dados["frontend_pagina_login"] = info
        print("FRONTEND_PAGINA_LOGIN_HTTP=" + str(info.get("status")))
        dados["orientacao"] = ("Reinicie o backend na raiz MEC-Servicos com python -m uvicorn backend.app.principal:app --reload e atualize a tela com Ctrl+F5."
            if not contrato_ok else "Confira o bloco PERFIL=admin do arquivo novo indicado pelo FIX2. Se o erro persistir, informe este diagnóstico e a mensagem exibida na tela.")
    except Exception:
        dados["erro"] = "Não foi possível concluir o diagnóstico. Nenhuma senha foi registrada."
    arquivo = raiz / (STEM + ".json")
    texto = raiz / (STEM + ".txt")
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    texto.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SENHAS_TRANSMITIDAS=False")
    print("CONTAS_ALTERADAS=False")
    print("JSON=" + str(arquivo))
    print("RELATORIO=" + str(texto))
    print("RESULTADO=DIAGNOSTICO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
