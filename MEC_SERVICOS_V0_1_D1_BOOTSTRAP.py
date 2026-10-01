from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D1_BOOTSTRAP.py"
REVISION = "MEC-SERVICOS-V0.1-D1-BOOTSTRAP-2026-09-30"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D1_BOOTSTRAP_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D1_BOOTSTRAP.json"

FILES: Dict[str, str] = {'.env.example': 'MEC_APP_NAME=Plataforma de Serviços Mecânicos\n'
                 'MEC_APP_VERSION=0.1.0\n'
                 'MEC_ENVIRONMENT=development\n'
                 'MEC_API_V1_PREFIX=/api/v1\n'
                 'MEC_DEBUG=true\n',
 '.gitignore': '# Python\n'
               '__pycache__/\n'
               '*.py[cod]\n'
               '*$py.class\n'
               '*.so\n'
               '\n'
               '# Virtual environments\n'
               '.venv/\n'
               'venv/\n'
               'env/\n'
               '\n'
               '# Test / tooling\n'
               '.pytest_cache/\n'
               '.coverage\n'
               'htmlcov/\n'
               '.mypy_cache/\n'
               '.ruff_cache/\n'
               '\n'
               '# Environment / secrets\n'
               '.env\n'
               '.env.*\n'
               '!.env.example\n'
               '\n'
               '# IDE / OS\n'
               '.vscode/\n'
               '.idea/\n'
               '.DS_Store\n'
               'Thumbs.db\n'
               '\n'
               '# Runtime / local data\n'
               'storage/\n'
               'uploads/\n'
               'logs/\n'
               '\n'
               '# Build artifacts\n'
               'build/\n'
               'dist/\n'
               '*.egg-info/\n',
 'README.md': '# Plataforma de Serviços Mecânicos\n'
              '\n'
              'Projeto independente para conectar clientes/projetistas e fornecedores de serviços '
              'mecânicos.\n'
              '\n'
              '## Estado\n'
              '\n'
              'Baseline inicial: **V0.1 D1 — Bootstrap**\n'
              '\n'
              'Nesta etapa o projeto possui:\n'
              '\n'
              '- API FastAPI mínima;\n'
              '- configuração por variáveis de ambiente;\n'
              '- endpoint raiz;\n'
              '- endpoint `/api/v1/health`;\n'
              '- teste automatizado do health check;\n'
              '- estrutura preparada para crescer de forma modular.\n'
              '\n'
              '## Importante\n'
              '\n'
              'Este projeto é independente do CGX Platform. Nesta fase não existe integração, dependência '
              'nem compartilhamento de código entre os dois.\n'
              '\n'
              '## Instalação\n'
              '\n'
              'No PowerShell, dentro da raiz deste projeto:\n'
              '\n'
              '```powershell\n'
              'python -m venv .venv\n'
              '.\\.venv\\Scripts\\Activate.ps1\n'
              'python -m pip install --upgrade pip\n'
              'python -m pip install -r requirements.txt\n'
              '```\n'
              '\n'
              '## Testes\n'
              '\n'
              '```powershell\n'
              'python -m pytest\n'
              '```\n'
              '\n'
              '## Executar a API\n'
              '\n'
              '```powershell\n'
              'python -m uvicorn backend.app.main:app --reload\n'
              '```\n'
              '\n'
              'Depois acesse:\n'
              '\n'
              '- API: `http://127.0.0.1:8000/`\n'
              '- Health: `http://127.0.0.1:8000/api/v1/health`\n'
              '- Swagger: `http://127.0.0.1:8000/docs`\n'
              '\n'
              '## Próxima etapa planejada\n'
              '\n'
              'V0.1 D2: banco de dados e persistência inicial, mantendo o mesmo método incremental e '
              'versionado.\n',
 'backend/__init__.py': '"""Backend da Plataforma de Serviços Mecânicos."""\n',
 'backend/app/__init__.py': '"""Aplicação principal."""\n',
 'backend/app/api/__init__.py': '"""Camada de API."""\n',
 'backend/app/api/router.py': 'from __future__ import annotations\n'
                              '\n'
                              'from fastapi import APIRouter\n'
                              '\n'
                              'from backend.app.api.routes.health import router as health_router\n'
                              '\n'
                              'api_router = APIRouter()\n'
                              'api_router.include_router(health_router)\n',
 'backend/app/api/routes/__init__.py': '"""Rotas HTTP da API."""\n',
 'backend/app/api/routes/health.py': 'from __future__ import annotations\n'
                                     '\n'
                                     'from fastapi import APIRouter\n'
                                     '\n'
                                     'from backend.app.core.config import settings\n'
                                     '\n'
                                     'router = APIRouter(tags=["system"])\n'
                                     '\n'
                                     '\n'
                                     '@router.get("/health")\n'
                                     'async def health() -> dict[str, str]:\n'
                                     '    return {\n'
                                     '        "status": "ok",\n'
                                     '        "service": settings.app_name,\n'
                                     '        "version": settings.app_version,\n'
                                     '    }\n',
 'backend/app/auth/__init__.py': '"""Autenticação e autorização. Será implementada em etapa posterior."""\n',
 'backend/app/core/__init__.py': '"""Configurações e infraestrutura central."""\n',
 'backend/app/core/config.py': 'from __future__ import annotations\n'
                               '\n'
                               'from pydantic_settings import BaseSettings, SettingsConfigDict\n'
                               '\n'
                               '\n'
                               'class Settings(BaseSettings):\n'
                               '    app_name: str = "Plataforma de Serviços Mecânicos"\n'
                               '    app_version: str = "0.1.0"\n'
                               '    environment: str = "development"\n'
                               '    api_v1_prefix: str = "/api/v1"\n'
                               '    debug: bool = True\n'
                               '\n'
                               '    model_config = SettingsConfigDict(\n'
                               '        env_file=".env",\n'
                               '        env_prefix="MEC_",\n'
                               '        extra="ignore",\n'
                               '    )\n'
                               '\n'
                               '\n'
                               'settings = Settings()\n',
 'backend/app/database/__init__.py': '"""Infraestrutura de banco de dados. Será implementada em V0.1 '
                                     'D2."""\n',
 'backend/app/main.py': 'from __future__ import annotations\n'
                        '\n'
                        'from fastapi import FastAPI\n'
                        '\n'
                        'from backend.app.api.router import api_router\n'
                        'from backend.app.core.config import settings\n'
                        '\n'
                        '\n'
                        'def create_app() -> FastAPI:\n'
                        '    application = FastAPI(\n'
                        '        title=settings.app_name,\n'
                        '        version=settings.app_version,\n'
                        '        debug=settings.debug,\n'
                        '    )\n'
                        '\n'
                        '    application.include_router(\n'
                        '        api_router,\n'
                        '        prefix=settings.api_v1_prefix,\n'
                        '    )\n'
                        '\n'
                        '    @application.get("/", tags=["system"])\n'
                        '    async def root() -> dict[str, str]:\n'
                        '        return {\n'
                        '            "name": settings.app_name,\n'
                        '            "version": settings.app_version,\n'
                        '            "status": "running",\n'
                        '        }\n'
                        '\n'
                        '    return application\n'
                        '\n'
                        '\n'
                        'app = create_app()\n',
 'backend/app/models/__init__.py': '"""Modelos de domínio e persistência. Será expandido nas próximas '
                                   'etapas."""\n',
 'backend/app/repositories/__init__.py': '"""Repositórios de persistência."""\n',
 'backend/app/schemas/__init__.py': '"""Schemas de entrada e saída da API."""\n',
 'backend/app/services/__init__.py': '"""Serviços e regras de negócio."""\n',
 'docs/README.md': '# Documentação\n'
                   '\n'
                   'Documentação técnica e funcional da Plataforma de Serviços Mecânicos.\n'
                   '\n'
                   'O projeto permanece independente do CGX Platform.\n',
 'pyproject.toml': '[project]\n'
                   'name = "mec-servicos"\n'
                   'version = "0.1.0"\n'
                   'description = "Plataforma B2B independente para intermediação de serviços mecânicos."\n'
                   'requires-python = ">=3.11"\n'
                   '\n'
                   '[tool.pytest.ini_options]\n'
                   'testpaths = ["tests"]\n'
                   'pythonpath = ["."]\n'
                   'addopts = "-q"\n',
 'requirements.txt': 'fastapi>=0.115,<1.0\n'
                     'uvicorn[standard]>=0.32,<1.0\n'
                     'pydantic-settings>=2.7,<3.0\n'
                     'pytest>=8.3,<9.0\n'
                     'httpx>=0.28,<1.0\n',
 'tests/__init__.py': '"""Testes automatizados."""\n',
 'tests/test_health.py': 'from fastapi.testclient import TestClient\n'
                         '\n'
                         'from backend.app.main import app\n'
                         '\n'
                         'client = TestClient(app)\n'
                         '\n'
                         '\n'
                         'def test_root() -> None:\n'
                         '    response = client.get("/")\n'
                         '    assert response.status_code == 200\n'
                         '    payload = response.json()\n'
                         '    assert payload["status"] == "running"\n'
                         '    assert payload["version"] == "0.1.0"\n'
                         '\n'
                         '\n'
                         'def test_health() -> None:\n'
                         '    response = client.get("/api/v1/health")\n'
                         '    assert response.status_code == 200\n'
                         '    payload = response.json()\n'
                         '    assert payload["status"] == "ok"\n'
                         '    assert payload["version"] == "0.1.0"\n'}

