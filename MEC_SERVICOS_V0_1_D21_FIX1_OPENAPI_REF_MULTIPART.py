from __future__ import annotations

import ast
import importlib.util
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

TARGET_NAME = "MEC_SERVICOS_V0_1_D21_PORTAL_CLIENTE_SOLICITACOES_COMPLETO.py"
BACKUP_ROOT = "_mec_backups"


def find_root() -> Path:
    for root in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (
            (root / "backend" / "app" / "principal.py").exists()
            and (root / "frontend" / "src" / "App.tsx").exists()
            and (root / TARGET_NAME).exists()
        ):
            return root
    raise RuntimeError(
        "Nao encontrei a raiz do MEC-Servicos. "
        "Execute este script na raiz do projeto."
    )


def backup_file(root: Path, target: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / BACKUP_ROOT / f"D21_FIX1_OPENAPI_REF_MULTIPART_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup_dir / target.name)
    return backup_dir


def patch_contracts(target: Path) -> bool:
    original = target.read_text(encoding="utf-8")

    if "def resolve_ref(schema: object)" in original:
        return False

    replacement = r'''def contracts(openapi: dict) -> tuple[str, str, str]:
    paths = openapi.get("paths", {})
    solicitation = None
    technical_path = None
    technical_field = None

    def resolve_ref(schema: object) -> dict:
        if not isinstance(schema, dict):
            return {}

        current = schema
        visited: set[str] = set()

        while isinstance(current, dict) and "$ref" in current:
            ref = current.get("$ref")

            if not isinstance(ref, str) or not ref.startswith("#/"):
                return {}

            if ref in visited:
                return {}

            visited.add(ref)
            node: object = openapi

            for part in ref[2:].split("/"):
                if not isinstance(node, dict):
                    return {}

                node = node.get(
                    part.replace("~1", "/").replace("~0", "~")
                )

            if not isinstance(node, dict):
                return {}

            current = node

        return current if isinstance(current, dict) else {}

    def collect_properties(schema: object) -> dict:
        resolved = resolve_ref(schema)
        properties = dict(resolved.get("properties") or {})

        for branch in resolved.get("allOf", []) or []:
            properties.update(collect_properties(branch))

        return properties

    def is_file_schema(name: str, schema: object) -> bool:
        resolved = resolve_ref(schema)

        if resolved.get("format") == "binary":
            return True

        if (
            resolved.get("type") == "string"
            and resolved.get("contentMediaType")
        ):
            return True

        return name.strip().lower() in {
            "file",
            "arquivo",
            "arquivo_tecnico",
            "arquivo-tecnico",
        }

    for path, item in paths.items():
        if not isinstance(item, dict):
            continue

        if (
            path.endswith("/solicitacoes-servico")
            and item.get("get")
            and item.get("post")
        ):
            names = {
                str(parameter.get("name"))
                for parameter in item["get"].get("parameters", [])
                if isinstance(parameter, dict)
            }

            if "empresa_cliente_id" in names:
                solicitation = path

        if "arquivos-tecnicos" in path and item.get("post"):
            multipart = (
                item["post"]
                .get("requestBody", {})
                .get("content", {})
                .get("multipart/form-data")
            )

            if not multipart:
                continue

            props = collect_properties(multipart.get("schema", {}))

            for name, field_schema in props.items():
                if is_file_schema(str(name), field_schema):
                    technical_path = path
                    technical_field = str(name)
                    break

    if not solicitation:
        raise RuntimeError(
            "OpenAPI nao expos GET+POST /solicitacoes-servico "
            "com filtro empresa_cliente_id."
        )

    if not technical_path or not technical_field:
        raise RuntimeError(
            "OpenAPI nao expos uma rota multipart de Arquivos Tecnicos."
        )

    return solicitation, technical_path, technical_field
'''

    pattern = re.compile(
        r"(?ms)^def contracts\(openapi: dict\).*?(?=^def backup\()"
    )
    match = pattern.search(original)

    if not match:
        raise RuntimeError(
            "Nao encontrei a funcao contracts() esperada no D21."
        )

    updated = (
        original[:match.start()]
        + replacement.rstrip()
        + "\n\n"
        + original[match.end():]
    )

    target.write_text(
        updated.rstrip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return True


def validate_ast(target: Path) -> None:
    ast.parse(target.read_text(encoding="utf-8"))


def validate_contract(root: Path, target: Path) -> tuple[str, str, str]:
    sys.path.insert(0, str(root))

    from backend.app.principal import app

    spec = importlib.util.spec_from_file_location("d21_target", target)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Nao foi possivel carregar o D21 para validacao."
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module.contracts(app.openapi())


def main() -> int:
    print("MEC Servicos - D21 FIX1 OpenAPI $ref + multipart")

    root = find_root()
    target = root / TARGET_NAME

    print(f"ROOT={root}")
    print(f"TARGET={target}")

    backup_dir = backup_file(root, target)
    print(f"BACKUP_DIR={backup_dir}")

    changed = patch_contracts(target)
    print(f"PATCHED={changed}")

    try:
        validate_ast(target)
        print("AST_OK=True")

        solicitation, technical_path, technical_field = validate_contract(
            root, target
        )

        print(f"SOLICITACAO_LIST_ENDPOINT={solicitation}")
        print(f"MULTIPART_ENDPOINT={technical_path}")
        print(f"TECHNICAL_FIELD={technical_field}")
        print("OPENAPI_REF_RESOLUTION=True")
        print("CONTENT_MEDIA_TYPE_SUPPORT=True")
        print("BACKEND_CHANGED=False")
        print("D21_FIX1=OK")
        print()
        print("Agora execute:")
        print(f"python .\\{TARGET_NAME}")
        return 0

    except Exception as exc:
        print(f"ERRO={type(exc).__name__}: {exc}")
        print("Restaurando o backup do D21...")
        shutil.copy2(backup_dir / target.name, target)
        print("RESTORED=True")
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
