
from __future__ import annotations

import ast
import importlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_NAME = "MEC_SERVICOS_V0_1_D21_FIX2_BACKEND_CONTRATO.py"
REVISION = "MEC-SERVICOS-V0.1-D21-FIX2-BACKEND-CONTRATO-2026-10-01"
BACKUP_ROOT = "_mec_backups"


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_utf8(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        normalize(content).rstrip("\n") + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def find_root() -> Path:
    here = Path.cwd().resolve()
    for root in [here, *here.parents]:
        if (
            (root / "backend" / "app" / "principal.py").exists()
            and (root / "frontend").exists()
        ):
            return root
    raise RuntimeError("Não encontrei a raiz do MEC-Servicos.")


def backup_files(root: Path, paths: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / BACKUP_ROOT / f"D21_FIX2_BACKEND_CONTRATO_{stamp}"

    for path in paths:
        if path.exists():
            destination = backup_dir / path.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)

    return backup_dir


def validate_ast(path: Path) -> None:
    ast.parse(path.read_text(encoding="utf-8"))


def patch_router(router_path: Path) -> bool:
    text = normalize(router_path.read_text(encoding="utf-8"))

    import_line = (
        "from backend.app.api.rotas.arquivos_tecnicos "
        "import roteador as roteador_arquivos_tecnicos"
    )
    include_line = "roteador_api.include_router(roteador_arquivos_tecnicos)"

    changed = False

    if import_line not in text:
        anchor = (
            "from backend.app.api.rotas.ranking_fornecedores "
            "import roteador as roteador_ranking_fornecedores"
        )

        if anchor in text:
            text = text.replace(
                anchor,
                anchor + "\n" + import_line,
                1,
            )
        else:
            text += "\n" + import_line

        changed = True

    if include_line not in text:
        anchor = (
            "roteador_api.include_router("
            "roteador_ranking_fornecedores"
            ")"
        )

        if anchor in text:
            text = text.replace(
                anchor,
                anchor + "\n" + include_line,
                1,
            )
        else:
            text += "\n" + include_line

        changed = True

    if changed:
        write_utf8(router_path, text)

    return changed


def patch_repository(repository_path: Path) -> bool:
    text = normalize(repository_path.read_text(encoding="utf-8"))

    if "def listar_solicitacoes_por_cliente(" in text:
        return False

    marker = (
        "    def listar_fornecedores_compativeis(\n"
        "        self,\n"
        "        solicitacao: SolicitacaoServico,\n"
    )

    method = """    def listar_solicitacoes_por_cliente(
        self,
        empresa_cliente_id: int,
    ) -> list[SolicitacaoServico]:
        consulta = (
            select(SolicitacaoServico)
            .where(
                SolicitacaoServico.empresa_cliente_id == empresa_cliente_id
            )
            .order_by(SolicitacaoServico.id.desc())
        )
        return list(self.banco.scalars(consulta).all())

"""

    if marker not in text:
        raise RuntimeError(
            "Não encontrei o ponto seguro para inserir a listagem "
            "de solicitações no RepositorioCompatibilidade."
        )

    text = text.replace(marker, method + marker, 1)
    write_utf8(repository_path, text)
    return True


def patch_service(service_path: Path) -> bool:
    text = normalize(service_path.read_text(encoding="utf-8"))

    if "def listar_solicitacoes_por_cliente(" in text:
        return False

    marker = (
        "    def listar_fornecedores_compativeis(\n"
        "        self,\n"
        "        solicitacao_id: int,\n"
    )

    method = """    def listar_solicitacoes_por_cliente(
        self,
        empresa_cliente_id: int,
    ) -> list[SolicitacaoServico]:
        return self.repositorio.listar_solicitacoes_por_cliente(
            empresa_cliente_id
        )

"""

    if marker not in text:
        raise RuntimeError(
            "Não encontrei o ponto seguro para inserir a listagem "
            "de solicitações no ServicoCompatibilidade."
        )

    text = text.replace(marker, method + marker, 1)
    write_utf8(service_path, text)
    return True


def patch_solicitacoes_route(route_path: Path) -> bool:
    text = normalize(route_path.read_text(encoding="utf-8"))

    if "def listar_solicitacoes(" in text:
        return False

    marker = '\n\n@roteador.post(\n    "",\n'

    method = """

@roteador.get(
    "",
    response_model=list[SolicitacaoServicoLeitura],
)
def listar_solicitacoes(
    empresa_cliente_id: int,
    banco: SessaoBanco,
) -> list[SolicitacaoServicoLeitura]:
    return [
        SolicitacaoServicoLeitura.model_validate(item)
        for item in ServicoCompatibilidade(
            banco
        ).listar_solicitacoes_por_cliente(
            empresa_cliente_id
        )
    ]
"""

    if marker not in text:
        raise RuntimeError(
            "Não encontrei o início do POST de solicitações para inserir "
            "o GET de listagem."
        )

    text = text.replace(marker, method + marker, 1)
    write_utf8(route_path, text)
    return True


def patch_requirements(requirements_path: Path) -> bool:
    text = normalize(requirements_path.read_text(encoding="utf-8"))

    if any(
        line.strip().lower().startswith("python-multipart")
        for line in text.splitlines()
    ):
        return False

    if not text.endswith("\n"):
        text += "\n"

    text += "python-multipart>=0.0.9,<1.0\n"
    write_utf8(requirements_path, text)
    return True


def discover_d16_router(root: Path) -> dict:
    sys.path.insert(0, str(root))

    module = importlib.import_module(
        "backend.app.api.rotas.arquivos_tecnicos"
    )

    router = getattr(module, "roteador", None)
    if router is None:
        raise RuntimeError(
            "backend.app.api.rotas.arquivos_tecnicos não expõe "
            "a variável 'roteador'."
        )

    routes = []

    for route in getattr(router, "routes", []):
        routes.append(
            {
                "path": getattr(route, "path", ""),
                "methods": sorted(
                    getattr(route, "methods", set()) or []
                ),
                "endpoint": getattr(
                    getattr(route, "endpoint", None),
                    "__name__",
                    None,
                ),
            }
        )

    return {
        "module": "backend.app.api.rotas.arquivos_tecnicos",
        "routes": routes,
    }


def validate_openapi(root: Path) -> dict:
    sys.path.insert(0, str(root))

    for module_name in [
        "backend.app.api.roteador",
        "backend.app.api.rotas.solicitacoes",
        "backend.app.repositories.compatibilidade",
        "backend.app.services.compatibilidade",
        "backend.app.principal",
    ]:
        module = importlib.import_module(module_name)
        importlib.reload(module)

    from backend.app.principal import app

    schema = app.openapi()
    paths = schema.get("paths", {})

    solicitacao_list_path = None

    for path, item in paths.items():
        if not path.endswith("/solicitacoes-servico"):
            continue

        if not isinstance(item, dict):
            continue

        get_operation = item.get("get")
        post_operation = item.get("post")

        if not get_operation or not post_operation:
            continue

        parameter_names = {
            str(parameter.get("name"))
            for parameter in get_operation.get("parameters", [])
            if isinstance(parameter, dict)
        }

        if "empresa_cliente_id" in parameter_names:
            solicitacao_list_path = path

    multipart_routes = []

    for path, item in paths.items():
        if "arquivos-tecnicos" not in path:
            continue

        if not isinstance(item, dict):
            continue

        for method, operation in item.items():
            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }:
                continue

            if not isinstance(operation, dict):
                continue

            content = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("multipart/form-data")
            )

            if content:
                multipart_routes.append(
                    {
                        "path": path,
                        "method": method.upper(),
                    }
                )

    return {
        "solicitacao_list_path": solicitacao_list_path,
        "multipart_routes": multipart_routes,
    }


