
from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "tests" / "test_acompanhamento_producao.py"
BACKUP_ROOT = ROOT / "_mec_backups"
REVISION = "MEC-SERVICOS-V0.1-D10-FIX1-ISOLAMENTO-TESTES-2026-10-01"

FIXED_TEST = r'\nfrom __future__ import annotations\n\nfrom collections.abc import Generator\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.material import Material\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.principal import app\n\n\n@pytest.fixture()\ndef ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:\n    engine = create_engine(\n        "sqlite://",\n        connect_args={"check_same_thread": False},\n        poolclass=StaticPool,\n    )\n    SessaoTeste = sessionmaker(\n        bind=engine,\n        autoflush=False,\n        expire_on_commit=False,\n        class_=Session,\n    )\n    Base.metadata.create_all(bind=engine)\n\n    def substituir_banco() -> Generator[Session, None, None]:\n        banco = SessaoTeste()\n        try:\n            yield banco\n        finally:\n            banco.close()\n\n    app.dependency_overrides[obter_banco] = substituir_banco\n    try:\n        with TestClient(app) as test_client:\n            yield test_client, SessaoTeste\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(bind=engine)\n        engine.dispose()\n\n\ndef preparar_ordem(SessaoTeste: sessionmaker) -> tuple[int, int, int]:\n    banco = SessaoTeste()\n\n    cliente = Empresa(\n        razao_social="Cliente D10",\n        documento="D10-CLIENTE-001",\n        tipo_empresa="cliente",\n    )\n    fornecedor = Empresa(\n        razao_social="Fornecedor D10",\n        documento="D10-FORNECEDOR-001",\n        tipo_empresa="fornecedor",\n    )\n    processo = ProcessoFabricacao(\n        codigo="usinagem_cnc_d10",\n        nome="Usinagem CNC D10",\n        descricao="Usinagem D10.",\n    )\n    material = Material(\n        codigo="aluminio_6061_d10",\n        nome="Aluminio 6061 D10",\n        familia="Aluminio",\n        especificacao="Liga D10.",\n    )\n    banco.add_all([cliente, fornecedor, processo, material])\n    banco.commit()\n    for item in (cliente, fornecedor, processo, material):\n        banco.refresh(item)\n\n    solicitacao = SolicitacaoServico(\n        empresa_cliente_id=cliente.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        dimensao_x_maxima_mm=100,\n        dimensao_y_maxima_mm=100,\n        dimensao_z_maxima_mm=100,\n        tolerancia_requerida_mm=0.02,\n        quantidade=5,\n        observacoes="Solicitacao D10.",\n        status="aberta",\n    )\n    banco.add(solicitacao)\n    banco.commit()\n    banco.refresh(solicitacao)\n\n    cotacao = CotacaoFornecedor(\n        solicitacao_id=solicitacao.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("5000.00"),\n        prazo_dias=10,\n        validade_dias=10,\n        observacoes="Cotacao D10.",\n        status="aceita",\n        decidida_por_empresa_id=cliente.id,\n    )\n    banco.add(cotacao)\n    banco.commit()\n    banco.refresh(cotacao)\n\n    contratacao = ContratacaoServico(\n        solicitacao_id=solicitacao.id,\n        cotacao_id=cotacao.id,\n        empresa_cliente_id=cliente.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("5000.00"),\n        prazo_dias=10,\n        observacoes="Contratacao D10.",\n        status="ativa",\n    )\n    banco.add(contratacao)\n    banco.commit()\n    banco.refresh(contratacao)\n\n    ordem = OrdemServico(\n        contratacao_id=contratacao.id,\n        solicitacao_id=solicitacao.id,\n        cotacao_id=cotacao.id,\n        empresa_cliente_id=cliente.id,\n        empresa_fornecedora_id=fornecedor.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        quantidade=5,\n        valor_total=Decimal("5000.00"),\n        prazo_dias=10,\n        status="em_execucao",\n    )\n    banco.add(ordem)\n    banco.commit()\n    banco.refresh(ordem)\n\n    ids = (cliente.id, fornecedor.id, ordem.id)\n    banco.close()\n    return ids\n\n\ndef test_registrar_etapa_e_listar_historico(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",\n        json={\n            "empresa_fornecedora_id": fornecedor_id,\n            "etapa": "aguardando_material",\n            "observacoes": "Material em compra.",\n        },\n    )\n    assert resposta.status_code == 201\n    assert resposta.json()["etapa"] == "aguardando_material"\n\n    resposta = cliente_http.get(\n        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",\n    )\n    assert resposta.status_code == 200\n    assert len(resposta.json()) == 1\n\n\ndef test_acompanhamento_retorna_etapa_atual(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)\n\n    for etapa in ("aguardando_material", "em_usinagem"):\n        resposta = cliente_http.post(\n            f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",\n            json={\n                "empresa_fornecedora_id": fornecedor_id,\n                "etapa": etapa,\n            },\n        )\n        assert resposta.status_code == 201\n\n    resposta = cliente_http.get(\n        f"/api/v1/ordens-servico/{ordem_id}/acompanhamento-producao",\n    )\n    assert resposta.status_code == 200\n    corpo = resposta.json()\n    assert corpo["etapa_atual"] == "em_usinagem"\n    assert len(corpo["historico"]) == 2\n\n\ndef test_fornecedor_incorreto_nao_pode_atualizar(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",\n        json={\n            "empresa_fornecedora_id": fornecedor_id + 1000,\n            "etapa": "em_usinagem",\n        },\n    )\n    assert resposta.status_code == 403\n    assert resposta.json()["detail"] == "empresa_nao_e_fornecedora_da_ordem_servico"\n\n\ndef test_etapa_invalida_e_rejeitada(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)\n\n    resposta = cliente_http.post(\n        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",\n        json={\n            "empresa_fornecedora_id": fornecedor_id,\n            "etapa": "etapa_inexistente",\n        },\n    )\n    assert resposta.status_code == 422\n\n\ndef test_ordem_concluida_nao_recebe_nova_etapa(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    _, fornecedor_id, ordem_id = preparar_ordem(SessaoTeste)\n\n    banco = SessaoTeste()\n    ordem = banco.get(OrdemServico, ordem_id)\n    ordem.status = "concluida"\n    banco.commit()\n    banco.close()\n\n    resposta = cliente_http.post(\n        f"/api/v1/ordens-servico/{ordem_id}/etapas-producao",\n        json={\n            "empresa_fornecedora_id": fornecedor_id,\n            "etapa": "pronto_para_envio",\n        },\n    )\n    assert resposta.status_code == 409\n'

