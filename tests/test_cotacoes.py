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


def cadastrar_empresa(
    cliente: TestClient,
    documento: str,
    tipo: str,
    nome: str,
) -> int:
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


def adicionar_fornecedor_compativel(
    cliente: TestClient,
    processo_id: int,
    material_id: int,
    documento: str,
    nome: str,
) -> int:
    fornecedor_id = cadastrar_empresa(
        cliente,
        documento,
        "fornecedor",
        nome,
    )
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
    return fornecedor_id


def criar_cotacao(
    cliente: TestClient,
    solicitacao_id: int,
    fornecedor_id: int,
    valor: str = "12500.00",
) -> dict:
    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "valor_total": valor,
            "prazo_dias": 15,
            "validade_dias": 10,
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def preparar_cenario(cliente: TestClient) -> tuple[int, int, int, int, int]:
    cliente_id = cadastrar_empresa(
        cliente,
        "98765432000110",
        "cliente",
        "Cliente Cotação Ltda",
    )
    fornecedor_id = cadastrar_empresa(
        cliente,
        "12345678000190",
        "fornecedor",
        "Fornecedor Cotação Ltda",
    )

    processo = cliente.post(
        "/api/v1/processos-fabricacao",
        json={"codigo": "usinagem_cnc", "nome": "Usinagem CNC"},
    )
    material = cliente.post(
        "/api/v1/materiais",
        json={
            "codigo": "aluminio_6061",
            "nome": "Alumínio 6061",
            "familia": "Alumínio",
        },
    )
    assert processo.status_code == 201
    assert material.status_code == 201

    processo_id = processo.json()["id"]
    material_id = material.json()["id"]

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

    solicitacao = cliente.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "600.000",
            "dimensao_y_maxima_mm": "400.000",
            "dimensao_z_maxima_mm": "300.000",
            "tolerancia_requerida_mm": "0.0200",
            "quantidade": 10,
            "observacoes": "Solicitação de teste D7.",
        },
    )
    assert solicitacao.status_code == 201

    return (
        solicitacao.json()["id"],
        cliente_id,
        fornecedor_id,
        processo_id,
        material_id,
    )


def test_cria_cotacao_de_fornecedor_compativel(cliente: TestClient) -> None:
    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    dados = criar_cotacao(cliente, solicitacao_id, fornecedor_id)
    assert dados["status"] == "enviada"
    assert dados["encerrada_em"] is None
    assert dados["decidida_por_empresa_id"] is None


def test_lista_cotacoes_da_solicitacao(cliente: TestClient) -> None:
    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    resposta = cliente.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes"
    )

    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_fornecedor_incompativel_nao_pode_cotar(cliente: TestClient) -> None:
    solicitacao_id, _cliente_id, _fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    outro_fornecedor = cadastrar_empresa(
        cliente,
        "11222333000144",
        "fornecedor",
        "Fornecedor Incompatível Ltda",
    )

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",
        json={
            "empresa_fornecedora_id": outro_fornecedor,
            "valor_total": "10000.00",
            "prazo_dias": 10,
            "validade_dias": 10,
        },
    )

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == (
        "fornecedor_nao_compativel_com_a_solicitacao"
    )


def test_empresa_cliente_nao_pode_enviar_cotacao(cliente: TestClient) -> None:
    solicitacao_id, _cliente_id, _fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    cliente_extra = cadastrar_empresa(
        cliente,
        "55666777000188",
        "cliente",
        "Cliente Extra Ltda",
    )

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",
        json={
            "empresa_fornecedora_id": cliente_extra,
            "valor_total": "10000.00",
            "prazo_dias": 10,
            "validade_dias": 10,
        },
    )
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "empresa_nao_e_fornecedora"


def test_nao_permite_duas_cotacoes_do_mesmo_fornecedor(
    cliente: TestClient,
) -> None:
    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    primeira = criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    segunda = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "valor_total": "11000.00",
            "prazo_dias": 12,
            "validade_dias": 10,
        },
    )

    assert primeira["status"] == "enviada"
    assert segunda.status_code == 409
    assert segunda.json()["detail"] == (
        "cotacao_ja_cadastrada_para_este_fornecedor"
    )


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("valor_total", "0"),
        ("prazo_dias", 0),
        ("validade_dias", 0),
    ],
)
def test_dados_comerciais_invalidos_sao_rejeitados(
    cliente: TestClient,
    campo: str,
    valor: object,
) -> None:
    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    dados = {
        "empresa_fornecedora_id": fornecedor_id,
        "valor_total": "10000.00",
        "prazo_dias": 10,
        "validade_dias": 10,
    }
    dados[campo] = valor

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",
        json=dados,
    )
    assert resposta.status_code == 422


