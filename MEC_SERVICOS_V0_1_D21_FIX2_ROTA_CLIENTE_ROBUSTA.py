from __future__ import annotations

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path

TARGET_APP = Path("frontend/src/App.tsx")
PAGE_FILE = Path("frontend/src/pages/client/ClientSolicitacoesPage.tsx")
PAGE_IMPORT = 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";'
BACKUP_ROOT = "_mec_backups"


def find_root() -> Path:
    for root in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (root / TARGET_APP).exists() and (root / "backend" / "app" / "principal.py").exists():
            return root
    raise RuntimeError("Nao encontrei a raiz do MEC-Servicos.")


def backup(root: Path, target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = root / BACKUP_ROOT / f"D21_FIX2_ROTA_CLIENTE_ROBUSTA_{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, directory / target.name)
    return directory


def patch_app(target: Path) -> bool:
    source = target.read_text(encoding="utf-8")

    if PAGE_IMPORT not in source:
        marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
        if marker not in source:
            raise RuntimeError("Nao encontrei o import de ClientDashboard em App.tsx.")
        source = source.replace(marker, marker + "\n" + PAGE_IMPORT, 1)

    client_marker = '<Route path="/cliente" element={<ClientLayout />}>'
    start = source.find(client_marker)
    if start < 0:
        raise RuntimeError('Nao encontrei a rota pai /cliente com ClientLayout.')

    end = source.find("\n        </Route>", start)
    if end < 0:
        raise RuntimeError("Nao encontrei o fechamento da rota pai /cliente.")

    client_block = source[start:end]

    pattern = re.compile(
        r'<Route\s+path="solicitacoes"\s+element=\{\s*<ModulePage\b.*?/>\s*\}\s*/>',
        re.S,
    )
    match = pattern.search(client_block)

    if not match:
        raise RuntimeError(
            'Nao encontrei a rota cliente path="solicitacoes" usando ModulePage.'
        )

    replacement = (
        '<Route\n'
        '            path="solicitacoes"\n'
        '            element={<ClientSolicitacoesPage />}\n'
        '          />'
    )

    patched_block = client_block[:match.start()] + replacement + client_block[match.end():]
    source = source[:start] + patched_block + source[end:]

    target.write_text(
        source.rstrip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return True


def validate(target: Path) -> None:
    source = target.read_text(encoding="utf-8")
    ast.parse(source)

    if PAGE_IMPORT not in source:
        raise RuntimeError("Import ClientSolicitacoesPage ausente.")

    client_marker = '<Route path="/cliente" element={<ClientLayout />}>'
    start = source.find(client_marker)
    if start < 0:
        raise RuntimeError("Rota pai /cliente ausente.")

    end = source.find("\n        </Route>", start)
    if end < 0:
        raise RuntimeError("Fechamento da rota /cliente ausente.")

    client_block = source[start:end]

    if "<ClientSolicitacoesPage />" not in client_block:
        raise RuntimeError("ClientSolicitacoesPage nao foi conectado dentro da rota /cliente.")

    old_pattern = re.compile(
        r'<Route\s+path="solicitacoes"\s+element=\{\s*<ModulePage\b',
        re.S,
    )
    if old_pattern.search(client_block):
        raise RuntimeError("A rota cliente solicitacoes ainda aponta para ModulePage.")


def main() -> int:
    print("MEC Servicos - D21 FIX2 Rota Cliente Robusta")

    root = find_root()
    target = root / TARGET_APP

    print(f"ROOT={root}")
    print(f"TARGET={target}")

    page_file = root / PAGE_FILE
    print(f"PAGE_FILE={page_file}")
    if not page_file.exists():
        raise RuntimeError(
            "ClientSolicitacoesPage.tsx nao foi encontrado. "
            "O D21 principal precisa criar a pagina antes da rota ser conectada."
        )

    backup_dir = backup(root, target)
    print(f"BACKUP_DIR={backup_dir}")

    try:
        changed = patch_app(target)
        print(f"PATCHED={changed}")

        validate(target)

        print("AST_OK=True")
        print("CLIENT_ROUTE_FOUND=True")
        print("CLIENT_ROUTE_PATCHED=True")
        print("CLIENT_SOLICITACOES_PAGE=True")
        print("BACKEND_CHANGED=False")
        print("D21_FIX2=OK")
        print()
        print("Agora execute:")
        print("cd .\\frontend")
        print("npm run build")
        print("cd ..")
        return 0

    except Exception as exc:
        print(f"ERRO={type(exc).__name__}: {exc}")
        print("Restaurando App.tsx...")
        shutil.copy2(backup_dir / target.name, target)
        print("RESTORED=True")
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
