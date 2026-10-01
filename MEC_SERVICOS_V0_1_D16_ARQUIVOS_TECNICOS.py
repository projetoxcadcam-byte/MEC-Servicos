
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


SCRIPT_NAME = "MEC_SERVICOS_V0_1_D16_ARQUIVOS_TECNICOS.py"
REVISION = "MEC-SERVICOS-V0.1-D16-ARQUIVOS-TECNICOS-2026-10-01"
ROOT = Path(__file__).resolve().parent
BACKUP_ROOT = ROOT / "_mec_backups"
REPORT = ROOT / "MEC_SERVICOS_V0_1_D16_ARQUIVOS_TECNICOS_RELATORIO.txt"
JSON_REPORT = ROOT / "MEC_SERVICOS_V0_1_D16_ARQUIVOS_TECNICOS.json"
DB_PATH = ROOT / "data" / "mec_servicos.db"

D15_REQUIRED = [
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
MAX_SIZE_MB = 100
MULTIPART_REQUIREMENT = "python-multipart>=0.0.9,<1.0"

TARGETS = {'backend/app/models/arquivo_tecnico.py': 'from __future__ import annotations\n\nfrom datetime import datetime\n\nfrom sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func\nfrom sqlalchemy.orm import Mapped, mapped_column\n\nfrom backend.app.database.base import Base\n\n\nclass ArquivoTecnico(Base):\n    __tablename__ = "arquivos_tecnicos"\n    __table_args__ = (\n        CheckConstraint(\n            "tamanho_bytes >= 0",\n            name="ck_arquivos_tecnicos_tamanho",\n        ),\n    )\n\n    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)\n    solicitacao_id: Mapped[int] = mapped_column(\n        ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    nome_original: Mapped[str] = mapped_column(String(255), nullable=False)\n    extensao: Mapped[str] = mapped_column(String(10), nullable=False)\n    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)\n    tamanho_bytes: Mapped[int] = mapped_column(Integer, nullable=False)\n    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)\n    caminho_arquivo: Mapped[str] = mapped_column(Text, nullable=False)\n    criado_em: Mapped[datetime] = mapped_column(\n        DateTime(timezone=True),\n        server_default=func.now(),\n        nullable=False,\n    )\n    ativo: Mapped[bool] = mapped_column(\n        Boolean,\n        nullable=False,\n        default=True,\n        server_default="1",\n        index=True,\n    )\n', 'backend/app/repositories/arquivo_tecnico.py': 'from __future__ import annotations\n\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.arquivo_tecnico import ArquivoTecnico\n\n\nclass RepositorioArquivoTecnico:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def criar(self, arquivo: ArquivoTecnico) -> ArquivoTecnico:\n        self.banco.add(arquivo)\n        self.banco.commit()\n        self.banco.refresh(arquivo)\n        return arquivo\n\n    def obter_ativo_por_id(self, arquivo_id: int) -> ArquivoTecnico | None:\n        return self.banco.scalar(\n            select(ArquivoTecnico).where(\n                ArquivoTecnico.id == arquivo_id,\n                ArquivoTecnico.ativo.is_(True),\n            )\n        )\n\n    def listar_ativos_por_solicitacao(\n        self,\n        solicitacao_id: int,\n    ) -> list[ArquivoTecnico]:\n        return list(\n            self.banco.scalars(\n                select(ArquivoTecnico)\n                .where(\n                    ArquivoTecnico.solicitacao_id == solicitacao_id,\n                    ArquivoTecnico.ativo.is_(True),\n                )\n                .order_by(\n                    ArquivoTecnico.criado_em.desc(),\n                    ArquivoTecnico.id.desc(),\n                )\n            )\n        )\n\n    def salvar(self, arquivo: ArquivoTecnico) -> ArquivoTecnico:\n        self.banco.add(arquivo)\n        self.banco.commit()\n        self.banco.refresh(arquivo)\n        return arquivo\n', 'backend/app/schemas/arquivo_tecnico.py': 'from __future__ import annotations\n\nfrom datetime import datetime\n\nfrom pydantic import BaseModel, ConfigDict\n\n\nclass ArquivoTecnicoResposta(BaseModel):\n    model_config = ConfigDict(from_attributes=True)\n\n    id: int\n    solicitacao_id: int\n    nome_original: str\n    extensao: str\n    content_type: str | None\n    tamanho_bytes: int\n    sha256: str\n    criado_em: datetime\n    ativo: bool\n', 'backend/app/services/arquivo_tecnico.py': 'from __future__ import annotations\n\nimport hashlib\nimport os\nimport uuid\nfrom pathlib import Path\n\nfrom fastapi import HTTPException, UploadFile\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.arquivo_tecnico import ArquivoTecnico\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.repositories.arquivo_tecnico import RepositorioArquivoTecnico\n\n\nclass ServicoArquivoTecnico:\n    ALLOWED_EXTENSIONS = frozenset(\n        {".step", ".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf"}\n    )\n    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024\n    CHUNK_SIZE = 1024 * 1024\n    STORAGE_ROOT = Path("storage") / "arquivos_tecnicos"\n\n    def __init__(self, banco: Session, *, storage_root: Path | None = None) -> None:\n        self.banco = banco\n        self.repositorio = RepositorioArquivoTecnico(banco)\n        self.storage_root = (\n            storage_root.resolve()\n            if storage_root is not None\n            else (Path(__file__).resolve().parents[3] / self.STORAGE_ROOT).resolve()\n        )\n\n    def _solicitacao_existe(self, solicitacao_id: int) -> None:\n        if self.banco.get(SolicitacaoServico, solicitacao_id) is None:\n            raise HTTPException(\n                status_code=404,\n                detail="solicitacao_nao_encontrada",\n            )\n\n    def _validar_extensao(self, filename: str | None) -> tuple[str, str]:\n        nome = Path(filename or "").name\n        if not nome or nome in {".", ".."}:\n            raise HTTPException(\n                status_code=400,\n                detail="nome_arquivo_obrigatorio",\n            )\n        if len(nome) > 255:\n            raise HTTPException(\n                status_code=400,\n                detail="nome_arquivo_muito_longo",\n            )\n\n        extensao = Path(nome).suffix.lower()\n        if extensao not in self.ALLOWED_EXTENSIONS:\n            raise HTTPException(\n                status_code=415,\n                detail="extensao_arquivo_nao_permitida",\n            )\n        return nome, extensao\n\n    async def criar(\n        self,\n        solicitacao_id: int,\n        arquivo: UploadFile,\n    ) -> ArquivoTecnico:\n        self._solicitacao_existe(solicitacao_id)\n        nome_original, extensao = self._validar_extensao(arquivo.filename)\n\n        self.storage_root.mkdir(parents=True, exist_ok=True)\n        nome_fisico = f"{uuid.uuid4().hex}{extensao}"\n        destino = self.storage_root / nome_fisico\n        temporario = self.storage_root / f".{nome_fisico}.part"\n\n        total = 0\n        digest = hashlib.sha256()\n\n        try:\n            with temporario.open("wb") as saida:\n                while True:\n                    bloco = await arquivo.read(self.CHUNK_SIZE)\n                    if not bloco:\n                        break\n\n                    total += len(bloco)\n                    if total > self.MAX_FILE_SIZE_BYTES:\n                        raise HTTPException(\n                            status_code=413,\n                            detail="arquivo_excede_limite_de_tamanho",\n                        )\n\n                    digest.update(bloco)\n                    saida.write(bloco)\n\n            os.replace(temporario, destino)\n\n            item = ArquivoTecnico(\n                solicitacao_id=solicitacao_id,\n                nome_original=nome_original,\n                extensao=extensao,\n                content_type=arquivo.content_type,\n                tamanho_bytes=total,\n                sha256=digest.hexdigest(),\n                caminho_arquivo=str(destino),\n                ativo=True,\n            )\n\n            try:\n                return self.repositorio.criar(item)\n            except Exception:\n                self.banco.rollback()\n                destino.unlink(missing_ok=True)\n                raise\n\n        except HTTPException:\n            temporario.unlink(missing_ok=True)\n            destino.unlink(missing_ok=True)\n            raise\n        except Exception:\n            temporario.unlink(missing_ok=True)\n            destino.unlink(missing_ok=True)\n            raise\n        finally:\n            await arquivo.close()\n\n    def listar(self, solicitacao_id: int) -> list[ArquivoTecnico]:\n        self._solicitacao_existe(solicitacao_id)\n        return self.repositorio.listar_ativos_por_solicitacao(solicitacao_id)\n\n    def obter(self, arquivo_id: int) -> ArquivoTecnico:\n        item = self.repositorio.obter_ativo_por_id(arquivo_id)\n        if item is None:\n            raise HTTPException(\n                status_code=404,\n                detail="arquivo_tecnico_nao_encontrado",\n            )\n        return item\n\n    def caminho_seguro(self, item: ArquivoTecnico) -> Path:\n        caminho = Path(item.caminho_arquivo).resolve()\n        if not caminho.is_relative_to(self.storage_root):\n            raise HTTPException(\n                status_code=500,\n                detail="caminho_arquivo_invalido",\n            )\n        if not caminho.is_file():\n            raise HTTPException(\n                status_code=404,\n                detail="arquivo_fisico_nao_encontrado",\n            )\n        return caminho\n\n    def desvincular(self, arquivo_id: int) -> None:\n        item = self.repositorio.obter_ativo_por_id(arquivo_id)\n        if item is None:\n            raise HTTPException(\n                status_code=404,\n                detail="arquivo_tecnico_nao_encontrado",\n            )\n\n        item.ativo = False\n        self.repositorio.salvar(item)\n', 'backend/app/api/rotas/arquivos_tecnicos.py': 'from __future__ import annotations\n\nfrom fastapi import APIRouter, Depends, File, UploadFile, status\nfrom fastapi.responses import FileResponse\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\n\n\nroteador = APIRouter(tags=["arquivos-tecnicos"])\n\n\n@roteador.post(\n    "/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n    response_model=ArquivoTecnicoResposta,\n    status_code=status.HTTP_201_CREATED,\n)\nasync def enviar_arquivo_tecnico(\n    solicitacao_id: int,\n    file: UploadFile = File(...),\n    banco: Session = Depends(obter_banco),\n) -> ArquivoTecnicoResposta:\n    item = await ServicoArquivoTecnico(banco).criar(solicitacao_id, file)\n    return ArquivoTecnicoResposta.model_validate(item)\n\n\n@roteador.get(\n    "/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n    response_model=list[ArquivoTecnicoResposta],\n)\ndef listar_arquivos_tecnicos(\n    solicitacao_id: int,\n    banco: Session = Depends(obter_banco),\n) -> list[ArquivoTecnicoResposta]:\n    itens = ServicoArquivoTecnico(banco).listar(solicitacao_id)\n    return [ArquivoTecnicoResposta.model_validate(item) for item in itens]\n\n\n@roteador.get(\n    "/arquivos-tecnicos/{arquivo_id}",\n    response_model=ArquivoTecnicoResposta,\n)\ndef obter_arquivo_tecnico(\n    arquivo_id: int,\n    banco: Session = Depends(obter_banco),\n) -> ArquivoTecnicoResposta:\n    item = ServicoArquivoTecnico(banco).obter(arquivo_id)\n    return ArquivoTecnicoResposta.model_validate(item)\n\n\n@roteador.get(\n    "/arquivos-tecnicos/{arquivo_id}/download",\n    response_class=FileResponse,\n)\ndef baixar_arquivo_tecnico(\n    arquivo_id: int,\n    banco: Session = Depends(obter_banco),\n) -> FileResponse:\n    servico = ServicoArquivoTecnico(banco)\n    item = servico.obter(arquivo_id)\n    caminho = servico.caminho_seguro(item)\n\n    return FileResponse(\n        path=caminho,\n        media_type=item.content_type or "application/octet-stream",\n        filename=item.nome_original,\n    )\n\n\n@roteador.delete(\n    "/arquivos-tecnicos/{arquivo_id}",\n    status_code=status.HTTP_204_NO_CONTENT,\n)\ndef desvincular_arquivo_tecnico(\n    arquivo_id: int,\n    banco: Session = Depends(obter_banco),\n) -> None:\n    ServicoArquivoTecnico(banco).desvincular(arquivo_id)\n', 'tests/test_arquivos_tecnicos.py': 'from __future__ import annotations\n\nimport hashlib\nfrom collections.abc import Generator\nfrom pathlib import Path\n\nimport pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine, select\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.arquivo_tecnico import ArquivoTecnico\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.principal import app\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\n\n\n@pytest.fixture()\ndef ambiente(\n    tmp_path: Path,\n    monkeypatch: pytest.MonkeyPatch,\n) -> Generator[tuple[TestClient, sessionmaker], None, None]:\n    engine = create_engine(\n        "sqlite://",\n        connect_args={"check_same_thread": False},\n        poolclass=StaticPool,\n    )\n    SessaoTeste = sessionmaker(\n        bind=engine,\n        autoflush=False,\n        expire_on_commit=False,\n        class_=Session,\n    )\n    Base.metadata.create_all(bind=engine)\n\n    monkeypatch.setattr(\n        ServicoArquivoTecnico,\n        "STORAGE_ROOT",\n        tmp_path / "arquivos_tecnicos",\n    )\n\n    def substituir_banco() -> Generator[Session, None, None]:\n        banco = SessaoTeste()\n        try:\n            yield banco\n        finally:\n            banco.close()\n\n    app.dependency_overrides[obter_banco] = substituir_banco\n    try:\n        with TestClient(app) as test_client:\n            yield test_client, SessaoTeste\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(bind=engine)\n        engine.dispose()\n\n\ndef preparar_solicitacao(SessaoTeste: sessionmaker) -> int:\n    banco = SessaoTeste()\n\n    cliente = Empresa(\n        razao_social="Cliente D16",\n        documento="D16-CLIENTE-001",\n        tipo_empresa="cliente",\n    )\n    processo = ProcessoFabricacao(\n        codigo="usinagem_cnc_d16",\n        nome="Usinagem CNC D16",\n        descricao="Processo D16.",\n    )\n    material = Material(\n        codigo="aluminio_6061_d16",\n        nome="Aluminio 6061 D16",\n        familia="Aluminio",\n        especificacao="Liga D16.",\n    )\n\n    banco.add_all([cliente, processo, material])\n    banco.commit()\n\n    solicitacao = SolicitacaoServico(\n        empresa_cliente_id=cliente.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        dimensao_x_maxima_mm=100,\n        dimensao_y_maxima_mm=100,\n        dimensao_z_maxima_mm=100,\n        tolerancia_requerida_mm=0.02,\n        quantidade=1,\n        observacoes="Solicitacao D16.",\n        status="aberta",\n    )\n    banco.add(solicitacao)\n    banco.commit()\n\n    solicitacao_id = solicitacao.id\n    banco.close()\n    return solicitacao_id\n\n\ndef test_upload_arquivo_permitido_registra_sha256_e_metadados(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n    conteudo = b"STEP-D16-CONTENT"\n\n    resposta = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={\n            "file": (\n                "peca.step",\n                conteudo,\n                "application/step",\n            )\n        },\n    )\n\n    assert resposta.status_code == 201\n    corpo = resposta.json()\n    assert corpo["solicitacao_id"] == solicitacao_id\n    assert corpo["nome_original"] == "peca.step"\n    assert corpo["extensao"] == ".step"\n    assert corpo["tamanho_bytes"] == len(conteudo)\n    assert corpo["sha256"] == hashlib.sha256(conteudo).hexdigest()\n    assert corpo["ativo"] is True\n\n    banco = SessaoTeste()\n    item = banco.scalar(\n        select(ArquivoTecnico).where(ArquivoTecnico.id == corpo["id"])\n    )\n    assert item is not None\n    assert Path(item.caminho_arquivo).is_file()\n    assert Path(item.caminho_arquivo).read_bytes() == conteudo\n    banco.close()\n\n\n@pytest.mark.parametrize(\n    "extensao",\n    [".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf"],\n)\ndef test_demais_extensoes_permitidas(ambiente, extensao):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={\n            "file": (\n                f"arquivo{extensao}",\n                b"D16",\n                "application/octet-stream",\n            )\n        },\n    )\n\n    assert resposta.status_code == 201\n    assert resposta.json()["extensao"] == extensao\n\n\ndef test_extensao_nao_permitida_e_bloqueada(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={"file": ("peca.stl", b"STL", "model/stl")},\n    )\n\n    assert resposta.status_code == 415\n    assert resposta.json()["detail"] == "extensao_arquivo_nao_permitida"\n\n\ndef test_limite_de_tamanho_e_aplicado(\n    ambiente,\n    monkeypatch: pytest.MonkeyPatch,\n):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n\n    monkeypatch.setattr(\n        ServicoArquivoTecnico,\n        "MAX_FILE_SIZE_BYTES",\n        8,\n    )\n\n    resposta = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={"file": ("grande.pdf", b"123456789", "application/pdf")},\n    )\n\n    assert resposta.status_code == 413\n    assert resposta.json()["detail"] == "arquivo_excede_limite_de_tamanho"\n\n\ndef test_listar_e_baixar_arquivo(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n    conteudo = b"PDF-D16"\n\n    upload = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={\n            "file": (\n                "desenho.pdf",\n                conteudo,\n                "application/pdf",\n            )\n        },\n    )\n    assert upload.status_code == 201\n    arquivo_id = upload.json()["id"]\n\n    lista = cliente_http.get(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos"\n    )\n    assert lista.status_code == 200\n    assert len(lista.json()) == 1\n    assert lista.json()[0]["id"] == arquivo_id\n\n    metadata = cliente_http.get(f"/api/v1/arquivos-tecnicos/{arquivo_id}")\n    assert metadata.status_code == 200\n    assert metadata.json()["nome_original"] == "desenho.pdf"\n\n    download = cliente_http.get(\n        f"/api/v1/arquivos-tecnicos/{arquivo_id}/download"\n    )\n    assert download.status_code == 200\n    assert download.content == conteudo\n    assert "desenho.pdf" in download.headers.get("content-disposition", "")\n\n\ndef test_solicitacao_inexistente_e_bloqueada(ambiente):\n    cliente_http, _ = ambiente\n\n    resposta = cliente_http.post(\n        "/api/v1/solicitacoes-servico/999999/arquivos-tecnicos",\n        files={\n            "file": (\n                "peca.pdf",\n                b"D16",\n                "application/pdf",\n            )\n        },\n    )\n\n    assert resposta.status_code == 404\n    assert resposta.json()["detail"] == "solicitacao_nao_encontrada"\n\n\ndef test_desvincular_preserva_historico_e_arquivo_fisico(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n    conteudo = b"HISTORICO-D16"\n\n    upload = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={\n            "file": (\n                "historico.pdf",\n                conteudo,\n                "application/pdf",\n            )\n        },\n    )\n    assert upload.status_code == 201\n    arquivo_id = upload.json()["id"]\n\n    banco = SessaoTeste()\n    item = banco.get(ArquivoTecnico, arquivo_id)\n    assert item is not None\n    caminho = Path(item.caminho_arquivo)\n    banco.close()\n\n    resposta = cliente_http.delete(\n        f"/api/v1/arquivos-tecnicos/{arquivo_id}"\n    )\n    assert resposta.status_code == 204\n    assert caminho.is_file()\n    assert caminho.read_bytes() == conteudo\n\n    banco = SessaoTeste()\n    item = banco.get(ArquivoTecnico, arquivo_id)\n    assert item is not None\n    assert item.ativo is False\n    banco.close()\n\n    assert (\n        cliente_http.get(\n            f"/api/v1/arquivos-tecnicos/{arquivo_id}"\n        ).status_code\n        == 404\n    )\n    assert (\n        cliente_http.get(\n            f"/api/v1/arquivos-tecnicos/{arquivo_id}/download"\n        ).status_code\n        == 404\n    )\n\n\ndef test_arquivo_desvinculado_nao_aparece_na_listagem(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    solicitacao_id = preparar_solicitacao(SessaoTeste)\n\n    upload = cliente_http.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",\n        files={\n            "file": (\n                "peca.pdf",\n                b"D16",\n                "application/pdf",\n            )\n        },\n    )\n    assert upload.status_code == 201\n\n    arquivo_id = upload.json()["id"]\n    assert (\n        cliente_http.delete(\n            f"/api/v1/arquivos-tecnicos/{arquivo_id}"\n        ).status_code\n        == 204\n    )\n\n    resposta = cliente_http.get(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos"\n    )\n    assert resposta.status_code == 200\n    assert resposta.json() == []\n'}


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def backup_file(path: Path, backup_dir: Path) -> bool:
    if not path.exists():
        return False
    destination = backup_dir / path.relative_to(ROOT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return True


def ast_ok(path: Path) -> tuple[bool, str | None]:
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        return True, None
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def ensure_router(text: str) -> tuple[str, bool]:
    import_line = (
        "from backend.app.api.rotas.arquivos_tecnicos "
        "import roteador as roteador_arquivos_tecnicos"
    )
    include_line = "roteador_api.include_router(roteador_arquivos_tecnicos)"

    changed = False

    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
        changed = True

    if include_line not in text:
        text = text.rstrip() + "\n" + include_line + "\n"
        changed = True

    return text, changed


def ensure_models_init(text: str) -> tuple[str, bool]:
    import_line = "from backend.app.models.arquivo_tecnico import ArquivoTecnico"
    changed = False

    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
        changed = True

    if '"ArquivoTecnico"' not in text:
        match = re.search(r"__all__\s*=\s*\[(.*?)\n\]", text, flags=re.DOTALL)
        if match:
            bloco = match.group(1)
            bloco = bloco.rstrip() + '\n    "ArquivoTecnico",'
            text = text[:match.start(1)] + bloco + text[match.end(1):]
        else:
            text = text.rstrip() + '\n\n__all__ = ["ArquivoTecnico"]\n'
        changed = True

    return text, changed


def ensure_requirement(text: str) -> tuple[str, bool]:
    if re.search(r"(?im)^\s*python-multipart(?:[<>=!~].*)?$", text):
        return text, False
    return text.rstrip() + "\n" + MULTIPART_REQUIREMENT + "\n", True


def migrar_banco() -> dict[str, object]:
    result: dict[str, object] = {
        "database_changed": False,
        "database_already_migrated": False,
        "rows_existing": 0,
        "table": "arquivos_tecnicos",
    }

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco não encontrado: {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        exists = con.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table' AND name='arquivos_tecnicos'
            """
        ).fetchone()

        if exists:
            result["database_already_migrated"] = True
            result["rows_existing"] = int(
                con.execute("SELECT COUNT(*) FROM arquivos_tecnicos").fetchone()[0]
            )
            return result

        con.execute(
            """
            CREATE TABLE arquivos_tecnicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitacao_id INTEGER NOT NULL,
                nome_original VARCHAR(255) NOT NULL,
                extensao VARCHAR(10) NOT NULL,
                content_type VARCHAR(255),
                tamanho_bytes INTEGER NOT NULL
                    CHECK (tamanho_bytes >= 0),
                sha256 VARCHAR(64) NOT NULL,
                caminho_arquivo TEXT NOT NULL,
                criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ativo BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (solicitacao_id)
                    REFERENCES solicitacoes_servico(id)
                    ON DELETE RESTRICT
            )
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_arquivos_tecnicos_solicitacao_id
            ON arquivos_tecnicos (solicitacao_id)
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_arquivos_tecnicos_sha256
            ON arquivos_tecnicos (sha256)
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_arquivos_tecnicos_ativo
            ON arquivos_tecnicos (ativo)
            """
        )
        con.commit()

        result["database_changed"] = True
        result["rows_existing"] = 0
        return result
    finally:
        con.close()


def validate_targets() -> tuple[bool, list[str], list[str]]:
    missing: list[str] = []
    errors: list[str] = []

    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        ok, error = ast_ok(path)
        if not ok:
            errors.append(f"{rel}: {error}")

    for rel in [
        "backend/app/api/roteador.py",
        "backend/app/models/__init__.py",
    ]:
        path = ROOT / rel
        ok, error = ast_ok(path)
        if not ok:
            errors.append(f"{rel}: {error}")

    return not missing and not errors, missing, errors


def main() -> int:
    print("Plataforma de Serviços Mecânicos — V0.1 D16 Arquivos Técnicos")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {ROOT}")

    if not (ROOT / "backend" / "app").is_dir() or not (ROOT / "tests").is_dir():
        print("ERRO: execute na raiz do MEC-Servicos.")
        return 20

    missing_d15 = [rel for rel in D15_REQUIRED if not (ROOT / rel).exists()]
    if missing_d15:
        print("D15_BASELINE_OK= False")
        for rel in missing_d15:
            print(f"MISSING= {rel}")
        return 21

    print("D15_BASELINE_OK= True")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D16_ARQUIVOS_TECNICOS_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_targets = [
        ROOT / rel for rel in TARGETS
    ] + [
        ROOT / "backend/app/api/roteador.py",
        ROOT / "backend/app/models/__init__.py",
        ROOT / "requirements.txt",
        DB_PATH,
    ]

    backed_up_paths: set[str] = set()
    backed_up = 0
    for path in backup_targets:
        if not path.exists():
            continue
        rel = str(path.relative_to(ROOT))
        if rel in backed_up_paths:
            continue
        if backup_file(path, backup_dir):
            backed_up_paths.add(rel)
            backed_up += 1

    try:
        database = migrar_banco()

        changed: list[str] = []

        for rel, content in TARGETS.items():
            path = ROOT / rel
            old = path.read_text(encoding="utf-8") if path.exists() else None
            if old != content:
                atomic_write(path, content)
                changed.append(rel)

        router_path = ROOT / "backend/app/api/roteador.py"
        old_router = router_path.read_text(encoding="utf-8")
        new_router, router_changed = ensure_router(old_router)
        if router_changed:
            atomic_write(router_path, new_router)
            changed.append("backend/app/api/roteador.py")

        models_path = ROOT / "backend/app/models/__init__.py"
        old_models = models_path.read_text(encoding="utf-8")
        new_models, models_changed = ensure_models_init(old_models)
        if models_changed:
            atomic_write(models_path, new_models)
            changed.append("backend/app/models/__init__.py")

        requirements_path = ROOT / "requirements.txt"
        old_requirements = requirements_path.read_text(encoding="utf-8")
        new_requirements, requirements_changed = ensure_requirement(old_requirements)
        if requirements_changed:
            atomic_write(requirements_path, new_requirements)
            changed.append("requirements.txt")

        ok, missing, ast_errors = validate_targets()

        multipart_installed = importlib.util.find_spec("multipart") is not None
        report = {
            "project": "Plataforma de Serviços Mecânicos",
            "revision": REVISION,
            "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
            "root": str(ROOT),
            "d15_baseline_ok": True,
            "ast_ok": ok,
            "missing": missing,
            "ast_errors": ast_errors,
            "table_arquivos_tecnicos": True,
            "database": database,
            "database_changed": bool(database["database_changed"]),
            "database_already_migrated": bool(database["database_already_migrated"]),
            "backed_up": backed_up,
            "changed_files": changed,
            "storage": {
                "backend": "local_filesystem",
                "directory": "storage/arquivos_tecnicos",
                "allowed_extensions": ALLOWED_EXTENSIONS,
                "max_size_mb": MAX_SIZE_MB,
                "sha256": True,
                "logical_unlink": True,
                "physical_delete": False,
            },
            "security": {
                "generated_physical_filename": True,
                "path_traversal_protection": True,
                "streaming_upload": True,
            },
            "dependencies": {
                "python_multipart_required": True,
                "python_multipart_installed": multipart_installed,
            },
            "not_in_scope": {
                "cad_parser": False,
                "viewer": False,
                "s3": False,
            },
            "endpoints": [
                "POST /api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
                "GET /api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
                "GET /api/v1/arquivos-tecnicos/{arquivo_id}",
                "GET /api/v1/arquivos-tecnicos/{arquivo_id}/download",
                "DELETE /api/v1/arquivos-tecnicos/{arquivo_id}",
            ],
            "backup_dir": str(backup_dir),
        }

        REPORT.write_text(
            "\n".join(
                [
                    "Plataforma de Serviços Mecânicos — V0.1 D16 Arquivos Técnicos",
                    f"REVISION= {REVISION}",
                    f"ROOT= {ROOT}",
                    "D15_BASELINE_OK= True",
                    f"AST_OK= {ok}",
                    "TABLE_ARQUIVOS_TECNICOS= True",
                    "ORM_TABLE_CREATED= True",
                    f"DATABASE_CHANGED= {database['database_changed']}",
                    f"DATABASE_ALREADY_MIGRATED= {database['database_already_migrated']}",
                    f"BACKED_UP= {backed_up}",
                    f"CHANGED_FILES= {len(changed)}",
                    "LOCAL_FILESYSTEM= True",
                    "MAX_SIZE_MB= 100",
                    "SHA256= True",
                    "LOGICAL_UNLINK= True",
                    "PHYSICAL_DELETE= False",
                    "PATH_TRAVERSAL_PROTECTION= True",
                    "STREAMING_UPLOAD= True",
                    "CAD_PARSER= False",
                    "VIEWER= False",
                    "S3= False",
                    "PYTHON_MULTIPART_REQUIRED= True",
                    f"PYTHON_MULTIPART_INSTALLED= {multipart_installed}",
                    f"BACKUP_DIR= {backup_dir}",
                    f"REPORT= {REPORT}",
                    f"JSON= {JSON_REPORT}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        JSON_REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        print("AST_OK=", ok)
        print("TABLE_ARQUIVOS_TECNICOS= True")
        print("ORM_TABLE_CREATED= True")
        print("DATABASE_CHANGED=", database["database_changed"])
        print("DATABASE_ALREADY_MIGRATED=", database["database_already_migrated"])
        print("BACKED_UP=", backed_up)
        print("CHANGED_FILES=", len(changed))
        print("LOCAL_FILESYSTEM= True")
        print("MAX_SIZE_MB= 100")
        print("SHA256= True")
        print("LOGICAL_UNLINK= True")
        print("PHYSICAL_DELETE= False")
        print("PATH_TRAVERSAL_PROTECTION= True")
        print("STREAMING_UPLOAD= True")
        print("CAD_PARSER= False")
        print("VIEWER= False")
        print("S3= False")
        print("PYTHON_MULTIPART_REQUIRED= True")
        print("PYTHON_MULTIPART_INSTALLED=", multipart_installed)
        print("BACKUP_DIR=", backup_dir)
        print("REPORT=", REPORT)
        print("JSON=", JSON_REPORT)

        if not ok:
            print("ERRO: validação AST do D16 falhou.")
            return 40

        print("D16_ARQUIVOS_TECNICOS_APPLIED= True")
        if not multipart_installed:
            print("DEPENDENCY_ACTION_REQUIRED= True")
            print("Execute: python -m pip install -r requirements.txt")
        else:
            print("DEPENDENCY_ACTION_REQUIRED= False")

        return 0

    except Exception as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}")
        print(f"BACKUP_DIR= {backup_dir}")
        print("O banco foi protegido por backup antes da tentativa.")
        print("Os arquivos do projeto podem não ter sido aplicados.")
        return 50


if __name__ == "__main__":
    raise SystemExit(main())
