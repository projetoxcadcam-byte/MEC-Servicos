from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.principal import app


@pytest.fixture()
def cliente() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)

    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = substituir_banco
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_criar_listar_e_obter_empresa(cliente: TestClient) -> None:
    resposta_criacao = cliente.post(
        "/api/v1/empresas",
        json={
            "razao_social": "Oficina Paraná Ltda",
            "documento": "12.345.678/0001-90",
            "tipo_empresa": "fornecedor",
        },
    )
    assert resposta_criacao.status_code == 201
    criada = resposta_criacao.json()
    assert criada["id"] == 1
    assert criada["razao_social"] == "Oficina Paraná Ltda"
    assert criada["documento"] == "12345678000190"
    assert criada["tipo_empresa"] == "fornecedor"
    assert criada["avaliacao"] is None

    resposta_lista = cliente.get("/api/v1/empresas")
    assert resposta_lista.status_code == 200
    lista = resposta_lista.json()
    assert len(lista) == 1
    assert lista[0]["id"] == criada["id"]

    resposta_obter = cliente.get(f"/api/v1/empresas/{criada['id']}")
    assert resposta_obter.status_code == 200
    assert resposta_obter.json()["documento"] == "12345678000190"


def test_documento_duplicado_retorna_409(cliente: TestClient) -> None:
    dados = {
        "razao_social": "Fornecedor A Ltda",
        "documento": "12345678901",
        "tipo_empresa": "fornecedor",
    }
    primeira = cliente.post("/api/v1/empresas", json=dados)
    segunda = cliente.post("/api/v1/empresas", json=dados)

    assert primeira.status_code == 201
    assert segunda.status_code == 409
    assert segunda.json()["detail"] == "documento_da_empresa_ja_cadastrado"


def test_documento_invalido_retorna_422(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/api/v1/empresas",
        json={
            "razao_social": "Cliente Teste",
            "documento": "123",
            "tipo_empresa": "cliente",
        },
    )
    assert resposta.status_code == 422


def test_documento_com_12_digitos_retorna_422(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/api/v1/empresas",
        json={
            "razao_social": "Cliente Teste",
            "documento": "123331231531",
            "tipo_empresa": "cliente",
        },
    )
    assert resposta.status_code == 422


def test_tipo_empresa_invalido_retorna_422(cliente: TestClient) -> None:
    resposta = cliente.post(
        "/api/v1/empresas",
        json={
            "razao_social": "Cliente Teste",
            "documento": "12345678901",
            "tipo_empresa": "invalido",
        },
    )
    assert resposta.status_code == 422


def test_empresa_inexistente_retorna_404(cliente: TestClient) -> None:
    resposta = cliente.get("/api/v1/empresas/999")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "empresa_nao_encontrada"
