from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D16_DIAGNOSTICO_ARQUIVOS_TECNICOS_FIX1.py"
REVISION = "MEC-SERVICOS-V0.1-D16-DIAGNOSTICO-ARQUIVOS-TECNICOS-FIX1-ROOT-VALIDATION-2026-10-01"
REPORT_TXT = "MEC_SERVICOS_V0_1_D16_DIAGNOSTICO_ARQUIVOS_TECNICOS_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D16_DIAGNOSTICO_ARQUIVOS_TECNICOS.json"

TARGETS = [
    "backend/app/database/base.py",
    "backend/app/database/sessao.py",
    "backend/app/principal.py",
    "backend/app/api/roteador.py",
    "backend/app/models/__init__.py",
    "backend/app/models/solicitacao.py",
    "backend/app/schemas/solicitacao.py",
    "backend/app/services/solicitacao.py",
    "backend/app/repositories/solicitacao.py",
    "backend/app/models/empresa.py",
    "backend/app/api/rotas/solicitacoes.py",
]

D15_TARGETS = [
    "MEC_SERVICOS_V0_1_D15_RANKING_FORNECEDORES.py",
    "MEC_SERVICOS_V0_1_D15_RANKING_FORNECEDORES.json",
    "MEC_SERVICOS_V0_1_D15_RANKING_FORNECEDORES_RELATORIO.txt",
    "backend/app/api/rotas/ranking_fornecedores.py",
    "backend/app/repositories/ranking_fornecedor.py",
    "backend/app/schemas/ranking_fornecedor.py",
    "backend/app/services/ranking_fornecedor.py",
    "tests/test_ranking_fornecedores.py",
]

ALLOWED_EXTENSIONS = [".step", ".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf"]


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        return (result.stdout or result.stderr).strip()
    except Exception as exc:
        return f"git_error: {type(exc).__name__}: {exc}"


def ast_check(path: Path) -> tuple[bool, str | None]:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_tokens(text: str, tokens: list[str]) -> dict[str, bool]:
    return {token: token in text for token in tokens}