def main() -> int:
    root = find_root()

    router_path = root / "backend" / "app" / "api" / "roteador.py"
    repository_path = (
        root / "backend" / "app" / "repositories" / "compatibilidade.py"
    )
    service_path = (
        root / "backend" / "app" / "services" / "compatibilidade.py"
    )
    solicitacoes_path = (
        root / "backend" / "app" / "api" / "rotas" / "solicitacoes.py"
    )
    requirements_path = root / "requirements.txt"
    arquivos_path = (
        root / "backend" / "app" / "api" / "rotas" / "arquivos_tecnicos.py"
    )

    print("MEC Serviços — D21 FIX2 Backend / Contrato do Portal do Cliente")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    required = [
        router_path,
        repository_path,
        service_path,
        solicitacoes_path,
        requirements_path,
        arquivos_path,
    ]

    missing = [
        str(path.relative_to(root))
        for path in required
        if not path.exists()
    ]

    if missing:
        print(f"MISSING_FILES= {missing}")
        print("Nenhuma alteração foi aplicada.")
        return 40

    before_d16 = discover_d16_router(root)

    backup_dir = backup_files(
        root,
        [
            router_path,
            repository_path,
            service_path,
            solicitacoes_path,
            requirements_path,
        ],
    )

    changed = []

    if patch_router(router_path):
        changed.append(str(router_path.relative_to(root)))

    if patch_repository(repository_path):
        changed.append(str(repository_path.relative_to(root)))

    if patch_service(service_path):
        changed.append(str(service_path.relative_to(root)))

    if patch_solicitacoes_route(solicitacoes_path):
        changed.append(str(solicitacoes_path.relative_to(root)))

    if patch_requirements(requirements_path):
        changed.append(str(requirements_path.relative_to(root)))

    for path in [
        router_path,
        repository_path,
        service_path,
        solicitacoes_path,
    ]:
        validate_ast(path)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
        ],
        cwd=root,
        check=True,
    )

    after_openapi = validate_openapi(root)

    pytest = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            ".\\tests\\test_arquivos_tecnicos.py",
            ".\\tests\\test_compatibilidade_fornecedores.py",
            "-q",
        ],
        cwd=root,
        text=True,
        check=False,
    )

    status = (
        "OK"
        if (
            after_openapi["solicitacao_list_path"]
            and after_openapi["multipart_routes"]
            and pytest.returncode == 0
        )
        else "FAILED"
    )

    report = {
        "revision": REVISION,
        "root": str(root),
        "backup_dir": str(backup_dir),
        "changed": changed,
        "d16_router_before_fix": before_d16,
        "openapi_after_fix": after_openapi,
        "pytest_returncode": pytest.returncode,
        "status": status,
    }

    report_path = (
        root / "MEC_SERVICOS_V0_1_D21_FIX2_BACKEND_CONTRATO.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("")
    print(f"BACKUP_DIR= {backup_dir}")
    print(f"CHANGED_FILES= {len(changed)}")
    print(
        "SOLICITACOES_LIST_ENDPOINT="
        f" {after_openapi['solicitacao_list_path']}"
    )
    print(
        "MULTIPART_ROUTES="
        f" {len(after_openapi['multipart_routes'])}"
    )

    for item in after_openapi["multipart_routes"]:
        print(f"  {item['method']} {item['path']}")

    print(
        f"PYTEST= {'OK' if pytest.returncode == 0 else 'FAILED'}"
    )
    print(f"REPORT= {report_path}")

    if status != "OK":
        print("D21_FIX2= FAILED")
        return 40

    print("D21_FIX2= OK")
    print("")
    print("Agora execute novamente:")
    print(
        "  python .\\MEC_SERVICOS_V0_1_D21_PORTAL_CLIENTE_SOLICITACOES_COMPLETO.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
