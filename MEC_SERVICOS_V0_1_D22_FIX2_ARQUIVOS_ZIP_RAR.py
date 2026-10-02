r"""MEC-Serviços D22 FIX2 — envio de arquivos ZIP e RAR.

Execute na raiz do projeto, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D22_FIX2_ARQUIVOS_ZIP_RAR.py

Atualiza a lista de extensões do serviço e o seletor/textos da tela D22.
Mantém os formatos anteriores, o limite de 100 MB e o upload multipart.
Os pacotes compactados são armazenados e baixados como um único anexo.
Cria backup, valida as extensões, executa pytest e npm run build.
Se uma etapa falhar, restaura os fontes alterados e o dist anterior.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


REVISION = "MEC-SERVICOS-V0.1-D22-FIX2-ARQUIVOS-ZIP-RAR-2026-10-02"
SERVICO_REL = Path("backend/app/services/arquivo_tecnico.py")
PAGINA_REL = Path("frontend/src/pages/client/ClientArquivosTecnicosPage.tsx")
API_REL = Path("frontend/src/services/api.ts")
ROTAS_REL = Path("backend/app/api/rotas/arquivos_tecnicos.py")
PACOTE_REL = Path("frontend/package.json")
DIST_REL = Path("frontend/dist")
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D22_FIX2_ARQUIVOS_ZIP_RAR_RELATORIO"
EXTENSOES_ANTERIORES = (".step", ".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf")
EXTENSOES_NOVAS = (".zip", ".rar")
LIMITE_BYTES = 100 * 1024 * 1024

VAZIO_ANTES = "Formatos aceitos: STEP, STP, IGES, IGS, DXF, DWG e PDF."
VAZIO_DEPOIS = "Formatos aceitos: STEP, STP, IGES, IGS, DXF, DWG, PDF, ZIP e RAR."
RODAPE_ANTES = (
    "O backend aceita arquivos STEP, STP, IGES, IGS, DXF, DWG e PDF, "
    "com limite de 100 MB por arquivo."
)
RODAPE_DEPOIS = (
    "Formatos aceitos: STEP, STP, IGES, IGS, DXF, DWG, PDF, ZIP e RAR. "
    "Limite de 100 MB por arquivo."
)
PADRAO_ACCEPT = re.compile(
    r'''\bconst\s+ACCEPT\s*=\s*(["'])([^"'\r\n]+)\1\s*;'''
)

VALIDACAO_EXTENSOES = r'''
from fastapi import HTTPException
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico

servico = object.__new__(ServicoArquivoTecnico)
for extensao in (".step", ".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf", ".zip", ".rar"):
    for sufixo in (extensao, extensao.upper()):
        nome = "peca" + sufixo
        resultado = servico._validar_extensao(nome)
        if resultado != (nome, extensao):
            raise RuntimeError("Extensão recusada ou alterada: " + nome)
for nome in ("programa.exe", "pacote.zip.exe", "pacote.rar.bat"):
    try:
        servico._validar_extensao(nome)
    except HTTPException as erro:
        if erro.status_code != 415 or erro.detail != "extensao_arquivo_nao_permitida":
            raise RuntimeError("Resposta inesperada para extensão bloqueada.") from erro
    else:
        raise RuntimeError("Uma extensão bloqueada foi aceita: " + nome)
if ServicoArquivoTecnico.MAX_FILE_SIZE_BYTES != 100 * 1024 * 1024:
    raise RuntimeError("O limite de tamanho mudou.")
print("ZIP_RAR_MAIUSCULAS_MINUSCULAS_OK=True")
print("FORMATOS_ANTERIORES_OK=True")
print("BLOQUEIO_EXTENSAO_INDEVIDA_OK=True")
print("LIMITE_100_MB_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    atual = Path.cwd().resolve()
    for raiz in (atual, *atual.parents):
        if (raiz / SERVICO_REL).is_file() and (raiz / PAGINA_REL).is_file():
            return raiz
    raise RuntimeError("Execute este script na raiz da pasta MEC-Servicos.")


def localizar_lista_extensoes(texto: str) -> tuple[ast.AST, list[str]]:
    arvore = ast.parse(texto)
    classes = [
        nodo for nodo in arvore.body
        if isinstance(nodo, ast.ClassDef) and nodo.name == "ServicoArquivoTecnico"
    ]
    if len(classes) != 1:
        raise RuntimeError("ServicoArquivoTecnico não corresponde ao contrato D22.")
    valores = []
    for nodo in classes[0].body:
        if isinstance(nodo, ast.Assign) and any(
            isinstance(alvo, ast.Name) and alvo.id == "ALLOWED_EXTENSIONS"
            for alvo in nodo.targets
        ):
            valores.append(nodo.value)
    if len(valores) != 1:
        raise RuntimeError("Não foi possível identificar ALLOWED_EXTENSIONS com segurança.")
    chamada = valores[0]
    if not (
        isinstance(chamada, ast.Call)
        and isinstance(chamada.func, ast.Name)
        and chamada.func.id == "frozenset"
        and len(chamada.args) == 1
        and not chamada.keywords
        and isinstance(chamada.args[0], (ast.Set, ast.List, ast.Tuple))
    ):
        raise RuntimeError("A lista de extensões difere do formato conferido no D22.")
    literal = chamada.args[0]
    if not all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in literal.elts):
        raise RuntimeError("A lista de extensões contém valores inesperados.")
    extensoes = [item.value for item in literal.elts]
    if not set(EXTENSOES_ANTERIORES).issubset(extensoes):
        raise RuntimeError("A lista atual não contém todos os formatos anteriores do D22.")
    return literal, extensoes


def deslocamento(texto: str, linha: int, coluna_bytes: int) -> int:
    linhas = texto.splitlines(keepends=True)
    prefixo = linhas[linha - 1].encode("utf-8")[:coluna_bytes].decode("utf-8")
    return sum(len(item) for item in linhas[:linha - 1]) + len(prefixo)


def atualizar_servico(texto: str) -> str:
    literal, extensoes = localizar_lista_extensoes(texto)
    if set(EXTENSOES_NOVAS).issubset(extensoes):
        return texto
    novas = extensoes + [item for item in EXTENSOES_NOVAS if item not in extensoes]
    inicio = deslocamento(texto, literal.lineno, literal.col_offset)
    fim = deslocamento(texto, literal.end_lineno, literal.end_col_offset)
    lista = "{" + ", ".join(json.dumps(item) for item in novas) + "}"
    atualizado = texto[:inicio] + lista + texto[fim:]
    ast.parse(atualizado)
    _, conferidas = localizar_lista_extensoes(atualizado)
    if set(conferidas) != set(extensoes) | set(EXTENSOES_NOVAS):
        raise RuntimeError("A validação da nova lista de extensões falhou.")
    return atualizado


def atualizar_pagina(texto: str) -> str:
    ocorrencias = list(PADRAO_ACCEPT.finditer(texto))
    if len(ocorrencias) != 1:
        raise RuntimeError("Não foi possível identificar o seletor ACCEPT da tela D22.")
    ocorrencia = ocorrencias[0]
    extensoes = [item.strip() for item in ocorrencia.group(2).split(",")]
    if not set(EXTENSOES_ANTERIORES).issubset(extensoes):
        raise RuntimeError("O seletor da tela não contém os formatos anteriores do D22.")
    novas = extensoes + [item for item in EXTENSOES_NOVAS if item not in extensoes]
    atualizado = texto[:ocorrencia.start(2)] + ",".join(novas) + texto[ocorrencia.end(2):]
    for antes, depois in ((VAZIO_ANTES, VAZIO_DEPOIS), (RODAPE_ANTES, RODAPE_DEPOIS)):
        if antes in atualizado:
            atualizado = atualizado.replace(antes, depois)
        elif depois not in atualizado:
            raise RuntimeError("Os textos da tela diferem do D22 conferido. Nenhum arquivo foi alterado.")
    return atualizado


def codificar(texto: str, original: bytes) -> bytes:
    marcador = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
    return marcador + texto.encode("utf-8")


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d22_fix2_", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def validar_contrato(raiz: Path, servico: str, pagina: str) -> dict[str, bool]:
    api = ler_texto(raiz / API_REL)
    rotas = ler_texto(raiz / ROTAS_REL)
    ast.parse(rotas)
    pacote = json.loads(ler_texto(raiz / PACOTE_REL))
    verificacoes = {
        "limite_backend_100_mb": bool(re.search(r"MAX_FILE_SIZE_BYTES\s*=\s*100\s*\*\s*1024\s*\*\s*1024", servico)),
        "limite_tela_100_mb": bool(re.search(r"MAX_FILE_SIZE_BYTES\s*=\s*100\s*\*\s*1024\s*\*\s*1024", pagina)),
        "upload_formdata": bool(re.search(r"new\s+FormData\s*\(\s*\)", pagina)),
        "campo_file_tela": bool(re.search(r'''dados\.append\(\s*["']file["']\s*,\s*arquivo\s*\)''', pagina)),
        "campo_file_backend": bool(re.search(r"file\s*:\s*UploadFile\s*=\s*File\(\s*\.\.\.\s*\)", rotas)),
        "endpoint_upload": "/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos" in rotas,
        "multipart_fix1_preservado": not bool(re.search(r'''["']Content-Type["']\s*:\s*["']application/json''', api, re.IGNORECASE)),
        "build_disponivel": bool(pacote.get("scripts", {}).get("build")),
    }
    falhas = [nome for nome, ok in verificacoes.items() if not ok]
    if falhas:
        raise RuntimeError("O contrato atual não confere: " + ", ".join(falhas))
    return verificacoes


def executar_etapa(raiz: Path, nome: str, comando: list[str], pasta: Path, relatorio: dict) -> None:
    print(f"Executando {nome}...", flush=True)
    processo = subprocess.run(
        comando, cwd=pasta, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=600,
    )
    saida = (processo.stdout or "") + (processo.stderr or "")
    relatorio["etapas"].append({"nome": nome, "returncode": processo.returncode, "saida": saida})
    if saida:
        print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
    print(f"{nome.upper().replace(' ', '_')}_RETURN_CODE={processo.returncode}", flush=True)
    if processo.returncode:
        raise RuntimeError(f"A etapa {nome} falhou; confira a saída acima e o relatório.")


def salvar_relatorios(raiz: Path, relatorio: dict) -> None:
    caminho_json = raiz / (RELATORIO_NOME + ".json")
    caminho_txt = raiz / (RELATORIO_NOME + ".txt")
    caminho_json.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    linhas = ["MEC-Serviços D22 FIX2 — Arquivos ZIP e RAR"]
    for nome in ("revision", "raiz", "backup", "arquivos_alterados", "restaurado", "erro", "resultado"):
        if nome in relatorio:
            linhas.append(f"{nome.upper()}={relatorio[nome]}")
    linhas.append("VALIDACAO_NO_NAVEGADOR=PENDENTE")
    for etapa in relatorio["etapas"]:
        linhas.extend(["", f"ETAPA={etapa['nome']}; RETURN_CODE={etapa['returncode']}", etapa["saida"]])
    caminho_txt.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"RELATORIO={caminho_txt}", flush=True)
    print(f"JSON={caminho_json}", flush=True)


def main() -> int:
    print("MEC-Serviços D22 FIX2 — Arquivos ZIP e RAR", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    raiz: Path | None = None
    backup: Path | None = None
    originais: dict[Path, bytes] = {}
    gravados: list[Path] = []
    build_iniciado = False
    dist_anterior = False
    relatorio = {
        "revision": REVISION, "resultado": "ERRO", "restaurado": False,
        "arquivos_alterados": [], "etapas": [], "validacao_no_navegador": "PENDENTE",
    }
    try:
        raiz = localizar_raiz()
        relatorio["raiz"] = str(raiz)
        print(f"ROOT={raiz}", flush=True)
        originais = {rel: (raiz / rel).read_bytes() for rel in (SERVICO_REL, PAGINA_REL)}
        servico = originais[SERVICO_REL].decode("utf-8-sig")
        pagina = originais[PAGINA_REL].decode("utf-8-sig")
        relatorio["contrato"] = validar_contrato(raiz, servico, pagina)
        novos = {
            SERVICO_REL: codificar(atualizar_servico(servico), originais[SERVICO_REL]),
            PAGINA_REL: codificar(atualizar_pagina(pagina), originais[PAGINA_REL]),
        }
        print("CONTRATO_D22_OK=True", flush=True)
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm não encontrado no PATH. Abra o PowerShell com Node.js disponível.")
        if importlib.util.find_spec("pytest") is None:
            raise RuntimeError("pytest não encontrado. Execute com a .venv do projeto ativa.")
        preservados = {rel: (raiz / rel).read_bytes() for rel in (API_REL, ROTAS_REL)}
        backup = raiz / "_mec_backups" / ("D22_FIX2_ARQUIVOS_ZIP_RAR_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        for rel in originais:
            destino = backup / rel
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raiz / rel, destino)
        dist = raiz / DIST_REL
        if dist.is_symlink() or (dist.exists() and not dist.is_dir()):
            raise RuntimeError("frontend/dist tem um formato inesperado. Nenhum fonte foi alterado.")
        dist_anterior = dist.is_dir()
        if dist_anterior:
            shutil.copytree(dist, backup / DIST_REL)
        relatorio["backup"] = str(backup)
        print(f"BACKUP_DIR={backup}", flush=True)
        for rel, conteudo in novos.items():
            if (raiz / rel).read_bytes() != originais[rel]:
                raise RuntimeError(f"O arquivo {rel} foi modificado durante a execução.")
            if conteudo != originais[rel]:
                gravados.append(rel)
                gravar_atomico(raiz / rel, conteudo)
                relatorio["arquivos_alterados"].append(str(rel))
        if not gravados:
            print("ATUALIZACAO_JA_APLICADA=True", flush=True)
        for rel, conteudo in novos.items():
            if (raiz / rel).read_bytes() != conteudo:
                raise RuntimeError(f"A gravação de {rel} não confere.")
        print("ZIP_RAR_BACKEND_E_TELA_OK=True", flush=True)
        executar_etapa(raiz, "validacao extensoes", [sys.executable, "-c", VALIDACAO_EXTENSOES], raiz, relatorio)
        executar_etapa(raiz, "pytest", [sys.executable, "-m", "pytest", "-q"], raiz, relatorio)
        build_iniciado = True
        executar_etapa(raiz, "npm build", [npm, "run", "build"], raiz / "frontend", relatorio)
        if any((raiz / rel).read_bytes() != conteudo for rel, conteudo in preservados.items()):
            raise RuntimeError("api.ts ou as rotas foram alterados durante a validação.")
        if any((raiz / rel).read_bytes() != conteudo for rel, conteudo in novos.items()):
            raise RuntimeError("Os fontes foram alterados durante a validação.")
        relatorio["resultado"] = "OK"
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["erro"] = str(erro) or "Execução interrompida pelo usuário."
        print(f"ERRO={relatorio['erro']}", flush=True)
        falhas_restauracao = []
        if raiz is not None:
            for rel in reversed(gravados):
                try:
                    gravar_atomico(raiz / rel, originais[rel])
                except Exception as falha:
                    falhas_restauracao.append(f"{rel}: {falha}")
            if build_iniciado and backup is not None:
                try:
                    dist = raiz / DIST_REL
                    if dist.is_dir():
                        shutil.rmtree(dist)
                    elif dist.exists() or dist.is_symlink():
                        dist.unlink()
                    if dist_anterior:
                        shutil.copytree(backup / DIST_REL, dist)
                except Exception as falha:
                    falhas_restauracao.append(f"{DIST_REL}: {falha}")
        if gravados or build_iniciado:
            relatorio["restaurado"] = not falhas_restauracao
            print(f"RESTAURADO={relatorio['restaurado']}", flush=True)
        if falhas_restauracao:
            relatorio["falhas_restauracao"] = falhas_restauracao
            print("FALHAS_RESTAURACAO=" + "; ".join(falhas_restauracao), flush=True)
    if raiz is not None:
        try:
            salvar_relatorios(raiz, relatorio)
        except Exception as erro:
            print(f"ERRO_AO_SALVAR_RELATORIO={erro}", flush=True)
            relatorio["resultado"] = "ERRO"
    print(f"RESULTADO={relatorio['resultado']}", flush=True)
    if relatorio["resultado"] == "OK":
        print("Reinicie o backend e atualize /cliente/arquivos-tecnicos com Ctrl+F5.", flush=True)
        print("Teste enviar, baixar e desvincular um ZIP e um RAR.", flush=True)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