def main() -> int:
    root = Path.cwd().resolve()

    report: list[str] = []
    data: dict[str, object] = {
        "revision": REVISION,
        "root": str(root),
        "generated_at": datetime.now().astimezone().isoformat(),
        "targets": {},
        "d15": {},
        "git": {},
        "dependencies": {},
        "architecture": {},
        "safety": {},
    }

    print("Plataforma de Serviços Mecânicos — D16 Diagnóstico Arquivos Técnicos")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    # Validação da raiz:
    # O MEC-Servicos pode conter outros diretórios/projetos auxiliares no mesmo
    # workspace. Portanto, a simples existência de src/cgx NÃO é suficiente
    # para classificar a raiz como CGX Platform.
    backend_dir = root / "backend"
    tests_dir = root / "tests"
    backend_app_dir = backend_dir / "app"

    if not backend_dir.is_dir() or not tests_dir.is_dir() or not backend_app_dir.is_dir():
        if (root / "src" / "cgx").exists() or (root / "src" / "cgx_platform").exists():
            print("ERRO: esta pasta não possui a estrutura backend/app + tests do MEC-Servicos.")
            print("A raiz encontrada parece ser o CGX Platform ou outra pasta.")
        else:
            print("ERRO: backend/app e/ou tests não encontrados; execute na raiz do MEC-Servicos.")
        return 21

    print("ROOT_VALIDATION= MEC-SERVICOS")
    print(f"BACKEND_APP_EXISTS= {backend_app_dir.is_dir()}")
    print(f"TESTS_EXISTS= {tests_dir.is_dir()}")

    report.append("Plataforma de Serviços Mecânicos — D16 Diagnóstico Arquivos Técnicos")
    report.append(f"REVISION= {REVISION}")
    report.append(f"ROOT= {root}")
    report.append("")

    # Git state: read-only.
    status = run_git(root, "status", "--short")
    branch = run_git(root, "branch", "--show-current")
    head = run_git(root, "rev-parse", "--short", "HEAD")
    tags = run_git(root, "tag", "--points-at", "HEAD")

    data["git"] = {
        "branch": branch,
        "head": head,
        "tags_at_head": tags,
        "status": status,
        "clean": not bool(status.strip()),
    }

    report.append("=== GIT ===")
    report.append(f"BRANCH= {branch}")
    report.append(f"HEAD= {head}")
    report.append(f"TAGS_AT_HEAD= {tags or '<none>'}")
    report.append("STATUS:")
    report.append(status or "<clean>")
    report.append("")

    # D15 baseline.
    d15: dict[str, object] = {}
    d15_ok = True
    for rel in D15_TARGETS:
        path = root / rel
        exists = path.exists()
        item: dict[str, object] = {"exists": exists}
        if exists and path.is_file():
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            if path.suffix.lower() == ".py":
                ok, err = ast_check(path)
                item["ast_ok"] = ok
                if err:
                    item["ast_error"] = err
                    d15_ok = False
        else:
            d15_ok = False
        d15[rel] = item

    data["d15"] = {"expected_files_present": d15_ok, "files": d15}

    report.append("=== D15 BASELINE ===")
    report.append(f"D15_TARGETS_PRESENT= {d15_ok}")
    for rel, item in d15.items():
        report.append(f"{rel}: {item}")
    report.append("")

    # Current architecture inventory.
    architecture: dict[str, object] = {}
    for rel in TARGETS:
        path = root / rel
        exists = path.exists()
        item: dict[str, object] = {"exists": exists}

        if exists and path.is_file():
            text = read(path)
            item["sha256"] = sha256_text(text)
            if path.suffix.lower() == ".py":
                ok, err = ast_check(path)
                item["ast_ok"] = ok
                if err:
                    item["ast_error"] = err

            tokens = [
                "class SolicitacaoServico",
                "class Empresa",
                "__tablename__",
                "Base",
                "create_all",
                "FastAPI",
                "APIRouter",
                "UploadFile",
                "File(",
                "multipart",
                "Form(",
                "FileResponse",
                "StreamingResponse",
                "include_router",
            ]
            item["tokens"] = find_tokens(text, tokens)

        architecture[rel] = item

    data["architecture"] = architecture

    report.append("=== ARQUITETURA ===")
    for rel, item in architecture.items():
        report.append(f"{rel}: {item}")
    report.append("")

    # Dependency detection without installing anything.
    dependencies = {}
    try:
        import fastapi  # type: ignore
        dependencies["fastapi"] = getattr(fastapi, "__version__", "installed")
    except Exception as exc:
        dependencies["fastapi"] = f"missing_or_error: {exc}"

    try:
        import sqlalchemy  # type: ignore
        dependencies["sqlalchemy"] = getattr(sqlalchemy, "__version__", "installed")
    except Exception as exc:
        dependencies["sqlalchemy"] = f"missing_or_error: {exc}"

    try:
        import multipart  # type: ignore
        dependencies["python_multipart"] = "installed"
    except Exception as exc:
        dependencies["python_multipart"] = f"missing_or_error: {exc}"

    data["dependencies"] = dependencies

    report.append("=== DEPENDÊNCIAS ===")
    for key, value in dependencies.items():
        report.append(f"{key}= {value}")
    report.append("")

    # Storage policy for D16.
    storage_policy = {
        "allowed_extensions": ALLOWED_EXTENSIONS,
        "max_size_mb_initial": 100,
        "hash": "SHA-256",
        "physical_delete_on_unlink": False,
        "initial_backend": "local_filesystem",
        "future_backend": "S3_or_cloud_storage",
        "cad_parser_in_d16": False,
        "viewer_in_d16": False,
    }
    data["safety"] = storage_policy

    report.append("=== D16 ESCOPO DE SEGURANÇA ===")
    for key, value in storage_policy.items():
        report.append(f"{key}= {value}")
    report.append("")

    report.append("=== DECISÃO DO DIAGNÓSTICO ===")
    report.append(
        "O D16 será implementado somente após confirmar a arquitetura real "
        "do backend, evitando substituir ou sobrescrever padrões existentes."
    )
    report.append(
        "Nenhum arquivo do projeto foi alterado por este diagnóstico."
    )

    (root / REPORT_TXT).write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / REPORT_JSON).write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"REPORT= {root / REPORT_TXT}")
    print(f"JSON= {root / REPORT_JSON}")
    print("FILES_CHANGED= 0")
    print("DATABASE_CHANGED= False")
    print("PROJECT_FILES_MODIFIED= False")
    print("D16_DIAGNOSTIC_OK= True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
