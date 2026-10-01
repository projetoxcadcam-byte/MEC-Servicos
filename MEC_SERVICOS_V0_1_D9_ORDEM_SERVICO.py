from __future__ import annotations

import ast
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = "MEC-SERVICOS-V0.1-D9-ORDEM-SERVICO-2026-10-01"
BACKUP_ROOT = ROOT / "_mec_backups"
DB_PATH = ROOT / "data" / "mec_servicos.db"

MODEL = """
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class OrdemServico(Base):
    __tablename__ = "ordens_servico"
    __table_args__ = (
        UniqueConstraint("contratacao_id", name="uq_ordem_servico_contratacao"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contratacao_id: Mapped[int] = mapped_column(ForeignKey("contratacoes_servico.id"), nullable=False, index=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes_servico.id"), nullable=False, index=True)
    cotacao_id: Mapped[int] = mapped_column(ForeignKey("cotacoes_fornecedor.id"), nullable=False, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    empresa_fornecedora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id"), nullable=False, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materiais.id"), nullable=False, index=True)

    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="aberta", index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
""".lstrip()

SCHEMA = """
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrdemServicoCriacao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)


class OrdemServicoAcao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    observacoes: str | None = None


class OrdemServicoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contratacao_id: int
    solicitacao_id: int
    cotacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    processo_id: int
    material_id: int
    quantidade: int
    valor_total: Decimal
    prazo_dias: int
    status: str
    observacoes: str | None
    criada_em: datetime
    iniciada_em: datetime | None
    concluida_em: datetime | None
    cancelada_em: datetime | None
""".lstrip()

REPOSITORY = """
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.ordem_servico import OrdemServico


class RepositorioOrdemServico:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, ordem: OrdemServico) -> OrdemServico:
        self.banco.add(ordem)
        self.banco.commit()
        self.banco.refresh(ordem)
        return ordem

    def buscar(self, ordem_id: int) -> OrdemServico | None:
        return self.banco.get(OrdemServico, ordem_id)

    def buscar_por_contratacao(self, contratacao_id: int) -> OrdemServico | None:
        stmt = select(OrdemServico).where(OrdemServico.contratacao_id == contratacao_id)
        return self.banco.scalar(stmt)

    def listar(self) -> list[OrdemServico]:
        stmt = select(OrdemServico).order_by(OrdemServico.id)
        return list(self.banco.scalars(stmt).all())
""".lstrip()

