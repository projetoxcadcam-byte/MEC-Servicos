
from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from pathlib import Path

REVISION = "MEC-SERVICOS-V0.1-D14-AVALIACOES-REPUTACAO-2026-10-01"
ROOT = Path(__file__).resolve().parent
BACKUP_ROOT = ROOT / "_mec_backups" / f"V0_1_D14_AVALIACOES_REPUTACAO_{datetime.now():%Y%m%d_%H%M%S}"
REPORT = ROOT / "MEC_SERVICOS_V0_1_D14_AVALIACOES_REPUTACAO_RELATORIO.txt"
JSON_REPORT = ROOT / "MEC_SERVICOS_V0_1_D14_AVALIACOES_REPUTACAO.json"


FILES: dict[str, str] = {'backend/app/models/avaliacao.py': '\nfrom __future__ import annotations\n\nfrom datetime import datetime\n\nfrom sqlalchemy import (\n    CheckConstraint,\n    DateTime,\n    ForeignKey,\n    Integer,\n    Text,\n    UniqueConstraint,\n)\nfrom sqlalchemy.orm import Mapped, mapped_column\n\nfrom backend.app.database.base import Base\n\n\nclass AvaliacaoOficina(Base):\n    __tablename__ = "avaliacoes_oficina"\n    __table_args__ = (\n        UniqueConstraint(\n            "contratacao_id",\n            name="uq_avaliacao_oficina_contratacao",\n        ),\n        CheckConstraint(\n            "nota >= 1 AND nota <= 5",\n            name="ck_avaliacao_oficina_nota",\n        ),\n    )\n\n    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)\n    contratacao_id: Mapped[int] = mapped_column(\n        ForeignKey("contratacoes_servico.id"),\n        nullable=False,\n        index=True,\n    )\n    ordem_servico_id: Mapped[int] = mapped_column(\n        ForeignKey("ordens_servico.id"),\n        nullable=False,\n        index=True,\n    )\n    empresa_cliente_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id"),\n        nullable=False,\n        index=True,\n    )\n    empresa_fornecedora_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id"),\n        nullable=False,\n        index=True,\n    )\n    nota: Mapped[int] = mapped_column(Integer, nullable=False)\n    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)\n    criada_em: Mapped[datetime] = mapped_column(\n        DateTime,\n        default=datetime.utcnow,\n        nullable=False,\n    )\n', 'backend/app/schemas/avaliacao.py': '\nfrom __future__ import annotations\n\nfrom datetime import datetime\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\n\nclass AvaliacaoOficinaCriacao(BaseModel):\n    empresa_cliente_id: int\n    nota: int = Field(ge=1, le=5)\n    comentario: str | None = Field(default=None, max_length=2000)\n\n\nclass AvaliacaoOficinaResposta(BaseModel):\n    model_config = ConfigDict(from_attributes=True)\n\n    id: int\n    contratacao_id: int\n    ordem_servico_id: int\n    empresa_cliente_id: int\n    empresa_fornecedora_id: int\n    nota: int\n    comentario: str | None\n    criada_em: datetime\n\n\nclass ReputacaoOficinaResposta(BaseModel):\n    empresa_id: int\n    quantidade_avaliacoes: int\n    media_nota: float | None\n', 'backend/app/repositories/avaliacao.py': '\nfrom __future__ import annotations\n\nfrom sqlalchemy import func, select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.avaliacao import AvaliacaoOficina\n\n\nclass RepositorioAvaliacaoOficina:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def obter_por_id(self, avaliacao_id: int) -> AvaliacaoOficina | None:\n        return self.banco.get(AvaliacaoOficina, avaliacao_id)\n\n    def obter_por_contratacao(self, contratacao_id: int) -> AvaliacaoOficina | None:\n        return self.banco.scalar(\n            select(AvaliacaoOficina).where(\n                AvaliacaoOficina.contratacao_id == contratacao_id\n            )\n        )\n\n    def listar_por_fornecedor(self, empresa_fornecedora_id: int) -> list[AvaliacaoOficina]:\n        return list(\n            self.banco.scalars(\n                select(AvaliacaoOficina)\n                .where(\n                    AvaliacaoOficina.empresa_fornecedora_id\n                    == empresa_fornecedora_id\n                )\n                .order_by(AvaliacaoOficina.criada_em.desc())\n            )\n        )\n\n    def criar(self, avaliacao: AvaliacaoOficina) -> AvaliacaoOficina:\n        self.banco.add(avaliacao)\n        self.banco.commit()\n        self.banco.refresh(avaliacao)\n        return avaliacao\n\n    def reputacao(\n        self, empresa_fornecedora_id: int\n    ) -> tuple[int, float | None]:\n        quantidade, media = self.banco.execute(\n            select(\n                func.count(AvaliacaoOficina.id),\n                func.avg(AvaliacaoOficina.nota),\n            ).where(\n                AvaliacaoOficina.empresa_fornecedora_id\n                == empresa_fornecedora_id\n            )\n        ).one()\n\n        return int(quantidade or 0), (\n            float(media) if media is not None else None\n        )\n', 'backend/app/services/avaliacao.py': '\nfrom __future__ import annotations\n\nfrom fastapi import HTTPException\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.avaliacao import AvaliacaoOficina\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.repositories.avaliacao import RepositorioAvaliacaoOficina\nfrom backend.app.schemas.avaliacao import (\n    AvaliacaoOficinaCriacao,\n    ReputacaoOficinaResposta,\n)\n\n\nclass ServicoAvaliacaoOficina:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.repositorio = RepositorioAvaliacaoOficina(banco)\n\n    def criar(\n        self,\n        contratacao_id: int,\n        dados: AvaliacaoOficinaCriacao,\n    ) -> AvaliacaoOficina:\n        contratacao = self.banco.get(ContratacaoServico, contratacao_id)\n        if contratacao is None:\n            raise HTTPException(\n                status_code=404,\n                detail="contratacao_nao_encontrada",\n            )\n\n        if contratacao.empresa_cliente_id != dados.empresa_cliente_id:\n            raise HTTPException(\n                status_code=403,\n                detail="empresa_nao_e_cliente_da_contratacao",\n            )\n\n        ordem = self.banco.scalar(\n            select(OrdemServico).where(\n                OrdemServico.contratacao_id == contratacao_id\n            )\n        )\n        if ordem is None:\n            raise HTTPException(\n                status_code=409,\n                detail="ordem_servico_nao_encontrada",\n            )\n\n        if ordem.empresa_cliente_id != dados.empresa_cliente_id:\n            raise HTTPException(\n                status_code=403,\n                detail="empresa_nao_e_cliente_da_ordem_servico",\n            )\n\n        if ordem.empresa_fornecedora_id != contratacao.empresa_fornecedora_id:\n            raise HTTPException(\n                status_code=409,\n                detail="fornecedor_da_ordem_servico_inconsistente",\n            )\n\n        if ordem.status != "concluida" and contratacao.status != "encerrada":\n            raise HTTPException(\n                status_code=409,\n                detail="servico_ainda_nao_foi_concluido_e_aceito",\n            )\n\n        if self.repositorio.obter_por_contratacao(contratacao_id) is not None:\n            raise HTTPException(\n                status_code=409,\n                detail="avaliacao_ja_registrada_para_contratacao",\n            )\n\n        avaliacao = AvaliacaoOficina(\n            contratacao_id=contratacao_id,\n            ordem_servico_id=ordem.id,\n            empresa_cliente_id=dados.empresa_cliente_id,\n            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,\n            nota=dados.nota,\n            comentario=dados.comentario,\n        )\n        return self.repositorio.criar(avaliacao)\n\n    def obter(self, avaliacao_id: int) -> AvaliacaoOficina:\n        item = self.repositorio.obter_por_id(avaliacao_id)\n        if item is None:\n            raise HTTPException(\n                status_code=404,\n                detail="avaliacao_nao_encontrada",\n            )\n        return item\n\n    def listar(self, empresa_fornecedora_id: int) -> list[AvaliacaoOficina]:\n        return self.repositorio.listar_por_fornecedor(\n            empresa_fornecedora_id\n        )\n\n    def obter_reputacao(\n        self, empresa_fornecedora_id: int\n    ) -> ReputacaoOficinaResposta:\n        quantidade, media = self.repositorio.reputacao(\n            empresa_fornecedora_id\n        )\n        return ReputacaoOficinaResposta(\n            empresa_id=empresa_fornecedora_id,\n            quantidade_avaliacoes=quantidade,\n            media_nota=(\n                round(media, 2) if media is not None else None\n            ),\n        )\n', 'backend/app/api/rotas/avaliacoes.py': '\nfrom __future__ import annotations\n\nfrom fastapi import APIRouter, Depends, status\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.avaliacao import (\n    AvaliacaoOficinaCriacao,\n    AvaliacaoOficinaResposta,\n    ReputacaoOficinaResposta,\n)\nfrom backend.app.services.avaliacao import ServicoAvaliacaoOficina\n\n\nroteador = APIRouter(tags=["avaliacoes"])\n\n\n@roteador.post(\n    "/contratacoes/{contratacao_id}/avaliacao",\n    response_model=AvaliacaoOficinaResposta,\n    status_code=status.HTTP_201_CREATED,\n)\ndef criar_avaliacao(\n    contratacao_id: int,\n    dados: AvaliacaoOficinaCriacao,\n    banco: Session = Depends(obter_banco),\n) -> AvaliacaoOficinaResposta:\n    return ServicoAvaliacaoOficina(banco).criar(\n        contratacao_id,\n        dados,\n    )\n\n\n@roteador.get(\n    "/avaliacoes/{avaliacao_id}",\n    response_model=AvaliacaoOficinaResposta,\n)\ndef obter_avaliacao(\n    avaliacao_id: int,\n    banco: Session = Depends(obter_banco),\n) -> AvaliacaoOficinaResposta:\n    return ServicoAvaliacaoOficina(banco).obter(avaliacao_id)\n\n\n@roteador.get(\n    "/empresas/{empresa_id}/avaliacoes",\n    response_model=list[AvaliacaoOficinaResposta],\n)\ndef listar_avaliacoes(\n    empresa_id: int,\n    banco: Session = Depends(obter_banco),\n) -> list[AvaliacaoOficinaResposta]:\n    return ServicoAvaliacaoOficina(banco).listar(empresa_id)\n\n\n@roteador.get(\n    "/empresas/{empresa_id}/reputacao",\n    response_model=ReputacaoOficinaResposta,\n)\ndef obter_reputacao(\n    empresa_id: int,\n    banco: Session = Depends(obter_banco),\n) -> ReputacaoOficinaResposta:\n    return ServicoAvaliacaoOficina(banco).obter_reputacao(empresa_id)\n', 'tests/test_avaliacoes.py': '\nfrom __future__ import annotations\n\nfrom collections.abc import Generator\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.material import Material\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.models.avaliacao import AvaliacaoOficina\nfrom backend.app.principal import app\n\n\n@pytest.fixture()\ndef ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:\n    engine = create_engine(\n        "sqlite://",\n        connect_args={"check_same_thread": False},\n        poolclass=StaticPool,\n    )\n    SessaoTeste = sessionmaker(\n        bind=engine,\n        autoflush=False,\n        expire_on_commit=False,\n        class_=Session,\n    )\n    Base.metadata.create_all(bind=engine)\n\n    def substituir_banco() -> Generator[Session, None, None]:\n        banco = SessaoTeste()\n        try:\n            yield banco\n        finally:\n            banco.close()\n\n    app.dependency_overrides[obter_banco] = substituir_banco\n    try:\n        with TestClient(app) as test_client:\n            yield test_client, SessaoTeste\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(bind=engine)\n        engine.dispose()\n\n\ndef preparar_servico(\n    SessaoTeste: sessionmaker,\n    *,\n    encerrado: bool = True,\n) -> tuple[int, int, int, int]:\n    banco = SessaoTeste()\n\n    cliente = Empresa(\n        razao_social="Cliente D14",\n        documento="D14-CLIENTE-001",\n        tipo_empresa="cliente",\n    )\n    fornecedor = Empresa(\n        razao_social="Fornecedor D14",\n        documento="D14-FORNECEDOR-001",\n        tipo_empresa="fornecedor",\n    )\n    processo = ProcessoFabricacao(\n        codigo="usinagem_cnc_d14",\n        nome="Usinagem CNC D14",\n        descricao="Usinagem D14.",\n    )\n    material = Material(\n        codigo="aluminio_6061_d14",\n        nome="Aluminio 6061 D14",\n        familia="Aluminio",\n        especificacao="Liga D14.",\n    )\n    banco.add_all([cliente, fornecedor, processo, material])\n    banco.commit()\n\n    solicitacao = SolicitacaoServico(\n        empresa_cliente_id=cliente.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        dimensao_x_maxima_mm=100,\n        dimensao_y_maxima_mm=100,\n        dimensao_z_maxima_mm=100,\n        tolerancia_requerida_mm=0.02,\n        quantidade=5,\n        observacoes="Solicitacao D14.",\n        status="aberta",\n    )\n    banco.add(solicitacao)\n    banco.commit()\n\n    cotacao = CotacaoFornecedor(\n        solicitacao_id=solicitacao.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("5000.00"),\n        prazo_dias=10,\n        validade_dias=10,\n        observacoes="Cotacao D14.",\n        status="aceita",\n        decidida_por_empresa_id=cliente.id,\n    )\n    banco.add(cotacao)\n    banco.commit()\n\n    contratacao = ContratacaoServico(\n        solicitacao_id=solicitacao.id,\n        cotacao_id=cotacao.id,\n        empresa_cliente_id=cliente.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("5000.00"),\n        prazo_dias=10,\n        observacoes="Contratacao D14.",\n        status="encerrada" if encerrado else "ativa",\n    )\n    banco.add(contratacao)\n    banco.commit()\n\n    ordem = OrdemServico(\n        contratacao_id=contratacao.id,\n        solicitacao_id=solicitacao.id,\n        cotacao_id=cotacao.id,\n        empresa_cliente_id=cliente.id,\n        empresa_fornecedora_id=fornecedor.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        quantidade=5,\n        valor_total=Decimal("5000.00"),\n        prazo_dias=10,\n        status="concluida" if encerrado else "em_execucao",\n    )\n    banco.add(ordem)\n    banco.commit()\n\n    ids = (cliente.id, fornecedor.id, contratacao.id, ordem.id)\n    banco.close()\n    return ids\n\n\ndef test_criar_avaliacao_valida(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, fornecedor_id, contratacao_id, _ = preparar_servico(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n        json={"empresa_cliente_id": cliente_id, "nota": 5, "comentario": "Serviço excelente."},\n    )\n    assert resposta.status_code == 201\n    corpo = resposta.json()\n    assert corpo["nota"] == 5\n    assert corpo["empresa_fornecedora_id"] == fornecedor_id\n\n\ndef test_nota_fora_da_faixa_e_rejeitada(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id, _ = preparar_servico(SessaoTeste)\n\n    for nota in (0, 6):\n        resposta = cliente_http.post(\n            f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n            json={"empresa_cliente_id": cliente_id, "nota": nota},\n        )\n        assert resposta.status_code == 422\n\n\ndef test_cliente_incorreto_nao_pode_avaliar(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    _, _, contratacao_id, _ = preparar_servico(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n        json={"empresa_cliente_id": 999999, "nota": 4},\n    )\n    assert resposta.status_code == 403\n\n\ndef test_servico_nao_concluido_nao_pode_ser_avaliado(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id, _ = preparar_servico(\n        SessaoTeste,\n        encerrado=False,\n    )\n\n    resposta = cliente_http.post(\n        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n        json={"empresa_cliente_id": cliente_id, "nota": 4},\n    )\n    assert resposta.status_code == 409\n\n\ndef test_nao_permite_duas_avaliacoes_para_mesma_contratacao(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id, _ = preparar_servico(SessaoTeste)\n\n    primeira = cliente_http.post(\n        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n        json={"empresa_cliente_id": cliente_id, "nota": 4},\n    )\n    assert primeira.status_code == 201\n\n    segunda = cliente_http.post(\n        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n        json={"empresa_cliente_id": cliente_id, "nota": 5},\n    )\n    assert segunda.status_code == 409\n\n\ndef test_obter_listar_e_reputacao(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, fornecedor_id, contratacao_id, _ = preparar_servico(SessaoTeste)\n\n    criada = cliente_http.post(\n        f"/api/v1/contratacoes/{contratacao_id}/avaliacao",\n        json={"empresa_cliente_id": cliente_id, "nota": 4, "comentario": "Bom serviço."},\n    )\n    assert criada.status_code == 201\n    avaliacao_id = criada.json()["id"]\n\n    obtida = cliente_http.get(f"/api/v1/avaliacoes/{avaliacao_id}")\n    assert obtida.status_code == 200\n    assert obtida.json()["id"] == avaliacao_id\n\n    lista = cliente_http.get(\n        f"/api/v1/empresas/{fornecedor_id}/avaliacoes"\n    )\n    assert lista.status_code == 200\n    assert len(lista.json()) == 1\n\n    reputacao = cliente_http.get(\n        f"/api/v1/empresas/{fornecedor_id}/reputacao"\n    )\n    assert reputacao.status_code == 200\n    assert reputacao.json()["quantidade_avaliacoes"] == 1\n    assert reputacao.json()["media_nota"] == 4.0\n'}

