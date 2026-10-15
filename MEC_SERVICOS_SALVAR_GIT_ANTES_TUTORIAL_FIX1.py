"""Salva o checkpoint do MEC-Serviços antes da homologação do tutorial.

Execute na raiz do projeto com o Python da .venv. Usa o Git e o acesso ao
GitHub já configurados no computador. Não instala ou testa o tutorial.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import uuid

REVISION = "MEC-SERVICOS-GIT-ANTES-TESTE-TUTORIAL-FIX1-2026-10-15"
STEM = "MEC_SERVICOS_GIT_ANTES_TUTORIAL_FIX1_RELATORIO"
MENSAGEM = "Checkpoint do MEC-Servicos antes do teste do tutorial por perfil"
MARCADOR = "# MEC: arquivos locais fora do checkpoint Git"
PASTAS_LOCAIS = {
    ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "data", "upload", "uploads", "_mec_backups", "_mec_videos",
}
EXTENSOES_LOCAIS = {
    ".db", ".db3", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".sqlite-wal",
    ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm", ".pyc", ".pyo", ".log", ".tmp",
    ".bak", ".wav", ".mp3", ".mp4", ".webm", ".avi", ".rar", ".zip", ".7z",
    ".pdf", ".step", ".stp", ".dwg", ".dxf", ".igs", ".iges", ".stl",
    ".pem", ".key", ".pfx", ".p12",
}
EXEMPLOS_ENV = {".env.example", ".env.exemplo", ".env.sample", ".env.template"}
REGRAS = [
    "**/.venv/", "**/venv/", "**/node_modules/", "**/__pycache__/", "**/.pytest_cache/",
    "**/.mypy_cache/", "**/.ruff_cache/", "**/data/", "**/upload/", "**/uploads/",
    "/_mec_backups/", "/_mec_videos/", "/frontend/dist/", "/.coverage", "/htmlcov/",
    ".env", ".env.*", "!.env.example", "!.env.exemplo", "!.env.sample", "!.env.template",
    "MEC*_RELATORIO*.json", "MEC*_RELATORIO*.txt", "*_RELATORIO.json", "*_RELATORIO.txt",
    "mec*_relatorio*.json", "mec*_relatorio*.txt", "*_relatorio.json", "*_relatorio.txt",
    "*CREDENCIAIS*.txt", "*CREDENCIAIS*.json", "*CREDENCIAIS*.csv", "*ACESSOS_INICIAIS*.txt",
    "*credenciais*.txt", "*credenciais*.json", "*credenciais*.csv", "*acessos_iniciais*.txt",
    "*SENHAS*.txt", "*SENHAS*.json", "*senhas*.txt", "*senhas*.json",
    *["*" + extensao for extensao in sorted(EXTENSOES_LOCAIS)],
]
SEGREDOS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
]


class ErroCheckpoint(RuntimeError):
    pass


class Git:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.executavel = shutil.which("git")
        if not self.executavel:
            raise ErroCheckpoint("Git não encontrado neste computador.")

    def executar_bytes(self, *argumentos: str, limite: int = 30) -> bytes:
        ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            retorno = subprocess.run([self.executavel, "--literal-pathspecs", "-C", str(self.raiz), *argumentos],
                capture_output=True, env=ambiente, timeout=limite)
        except subprocess.TimeoutExpired:
            raise ErroCheckpoint("O comando Git demorou além do limite. Confira a conexão e execute novamente; os arquivos locais permanecem disponíveis.") from None
        if retorno.returncode:
            detalhe = retorno.stderr.decode("utf-8", errors="replace").strip()
            raise ErroCheckpoint("Git não concluiu " + argumentos[0] + ": " + detalhe[-4000:])
        return retorno.stdout

    def executar(self, *argumentos: str, limite: int = 30) -> str:
        return self.executar_bytes(*argumentos, limite=limite).decode("utf-8", errors="replace")

    def lista(self, *argumentos: str) -> list[str]:
        return [nome for nome in self.executar(*argumentos).split("\0") if nome]


def localizar_raiz() -> Path:
    for raiz in dict.fromkeys([Path.cwd().resolve(), Path(__file__).resolve().parent]):
        if (raiz / "backend/app/principal.py").is_file() and (raiz / "frontend/package.json").is_file():
            return raiz
    raise ErroCheckpoint("Salve e execute este arquivo na pasta C:\\Users\\Omega\\Desktop\\MEC-Servicos.")


def caminho_seguro(raiz: Path, relativo: str) -> Path:
    p = Path(relativo)
    if p.is_absolute() or ".." in p.parts:
        raise ErroCheckpoint("Caminho fora do projeto: " + relativo)
    alvo = raiz / p
    for componente in [alvo, *alvo.parents]:
        if componente == raiz:
            break
        if componente.is_symlink() or getattr(componente, "is_junction", lambda: False)():
            raise ErroCheckpoint("Arquivo com redirecionamento local precisa de conferência: " + relativo)
    if not alvo.resolve().is_relative_to(raiz):
        raise ErroCheckpoint("Caminho fora do projeto: " + relativo)
    return alvo


def arquivo_local(nome: str) -> bool:
    valor = nome.replace("\\", "/").casefold()
    partes = valor.split("/")
    base = partes[-1]
    if any(p in PASTAS_LOCAIS for p in partes[:-1]):
        return True
    if valor.startswith(("frontend/dist/", "htmlcov/")) or base in {".coverage", ".credentials", "credentials.json"}:
        return True
    if base.startswith(".env") and base not in EXEMPLOS_ENV:
        return True
    if any(base.endswith(extensao) for extensao in EXTENSOES_LOCAIS):
        return True
    if base.endswith((".txt", ".json", ".csv")):
        if any(p in base for p in ["credenciais", "senhas", "acessos_iniciais"]):
            return True
        if (base.startswith("mec") and "_relatorio" in base) or re.search(r"_relatorio\.(?:txt|json)$", base):
            return True
    return False


def relatorio_gerado(nome: str) -> bool:
    base = nome.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return base.endswith((".json", ".txt")) and (
        (base.startswith("mec") and "_relatorio" in base)
        or bool(re.search(r"_relatorio\.(?:txt|json)$", base))
    )


def conferir_conteudo(nome: str, dados: bytes) -> None:
    if len(dados) > 25 * 1024 * 1024:
        raise ErroCheckpoint("Arquivo maior que 25 MB precisa de conferência antes do envio: " + nome)
    if any(padrao.search(dados) for padrao in SEGREDOS):
        raise ErroCheckpoint("Possível chave privada ou token encontrado; conteúdo não exibido e envio interrompido: " + nome)


def conferir_origem(git: Git) -> None:
    def origem_mec(url: str) -> bool:
        if url.startswith("git@github.com:"):
            caminho = url.split(":", 1)[1]
        else:
            valor = urlsplit(url)
            if valor.scheme not in {"https", "ssh"} or valor.hostname != "github.com":
                return False
            if valor.scheme == "https" and (valor.username or valor.password):
                return False
            caminho = valor.path.lstrip("/")
        return caminho.rstrip("/").casefold().removesuffix(".git") == "projetoxcadcam-byte/mec-servicos"
    for argumentos in [("remote", "get-url", "--all", "origin"), ("remote", "get-url", "--push", "--all", "origin")]:
        urls = git.executar(*argumentos).strip().splitlines()
        if not urls or not all(origem_mec(url) for url in urls):
            raise ErroCheckpoint("Origin não corresponde ao repositório MEC-Servicos no GitHub.")


def conferir_repositorio(git: Git) -> None:
    raiz_git = Path(git.executar("rev-parse", "--show-toplevel").strip()).resolve()
    if raiz_git != git.raiz:
        raise ErroCheckpoint("A pasta MEC-Servicos precisa ser a raiz do próprio repositório Git.")
    if git.executar("branch", "--show-current").strip() != "main":
        raise ErroCheckpoint("O checkpoint espera a branch main. Sua branch atual foi preservada.")
    if git.lista("ls-files", "--unmerged", "-z"):
        raise ErroCheckpoint("Há conflitos no índice do Git. Resolva-os antes de criar o checkpoint.")
    for marcador in ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "index.lock"]:
        nome = Path(git.executar("rev-parse", "--git-path", marcador).strip())
        nome = nome if nome.is_absolute() else git.raiz / nome
        if nome.exists():
            raise ErroCheckpoint("Há outra operação Git em andamento: " + marcador + ". Conclua-a antes do checkpoint.")
    for campo in ["user.name", "user.email"]:
        if not git.executar("config", "--get", campo).strip():
            raise ErroCheckpoint("Configure seu nome e e-mail no Git antes de criar o checkpoint.")


def preparar_gitignore(raiz: Path) -> None:
    alvo = caminho_seguro(raiz, ".gitignore")
    antes = alvo.read_bytes() if alvo.exists() else b""
    texto = antes.decode("utf-8-sig")
    if MARCADOR in texto:
        return
    quebra = b"\r\n" if b"\r\n" in antes else b"\n"
    bloco = (MARCADOR + "\n" + "\n".join(REGRAS) + "\n").encode("utf-8").replace(b"\n", quebra)
    if antes and not antes.endswith(b"\n"):
        antes += quebra
    gravar_atomico(alvo, antes + quebra + bloco)


def gravar_atomico(alvo: Path, dados: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=alvo.parent, prefix="mec_git_", delete=False) as arquivo:
        arquivo.write(dados)
        temporario = Path(arquivo.name)
    try:
        os.replace(temporario, alvo)
    finally:
        temporario.unlink(missing_ok=True)


def conferir_commits_pendentes(git: Git, commits: list[str]) -> None:
    # Inspeciona também commits locais anteriores: arquivos removidos depois
    # ainda poderiam estar presentes no histórico que seria enviado.
    for commit in commits:
        nomes = git.lista("diff-tree", "--root", "--no-commit-id", "--name-only", "--diff-filter=AM", "-m", "-r", "-z", commit)
        for nome in nomes:
            if arquivo_local(nome):
                raise ErroCheckpoint("Um commit local ainda não enviado contém arquivo de uso local; histórico preservado para conferência: " + nome)
            conferir_conteudo(nome, git.executar_bytes("show", commit + ":" + nome))


def adicionar_arquivos(git: Git, nomes: list[str]) -> None:
    lote: list[str] = []
    tamanho = 0
    for nome in nomes:
        if lote and tamanho + len(nome) + 3 > 12000:
            git.executar("add", "-A", "--", *lote, limite=120)
            lote = []
            tamanho = 0
        lote.append(nome)
        tamanho += len(nome) + 3
    if lote:
        git.executar("add", "-A", "--", *lote, limite=120)


def preservar_e_desversionar_relatorios(git: Git, nomes: list[str], relatorio: dict) -> None:
    if not nomes:
        relatorio.update(relatorios_retirados_do_git=0, relatorios_locais_preservados=True)
        return
    backup = caminho_seguro(git.raiz, "_mec_backups/GIT_RELATORIOS_FIX1_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, exist_ok=False)
    manifesto = {}
    for nome in nomes:
        alvo = caminho_seguro(git.raiz, nome)
        dados = alvo.read_bytes() if alvo.is_file() else None
        if alvo.exists() and dados is None:
            raise ErroCheckpoint("Relatório não é um arquivo regular; preservado para conferência: " + nome)
        if dados is not None:
            copia = caminho_seguro(backup, "locais/" + nome)
            copia.parent.mkdir(parents=True, exist_ok=True)
            copia.write_bytes(dados)
            if copia.read_bytes() != dados:
                raise ErroCheckpoint("Não foi possível validar o backup local do relatório: " + nome)
        indice = git.executar_bytes("show", ":" + nome)
        copia_indice = caminho_seguro(backup, "indice/" + nome)
        copia_indice.parent.mkdir(parents=True, exist_ok=True)
        copia_indice.write_bytes(indice)
        manifesto[nome] = {
            "existia_localmente": dados is not None,
            "sha256_local": hashlib.sha256(dados).hexdigest() if dados is not None else None,
            "sha256_indice": hashlib.sha256(indice).hexdigest(),
        }
    (backup / "MANIFESTO.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    relatorio.update(backup_relatorios=str(backup), relatorios_retirados_do_git=0, relatorios_locais_preservados=False)
    print("BACKUP_RELATORIOS=" + str(backup), flush=True)
    # --cached retira somente do índice. O backup contém tanto o arquivo local
    # quanto uma eventual versão diferente que já estava preparada no índice.
    lote = []
    tamanho = 0
    for nome in nomes:
        if lote and tamanho + len(nome) + 3 > 12000:
            git.executar("rm", "--cached", "-f", "--ignore-unmatch", "--", *lote, limite=120)
            lote = []
            tamanho = 0
        lote.append(nome)
        tamanho += len(nome) + 3
    if lote:
        git.executar("rm", "--cached", "-f", "--ignore-unmatch", "--", *lote, limite=120)
    restantes = set(git.lista("ls-files", "-z"))
    for nome, registro in manifesto.items():
        if nome in restantes:
            raise ErroCheckpoint("O relatório ainda consta no índice: " + nome)
        alvo = caminho_seguro(git.raiz, nome)
        atual = hashlib.sha256(alvo.read_bytes()).hexdigest() if alvo.is_file() else None
        if atual != registro["sha256_local"]:
            raise ErroCheckpoint("O relatório local mudou durante a conferência; a alteração posterior foi preservada: " + nome)
    relatorio.update(relatorios_retirados_do_git=len(nomes), relatorios_locais_preservados=True)
    print("RELATORIOS_RETIRADOS_DO_GIT=" + str(len(nomes)), flush=True)
    print("RELATORIOS_LOCAIS_PRESERVADOS=True", flush=True)
    print("HISTORICO_ANTERIOR_GIT_PRESERVADO=True", flush=True)


def salvar_relatorio(raiz: Path, relatorio: dict) -> None:
    conteudo = (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for extensao in ["json", "txt"]:
        alvo = caminho_seguro(raiz, STEM + "." + extensao)
        gravar_atomico(alvo, conteudo)
        print(extensao.upper() + "=" + str(alvo), flush=True)


def main() -> int:
    print("MEC-Serviços — Git antes do tutorial FIX1", flush=True)
    print("REVISION=" + REVISION, flush=True)
    raiz = None
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapa": "inicio",
                 "commit_criado": False, "push_confirmado": False, "tutorial_testado": False}
    try:
        raiz = localizar_raiz()
        git = Git(raiz)
        print("ROOT=" + str(raiz), flush=True)
        conferir_repositorio(git)
        conferir_origem(git)
        print("ORIGIN_MEC_CONFIRMADO=True", flush=True)
        print("BRANCH=main", flush=True)
        relatorio["etapa"] = "conferir_arquivos_locais"
        rastreados = git.lista("ls-files", "-z")
        relatorios_rastreados = [nome for nome in rastreados if relatorio_gerado(nome)]
        indevidos = [nome for nome in rastreados if arquivo_local(nome) and not relatorio_gerado(nome)]
        if indevidos:
            raise ErroCheckpoint("Estes arquivos de uso local já estão rastreados no Git. O checkpoint parou antes do envio; os arquivos foram preservados: " + "; ".join(indevidos[:15]))
        relatorio["etapa"] = "conferir_remoto"
        print("Conferindo origin/main no GitHub...", flush=True)
        git.executar("fetch", "--no-tags", "origin", "refs/heads/main:refs/remotes/origin/main", limite=180)
        atras = int(git.executar("rev-list", "--count", "HEAD..refs/remotes/origin/main").strip())
        if atras:
            raise ErroCheckpoint("Origin/main tem alterações que ainda não estão neste computador. O checkpoint parou para integrar essas alterações; nenhum merge ou descarte foi executado.")
        commits_pendentes = git.executar("rev-list", "refs/remotes/origin/main..HEAD").splitlines()
        conferir_commits_pendentes(git, commits_pendentes)
        relatorio["etapa"] = "preparar_checkpoint"
        preparar_gitignore(raiz)
        candidatos = sorted(set(git.lista("ls-files", "--cached", "--others", "--exclude-standard", "-z")))
        nomes = [nome for nome in candidatos if not arquivo_local(nome)]
        for nome in nomes:
            alvo = caminho_seguro(raiz, nome)
            if alvo.is_file():
                conferir_conteudo(nome, alvo.read_bytes())
            elif alvo.exists():
                raise ErroCheckpoint("Destino rastreado precisa de conferência: " + nome)
        print("ARQUIVOS_CONFERIDOS=" + str(len(nomes)), flush=True)
        relatorio["etapa"] = "preservar_relatorios"
        preservar_e_desversionar_relatorios(git, relatorios_rastreados, relatorio)
        relatorio["etapa"] = "preparar_commit"
        adicionar_arquivos(git, nomes)
        staged = git.lista("diff", "--cached", "--name-only", "-z")
        novas_versoes = git.lista("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z")
        if any(arquivo_local(nome) for nome in novas_versoes):
            raise ErroCheckpoint("O índice contém arquivo de uso local; commit e envio interrompidos.")
        if staged:
            relatorio["etapa"] = "commit"
            print("Criando commit do checkpoint...", flush=True)
            git.executar("commit", "-m", MENSAGEM, limite=180)
            relatorio["commit_criado"] = True
        else:
            print("SEM_ALTERACOES_NOVAS=True; será identificado o commit atual.", flush=True)
        commit = git.executar("rev-parse", "HEAD").strip()
        conferir_commits_pendentes(git, [c for c in git.executar("rev-list", "refs/remotes/origin/main..HEAD").splitlines() if c not in commits_pendentes])
        tag = "checkpoint-antes-teste-tutorial-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        relatorio.update(commit=commit, tag=tag, branch="main", arquivos_no_commit=len(staged))
        relatorio["etapa"] = "tag"
        git.executar("tag", "-a", tag, "-m", "Estado do MEC-Servicos antes da homologacao do tutorial por perfil", commit)
        tag_objeto = git.executar("rev-parse", "refs/tags/" + tag).strip()
        print("COMMIT=" + commit, flush=True)
        print("TAG=" + tag, flush=True)
        relatorio["etapa"] = "push"
        print("Enviando main e a tag ao GitHub...", flush=True)
        git.executar("push", "--atomic", "--set-upstream", "origin", "HEAD:refs/heads/main", "refs/tags/" + tag + ":refs/tags/" + tag, limite=180)
        relatorio["etapa"] = "confirmar_envio"
        refs = {}
        for linha in git.executar("ls-remote", "origin", "refs/heads/main", "refs/tags/" + tag, limite=120).splitlines():
            valor, referencia = linha.split("\t", 1)
            refs[referencia] = valor
        if refs.get("refs/heads/main") != commit or refs.get("refs/tags/" + tag) != tag_objeto:
            raise ErroCheckpoint("O envio precisa de conferência: as referências remotas não correspondem ao checkpoint local.")
        relatorio.update(resultado="OK", etapa="concluido", push_confirmado=True)
        print("PUSH_MAIN_CONFIRMADO=True", flush=True)
        print("PUSH_TAG_CONFIRMADO=True", flush=True)
        salvar_relatorio(raiz, relatorio)
        print("RESULTADO=OK", flush=True)
        print("Checkpoint salvo no GitHub. O teste do tutorial pode ser retomado depois desta conferência.", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ETAPA=" + relatorio["etapa"], flush=True)
        print("ERRO=" + relatorio["erro"], flush=True)
        if relatorio.get("commit"):
            print("CHECKPOINT_LOCAL=" + relatorio["commit"], flush=True)
        if raiz:
            try:
                salvar_relatorio(raiz, relatorio)
            except OSError:
                print("RELATORIO_NAO_GRAVADO=True; preserve a saída do terminal.", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