SERVICE = """
from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.ordem_servico import RepositorioOrdemServico
from backend.app.schemas.ordem_servico import OrdemServicoAcao, OrdemServicoCriacao


class OrdemServicoNaoEncontrada(Exception):
    pass


class ContratacaoNaoEncontradaParaOS(Exception):
    pass


class ContratacaoNaoAtiva(Exception):
    pass


class EmpresaNaoPodeOperarOS(Exception):
    pass


class OrdemServicoDuplicada(Exception):
    pass


class OrdemServicoNaoPodeSerIniciada(Exception):
    pass


class OrdemServicoNaoPodeSerConcluida(Exception):
    pass


class OrdemServicoNaoPodeSerCancelada(Exception):
    pass


class ServicoOrdemServico:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioOrdemServico(banco)

    def _contratacao(self, contratacao_id: int) -> ContratacaoServico:
        item = self.banco.get(ContratacaoServico, contratacao_id)
        if item is None:
            raise ContratacaoNaoEncontradaParaOS
        return item

    @staticmethod
    def _cliente_contratacao(item: ContratacaoServico, empresa_id: int) -> None:
        if item.empresa_cliente_id != empresa_id:
            raise EmpresaNaoPodeOperarOS

    @staticmethod
    def _cliente_ordem(item: OrdemServico, empresa_id: int) -> None:
        if item.empresa_cliente_id != empresa_id:
            raise EmpresaNaoPodeOperarOS

    def criar(self, contratacao_id: int, dados: OrdemServicoCriacao) -> OrdemServico:
        contratacao = self._contratacao(contratacao_id)
        self._cliente_contratacao(contratacao, dados.empresa_cliente_id)

        if contratacao.status != "ativa":
            raise ContratacaoNaoAtiva

        if self.repositorio.buscar_por_contratacao(contratacao_id) is not None:
            raise OrdemServicoDuplicada

        solicitacao = self.banco.get(SolicitacaoServico, contratacao.solicitacao_id)
        if solicitacao is None:
            raise ContratacaoNaoEncontradaParaOS

        ordem = OrdemServico(
            contratacao_id=contratacao.id,
            solicitacao_id=contratacao.solicitacao_id,
            cotacao_id=contratacao.cotacao_id,
            empresa_cliente_id=contratacao.empresa_cliente_id,
            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,
            processo_id=solicitacao.processo_id,
            material_id=solicitacao.material_id,
            quantidade=solicitacao.quantidade,
            valor_total=contratacao.valor_total,
            prazo_dias=contratacao.prazo_dias,
            status="aberta",
            observacoes=contratacao.observacoes,
        )
        try:
            return self.repositorio.criar(ordem)
        except IntegrityError as exc:
            self.banco.rollback()
            raise OrdemServicoDuplicada from exc

    def obter(self, ordem_id: int) -> OrdemServico:
        item = self.repositorio.buscar(ordem_id)
        if item is None:
            raise OrdemServicoNaoEncontrada
        return item

    def listar(self) -> list[OrdemServico]:
        return self.repositorio.listar()

    def iniciar(self, ordem_id: int, dados: OrdemServicoAcao) -> OrdemServico:
        item = self.obter(ordem_id)
        self._cliente_ordem(item, dados.empresa_cliente_id)
        if item.status != "aberta":
            raise OrdemServicoNaoPodeSerIniciada
        item.status = "em_execucao"
        item.iniciada_em = datetime.utcnow()
        if dados.observacoes is not None:
            item.observacoes = dados.observacoes
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def concluir(self, ordem_id: int, dados: OrdemServicoAcao) -> OrdemServico:
        item = self.obter(ordem_id)
        self._cliente_ordem(item, dados.empresa_cliente_id)
        if item.status != "em_execucao":
            raise OrdemServicoNaoPodeSerConcluida
        item.status = "concluida"
        item.concluida_em = datetime.utcnow()
        if dados.observacoes is not None:
            item.observacoes = dados.observacoes
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def cancelar(self, ordem_id: int, dados: OrdemServicoAcao) -> OrdemServico:
        item = self.obter(ordem_id)
        self._cliente_ordem(item, dados.empresa_cliente_id)
        if item.status in {"concluida", "cancelada"}:
            raise OrdemServicoNaoPodeSerCancelada
        item.status = "cancelada"
        item.cancelada_em = datetime.utcnow()
        if dados.observacoes is not None:
            item.observacoes = dados.observacoes
        self.banco.commit()
        self.banco.refresh(item)
        return item
""".lstrip()

