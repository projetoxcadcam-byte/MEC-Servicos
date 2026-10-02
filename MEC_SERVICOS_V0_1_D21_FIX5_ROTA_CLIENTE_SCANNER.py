from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


TARGET = Path("frontend/src/App.tsx")
PAGE = Path("frontend/src/pages/client/ClientSolicitacoesPage.tsx")
IMPORT_LINE = 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";'
BACKUP_ROOT = Path("_mec_backups")


def find_root() -> Path:
    for root in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (root / TARGET).exists() and (root / "backend" / "app" / "principal.py").exists():
            return root
    raise RuntimeError("Nao encontrei a raiz do MEC-Servicos.")


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def backup(root: Path, target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = root / BACKUP_ROOT / f"D21_FIX5_ROTA_CLIENTE_SCANNER_{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, directory / target.name)
    return directory


def route_start(lines: list[str], index: int) -> int:
    for i in range(index, -1, -1):
        if lines[i].lstrip().startswith("<Route"):
            return i
    raise RuntimeError("Nao encontrei o inicio do Route pai.")


def route_end(lines: list[str], start: int) -> int:
    # Em JSX, o fechamento do Route alvo usa o mesmo recuo da abertura.
    indent = len(lines[start]) - len(lines[start].lstrip())
    for i in range(start + 1, len(lines)):
        line = lines[i]
        current_indent = len(line) - len(line.lstrip())
        if current_indent == indent and line.strip() == "/>":
            return i
    raise RuntimeError("Nao encontrei o fechamento do Route.")


def find_client_solicitacao(lines: list[str]) -> tuple[int, int, int]:
    client_parent = None
    for i, line in enumerate(lines):
        if 'path="/cliente"' in line and "<Route" in line:
            client_parent = i
            break

    if client_parent is None:
        raise RuntimeError("Nao encontrei a rota pai /cliente.")

    for i in range(client_parent + 1, len(lines)):
        # Nao sair do bloco do cliente.
        if i > client_parent and 'path="/admin"' in lines[i] and "<Route" in lines[i]:
            break
        if 'path="solicitacoes"' in lines[i]:
            start = route_start(lines, i)
            end = route_end(lines, start)
            return client_parent, start, end

    raise RuntimeError("Nao encontrei path='solicitacoes' dentro da rota /cliente.")


def patch_app(target: Path) -> tuple[bool, dict[str, object]]:
    source = normalize(target.read_text(encoding="utf-8"))
    lines = source.splitlines()

    if not PAGE.exists():
        raise RuntimeError("ClientSolicitacoesPage.tsx nao existe.")

    if IMPORT_LINE not in source:
        marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
        if marker not in source:
            raise RuntimeError("Nao encontrei import de ClientDashboard.")
        source = source.replace(marker, marker + "\n" + IMPORT_LINE, 1)
        lines = source.splitlines()

    if '<Route' in source and '<ClientSolicitacoesPage />' in source:
        return False, {
            "client_parent": any('path="/cliente"' in x for x in lines),
            "solicitacoes": any('path="solicitacoes"' in x for x in lines),
            "already_patched": True,
        }

    client_parent, start, end = find_client_solicitacao(lines)

    indent = re_indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
    replacement = [
        f'{indent}<Route',
        f'{indent}  path="solicitacoes"',
        f'{indent}  element={{<ClientSolicitacoesPage />}}',
        f'{indent}/>',
    ]

    new_lines = lines[:start] + replacement + lines[end + 1:]
    target.write_text("\n".join(new_lines).rstrip("\n") + "\n", encoding="utf-8", newline="\n")

    return True, {
        "client_parent_line": client_parent + 1,
        "old_route_start": start + 1,
        "old_route_end": end + 1,
    }


def validate(target: Path) -> None:
    source = normalize(target.read_text(encoding="utf-8"))
    ast.parse(source)
    if IMPORT_LINE not in source:
        raise RuntimeError("Import ClientSolicitacoesPage ausente.")
    if '<Route path="/cliente" element={<ClientLayout />}>' not in source:
        raise RuntimeError("Rota /cliente nao esta na forma esperada.")
    if 'path="solicitacoes"' not in source:
        raise RuntimeError("Rota cliente solicitacoes ausente.")
    if '<ClientSolicitacoesPage />' not in source:
        raise RuntimeError("Rota cliente solicitacoes nao aponta para ClientSolicitacoesPage.")


def main() -> int:
    print("MEC Servicos - D21 FIX5 Scanner de Rota Cliente")

    root = find_root()
    target = root / TARGET
    page = root / PAGE
    print(f"ROOT={root}")
    print(f"TARGET={target}")
    print(f"PAGE={page}")
    print(f"PAGE_EXISTS={page.exists()}")

    backup_dir = backup(root, target)
    print(f"BACKUP_DIR={backup_dir}")

    try:
        changed, info = patch_app(target)
        print(f"PATCHED={changed}")
        print(f"SCAN={info}")
        validate(target)
        print("AST_OK=True")
        print("CLIENT_ROUTE_FOUND=True")
        print("CLIENT_SOLICITACOES_ROUTE=True")
        print("CLIENT_SOLICITACOES_PAGE=True")
        print("BACKEND_CHANGED=False")
        print("D21_FIX5=OK")
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
