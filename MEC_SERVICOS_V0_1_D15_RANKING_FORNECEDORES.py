from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from pathlib import Path

REVISION = "MEC-SERVICOS-V0.1-D15-RANKING-FORNECEDORES-2026-10-01"
ROOT = Path(__file__).resolve().parent
BACKUP_ROOT = ROOT / "_mec_backups" / f"V0_1_D15_RANKING_FORNECEDORES_{datetime.now():%Y%m%d_%H%M%S}"
REPORT = ROOT / "MEC_SERVICOS_V0_1_D15_RANKING_FORNECEDORES_RELATORIO.txt"
JSON_REPORT = ROOT / "MEC_SERVICOS_V0_1_D15_RANKING_FORNECEDORES.json"

FILES: dict[str, str] = {'backend/app/schemas/ranking_fornecedor.py': '\nfrom __future__ import annotations\n\nfrom pydantic import BaseModel\n\n\nclass RankingFornecedorItem(BaseModel):\n    posicao: int\n    empresa_id: int\n    razao_social: str\n    quantidade_avaliacoes: int\n    media_nota: float | None\n\n\nclass RankingFornecedoresResposta(BaseModel):\n    total_fornecedores: int\n    fornecedores_avaliados: int\n    itens: list[RankingFornecedorItem]\n', 'backend/app/repositories/ranking_fornecedor.py': '\nfrom __future__ import annotations\n\nfrom sqlalchemy import func, select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.avaliacao import AvaliacaoOficina\nfrom backend.app.models.empresa import Empresa\n\n\nclass RepositorioRankingFornecedores:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def listar(self) -> list[tuple[Empresa, int, float | None]]:\n        linhas = self.banco.execute(\n            select(\n                Empresa,\n                func.count(AvaliacaoOficina.id),\n                func.avg(AvaliacaoOficina.nota),\n            )\n            .outerjoin(\n                AvaliacaoOficina,\n                AvaliacaoOficina.empresa_fornecedora_id == Empresa.id,\n            )\n            .where(Empresa.tipo_empresa == "fornecedor")\n            .group_by(Empresa.id)\n        ).all()\n\n        dados = [\n            (\n                empresa,\n                int(quantidade or 0),\n                float(media) if media is not None else None,\n            )\n            for empresa, quantidade, media in linhas\n        ]\n\n        dados.sort(\n            key=lambda item: (\n                item[2] is None,\n                -(item[2] if item[2] is not None else 0.0),\n                -item[1],\n                item[0].razao_social.casefold(),\n                item[0].id,\n            )\n        )\n        return dados\n', 'backend/app/services/ranking_fornecedor.py': '\nfrom __future__ import annotations\n\nfrom backend.app.repositories.ranking_fornecedor import RepositorioRankingFornecedores\nfrom backend.app.schemas.ranking_fornecedor import (\n    RankingFornecedorItem,\n    RankingFornecedoresResposta,\n)\n\n\nclass ServicoRankingFornecedores:\n    def __init__(self, banco) -> None:\n        self.repositorio = RepositorioRankingFornecedores(banco)\n\n    def obter_ranking(self) -> RankingFornecedoresResposta:\n        dados = self.repositorio.listar()\n        itens = [\n            RankingFornecedorItem(\n                posicao=posicao,\n                empresa_id=empresa.id,\n                razao_social=empresa.razao_social,\n                quantidade_avaliacoes=quantidade,\n                media_nota=round(media, 2) if media is not None else None,\n            )\n            for posicao, (empresa, quantidade, media) in enumerate(dados, start=1)\n        ]\n        return RankingFornecedoresResposta(\n            total_fornecedores=len(itens),\n            fornecedores_avaliados=sum(\n                1 for item in itens if item.quantidade_avaliacoes > 0\n            ),\n            itens=itens,\n        )\n', 'backend/app/api/rotas/ranking_fornecedores.py': '\nfrom __future__ import annotations\n\nfrom fastapi import APIRouter, Depends\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.ranking_fornecedor import RankingFornecedoresResposta\nfrom backend.app.services.ranking_fornecedor import ServicoRankingFornecedores\n\n\nroteador = APIRouter(tags=["ranking-fornecedores"])\n\n\n@roteador.get(\n    "/fornecedores/ranking",\n    response_model=RankingFornecedoresResposta,\n)\ndef obter_ranking_fornecedores(\n    banco: Session = Depends(obter_banco),\n) -> RankingFornecedoresResposta:\n    return ServicoRankingFornecedores(banco).obter_ranking()\n', 'tests/test_ranking_fornecedores.py': '\nfrom __future__ import annotations\n\nfrom collections.abc import Generator\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.material import Material\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.models.avaliacao import AvaliacaoOficina\nfrom backend.app.principal import app\n\n\n@pytest.fixture()\ndef ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:\n    engine = create_engine(\n        "sqlite://",\n        connect_args={"check_same_thread": False},\n        poolclass=StaticPool,\n    )\n    SessaoTeste = sessionmaker(\n        bind=engine,\n        autoflush=False,\n        expire_on_commit=False,\n        class_=Session,\n    )\n    Base.metadata.create_all(bind=engine)\n\n    def substituir_banco() -> Generator[Session, None, None]:\n        banco = SessaoTeste()\n        try:\n            yield banco\n        finally:\n            banco.close()\n\n    app.dependency_overrides[obter_banco] = substituir_banco\n    try:\n        with TestClient(app) as test_client:\n            yield test_client, SessaoTeste\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(bind=engine)\n        engine.dispose()\n\n\ndef preparar_fornecedor(\n    SessaoTeste: sessionmaker,\n    *,\n    sufixo: str,\n    razao_social: str,\n    notas: list[int],\n) -> int:\n    banco = SessaoTeste()\n    cliente = Empresa(\n        razao_social=f"Cliente D15 {sufixo}",\n        documento=f"D15-CLIENTE-{sufixo}",\n        tipo_empresa="cliente",\n    )\n    fornecedor = Empresa(\n        razao_social=razao_social,\n        documento=f"D15-FORNECEDOR-{sufixo}",\n        tipo_empresa="fornecedor",\n    )\n    processo = ProcessoFabricacao(\n        codigo=f"usinagem_cnc_d15_{sufixo}",\n        nome=f"Usinagem CNC D15 {sufixo}",\n        descricao="Usinagem D15.",\n    )\n    material = Material(\n        codigo=f"aluminio_6061_d15_{sufixo}",\n        nome=f"Aluminio 6061 D15 {sufixo}",\n        familia="Aluminio",\n        especificacao="Liga D15.",\n    )\n    banco.add_all([cliente, fornecedor, processo, material])\n    banco.commit()\n\n    for indice, nota in enumerate(notas, start=1):\n        solicitacao = SolicitacaoServico(\n            empresa_cliente_id=cliente.id,\n            processo_id=processo.id,\n            material_id=material.id,\n            dimensao_x_maxima_mm=100,\n            dimensao_y_maxima_mm=100,\n            dimensao_z_maxima_mm=100,\n            tolerancia_requerida_mm=0.02,\n            quantidade=5,\n            observacoes=f"Solicitacao D15 {sufixo}-{indice}.",\n            status="aberta",\n        )\n        banco.add(solicitacao)\n        banco.commit()\n\n        cotacao = CotacaoFornecedor(\n            solicitacao_id=solicitacao.id,\n            empresa_fornecedora_id=fornecedor.id,\n            valor_total=Decimal("5000.00"),\n            prazo_dias=10,\n            validade_dias=10,\n            observacoes=f"Cotacao D15 {sufixo}-{indice}.",\n            status="aceita",\n            decidida_por_empresa_id=cliente.id,\n        )\n        banco.add(cotacao)\n        banco.commit()\n\n        contratacao = ContratacaoServico(\n            solicitacao_id=solicitacao.id,\n            cotacao_id=cotacao.id,\n            empresa_cliente_id=cliente.id,\n            empresa_fornecedora_id=fornecedor.id,\n            valor_total=Decimal("5000.00"),\n            prazo_dias=10,\n            observacoes=f"Contratacao D15 {sufixo}-{indice}.",\n            status="encerrada",\n        )\n        banco.add(contratacao)\n        banco.commit()\n\n        ordem = OrdemServico(\n            contratacao_id=contratacao.id,\n            solicitacao_id=solicitacao.id,\n            cotacao_id=cotacao.id,\n            empresa_cliente_id=cliente.id,\n            empresa_fornecedora_id=fornecedor.id,\n            processo_id=processo.id,\n            material_id=material.id,\n            quantidade=5,\n            valor_total=Decimal("5000.00"),\n            prazo_dias=10,\n            status="concluida",\n        )\n        banco.add(ordem)\n        banco.commit()\n\n        avaliacao = AvaliacaoOficina(\n            contratacao_id=contratacao.id,\n            ordem_servico_id=ordem.id,\n            empresa_cliente_id=cliente.id,\n            empresa_fornecedora_id=fornecedor.id,\n            nota=nota,\n        )\n        banco.add(avaliacao)\n        banco.commit()\n\n    banco.refresh(fornecedor)\n    fornecedor_id = fornecedor.id\n    banco.close()\n    return fornecedor_id\n\n\ndef preparar_fornecedor_sem_avaliacao(\n    SessaoTeste: sessionmaker,\n    *,\n    sufixo: str,\n    razao_social: str,\n) -> int:\n    banco = SessaoTeste()\n    fornecedor = Empresa(\n        razao_social=razao_social,\n        documento=f"D15-FORNECEDOR-{sufixo}",\n        tipo_empresa="fornecedor",\n    )\n    banco.add(fornecedor)\n    banco.commit()\n    banco.refresh(fornecedor)\n    fornecedor_id = fornecedor.id\n    banco.close()\n    return fornecedor_id\n\n\ndef test_ranking_ordena_por_media_e_quantidade(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="A",\n        razao_social="Fornecedor Alfa D15",\n        notas=[5, 5],\n    )\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="B",\n        razao_social="Fornecedor Beta D15",\n        notas=[4, 4, 4],\n    )\n\n    resposta = cliente_http.get("/api/v1/fornecedores/ranking")\n    assert resposta.status_code == 200\n    itens = resposta.json()["itens"]\n    assert [item["razao_social"] for item in itens[:2]] == [\n        "Fornecedor Alfa D15",\n        "Fornecedor Beta D15",\n    ]\n    assert itens[0]["media_nota"] == 5.0\n    assert itens[0]["quantidade_avaliacoes"] == 2\n    assert itens[0]["posicao"] == 1\n    assert itens[1]["posicao"] == 2\n\n\ndef test_quantidade_de_avaliacoes_desempata_media_igual(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="C",\n        razao_social="Fornecedor Gama D15",\n        notas=[5],\n    )\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="D",\n        razao_social="Fornecedor Delta D15",\n        notas=[5, 5, 5],\n    )\n\n    itens = cliente_http.get("/api/v1/fornecedores/ranking").json()["itens"]\n    assert itens[0]["razao_social"] == "Fornecedor Delta D15"\n    assert itens[1]["razao_social"] == "Fornecedor Gama D15"\n    assert itens[0]["media_nota"] == itens[1]["media_nota"] == 5.0\n    assert itens[0]["quantidade_avaliacoes"] == 3\n    assert itens[1]["quantidade_avaliacoes"] == 1\n\n\ndef test_fornecedor_sem_avaliacao_fica_apos_avaliados(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="E",\n        razao_social="Fornecedor Epsilon D15",\n        notas=[3],\n    )\n    preparar_fornecedor_sem_avaliacao(\n        SessaoTeste,\n        sufixo="F",\n        razao_social="Fornecedor Zeta D15",\n    )\n\n    resposta = cliente_http.get("/api/v1/fornecedores/ranking")\n    assert resposta.status_code == 200\n    corpo = resposta.json()\n    assert corpo["total_fornecedores"] == 2\n    assert corpo["fornecedores_avaliados"] == 1\n    assert corpo["itens"][0]["razao_social"] == "Fornecedor Epsilon D15"\n    assert corpo["itens"][1]["razao_social"] == "Fornecedor Zeta D15"\n    assert corpo["itens"][1]["media_nota"] is None\n    assert corpo["itens"][1]["quantidade_avaliacoes"] == 0\n\n\ndef test_ordem_e_deterministica_por_nome(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="G",\n        razao_social="Fornecedor Alpha D15",\n        notas=[4],\n    )\n    preparar_fornecedor(\n        SessaoTeste,\n        sufixo="H",\n        razao_social="Fornecedor Beta D15",\n        notas=[4],\n    )\n\n    itens = cliente_http.get("/api/v1/fornecedores/ranking").json()["itens"]\n    assert [item["razao_social"] for item in itens] == [\n        "Fornecedor Alpha D15",\n        "Fornecedor Beta D15",\n    ]\n    assert [item["posicao"] for item in itens] == [1, 2]\n'}


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
        "from backend.app.api.rotas.ranking_fornecedores "
        "import roteador as roteador_ranking_fornecedores"
    )
    include_line = "roteador_api.include_router(roteador_ranking_fornecedores)"

    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
        alteracoes += 1

    if include_line not in text:
        text = text.rstrip() + "\n" + include_line + "\n"
        alteracoes += 1

    return text, alteracoes


