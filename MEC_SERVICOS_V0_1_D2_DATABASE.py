from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D2_DATABASE.py"
REVISION = "MEC-SERVICOS-V0.1-D2-DATABASE-2026-09-30"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D2_DATABASE_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D2_DATABASE.json"
BACKUP_ROOT = "_mec_backups"

EXPECTED_D1: Dict[str, str] = {'.env.example': 'MEC_APP_NAME=Plataforma de Serviços Mecânicos\n'
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
 'backend/app/api/router.py': 'from __future__ import annotations\n'
                              '\n'
                              'from fastapi import APIRouter\n'
                              '\n'
                              'from backend.app.api.routes.health import router as health_router\n'
                              '\n'
                              'api_router = APIRouter()\n'
                              'api_router.include_router(health_router)\n',
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
 'backend/app/database/__init__.py': '"""Infraestrutura de banco de dados. Será implementada em V0.1 D2."""\n',
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
 'requirements.txt': 'fastapi>=0.115,<1.0\n'
                     'uvicorn[standard]>=0.32,<1.0\n'
                     'pydantic-settings>=2.7,<3.0\n'
                     'pytest>=8.3,<9.0\n'
                     'httpx>=0.28,<1.0\n',
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
TARGET_FILES: Dict[str, str] = {'.env.example': 'MEC_APP_NAME=Plataforma de Serviços Mecânicos\n'
                 'MEC_APP_VERSION=0.1.0\n'
                 'MEC_ENVIRONMENT=development\n'
                 'MEC_API_V1_PREFIX=/api/v1\n'
                 'MEC_DEBUG=true\n'
                 'MEC_DATABASE_URL=sqlite:///./data/mec_servicos.db\n',
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
               'data/*.db\n'
               'data/*.sqlite\n'
               'data/*.sqlite3\n'
               '\n'
               '# Build artifacts\n'
               'build/\n'
               'dist/\n'
               '*.egg-info/\n',
 'backend/app/api/router.py': 'from __future__ import annotations\n'
                              '\n'
                              'from fastapi import APIRouter\n'
                              '\n'
                              'from backend.app.api.routes.database import router as database_router\n'
                              'from backend.app.api.routes.health import router as health_router\n'
                              '\n'
                              'api_router = APIRouter()\n'
                              'api_router.include_router(health_router)\n'
                              'api_router.include_router(database_router)\n',
 'backend/app/api/routes/database.py': 'from __future__ import annotations\n'
                                       '\n'
                                       'from fastapi import APIRouter, Depends, HTTPException\n'
                                       'from sqlalchemy import text\n'
                                       'from sqlalchemy.exc import SQLAlchemyError\n'
                                       'from sqlalchemy.orm import Session\n'
                                       '\n'
                                       'from backend.app.database.session import get_db\n'
                                       '\n'
                                       'router = APIRouter(tags=["database"])\n'
                                       '\n'
                                       '\n'
                                       '@router.get("/database/health")\n'
                                       'def database_health(db: Session = Depends(get_db)) -> dict[str, str]:\n'
                                       '    try:\n'
                                       '        value = db.execute(text("SELECT 1")).scalar_one()\n'
                                       '    except SQLAlchemyError as exc:\n'
                                       '        raise HTTPException(\n'
                                       '            status_code=503,\n'
                                       '            detail="database_unavailable",\n'
                                       '        ) from exc\n'
                                       '\n'
                                       '    return {\n'
                                       '        "status": "ok",\n'
                                       '        "database": "connected",\n'
                                       '        "probe": str(value),\n'
                                       '    }\n',
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
                               '    database_url: str = "sqlite:///./data/mec_servicos.db"\n'
                               '\n'
                               '    model_config = SettingsConfigDict(\n'
                               '        env_file=".env",\n'
                               '        env_prefix="MEC_",\n'
                               '        extra="ignore",\n'
                               '    )\n'
                               '\n'
                               '\n'
                               'settings = Settings()\n',
 'backend/app/database/__init__.py': 'from backend.app.database.base import Base\n'
                                     'from backend.app.database.session import SessionLocal, engine, get_db\n'
                                     '\n'
                                     '__all__ = ["Base", "SessionLocal", "engine", "get_db"]\n',
 'backend/app/database/base.py': 'from __future__ import annotations\n'
                                 '\n'
                                 'from sqlalchemy.orm import DeclarativeBase\n'
                                 '\n'
                                 '\n'
                                 'class Base(DeclarativeBase):\n'
                                 '    pass\n',
 'backend/app/database/init_db.py': 'from __future__ import annotations\n'
                                    '\n'
                                    'from pathlib import Path\n'
                                    '\n'
                                    'from backend.app.core.config import settings\n'
                                    'from backend.app.database.base import Base\n'
                                    'from backend.app.database.session import engine\n'
                                    'from backend.app.models import Company  # noqa: F401\n'
                                    '\n'
                                    '\n'
                                    'def _ensure_sqlite_parent() -> None:\n'
                                    '    prefix = "sqlite:///"\n'
                                    '    if not settings.database_url.startswith(prefix):\n'
                                    '        return\n'
                                    '\n'
                                    '    raw_path = settings.database_url[len(prefix):]\n'
                                    '    if not raw_path or raw_path == ":memory:":\n'
                                    '        return\n'
                                    '\n'
                                    '    database_path = Path(raw_path)\n'
                                    '    if not database_path.is_absolute():\n'
                                    '        database_path = Path.cwd() / database_path\n'
                                    '    database_path.parent.mkdir(parents=True, exist_ok=True)\n'
                                    '\n'
                                    '\n'
                                    'def init_db() -> None:\n'
                                    '    _ensure_sqlite_parent()\n'
                                    '    Base.metadata.create_all(bind=engine)\n',
 'backend/app/database/session.py': 'from __future__ import annotations\n'
                                    '\n'
                                    'from collections.abc import Generator\n'
                                    '\n'
                                    'from sqlalchemy import create_engine\n'
                                    'from sqlalchemy.orm import Session, sessionmaker\n'
                                    '\n'
                                    'from backend.app.core.config import settings\n'
                                    '\n'
                                    '\n'
                                    'def _engine_kwargs(database_url: str) -> dict:\n'
                                    '    if database_url.startswith("sqlite"):\n'
                                    '        return {"connect_args": {"check_same_thread": False}}\n'
                                    '    return {}\n'
                                    '\n'
                                    '\n'
                                    'engine = create_engine(\n'
                                    '    settings.database_url,\n'
                                    '    pool_pre_ping=True,\n'
                                    '    **_engine_kwargs(settings.database_url),\n'
                                    ')\n'
                                    '\n'
                                    'SessionLocal = sessionmaker(\n'
                                    '    bind=engine,\n'
                                    '    autoflush=False,\n'
                                    '    expire_on_commit=False,\n'
                                    '    class_=Session,\n'
                                    ')\n'
                                    '\n'
                                    '\n'
                                    'def get_db() -> Generator[Session, None, None]:\n'
                                    '    db = SessionLocal()\n'
                                    '    try:\n'
                                    '        yield db\n'
                                    '    finally:\n'
                                    '        db.close()\n',
 'backend/app/main.py': 'from __future__ import annotations\n'
                        '\n'
                        'from contextlib import asynccontextmanager\n'
                        'from collections.abc import AsyncIterator\n'
                        '\n'
                        'from fastapi import FastAPI\n'
                        '\n'
                        'from backend.app.api.router import api_router\n'
                        'from backend.app.core.config import settings\n'
                        'from backend.app.database.init_db import init_db\n'
                        '\n'
                        '\n'
                        '@asynccontextmanager\n'
                        'async def lifespan(_: FastAPI) -> AsyncIterator[None]:\n'
                        '    init_db()\n'
                        '    yield\n'
                        '\n'
                        '\n'
                        'def create_app() -> FastAPI:\n'
                        '    application = FastAPI(\n'
                        '        title=settings.app_name,\n'
                        '        version=settings.app_version,\n'
                        '        debug=settings.debug,\n'
                        '        lifespan=lifespan,\n'
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
 'backend/app/models/__init__.py': 'from backend.app.models.company import Company\n\n__all__ = ["Company"]\n',
 'backend/app/models/company.py': 'from __future__ import annotations\n'
                                  '\n'
                                  'from datetime import datetime\n'
                                  '\n'
                                  'from sqlalchemy import CheckConstraint, DateTime, Float, String, func\n'
                                  'from sqlalchemy.orm import Mapped, mapped_column\n'
                                  '\n'
                                  'from backend.app.database.base import Base\n'
                                  '\n'
                                  '\n'
                                  'class Company(Base):\n'
                                  '    __tablename__ = "companies"\n'
                                  '    __table_args__ = (\n'
                                  '        CheckConstraint(\n'
                                  '            "company_type IN (\'client\', \'supplier\', \'both\')",\n'
                                  '            name="ck_companies_company_type",\n'
                                  '        ),\n'
                                  '        CheckConstraint(\n'
                                  '            "rating IS NULL OR (rating >= 0 AND rating <= 5)",\n'
                                  '            name="ck_companies_rating",\n'
                                  '        ),\n'
                                  '    )\n'
                                  '\n'
                                  '    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)\n'
                                  '    legal_name: Mapped[str] = mapped_column(String(200), nullable=False, '
                                  'index=True)\n'
                                  '    document: Mapped[str] = mapped_column(String(32), nullable=False, '
                                  'unique=True, index=True)\n'
                                  '    company_type: Mapped[str] = mapped_column(String(16), nullable=False)\n'
                                  '    rating: Mapped[float | None] = mapped_column(Float, nullable=True)\n'
                                  '    created_at: Mapped[datetime] = mapped_column(\n'
                                  '        DateTime(timezone=True),\n'
                                  '        server_default=func.now(),\n'
                                  '        nullable=False,\n'
                                  '    )\n'
                                  '    updated_at: Mapped[datetime] = mapped_column(\n'
                                  '        DateTime(timezone=True),\n'
                                  '        server_default=func.now(),\n'
                                  '        onupdate=func.now(),\n'
                                  '        nullable=False,\n'
                                  '    )\n'
                                  '\n'
                                  '    def __repr__(self) -> str:\n'
                                  '        return (\n'
                                  '            f"Company(id={self.id!r}, legal_name={self.legal_name!r}, "\n'
                                  '            f"document={self.document!r}, '
                                  'company_type={self.company_type!r})"\n'
                                  '        )\n',
 'data/.gitkeep': '',
 'requirements.txt': 'fastapi>=0.115,<1.0\n'
                     'uvicorn[standard]>=0.32,<1.0\n'
                     'pydantic-settings>=2.7,<3.0\n'
                     'sqlalchemy>=2.0,<3.0\n'
                     'pytest>=8.3,<9.0\n'
                     'httpx>=0.28,<1.0\n',
 'tests/test_database.py': 'from sqlalchemy import create_engine, select\n'
                           'from sqlalchemy.orm import Session\n'
                           'from sqlalchemy.pool import StaticPool\n'
                           '\n'
                           'from backend.app.database.base import Base\n'
                           'from backend.app.models.company import Company\n'
                           '\n'
                           '\n'
                           'def test_company_persistence_in_memory() -> None:\n'
                           '    engine = create_engine(\n'
                           '        "sqlite://",\n'
                           '        connect_args={"check_same_thread": False},\n'
                           '        poolclass=StaticPool,\n'
                           '    )\n'
                           '    Base.metadata.create_all(bind=engine)\n'
                           '\n'
                           '    with Session(engine) as session:\n'
                           '        company = Company(\n'
                           '            legal_name="Oficina Teste Ltda",\n'
                           '            document="TEST-DOC-0001",\n'
                           '            company_type="supplier",\n'
                           '        )\n'
                           '        session.add(company)\n'
                           '        session.commit()\n'
                           '        company_id = company.id\n'
                           '\n'
                           '    with Session(engine) as session:\n'
                           '        loaded = session.scalar(\n'
                           '            select(Company).where(Company.id == company_id)\n'
                           '        )\n'
                           '\n'
                           '        assert loaded is not None\n'
                           '        assert loaded.legal_name == "Oficina Teste Ltda"\n'
                           '        assert loaded.document == "TEST-DOC-0001"\n'
                           '        assert loaded.company_type == "supplier"\n'
                           '        assert loaded.rating is None\n',
 'tests/test_health.py': 'from fastapi.testclient import TestClient\n'
                         '\n'
                         'from backend.app.main import app\n'
                         '\n'
                         '\n'
                         'def test_root() -> None:\n'
                         '    with TestClient(app) as client:\n'
                         '        response = client.get("/")\n'
                         '    assert response.status_code == 200\n'
                         '    payload = response.json()\n'
                         '    assert payload["status"] == "running"\n'
                         '    assert payload["version"] == "0.1.0"\n'
                         '\n'
                         '\n'
                         'def test_health() -> None:\n'
                         '    with TestClient(app) as client:\n'
                         '        response = client.get("/api/v1/health")\n'
                         '    assert response.status_code == 200\n'
                         '    payload = response.json()\n'
                         '    assert payload["status"] == "ok"\n'
                         '    assert payload["version"] == "0.1.0"\n'
                         '\n'
                         '\n'
                         'def test_database_health() -> None:\n'
                         '    with TestClient(app) as client:\n'
                         '        response = client.get("/api/v1/database/health")\n'
                         '    assert response.status_code == 200\n'
                         '    payload = response.json()\n'
                         '    assert payload == {\n'
                         '        "status": "ok",\n'
                         '        "database": "connected",\n'
                         '        "probe": "1",\n'
                         '    }\n'}
REQUIRED_D1 = ['backend/app/api/routes/health.py',
 'backend/app/main.py',
 'backend/app/core/config.py',
 'tests/test_health.py',
 'requirements.txt',
 'pyproject.toml']


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
    return (root / "src" / "cgx").exists() or (root / "src" / "cgx_platform").exists()


def dependency_status() -> Dict[str, bool]:
    names = ["fastapi", "uvicorn", "pydantic_settings", "sqlalchemy", "pytest", "httpx"]
    return {name: importlib.util.find_spec(name) is not None for name in names}


def validate_python_files(root: Path, paths: List[str]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    for rel in paths:
        if not rel.endswith(".py"):
            continue
        path = root / rel
        if not path.exists():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    return (not errors, errors)


def main() -> int:
    root = Path.cwd().resolve()
    print(f"{PROJECT_LABEL} — V0.1 D2 Database")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    if is_cgx_root(root):
        print("ERRO: esta pasta parece ser a raiz do CGX Platform.")
        print("Execute este arquivo somente na raiz do projeto MEC-Servicos.")
        return 20

    missing_d1 = [rel for rel in REQUIRED_D1 if not (root / rel).exists()]
    if missing_d1:
        print("ERRO: baseline D1 incompleta. Arquivos ausentes:")
        for rel in missing_d1:
            print(f"  MISSING_D1: {rel}")
        return 21

    conflicts: List[str] = []
    already_target: List[str] = []
    eligible_updates: List[str] = []
    eligible_creates: List[str] = []

    for rel, target_content in TARGET_FILES.items():
        path = root / rel
        target_content = normalize(target_content)

        if not path.exists():
            eligible_creates.append(rel)
            continue

        current = normalize(path.read_text(encoding="utf-8"))
        if current == target_content:
            already_target.append(rel)
            continue

        expected = EXPECTED_D1.get(rel)
        if expected is not None and current == normalize(expected):
            eligible_updates.append(rel)
            continue

        conflicts.append(rel)

    if conflicts:
        print("ERRO: foram encontrados arquivos divergentes da baseline D1.")
        print("Nenhum arquivo foi alterado.")
        for rel in conflicts:
            print(f"  CONFLICT: {rel}")

        conflict_report = {
            "project": PROJECT_LABEL,
            "revision": REVISION,
            "status": "CONFLICT",
            "root": str(root),
            "conflicts": conflicts,
            "message": "Nenhum arquivo foi alterado.",
        }
        atomic_write(
            root / REPORT_JSON,
            json.dumps(conflict_report, indent=2, ensure_ascii=False) + "\n",
        )
        atomic_write(
            root / REPORT_TXT,
            "\n".join([
                f"{PROJECT_LABEL} — V0.1 D2 Database",
                f"REVISION={REVISION}",
                f"ROOT={root}",
                "STATUS=CONFLICT",
                "NO_FILES_CHANGED=True",
                "",
                "CONFLICTS:",
                *[f"  {item}" for item in conflicts],
                "",
            ]),
        )
        return 30

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / BACKUP_ROOT / f"V0_1_D2_DATABASE_{timestamp}"
    backed_up: List[str] = []

    if eligible_updates:
        for rel in eligible_updates:
            src = root / rel
            dst = backup_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            backed_up.append(rel)

    changed: List[str] = []
    for rel in eligible_updates + eligible_creates:
        atomic_write(root / rel, TARGET_FILES[rel])
        changed.append(rel)

    all_target_paths = sorted(TARGET_FILES.keys())
    missing_target = [rel for rel in all_target_paths if not (root / rel).exists()]
    content_mismatch = []
    for rel in all_target_paths:
        path = root / rel
        if not path.exists():
            continue
        current = normalize(path.read_text(encoding="utf-8"))
        if current != normalize(TARGET_FILES[rel]):
            content_mismatch.append(rel)

    ast_ok, ast_errors = validate_python_files(root, all_target_paths)
    files_ok = not missing_target and not content_mismatch
    deps = dependency_status()

    target_hashes = {}
    for rel in all_target_paths:
        path = root / rel
        if path.exists():
            target_hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))

    sqlalchemy_installed = deps.get("sqlalchemy", False)
    status = "OK" if files_ok and ast_ok else "FAILED"

    report = {
        "project": PROJECT_LABEL,
        "revision": REVISION,
        "script": SCRIPT_NAME,
        "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "status": status,
        "d1_baseline_present": True,
        "files_ok": files_ok,
        "ast_ok": ast_ok,
        "changed": changed,
        "already_target": already_target,
        "backed_up": backed_up,
        "backup_dir": str(backup_dir) if backed_up else None,
        "missing_target": missing_target,
        "content_mismatch": content_mismatch,
        "ast_errors": ast_errors,
        "dependencies_installed": deps,
        "sqlalchemy_installed": sqlalchemy_installed,
        "target_hashes_sha256": target_hashes,
        "database": {
            "development_engine": "SQLite",
            "default_url": "sqlite:///./data/mec_servicos.db",
            "first_model": "Company",
            "table": "companies",
            "startup_create_all": True,
        },
        "next_commands": [
            r"python -m pip install -r requirements.txt",
            r"python -m pytest",
            r"python -m uvicorn backend.app.main:app --reload",
        ],
    }

    atomic_write(
        root / REPORT_JSON,
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    )

    dep_lines = [
        f"  {name}={'INSTALLED' if installed else 'MISSING'}"
        for name, installed in deps.items()
    ]

    txt_lines = [
        f"{PROJECT_LABEL} — V0.1 D2 Database",
        f"REVISION={REVISION}",
        f"ROOT={root}",
        "",
        f"STATUS={status}",
        "D1_BASELINE_PRESENT=True",
        f"FILES_OK={files_ok}",
        f"AST_OK={ast_ok}",
        f"SQLALCHEMY_INSTALLED={sqlalchemy_installed}",
        f"CHANGED={len(changed)}",
        f"ALREADY_TARGET={len(already_target)}",
        f"BACKED_UP={len(backed_up)}",
        "",
        "CHANGED_FILES:",
        *([f"  {item}" for item in changed] or ["  (none)"]),
        "",
        "BACKED_UP_FILES:",
        *([f"  {item}" for item in backed_up] or ["  (none)"]),
        "",
        f"BACKUP_DIR={str(backup_dir) if backed_up else '(none)'}",
        "",
        "MISSING_TARGET:",
        *([f"  {item}" for item in missing_target] or ["  (none)"]),
        "",
        "CONTENT_MISMATCH:",
        *([f"  {item}" for item in content_mismatch] or ["  (none)"]),
        "",
        "AST_ERRORS:",
        *([f"  {item}" for item in ast_errors] or ["  (none)"]),
        "",
        "DEPENDENCIES:",
        *dep_lines,
        "",
        "DATABASE_BASELINE:",
        "  ENGINE=SQLite",
        "  URL=sqlite:///./data/mec_servicos.db",
        "  MODEL=Company",
        "  TABLE=companies",
        "",
        "NEXT:",
        "  1. python -m pip install -r requirements.txt",
        "  2. python -m pytest",
        "  3. python -m uvicorn backend.app.main:app --reload",
        "  4. Testar /api/v1/database/health",
        "",
        "OBSERVACAO:",
        "  SQLite e apenas o banco local desta etapa de desenvolvimento.",
        "  A camada foi separada para permitir PostgreSQL futuramente.",
        "",
    ]
    atomic_write(root / REPORT_TXT, "\n".join(txt_lines))

    print(f"FILES_OK= {files_ok}")
    print(f"AST_OK= {ast_ok}")
    print(f"SQLALCHEMY_INSTALLED= {sqlalchemy_installed}")
    print(f"CHANGED= {len(changed)}")
    print(f"BACKED_UP= {len(backed_up)}")
    if backed_up:
        print(f"BACKUP_DIR= {backup_dir}")
    print(f"REPORT= {root / REPORT_TXT}")
    print(f"JSON= {root / REPORT_JSON}")

    if not files_ok or not ast_ok:
        print("ERRO: a validacao estatica do D2 falhou.")
        return 40

    print("D2_DATABASE_APPLIED= True")
    if not sqlalchemy_installed:
        print("DEPENDENCY_ACTION_REQUIRED= True")
        print("Execute: python -m pip install -r requirements.txt")
    else:
        print("DEPENDENCY_ACTION_REQUIRED= False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
