r"""D22 FIX1: corrige o envio de arquivos técnicos pelo cliente Axios.

Execute na raiz do MEC-Servicos, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D22_FIX1_UPLOAD_MULTIPART.py

A API define automaticamente o Content-Type para objetos JSON e FormData.
O script valida o contrato já instalado, salva backup de api.ts, executa
npm run build e restaura api.ts se a validação ou o build falhar.
O envio, o download e a desvinculação precisam ser conferidos no navegador.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


REVISION = "MEC-SERVICOS-V0.1-D22-FIX1-UPLOAD-MULTIPART-2026-10-02"
API_REL = Path("frontend/src/services/api.ts")
PAGE_REL = Path("frontend/src/pages/client/ClientArquivosTecnicosPage.tsx")
BACKEND_REL = Path("backend/app/api/rotas/arquivos_tecnicos.py")
PACKAGE_REL = Path("frontend/package.json")
REPORT_STEM = "MEC_SERVICOS_V0_1_D22_FIX1_UPLOAD_MULTIPART_RELATORIO"

API_ANTES = '''import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});
'''

API_DEPOIS = '''import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
});
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8-sig")


def tokens_api(texto: str) -> str:
    # Só aceitamos a configuração mostrada pelo usuário ou a já corrigida.
    # Essa comparação não é usada para alterar outros módulos TypeScript.
    return re.sub(r"\s+", "", texto).replace("'", '"')


def localizar_raiz() -> Path:
    atual = Path.cwd().resolve()
    for raiz in (atual, *atual.parents):
        if (raiz / API_REL).is_file() and (raiz / "backend/app/principal.py").is_file():
            return raiz
    raise RuntimeError("Execute este script dentro da pasta MEC-Servicos.")


def validar_contrato(raiz: Path) -> dict[str, bool]:
    pagina = ler_texto(raiz / PAGE_REL)
    backend = ler_texto(raiz / BACKEND_REL)
    ast.parse(backend)
    pacote = json.loads(ler_texto(raiz / PACKAGE_REL))
    verificacoes = {
        "formdata_na_pagina": bool(re.search(r"new\s+FormData\s*\(\s*\)", pagina)),
        "campo_file_na_pagina": bool(
            re.search(r'''dados\.append\(\s*["']file["']\s*,\s*arquivo\s*\)''', pagina)
        ),
        "post_formdata_no_endpoint": bool(re.search(
            r"api\.post\(\s*`/solicitacoes-servico/\$\{solicitacaoId\}/arquivos-tecnicos`\s*,\s*dados\s*,?\s*\)",
            pagina,
        )),
        "endpoint_upload_backend": (
            "/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos" in backend
            and "@roteador.post" in backend
        ),
        "campo_file_no_backend": bool(re.search(
            r"file\s*:\s*UploadFile\s*=\s*File\(\s*\.\.\.\s*\)", backend
        )),
        "script_build_disponivel": bool(pacote.get("scripts", {}).get("build")),
    }
    faltantes = [nome for nome, ok in verificacoes.items() if not ok]
    if faltantes:
        raise RuntimeError("O contrato D22 não confere: " + ", ".join(faltantes))
    return verificacoes


def salvar_relatorios(raiz: Path, relatorio: dict[str, object]) -> None:
    json_path = raiz / (REPORT_STEM + ".json")
    txt_path = raiz / (REPORT_STEM + ".txt")
    json_path.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    linhas = ["MEC-Serviços D22 FIX1 — Upload multipart"]
    for chave in ("revision", "raiz", "backup", "api_alterada", "npm_build_returncode",
                  "fontes_lidas_preservadas", "restaurado", "erro", "resultado"):
        if chave in relatorio:
            linhas.append(f"{chave.upper()}={relatorio[chave]}")
    linhas.append("VALIDACAO_NO_NAVEGADOR=PENDENTE")
    linhas.extend(["", "SAÍDA DO BUILD:", str(relatorio.get("build_saida", ""))])
    txt_path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"RELATORIO={txt_path}")
    print(f"JSON={json_path}")


def main() -> int:
    print("MEC-Serviços D22 FIX1 — Upload multipart", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    raiz: Path | None = None
    alvo: Path | None = None
    original: bytes | None = None
    alteracao_iniciada = False
    relatorio: dict[str, object] = {
        "revision": REVISION, "resultado": "ERRO", "restaurado": False,
        "api_alterada": False, "validacao_no_navegador": "PENDENTE",
    }

    try:
        raiz = localizar_raiz()
        relatorio["raiz"] = str(raiz)
        print(f"ROOT={raiz}", flush=True)
        alvo = raiz / API_REL
        original = alvo.read_bytes()
        texto = original.decode("utf-8-sig")
        reconhecido = tokens_api(texto)
        if reconhecido not in {tokens_api(API_ANTES), tokens_api(API_DEPOIS)}:
            raise RuntimeError(
                "api.ts difere da configuração conferida. Nenhuma alteração foi aplicada. "
                "Envie o conteúdo atual de frontend/src/services/api.ts."
            )

        relatorio["contrato"] = validar_contrato(raiz)
        print("CONTRATO_D22_OK=True", flush=True)
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm não encontrado no PATH. Abra o PowerShell com Node.js disponível.")

        fontes = (PAGE_REL, BACKEND_REL, PACKAGE_REL)
        hashes = {str(rel): hashlib.sha256((raiz / rel).read_bytes()).hexdigest() for rel in fontes}
        backup_dir = raiz / "_mec_backups" / (
            "D22_FIX1_UPLOAD_MULTIPART_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        )
        backup_api = backup_dir / API_REL
        backup_api.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(alvo, backup_api)
        relatorio["backup"] = str(backup_dir)
        print(f"BACKUP_DIR={backup_dir}", flush=True)

        if reconhecido == tokens_api(API_ANTES):
            alteracao_iniciada = True
            alvo.write_text(API_DEPOIS, encoding="utf-8", newline="\n")
            relatorio["api_alterada"] = True
        else:
            print("CORRECAO_JA_APLICADA=True", flush=True)
        if tokens_api(ler_texto(alvo)) != tokens_api(API_DEPOIS):
            raise RuntimeError("A validação de api.ts após a gravação falhou.")
        print("API_SEM_JSON_FORCADO=True", flush=True)
        print("Executando npm run build...", flush=True)
        processo = subprocess.run(
            [npm, "run", "build"], cwd=raiz / "frontend",
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        saida = (processo.stdout or "") + (processo.stderr or "")
        relatorio["npm_build_returncode"] = processo.returncode
        relatorio["build_saida"] = saida[-20000:]
        if saida:
            print(saida[-12000:], flush=True)
        print(f"NPM_BUILD_RETURN_CODE={processo.returncode}", flush=True)
        if processo.returncode != 0:
            raise RuntimeError("npm run build falhou. A configuração anterior será restaurada.")

        preservadas = all(
            hashlib.sha256((raiz / rel).read_bytes()).hexdigest() == hashes[str(rel)]
            for rel in fontes
        )
        relatorio["fontes_lidas_preservadas"] = preservadas
        if not preservadas:
            raise RuntimeError("Uma das fontes conferidas mudou durante o build; consulte o relatório.")
        relatorio["resultado"] = "OK"
        salvar_relatorios(raiz, relatorio)
        print("RESULTADO=OK", flush=True)
        print("Atualize /cliente/arquivos-tecnicos e teste enviar, baixar e desvincular um arquivo.")
        return 0

    except (Exception, KeyboardInterrupt) as erro:
        relatorio["resultado"] = "ERRO"
        relatorio["erro"] = f"{type(erro).__name__}: {erro}"
        print(f"ERRO={relatorio['erro']}", flush=True)
        if alteracao_iniciada and alvo is not None and original is not None:
            try:
                alvo.write_bytes(original)
                relatorio["restaurado"] = alvo.read_bytes() == original
                print(f"API_RESTAURADA={relatorio['restaurado']}", flush=True)
            except Exception as falha:
                relatorio["erro_restauracao"] = str(falha)
                print(f"ERRO_RESTAURACAO={falha}", flush=True)
                print(f"O backup está em: {relatorio.get('backup', '')}", flush=True)
        if raiz is not None:
            try:
                salvar_relatorios(raiz, relatorio)
            except Exception as falha:
                print(f"ERRO_RELATORIO={falha}", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
