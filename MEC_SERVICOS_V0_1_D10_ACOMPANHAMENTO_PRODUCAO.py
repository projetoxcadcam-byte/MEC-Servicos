
from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = "MEC-SERVICOS-V0.1-D10-ACOMPANHAMENTO-PRODUCAO-2026-10-01"
BACKUP_ROOT = ROOT / "_mec_backups"

FILES = {
    "model": ROOT / "backend/app/models/etapa_producao.py",
    "repository": ROOT / "backend/app/repositories/etapa_producao.py",
    "schema": ROOT / "backend/app/schemas/etapa_producao.py",
    "service": ROOT / "backend/app/services/etapa_producao.py",
    "route": ROOT / "backend/app/api/rotas/etapas_producao.py",
    "models_init": ROOT / "backend/app/models/__init__.py",
    "router": ROOT / "backend/app/api/roteador.py",
    "test": ROOT / "tests/test_acompanhamento_producao.py",
}

MODEL = '''from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class EtapaProducao(Base):
    __tablename__ = "etapas_producao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(
        ForeignKey("ordens_servico.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    empresa_fornecedora_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id"),
        nullable=False,
        index=True,
    )
    etapa: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
'''

REPOSITORY = '''from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.etapa_producao import EtapaProducao


class RepositorioEtapaProducao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, item: EtapaProducao) -> EtapaProducao:
        self.banco.add(item)
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def listar_por_ordem(self, ordem_servico_id: int) -> list[EtapaProducao]:
        stmt = (
            select(EtapaProducao)
            .where(EtapaProducao.ordem_servico_id == ordem_servico_id)
            .order_by(EtapaProducao.id)
        )
        return list(self.banco.scalars(stmt).all())

    def atual(self, ordem_servico_id: int) -> EtapaProducao | None:
        stmt = (
            select(EtapaProducao)
            .where(EtapaProducao.ordem_servico_id == ordem_servico_id)
            .order_by(EtapaProducao.id.desc())
            .limit(1)
        )
        return self.banco.scalar(stmt)
'''

SCHEMA = '''from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


ETAPAS_PRODUCAO = (
    "aguardando_material",
    "em_usinagem",
    "em_solda_dobra",
    "em_acabamento",
    "pronto_para_envio",
)


class EtapaProducaoCriacao(BaseModel):
    empresa_fornecedora_id: int = Field(gt=0)
    etapa: str
    observacoes: str | None = None

    @field_validator("etapa")
    @classmethod
    def validar_etapa(cls, valor: str) -> str:
        valor = valor.strip().lower()
        if valor not in ETAPAS_PRODUCAO:
            raise ValueError(
                "etapa_invalida; valores permitidos: "
                + ", ".join(ETAPAS_PRODUCAO)
            )
        return valor


class EtapaProducaoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem_servico_id: int
    empresa_fornecedora_id: int
    etapa: str
    observacoes: str | None
    criada_em: datetime


class AcompanhamentoProducaoLeitura(BaseModel):
    ordem_servico_id: int
    etapa_atual: str | None
    historico: list[EtapaProducaoLeitura]
'''

SERVICE = '''from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.repositories.etapa_producao import RepositorioEtapaProducao
from backend.app.schemas.etapa_producao import (
    AcompanhamentoProducaoLeitura,
    EtapaProducaoCriacao,
)


class OrdemServicoNaoEncontradaParaProducao(Exception):
    pass


class EmpresaFornecedoraNaoPodeAtualizarProducao(Exception):
    pass


class OrdemServicoNaoPodeAtualizarProducao(Exception):
    pass


class ServicoEtapaProducao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioEtapaProducao(banco)

    def _ordem(self, ordem_servico_id: int) -> OrdemServico:
        item = self.banco.get(OrdemServico, ordem_servico_id)
        if item is None:
            raise OrdemServicoNaoEncontradaParaProducao
        return item

    @staticmethod
    def _fornecedor_pode_operar(
        ordem: OrdemServico,
        empresa_fornecedora_id: int,
    ) -> None:
        if ordem.empresa_fornecedora_id != empresa_fornecedora_id:
            raise EmpresaFornecedoraNaoPodeAtualizarProducao

    def registrar(
        self,
        ordem_servico_id: int,
        dados: EtapaProducaoCriacao,
    ) -> EtapaProducao:
        ordem = self._ordem(ordem_servico_id)
        self._fornecedor_pode_operar(
            ordem,
            dados.empresa_fornecedora_id,
        )

        if ordem.status in {"concluida", "cancelada"}:
            raise OrdemServicoNaoPodeAtualizarProducao

        item = EtapaProducao(
            ordem_servico_id=ordem.id,
            empresa_fornecedora_id=ordem.empresa_fornecedora_id,
            etapa=dados.etapa,
            observacoes=dados.observacoes,
        )
        return self.repositorio.criar(item)

    def acompanhamento(
        self,
        ordem_servico_id: int,
    ) -> AcompanhamentoProducaoLeitura:
        ordem = self._ordem(ordem_servico_id)
        historico = self.repositorio.listar_por_ordem(ordem.id)
        atual = historico[-1].etapa if historico else None
        return AcompanhamentoProducaoLeitura(
            ordem_servico_id=ordem.id,
            etapa_atual=atual,
            historico=historico,
        )

    def listar(self, ordem_servico_id: int) -> list[EtapaProducao]:
        ordem = self._ordem(ordem_servico_id)
        return self.repositorio.listar_por_ordem(ordem.id)
'''

