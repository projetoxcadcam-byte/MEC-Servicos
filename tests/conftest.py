

# MEC_D30_TESTES_NEGOCIO_INICIO
# Os testes anteriores ao D30 verificam regras de negócio no contexto admin.
# Só arquivos com o hash registrado na instalação recebem essa compatibilidade.
# test_acesso_d30.py e testes marcados acesso_real usam sessões reais, sem override.
import hashlib as _mec_hashlib
import json as _mec_json
from pathlib import Path as _MecPath
import pytest as _mec_pytest


@_mec_pytest.hookimpl(specname="pytest_configure")
def pytest_configure_mec_d30(config):
    config.addinivalue_line("markers", "acesso_real: autenticação real D30, sem compatibilidade de testes legados")


@_mec_pytest.fixture(autouse=True)
def _mec_d30_contexto_testes_negocio(request, monkeypatch):
    if request.node.get_closest_marker("acesso_real"):
        return
    raiz = _MecPath(__file__).resolve().parent.parent
    arquivo = _MecPath(str(request.node.path)).resolve()
    try:
        relativo = arquivo.relative_to(raiz).as_posix()
        manifesto = _mec_json.loads((raiz / "tests/mec_d30_legado_sha256.json").read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    esperado = manifesto.get(relativo)
    if not esperado or _mec_hashlib.sha256(arquivo.read_bytes()).hexdigest() != esperado:
        return
    from fastapi import Request as _MecRequest
    from starlette.testclient import TestClient as _MecTestClient
    from backend.app.core.armazenamento_acesso import UsuarioAcesso as _MecUsuario
    from backend.app.core.permissoes_acesso import autorizar_requisicao as _mec_autorizar
    def administrador_de_teste(request: _MecRequest):
        request.state.usuario_acesso = _MecUsuario(0, "Teste de negócio", "teste@local.invalid", "admin", None, False)
    # A anotação precisa ser resolvida também em conftest com future annotations.
    administrador_de_teste.__annotations__["request"] = _MecRequest
    anterior = _MecTestClient.request
    aplicativos = set()
    def requisicao_contexto(cliente, *args, **kwargs):
        app = cliente.app
        if id(app) not in aplicativos:
            monkeypatch.setitem(app.dependency_overrides, _mec_autorizar, administrador_de_teste)
            aplicativos.add(id(app))
        return anterior(cliente, *args, **kwargs)
    monkeypatch.setattr(_MecTestClient, "request", requisicao_contexto)
# MEC_D30_TESTES_NEGOCIO_FIM