ROUTE = """
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.ordem_servico import OrdemServicoAcao, OrdemServicoCriacao, OrdemServicoLeitura
from backend.app.services.ordem_servico import (
    ContratacaoNaoAtiva,
    ContratacaoNaoEncontradaParaOS,
    EmpresaNaoPodeOperarOS,
    OrdemServicoDuplicada,
    OrdemServicoNaoEncontrada,
    OrdemServicoNaoPodeSerCancelada,
    OrdemServicoNaoPodeSerConcluida,
    OrdemServicoNaoPodeSerIniciada,
    ServicoOrdemServico,
)

roteador = APIRouter(prefix="/", tags=["ordens de serviço"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post("/contratacoes/{contratacao_id}/ordem-servico", response_model=OrdemServicoLeitura, status_code=status.HTTP_201_CREATED)
def criar_ordem_servico(contratacao_id: int, dados: OrdemServicoCriacao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).criar(contratacao_id, dados)
    except ContratacaoNaoEncontradaParaOS as exc:
        raise HTTPException(status_code=404, detail="contratacao_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_contratacao") from exc
    except ContratacaoNaoAtiva as exc:
        raise HTTPException(status_code=409, detail="contratacao_nao_esta_ativa") from exc
    except OrdemServicoDuplicada as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_ja_cadastrada_para_esta_contratacao") from exc


@roteador.get("/ordens-servico", response_model=list[OrdemServicoLeitura])
def listar_ordens_servico(banco: SessaoBanco) -> list[OrdemServicoLeitura]:
    return ServicoOrdemServico(banco).listar()


@roteador.get("/ordens-servico/{ordem_id}", response_model=OrdemServicoLeitura)
def obter_ordem_servico(ordem_id: int, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).obter(ordem_id)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc


@roteador.post("/ordens-servico/{ordem_id}/iniciar", response_model=OrdemServicoLeitura)
def iniciar_ordem_servico(ordem_id: int, dados: OrdemServicoAcao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).iniciar(ordem_id, dados)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_ordem_servico") from exc
    except OrdemServicoNaoPodeSerIniciada as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_nao_pode_ser_iniciada") from exc


@roteador.post("/ordens-servico/{ordem_id}/concluir", response_model=OrdemServicoLeitura)
def concluir_ordem_servico(ordem_id: int, dados: OrdemServicoAcao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).concluir(ordem_id, dados)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_ordem_servico") from exc
    except OrdemServicoNaoPodeSerConcluida as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_nao_pode_ser_concluida") from exc


@roteador.post("/ordens-servico/{ordem_id}/cancelar", response_model=OrdemServicoLeitura)
def cancelar_ordem_servico(ordem_id: int, dados: OrdemServicoAcao, banco: SessaoBanco) -> OrdemServicoLeitura:
    try:
        return ServicoOrdemServico(banco).cancelar(ordem_id, dados)
    except OrdemServicoNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail="ordem_servico_nao_encontrada") from exc
    except EmpresaNaoPodeOperarOS as exc:
        raise HTTPException(status_code=403, detail="empresa_nao_e_cliente_da_ordem_servico") from exc
    except OrdemServicoNaoPodeSerCancelada as exc:
        raise HTTPException(status_code=409, detail="ordem_servico_nao_pode_ser_cancelada") from exc
""".lstrip()

