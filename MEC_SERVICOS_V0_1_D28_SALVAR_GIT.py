r"""Salva o checkpoint MEC-Serviços D28 no GitHub.

Na raiz do MEC-Servicos, com o D28 instalado e aprovado:
    python .\MEC_SERVICOS_V0_1_D28_SALVAR_GIT.py

Confere o origin, a branch main, o relatório D28 e os sete fontes instalados.
Inclui código, testes, configurações e scripts/relatórios MEC. Corrige os
finais de textos MEC com backup, cria o commit e a tag v0.1.0-d28 e envia
ambos ao GitHub. Uma falha de envio preserva o commit para nova execução.
Dados, anexos, ambientes e arquivos de outros projetos permanecem locais.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

REVISION = "MEC-SERVICOS-V0.1-D28-CHECKPOINT-GIT-2026-10-02"
REVISION_D28 = "MEC-SERVICOS-V0.1-D28-PORTAIS-ENTREGAS-ACEITE-2026-10-02"
INSTALADOR_D28 = "MEC_SERVICOS_V0_1_D28_PORTAIS_ENTREGAS_ACEITE.py"
RELATORIO_D28 = "MEC_SERVICOS_V0_1_D28_PORTAIS_ENTREGAS_ACEITE_RELATORIO.json"
TAG = "v0.1.0-d28"
MENSAGEM = "MEC-Servicos V0.1 D28 - Portais, producao, entregas e aceite"
REPOSITORIO = "projetoxcadcam-byte/mec-servicos"
ARQUIVOS_MEC = {
    ".gitignore", ".gitattributes", "README.md", "requirements.txt", "pyproject.toml",
    "frontend/package.json", "frontend/package-lock.json", "frontend/vite.config.ts",
    "frontend/index.html", "frontend/tsconfig.json", "frontend/tsconfig.app.json", "frontend/tsconfig.node.json",
    "tests/conftest.py", "tests/__init__.py", "CONFIGURAR_FRONTEND_MEC_SERVICOS.ps1",
    "D22_CONTRATO_ARQUIVOS_TECNICOS.txt",
}
FONTES_D28 = {
    "backend/app/api/rotas/portal_entregas.py", "backend/app/schemas/portal_entregas.py",
    "backend/app/services/portal_entregas.py", "tests/test_portal_entregas.py",
    "frontend/src/pages/entregas/PortalEntregasPage.tsx",
    "frontend/src/pages/entregas/PortalEntregasPage.css", "frontend/src/pages/entregas/entregasPortal.ts",
}


def git(raiz: Path, *argumentos: str, mostrar: bool = False, retornos: tuple[int, ...] = (0,)):
    executavel = shutil.which("git")
    if not executavel:
        raise RuntimeError("Git não encontrado no PATH.")
    if mostrar:
        print("Executando git " + " ".join(argumentos) + "...", flush=True)
    processo = subprocess.run([executavel, "-c", "core.quotepath=false", *argumentos], cwd=raiz,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=300)
    if mostrar:
        for saida in (processo.stdout, processo.stderr):
            if saida:
                print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
    if processo.returncode not in retornos:
        raise RuntimeError("git " + " ".join(argumentos) + f" retornou {processo.returncode}. "
                           + (processo.stderr or processo.stdout or "").strip())
    return processo


def nomes(saida: str) -> list[str]:
    return [nome for nome in saida.split("\0") if nome]


def caminho_mec(nome: str) -> bool:
    caminho = PurePosixPath(nome)
    if caminho.is_absolute() or ".." in caminho.parts:
        return False
    if any(p in {"__pycache__", "node_modules", "dist", "_mec_backups", "data", "storage", "uploads", "cgx", "mold"}
           or p == ".env" or p.startswith(".env.") for p in caminho.parts):
        return False
    if caminho.suffix.lower() in {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}:
        return False
    if nome in ARQUIVOS_MEC:
        return True
    if nome.startswith(("backend/app/", "frontend/src/")):
        return True
    if len(caminho.parts) == 2 and caminho.parts[0] == "tests" and caminho.name.startswith("test_") and caminho.suffix == ".py":
        return True
    return len(caminho.parts) == 1 and caminho.name.startswith("MEC_SERVICOS") and caminho.suffix in {".py", ".json", ".txt"}


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (*FONTES_D28, "backend/app/principal.py", "backend/app/api/roteador.py",
                    "frontend/src/App.tsx", "frontend/package.json", INSTALADOR_D28, RELATORIO_D28)
    ausentes = sorted(nome for nome in obrigatorios if not (raiz / nome).is_file())
    if ausentes:
        raise RuntimeError("Execute na raiz de MEC-Servicos com D28 instalado. Arquivos ausentes: " + ", ".join(ausentes))
    raiz_git = Path(git(raiz, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if raiz_git != raiz:
        raise RuntimeError("A raiz do projeto difere da raiz do repositório Git.")
    return raiz


def origem_mec(origem: str) -> bool:
    if origem.lower().startswith("git@github.com:"):
        caminho = origem.split(":", 1)[1]
    else:
        partes = urlsplit(origem)
        if partes.hostname != "github.com" or partes.scheme not in {"https", "ssh"}:
            return False
        caminho = partes.path.lstrip("/")
    return caminho.rstrip("/").lower().removesuffix(".git") == REPOSITORIO


def validar_origem(raiz: Path) -> None:
    for argumentos in (("remote", "get-url", "--all", "origin"), ("remote", "get-url", "--push", "--all", "origin")):
        urls = git(raiz, *argumentos).stdout.splitlines()
        if not urls or not all(origem_mec(url.strip()) for url in urls):
            raise RuntimeError("O origin de consulta ou envio difere do repositório GitHub MEC-Servicos esperado.")
    print("ORIGIN_MEC_CONSULTA_E_ENVIO_CONFIRMADOS=True", flush=True)


def validar_evidencia(raiz: Path) -> None:
    relatorio = json.loads((raiz / RELATORIO_D28).read_text(encoding="utf-8-sig"))
    etapas = {e.get("nome"): e.get("returncode") for e in relatorio.get("etapas", [])}
    if relatorio.get("revision") != REVISION_D28 or relatorio.get("resultado") != "OK" or any(
        etapas.get(nome) != 0 for nome in ("validacao contrato", "contrato portais", "pytest", "npm build")):
        raise RuntimeError("O relatório D28 não registra contrato, testes e build aprovados. Confira a instalação D28.")
    arvore = ast.parse((raiz / INSTALADOR_D28).read_text(encoding="utf-8-sig"))
    valores = {}
    for item in arvore.body:
        if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name) and item.targets[0].id in {"REVISION", "FONTES"}:
            valores[item.targets[0].id] = ast.literal_eval(item.value)
    fontes = valores.get("FONTES")
    if valores.get("REVISION") != REVISION_D28 or not isinstance(fontes, dict) or set(fontes) != FONTES_D28:
        raise RuntimeError("O instalador D28 difere da revisão esperada.")
    for nome, fonte in fontes.items():
        atual = (raiz / nome).read_text(encoding="utf-8-sig").replace("\r\n", "\n").rstrip()
        if atual != fonte.replace("\r\n", "\n").rstrip():
            raise RuntimeError("Um fonte D28 foi alterado após a instalação aprovada: " + nome)
    print("EVIDENCIA_D28_CONTRATO_TESTES_BUILD_OK=True", flush=True)
    print("SETE_FONTES_D28_CONFERIDOS=True", flush=True)


def conferir_estado(raiz: Path) -> None:
    if git(raiz, "branch", "--show-current").stdout.strip() != "main":
        raise RuntimeError("A branch atual precisa ser main. Nenhum arquivo foi preparado.")
    if git(raiz, "diff", "--name-only", "--diff-filter=U", "-z").stdout:
        raise RuntimeError("Há conflitos Git pendentes. O checkpoint foi interrompido.")
    for nome in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-apply", "rebase-merge"):
        caminho = Path(git(raiz, "rev-parse", "--git-path", nome).stdout.strip())
        if not caminho.is_absolute():
            caminho = raiz / caminho
        if caminho.exists():
            raise RuntimeError("Existe uma integração Git em andamento. Conclua essa operação antes do checkpoint.")


def conferir_index(raiz: Path) -> list[str]:
    preparados = nomes(git(raiz, "diff", "--cached", "--name-only", "--no-renames", "-z").stdout)
    externos = [nome for nome in preparados if not caminho_mec(nome)]
    if externos:
        raise RuntimeError("Há arquivos preparados fora do checkpoint MEC. Eles foram preservados: " + ", ".join(externos))
    return preparados


def alteracoes_mec(raiz: Path) -> list[str]:
    encontrados = set()
    for argumentos in (("diff", "--name-only", "--no-renames", "-z"),
                       ("diff", "--cached", "--name-only", "--no-renames", "-z"),
                       ("ls-files", "--others", "--exclude-standard", "-z")):
        encontrados.update(nomes(git(raiz, *argumentos).stdout))
    return sorted(nome for nome in encontrados if caminho_mec(nome))


def ajustar_texto(conteudo: bytes) -> bytes:
    quebra = b"\r\n" if b"\r\n" in conteudo else b"\n"
    linhas = [linha.rstrip(b" \t") for linha in conteudo.splitlines()]
    while linhas and not linhas[-1]:
        linhas.pop()
    if not linhas:
        return conteudo
    return quebra.join(linhas) + quebra


def corrigir_textos(raiz: Path, candidatos: list[str]) -> None:
    alterados = {}
    for nome in candidatos:
        p = PurePosixPath(nome)
        caminho = raiz / nome
        if p.suffix != ".txt" or len(p.parts) != 1 or not caminho.is_file() or caminho.is_symlink():
            continue
        anterior = caminho.read_bytes();novo = ajustar_texto(anterior)
        if novo != anterior:
            alterados[nome] = (anterior, novo)
    if not alterados:
        return
    backup = raiz / "_mec_backups" / ("D28_GIT_TEXTOS_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    backup.mkdir(parents=True, exist_ok=False)
    print(f"BACKUP_TEXTOS={backup}", flush=True)
    for nome, (anterior, novo) in alterados.items():
        (backup / nome).write_bytes(anterior)
        caminho = raiz / nome
        if caminho.read_bytes() != anterior:
            raise RuntimeError("O texto foi alterado durante o checkpoint: " + nome)
        temporario = None
        try:
            with tempfile.NamedTemporaryFile(dir=raiz, prefix="mec_d28_git_texto_", delete=False) as arquivo:
                temporario = Path(arquivo.name);arquivo.write(novo)
            os.replace(temporario, caminho)
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)
        print("FINAL_TEXTO_CORRIGIDO=" + nome, flush=True)


def tag_local(raiz: Path) -> tuple[str, str] | None:
    consulta = git(raiz, "show-ref", "--verify", "--quiet", "refs/tags/" + TAG, retornos=(0, 1))
    if consulta.returncode == 1:
        return None
    objeto = git(raiz, "rev-parse", "refs/tags/" + TAG).stdout.strip()
    commit = git(raiz, "rev-parse", "refs/tags/" + TAG + "^{commit}").stdout.strip()
    return objeto, commit


def referencias_remotas(raiz: Path) -> dict[str, str]:
    saida = git(raiz, "ls-remote", "origin", "refs/heads/main", "refs/tags/" + TAG, "refs/tags/" + TAG + "^{}").stdout
    return {campos[1]: campos[0] for linha in saida.splitlines() if len(campos := linha.split()) == 2}


def main() -> int:
    print("MEC-Serviços D28 — Salvar checkpoint no GitHub", flush=True)
    print("REVISION=" + REVISION, flush=True)
    commit = None;envio_concluido = False
    try:
        raiz = localizar_raiz();print(f"ROOT={raiz}", flush=True)
        conferir_estado(raiz);validar_origem(raiz);validar_evidencia(raiz);conferir_index(raiz)
        print("ESCOPO=Backend, frontend, testes, configurações e scripts/relatórios MEC", flush=True)
        git(raiz, "fetch", "--no-tags", "origin", "main", mostrar=True)
        inicial = git(raiz, "rev-parse", "HEAD").stdout.strip()
        if git(raiz, "merge-base", "--is-ancestor", "FETCH_HEAD", "HEAD", retornos=(0, 1)).returncode != 0:
            raise RuntimeError("origin/main contém commits ainda não integrados. Envie esta saída para sincronizarmos.")
        remotas = referencias_remotas(raiz)
        remota_tag = remotas.get("refs/tags/" + TAG + "^{}", remotas.get("refs/tags/" + TAG))
        local_tag = tag_local(raiz)
        candidatos = alteracoes_mec(raiz)
        if local_tag is not None or remota_tag is not None:
            if candidatos or (local_tag and local_tag[1] != inicial) or (remota_tag and remota_tag != inicial):
                raise RuntimeError("A tag " + TAG + " já existe e conflita com este checkpoint. Ela foi preservada.")
            if local_tag and remota_tag and local_tag[0] != remotas.get("refs/tags/" + TAG):
                raise RuntimeError("A tag local difere da tag remota. As duas referências foram preservadas.")
        if candidatos:
            corrigir_textos(raiz, candidatos)
            candidatos = alteracoes_mec(raiz)
            git(raiz, "add", "--", *(":(top,literal)" + nome for nome in candidatos), mostrar=True)
            preparados = conferir_index(raiz)
            if not preparados:
                raise RuntimeError("Nenhum arquivo ficou preparado para o checkpoint.")
            print(f"ARQUIVOS_NO_CHECKPOINT={len(preparados)}", flush=True)
            # CRLF é um final de linha válido; mantém as verificações padrão de espaços.
            git(raiz, "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
                "diff", "--cached", "--check", mostrar=True)
            git(raiz, "diff", "--cached", "--stat", mostrar=True)
            # Confere a branch e o HEAD antes de gravar o commit.
            conferir_estado(raiz)
            if git(raiz, "rev-parse", "HEAD").stdout.strip() != inicial:
                raise RuntimeError("O HEAD mudou durante a preparação. O index foi preservado.")
            git(raiz, "commit", "-m", MENSAGEM, mostrar=True)
        elif local_tag is None and remota_tag is None:
            if git(raiz, "log", "-1", "--format=%s").stdout.strip() != MENSAGEM:
                raise RuntimeError("Nenhuma alteração MEC encontrada e o checkpoint D28 ainda não está registrado.")
            print("COMMIT_D28_JA_REGISTRADO=True", flush=True)
        else:
            print("CHECKPOINT_LOCAL_JA_REGISTRADO=True", flush=True)
        commit = git(raiz, "rev-parse", "HEAD").stdout.strip()
        print("COMMIT_LOCAL=" + commit, flush=True)
        if remota_tag is not None and tag_local(raiz) is None:
            git(raiz, "fetch", "origin", "refs/tags/" + TAG + ":refs/tags/" + TAG, mostrar=True)
        if tag_local(raiz) is None:
            git(raiz, "tag", "-a", TAG, "-m", MENSAGEM, mostrar=True)
        conferir_estado(raiz)
        tag = tag_local(raiz)
        if tag is None or tag[1] != commit or git(raiz, "rev-parse", "HEAD").stdout.strip() != commit:
            raise RuntimeError("As referências locais mudaram durante o checkpoint. O commit foi preservado.")
        if alteracoes_mec(raiz):
            raise RuntimeError("Surgiram alterações MEC durante o checkpoint. O commit foi preservado e ainda não foi enviado.")
        print("TAG=" + TAG, flush=True)
        git(raiz, "push", "--atomic", "origin", commit + ":refs/heads/main", tag[0] + ":refs/tags/" + TAG, mostrar=True)
        envio_concluido = True
        remotas = referencias_remotas(raiz)
        tag_commit = remotas.get("refs/tags/" + TAG + "^{}", remotas.get("refs/tags/" + TAG))
        if remotas.get("refs/heads/main") != commit or tag_commit != commit or remotas.get("refs/tags/" + TAG) != tag[0]:
            raise RuntimeError("O envio terminou, mas a confirmação remota não corresponde ao checkpoint.")
        if alteracoes_mec(raiz):
            raise RuntimeError("Surgiram alterações MEC após o envio. O checkpoint enviado foi preservado.")
        print("PUSH_MAIN_E_TAG_OK=True", flush=True)
        print("ARQUIVOS_MEC_SEM_PENDENCIAS=True", flush=True)
        print("REPOSITORIO=https://github.com/projetoxcadcam-byte/MEC-Servicos", flush=True)
        print("STATUS_GERAL:", flush=True);git(raiz, "status", "--short", mostrar=True)
        print("RESULTADO=OK", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        print("ERRO=" + (str(erro) or "Execução interrompida pelo usuário."), flush=True)
        if commit:
            print("COMMIT_LOCAL_PRESERVADO=" + commit, flush=True)
            print(f"ENVIO_TERMINOU={envio_concluido}", flush=True)
            print("O commit local permite retomar o salvamento executando o mesmo script.", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