ROUTE = '''from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.etapa_producao import (
    AcompanhamentoProducaoLeitura,
    EtapaProducaoCriacao,
    EtapaProducaoLeitura,
)
from backend.app.services.etapa_producao import (
    EmpresaFornecedoraNaoPodeAtualizarProducao,
    OrdemServicoNaoEncontradaParaProducao,
    OrdemServicoNaoPodeAtualizarProducao,
    ServicoEtapaProducao,
)

roteador = APIRouter(tags=["acompanhamento de produção"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "/ordens-servico/{ordem_servico_id}/etapas-producao",
    response_model=EtapaProducaoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def registrar_etapa_producao(
    ordem_servico_id: int,
    dados: EtapaProducaoCriacao,
    banco: SessaoBanco,
) -> EtapaProducaoLeitura:
    try:
        return ServicoEtapaProducao(banco).registrar(
            ordem_servico_id,
            dados,
        )
    except OrdemServicoNaoEncontradaParaProducao as exc:
        raise HTTPException(
            status_code=404,
            detail="ordem_servico_nao_encontrada",
        ) from exc
    except EmpresaFornecedoraNaoPodeAtualizarProducao as exc:
        raise HTTPException(
            status_code=403,
            detail="empresa_nao_e_fornecedora_da_ordem_servico",
        ) from exc
    except OrdemServicoNaoPodeAtualizarProducao as exc:
        raise HTTPException(
            status_code=409,
            detail="ordem_servico_nao_pode_atualizar_producao",
        ) from exc


@roteador.get(
    "/ordens-servico/{ordem_servico_id}/etapas-producao",
    response_model=list[EtapaProducaoLeitura],
)
def listar_etapas_producao(
    ordem_servico_id: int,
    banco: SessaoBanco,
) -> list[EtapaProducaoLeitura]:
    try:
        return ServicoEtapaProducao(banco).listar(ordem_servico_id)
    except OrdemServicoNaoEncontradaParaProducao as exc:
        raise HTTPException(
            status_code=404,
            detail="ordem_servico_nao_encontrada",
        ) from exc


@roteador.get(
    "/ordens-servico/{ordem_servico_id}/acompanhamento-producao",
    response_model=AcompanhamentoProducaoLeitura,
)
def obter_acompanhamento_producao(
    ordem_servico_id: int,
    banco: SessaoBanco,
) -> AcompanhamentoProducaoLeitura:
    try:
        return ServicoEtapaProducao(banco).acompanhamento(
            ordem_servico_id,
        )
    except OrdemServicoNaoEncontradaParaProducao as exc:
        raise HTTPException(
            status_code=404,
            detail="ordem_servico_nao_encontrada",
        ) from exc
'''