TEST = """
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.capacidade import CapacidadeTecnica
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.processo import Processo
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import app


def _client() -> tuple[TestClient, Session, object]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessao = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    banco = sessao()
    app.dependency_overrides[obter_banco] = lambda: banco
    return TestClient(app), banco, engine


def _base(banco: Session, sufixo: str):
    cliente = Empresa(razao_social=f"Cliente OS {sufixo}", documento=f"700000000{sufixo}", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social=f"Fornecedor OS {sufixo}", documento=f"800000000{sufixo}", tipo_empresa="fornecedor")
    processo = Processo(codigo=f"usinagem_cnc_os_{sufixo}", nome="Usinagem CNC", descricao="Processo D9.")
    material = Material(codigo=f"aco_os_{sufixo}", nome="Aço D9", familia="Aço", especificacao="Material D9.")
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()

    banco.add(CapacidadeTecnica(empresa_id=fornecedor.id, processo_id=processo.id, dimensao_x_maxima_mm=800, dimensao_y_maxima_mm=500, dimensao_z_maxima_mm=450, tolerancia_minima_mm=0.02))
    banco.add(MaterialFornecedor(empresa_id=fornecedor.id, material_id=material.id, observacoes="Material D9."))
    banco.commit()

    solicitacao = SolicitacaoServico(empresa_cliente_id=cliente.id, processo_id=processo.id, material_id=material.id, dimensao_x_maxima_mm=600, dimensao_y_maxima_mm=400, dimensao_z_maxima_mm=300, tolerancia_requerida_mm=0.02, quantidade=10, observacoes="Solicitação D9.", status="aberta")
    banco.add(solicitacao)
    banco.commit()

    cotacao = CotacaoFornecedor(solicitacao_id=solicitacao.id, empresa_fornecedora_id=fornecedor.id, valor_total=Decimal("12500.00"), prazo_dias=15, validade_dias=10, observacoes="Cotação D9.", status="aceita", criada_em=datetime.utcnow(), encerrada_em=datetime.utcnow(), decidida_por_empresa_id=cliente.id)
    banco.add(cotacao)
    banco.commit()

    contratacao = ContratacaoServico(solicitacao_id=solicitacao.id, cotacao_id=cotacao.id, empresa_cliente_id=cliente.id, empresa_fornecedora_id=fornecedor.id, valor_total=Decimal("12500.00"), prazo_dias=15, observacoes="Contratação D9.", status="ativa", criada_em=datetime.utcnow())
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)
    return cliente, fornecedor, contratacao


def _fim(banco, engine):
    app.dependency_overrides.clear()
    banco.close()
    engine.dispose()


def test_criar_ordem_servico_a_partir_de_contratacao():
    http, banco, engine = _client()
    try:
        cliente, fornecedor, contratacao = _base(banco, "41")
        resposta = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        assert resposta.status_code == 201
        dados = resposta.json()
        assert dados["contratacao_id"] == contratacao.id
        assert dados["empresa_fornecedora_id"] == fornecedor.id
        assert dados["status"] == "aberta"
        assert dados["quantidade"] == 10
    finally:
        _fim(banco, engine)


def test_nao_permite_duas_ordens_para_mesma_contratacao():
    http, banco, engine = _client()
    try:
        cliente, _, contratacao = _base(banco, "42")
        primeira = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        segunda = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        assert primeira.status_code == 201
        assert segunda.status_code == 409
        assert segunda.json()["detail"] == "ordem_servico_ja_cadastrada_para_esta_contratacao"
    finally:
        _fim(banco, engine)


def test_iniciar_concluir_e_obter_ordem_servico():
    http, banco, engine = _client()
    try:
        cliente, _, contratacao = _base(banco, "43")
        criada = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        ordem_id = criada.json()["id"]
        iniciada = http.post(f"/api/v1/ordens-servico/{ordem_id}/iniciar", json={"empresa_cliente_id": cliente.id})
        assert iniciada.status_code == 200
        assert iniciada.json()["status"] == "em_execucao"
        concluida = http.post(f"/api/v1/ordens-servico/{ordem_id}/concluir", json={"empresa_cliente_id": cliente.id})
        assert concluida.status_code == 200
        assert concluida.json()["status"] == "concluida"
        obtida = http.get(f"/api/v1/ordens-servico/{ordem_id}")
        assert obtida.status_code == 200
        assert obtida.json()["status"] == "concluida"
    finally:
        _fim(banco, engine)


def test_empresa_incorreta_nao_pode_operar_ordem():
    http, banco, engine = _client()
    try:
        cliente, fornecedor, contratacao = _base(banco, "44")
        criada = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        ordem_id = criada.json()["id"]
        resposta = http.post(f"/api/v1/ordens-servico/{ordem_id}/iniciar", json={"empresa_cliente_id": fornecedor.id})
        assert resposta.status_code == 403
        assert resposta.json()["detail"] == "empresa_nao_e_cliente_da_ordem_servico"
    finally:
        _fim(banco, engine)


def test_cancelar_ordem_servico():
    http, banco, engine = _client()
    try:
        cliente, _, contratacao = _base(banco, "45")
        criada = http.post(f"/api/v1/contratacoes/{contratacao.id}/ordem-servico", json={"empresa_cliente_id": cliente.id})
        ordem_id = criada.json()["id"]
        cancelada = http.post(f"/api/v1/ordens-servico/{ordem_id}/cancelar", json={"empresa_cliente_id": cliente.id, "observacoes": "Cancelamento D9."})
        assert cancelada.status_code == 200
        assert cancelada.json()["status"] == "cancelada"
        assert cancelada.json()["cancelada_em"] is not None
    finally:
        _fim(banco, engine)
""".lstrip()

FILES = {
    "backend/app/models/ordem_servico.py": MODEL,
    "backend/app/schemas/ordem_servico.py": SCHEMA,
    "backend/app/repositories/ordem_servico.py": REPOSITORY,
    "backend/app/services/ordem_servico.py": SERVICE,
    "backend/app/api/rotas/ordens_servico.py": ROUTE,
    "tests/test_ordens_servico.py": TEST,
}