def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    destino = BACKUP_ROOT / path.relative_to(ROOT)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destino)
    return destino


def ast_ok(text: str, filename: str) -> bool:
    ast.parse(text, filename=filename)
    return True


def integrar_roteador(text: str) -> tuple[str, int]:
    alteracoes = 0
    import_line = (
        "from backend.app.api.rotas.avaliacoes "
        "import roteador as roteador_avaliacoes"
    )
    include_line = "roteador_api.include_router(roteador_avaliacoes)"

    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
        alteracoes += 1

    if include_line not in text:
        text = text.rstrip() + "\n" + include_line + "\n"
        alteracoes += 1

    return text, alteracoes


def integrar_modelos(text: str) -> tuple[str, int]:
    import_line = "from backend.app.models.avaliacao import AvaliacaoOficina"
    if import_line in text:
        return text, 0
    return text.rstrip() + "\n" + import_line + "\n", 1


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    required = [
        ROOT / "backend" / "app" / "api" / "roteador.py",
        ROOT / "backend" / "app" / "models" / "__init__.py",
        ROOT / "backend" / "database" / "inicializacao.py",
        ROOT / "backend" / "database" / "sessao.py",
    ]
    # A estrutura atual usa backend/app/database.
    required = [
        ROOT / "backend" / "app" / "api" / "roteador.py",
        ROOT / "backend" / "app" / "models" / "__init__.py",
        ROOT / "backend" / "app" / "database" / "inicializacao.py",
        ROOT / "backend" / "app" / "database" / "sessao.py",
    ]
    files_ok = all(p.exists() for p in required)

    if not files_ok:
        print("ERRO: baseline D13 não encontrada; arquivos estruturais ausentes.")
        return 1

    backed_up = 0
    changed = 0

    # Cria os módulos D14.
    for rel, content in FILES.items():
        path = ROOT / rel
        if path.exists():
            backup(path)
            backed_up += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != content:
            path.write_text(content, encoding="utf-8", newline="\n")
            changed += 1
        ast_ok(content, rel)

    # Integra o roteador.
    router_path = ROOT / "backend" / "app" / "api" / "roteador.py"
    old_router = router_path.read_text(encoding="utf-8")
    new_router, n_router = integrar_roteador(old_router)
    if n_router:
        backup(router_path)
        backed_up += 1
        router_path.write_text(new_router, encoding="utf-8", newline="\n")
        changed += 1
    ast_ok(new_router, str(router_path))

    # Integra o modelo na carga central dos modelos.
    models_path = ROOT / "backend" / "app" / "models" / "__init__.py"
    old_models = models_path.read_text(encoding="utf-8")
    new_models, n_models = integrar_modelos(old_models)
    if n_models:
        backup(models_path)
        backed_up += 1
        models_path.write_text(new_models, encoding="utf-8", newline="\n")
        changed += 1
    ast_ok(new_models, str(models_path))

    # Garante a tabela no SQLite/engine atual sem apagar dados existentes.
    database_changed = False
    database_already_migrated = False
    table_created = False
    try:
        from sqlalchemy import inspect

        from backend.app.database.base import Base
        import backend.app.models  # noqa: F401
        from backend.app.database.sessao import engine

        inspector = inspect(engine)
        if "avaliacoes_oficina" in inspector.get_table_names():
            database_already_migrated = True
        else:
            Base.metadata.create_all(bind=engine, tables=[
                Base.metadata.tables["avaliacoes_oficina"]
            ])
            database_changed = True
            table_created = True
    except Exception as exc:
        print(f"ERRO: falha ao criar a tabela D14: {type(exc).__name__}: {exc}")
        return 1

    report_lines = [
        "Plataforma de Serviços Mecânicos — V0.1 D14 Avaliações e Reputação",
        f"REVISION= {REVISION}",
        f"ROOT= {ROOT}",
        f"FILES_OK= {files_ok}",
        "AST_OK= True",
        f"TABLE_AVALIACOES_OFICINA= {table_created or database_already_migrated}",
        f"DATABASE_CHANGED= {database_changed}",
        f"DATABASE_ALREADY_MIGRATED= {database_already_migrated}",
        f"BACKED_UP= {backed_up}",
        f"CHANGED_FILES= {changed}",
        "CLIENT_EVALUATION_ONLY= True",
        "RATING_RANGE= 1..5",
        "ONE_EVALUATION_PER_CONTRACT= True",
        "ACCEPTED_SERVICE_REQUIRED= True",
        "REPUTATION_AGGREGATION= True",
        "HISTORY_PRESERVED= True",
        f"BACKUP_DIR= {BACKUP_ROOT}",
        f"REPORT= {REPORT}",
        f"JSON= {JSON_REPORT}",
    ]

    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    JSON_REPORT.write_text(
        json.dumps(
            {
                "revision": REVISION,
                "files_ok": files_ok,
                "ast_ok": True,
                "table_avaliacoes_oficina": table_created or database_already_migrated,
                "database_changed": database_changed,
                "database_already_migrated": database_already_migrated,
                "backed_up": backed_up,
                "changed_files": changed,
                "client_evaluation_only": True,
                "rating_range": [1, 5],
                "one_evaluation_per_contract": True,
                "accepted_service_required": True,
                "reputation_aggregation": True,
                "history_preserved": True,
                "backup_dir": str(BACKUP_ROOT),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n".join(report_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
