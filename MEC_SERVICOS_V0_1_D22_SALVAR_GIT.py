r"""Registra o checkpoint validado do MEC-Serviços até o D22.

Na raiz de MEC-Servicos, execute:
    python .\MEC_SERVICOS_V0_1_D22_SALVAR_GIT.py

Inclui o código dos portais, solicitações, upload ZIP/RAR, configurações do
frontend e scripts/relatórios MEC. Cria commit em main, a tag v0.1.0-d22 e
envia ambos ao origin do MEC-Servicos. Confere a evidência de testes/build
do FIX3 já executado. Arquivos CGX e a imagem de marcas ficam preservados
localmente. Uma falha de envio mantém o commit local para nova execução.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


REVISION = "MEC-SERVICOS-V0.1-D22-CHECKPOINT-GIT-2026-10-02"
TAG = "v0.1.0-d22"
MENSAGEM = "MEC-Servicos V0.1 D22 - Portais, solicitacoes e arquivos tecnicos ZIP/RAR"
RELATORIO_FIX3 = "MEC_SERVICOS_V0_1_D22_FIX3_ZIP_RAR_TESTES_MEC_RELATORIO.json"
PASTAS_MEC = ("backend/app", "frontend/src")
ARQUIVOS_MEC = (
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/vite.config.ts",
    "tests/test_portal_cliente_solicitacoes.py",
    "CONFIGURAR_FRONTEND_MEC_SERVICOS.ps1",
    "D22_CONTRATO_ARQUIVOS_TECNICOS.txt",
)
PADROES_MEC = (
    ":(top,glob)MEC_SERVICOS*.py",
    ":(top,glob)MEC_SERVICOS*.json",
    ":(top,glob)MEC_SERVICOS*.txt",
)


def git(
    raiz: Path,
    *argumentos: str,
    mostrar: bool = False,
    retornos: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess:
    executavel = shutil.which("git")
    if not executavel:
        raise RuntimeError("Git não encontrado no PATH.")
    if mostrar:
        print("Executando git " + " ".join(argumentos) + "...", flush=True)
    processo = subprocess.run(
        [executavel, "-c", "core.quotepath=false", *argumentos],
        cwd=raiz, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False, timeout=300,
    )
    if mostrar:
        for saida in (processo.stdout, processo.stderr):
            if saida:
                print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
    if processo.returncode not in retornos:
        detalhe = (processo.stderr or processo.stdout or "").strip()
        raise RuntimeError(
            "git " + " ".join(argumentos) + f" retornou {processo.returncode}. " + detalhe
        )
    return processo


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/services/arquivo_tecnico.py",
        "frontend/package.json", "frontend/src/services/api.ts",
        "frontend/src/pages/client/ClientArquivosTecnicosPage.tsx",
    )
    if not all((raiz / nome).is_file() for nome in obrigatorios):
        raise RuntimeError("Execute este script na raiz do projeto MEC-Servicos.")
    raiz_git = Path(git(raiz, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if raiz_git != raiz:
        raise RuntimeError("A raiz do projeto difere da raiz do repositório Git.")
    return raiz


def validar_origem(raiz: Path) -> None:
    origem = git(raiz, "remote", "get-url", "origin").stdout.strip()
    if origem.lower().startswith("git@github.com:"):
        caminho = origem.split(":", 1)[1]
    else:
        partes = urlsplit(origem)
        if partes.hostname != "github.com" or partes.scheme not in {"https", "ssh"}:
            raise RuntimeError("O origin não corresponde ao GitHub do MEC-Servicos.")
        caminho = partes.path.lstrip("/")
    if caminho.rstrip("/").lower().removesuffix(".git") != "projetoxcadcam-byte/mec-servicos":
        raise RuntimeError("O origin não corresponde ao repositório MEC-Servicos esperado.")
    print("ORIGIN_MEC_CONFIRMADO=True", flush=True)


def validar_evidencia(raiz: Path) -> None:
    caminho = raiz / RELATORIO_FIX3
    if not caminho.is_file():
        raise RuntimeError("O relatório aprovado do FIX3 não foi encontrado na raiz.")
    relatorio = json.loads(caminho.read_text(encoding="utf-8-sig"))
    etapas = {item.get("nome"): item.get("returncode") for item in relatorio.get("etapas", [])}
    if relatorio.get("resultado") != "OK" or any(
        etapas.get(nome) != 0 for nome in ("validacao extensoes", "pytest", "npm build")
    ):
        raise RuntimeError("O relatório do FIX3 não registra validação, testes e build aprovados.")
    print("EVIDENCIA_FIX3_TESTES_BUILD_OK=True", flush=True)


def caminho_mec(nome: str) -> bool:
    caminho = PurePosixPath(nome)
    if nome in ARQUIVOS_MEC:
        return True
    if any(nome.startswith(pasta + "/") for pasta in PASTAS_MEC):
        return True
    return (
        len(caminho.parts) == 1
        and caminho.name.startswith("MEC_SERVICOS")
        and caminho.suffix in {".py", ".json", ".txt"}
    )


def conferir_index(raiz: Path) -> list[str]:
    nomes = [nome for nome in git(raiz, "diff", "--cached", "--name-only", "-z").stdout.split("\0") if nome]
    externos = [nome for nome in nomes if not caminho_mec(nome)]
    if externos:
        raise RuntimeError(
            "Há arquivos preparados para commit fora do checkpoint MEC: " + ", ".join(externos)
        )
    return nomes


def tag_local(raiz: Path) -> str | None:
    consulta = git(raiz, "show-ref", "--verify", "--quiet", "refs/tags/" + TAG, retornos=(0, 1))
    if consulta.returncode == 1:
        return None
    return git(raiz, "rev-parse", TAG + "^{commit}").stdout.strip()


def referencias_remotas(raiz: Path) -> dict[str, str]:
    saida = git(
        raiz, "ls-remote", "origin", "refs/heads/main", "refs/tags/" + TAG,
        "refs/tags/" + TAG + "^{}",
    ).stdout
    referencias = {}
    for linha in saida.splitlines():
        campos = linha.split()
        if len(campos) == 2:
            referencias[campos[1]] = campos[0]
    return referencias


def main() -> int:
    print("MEC-Serviços D22 — Salvar checkpoint no Git", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    raiz: Path | None = None
    commit: str | None = None
    envio_concluido = False
    try:
        raiz = localizar_raiz()
        print(f"ROOT={raiz}", flush=True)
        branch = git(raiz, "branch", "--show-current").stdout.strip()
        if branch != "main":
            raise RuntimeError("A branch atual precisa ser main; encontrada: " + (branch or "HEAD destacado"))
        validar_origem(raiz)
        validar_evidencia(raiz)
        conferir_index(raiz)
        escopo = [*PASTAS_MEC, *(nome for nome in ARQUIVOS_MEC if (raiz / nome).exists()), *PADROES_MEC]
        print("ESCOPO=Backend, frontend, solicitações e scripts/relatórios MEC", flush=True)
        print("Atualizando a referência de origin/main...", flush=True)
        git(raiz, "fetch", "origin", "main", mostrar=True)
        atual = git(raiz, "rev-parse", "HEAD").stdout.strip()
        ancestrais = git(raiz, "merge-base", "--is-ancestor", "FETCH_HEAD", "HEAD", retornos=(0, 1))
        if ancestrais.returncode != 0:
            raise RuntimeError("origin/main contém commits ainda não integrados. Envie esta saída para sincronizarmos.")
        remoto = referencias_remotas(raiz)
        remota_tag = remoto.get("refs/tags/" + TAG + "^{}", remoto.get("refs/tags/" + TAG))
        local_tag = tag_local(raiz)
        pendentes = bool(git(raiz, "status", "--porcelain=v1", "--untracked-files=all", "--", *escopo).stdout)
        if local_tag is not None or remota_tag is not None:
            if pendentes or any(valor != atual for valor in (local_tag, remota_tag) if valor is not None):
                raise RuntimeError(f"A tag {TAG} já existe e conflita com este checkpoint. Sua referência foi preservada.")
        if pendentes:
            git(raiz, "add", "--", *escopo, mostrar=True)
            preparados = conferir_index(raiz)
            if not preparados:
                raise RuntimeError("Nenhum arquivo do checkpoint ficou preparado para commit.")
            print(f"ARQUIVOS_NO_CHECKPOINT={len(preparados)}", flush=True)
            git(raiz, "diff", "--cached", "--check", mostrar=True)
            git(raiz, "diff", "--cached", "--stat", mostrar=True)
            git(raiz, "commit", "-m", MENSAGEM, mostrar=True)
        elif local_tag is None and remota_tag is None:
            assunto = git(raiz, "log", "-1", "--format=%s").stdout.strip()
            if assunto != MENSAGEM:
                raise RuntimeError("Nenhuma alteração MEC encontrada e a tag D22 ainda não existe. Confira o status.")
            print("COMMIT_D22_JA_REGISTRADO=True", flush=True)
        else:
            print("CHECKPOINT_LOCAL_JA_REGISTRADO=True", flush=True)
        commit = git(raiz, "rev-parse", "HEAD").stdout.strip()
        print(f"COMMIT_LOCAL={commit}", flush=True)
        if remota_tag is not None and tag_local(raiz) is None:
            git(raiz, "fetch", "origin", "refs/tags/" + TAG + ":refs/tags/" + TAG, mostrar=True)
        if tag_local(raiz) is None:
            git(raiz, "tag", "-a", TAG, "-m", MENSAGEM, mostrar=True)
        print(f"TAG={TAG}", flush=True)
        git(raiz, "push", "--atomic", "origin", "main", "refs/tags/" + TAG, mostrar=True)
        envio_concluido = True
        referencias = referencias_remotas(raiz)
        tag_commit = referencias.get("refs/tags/" + TAG + "^{}", referencias.get("refs/tags/" + TAG))
        if referencias.get("refs/heads/main") != commit or tag_commit != commit:
            raise RuntimeError("O envio terminou, mas a confirmação das referências remotas não corresponde ao checkpoint.")
        if git(raiz, "status", "--porcelain=v1", "--untracked-files=all", "--", *escopo).stdout:
            raise RuntimeError("Surgiram alterações MEC durante o salvamento. Confira o status antes de continuar.")
        print("PUSH_MAIN_E_TAG_OK=True", flush=True)
        print("ARQUIVOS_MEC_SEM_PENDENCIAS=True", flush=True)
        print("STATUS_GERAL (inclui os arquivos locais fora deste checkpoint):", flush=True)
        git(raiz, "status", "--short", mostrar=True)
        print("RESULTADO=OK", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        print("ERRO=" + (str(erro) or "Execução interrompida pelo usuário."), flush=True)
        if commit:
            print(f"COMMIT_LOCAL_PRESERVADO={commit}", flush=True)
            print(f"ENVIO_TERMINOU={envio_concluido}", flush=True)
            print("Envie a saída completa; o commit local permite retomar o salvamento.", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