def main() -> int:
    if not TARGET.exists():
        print("ERRO: TARGET ausente:", TARGET)
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"D10_FIX1_ISOLAMENTO_TESTES_{stamp}"
    backup_path = backup_dir / TARGET.relative_to(ROOT)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET, backup_path)

    TARGET.write_text(FIXED_TEST, encoding="utf-8")
    ast.parse(TARGET.read_text(encoding="utf-8"))

    report = ROOT / "MEC_SERVICOS_V0_1_D10_FIX1_ISOLAMENTO_TESTES_RELATORIO.txt"
    report_json = ROOT / "MEC_SERVICOS_V0_1_D10_FIX1_ISOLAMENTO_TESTES.json"

    payload = {
        "revision": REVISION,
        "target": str(TARGET),
        "changed": True,
        "ast_ok": True,
        "root_cause": (
            "O teste D10 mantinha um SQLite in-memory com StaticPool "
            "no escopo do módulo; os cinco testes reutilizavam o mesmo "
            "banco e repetiam codigo/nome únicos de processo/material."
        ),
        "fix": (
            "Fixture function-scoped cria um novo engine SQLite in-memory "
            "para cada teste, executa create_all antes e drop_all depois."
        ),
        "backup": str(backup_path),
    }

    report_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report.write_text(
        "\n".join(
            [
                "Plataforma de Serviços Mecânicos — D10 FIX1 Isolamento dos Testes",
                f"REVISION= {REVISION}",
                f"ROOT= {ROOT}",
                f"TARGET= {TARGET}",
                "AST_OK= True",
                "FIXTURE_SCOPE= function",
                "SQLITE_MEMORY_ISOLATION= True",
                "DROP_ALL_AFTER_TEST= True",
                f"BACKUP= {backup_path}",
                f"REPORT= {report}",
                f"JSON= {report_json}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print("Plataforma de Serviços Mecânicos — D10 FIX1")
    print("REVISION=", REVISION)
    print("ROOT=", ROOT)
    print("TARGET=", TARGET)
    print("AST_OK= True")
    print("FIXTURE_SCOPE= function")
    print("SQLITE_MEMORY_ISOLATION= True")
    print("DROP_ALL_AFTER_TEST= True")
    print("BACKUP=", backup_path)
    print("REPORT=", report)
    print("JSON=", report_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
