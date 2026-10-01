from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D3_FIX2_PORTUGUES.py"
REVISION = "MEC-SERVICOS-V0.1-D3-FIX2-PORTUGUES-2026-09-30"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D3_FIX2_PORTUGUES_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D3_FIX2_PORTUGUES.json"
BACKUP_ROOT = "_mec_backups"

EXPECTED_D3: Dict[str, str] = {'.env.example': 'MEC_APP_NAME=Plataforma de Serviços Mecânicos\n'
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
 'README.md': '# Plataforma de Serviços Mecânicos\n'
              '\n'
              'Projeto independente para conectar clientes/projetistas e fornecedores de serviços mecânicos.\n'
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
              'Este projeto é independente do CGX Platform. Nesta fase não existe integração, dependência nem '
              'compartilhamento de código entre os dois.\n'
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
              'V0.1 D2: banco de dados e persistência inicial, mantendo o mesmo método incremental e versionado.\n',
 'backend/__init__.py': '"""Backend da Plataforma de Serviços Mecânicos."""\n',
 'backend/app/__init__.py': '"""Aplicação principal."""\n',
 'backend/app/api/__init__.py': '"""Camada de API."""\n',
 'backend/app/api/router.py': 'from __future__ import annotations\n'
                              '\n'
                              'from fastapi import APIRouter\n'
                              '\n'
                              'from backend.app.api.routes.companies import router as companies_router\n'
                              'from backend.app.api.routes.database import router as database_router\n'
                              'from backend.app.api.routes.health import router as health_router\n'
                              '\n'
                              'api_router = APIRouter()\n'
                              'api_router.include_router(health_router)\n'
                              'api_router.include_router(database_router)\n'
                              'api_router.include_router(companies_router)\n',
 'backend/app/api/routes/__init__.py': '"""Rotas HTTP da API."""\n',
 'backend/app/api/routes/companies.py': 'from __future__ import annotations\n'
                                        '\n'
                                        'from typing import Annotated\n'
                                        '\n'
                                        'from fastapi import APIRouter, Depends, HTTPException, Query, status\n'
                                        'from sqlalchemy.orm import Session\n'
                                        '\n'
                                        'from backend.app.database.session import get_db\n'
                                        'from backend.app.schemas.company import CompanyCreate, CompanyRead\n'
                                        'from backend.app.services.company import (\n'
                                        '    CompanyNotFoundError,\n'
                                        '    CompanyService,\n'
                                        '    DuplicateCompanyDocumentError,\n'
                                        ')\n'
                                        '\n'
                                        'router = APIRouter(prefix="/companies", tags=["companies"])\n'
                                        'DbSession = Annotated[Session, Depends(get_db)]\n'
                                        '\n'
                                        '\n'
                                        '@router.post("", response_model=CompanyRead, '
                                        'status_code=status.HTTP_201_CREATED)\n'
                                        'def create_company(payload: CompanyCreate, db: DbSession) -> CompanyRead:\n'
                                        '    service = CompanyService(db)\n'
                                        '    try:\n'
                                        '        company = service.create(payload)\n'
                                        '    except DuplicateCompanyDocumentError as exc:\n'
                                        '        raise HTTPException(\n'
                                        '            status_code=status.HTTP_409_CONFLICT,\n'
                                        '            detail="company_document_already_registered",\n'
                                        '        ) from exc\n'
                                        '    return CompanyRead.model_validate(company)\n'
                                        '\n'
                                        '\n'
                                        '@router.get("", response_model=list[CompanyRead])\n'
                                        'def list_companies(\n'
                                        '    db: DbSession,\n'
                                        '    offset: int = Query(default=0, ge=0),\n'
                                        '    limit: int = Query(default=100, ge=1, le=200),\n'
                                        ') -> list[CompanyRead]:\n'
                                        '    service = CompanyService(db)\n'
                                        '    return [\n'
                                        '        CompanyRead.model_validate(company)\n'
                                        '        for company in service.list(offset=offset, limit=limit)\n'
                                        '    ]\n'
                                        '\n'
                                        '\n'
                                        '@router.get("/{company_id}", response_model=CompanyRead)\n'
                                        'def get_company(company_id: int, db: DbSession) -> CompanyRead:\n'
                                        '    service = CompanyService(db)\n'
                                        '    try:\n'
                                        '        company = service.get(company_id)\n'
                                        '    except CompanyNotFoundError as exc:\n'
                                        '        raise HTTPException(\n'
                                        '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                        '            detail="company_not_found",\n'
                                        '        ) from exc\n'
                                        '    return CompanyRead.model_validate(company)\n',
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
                                  '    document: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, '
                                  'index=True)\n'
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
                                  '            f"document={self.document!r}, company_type={self.company_type!r})"\n'
                                  '        )\n',
 'backend/app/repositories/__init__.py': 'from backend.app.repositories.company import CompanyRepository\n'
                                         '\n'
                                         '__all__ = ["CompanyRepository"]\n',
 'backend/app/repositories/company.py': 'from __future__ import annotations\n'
                                        '\n'
                                        'from sqlalchemy import select\n'
                                        'from sqlalchemy.orm import Session\n'
                                        '\n'
                                        'from backend.app.models.company import Company\n'
                                        'from backend.app.schemas.company import CompanyCreate\n'
                                        '\n'
                                        '\n'
                                        'class CompanyRepository:\n'
                                        '    def __init__(self, db: Session) -> None:\n'
                                        '        self.db = db\n'
                                        '\n'
                                        '    def get_by_id(self, company_id: int) -> Company | None:\n'
                                        '        return self.db.get(Company, company_id)\n'
                                        '\n'
                                        '    def get_by_document(self, document: str) -> Company | None:\n'
                                        '        statement = select(Company).where(Company.document == document)\n'
                                        '        return self.db.scalar(statement)\n'
                                        '\n'
                                        '    def list(self, *, offset: int = 0, limit: int = 100) -> list[Company]:\n'
                                        '        statement = (\n'
                                        '            select(Company)\n'
                                        '            .order_by(Company.id)\n'
                                        '            .offset(offset)\n'
                                        '            .limit(limit)\n'
                                        '        )\n'
                                        '        return list(self.db.scalars(statement).all())\n'
                                        '\n'
                                        '    def create(self, data: CompanyCreate) -> Company:\n'
                                        '        company = Company(\n'
                                        '            legal_name=data.legal_name,\n'
                                        '            document=data.document,\n'
                                        '            company_type=data.company_type.value,\n'
                                        '        )\n'
                                        '        self.db.add(company)\n'
                                        '        self.db.commit()\n'
                                        '        self.db.refresh(company)\n'
                                        '        return company\n',
 'backend/app/schemas/__init__.py': 'from backend.app.schemas.company import CompanyCreate, CompanyRead, CompanyType\n'
                                    '\n'
                                    '__all__ = ["CompanyCreate", "CompanyRead", "CompanyType"]\n',
 'backend/app/schemas/company.py': 'from __future__ import annotations\n'
                                   '\n'
                                   'import re\n'
                                   'from datetime import datetime\n'
                                   'from enum import Enum\n'
                                   '\n'
                                   'from pydantic import BaseModel, ConfigDict, Field, field_validator\n'
                                   '\n'
                                   '\n'
                                   'class CompanyType(str, Enum):\n'
                                   '    CLIENT = "client"\n'
                                   '    SUPPLIER = "supplier"\n'
                                   '    BOTH = "both"\n'
                                   '\n'
                                   '\n'
                                   'def normalize_document(value: str) -> str:\n'
                                   '    digits = re.sub(r"\\D", "", value or "")\n'
                                   '    if len(digits) not in (11, 14):\n'
                                   '        raise ValueError("document must contain 11 digits (CPF) or 14 digits '
                                   '(CNPJ)")\n'
                                   '    return digits\n'
                                   '\n'
                                   '\n'
                                   'class CompanyCreate(BaseModel):\n'
                                   '    legal_name: str = Field(min_length=2, max_length=200)\n'
                                   '    document: str\n'
                                   '    company_type: CompanyType\n'
                                   '\n'
                                   '    @field_validator("legal_name")\n'
                                   '    @classmethod\n'
                                   '    def clean_legal_name(cls, value: str) -> str:\n'
                                   '        cleaned = " ".join(value.split())\n'
                                   '        if len(cleaned) < 2:\n'
                                   '            raise ValueError("legal_name is too short")\n'
                                   '        return cleaned\n'
                                   '\n'
                                   '    @field_validator("document")\n'
                                   '    @classmethod\n'
                                   '    def clean_document(cls, value: str) -> str:\n'
                                   '        return normalize_document(value)\n'
                                   '\n'
                                   '\n'
                                   'class CompanyRead(BaseModel):\n'
                                   '    model_config = ConfigDict(from_attributes=True)\n'
                                   '\n'
                                   '    id: int\n'
                                   '    legal_name: str\n'
                                   '    document: str\n'
                                   '    company_type: CompanyType\n'
                                   '    rating: float | None\n'
                                   '    created_at: datetime\n'
                                   '    updated_at: datetime\n',
 'backend/app/services/__init__.py': 'from backend.app.services.company import (\n'
                                     '    CompanyNotFoundError,\n'
                                     '    CompanyService,\n'
                                     '    DuplicateCompanyDocumentError,\n'
                                     ')\n'
                                     '\n'
                                     '__all__ = [\n'
                                     '    "CompanyNotFoundError",\n'
                                     '    "CompanyService",\n'
                                     '    "DuplicateCompanyDocumentError",\n'
                                     ']\n',
 'backend/app/services/company.py': 'from __future__ import annotations\n'
                                    '\n'
                                    'from sqlalchemy.exc import IntegrityError\n'
                                    'from sqlalchemy.orm import Session\n'
                                    '\n'
                                    'from backend.app.models.company import Company\n'
                                    'from backend.app.repositories.company import CompanyRepository\n'
                                    'from backend.app.schemas.company import CompanyCreate\n'
                                    '\n'
                                    '\n'
                                    'class CompanyNotFoundError(LookupError):\n'
                                    '    pass\n'
                                    '\n'
                                    '\n'
                                    'class DuplicateCompanyDocumentError(ValueError):\n'
                                    '    pass\n'
                                    '\n'
                                    '\n'
                                    'class CompanyService:\n'
                                    '    def __init__(self, db: Session) -> None:\n'
                                    '        self.repository = CompanyRepository(db)\n'
                                    '\n'
                                    '    def create(self, data: CompanyCreate) -> Company:\n'
                                    '        if self.repository.get_by_document(data.document) is not None:\n'
                                    '            raise DuplicateCompanyDocumentError(data.document)\n'
                                    '\n'
                                    '        try:\n'
                                    '            return self.repository.create(data)\n'
                                    '        except IntegrityError as exc:\n'
                                    '            self.repository.db.rollback()\n'
                                    '            raise DuplicateCompanyDocumentError(data.document) from exc\n'
                                    '\n'
                                    '    def get(self, company_id: int) -> Company:\n'
                                    '        company = self.repository.get_by_id(company_id)\n'
                                    '        if company is None:\n'
                                    '            raise CompanyNotFoundError(company_id)\n'
                                    '        return company\n'
                                    '\n'
                                    '    def list(self, *, offset: int = 0, limit: int = 100) -> list[Company]:\n'
                                    '        return self.repository.list(offset=offset, limit=limit)\n',
 'data/.gitkeep': '',
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
                     'sqlalchemy>=2.0,<3.0\n'
                     'pytest>=8.3,<9.0\n'
                     'httpx>=0.28,<1.0\n',
 'tests/__init__.py': '"""Testes automatizados."""\n',
 'tests/test_companies_api.py': 'from collections.abc import Generator\n'
                                '\n'
                                'import pytest\n'
                                'from fastapi.testclient import TestClient\n'
                                'from sqlalchemy import create_engine\n'
                                'from sqlalchemy.orm import Session, sessionmaker\n'
                                'from sqlalchemy.pool import StaticPool\n'
                                '\n'
                                'from backend.app.database.base import Base\n'
                                'from backend.app.database.session import get_db\n'
                                'from backend.app.main import app\n'
                                '\n'
                                '\n'
                                '@pytest.fixture()\n'
                                'def client() -> Generator[TestClient, None, None]:\n'
                                '    engine = create_engine(\n'
                                '        "sqlite://",\n'
                                '        connect_args={"check_same_thread": False},\n'
                                '        poolclass=StaticPool,\n'
                                '    )\n'
                                '    TestingSessionLocal = sessionmaker(\n'
                                '        bind=engine,\n'
                                '        autoflush=False,\n'
                                '        expire_on_commit=False,\n'
                                '        class_=Session,\n'
                                '    )\n'
                                '    Base.metadata.create_all(bind=engine)\n'
                                '\n'
                                '    def override_get_db() -> Generator[Session, None, None]:\n'
                                '        db = TestingSessionLocal()\n'
                                '        try:\n'
                                '            yield db\n'
                                '        finally:\n'
                                '            db.close()\n'
                                '\n'
                                '    app.dependency_overrides[get_db] = override_get_db\n'
                                '    with TestClient(app) as test_client:\n'
                                '        yield test_client\n'
                                '    app.dependency_overrides.clear()\n'
                                '    Base.metadata.drop_all(bind=engine)\n'
                                '    engine.dispose()\n'
                                '\n'
                                '\n'
                                'def test_create_list_and_get_company(client: TestClient) -> None:\n'
                                '    create_response = client.post(\n'
                                '        "/api/v1/companies",\n'
                                '        json={\n'
                                '            "legal_name": "Oficina Paraná Ltda",\n'
                                '            "document": "12.345.678/0001-90",\n'
                                '            "company_type": "supplier",\n'
                                '        },\n'
                                '    )\n'
                                '    assert create_response.status_code == 201\n'
                                '    created = create_response.json()\n'
                                '    assert created["id"] == 1\n'
                                '    assert created["legal_name"] == "Oficina Paraná Ltda"\n'
                                '    assert created["document"] == "12345678000190"\n'
                                '    assert created["company_type"] == "supplier"\n'
                                '    assert created["rating"] is None\n'
                                '\n'
                                '    list_response = client.get("/api/v1/companies")\n'
                                '    assert list_response.status_code == 200\n'
                                '    listed = list_response.json()\n'
                                '    assert len(listed) == 1\n'
                                '    assert listed[0]["id"] == created["id"]\n'
                                '\n'
                                '    get_response = client.get(f"/api/v1/companies/{created[\'id\']}")\n'
                                '    assert get_response.status_code == 200\n'
                                '    assert get_response.json()["document"] == "12345678000190"\n'
                                '\n'
                                '\n'
                                'def test_duplicate_document_returns_409(client: TestClient) -> None:\n'
                                '    payload = {\n'
                                '        "legal_name": "Fornecedor A Ltda",\n'
                                '        "document": "12345678901",\n'
                                '        "company_type": "supplier",\n'
                                '    }\n'
                                '    first = client.post("/api/v1/companies", json=payload)\n'
                                '    second = client.post("/api/v1/companies", json=payload)\n'
                                '\n'
                                '    assert first.status_code == 201\n'
                                '    assert second.status_code == 409\n'
                                '    assert second.json()["detail"] == "company_document_already_registered"\n'
                                '\n'
                                '\n'
                                'def test_invalid_document_returns_422(client: TestClient) -> None:\n'
                                '    response = client.post(\n'
                                '        "/api/v1/companies",\n'
                                '        json={\n'
                                '            "legal_name": "Cliente Teste",\n'
                                '            "document": "123",\n'
                                '            "company_type": "client",\n'
                                '        },\n'
                                '    )\n'
                                '    assert response.status_code == 422\n'
                                '\n'
                                '\n'
                                'def test_invalid_company_type_returns_422(client: TestClient) -> None:\n'
                                '    response = client.post(\n'
                                '        "/api/v1/companies",\n'
                                '        json={\n'
                                '            "legal_name": "Cliente Teste",\n'
                                '            "document": "12345678901",\n'
                                '            "company_type": "invalid",\n'
                                '        },\n'
                                '    )\n'
                                '    assert response.status_code == 422\n'
                                '\n'
                                '\n'
                                'def test_company_not_found_returns_404(client: TestClient) -> None:\n'
                                '    response = client.get("/api/v1/companies/999")\n'
                                '    assert response.status_code == 404\n'
                                '    assert response.json()["detail"] == "company_not_found"\n',
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
TARGET_FILES: Dict[str, str] = {'.env.example': 'MEC_NOME_APLICACAO=Plataforma de Serviços Mecânicos\n'
                 'MEC_VERSAO_APLICACAO=0.1.0\n'
                 'MEC_AMBIENTE=desenvolvimento\n'
                 'MEC_PREFIXO_API=/api/v1\n'
                 'MEC_MODO_DEBUG=true\n'
                 'MEC_URL_BANCO_DADOS=sqlite:///./data/mec_servicos.db\n',
 '.gitignore': '# Python\n'
               '__pycache__/\n'
               '*.py[cod]\n'
               '*$py.class\n'
               '*.so\n'
               '\n'
               '# Ambientes virtuais\n'
               '.venv/\n'
               'venv/\n'
               'env/\n'
               '\n'
               '# Testes e ferramentas\n'
               '.pytest_cache/\n'
               '.coverage\n'
               'htmlcov/\n'
               '.mypy_cache/\n'
               '.ruff_cache/\n'
               '\n'
               '# Ambiente e segredos\n'
               '.env\n'
               '.env.*\n'
               '!.env.example\n'
               '\n'
               '# IDE e sistema operacional\n'
               '.vscode/\n'
               '.idea/\n'
               '.DS_Store\n'
               'Thumbs.db\n'
               '\n'
               '# Dados e execução local\n'
               'storage/\n'
               'uploads/\n'
               'logs/\n'
               'data/*.db\n'
               'data/*.sqlite\n'
               'data/*.sqlite3\n'
               '\n'
               '# Artefatos de compilação\n'
               'build/\n'
               'dist/\n'
               '*.egg-info/\n',
 'README.md': '# Plataforma de Serviços Mecânicos\n'
              '\n'
              'Projeto independente para conectar clientes e fornecedores de serviços mecânicos.\n'
              '\n'
              '## Regra de idioma\n'
              '\n'
              'A aplicação é desenvolvida em português: interface, documentação, mensagens,\n'
              'validações, nomes do domínio e módulos específicos da aplicação.\n'
              '\n'
              'Nomes de tecnologias externas, como Python, FastAPI, SQLAlchemy, SQLite e Uvicorn,\n'
              'permanecem com seus nomes oficiais.\n'
              '\n'
              '## Estado\n'
              '\n'
              '**V0.1 D3 FIX1 — Português**\n'
              '\n'
              'Nesta etapa os componentes do D3 foram traduzidos para português, preservando os\n'
              'dados existentes no banco local.\n'
              '\n'
              '## Executar\n'
              '\n'
              '```powershell\n'
              'python -m pytest\n'
              'python -m uvicorn backend.app.principal:app --reload\n'
              '```\n'
              '\n'
              'Endpoints principais:\n'
              '\n'
              '- `http://127.0.0.1:8000/`\n'
              '- `http://127.0.0.1:8000/api/v1/saude`\n'
              '- `http://127.0.0.1:8000/api/v1/banco-dados/saude`\n'
              '- `http://127.0.0.1:8000/api/v1/empresas`\n'
              '- `http://127.0.0.1:8000/docs`\n'
              '\n'
              'O projeto continua independente do CGX Platform.\n',
 'backend/__init__.py': '"""Backend técnico da Plataforma de Serviços Mecânicos."""\n',
 'backend/app/__init__.py': '"""Aplicação da Plataforma de Serviços Mecânicos."""\n',
 'backend/app/api/__init__.py': '"""Interface de programação da aplicação."""\n',
 'backend/app/api/rotas/__init__.py': '"""Rotas HTTP da aplicação."""\n',
 'backend/app/api/rotas/banco_dados.py': 'from __future__ import annotations\n'
                                         '\n'
                                         'from fastapi import APIRouter, Depends, HTTPException\n'
                                         'from sqlalchemy import text\n'
                                         'from sqlalchemy.exc import SQLAlchemyError\n'
                                         'from sqlalchemy.orm import Session\n'
                                         '\n'
                                         'from backend.app.database.sessao import obter_banco\n'
                                         '\n'
                                         'roteador = APIRouter(tags=["banco de dados"])\n'
                                         '\n'
                                         '\n'
                                         '@roteador.get("/banco-dados/saude")\n'
                                         'def saude_banco(banco: Session = Depends(obter_banco)) -> dict[str, str]:\n'
                                         '    try:\n'
                                         '        valor = banco.execute(text("SELECT 1")).scalar_one()\n'
                                         '    except SQLAlchemyError as exc:\n'
                                         '        raise HTTPException(\n'
                                         '            status_code=503,\n'
                                         '            detail="banco_de_dados_indisponivel",\n'
                                         '        ) from exc\n'
                                         '\n'
                                         '    return {\n'
                                         '        "status": "ok",\n'
                                         '        "banco": "conectado",\n'
                                         '        "sondagem": str(valor),\n'
                                         '    }\n',
 'backend/app/api/rotas/empresas.py': 'from __future__ import annotations\n'
                                      '\n'
                                      'from typing import Annotated\n'
                                      '\n'
                                      'from fastapi import APIRouter, Depends, HTTPException, Query, status\n'
                                      'from sqlalchemy.orm import Session\n'
                                      '\n'
                                      'from backend.app.database.sessao import obter_banco\n'
                                      'from backend.app.schemas.empresa import EmpresaCriacao, EmpresaLeitura\n'
                                      'from backend.app.services.empresa import (\n'
                                      '    DocumentoEmpresaDuplicado,\n'
                                      '    EmpresaNaoEncontrada,\n'
                                      '    ServicoEmpresa,\n'
                                      ')\n'
                                      '\n'
                                      'roteador = APIRouter(prefix="/empresas", tags=["empresas"])\n'
                                      'SessaoBanco = Annotated[Session, Depends(obter_banco)]\n'
                                      '\n'
                                      '\n'
                                      '@roteador.post("", response_model=EmpresaLeitura, '
                                      'status_code=status.HTTP_201_CREATED)\n'
                                      'def criar_empresa(\n'
                                      '    dados: EmpresaCriacao,\n'
                                      '    banco: SessaoBanco,\n'
                                      ') -> EmpresaLeitura:\n'
                                      '    servico = ServicoEmpresa(banco)\n'
                                      '    try:\n'
                                      '        empresa = servico.criar(dados)\n'
                                      '    except DocumentoEmpresaDuplicado as exc:\n'
                                      '        raise HTTPException(\n'
                                      '            status_code=status.HTTP_409_CONFLICT,\n'
                                      '            detail="documento_da_empresa_ja_cadastrado",\n'
                                      '        ) from exc\n'
                                      '    return EmpresaLeitura.model_validate(empresa)\n'
                                      '\n'
                                      '\n'
                                      '@roteador.get("", response_model=list[EmpresaLeitura])\n'
                                      'def listar_empresas(\n'
                                      '    banco: SessaoBanco,\n'
                                      '    deslocamento: int = Query(default=0, ge=0),\n'
                                      '    limite: int = Query(default=100, ge=1, le=200),\n'
                                      ') -> list[EmpresaLeitura]:\n'
                                      '    servico = ServicoEmpresa(banco)\n'
                                      '    return [\n'
                                      '        EmpresaLeitura.model_validate(empresa)\n'
                                      '        for empresa in servico.listar(\n'
                                      '            deslocamento=deslocamento,\n'
                                      '            limite=limite,\n'
                                      '        )\n'
                                      '    ]\n'
                                      '\n'
                                      '\n'
                                      '@roteador.get("/{empresa_id}", response_model=EmpresaLeitura)\n'
                                      'def obter_empresa(\n'
                                      '    empresa_id: int,\n'
                                      '    banco: SessaoBanco,\n'
                                      ') -> EmpresaLeitura:\n'
                                      '    servico = ServicoEmpresa(banco)\n'
                                      '    try:\n'
                                      '        empresa = servico.obter(empresa_id)\n'
                                      '    except EmpresaNaoEncontrada as exc:\n'
                                      '        raise HTTPException(\n'
                                      '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                      '            detail="empresa_nao_encontrada",\n'
                                      '        ) from exc\n'
                                      '    return EmpresaLeitura.model_validate(empresa)\n',
 'backend/app/api/rotas/saude.py': 'from __future__ import annotations\n'
                                   '\n'
                                   'from fastapi import APIRouter\n'
                                   '\n'
                                   'from backend.app.core.configuracao import configuracoes\n'
                                   '\n'
                                   'roteador = APIRouter(tags=["sistema"])\n'
                                   '\n'
                                   '\n'
                                   '@roteador.get("/saude")\n'
                                   'async def saude() -> dict[str, str]:\n'
                                   '    return {\n'
                                   '        "status": "ok",\n'
                                   '        "servico": configuracoes.nome_aplicacao,\n'
                                   '        "versao": configuracoes.versao_aplicacao,\n'
                                   '    }\n',
 'backend/app/api/roteador.py': 'from __future__ import annotations\n'
                                '\n'
                                'from fastapi import APIRouter\n'
                                '\n'
                                'from backend.app.api.rotas.banco_dados import roteador as roteador_banco\n'
                                'from backend.app.api.rotas.empresas import roteador as roteador_empresas\n'
                                'from backend.app.api.rotas.saude import roteador as roteador_saude\n'
                                '\n'
                                'roteador_api = APIRouter()\n'
                                'roteador_api.include_router(roteador_saude)\n'
                                'roteador_api.include_router(roteador_banco)\n'
                                'roteador_api.include_router(roteador_empresas)\n',
 'backend/app/auth/__init__.py': '"""Autenticação e autorização."""\n',
 'backend/app/core/__init__.py': '"""Configurações e infraestrutura central."""\n',
 'backend/app/core/configuracao.py': 'from __future__ import annotations\n'
                                     '\n'
                                     'from pydantic_settings import BaseSettings, SettingsConfigDict\n'
                                     '\n'
                                     '\n'
                                     'class Configuracoes(BaseSettings):\n'
                                     '    nome_aplicacao: str = "Plataforma de Serviços Mecânicos"\n'
                                     '    versao_aplicacao: str = "0.1.0"\n'
                                     '    ambiente: str = "desenvolvimento"\n'
                                     '    prefixo_api: str = "/api/v1"\n'
                                     '    modo_debug: bool = True\n'
                                     '    url_banco_dados: str = "sqlite:///./data/mec_servicos.db"\n'
                                     '\n'
                                     '    model_config = SettingsConfigDict(\n'
                                     '        env_file=".env",\n'
                                     '        env_prefix="MEC_",\n'
                                     '        extra="ignore",\n'
                                     '    )\n'
                                     '\n'
                                     '\n'
                                     'configuracoes = Configuracoes()\n',
 'backend/app/database/__init__.py': 'from backend.app.database.base import Base\n'
                                     'from backend.app.database.sessao import SessaoLocal, engine, obter_banco\n'
                                     '\n'
                                     '__all__ = ["Base", "SessaoLocal", "engine", "obter_banco"]\n',
 'backend/app/database/base.py': 'from __future__ import annotations\n'
                                 '\n'
                                 'from sqlalchemy.orm import DeclarativeBase\n'
                                 '\n'
                                 '\n'
                                 'class Base(DeclarativeBase):\n'
                                 '    pass\n',
 'backend/app/database/inicializacao.py': 'from __future__ import annotations\n'
                                          '\n'
                                          'from pathlib import Path\n'
                                          '\n'
                                          'from sqlalchemy import inspect, text\n'
                                          '\n'
                                          'from backend.app.core.configuracao import configuracoes\n'
                                          'from backend.app.database.base import Base\n'
                                          'from backend.app.database.sessao import engine\n'
                                          'from backend.app.models import Empresa\n'
                                          '\n'
                                          '\n'
                                          'def _garantir_pasta_sqlite() -> None:\n'
                                          '    prefixo = "sqlite:///"\n'
                                          '    if not configuracoes.url_banco_dados.startswith(prefixo):\n'
                                          '        return\n'
                                          '\n'
                                          '    caminho_bruto = configuracoes.url_banco_dados[len(prefixo):]\n'
                                          '    if not caminho_bruto or caminho_bruto == ":memory:":\n'
                                          '        return\n'
                                          '\n'
                                          '    caminho = Path(caminho_bruto)\n'
                                          '    if not caminho.is_absolute():\n'
                                          '        caminho = Path.cwd() / caminho\n'
                                          '    caminho.parent.mkdir(parents=True, exist_ok=True)\n'
                                          '\n'
                                          '\n'
                                          'def _migrar_companies_para_empresas() -> None:\n'
                                          '    if not configuracoes.url_banco_dados.startswith("sqlite"):\n'
                                          '        return\n'
                                          '\n'
                                          '    inspetor = inspect(engine)\n'
                                          '    tabelas = set(inspetor.get_table_names())\n'
                                          '\n'
                                          '    if "empresas" in tabelas and "companies" in tabelas:\n'
                                          '        raise RuntimeError(\n'
                                          '            "Banco em estado ambíguo: as tabelas \'companies\' e '
                                          '\'empresas\' existem simultaneamente."\n'
                                          '        )\n'
                                          '\n'
                                          '    if "companies" not in tabelas:\n'
                                          '        return\n'
                                          '\n'
                                          '    colunas = {coluna["name"] for coluna in '
                                          'inspetor.get_columns("companies")}\n'
                                          '    esperadas = {\n'
                                          '        "id",\n'
                                          '        "legal_name",\n'
                                          '        "document",\n'
                                          '        "company_type",\n'
                                          '        "rating",\n'
                                          '        "created_at",\n'
                                          '        "updated_at",\n'
                                          '    }\n'
                                          '    ausentes = esperadas - colunas\n'
                                          '    if ausentes:\n'
                                          '        raise RuntimeError(\n'
                                          '            "A tabela legada \'companies\' não possui as colunas esperadas: '
                                          '"\n'
                                          '            + ", ".join(sorted(ausentes))\n'
                                          '        )\n'
                                          '\n'
                                          '    with engine.begin() as conexao:\n'
                                          '        tipos_invalidos = conexao.execute(\n'
                                          '            text(\n'
                                          '                """\n'
                                          '                SELECT DISTINCT company_type\n'
                                          '                FROM companies\n'
                                          "                WHERE company_type NOT IN ('client', 'supplier', 'both')\n"
                                          '                """\n'
                                          '            )\n'
                                          '        ).scalars().all()\n'
                                          '\n'
                                          '        if tipos_invalidos:\n'
                                          '            raise RuntimeError(\n'
                                          '                "A tabela legada \'companies\' possui tipos de empresa '
                                          'desconhecidos: "\n'
                                          '                + ", ".join(str(valor) for valor in tipos_invalidos)\n'
                                          '            )\n'
                                          '\n'
                                          '        conexao.execute(\n'
                                          '            text(\n'
                                          '                """\n'
                                          '                CREATE TABLE empresas (\n'
                                          '                    id INTEGER PRIMARY KEY,\n'
                                          '                    razao_social VARCHAR(200) NOT NULL,\n'
                                          '                    documento VARCHAR(32) NOT NULL UNIQUE,\n'
                                          '                    tipo_empresa VARCHAR(16) NOT NULL\n'
                                          "                        CHECK (tipo_empresa IN ('cliente', 'fornecedor', "
                                          "'ambos')),\n"
                                          '                    avaliacao FLOAT,\n'
                                          '                    criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,\n'
                                          '                    atualizado_em DATETIME NOT NULL DEFAULT '
                                          'CURRENT_TIMESTAMP,\n'
                                          '                    CONSTRAINT ck_empresas_avaliacao\n'
                                          '                        CHECK (avaliacao IS NULL OR (avaliacao >= 0 AND '
                                          'avaliacao <= 5))\n'
                                          '                )\n'
                                          '                """\n'
                                          '            )\n'
                                          '        )\n'
                                          '\n'
                                          '        conexao.execute(\n'
                                          '            text(\n'
                                          '                """\n'
                                          '                INSERT INTO empresas (\n'
                                          '                    id,\n'
                                          '                    razao_social,\n'
                                          '                    documento,\n'
                                          '                    tipo_empresa,\n'
                                          '                    avaliacao,\n'
                                          '                    criado_em,\n'
                                          '                    atualizado_em\n'
                                          '                )\n'
                                          '                SELECT\n'
                                          '                    id,\n'
                                          '                    legal_name,\n'
                                          '                    document,\n'
                                          '                    CASE company_type\n'
                                          "                        WHEN 'client' THEN 'cliente'\n"
                                          "                        WHEN 'supplier' THEN 'fornecedor'\n"
                                          "                        WHEN 'both' THEN 'ambos'\n"
                                          '                    END,\n'
                                          '                    rating,\n'
                                          '                    created_at,\n'
                                          '                    updated_at\n'
                                          '                FROM companies\n'
                                          '                """\n'
                                          '            )\n'
                                          '        )\n'
                                          '\n'
                                          '        conexao.execute(\n'
                                          '            text(\n'
                                          '                "CREATE INDEX IF NOT EXISTS ix_empresas_razao_social "\n'
                                          '                "ON empresas (razao_social)"\n'
                                          '            )\n'
                                          '        )\n'
                                          '        conexao.execute(text("DROP TABLE companies"))\n'
                                          '\n'
                                          '\n'
                                          'def inicializar_banco() -> None:\n'
                                          '    _garantir_pasta_sqlite()\n'
                                          '    _migrar_companies_para_empresas()\n'
                                          '    Base.metadata.create_all(bind=engine)\n',
 'backend/app/database/sessao.py': 'from __future__ import annotations\n'
                                   '\n'
                                   'from collections.abc import Generator\n'
                                   '\n'
                                   'from sqlalchemy import create_engine\n'
                                   'from sqlalchemy.orm import Session, sessionmaker\n'
                                   '\n'
                                   'from backend.app.core.configuracao import configuracoes\n'
                                   '\n'
                                   '\n'
                                   'def _argumentos_engine(url_banco: str) -> dict:\n'
                                   '    if url_banco.startswith("sqlite"):\n'
                                   '        return {"connect_args": {"check_same_thread": False}}\n'
                                   '    return {}\n'
                                   '\n'
                                   '\n'
                                   'engine = create_engine(\n'
                                   '    configuracoes.url_banco_dados,\n'
                                   '    pool_pre_ping=True,\n'
                                   '    **_argumentos_engine(configuracoes.url_banco_dados),\n'
                                   ')\n'
                                   '\n'
                                   'SessaoLocal = sessionmaker(\n'
                                   '    bind=engine,\n'
                                   '    autoflush=False,\n'
                                   '    expire_on_commit=False,\n'
                                   '    class_=Session,\n'
                                   ')\n'
                                   '\n'
                                   '\n'
                                   'def obter_banco() -> Generator[Session, None, None]:\n'
                                   '    banco = SessaoLocal()\n'
                                   '    try:\n'
                                   '        yield banco\n'
                                   '    finally:\n'
                                   '        banco.close()\n',
 'backend/app/models/__init__.py': 'from backend.app.models.empresa import Empresa\n\n__all__ = ["Empresa"]\n',
 'backend/app/models/empresa.py': 'from __future__ import annotations\n'
                                  '\n'
                                  'from datetime import datetime\n'
                                  '\n'
                                  'from sqlalchemy import CheckConstraint, DateTime, Float, String, func\n'
                                  'from sqlalchemy.orm import Mapped, mapped_column\n'
                                  '\n'
                                  'from backend.app.database.base import Base\n'
                                  '\n'
                                  '\n'
                                  'class Empresa(Base):\n'
                                  '    __tablename__ = "empresas"\n'
                                  '    __table_args__ = (\n'
                                  '        CheckConstraint(\n'
                                  '            "tipo_empresa IN (\'cliente\', \'fornecedor\', \'ambos\')",\n'
                                  '            name="ck_empresas_tipo_empresa",\n'
                                  '        ),\n'
                                  '        CheckConstraint(\n'
                                  '            "avaliacao IS NULL OR (avaliacao >= 0 AND avaliacao <= 5)",\n'
                                  '            name="ck_empresas_avaliacao",\n'
                                  '        ),\n'
                                  '    )\n'
                                  '\n'
                                  '    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)\n'
                                  '    razao_social: Mapped[str] = mapped_column(String(200), nullable=False, '
                                  'index=True)\n'
                                  '    documento: Mapped[str] = mapped_column(\n'
                                  '        String(32), nullable=False, unique=True\n'
                                  '    )\n'
                                  '    tipo_empresa: Mapped[str] = mapped_column(String(16), nullable=False)\n'
                                  '    avaliacao: Mapped[float | None] = mapped_column(Float, nullable=True)\n'
                                  '    criado_em: Mapped[datetime] = mapped_column(\n'
                                  '        DateTime(timezone=True),\n'
                                  '        server_default=func.now(),\n'
                                  '        nullable=False,\n'
                                  '    )\n'
                                  '    atualizado_em: Mapped[datetime] = mapped_column(\n'
                                  '        DateTime(timezone=True),\n'
                                  '        server_default=func.now(),\n'
                                  '        onupdate=func.now(),\n'
                                  '        nullable=False,\n'
                                  '    )\n'
                                  '\n'
                                  '    def __repr__(self) -> str:\n'
                                  '        return (\n'
                                  '            f"Empresa(id={self.id!r}, razao_social={self.razao_social!r}, "\n'
                                  '            f"documento={self.documento!r}, tipo_empresa={self.tipo_empresa!r})"\n'
                                  '        )\n',
 'backend/app/principal.py': 'from __future__ import annotations\n'
                             '\n'
                             'from collections.abc import AsyncIterator\n'
                             'from contextlib import asynccontextmanager\n'
                             '\n'
                             'from fastapi import FastAPI\n'
                             '\n'
                             'from backend.app.api.roteador import roteador_api\n'
                             'from backend.app.core.configuracao import configuracoes\n'
                             'from backend.app.database.inicializacao import inicializar_banco\n'
                             '\n'
                             '\n'
                             '@asynccontextmanager\n'
                             'async def ciclo_vida(_: FastAPI) -> AsyncIterator[None]:\n'
                             '    inicializar_banco()\n'
                             '    yield\n'
                             '\n'
                             '\n'
                             'def criar_aplicacao() -> FastAPI:\n'
                             '    aplicacao = FastAPI(\n'
                             '        title=configuracoes.nome_aplicacao,\n'
                             '        version=configuracoes.versao_aplicacao,\n'
                             '        debug=configuracoes.modo_debug,\n'
                             '        lifespan=ciclo_vida,\n'
                             '    )\n'
                             '\n'
                             '    aplicacao.include_router(\n'
                             '        roteador_api,\n'
                             '        prefix=configuracoes.prefixo_api,\n'
                             '    )\n'
                             '\n'
                             '    @aplicacao.get("/", tags=["sistema"])\n'
                             '    async def raiz() -> dict[str, str]:\n'
                             '        return {\n'
                             '            "nome": configuracoes.nome_aplicacao,\n'
                             '            "versao": configuracoes.versao_aplicacao,\n'
                             '            "status": "em_execucao",\n'
                             '        }\n'
                             '\n'
                             '    return aplicacao\n'
                             '\n'
                             '\n'
                             'app = criar_aplicacao()\n',
 'backend/app/repositories/__init__.py': 'from backend.app.repositories.empresa import RepositorioEmpresa\n'
                                         '\n'
                                         '__all__ = ["RepositorioEmpresa"]\n',
 'backend/app/repositories/empresa.py': 'from __future__ import annotations\n'
                                        '\n'
                                        'from sqlalchemy import select\n'
                                        'from sqlalchemy.orm import Session\n'
                                        '\n'
                                        'from backend.app.models.empresa import Empresa\n'
                                        'from backend.app.schemas.empresa import EmpresaCriacao\n'
                                        '\n'
                                        '\n'
                                        'class RepositorioEmpresa:\n'
                                        '    def __init__(self, banco: Session) -> None:\n'
                                        '        self.banco = banco\n'
                                        '\n'
                                        '    def obter_por_id(self, empresa_id: int) -> Empresa | None:\n'
                                        '        return self.banco.get(Empresa, empresa_id)\n'
                                        '\n'
                                        '    def obter_por_documento(self, documento: str) -> Empresa | None:\n'
                                        '        consulta = select(Empresa).where(Empresa.documento == documento)\n'
                                        '        return self.banco.scalar(consulta)\n'
                                        '\n'
                                        '    def listar(self, *, deslocamento: int = 0, limite: int = 100) -> '
                                        'list[Empresa]:\n'
                                        '        consulta = (\n'
                                        '            select(Empresa)\n'
                                        '            .order_by(Empresa.id)\n'
                                        '            .offset(deslocamento)\n'
                                        '            .limit(limite)\n'
                                        '        )\n'
                                        '        return list(self.banco.scalars(consulta).all())\n'
                                        '\n'
                                        '    def criar(self, dados: EmpresaCriacao) -> Empresa:\n'
                                        '        empresa = Empresa(\n'
                                        '            razao_social=dados.razao_social,\n'
                                        '            documento=dados.documento,\n'
                                        '            tipo_empresa=dados.tipo_empresa.value,\n'
                                        '        )\n'
                                        '        self.banco.add(empresa)\n'
                                        '        self.banco.commit()\n'
                                        '        self.banco.refresh(empresa)\n'
                                        '        return empresa\n',
 'backend/app/schemas/__init__.py': 'from backend.app.schemas.empresa import EmpresaCriacao, EmpresaLeitura, '
                                    'TipoEmpresa\n'
                                    '\n'
                                    '__all__ = ["EmpresaCriacao", "EmpresaLeitura", "TipoEmpresa"]\n',
 'backend/app/schemas/empresa.py': 'from __future__ import annotations\n'
                                   '\n'
                                   'import re\n'
                                   'from datetime import datetime\n'
                                   'from enum import Enum\n'
                                   '\n'
                                   'from pydantic import BaseModel, ConfigDict, Field, field_validator\n'
                                   '\n'
                                   '\n'
                                   'class TipoEmpresa(str, Enum):\n'
                                   '    CLIENTE = "cliente"\n'
                                   '    FORNECEDOR = "fornecedor"\n'
                                   '    AMBOS = "ambos"\n'
                                   '\n'
                                   '\n'
                                   'def normalizar_documento(valor: str) -> str:\n'
                                   '    digitos = re.sub(r"\\D", "", valor or "")\n'
                                   '    if len(digitos) not in (11, 14):\n'
                                   '        raise ValueError("documento deve conter 11 dígitos (CPF) ou 14 dígitos '
                                   '(CNPJ)")\n'
                                   '    return digitos\n'
                                   '\n'
                                   '\n'
                                   'class EmpresaCriacao(BaseModel):\n'
                                   '    razao_social: str = Field(min_length=2, max_length=200)\n'
                                   '    documento: str\n'
                                   '    tipo_empresa: TipoEmpresa\n'
                                   '\n'
                                   '    @field_validator("razao_social")\n'
                                   '    @classmethod\n'
                                   '    def limpar_razao_social(cls, valor: str) -> str:\n'
                                   '        limpo = " ".join(valor.split())\n'
                                   '        if len(limpo) < 2:\n'
                                   '            raise ValueError("razão social muito curta")\n'
                                   '        return limpo\n'
                                   '\n'
                                   '    @field_validator("documento")\n'
                                   '    @classmethod\n'
                                   '    def limpar_documento(cls, valor: str) -> str:\n'
                                   '        return normalizar_documento(valor)\n'
                                   '\n'
                                   '\n'
                                   'class EmpresaLeitura(BaseModel):\n'
                                   '    model_config = ConfigDict(from_attributes=True)\n'
                                   '\n'
                                   '    id: int\n'
                                   '    razao_social: str\n'
                                   '    documento: str\n'
                                   '    tipo_empresa: TipoEmpresa\n'
                                   '    avaliacao: float | None\n'
                                   '    criado_em: datetime\n'
                                   '    atualizado_em: datetime\n',
 'backend/app/services/__init__.py': 'from backend.app.services.empresa import (\n'
                                     '    DocumentoEmpresaDuplicado,\n'
                                     '    EmpresaNaoEncontrada,\n'
                                     '    ServicoEmpresa,\n'
                                     ')\n'
                                     '\n'
                                     '__all__ = [\n'
                                     '    "DocumentoEmpresaDuplicado",\n'
                                     '    "EmpresaNaoEncontrada",\n'
                                     '    "ServicoEmpresa",\n'
                                     ']\n',
 'backend/app/services/empresa.py': 'from __future__ import annotations\n'
                                    '\n'
                                    'from sqlalchemy.exc import IntegrityError\n'
                                    'from sqlalchemy.orm import Session\n'
                                    '\n'
                                    'from backend.app.models.empresa import Empresa\n'
                                    'from backend.app.repositories.empresa import RepositorioEmpresa\n'
                                    'from backend.app.schemas.empresa import EmpresaCriacao\n'
                                    '\n'
                                    '\n'
                                    'class EmpresaNaoEncontrada(LookupError):\n'
                                    '    pass\n'
                                    '\n'
                                    '\n'
                                    'class DocumentoEmpresaDuplicado(ValueError):\n'
                                    '    pass\n'
                                    '\n'
                                    '\n'
                                    'class ServicoEmpresa:\n'
                                    '    def __init__(self, banco: Session) -> None:\n'
                                    '        self.repositorio = RepositorioEmpresa(banco)\n'
                                    '\n'
                                    '    def criar(self, dados: EmpresaCriacao) -> Empresa:\n'
                                    '        if self.repositorio.obter_por_documento(dados.documento) is not None:\n'
                                    '            raise DocumentoEmpresaDuplicado(dados.documento)\n'
                                    '\n'
                                    '        try:\n'
                                    '            return self.repositorio.criar(dados)\n'
                                    '        except IntegrityError as exc:\n'
                                    '            self.repositorio.banco.rollback()\n'
                                    '            raise DocumentoEmpresaDuplicado(dados.documento) from exc\n'
                                    '\n'
                                    '    def obter(self, empresa_id: int) -> Empresa:\n'
                                    '        empresa = self.repositorio.obter_por_id(empresa_id)\n'
                                    '        if empresa is None:\n'
                                    '            raise EmpresaNaoEncontrada(empresa_id)\n'
                                    '        return empresa\n'
                                    '\n'
                                    '    def listar(self, *, deslocamento: int = 0, limite: int = 100) -> '
                                    'list[Empresa]:\n'
                                    '        return self.repositorio.listar(\n'
                                    '            deslocamento=deslocamento,\n'
                                    '            limite=limite,\n'
                                    '        )\n',
 'docs/README.md': '# Documentação\n'
                   '\n'
                   'Documentação técnica e funcional da Plataforma de Serviços Mecânicos.\n'
                   '\n'
                   'Todo o conteúdo voltado ao usuário e ao domínio da aplicação deve ser mantido em português.\n'
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
 'tests/test_banco_dados.py': 'from sqlalchemy import create_engine, select\n'
                              'from sqlalchemy.orm import Session\n'
                              'from sqlalchemy.pool import StaticPool\n'
                              '\n'
                              'from backend.app.database.base import Base\n'
                              'from backend.app.models.empresa import Empresa\n'
                              '\n'
                              '\n'
                              'def test_persistencia_empresa_em_memoria() -> None:\n'
                              '    engine = create_engine(\n'
                              '        "sqlite://",\n'
                              '        connect_args={"check_same_thread": False},\n'
                              '        poolclass=StaticPool,\n'
                              '    )\n'
                              '    Base.metadata.create_all(bind=engine)\n'
                              '\n'
                              '    with Session(engine) as banco:\n'
                              '        empresa = Empresa(\n'
                              '            razao_social="Oficina Teste Ltda",\n'
                              '            documento="TEST-DOC-0001",\n'
                              '            tipo_empresa="fornecedor",\n'
                              '        )\n'
                              '        banco.add(empresa)\n'
                              '        banco.commit()\n'
                              '        empresa_id = empresa.id\n'
                              '\n'
                              '    with Session(engine) as banco:\n'
                              '        carregada = banco.scalar(\n'
                              '            select(Empresa).where(Empresa.id == empresa_id)\n'
                              '        )\n'
                              '\n'
                              '        assert carregada is not None\n'
                              '        assert carregada.razao_social == "Oficina Teste Ltda"\n'
                              '        assert carregada.documento == "TEST-DOC-0001"\n'
                              '        assert carregada.tipo_empresa == "fornecedor"\n'
                              '        assert carregada.avaliacao is None\n',
 'tests/test_empresas_api.py': 'from collections.abc import Generator\n'
                               '\n'
                               'import pytest\n'
                               'from fastapi.testclient import TestClient\n'
                               'from sqlalchemy import create_engine\n'
                               'from sqlalchemy.orm import Session, sessionmaker\n'
                               'from sqlalchemy.pool import StaticPool\n'
                               '\n'
                               'from backend.app.database.base import Base\n'
                               'from backend.app.database.sessao import obter_banco\n'
                               'from backend.app.principal import app\n'
                               '\n'
                               '\n'
                               '@pytest.fixture()\n'
                               'def cliente() -> Generator[TestClient, None, None]:\n'
                               '    engine = create_engine(\n'
                               '        "sqlite://",\n'
                               '        connect_args={"check_same_thread": False},\n'
                               '        poolclass=StaticPool,\n'
                               '    )\n'
                               '    SessaoTeste = sessionmaker(\n'
                               '        bind=engine,\n'
                               '        autoflush=False,\n'
                               '        expire_on_commit=False,\n'
                               '        class_=Session,\n'
                               '    )\n'
                               '    Base.metadata.create_all(bind=engine)\n'
                               '\n'
                               '    def substituir_banco() -> Generator[Session, None, None]:\n'
                               '        banco = SessaoTeste()\n'
                               '        try:\n'
                               '            yield banco\n'
                               '        finally:\n'
                               '            banco.close()\n'
                               '\n'
                               '    app.dependency_overrides[obter_banco] = substituir_banco\n'
                               '    with TestClient(app) as test_client:\n'
                               '        yield test_client\n'
                               '    app.dependency_overrides.clear()\n'
                               '    Base.metadata.drop_all(bind=engine)\n'
                               '    engine.dispose()\n'
                               '\n'
                               '\n'
                               'def test_criar_listar_e_obter_empresa(cliente: TestClient) -> None:\n'
                               '    resposta_criacao = cliente.post(\n'
                               '        "/api/v1/empresas",\n'
                               '        json={\n'
                               '            "razao_social": "Oficina Paraná Ltda",\n'
                               '            "documento": "12.345.678/0001-90",\n'
                               '            "tipo_empresa": "fornecedor",\n'
                               '        },\n'
                               '    )\n'
                               '    assert resposta_criacao.status_code == 201\n'
                               '    criada = resposta_criacao.json()\n'
                               '    assert criada["id"] == 1\n'
                               '    assert criada["razao_social"] == "Oficina Paraná Ltda"\n'
                               '    assert criada["documento"] == "12345678000190"\n'
                               '    assert criada["tipo_empresa"] == "fornecedor"\n'
                               '    assert criada["avaliacao"] is None\n'
                               '\n'
                               '    resposta_lista = cliente.get("/api/v1/empresas")\n'
                               '    assert resposta_lista.status_code == 200\n'
                               '    lista = resposta_lista.json()\n'
                               '    assert len(lista) == 1\n'
                               '    assert lista[0]["id"] == criada["id"]\n'
                               '\n'
                               '    resposta_obter = cliente.get(f"/api/v1/empresas/{criada[\'id\']}")\n'
                               '    assert resposta_obter.status_code == 200\n'
                               '    assert resposta_obter.json()["documento"] == "12345678000190"\n'
                               '\n'
                               '\n'
                               'def test_documento_duplicado_retorna_409(cliente: TestClient) -> None:\n'
                               '    dados = {\n'
                               '        "razao_social": "Fornecedor A Ltda",\n'
                               '        "documento": "12345678901",\n'
                               '        "tipo_empresa": "fornecedor",\n'
                               '    }\n'
                               '    primeira = cliente.post("/api/v1/empresas", json=dados)\n'
                               '    segunda = cliente.post("/api/v1/empresas", json=dados)\n'
                               '\n'
                               '    assert primeira.status_code == 201\n'
                               '    assert segunda.status_code == 409\n'
                               '    assert segunda.json()["detail"] == "documento_da_empresa_ja_cadastrado"\n'
                               '\n'
                               '\n'
                               'def test_documento_invalido_retorna_422(cliente: TestClient) -> None:\n'
                               '    resposta = cliente.post(\n'
                               '        "/api/v1/empresas",\n'
                               '        json={\n'
                               '            "razao_social": "Cliente Teste",\n'
                               '            "documento": "123",\n'
                               '            "tipo_empresa": "cliente",\n'
                               '        },\n'
                               '    )\n'
                               '    assert resposta.status_code == 422\n'
                               '\n'
                               '\n'
                               'def test_documento_com_12_digitos_retorna_422(cliente: TestClient) -> None:\n'
                               '    resposta = cliente.post(\n'
                               '        "/api/v1/empresas",\n'
                               '        json={\n'
                               '            "razao_social": "Cliente Teste",\n'
                               '            "documento": "123331231531",\n'
                               '            "tipo_empresa": "cliente",\n'
                               '        },\n'
                               '    )\n'
                               '    assert resposta.status_code == 422\n'
                               '\n'
                               '\n'
                               'def test_tipo_empresa_invalido_retorna_422(cliente: TestClient) -> None:\n'
                               '    resposta = cliente.post(\n'
                               '        "/api/v1/empresas",\n'
                               '        json={\n'
                               '            "razao_social": "Cliente Teste",\n'
                               '            "documento": "12345678901",\n'
                               '            "tipo_empresa": "invalido",\n'
                               '        },\n'
                               '    )\n'
                               '    assert resposta.status_code == 422\n'
                               '\n'
                               '\n'
                               'def test_empresa_inexistente_retorna_404(cliente: TestClient) -> None:\n'
                               '    resposta = cliente.get("/api/v1/empresas/999")\n'
                               '    assert resposta.status_code == 404\n'
                               '    assert resposta.json()["detail"] == "empresa_nao_encontrada"\n',
 'tests/test_saude.py': 'from fastapi.testclient import TestClient\n'
                        '\n'
                        'from backend.app.principal import app\n'
                        '\n'
                        '\n'
                        'def test_raiz() -> None:\n'
                        '    with TestClient(app) as cliente:\n'
                        '        resposta = cliente.get("/")\n'
                        '    assert resposta.status_code == 200\n'
                        '    dados = resposta.json()\n'
                        '    assert dados["status"] == "em_execucao"\n'
                        '    assert dados["versao"] == "0.1.0"\n'
                        '\n'
                        '\n'
                        'def test_saude() -> None:\n'
                        '    with TestClient(app) as cliente:\n'
                        '        resposta = cliente.get("/api/v1/saude")\n'
                        '    assert resposta.status_code == 200\n'
                        '    dados = resposta.json()\n'
                        '    assert dados["status"] == "ok"\n'
                        '    assert dados["versao"] == "0.1.0"\n'}
STALE_FILES: List[str] = ['backend/app/api/router.py',
 'backend/app/api/routes/__init__.py',
 'backend/app/api/routes/companies.py',
 'backend/app/api/routes/database.py',
 'backend/app/api/routes/health.py',
 'backend/app/core/config.py',
 'backend/app/database/init_db.py',
 'backend/app/database/session.py',
 'backend/app/main.py',
 'backend/app/models/company.py',
 'backend/app/repositories/company.py',
 'backend/app/schemas/company.py',
 'backend/app/services/company.py',
 'tests/__init__.py',
 'tests/test_companies_api.py',
 'tests/test_database.py',
 'tests/test_health.py']
ENVIRONMENT_RENAME: Dict[str, str] = {'MEC_API_V1_PREFIX': 'MEC_PREFIXO_API',
 'MEC_APP_NAME': 'MEC_NOME_APLICACAO',
 'MEC_APP_VERSION': 'MEC_VERSAO_APLICACAO',
 'MEC_DATABASE_URL': 'MEC_URL_BANCO_DADOS',
 'MEC_DEBUG': 'MEC_MODO_DEBUG',
 'MEC_ENVIRONMENT': 'MEC_AMBIENTE'}


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
    print(f"{PROJECT_LABEL} — V0.1 D3 FIX2 Português")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    if is_cgx_root(root):
        print("ERRO: esta pasta parece ser a raiz do CGX Platform.")
        print("Execute este arquivo somente na raiz do projeto MEC-Servicos.")
        return 20

    # CORREÇÃO DO FIX1:
    # um arquivo que ainda está exatamente na baseline D3 é uma atualização
    # elegível, não um conflito. O FIX1 classificava esses arquivos como
    # conflito antes de comparar com a baseline.
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

        expected_old = EXPECTED_D3.get(rel)
        if expected_old is not None and current == normalize(expected_old):
            eligible_updates.append(rel)
            continue

        conflicts.append(rel)

    # Arquivos antigos que serão removidos também precisam estar na baseline
    # conhecida. Assim, uma edição manual do usuário nunca é apagada sem aviso.
    stale_conflicts: List[str] = []
    for rel in STALE_FILES:
        path = root / rel
        if not path.exists():
            continue
        expected_old = EXPECTED_D3.get(rel)
        if expected_old is None:
            stale_conflicts.append(rel)
            continue
        current = normalize(path.read_text(encoding="utf-8"))
        if current != normalize(expected_old):
            stale_conflicts.append(rel)

    conflicts = sorted(set(conflicts + stale_conflicts))

    if conflicts:
        print("ERRO: foram encontrados arquivos divergentes da baseline D3.")
        print("Nenhum arquivo foi alterado.")
        for rel in conflicts:
            print(f"  CONFLICT: {rel}")

        report = {
            "project": PROJECT_LABEL,
            "revision": REVISION,
            "status": "CONFLICT",
            "root": str(root),
            "conflicts": conflicts,
            "message": "Nenhum arquivo foi alterado.",
            "fix1_issue_corrected": True,
        }
        atomic_write(
            root / REPORT_JSON,
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        )
        atomic_write(
            root / REPORT_TXT,
            "\n".join([
                f"{PROJECT_LABEL} — V0.1 D3 FIX2 Português",
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
    backup_dir = root / BACKUP_ROOT / f"V0_1_D3_FIX2_PORTUGUES_{timestamp}"

    backed_up: List[str] = []
    created: List[str] = []
    changed: List[str] = []
    removed: List[str] = []

    # Backup do banco atual antes da migração companies -> empresas.
    database_path = root / "data" / "mec_servicos.db"
    if database_path.exists():
        destination = backup_dir / "data" / database_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, destination)
        backed_up.append(str(database_path.relative_to(root)))

    # Backup do .env se existir.
    env_path = root / ".env"
    if env_path.exists():
        destination = backup_dir / ".env"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(env_path, destination)
        backed_up.append(".env")

    # Backup dos arquivos que serão substituídos/removidos.
    backup_candidates = set(eligible_updates) | set(STALE_FILES)
    for rel in sorted(backup_candidates):
        path = root / rel
        if not path.exists():
            continue
        destination = backup_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        backed_up.append(rel)

    # Escreve os arquivos traduzidos.
    for rel in eligible_updates + eligible_creates:
        atomic_write(root / rel, TARGET_FILES[rel])
        if rel in eligible_creates:
            created.append(rel)
        else:
            changed.append(rel)

    # Remove somente os arquivos legados conhecidos e previamente validados.
    for rel in STALE_FILES:
        path = root / rel
        if not path.exists():
            continue
        path.unlink()
        removed.append(rel)

    # Remove diretórios legados apenas quando ficarem vazios.
    for directory in [
        root / "backend" / "app" / "api" / "routes",
    ]:
        if directory.exists() and directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass

    # Migra apenas nomes de variáveis MEC_* conhecidos no .env.
    env_migrated = False
    if env_path.exists():
        original = normalize(env_path.read_text(encoding="utf-8"))
        migrated = original
        for old_name, new_name in ENVIRONMENT_RENAME.items():
            migrated = migrated.replace(old_name + "=", new_name + "=")
        if migrated != original:
            atomic_write(env_path, migrated)
            env_migrated = True
            if ".env" not in changed:
                changed.append(".env")

    target_python = sorted(rel for rel in TARGET_FILES if rel.endswith(".py"))
    missing_target = [rel for rel in TARGET_FILES if not (root / rel).exists()]
    ast_ok, ast_errors = validate_python_files(root, target_python)
    files_ok = not missing_target

    content_mismatch: List[str] = []
    for rel, expected in TARGET_FILES.items():
        path = root / rel
        if not path.exists():
            continue
        if normalize(path.read_text(encoding="utf-8")) != normalize(expected):
            content_mismatch.append(rel)

    if content_mismatch:
        files_ok = False

    hashes = {}
    for rel in sorted(TARGET_FILES):
        path = root / rel
        if path.exists() and path.is_file():
            try:
                hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                pass

    status = "OK" if files_ok and ast_ok else "FAILED"

    report = {
        "project": PROJECT_LABEL,
        "revision": REVISION,
        "script": SCRIPT_NAME,
        "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "status": status,
        "fix1_issue_corrected": True,
        "files_ok": files_ok,
        "ast_ok": ast_ok,
        "created": created,
        "changed": changed,
        "already_target": already_target,
        "removed": removed,
        "backed_up": backed_up,
        "backup_dir": str(backup_dir) if backed_up else None,
        "env_migrated": env_migrated,
        "missing_target": missing_target,
        "content_mismatch": content_mismatch,
        "ast_errors": ast_errors,
        "target_hashes_sha256": hashes,
        "database_migration": {
            "legacy_table": "companies",
            "new_table": "empresas",
            "preserve_existing_data": True,
            "translate_company_type_values": {
                "client": "cliente",
                "supplier": "fornecedor",
                "both": "ambos",
            },
        },
        "next_commands": [
            r"python -m pytest",
            r"python -m uvicorn backend.app.principal:app --reload",
        ],
    }

    atomic_write(
        root / REPORT_JSON,
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    )

    txt_lines = [
        f"{PROJECT_LABEL} — V0.1 D3 FIX2 Português",
        f"REVISION={REVISION}",
        f"ROOT={root}",
        "",
        f"STATUS={status}",
        "FIX1_ISSUE_CORRECTED=True",
        f"FILES_OK={files_ok}",
        f"AST_OK={ast_ok}",
        f"CREATED={len(created)}",
        f"CHANGED={len(changed)}",
        f"ALREADY_TARGET={len(already_target)}",
        f"REMOVED={len(removed)}",
        f"BACKED_UP={len(backed_up)}",
        f"ENV_MIGRATED={env_migrated}",
        "",
        "CRIADOS:",
        *([f"  {item}" for item in created] or ["  (nenhum)"]),
        "",
        "ALTERADOS:",
        *([f"  {item}" for item in changed] or ["  (nenhum)"]),
        "",
        "JÁ EM PORTUGUÊS:",
        *([f"  {item}" for item in already_target] or ["  (nenhum)"]),
        "",
        "REMOVIDOS_APOS_BACKUP:",
        *([f"  {item}" for item in removed] or ["  (nenhum)"]),
        "",
        "BACKUP:",
        f"  {str(backup_dir) if backed_up else '(nenhum)'}",
        "",
        "MIGRACAO_BANCO:",
        "  companies -> empresas",
        "  legal_name -> razao_social",
        "  document -> documento",
        "  company_type -> tipo_empresa",
        "  client -> cliente",
        "  supplier -> fornecedor",
        "  both -> ambos",
        "",
        "OBSERVACAO:",
        "  O registro legado existente é preservado durante a migração.",
        "  A validação de novos documentos aceita 11 ou 14 dígitos.",
        "",
        "PROXIMO:",
        "  1. python -m pytest",
        "  2. python -m uvicorn backend.app.principal:app --reload",
        "  3. Abrir http://127.0.0.1:8000/docs",
        "",
    ]
    atomic_write(root / REPORT_TXT, "\n".join(txt_lines))

    print(f"FILES_OK= {files_ok}")
    print(f"AST_OK= {ast_ok}")
    print(f"CREATED= {len(created)}")
    print(f"CHANGED= {len(changed)}")
    print(f"ALREADY_TARGET= {len(already_target)}")
    print(f"REMOVED= {len(removed)}")
    print(f"BACKED_UP= {len(backed_up)}")
    print(f"ENV_MIGRATED= {env_migrated}")
    if backed_up:
        print(f"BACKUP_DIR= {backup_dir}")
    print(f"REPORT= {root / REPORT_TXT}")
    print(f"JSON= {root / REPORT_JSON}")

    if not files_ok or not ast_ok:
        print("ERRO: a validação da tradução falhou.")
        return 40

    print("D3_FIX2_PORTUGUES_APPLIED= True")
    print("MIGRACAO_BANCO_PRONTA= True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