def main() -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    required = [
        ROOT / "backend" / "app" / "api" / "roteador.py",
        ROOT / "backend" / "app" / "models" / "avaliacao.py",
        ROOT / "backend" / "app" / "repositories" / "avaliacao.py",
        ROOT / "backend" / "app" / "schemas" / "avaliacao.py",
        ROOT / "backend" / "app" / "services" / "avaliacao.py",
        ROOT / "backend" / "app" / "database" / "sessao.py",
        ROOT / "tests" / "test_avaliacoes.py",
    ]
    baseline_ok = all(p.exists() for p in required)
    if not baseline_ok:
        print("ERRO: baseline D14 não encontrada; execute primeiro o D14.")
        return 1

    backed_up = 0
    changed = 0

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

    router_path = ROOT / "backend" / "app" / "api" / "roteador.py"
    old_router = router_path.read_text(encoding="utf-8")
    new_router, n_router = integrar_roteador(old_router)
    if n_router:
        backup(router_path)
        backed_up += 1
        router_path.write_text(new_router, encoding="utf-8", newline="\n")
        changed += 1
    ast_ok(new_router, str(router_path))

    report_lines = [
        "Plataforma de Serviços Mecânicos — V0.1 D15 Ranking de Fornecedores",
        f"REVISION= {REVISION}",
        f"ROOT= {ROOT}",
        f"D14_BASELINE_OK= {baseline_ok}",
        "AST_OK= True",
        "DATABASE_CHANGED= False",
        "DATABASE_MIGRATION_REQUIRED= False",
        f"BACKED_UP= {backed_up}",
        f"CHANGED_FILES= {changed}",
        "DERIVED_FROM_D14_EVALUATIONS= True",
        "SUPPLIERS_ONLY= True",
        "AVERAGE_RATING_PRIMARY_ORDER= DESC",
        "RATING_COUNT_TIE_BREAK= DESC",
        "UNRATED_SUPPLIERS_LAST= True",
        "NAME_TIE_BREAK= ASC",
        "DETERMINISTIC_POSITION= True",
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
                "d14_baseline_ok": baseline_ok,
                "ast_ok": True,
                "database_changed": False,
                "database_migration_required": False,
                "backed_up": backed_up,
                "changed_files": changed,
                "derived_from_d14_evaluations": True,
                "suppliers_only": True,
                "average_rating_primary_order": "desc",
                "rating_count_tie_break": "desc",
                "unrated_suppliers_last": True,
                "name_tie_break": "asc",
                "deterministic_position": True,
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