DIRECTORIES = [
    "backend/app/api/routes",
    "backend/app/auth",
    "backend/app/core",
    "backend/app/database",
    "backend/app/models",
    "backend/app/repositories",
    "backend/app/schemas",
    "backend/app/services",
    "docs",
    "tests",
]


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(normalize(content), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def is_cgx_root(root: Path) -> bool:
    markers = [
        root / "src" / "cgx",
        root / "src" / "cgx_platform",
    ]
    return any(marker.exists() for marker in markers)


def dependency_status() -> Dict[str, bool]:
    names = ["fastapi", "uvicorn", "pydantic_settings", "pytest", "httpx"]
    return {name: importlib.util.find_spec(name) is not None for name in names}


def validate_python_files(root: Path, paths: List[str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for rel in paths:
        if not rel.endswith(".py"):
            continue
        path = root / rel
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    return (not errors, errors)


def main() -> int:
    root = Path.cwd().resolve()
    print(f"{PROJECT_LABEL} — V0.1 D1 Bootstrap")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    if is_cgx_root(root):
        print("ERRO: esta pasta parece ser a raiz do CGX Platform.")
        print("Este projeto deve permanecer independente.")
        print("Crie/abra uma pasta separada para a Plataforma de Serviços Mecânicos e execute novamente.")
        return 20

    created: List[str] = []
    identical: List[str] = []
    conflicts: List[str] = []
    directories_created: List[str] = []

    for rel in DIRECTORIES:
        path = root / rel
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            directories_created.append(rel)

    for rel, content in FILES.items():
        content = normalize(content)
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists():
            existing = normalize(path.read_text(encoding="utf-8"))
            if existing == content:
                identical.append(rel)
            else:
                conflicts.append(rel)
            continue

        atomic_write(path, content)
        created.append(rel)

    expected_paths = sorted(FILES.keys())
    missing = [rel for rel in expected_paths if not (root / rel).exists()]
    files_ok = not missing
    ast_ok, ast_errors = validate_python_files(root, expected_paths)
    deps = dependency_status()

    hashes = {}
    for rel in expected_paths:
        path = root / rel
        if path.exists() and path.is_file():
            try:
                hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                pass

    status = "OK" if files_ok and ast_ok and not conflicts else "ATTENTION"

    report = {
        "project": PROJECT_LABEL,
        "revision": REVISION,
        "script": SCRIPT_NAME,
        "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "status": status,
        "cgx_guard_ok": True,
        "files_ok": files_ok,
        "ast_ok": ast_ok,
        "created": created,
        "identical_existing": identical,
        "conflicts_not_overwritten": conflicts,
        "missing": missing,
        "ast_errors": ast_errors,
        "directories_created": directories_created,
        "dependencies_installed": deps,
        "hashes_sha256": hashes,
        "next_commands": [
            r"python -m venv .venv",
            r".\.venv\Scripts\Activate.ps1",
            r"python -m pip install --upgrade pip",
            r"python -m pip install -r requirements.txt",
            r"python -m pytest",
            r"python -m uvicorn backend.app.main:app --reload",
        ],
    }

    json_path = root / REPORT_JSON
    txt_path = root / REPORT_TXT
    atomic_write(json_path, json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    dep_lines = "\n".join(
        f"  {name}={'INSTALLED' if installed else 'MISSING'}"
        for name, installed in deps.items()
    )

    txt_lines = [
        f"{PROJECT_LABEL} — V0.1 D1 Bootstrap",
        f"REVISION={REVISION}",
        f"ROOT={root}",
        "",
        f"STATUS={status}",
        "CGX_GUARD_OK=True",
        f"FILES_OK={files_ok}",
        f"AST_OK={ast_ok}",
        f"CONFLICTS={len(conflicts)}",
        f"MISSING={len(missing)}",
        "",
        "CREATED:",
        *([f"  {item}" for item in created] or ["  (none)"]),
        "",
        "IDENTICAL_EXISTING:",
        *([f"  {item}" for item in identical] or ["  (none)"]),
        "",
        "CONFLICTS_NOT_OVERWRITTEN:",
        *([f"  {item}" for item in conflicts] or ["  (none)"]),
        "",
        "MISSING_FILES:",
        *([f"  {item}" for item in missing] or ["  (none)"]),
        "",
        "AST_ERRORS:",
        *([f"  {item}" for item in ast_errors] or ["  (none)"]),
        "",
        "DEPENDENCIES:",
        dep_lines,
        "",
        "NEXT:",
        "  1. Criar/ativar .venv, se ainda nao existir.",
        "  2. python -m pip install -r requirements.txt",
        "  3. python -m pytest",
        "  4. python -m uvicorn backend.app.main:app --reload",
        "",
        "OBSERVACAO:",
        "  O bootstrap nao sobrescreve arquivos existentes com conteudo diferente.",
        "  Se CONFLICTS > 0, envie este relatorio antes de alterar qualquer arquivo.",
        "",
    ]
    atomic_write(txt_path, "\n".join(txt_lines))

    print(f"FILES_OK= {files_ok}")
    print(f"AST_OK= {ast_ok}")
    print(f"CREATED= {len(created)}")
    print(f"IDENTICAL_EXISTING= {len(identical)}")
    print(f"CONFLICTS= {len(conflicts)}")
    print(f"REPORT= {txt_path}")
    print(f"JSON= {json_path}")

    if conflicts:
        print("ATENCAO: existem arquivos com conteudo diferente; nenhum deles foi sobrescrito.")
        for rel in conflicts:
            print(f"  CONFLICT: {rel}")
        return 30

    if not files_ok or not ast_ok:
        print("ERRO: validacao do bootstrap falhou.")
        return 40

    print("BOOTSTRAP_OK= True")
    print()
    print("Proximo passo, apos instalar as dependencias:")
    print("  python -m pytest")
    print("  python -m uvicorn backend.app.main:app --reload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
