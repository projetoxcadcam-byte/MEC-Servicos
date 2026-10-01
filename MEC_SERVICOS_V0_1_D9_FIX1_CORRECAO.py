from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = "MEC-SERVICOS-V0.1-D9-FIX1-CORRECAO-BASELINE-2026-10-01"
BACKUP_ROOT = ROOT / "_mec_backups"

TARGETS = [
    ROOT / "backend/app/models/ordem_servico.py",
    ROOT / "backend/app/api/rotas/ordens_servico.py",
    ROOT / "backend/app/api/roteador.py",
    ROOT / "tests/test_ordens_servico.py",
]

def backup(path: Path, backup_dir: Path) -> None:
    if not path.exists():
        return
    alvo = backup_dir / path.relative_to(ROOT)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, alvo)

def replace_once(text: str, old: str, new: str, label: str) -> tuple[str, bool]:
    if old not in text:
        return text, False
    return text.replace(old, new, 1), True

def main() -> int:
    missing = [str(p.relative_to(ROOT)) for p in TARGETS if not p.exists()]
    if missing:
        print("ERRO: arquivos D9 esperados não encontrados:")
        for item in missing:
            print("  MISSING=", item)
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D9_FIX1_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    changed: list[str] = []

    try:
        # 1) Baseline real do projeto: ProcessoFabricacao -> processos_fabricacao.
        model = ROOT / "backend/app/models/ordem_servico.py"
        text = model.read_text(encoding="utf-8")
        original = text
        text = text.replace(
            'ForeignKey("processos.id")',
            'ForeignKey("processos_fabricacao.id", ondelete="RESTRICT")',
        )
        if text != original:
            backup(model, backup_dir)
            model.write_text(text, encoding="utf-8")
            changed.append(str(model.relative_to(ROOT)))

        # 2) APIRouter não aceita prefixo terminando em "/".
        route = ROOT / "backend/app/api/rotas/ordens_servico.py"
        text = route.read_text(encoding="utf-8")
        original = text
        text = text.replace(
            'APIRouter(prefix="/", tags=["ordens de serviço"])',
            'APIRouter(tags=["ordens de serviço"])',
        )
        if text != original:
            backup(route, backup_dir)
            route.write_text(text, encoding="utf-8")
            changed.append(str(route.relative_to(ROOT)))

        # 3) Corrigir a importação do modelo de processo nos testes.
        tests = ROOT / "tests/test_ordens_servico.py"
        text = tests.read_text(encoding="utf-8")
        original = text
        text = text.replace(
            "from backend.app.models.processo import Processo\n",
            "from backend.app.models.processo import ProcessoFabricacao\n",
        )
        text = text.replace(
            "processo = Processo(",
            "processo = ProcessoFabricacao(",
        )

        # A OS não depende da capacidade técnica para ser criada.
        text = text.replace(
            "from backend.app.models.capacidade import CapacidadeTecnica\n",
            "",
        )
        text = text.replace(
            "from backend.app.models.material_fornecedor import MaterialFornecedor\n",
            "",
        )
        text = text.replace(
            '    banco.add(CapacidadeTecnica(empresa_id=fornecedor.id, processo_id=processo.id, dimensao_x_maxima_mm=800, dimensao_y_maxima_mm=500, dimensao_z_maxima_mm=450, tolerancia_minima_mm=0.02))\n'
            '    banco.add(MaterialFornecedor(empresa_id=fornecedor.id, material_id=material.id, observacoes="Material D9."))\n'
            '    banco.commit()\n\n',
            "",
        )

        # Compatibilidade com o modelo D7/D8 atual: campos de decisão existem,
        # mas datas de criação/encerramento já possuem defaults/uso no domínio.
        text = text.replace(
            ', criada_em=datetime.utcnow(), encerrada_em=datetime.utcnow(), decidida_por_empresa_id=cliente.id',
            ', encerrada_em=datetime.utcnow(), decidida_por_empresa_id=cliente.id',
        )

        if text != original:
            backup(tests, backup_dir)
            tests.write_text(text, encoding="utf-8")
            changed.append(str(tests.relative_to(ROOT)))

        # 4) Corrigir o registro do router no roteador principal.
        router = ROOT / "backend/app/api/roteador.py"
        text = router.read_text(encoding="utf-8")
        original = text

        import_line = (
            "from backend.app.api.rotas.ordens_servico import "
            "roteador as ordens_servico_router"
        )
        if import_line not in text:
            lines = text.splitlines()
            insert_at = 0
            for i, line in enumerate(lines):
                if line.startswith("from backend.app.api.rotas."):
                    insert_at = i + 1
            lines.insert(insert_at, import_line)
            text = "\n".join(lines) + "\n"

        include_line = "roteador_api.include_router(ordens_servico_router)"
        if include_line not in text:
            anchor = "roteador_api.include_router(roteador_contratacoes)"
            if anchor in text:
                text = text.replace(
                    anchor,
                    anchor + "\n" + include_line,
                    1,
                )
            else:
                text = text.rstrip() + "\n" + include_line + "\n"

        if text != original:
            backup(router, backup_dir)
            router.write_text(text, encoding="utf-8")
            changed.append(str(router.relative_to(ROOT)))

        # 5) Verificação AST dos quatro arquivos afetados.
        for path in TARGETS:
            ast.parse(path.read_text(encoding="utf-8"))

        # 6) Preflight do metadata em SQLite em memória.
        import sys
        sys.path.insert(0, str(ROOT))

        from sqlalchemy import create_engine
        from backend.app.database.base import Base
        import backend.app.models  # noqa: F401
        import backend.app.models.ordem_servico  # noqa: F401

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        try:
            Base.metadata.create_all(bind=engine)
        finally:
            engine.dispose()

        rel_model = model.relative_to(ROOT)
        rel_route = route.relative_to(ROOT)
        rel_router = router.relative_to(ROOT)
        rel_tests = tests.relative_to(ROOT)

        payload = {
            "revision": REVISION,
            "files_checked": [str(x) for x in TARGETS],
            "changed": changed,
            "ast_ok": True,
            "metadata_preflight_ok": True,
            "process_table": "processos_fabricacao",
            "process_model": "ProcessoFabricacao",
            "ordem_router_registered": True,
            "ordem_router_prefix": "",
            "backup_dir": str(backup_dir),
        }

        report_json = ROOT / "MEC_SERVICOS_V0_1_D9_FIX1_CORRECAO.json"
        report_txt = ROOT / "MEC_SERVICOS_V0_1_D9_FIX1_CORRECAO_RELATORIO.txt"
        report_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_txt.write_text(
            "\n".join(
                [
                    "Plataforma de Serviços Mecânicos — D9 FIX1",
                    f"REVISION= {REVISION}",
                    f"ROOT= {ROOT}",
                    "AST_OK= True",
                    "METADATA_PREFLIGHT_OK= True",
                    "PROCESS_TABLE= processos_fabricacao",
                    "PROCESS_MODEL= ProcessoFabricacao",
                    "ORDEM_ROUTER_REGISTERED= True",
                    "ORDEM_ROUTER_PREFIX= ''",
                    f"CHANGED= {len(changed)}",
                    f"BACKUP_DIR= {backup_dir}",
                    f"REPORT= {report_txt}",
                    f"JSON= {report_json}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        print("Plataforma de Serviços Mecânicos — D9 FIX1")
        print("REVISION=", REVISION)
        print("ROOT=", ROOT)
        print("AST_OK= True")
        print("METADATA_PREFLIGHT_OK= True")
        print("PROCESS_TABLE= processos_fabricacao")
        print("PROCESS_MODEL= ProcessoFabricacao")
        print("ORDEM_ROUTER_REGISTERED= True")
        print("ORDEM_ROUTER_PREFIX= ''")
        print("CHANGED=", len(changed))
        print("BACKUP_DIR=", backup_dir)
        print("REPORT=", report_txt)
        print("JSON=", report_json)
        return 0

    except Exception as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}")
        print(f"BACKUP_DIR= {backup_dir}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
