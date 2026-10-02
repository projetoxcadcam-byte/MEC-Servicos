from __future__ import annotations

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path

TARGET_APP = Path("frontend/src/App.tsx")
PAGE_FILE = Path("frontend/src/pages/client/ClientSolicitacoesPage.tsx")
BACKUP_ROOT = "_mec_backups"

IMPORT_RE = re.compile(
    r'(?m)^[ \t]*import[ \t]+ClientSolicitacoesPage[ \t]+from[ \t]+["\']'
    r'\./pages/client/ClientSolicitacoesPage["\'];?[ \t]*$'
)

CLIENT_PARENT_RE = re.compile(
    r'(?m)^(?P<indent>[ \t]*)<Route\s+'
    r'path=["\']/cliente["\']\s+'
    r'element=\{\s*<ClientLayout\s*/>\s*\}>[ \t]*$'
)

CLIENT_SOLICITACAO_RE = re.compile(
    r'(?ms)^[ \t]*<Route\s+'
    r'path=["\']solicitacoes["\']\s+'
    r'element=\{\s*'
    r'<ModulePage\b.*?'
    r'/>\s*'
    r'\}\s*/>[ \t]*'
)


def find_root() -> Path:
    for root in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (
            (root / TARGET_APP).exists()
            and (root / "backend" / "app" / "principal.py").exists()
        ):
            return root
    raise RuntimeError("Nao encontrei a raiz do MEC-Servicos.")


def backup(root: Path, target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = root / BACKUP_ROOT / f"D21_FIX3_ROTA_CLIENTE_ULTRA_ROBUSTA_{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, directory / target.name)
    return directory


def diagnostics(source: str) -> None:
    print(f"CLIENT_LAYOUT_IMPORT={'True' if 'ClientLayout' in source else 'False'}")
    print(f"CLIENT_PARENT_REGEX={'True' if CLIENT_PARENT_RE.search(source) else 'False'}")
    print(f"CLIENT_ROUTE_WORD={'True' if '/cliente' in source or 'cliente' in source else 'False'}")
    print(f"SOLICITACOES_WORD={'True' if 'solicitacoes' in source else 'False'}")

    relevant = []
    for index, line in enumerate(source.splitlines(), start=1):
        low = line.lower()
        if "clientelayout" in low or '"/cliente"' in low or "'/cliente'" in low:
            relevant.append((index, line))
    if relevant:
        print("DIAGNOSTIC_LINES:")
        for index, line in relevant[:20]:
            print(f"  {index}: {line}")


def add_import(source: str) -> str:
    if IMPORT_RE.search(source):
        return source

    marker = re.search(
        r'(?m)^[ \t]*import[ \t]+ClientDashboard[ \t]+from[ \t]+["\']'
        r'\./pages/client/ClientDashboard["\'];?[ \t]*$',
        source,
    )
    if marker:
        line = marker.group(0)
        return source[:marker.end()] + "\n" + line.replace(
            "ClientDashboard",
            "ClientSolicitacoesPage",
        ).replace(
            './pages/client/ClientDashboard',
            './pages/client/ClientSolicitacoesPage',
        ) + source[marker.end():]

    # Fallback: insert before ModulePage import.
    module_marker = re.search(
        r'(?m)^[ \t]*import[ \t]+ModulePage[ \t]+from[ \t]+["\']\./pages/ModulePage["\'];?[ \t]*$',
        source,
    )
    if module_marker:
        return (
            source[:module_marker.start()]
            + IMPORT_RE.pattern.split("$", 1)[0].replace(
                r"(?m)^", ""
            )
            + 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";\n'
            + source[module_marker.start():]
        )

    raise RuntimeError("Nao encontrei um ponto seguro para inserir o import de ClientSolicitacoesPage.")


def patch_app(target: Path) -> bool:
    source = target.read_text(encoding="utf-8")
    diagnostics(source)

    parent = CLIENT_PARENT_RE.search(source)
    if not parent:
        raise RuntimeError(
            "Nao encontrei a rota pai /cliente com ClientLayout. "
            "O diagnostico acima mostra a forma real encontrada em App.tsx."
        )

    indent = parent.group("indent")
    close_re = re.compile(rf"(?m)^{re.escape(indent)}</Route>\s*$")
    close = close_re.search(source, parent.end())
    if not close:
        raise RuntimeError("Nao encontrei o fechamento da rota pai /cliente.")

    block = source[parent.start():close.end()]

    child = CLIENT_SOLICITACAO_RE.search(block)
    if not child:
        raise RuntimeError(
            'Nao encontrei dentro de /cliente a rota path="solicitacoes" usando ModulePage.'
        )

    old = child.group(0)
    child_indent_match = re.match(r"[ \t]*", old)
    child_indent = child_indent_match.group(0) if child_indent_match else indent + "  "

    replacement = (
        f'{child_indent}<Route\n'
        f'{child_indent}  path="solicitacoes"\n'
        f'{child_indent}  element={{<ClientSolicitacoesPage />}}\n'
        f'{child_indent}/>\n'
    )

    block = block[:child.start()] + replacement + block[child.end():]

    source = source[:parent.start()] + block + source[close.end():]

    if not IMPORT_RE.search(source):
        source = add_import(source)

    target.write_text(
        source.rstrip("\r\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return True


def validate(target: Path) -> None:
    source = target.read_text(encoding="utf-8")
    ast.parse(source)

    if not IMPORT_RE.search(source):
        raise RuntimeError("Import ClientSolicitacoesPage ausente.")

    parent = CLIENT_PARENT_RE.search(source)
    if not parent:
        raise RuntimeError("Rota pai /cliente ausente apos patch.")

    indent = parent.group("indent")
    close_re = re.compile(rf"(?m)^{re.escape(indent)}</Route>\s*$")
    close = close_re.search(source, parent.end())
    if not close:
        raise RuntimeError("Fechamento da rota /cliente ausente apos patch.")

    block = source[parent.start():close.end()]

    if '<ClientSolicitacoesPage />' not in block:
        raise RuntimeError("ClientSolicitacoesPage nao esta dentro da rota /cliente.")

    if CLIENT_SOLICITACAO_RE.search(block):
        raise RuntimeError("A rota cliente solicitacoes ainda aponta para ModulePage.")


def main() -> int:
    print("MEC Servicos - D21 FIX3 Rota Cliente Ultra Robusta")

    root = find_root()
    target = root / TARGET_APP
    page = root / PAGE_FILE

    print(f"ROOT={root}")
    print(f"TARGET={target}")
    print(f"PAGE_FILE={page}")

    if not page.exists():
        raise RuntimeError(
            "ClientSolicitacoesPage.tsx nao foi encontrado. "
            "Nao vou alterar a rota sem a pagina existir."
        )

    backup_dir = backup(root, target)
    print(f"BACKUP_DIR={backup_dir}")

    try:
        patch_app(target)
        print("PATCHED=True")
        validate(target)
        print("AST_OK=True")
        print("CLIENT_ROUTE_FOUND=True")
        print("CLIENT_ROUTE_PATCHED=True")
        print("CLIENT_SOLICITACOES_PAGE=True")
        print("BACKEND_CHANGED=False")
        print("D21_FIX3=OK")
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
