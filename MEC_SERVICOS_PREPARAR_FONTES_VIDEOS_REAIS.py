"""Reúne fontes da instalação MEC para preparar vídeos com a interface real.

Execute na raiz do MEC-Servicos com o Python da .venv. Não instala dependências,
não inicia serviços e não altera o programa ou os bancos. Usa apenas a biblioteca
padrão do Python. O ZIP contém código da aplicação e recursos da interface.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
import zipfile

REVISION = "MEC-SERVICOS-FONTES-VIDEOS-REAIS-2026-10-14"
PASTAS_EXCLUIDAS = {
    "node_modules", "__pycache__", "data", "dados", "uploads", "upload",
    "anexos", "attachments", "documents", "documentos", "dist", "build",
    "coverage", "htmlcov", "logs", "credenciais", "credentials", "secrets",
}
EXTENSOES_INTERFACE = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".css", ".scss", ".sass",
    ".html", ".json", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico",
    ".avif", ".woff", ".woff2", ".ttf", ".otf",
}
ARQUIVOS_CONFIGURACAO = (
    "pyproject.toml", "requirements.txt", "backend/__init__.py",
    "frontend/package.json", "frontend/package-lock.json",
    "frontend/tsconfig.json", "frontend/tsconfig.app.json",
    "frontend/tsconfig.node.json", "frontend/vite.config.ts",
    "frontend/vite.config.js", "frontend/index.html",
)
FONTES_OBRIGATORIOS = (
    "frontend/package.json", "frontend/src/App.tsx", "frontend/src/main.tsx",
    "frontend/src/layouts/AdminLayout.tsx", "frontend/src/layouts/ClientLayout.tsx",
    "frontend/src/layouts/SupplierLayout.tsx",
    "frontend/src/pages/client/ClientSolicitacoesPage.tsx",
)
LIMITE_ARQUIVO = 25 * 1024 * 1024
LIMITE_TOTAL = 200 * 1024 * 1024


def e_link(caminho: Path) -> bool:
    if caminho.is_symlink():
        return True
    # Python 3.12 no Windows reconhece junctions separadamente de symlinks.
    verificar = getattr(caminho, "is_junction", None)
    return bool(verificar and verificar())


def raiz_projeto(informada: str | None) -> Path:
    candidatos = [Path(informada)] if informada else [Path.cwd(), Path(__file__).resolve().parent]
    if not informada and os.name == "nt":
        candidatos.append(Path(r"C:\Users\Omega\Desktop\MEC-Servicos"))
    for candidato in candidatos:
        raiz = candidato.resolve()
        if (raiz / "frontend/src").is_dir() and (raiz / "backend/app").is_dir():
            return raiz
    raise RuntimeError("Abra o PowerShell na pasta MEC-Servicos e execute novamente.")


def nome_permitido(nome: str) -> bool:
    valor = nome.casefold()
    return not (
        valor.startswith((".", "~"))
        or any(t in valor for t in ("credencial", "credential", "private-key", "private_key", "secret"))
        or valor.endswith((".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3"))
    )


def caminho_regular(raiz: Path, relativo: str) -> Path:
    caminho = raiz / relativo
    if caminho.is_absolute() and not caminho.resolve().is_relative_to(raiz):
        raise RuntimeError("Fonte fora da pasta do projeto: " + relativo)
    atual = caminho
    while atual != raiz:
        if e_link(atual):
            raise RuntimeError("Link ou junction não incluído: " + relativo)
        atual = atual.parent
    if not caminho.is_file():
        raise RuntimeError("Fonte necessário não encontrado: " + relativo)
    return caminho


def coletar_fontes(raiz: Path) -> list[Path]:
    for relativo in FONTES_OBRIGATORIOS:
        caminho_regular(raiz, relativo)
    selecionados: set[Path] = set()
    for relativo in ARQUIVOS_CONFIGURACAO:
        caminho = raiz / relativo
        if caminho.is_file() and not e_link(caminho):
            selecionados.add(caminho_regular(raiz, relativo))
    especificacoes = (
        ("backend/app", {".py", ".html", ".css", ".js"}),
        ("frontend/src", EXTENSOES_INTERFACE),
        ("frontend/public", EXTENSOES_INTERFACE),
    )
    for relativo, extensoes in especificacoes:
        pasta = raiz / relativo
        if not pasta.exists():
            continue
        if e_link(pasta):
            raise RuntimeError("Pasta de fontes é um link ou junction: " + relativo)
        for diretorio, subpastas, arquivos in os.walk(pasta, followlinks=False):
            pai = Path(diretorio)
            subpastas[:] = sorted(
                nome for nome in subpastas
                if nome.casefold() not in PASTAS_EXCLUIDAS
                and nome_permitido(nome) and not e_link(pai / nome)
            )
            for nome in sorted(arquivos):
                caminho = pai / nome
                # __init__.py é código necessário, apesar do prefixo reservado.
                permitido = nome == "__init__.py" or nome_permitido(nome)
                if not permitido or caminho.suffix.casefold() not in extensoes or e_link(caminho):
                    continue
                rel = caminho.relative_to(raiz).as_posix()
                selecionados.add(caminho_regular(raiz, rel))
    return sorted(selecionados, key=lambda p: p.relative_to(raiz).as_posix())


def criar_pacote(raiz: Path, destino: Path | None = None) -> tuple[Path, int, int]:
    fontes = coletar_fontes(raiz)
    total = 0
    for fonte in fontes:
        tamanho = fonte.stat().st_size
        if tamanho > LIMITE_ARQUIVO:
            raise RuntimeError("Fonte maior que 25 MB; confira: " + fonte.relative_to(raiz).as_posix())
        total += tamanho
    if total > LIMITE_TOTAL:
        raise RuntimeError("Fontes acima de 200 MB. Confira recursos grandes dentro de frontend/src ou public.")
    pasta = destino or raiz / "_mec_videos" / "fontes"
    pasta.mkdir(parents=True, exist_ok=True)
    instante = datetime.now(timezone.utc)
    nome = "MEC_SERVICOS_FONTES_VIDEOS_REAIS_" + instante.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8] + ".zip"
    final = pasta / nome
    manifesto = {
        "revision": REVISION,
        "criado_em_utc": instante.isoformat(),
        "finalidade": "Preparação de vídeos com a interface real em ambiente de demonstração",
        "inclui_bancos": False,
        "inclui_arquivos_env": False,
        "inclui_anexos_clientes": False,
        "arquivos": [],
    }
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="mec_fontes_", suffix=".tmp", dir=pasta, delete=False) as temp:
            temporario = Path(temp.name)
        with zipfile.ZipFile(temporario, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as pacote:
            for fonte in fontes:
                antes = fonte.stat()
                relativo = fonte.relative_to(raiz).as_posix()
                conteudo = fonte.read_bytes()
                depois = fonte.stat()
                if (antes.st_size, antes.st_mtime_ns) != (depois.st_size, depois.st_mtime_ns):
                    raise RuntimeError("Fonte alterado durante a coleta; execute novamente: " + relativo)
                if len(conteudo) != antes.st_size:
                    raise RuntimeError("Leitura incompleta: " + relativo)
                pacote.writestr(relativo, conteudo)
                manifesto["arquivos"].append({"arquivo": relativo, "bytes": len(conteudo), "sha256": hashlib.sha256(conteudo).hexdigest()})
            manifesto["total_fontes"] = len(fontes)
            manifesto["bytes_fontes"] = total
            pacote.writestr("MEC_FONTES_VIDEOS_MANIFESTO.json", json.dumps(manifesto, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(temporario) as pacote:
            if pacote.testzip() is not None:
                raise RuntimeError("A conferência do ZIP falhou.")
        temporario.replace(final)
        return final, len(fontes), total
    except BaseException:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", help="Pasta MEC-Servicos; normalmente não é necessário informar.")
    args = parser.parse_args(argv)
    print("MEC-Serviços — Fontes para vídeos com telas reais", flush=True)
    print("REVISION=" + REVISION, flush=True)
    try:
        raiz = raiz_projeto(args.raiz)
        print("ROOT=" + str(raiz), flush=True)
        print("Reunindo código e recursos da interface…", flush=True)
        arquivo, quantidade, tamanho = criar_pacote(raiz)
        print("FONTES_INCLUIDOS=" + str(quantidade), flush=True)
        print("BYTES_FONTES=" + str(tamanho), flush=True)
        print("BANCOS_INCLUIDOS=False", flush=True)
        print("ARQUIVOS_ENV_INCLUIDOS=False", flush=True)
        print("ANEXOS_CLIENTES_INCLUIDOS=False", flush=True)
        print("PROGRAMA_E_BANCOS_ALTERADOS=False", flush=True)
        print("ZIP=" + str(arquivo), flush=True)
        print("RESULTADO=OK", flush=True)
        print("Envie neste chat o arquivo ZIP indicado acima para preparar a gravação da interface.", flush=True)
        print("Este coletor ainda não grava telas nem gera áudio.", flush=True)
        return 0
    except KeyboardInterrupt:
        print("ERRO=Coleta interrompida. As fontes foram preservadas.", flush=True)
    except Exception as erro:
        print("ERRO=" + str(erro), flush=True)
    print("RESULTADO=ERRO", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
