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


def cadastrar_empresa(cliente: TestClient, documento: str, tipo: str, nome: str) -> int:
    resposta = cliente.post(
        "/api/v1/empresas",
        json={
            "razao_social": nome,
            "documento": documento,
            "tipo_empresa": tipo,
        },
    )
    assert resposta.status_code == 201
    return resposta.json()["id"]


def cadastrar_catalogo(cliente: TestClient) -> tuple[int, int]:
    processo = cliente.post(
        "/api/v1/processos-fabricacao",
        json={
            "codigo": "usinagem_cnc",
            "nome": "Usinagem CNC",
        },
    )
    material = cliente.post(
        "/api/v1/materiais",
        json={
            "codigo": "aluminio_6061",
            "nome": "Alumínio 6061",
            "familia": "alumínio",
        },
    )
    assert processo.status_code == 201
    assert material.status_code == 201
    return processo.json()["id"], material.json()["id"]


def cadastrar_capacidade_fornecedor(
    cliente: TestClient,
    fornecedor_id: int,
    processo_id: int,
    material_id: int,
) -> None:
    capacidade = cliente.post(
        f"/api/v1/empresas/{fornecedor_id}/capacidades",
        json={
            "processo_id": processo_id,
            "dimensao_x_maxima_mm": "800.000",
            "dimensao_y_maxima_mm": "500.000",
            "dimensao_z_maxima_mm": "450.000",
            "tolerancia_minima_mm": "0.0200",
        },
    )
    vinculo = cliente.post(
        f"/api/v1/empresas/{fornecedor_id}/materiais",
        json={"material_id": material_id},
    )
    assert capacidade.status_code == 201
    assert vinculo.status_code == 201


def criar_solicitacao(
    cliente: TestClient,
    cliente_id: int,
    processo_id: int,
    material_id: int,
    *,
    x: str = "600.000",
    y: str = "400.000",
    z: str = "300.000",
    tolerancia: str = "0.0200",
) -> int:
    resposta = cliente.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": x,
            "dimensao_y_maxima_mm": y,
            "dimensao_z_maxima_mm": z,
            "tolerancia_requerida_mm": tolerancia,
            "quantidade": 10,
        },
    )
    assert resposta.status_code == 201
    return resposta.json()["id"]


def test_fornecedor_compativel_por_processo_material_dimensoes_e_tolerancia(
    cliente: TestClient,
) -> None:
    cliente_id = cadastrar_empresa(
        cliente,
        "98765432000110",
        "cliente",
        "Cliente Mecânico Ltda",
    )
    fornecedor_id = cadastrar_empresa(
        cliente,
        "12345678000190",
        "fornecedor",
        "Fornecedor CNC Ltda",
    )
    processo_id, material_id = cadastrar_catalogo(cliente)
    cadastrar_capacidade_fornecedor(
        cliente,
        fornecedor_id,
        processo_id,
        material_id,
    )

    solicitacao_id = criar_solicitacao(
        cliente,
        cliente_id,
        processo_id,
        material_id,
    )

    resposta = cliente.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis"
    )
    assert resposta.status_code == 200
    itens = resposta.json()
    assert len(itens) == 1
    assert itens[0]["empresa_id"] == fornecedor_id
    assert itens[0]["processo_id"] == processo_id
    assert itens[0]["material_id"] == material_id


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"x": "900.000"},
        {"y": "600.000"},
        {"z": "500.000"},
        {"tolerancia": "0.0100"},
    ],
)
def test_requisito_fora_da_capacidade_nao_encontra_fornecedor(
    cliente: TestClient,
    alteracoes: dict[str, str],
) -> None:
    cliente_id = cadastrar_empresa(
        cliente,
        "98765432000110",
        "cliente",
        "Cliente Mecânico Ltda",
    )
    fornecedor_id = cadastrar_empresa(
        cliente,
        "12345678000190",
        "fornecedor",
        "Fornecedor CNC Ltda",
    )
    processo_id, material_id = cadastrar_catalogo(cliente)
    cadastrar_capacidade_fornecedor(
        cliente,
        fornecedor_id,
        processo_id,
        material_id,
    )

    solicitacao_id = criar_solicitacao(
        cliente,
        cliente_id,
        processo_id,
        material_id,
        **alteracoes,
    )

    resposta = cliente.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis"
    )
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_material_incompativel_nao_encontra_fornecedor(cliente: TestClient) -> None:
    cliente_id = cadastrar_empresa(
        cliente,
        "98765432000110",
        "cliente",
        "Cliente Mecânico Ltda",
    )
    fornecedor_id = cadastrar_empresa(
        cliente,
        "12345678000190",
        "fornecedor",
        "Fornecedor CNC Ltda",
    )
    processo_id, material_id = cadastrar_catalogo(cliente)
    cadastrar_capacidade_fornecedor(
        cliente,
        fornecedor_id,
        processo_id,
        material_id,
    )

    outro_material = cliente.post(
        "/api/v1/materiais",
        json={"codigo": "aco_1045", "nome": "Aço 1045"},
    )
    assert outro_material.status_code == 201

    solicitacao_id = criar_solicitacao(
        cliente,
        cliente_id,
        processo_id,
        outro_material.json()["id"],
    )

    resposta = cliente.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis"
    )
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_empresa_fornecedora_nao_pode_criar_solicitacao_de_cliente(
    cliente: TestClient,
) -> None:
    fornecedor_id = cadastrar_empresa(
        cliente,
        "12345678000190",
        "fornecedor",
        "Fornecedor CNC Ltda",
    )
    processo_id, material_id = cadastrar_catalogo(cliente)

    resposta = cliente.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": fornecedor_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "100.000",
            "dimensao_y_maxima_mm": "100.000",
            "dimensao_z_maxima_mm": "100.000",
            "tolerancia_requerida_mm": "0.0500",
            "quantidade": 1,
        },
    )
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "empresa_nao_e_cliente"


def test_solicitacao_com_dimensao_zero_e_rejeitada(cliente: TestClient) -> None:
    cliente_id = cadastrar_empresa(
        cliente,
        "98765432000110",
        "cliente",
        "Cliente Mecânico Ltda",
    )
    processo_id, material_id = cadastrar_catalogo(cliente)

    resposta = cliente.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "0",
            "dimensao_y_maxima_mm": "100.000",
            "dimensao_z_maxima_mm": "100.000",
            "tolerancia_requerida_mm": "0.0500",
            "quantidade": 1,
        },
    )
    assert resposta.status_code == 422