TEST = '''from __future__ import annotations

from decimal import Decimal
from itertools import count

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.material import Material
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.principal import app


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessaoTeste = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base.metadata.create_all(bind=engine)


def banco_teste():
    banco = SessaoTeste()
    try:
        yield banco
    finally:
        banco.close()


app.dependency_overrides[obter_banco] = banco_teste
cliente_http = TestClient(app)


_SEQUENCIA = count(1)


def preparar_ordem():
    numero = next(_SEQUENCIA)
    banco = SessaoTeste()

    cliente = Empresa(
        razao_social="Cliente D10",
        documento=f"D10-CLIENTE-{numero}",
        tipo_empresa="cliente",
    )
    fornecedor = Empresa(
        razao_social="Fornecedor D10",
        documento=f"D10-FORNECEDOR-{numero}",
        tipo_empresa="fornecedor",
    )
    processo = ProcessoFabricacao(
        codigo=f"usinagem_cnc_d10_{numero}",
        nome="Usinagem CNC",
        descricao="Usinagem D10.",
    )
    material = Material(
        codigo=f"aluminio_6061_d10_{numero}",
        nome="Aluminio 6061 D10",
        familia="Aluminio",
        especificacao="Liga D10.",
    )
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()
    banco.refresh(cliente)
    banco.refresh(fornecedor)
    banco.refresh(processo)
    banco.refresh(material)

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=100,
        dimensao_y_maxima_mm=100,
        dimensao_z_maxima_mm=100,
        tolerancia_requerida_mm=0.02,
        quantidade=5,
        observacoes="Solicitacao D10.",
        status="aberta",
    )
    banco.add(solicitacao)
    banco.commit()
    banco.refresh(solicitacao)

    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"),
        prazo_dias=10,
        validade_dias=10,
        observacoes="Cotacao D10.",
        status="aceita",
        decidida_por_empresa_id=cliente.id,
    )
    banco.add(cotacao)
    banco.commit()
    banco.refresh(cotacao)

    contratacao = ContratacaoServico(
        solicitacao_id=solicitacao.id,
        cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"),
        prazo_dias=10,
        observacoes="Contratacao D10.",
        status="ativa",
    )
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)

    ordem = OrdemServico(
        contratacao_id=contratacao.id,
        solicitacao_id=solicitacao.id,
        cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id,
        empresa_fornecedora_id=fornecedor.id,
        processo_id=processo.id,
        material_id=material.id,
        quantidade=5,
        valor_total=Decimal("5000.00"),
        prazo_dias=10,
        status="em_execucao",
    )
    banco.add(ordem)
    banco.commit()
    banco.refresh(ordem)

    ids = (cliente.id, fornecedor.id, ordem.id)
    banco.close()
    return ids


def test_registrar_etapa_e_listar_historico():
    _, fornecedor_id, ordem_id = preparar_ordem()

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "etapa": "aguardando_material",
            "observacoes": "Material em compra.",
        },
    )
    assert resposta.status_code == 201
    assert resposta.json()["etapa"] == "aguardando_material"

    resposta = cliente_http.get(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
    )
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_acompanhamento_retorna_etapa_atual():
    _, fornecedor_id, ordem_id = preparar_ordem()

    for etapa in ("aguardando_material", "em_usinagem"):
        resposta = cliente_http.post(
            f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
            json={
                "empresa_fornecedora_id": fornecedor_id,
                "etapa": etapa,
            },
        )
        assert resposta.status_code == 201

    resposta = cliente_http.get(
        f"/api/v1/ordens-servico/{ordem_id}/acompanhamento-producao",
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["etapa_atual"] == "em_usinagem"
    assert len(corpo["historico"]) == 2


def test_fornecedor_incorreto_nao_pode_atualizar():
    _, fornecedor_id, ordem_id = preparar_ordem()

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id + 1000,
            "etapa": "em_usinagem",
        },
    )
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "empresa_nao_e_fornecedora_da_ordem_servico"


def test_etapa_invalida_e_rejeitada():
    _, fornecedor_id, ordem_id = preparar_ordem()

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "etapa": "etapa_inexistente",
        },
    )
    assert resposta.status_code == 422


def test_ordem_concluida_nao_recebe_nova_etapa():
    _, fornecedor_id, ordem_id = preparar_ordem()

    banco = SessaoTeste()
    ordem = banco.get(OrdemServico, ordem_id)
    ordem.status = "concluida"
    banco.commit()
    banco.close()

    resposta = cliente_http.post(
        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "etapa": "pronto_para_envio",
        },
    )
    assert resposta.status_code == 409
'''


def backup(path: Path, backup_dir: Path) -> None:
    if path.exists():
        alvo = backup_dir / path.relative_to(ROOT)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, alvo)