def backup(path: Path, backup_dir: Path) -> None:
    if not path.exists():
        return
    target = backup_dir / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)

def write_new(path: Path, content: str, backup_dir: Path, changed: list[str], created: list[str]) -> None:
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if old == content:
            return
        backup(path, backup_dir)
        path.write_text(content, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(str(path.relative_to(ROOT)))

def main() -> int:
    changed: list[str] = []
    created: list[str] = []
    backed_up: list[str] = []

    required = [
        "backend/app/models/contratacao.py",
        "backend/app/api/rotas/contratacoes.py",
        "backend/app/api/roteador.py",
        "backend/app/models/__init__.py",
        "backend/app/database/base.py",
        "backend/app/database/sessao.py",
        "backend/app/principal.py",
    ]
    missing = [p for p in required if not (ROOT / p).exists()]
    if missing:
        print("ERRO: baseline D8 incompleto.")
        for item in missing:
            print("  MISSING:", item)
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D9_ORDEM_SERVICO_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        for rel, content in FILES.items():
            before = ROOT / rel
            if before.exists():
                backup(before, backup_dir)
                backed_up.append(rel)
            write_new(before, content, backup_dir, changed, created)

        models_init = ROOT / "backend/app/models/__init__.py"
        text = models_init.read_text(encoding="utf-8")
        line = "from backend.app.models.ordem_servico import OrdemServico"
        if line not in text:
            backup(models_init, backup_dir)
            models_init.write_text(text.rstrip() + "\n" + line + "\n", encoding="utf-8")
            changed.append(str(models_init.relative_to(ROOT)))

        router = ROOT / "backend/app/api/roteador.py"
        text = router.read_text(encoding="utf-8")
        import_line = "from backend.app.api.rotas.ordens_servico import roteador as ordens_servico_router"
        if import_line not in text:
            backup(router, backup_dir)
            lines = text.splitlines()
            idx = 0
            for i, line_text in enumerate(lines):
                if line_text.startswith("from backend.app.api.rotas."):
                    idx = i + 1
            lines.insert(idx, import_line)
            text = "\n".join(lines) + "\n"
            marker = "contratacoes_router"
            if marker in text and "ordens_servico_router" not in text.split(marker, 1)[1]:
                candidates = [
                    "api_router.include_router(contratacoes_router)",
                    "roteador.include_router(contratacoes_router)",
                ]
                for candidate in candidates:
                    if candidate in text:
                        text = text.replace(candidate, candidate + "\n" + candidate.replace("contratacoes_router", "ordens_servico_router"), 1)
                        break
                else:
                    raise RuntimeError("Não encontrei o include_router das contratações.")
            router.write_text(text, encoding="utf-8")
            changed.append(str(router.relative_to(ROOT)))

        readme = ROOT / "README.md"
        readme_text = readme.read_text(encoding="utf-8")
        if "V0.1 D9 — Ordem de Serviço" not in readme_text:
            backup(readme, backup_dir)
            readme.write_text(
                readme_text.rstrip()
                + "\n\n## V0.1 D9 — Ordem de Serviço\n\n"
                + "A contratação ativa pode gerar uma ordem de serviço única, com ciclo `aberta`, `em_execucao`, `concluida` ou `cancelada`.\n",
                encoding="utf-8",
            )
            changed.append(str(readme.relative_to(ROOT)))

        docs = ROOT / "docs/README.md"
        docs_text = docs.read_text(encoding="utf-8")
        if "D9 — Ordem de Serviço" not in docs_text:
            backup(docs, backup_dir)
            docs.write_text(
                docs_text.rstrip()
                + "\n\n## D9 — Ordem de Serviço\n\n"
                + "O D9 cria a ordem a partir da contratação ativa e prepara o acompanhamento da execução.\n"
                + "Próxima evolução: marcos de produção como matéria-prima, usinagem/corte, tratamento e envio.\n",
                encoding="utf-8",
            )
            changed.append(str(docs.relative_to(ROOT)))

        ast_targets = [ROOT / p for p in FILES]
        ast_targets += [models_init, router]
        for path in ast_targets:
            ast.parse(path.read_text(encoding="utf-8"))

        database_changed = False
        database_already_migrated = False
        if DB_PATH.exists():
            db_backup = backup_dir / DB_PATH.relative_to(ROOT)
            db_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DB_PATH, db_backup)
            backed_up.append(str(DB_PATH.relative_to(ROOT)))

            conn = sqlite3.connect(DB_PATH)
            try:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ordens_servico'"
                ).fetchone()
            finally:
                conn.close()

            if exists:
                database_already_migrated = True
            else:
                from backend.app.database.base import Base
                from backend.app.database.sessao import engine
                import backend.app.models.ordem_servico  # noqa: F401
                Base.metadata.create_all(bind=engine)
                database_changed = True

        report_json = ROOT / "MEC_SERVICOS_V0_1_D9_ORDEM_SERVICO.json"
        report_txt = ROOT / "MEC_SERVICOS_V0_1_D9_ORDEM_SERVICO_RELATORIO.txt"

        payload = {
            "revision": REVISION,
            "files_ok": True,
            "ast_ok": True,
            "created": created,
            "changed": changed,
            "backed_up": backed_up,
            "database_changed": database_changed,
            "database_already_migrated": database_already_migrated,
            "new_table": "ordens_servico",
            "statuses": ["aberta", "em_execucao", "concluida", "cancelada"],
            "endpoints": [
                "POST /api/v1/contratacoes/{contratacao_id}/ordem-servico",
                "GET /api/v1/ordens-servico",
                "GET /api/v1/ordens-servico/{ordem_id}",
                "POST /api/v1/ordens-servico/{ordem_id}/iniciar",
                "POST /api/v1/ordens-servico/{ordem_id}/concluir",
                "POST /api/v1/ordens-servico/{ordem_id}/cancelar",
            ],
        }
        report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_txt.write_text(
            "\n".join([
                "Plataforma de Serviços Mecânicos — V0.1 D9 Ordem de Serviço",
                f"REVISION= {REVISION}",
                f"ROOT= {ROOT}",
                "FILES_OK= True",
                "AST_OK= True",
                f"CREATED= {len(created)}",
                f"CHANGED= {len(changed)}",
                f"BACKED_UP= {len(backed_up)}",
                f"DATABASE_CHANGED= {database_changed}",
                f"DATABASE_ALREADY_MIGRATED= {database_already_migrated}",
                f"BACKUP_DIR= {backup_dir}",
                f"REPORT= {report_txt}",
                f"JSON= {report_json}",
                "D9_ORDEM_SERVICO_APPLIED= True",
                "ORDEM_SERVICO_PREPARADA= True",
                "EXECUCAO_PREPARADA= True",
                "CONCLUSAO_PREPARADA= True",
                "CANCELAMENTO_PREPARADO= True",
            ]) + "\n",
            encoding="utf-8",
        )

        print("Plataforma de Serviços Mecânicos — V0.1 D9 Ordem de Serviço")
        print("REVISION=", REVISION)
        print("ROOT=", ROOT)
        print("FILES_OK= True")
        print("AST_OK= True")
        print("CREATED=", len(created))
        print("CHANGED=", len(changed))
        print("BACKED_UP=", len(backed_up))
        print("DATABASE_CHANGED=", database_changed)
        print("DATABASE_ALREADY_MIGRATED=", database_already_migrated)
        print("BACKUP_DIR=", backup_dir)
        print("REPORT=", report_txt)
        print("JSON=", report_json)
        print("D9_ORDEM_SERVICO_APPLIED= True")
        print("ORDEM_SERVICO_PREPARADA= True")
        print("EXECUCAO_PREPARADA= True")
        print("CONCLUSAO_PREPARADA= True")
        print("CANCELAMENTO_PREPARADO= True")
        return 0

    except Exception as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}")
        print(f"BACKUP_DIR= {backup_dir}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
