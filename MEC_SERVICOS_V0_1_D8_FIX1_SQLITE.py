from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGET = ROOT / "tests" / "test_contratacoes.py"
BACKUP_ROOT = ROOT / "_mec_backups"
REVISION = "MEC-SERVICOS-V0.1-D8-FIX1-SQLITE-STATICPOOL-2026-10-01"


def main() -> int:
    report_path = ROOT / "MEC_SERVICOS_V0_1_D8_FIX1_SQLITE_RELATORIO.txt"
    json_path = ROOT / "MEC_SERVICOS_V0_1_D8_FIX1_SQLITE.json"

    lines: list[str] = [
        "Plataforma de Serviços Mecânicos — D8 FIX1",
        f"REVISION= {REVISION}",
        f"ROOT= {ROOT}",
        f"TARGET= {TARGET}",
    ]

    result = {
        "revision": REVISION,
        "root": str(ROOT),
        "target": str(TARGET),
        "target_exists": TARGET.exists(),
        "changed": False,
        "backup": None,
        "ast_ok": False,
        "staticpool_ok": False,
        "sqlite_memory_shared_ok": False,
        "error": None,
    }

    try:
        if not TARGET.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {TARGET}")

        original = TARGET.read_text(encoding="utf-8")

        # Diagnóstico antes do patch.
        had_staticpool = "from sqlalchemy.pool import StaticPool" in original
        had_poolclass = "poolclass=StaticPool" in original
        had_memory_url = '"sqlite:///:memory:"' in original

        # O padrão correto para SQLite em memória compartilhado entre
        # threads/TestClient é sqlite:// + StaticPool.
        updated = original

        if not had_staticpool:
            marker = "from sqlalchemy.orm import sessionmaker\n"
            if marker not in updated:
                raise RuntimeError(
                    "Não encontrei o import sessionmaker esperado para inserir StaticPool."
                )
            updated = updated.replace(
                marker,
                marker + "from sqlalchemy.pool import StaticPool\n",
                1,
            )

        if had_memory_url:
            updated = updated.replace(
                '"sqlite:///:memory:"',
                '"sqlite://"',
                1,
            )

        if "poolclass=StaticPool" not in updated:
            marker = '        connect_args={"check_same_thread": False},\n'
            if marker not in updated:
                raise RuntimeError(
                    "Não encontrei connect_args esperado para inserir poolclass=StaticPool."
                )
            updated = updated.replace(
                marker,
                marker + "        poolclass=StaticPool,\n",
                1,
            )

        if updated != original:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = BACKUP_ROOT / f"D8_FIX1_SQLITE_{stamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / "test_contratacoes.py"
            shutil.copy2(TARGET, backup_file)

            TARGET.write_text(updated, encoding="utf-8")

            result["changed"] = True
            result["backup"] = str(backup_file)
            lines.append(f"BACKUP= {backup_file}")
            lines.append("CHANGED= True")
        else:
            lines.append("CHANGED= False (patch já aplicado)")

        final_text = TARGET.read_text(encoding="utf-8")
        ast.parse(final_text)
        result["ast_ok"] = True

        result["staticpool_ok"] = (
            "from sqlalchemy.pool import StaticPool" in final_text
            and "poolclass=StaticPool" in final_text
        )
        result["sqlite_memory_shared_ok"] = (
            '"sqlite://"' in final_text
            and '"sqlite:///:memory:"' not in final_text
            and "poolclass=StaticPool" in final_text
        )

        lines.extend(
            [
                f"AST_OK= {result['ast_ok']}",
                f"STATICPOOL_OK= {result['staticpool_ok']}",
                f"SQLITE_MEMORY_SHARED_OK= {result['sqlite_memory_shared_ok']}",
                "EXPECTED_ENGINE= sqlite:// + StaticPool + check_same_thread=False",
            ]
        )

        if not result["staticpool_ok"] or not result["sqlite_memory_shared_ok"]:
            raise RuntimeError(
                "O patch não deixou o teste no padrão esperado de SQLite em memória compartilhado."
            )

        lines.append("D8_FIX1_SQLITE_APPLIED= True")

    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        lines.append(f"ERRO= {result['error']}")
        lines.append("D8_FIX1_SQLITE_APPLIED= False")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n".join(lines))
    print(f"REPORT= {report_path}")
    print(f"JSON= {json_path}")

    return 0 if result["error"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