def main() -> int:
    required = [
        ROOT / "backend/app/models/ordem_servico.py",
        ROOT / "backend/app/services/ordem_servico.py",
        ROOT / "backend/app/api/rotas/ordens_servico.py",
        ROOT / "backend/app/api/roteador.py",
        ROOT / "backend/app/models/__init__.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        print("ERRO: baseline D9 ausente:")
        for item in missing:
            print("MISSING=", item)
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D10_ACOMPANHAMENTO_PRODUCAO_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        changed = []

        new_files = {
            FILES["model"]: MODEL,
            FILES["repository"]: REPOSITORY,
            FILES["schema"]: SCHEMA,
            FILES["service"]: SERVICE,
            FILES["route"]: ROUTE,
            FILES["test"]: TEST,
        }

        for path, content in new_files.items():
            if path.exists():
                backup(path, backup_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))

        # Registrar o novo modelo no pacote de modelos.
        path = FILES["models_init"]
        text = path.read_text(encoding="utf-8")
        original = text
        import_line = "from backend.app.models.etapa_producao import EtapaProducao"
        if import_line not in text:
            lines = text.splitlines()
            idx = 0
            for i, line in enumerate(lines):
                if line.startswith("from backend.app.models."):
                    idx = i + 1
            lines.insert(idx, import_line)
            text = "\n".join(lines) + "\n"
        if '"EtapaProducao"' not in text:
            text = text.replace(
                '    "CotacaoFornecedor",\n',
                '    "CotacaoFornecedor",\n    "EtapaProducao",\n',
            )
        if text != original:
            backup(path, backup_dir)
            path.write_text(text, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))

        # Registrar o novo router.
        path = FILES["router"]
        text = path.read_text(encoding="utf-8")
        original = text
        import_line = (
            "from backend.app.api.rotas.etapas_producao import "
            "roteador as roteador_etapas_producao"
        )
        if import_line not in text:
            lines = text.splitlines()
            idx = 0
            for i, line in enumerate(lines):
                if line.startswith("from backend.app.api.rotas."):
                    idx = i + 1
            lines.insert(idx, import_line)
            text = "\n".join(lines) + "\n"

        include_line = "roteador_api.include_router(roteador_etapas_producao)"
        if include_line not in text:
            text = text.rstrip() + "\n" + include_line + "\n"

        if text != original:
            backup(path, backup_dir)
            path.write_text(text, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))

        # AST de todos os arquivos tocados.
        for path in [
            *new_files.keys(),
            FILES["models_init"],
            FILES["router"],
        ]:
            ast.parse(path.read_text(encoding="utf-8"))

        # Preflight real do SQLAlchemy.
        import sys
        sys.path.insert(0, str(ROOT))

        from sqlalchemy import create_engine
        from backend.app.database.base import Base
        import backend.app.models  # noqa: F401
        import backend.app.models.etapa_producao  # noqa: F401

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
        )
        try:
            Base.metadata.create_all(bind=engine)
            tables = set(Base.metadata.tables)
            if "ordens_servico" not in tables:
                raise RuntimeError("Tabela ordens_servico não está no metadata.")
            if "etapas_producao" not in tables:
                raise RuntimeError("Tabela etapas_producao não está no metadata.")
        finally:
            engine.dispose()

        report = ROOT / "MEC_SERVICOS_V0_1_D10_ACOMPANHAMENTO_PRODUCAO_RELATORIO.txt"
        report_json = ROOT / "MEC_SERVICOS_V0_1_D10_ACOMPANHAMENTO_PRODUCAO.json"

        payload = {
            "revision": REVISION,
            "ast_ok": True,
            "metadata_preflight_ok": True,
            "tables": ["ordens_servico", "etapas_producao"],
            "stages": [
                "aguardando_material",
                "em_usinagem",
                "em_solda_dobra",
                "em_acabamento",
                "pronto_para_envio",
            ],
            "supplier_only_update": True,
            "history_preserved": True,
            "changed": changed,
            "backup_dir": str(backup_dir),
        }

        report_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        report.write_text(
            "\n".join(
                [
                    "Plataforma de Serviços Mecânicos — V0.1 D10 Acompanhamento de Produção",
                    f"REVISION= {REVISION}",
                    f"ROOT= {ROOT}",
                    "AST_OK= True",
                    "METADATA_PREFLIGHT_OK= True",
                    "TABLE_ORDEM_SERVICO= ordens_servico",
                    "TABLE_ETAPAS_PRODUCAO= etapas_producao",
                    "SUPPLIER_ONLY_UPDATE= True",
                    "HISTORY_PRESERVED= True",
                    f"CHANGED= {len(changed)}",
                    f"BACKUP_DIR= {backup_dir}",
                    f"REPORT= {report}",
                    f"JSON= {report_json}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        print("Plataforma de Serviços Mecânicos — V0.1 D10 Acompanhamento de Produção")
        print("REVISION=", REVISION)
        print("ROOT=", ROOT)
        print("AST_OK= True")
        print("METADATA_PREFLIGHT_OK= True")
        print("TABLE_ORDEM_SERVICO= ordens_servico")
        print("TABLE_ETAPAS_PRODUCAO= etapas_producao")
        print("SUPPLIER_ONLY_UPDATE= True")
        print("HISTORY_PRESERVED= True")
        print("CHANGED=", len(changed))
        print("BACKUP_DIR=", backup_dir)
        print("REPORT=", report)
        print("JSON=", report_json)
        return 0

    except Exception as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}")
        print("BACKUP_DIR=", backup_dir)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
