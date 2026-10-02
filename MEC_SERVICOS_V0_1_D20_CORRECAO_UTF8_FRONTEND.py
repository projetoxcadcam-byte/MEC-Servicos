from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BACKUP_ROOT = ROOT / "_mec_backups"

TEXT_EXTENSIONS = {
    ".ts", ".tsx", ".css", ".html", ".json", ".md", ".txt", ".svg",
    ".js", ".jsx", ".xml", ".yml", ".yaml"
}

MOJIBAKE_MARKERS = (
    "Ã", "Â", "â", "ð", "�",
)


def score_mojibake(text: str) -> int:
    return sum(text.count(marker) for marker in MOJIBAKE_MARKERS)


def repair_once(text: str) -> str:
    try:
        candidate = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    # Only accept the conversion when it clearly reduces mojibake.
    before = score_mojibake(text)
    after = score_mojibake(candidate)

    if after < before:
        return candidate

    return text


def repair_text(text: str) -> tuple[str, int]:
    current = text
    passes = 0

    # Handles both single and accidental double encoding.
    for _ in range(4):
        repaired = repair_once(current)
        if repaired == current:
            break
        current = repaired
        passes += 1

    return current, passes


def main() -> int:
    print("MEC Serviços — D20 Correção UTF-8 / Mojibake do Frontend")
    print(
        "REVISION= MEC-SERVICOS-V0.1-D20-FIX-UTF8-MOJIBAKE-"
        "FRONTEND-2026-10-01"
    )
    print(f"ROOT= {ROOT}")

    if not FRONTEND.is_dir():
        print("ERRO: pasta frontend não encontrada.")
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D20_UTF8_FRONTEND_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    changed: list[str] = []
    scanned = 0
    backup_count = 0

    for path in FRONTEND.rglob("*"):
        if not path.is_file():
            continue

        if "node_modules" in path.parts or "dist" in path.parts:
            continue

        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue

        scanned += 1

        try:
            original = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                original = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                print(f"SKIP_BINARIO_O_ENCODING= {path.relative_to(ROOT)}")
                continue

        repaired, passes = repair_text(original)

        if repaired == original:
            continue

        relative = path.relative_to(ROOT)
        destination = backup_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        backup_count += 1

        # UTF-8 without BOM. This keeps the source consistently encoded.
        path.write_text(repaired, encoding="utf-8", newline="\n")

        changed.append(str(relative))
        print(f"CORRIGIDO= {relative} | PASSES={passes}")

    report = {
        "revision": "MEC-SERVICOS-V0.1-D20-FIX-UTF8-MOJIBAKE-FRONTEND-2026-10-01",
        "root": str(ROOT),
        "frontend": str(FRONTEND),
        "backup_dir": str(backup_dir),
        "scanned_text_files": scanned,
        "changed_files": len(changed),
        "backed_up_files": backup_count,
        "files": changed,
    }

    report_path = ROOT / "MEC_SERVICOS_V0_1_D20_CORRECAO_UTF8_RELATORIO.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )

    print()
    print(f"SCANNED= {scanned}")
    print(f"CHANGED= {len(changed)}")
    print(f"BACKED_UP= {backup_count}")
    print(f"BACKUP_DIR= {backup_dir}")
    print(f"REPORT= {report_path}")

    if changed:
        print()
        print("UTF8_CORRIGIDO= True")
        print("Próximos comandos:")
        print("cd .\\frontend")
        print("npm run build")
        print("cd ..")
        print("git diff --check")
    else:
        print()
        print("UTF8_CORRIGIDO= False")
        print("Nenhum arquivo com mojibake detectado no frontend.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