def test_solicitacao_inexistente_nao_aceita_cotacao(cliente: TestClient) -> None:
    fornecedor_id = cadastrar_empresa(
        cliente,
        "12345678000190",
        "fornecedor",
        "Fornecedor Cotação Ltda",
    )
    resposta = cliente.post(
        "/api/v1/solicitacoes-servico/999/cotacoes",
        json={
            "empresa_fornecedora_id": fornecedor_id,
            "valor_total": "10000.00",
            "prazo_dias": 10,
            "validade_dias": 10,
        },
    )
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "solicitacao_nao_encontrada"


def test_cliente_pode_aceitar_cotacao(cliente: TestClient) -> None:
    solicitacao_id, cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao['id']}/aceitar",
        json={"empresa_cliente_id": cliente_id},
    )

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["status"] == "aceita"
    assert dados["decidida_por_empresa_id"] == cliente_id
    assert dados["encerrada_em"] is not None


def test_aceite_recusa_automaticamente_as_demais_cotacoes(
    cliente: TestClient,
) -> None:
    solicitacao_id, cliente_id, fornecedor_id, processo_id, material_id = (
        preparar_cenario(cliente)
    )
    outro_fornecedor = adicionar_fornecedor_compativel(
        cliente,
        processo_id,
        material_id,
        "22333444000155",
        "Segundo Fornecedor Ltda",
    )

    primeira = criar_cotacao(
        cliente,
        solicitacao_id,
        fornecedor_id,
        "12000.00",
    )
    segunda = criar_cotacao(
        cliente,
        solicitacao_id,
        outro_fornecedor,
        "13000.00",
    )

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{primeira['id']}/aceitar",
        json={"empresa_cliente_id": cliente_id},
    )
    assert resposta.status_code == 200

    consulta = cliente.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes"
    )
    assert consulta.status_code == 200

    por_id = {item["id"]: item for item in consulta.json()}
    assert por_id[primeira["id"]]["status"] == "aceita"
    assert por_id[segunda["id"]]["status"] == "recusada"
    assert por_id[segunda["id"]]["decidida_por_empresa_id"] == cliente_id


def test_cliente_pode_recusar_cotacao(cliente: TestClient) -> None:
    solicitacao_id, cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao['id']}/recusar",
        json={"empresa_cliente_id": cliente_id},
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "recusada"
    assert resposta.json()["decidida_por_empresa_id"] == cliente_id


def test_empresa_que_nao_e_cliente_nao_pode_decidir(
    cliente: TestClient,
) -> None:
    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    outra_empresa = cadastrar_empresa(
        cliente,
        "66777888000199",
        "cliente",
        "Outro Cliente Ltda",
    )

    resposta = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao['id']}/aceitar",
        json={"empresa_cliente_id": outra_empresa},
    )

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == (
        "empresa_nao_e_cliente_da_solicitacao"
    )


def test_nao_pode_criar_nova_cotacao_depois_de_aceite(
    cliente: TestClient,
) -> None:
    solicitacao_id, cliente_id, fornecedor_id, processo_id, material_id = (
        preparar_cenario(cliente)
    )
    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    outro_fornecedor = adicionar_fornecedor_compativel(
        cliente,
        processo_id,
        material_id,
        "77888999000100",
        "Terceiro Fornecedor Ltda",
    )

    aceite = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao['id']}/aceitar",
        json={"empresa_cliente_id": cliente_id},
    )
    assert aceite.status_code == 200

    nova = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",
        json={
            "empresa_fornecedora_id": outro_fornecedor,
            "valor_total": "14000.00",
            "prazo_dias": 15,
            "validade_dias": 10,
        },
    )
    assert nova.status_code == 409
    assert nova.json()["detail"] == "solicitacao_ja_possui_cotacao_aceita"


def test_cotacao_decidida_nao_pode_ser_aceita_novamente(
    cliente: TestClient,
) -> None:
    solicitacao_id, cliente_id, fornecedor_id, _processo_id, _material_id = (
        preparar_cenario(cliente)
    )
    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)

    primeira = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao['id']}/recusar",
        json={"empresa_cliente_id": cliente_id},
    )
    segunda = cliente.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao['id']}/aceitar",
        json={"empresa_cliente_id": cliente_id},
    )

    assert primeira.status_code == 200
    assert segunda.status_code == 409
    assert segunda.json()["detail"] == "cotacao_nao_esta_pendente"
