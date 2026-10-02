r"""Corrige quatro terminações de texto e retoma o checkpoint D22.

Execute na raiz do MEC-Servicos:
    python .\MEC_SERVICOS_V0_1_D22_SALVAR_GIT_FIX1.py

Mantenha MEC_SERVICOS_V0_1_D22_SALVAR_GIT.py na mesma pasta.
Salva backup dos textos alterados, remove as linhas vazias extras no final,
prepara novamente esses arquivos e confere git diff --cached --check.
Depois retoma o salvamento anterior, que cria o commit, a tag v0.1.0-d22
e envia ambos ao GitHub. Preserva os arquivos locais de outros projetos.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


REVISION = "MEC-SERVICOS-V0.1-D22-CHECKPOINT-GIT-FIX1-FINAIS-TEXTO-2026-10-02"
SCRIPT_ANTERIOR = "MEC_SERVICOS_V0_1_D22_SALVAR_GIT.py"
REVISION_ANTERIOR = "MEC-SERVICOS-V0.1-D22-CHECKPOINT-GIT-2026-10-02"
TEXTOS = (
    "D22_CONTRATO_ARQUIVOS_TECNICOS.txt",
    "MEC_SERVICOS_V0_1_D22_FIX1_UPLOAD_MULTIPART_RELATORIO.txt",
    "MEC_SERVICOS_V0_1_D22_FIX2_ARQUIVOS_ZIP_RAR_RELATORIO.txt",
    "MEC_SERVICOS_V0_1_D22_FIX3_ZIP_RAR_TESTES_MEC_RELATORIO.txt",
)


def carregar_salvamento(raiz: Path):
    caminho = raiz / SCRIPT_ANTERIOR
    if not caminho.is_file():
        raise RuntimeError(f"Mantenha {SCRIPT_ANTERIOR} na raiz e execute novamente.")
    especificacao = importlib.util.spec_from_file_location("mec_d22_salvamento_anterior", caminho)
    if especificacao is None or especificacao.loader is None:
        raise RuntimeError("Não foi possível carregar o script de salvamento anterior.")
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    if getattr(modulo, "REVISION", None) != REVISION_ANTERIOR:
        raise RuntimeError("O script anterior difere da revisão conferida para esta correção.")
    return modulo


def ajustar_final(conteudo: bytes) -> bytes:
    linhas = conteudo.splitlines(keepends=True)
    while linhas and not linhas[-1].rstrip(b"\r\n").strip(b" \t"):
        linhas.pop()
    if not linhas:
        raise RuntimeError("Um dos textos está vazio; confira os arquivos antes de continuar.")
    corrigido = b"".join(linhas)
    if not corrigido.endswith((b"\r\n", b"\n", b"\r")):
        corrigido += b"\r\n" if b"\r\n" in conteudo else b"\n"
    return corrigido


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=caminho.parent, prefix="mec_d22_git_fix1_", delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def main() -> int:
    print("MEC-Serviços D22 — Salvamento Git FIX1", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    try:
        raiz = Path.cwd().resolve()
        salvamento = carregar_salvamento(raiz)
        if salvamento.localizar_raiz() != raiz:
            raise RuntimeError("Execute este script na raiz de MEC-Servicos.")
        if salvamento.git(raiz, "branch", "--show-current").stdout.strip() != "main":
            raise RuntimeError("A branch atual precisa ser main.")
        salvamento.validar_origem(raiz)
        salvamento.validar_evidencia(raiz)
        salvamento.conferir_index(raiz)

        originais = {}
        corrigidos = {}
        for nome in TEXTOS:
            caminho = raiz / nome
            if not caminho.is_file() or caminho.is_symlink():
                raise RuntimeError(f"O arquivo de texto esperado não foi encontrado: {nome}")
            originais[nome] = caminho.read_bytes()
            corrigidos[nome] = ajustar_final(originais[nome])
        alterados = [nome for nome in TEXTOS if corrigidos[nome] != originais[nome]]
        if alterados:
            backup = raiz / "_mec_backups" / (
                "D22_GIT_FIX1_FINAIS_TEXTO_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            )
            backup.mkdir(parents=True, exist_ok=False)
            for nome in alterados:
                shutil.copy2(raiz / nome, backup / nome)
            print(f"BACKUP_DIR={backup}", flush=True)
            for nome in alterados:
                if (raiz / nome).read_bytes() != originais[nome]:
                    raise RuntimeError(f"O texto {nome} foi alterado durante a execução.")
                gravar_atomico(raiz / nome, corrigidos[nome])
                print(f"FINAL_TEXTO_CORRIGIDO={nome}", flush=True)
        else:
            print("FINAIS_TEXTO_JA_CORRIGIDOS=True", flush=True)

        salvamento.git(raiz, "add", "--", *TEXTOS, mostrar=True)
        salvamento.git(raiz, "diff", "--cached", "--check", mostrar=True)
        print("GIT_DIFF_CACHED_CHECK_OK=True", flush=True)
        print("Retomando o salvamento do checkpoint D22...", flush=True)
        return salvamento.main()
    except (Exception, KeyboardInterrupt) as erro:
        print("ERRO=" + (str(erro) or "Execução interrompida pelo usuário."), flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
