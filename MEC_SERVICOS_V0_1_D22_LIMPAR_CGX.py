r"""Retira os itens CGX conhecidos da pasta do MEC-Serviços.

Na raiz C:\Users\Omega\Desktop\MEC-Servicos, execute:
    python .\MEC_SERVICOS_V0_1_D22_LIMPAR_CGX.py

Move os itens para uma pasta de backup ao lado do projeto, preservando
seu conteúdo e estrutura. Não precisa de pacotes da .venv nem de internet.
Interrompe antes da limpeza se algum alvo estiver versionado ou preparado
no Git. Se uma operação falhar, tenta devolver os itens já movidos.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


REVISION = "MEC-SERVICOS-V0.1-D22-LIMPAR-CGX-2026-10-02"
ALVOS = (
    "CGX_diagnostico_MOLD_COOLING_BUBBLERS_v0_8_9.py",
    "README_MOLD_CORE_v0_8_9.md",
    "src/cgx",
    "tests/mold",
)
MARCADORES_MEC = (
    "backend/app/principal.py",
    "backend/app/services/arquivo_tecnico.py",
    "frontend/package.json",
    "frontend/src/pages/client/ClientArquivosTecnicosPage.tsx",
)


def git(raiz: Path, *argumentos: str) -> str:
    executavel = shutil.which("git")
    if not executavel:
        raise RuntimeError("Git não encontrado no PATH.")
    processo = subprocess.run(
        [executavel, "-c", "core.quotepath=false", *argumentos],
        cwd=raiz, capture_output=True, encoding="utf-8", errors="replace",
        check=False, timeout=30,
    )
    if processo.returncode:
        detalhe = (processo.stderr or processo.stdout).strip()
        raise RuntimeError("Falha em git " + " ".join(argumentos) + ": " + detalhe)
    return processo.stdout


def validar_projeto() -> Path:
    raiz = Path.cwd().resolve()
    if not all((raiz / nome).is_file() for nome in MARCADORES_MEC):
        raise RuntimeError("Execute este script na raiz do projeto MEC-Servicos.")
    raiz_git = Path(git(raiz, "rev-parse", "--show-toplevel").strip()).resolve()
    if raiz_git != raiz:
        raise RuntimeError("A pasta atual não é a raiz do repositório MEC-Servicos.")
    origem = git(raiz, "remote", "get-url", "origin").strip()
    if origem.lower().startswith("git@github.com:"):
        caminho = origem.split(":", 1)[1]
    else:
        partes = urlsplit(origem)
        if partes.hostname != "github.com" or partes.scheme not in {"https", "ssh"}:
            raise RuntimeError("O origin não corresponde ao GitHub do MEC-Servicos.")
        caminho = partes.path.lstrip("/")
    if caminho.rstrip("/").lower().removesuffix(".git") != "projetoxcadcam-byte/mec-servicos":
        raise RuntimeError("O origin não corresponde ao repositório MEC-Servicos esperado.")
    return raiz


def existe(caminho: Path) -> bool:
    # Inclui links quebrados, para que sejam detectados antes de qualquer ação.
    return os.path.lexists(caminho)


def verificar_caminho(raiz: Path, nome: str) -> None:
    caminho = raiz
    for parte in Path(nome).parts:
        caminho = caminho / parte
        if not existe(caminho):
            continue
        dados = caminho.lstat()
        atributos = getattr(dados, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(dados.st_mode) or atributos & reparse:
            raise RuntimeError(f"O caminho {nome} passa por um link ou junction; limpeza interrompida.")
    alvo = raiz / nome
    if existe(alvo):
        pasta_esperada = nome in {"src/cgx", "tests/mold"}
        if (pasta_esperada and not alvo.is_dir()) or (not pasta_esperada and not alvo.is_file()):
            raise RuntimeError(f"Tipo de arquivo inesperado em {nome}; limpeza interrompida.")


def verificar_alvos_no_git(raiz: Path) -> None:
    # Confere também HEAD: um arquivo preparado para exclusão continua protegido.
    preparados = git(raiz, "ls-files", "--cached", "-z", "--", *ALVOS)
    versionados = git(raiz, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", *ALVOS)
    encontrados = sorted(set(filter(None, (preparados + versionados).split("\0"))))
    if encontrados:
        raise RuntimeError(
            "Há itens CGX versionados ou preparados no Git. Nada foi movido: "
            + ", ".join(encontrados)
        )


def escrever_relatorio(backup: Path, dados: dict) -> None:
    destino = backup / "RELATORIO_LIMPEZA_CGX.json"
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporario, destino)


def main() -> int:
    print("MEC-Serviços D22 — Retirar arquivos CGX do projeto", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    raiz: Path | None = None
    backup: Path | None = None
    movidos: list[str] = []
    src_removida = False
    relatorio: dict = {}
    try:
        raiz = validar_projeto()
        print(f"ROOT={raiz}", flush=True)
        print("ORIGIN_MEC_CONFIRMADO=True", flush=True)
        for nome in ALVOS:
            verificar_caminho(raiz, nome)
        verificar_alvos_no_git(raiz)
        print("ALVOS_FORA_DO_GIT=True", flush=True)
        presentes = [nome for nome in ALVOS if existe(raiz / nome)]
        for nome in ALVOS:
            print(f"{'ENCONTRADO' if nome in presentes else 'AUSENTE'}={nome}", flush=True)
        if not presentes:
            print("Nenhum dos itens CGX conhecidos permanece na pasta do projeto.", flush=True)
            print("RESULTADO=OK", flush=True)
            return 0

        instante = datetime.now()
        backup = raiz.parent / (
            raiz.name + "_CGX_REMOVIDOS_" + instante.strftime("%Y%m%d_%H%M%S_%f")
        )
        backup.mkdir(exist_ok=False)
        print(f"BACKUP_FORA_DO_PROJETO={backup}", flush=True)
        relatorio = {
            "revision": REVISION,
            "resultado": "EM_ANDAMENTO",
            "data_local": instante.isoformat(),
            "raiz_original": str(raiz),
            "backup": str(backup),
            "alvos_encontrados": presentes,
            "itens_movidos": [],
            "pasta_src_vazia_removida": False,
        }
        escrever_relatorio(backup, relatorio)
        for nome in presentes:
            origem = raiz / nome
            destino = backup / nome
            destino.parent.mkdir(parents=True, exist_ok=True)
            if existe(destino):
                raise RuntimeError(f"Já existe um destino de backup para {nome}.")
            # Renomear para a pasta ao lado mantém os dados no mesmo volume.
            origem.rename(destino)
            movidos.append(nome)
            print(f"RETIRADO_DO_PROJETO={nome}", flush=True)

        src = raiz / "src"
        if "src/cgx" in movidos and src.is_dir() and not any(src.iterdir()):
            src.rmdir()
            src_removida = True
            print("PASTA_SRC_VAZIA_REMOVIDA=True", flush=True)
        elif src.is_dir():
            print("PASTA_SRC_COM_OUTROS_ITENS_PRESERVADA=True", flush=True)

        if any(existe(raiz / nome) for nome in presentes):
            raise RuntimeError("Um dos itens reapareceu no projeto durante a limpeza.")
        relatorio.update({
            "resultado": "OK",
            "itens_movidos": movidos.copy(),
            "pasta_src_vazia_removida": src_removida,
        })
        escrever_relatorio(backup, relatorio)
        print(f"ITENS_RETIRADOS={len(movidos)}", flush=True)
        print(f"RELATORIO={backup / 'RELATORIO_LIMPEZA_CGX.json'}", flush=True)
        print("Conteúdo preservado no backup fora do projeto.", flush=True)
        print("RESULTADO=OK", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        print(f"ERRO={erro or 'Operação interrompida.'}", flush=True)
        falhas: list[str] = []
        if raiz is not None and backup is not None:
            for nome in reversed(movidos):
                try:
                    origem = raiz / nome
                    destino = backup / nome
                    if existe(origem):
                        raise RuntimeError("O caminho original foi recriado; nenhuma cópia foi sobrescrita.")
                    origem.parent.mkdir(parents=True, exist_ok=True)
                    destino.rename(origem)
                except Exception as falha:
                    falhas.append(f"{nome}: {falha}")
            if movidos:
                print(f"RESTAURADO={'True' if not falhas else 'False'}", flush=True)
            relatorio.update({
                "resultado": "ERRO",
                "erro": str(erro),
                "itens_movidos_antes_da_falha": movidos.copy(),
                "restaurado": not falhas,
                "falhas_restauracao": falhas,
            })
            try:
                escrever_relatorio(backup, relatorio)
            except Exception as falha:
                print(f"ERRO_RELATORIO={falha}", flush=True)
            for falha in falhas:
                print(f"ERRO_RESTAURACAO={falha}", flush=True)
            print(f"BACKUP_FORA_DO_PROJETO={backup}", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
