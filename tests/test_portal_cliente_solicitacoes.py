
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.principal import app


@pytest.fixture()
def ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:
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

    try:
        with TestClient(app) as test_client:
            yield test_client, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_base(SessaoTeste: sessionmaker) -> tuple[int, int, int, int]:
    banco = SessaoTeste()

    cliente = Empresa(
        razao_social="Cliente Portal D18",
        documento="D18-CLIENTE-001",
        tipo_empresa="cliente",
    )
    outro_cliente = Empresa(
        razao_social="Outro Cliente Portal D18",
        documento="D18-CLIENTE-002",
        tipo_empresa="cliente",
    )
    processo = ProcessoFabricacao(
        codigo="usinagem_cnc_d18",
        nome="Usinagem CNC D18",
        descricao="Processo de teste do portal D18.",
    )
    material = Material(
        codigo="aluminio_6061_d18",
        nome="Aluminio 6061 D18",
        familia="Aluminio",
        especificacao="Liga de teste D18.",
    )

    banco.add_all([cliente, outro_cliente, processo, material])
    banco.commit()

    ids = (cliente.id, outro_cliente.id, processo.id, material.id)
    banco.close()
    return ids


def test_listar_solicitacoes_por_cliente(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, outro_cliente_id, processo_id, material_id = preparar_base(
        SessaoTeste
    )

    primeira = cliente_http.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "100.000",
            "dimensao_y_maxima_mm": "80.000",
            "dimensao_z_maxima_mm": "50.000",
            "tolerancia_requerida_mm": "0.0200",
            "quantidade": 10,
            "observacoes": "Solicitacao D18 do cliente principal.",
        },
    )
    assert primeira.status_code == 201

    segunda = cliente_http.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": outro_cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "50.000",
            "dimensao_y_maxima_mm": "50.000",
            "dimensao_z_maxima_mm": "20.000",
            "tolerancia_requerida_mm": "0.0500",
            "quantidade": 2,
        },
    )
    assert segunda.status_code == 201

    resposta = cliente_http.get(
        "/api/v1/solicitacoes-servico",
        params={"empresa_cliente_id": cliente_id},
    )

    assert resposta.status_code == 200
    itens = resposta.json()

    assert len(itens) == 1
    assert itens[0]["empresa_cliente_id"] == cliente_id
    assert itens[0]["quantidade"] == 10
    assert itens[0]["status"] == "aberta"


def test_listar_solicitacoes_rejeita_empresa_inexistente(ambiente):
    cliente_http, _ = ambiente

    resposta = cliente_http.get(
        "/api/v1/solicitacoes-servico",
        params={"empresa_cliente_id": 999999},
    )

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "empresa_cliente_nao_encontrada"


def test_listar_solicitacoes_rejeita_fornecedor(ambiente):
    cliente_http, SessaoTeste = ambiente

    banco = SessaoTeste()
    fornecedor = Empresa(
        razao_social="Fornecedor Portal D18",
        documento="D18-FORNECEDOR-001",
        tipo_empresa="fornecedor",
    )
    banco.add(fornecedor)
    banco.commit()
    fornecedor_id = fornecedor.id
    banco.close()

    resposta = cliente_http.get(
        "/api/v1/solicitacoes-servico",
        params={"empresa_cliente_id": fornecedor_id},
    )

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "empresa_nao_e_cliente"
