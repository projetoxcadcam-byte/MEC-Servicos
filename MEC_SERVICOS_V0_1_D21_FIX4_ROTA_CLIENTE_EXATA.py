from __future__ import annotations

import ast
import shutil
from pathlib import Path
from datetime import datetime


TARGET = Path("frontend/src/App.tsx")
PAGE = Path("frontend/src/pages/client/ClientSolicitacoesPage.tsx")
IMPORT_LINE = 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";'
BACKUP_ROOT = Path("_mec_backups")

OLD_ROUTE = r'''<Route
            path="solicitacoes"
            element={
              <ModulePage
                title="Minhas Solicitações"
                description="Crie e acompanhe suas solicitações de serviços mecânicos."
              />
            }
          />'''

NEW_ROUTE = r'''<Route
            path="solicitacoes"
            element={<ClientSolicitacoesPage />}
          />'''


def find_root() -> Path:
    for root in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (
            (root / TARGET).exists()
            and (root / "backend" / "app" / "principal.py").exists()
        ):
            return root
    raise RuntimeError("Nao encontrei a raiz do MEC-Servicos.")


def backup(root: Path, target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = root / BACKUP_ROOT / f"D21_FIX4_ROTA_CLIENTE_EXATA_{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, directory / target.name)
    return directory


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def patch_app(target: Path) -> bool:
    source = normalize(target.read_text(encoding="utf-8"))

    if not PAGE.exists():
        raise RuntimeError(
            "ClientSolicitacoesPage.tsx nao existe. "
            "O D21 principal nao criou a pagina esperada."
        )

    if IMPORT_LINE not in source:
        marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
        if marker not in source:
            raise RuntimeError(
                "Nao encontrei o import de ClientDashboard para inserir o import da pagina."
            )
        source = source.replace(
            marker,
            marker + "\n" + IMPORT_LINE,
            1,
        )

    if NEW_ROUTE in source:
        return False

    if OLD_ROUTE not in source:
        raise RuntimeError(
            "A rota exata 'Minhas Solicitações' nao foi encontrada. "
            "Nenhuma alteracao foi aplicada."
        )

    source = source.replace(OLD_ROUTE, NEW_ROUTE, 1)

    target.write_text(
        source.rstrip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return True


def validate(target: Path) -> None:
    source = normalize(target.read_text(encoding="utf-8"))

    ast.parse(source)

    if IMPORT_LINE not in source:
        raise RuntimeError("Import ClientSolicitacoesPage ausente.")

    if NEW_ROUTE not in source:
        raise RuntimeError(
            "A rota Minhas Solicitações nao aponta para ClientSolicitacoesPage."
        )

    if OLD_ROUTE in source:
        raise RuntimeError(
            "A rota antiga ainda aponta para ModulePage."
        )

    if 'path="/cliente"' not in source:
        raise RuntimeError("Rota /cliente nao encontrada.")

    if '<Route path="/cliente" element={<ClientLayout />}>' not in source:
        raise RuntimeError(
            "Rota /cliente nao esta na forma esperada."
        )


def main() -> int:
    print("MEC Servicos - D21 FIX4 Rota Cliente Exata")

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
        changed = patch_app(target)
        print(f"PATCHED={changed}")

        validate(target)

        print("AST_OK=True")
        print("CLIENT_ROUTE_FOUND=True")
        print("CLIENT_SOLICITACOES_ROUTE=True")
        print("CLIENT_SOLICITACOES_PAGE=True")
        print("BACKEND_CHANGED=False")
        print("D21_FIX4=OK")
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
