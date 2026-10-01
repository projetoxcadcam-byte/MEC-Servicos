from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D3_COMPANIES.py"
REVISION = "MEC-SERVICOS-V0.1-D3-COMPANIES-2026-09-30"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D3_COMPANIES_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D3_COMPANIES.json"
BACKUP_ROOT = "_mec_backups"

EXPECTED_D2: Dict[str, str] = {'backend/app/api/router.py': 'from __future__ import annotations\n'
                              '\n'
                              'from fastapi import APIRouter\n'
                              '\n'
                              'from backend.app.api.routes.database import router as database_router\n'
                              'from backend.app.api.routes.health import router as health_router\n'
                              '\n'
                              'api_router = APIRouter()\n'
                              'api_router.include_router(health_router)\n'
                              'api_router.include_router(database_router)\n',
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
 'backend/app/repositories/__init__.py': '"""Repositórios de persistência."""\n',
 'backend/app/schemas/__init__.py': '"""Schemas de entrada e saída da API."""\n',
 'backend/app/services/__init__.py': '"""Serviços e regras de negócio."""\n'}
TARGET_FILES: Dict[str, str] = {'backend/app/api/router.py': 'from __future__ import annotations\n'
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
                                '    assert response.json()["detail"] == "company_not_found"\n'}
REQUIRED_D2 = ['backend/app/database/base.py',
 'backend/app/database/session.py',
 'backend/app/database/init_db.py',
 'backend/app/models/company.py',
 'backend/app/api/routes/database.py',
 'backend/app/api/router.py',
 'tests/test_database.py']


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
    print(f"{PROJECT_LABEL} — V0.1 D3 Companies")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    if is_cgx_root(root):
        print("ERRO: esta pasta parece ser a raiz do CGX Platform.")
        print("Execute este arquivo somente na raiz do projeto MEC-Servicos.")
        return 20

    missing_d2 = [rel for rel in REQUIRED_D2 if not (root / rel).exists()]
    if missing_d2:
        print("ERRO: baseline D2 incompleta. Arquivos ausentes:")
        for rel in missing_d2:
            print(f"  MISSING_D2: {rel}")
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

        expected = EXPECTED_D2.get(rel)
        if expected is not None and current == normalize(expected):
            eligible_updates.append(rel)
            continue

        conflicts.append(rel)

    if conflicts:
        print("ERRO: foram encontrados arquivos divergentes da baseline D2.")
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
        }
        atomic_write(root / REPORT_JSON, json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        atomic_write(
            root / REPORT_TXT,
            "\n".join([
                f"{PROJECT_LABEL} — V0.1 D3 Companies",
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
    backup_dir = root / BACKUP_ROOT / f"V0_1_D3_COMPANIES_{timestamp}"
    backed_up: List[str] = []

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

    all_target = sorted(TARGET_FILES.keys())
    missing_target = [rel for rel in all_target if not (root / rel).exists()]
    content_mismatch: List[str] = []

    for rel in all_target:
        path = root / rel
        if path.exists():
            current = normalize(path.read_text(encoding="utf-8"))
            if current != normalize(TARGET_FILES[rel]):
                content_mismatch.append(rel)

    ast_ok, ast_errors = validate_python_files(root, all_target)
    files_ok = not missing_target and not content_mismatch
    status = "OK" if files_ok and ast_ok else "FAILED"

    hashes = {}
    for rel in all_target:
        path = root / rel
        if path.exists():
            hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))

    report = {
        "project": PROJECT_LABEL,
        "revision": REVISION,
        "script": SCRIPT_NAME,
        "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "status": status,
        "d2_baseline_present": True,
        "files_ok": files_ok,
        "ast_ok": ast_ok,
        "changed": changed,
        "already_target": already_target,
        "backed_up": backed_up,
        "backup_dir": str(backup_dir) if backed_up else None,
        "missing_target": missing_target,
        "content_mismatch": content_mismatch,
        "ast_errors": ast_errors,
        "target_hashes_sha256": hashes,
        "features": [
            "CompanyCreate/CompanyRead schemas",
            "company type validation: client/supplier/both",
            "CPF/CNPJ format normalization by digit count",
            "CompanyRepository",
            "CompanyService",
            "POST /api/v1/companies",
            "GET /api/v1/companies",
            "GET /api/v1/companies/{company_id}",
            "duplicate document conflict = HTTP 409",
            "company not found = HTTP 404",
        ],
        "next_commands": [
            r"python -m pytest",
            r"python -m uvicorn backend.app.main:app --reload",
        ],
    }
    atomic_write(root / REPORT_JSON, json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    txt_lines = [
        f"{PROJECT_LABEL} — V0.1 D3 Companies",
        f"REVISION={REVISION}",
        f"ROOT={root}",
        "",
        f"STATUS={status}",
        "D2_BASELINE_PRESENT=True",
        f"FILES_OK={files_ok}",
        f"AST_OK={ast_ok}",
        f"CHANGED={len(changed)}",
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
        "API:",
        "  POST /api/v1/companies",
        "  GET  /api/v1/companies",
        "  GET  /api/v1/companies/{company_id}",
        "",
        "VALIDATION:",
        "  company_type=client|supplier|both",
        "  document=11 or 14 digits after normalization",
        "  duplicate document -> 409",
        "  missing company -> 404",
        "",
        "NEXT:",
        "  1. python -m pytest",
        "  2. python -m uvicorn backend.app.main:app --reload",
        "  3. Abrir http://127.0.0.1:8000/docs",
        "",
        "NOTE:",
        "  D3 normalizes CPF/CNPJ punctuation but does not yet validate official checksum digits.",
        "  Official document checksum validation can be added in a later dedicated step.",
        "",
    ]
    atomic_write(root / REPORT_TXT, "\n".join(txt_lines))

    print(f"FILES_OK= {files_ok}")
    print(f"AST_OK= {ast_ok}")
    print(f"CHANGED= {len(changed)}")
    print(f"BACKED_UP= {len(backed_up)}")
    if backed_up:
        print(f"BACKUP_DIR= {backup_dir}")
    print(f"REPORT= {root / REPORT_TXT}")
    print(f"JSON= {root / REPORT_JSON}")

    if not files_ok or not ast_ok:
        print("ERRO: a validacao estatica do D3 falhou.")
        return 40

    print("D3_COMPANIES_APPLIED= True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
