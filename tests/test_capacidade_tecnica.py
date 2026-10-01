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
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessaoTeste = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try: yield banco
        finally: banco.close()
    app.dependency_overrides[obter_banco] = substituir_banco
    with TestClient(app) as test_client: yield test_client
    app.dependency_overrides.clear(); Base.metadata.drop_all(bind=engine); engine.dispose()

def cadastrar_fornecedor(cliente: TestClient) -> None:
    r = cliente.post("/api/v1/empresas", json={"razao_social":"Fornecedor Técnico Ltda","documento":"12345678000190","tipo_empresa":"fornecedor"})
    assert r.status_code == 201

def cadastrar_cliente(cliente: TestClient) -> None:
    r = cliente.post("/api/v1/empresas", json={"razao_social":"Cliente Técnico Ltda","documento":"98765432000110","tipo_empresa":"cliente"})
    assert r.status_code == 201

def cadastrar_catalogo(cliente: TestClient) -> tuple[int,int]:
    p = cliente.post("/api/v1/processos-fabricacao", json={"codigo":"usinagem_cnc","nome":"Usinagem CNC","descricao":"Usinagem CNC para peças prismáticas."})
    m = cliente.post("/api/v1/materiais", json={"codigo":"aluminio_6061","nome":"Alumínio 6061","familia":"alumínio","especificacao":"Liga de alumínio 6061."})
    assert p.status_code == 201 and m.status_code == 201
    return p.json()["id"], m.json()["id"]

def test_capacidade_maquina_e_material_do_fornecedor(cliente: TestClient) -> None:
    cadastrar_fornecedor(cliente); processo_id, material_id = cadastrar_catalogo(cliente)
    c = cliente.post("/api/v1/empresas/1/capacidades", json={"processo_id":processo_id,"dimensao_x_maxima_mm":"800.000","dimensao_y_maxima_mm":"500.000","dimensao_z_maxima_mm":"450.000","tolerancia_minima_mm":"0.0200"})
    assert c.status_code == 201 and c.json()["tolerancia_minima_mm"] == "0.0200"
    q = cliente.post("/api/v1/empresas/1/maquinas", json={"processo_id":processo_id,"nome":"Centro CNC 01","fabricante":"Fabricante Teste","modelo":"CT-800","dimensao_x_maxima_mm":"800.000","dimensao_y_maxima_mm":"500.000","dimensao_z_maxima_mm":"450.000","tolerancia_minima_mm":"0.0100"})
    assert q.status_code == 201
    v = cliente.post("/api/v1/empresas/1/materiais", json={"material_id":material_id,"observacoes":"Material aceito."})
    assert v.status_code == 201
    assert cliente.get("/api/v1/empresas/1/capacidades").status_code == 200
    assert cliente.get("/api/v1/empresas/1/maquinas").status_code == 200
    assert cliente.get("/api/v1/empresas/1/materiais").status_code == 200

def test_empresa_cliente_nao_pode_declarar_capacidade_de_fornecedor(cliente: TestClient) -> None:
    cadastrar_cliente(cliente); processo_id, _ = cadastrar_catalogo(cliente)
    r = cliente.post("/api/v1/empresas/1/capacidades", json={"processo_id":processo_id,"dimensao_x_maxima_mm":"100","dimensao_y_maxima_mm":"100","dimensao_z_maxima_mm":"100","tolerancia_minima_mm":"0.0500"})
    assert r.status_code == 409 and r.json()["detail"] == "empresa_nao_e_fornecedora"

def test_dimensoes_e_tolerancia_precisam_ser_positivas(cliente: TestClient) -> None:
    cadastrar_fornecedor(cliente); processo_id, _ = cadastrar_catalogo(cliente)
    r = cliente.post("/api/v1/empresas/1/capacidades", json={"processo_id":processo_id,"dimensao_x_maxima_mm":"0","dimensao_y_maxima_mm":"100","dimensao_z_maxima_mm":"100","tolerancia_minima_mm":"0.0500"})
    assert r.status_code == 422

def test_duplicidade_de_processo_e_material_e_rejeitada(cliente: TestClient) -> None:
    cadastrar_fornecedor(cliente)
    assert cliente.post("/api/v1/processos-fabricacao", json={"codigo":"torno_cnc","nome":"Torno CNC"}).status_code == 201
    assert cliente.post("/api/v1/processos-fabricacao", json={"codigo":"torno_cnc","nome":"Torno CNC 2"}).status_code == 409
    assert cliente.post("/api/v1/materiais", json={"codigo":"aco_1045","nome":"Aço 1045"}).status_code == 201
    assert cliente.post("/api/v1/materiais", json={"codigo":"aco_1045","nome":"Aço 1045 2"}).status_code == 409

def test_capacidade_nao_pode_ser_repetida_para_o_mesmo_processo(cliente: TestClient) -> None:
    cadastrar_fornecedor(cliente); processo_id, _ = cadastrar_catalogo(cliente)
    dados={"processo_id":processo_id,"dimensao_x_maxima_mm":"300","dimensao_y_maxima_mm":"300","dimensao_z_maxima_mm":"300","tolerancia_minima_mm":"0.0500"}
    assert cliente.post("/api/v1/empresas/1/capacidades", json=dados).status_code == 201
    assert cliente.post("/api/v1/empresas/1/capacidades", json=dados).status_code == 409

def test_material_fornecedor_nao_pode_ser_vinculado_duas_vezes(cliente: TestClient) -> None:
    cadastrar_fornecedor(cliente); _, material_id = cadastrar_catalogo(cliente); dados={"material_id":material_id}
    assert cliente.post("/api/v1/empresas/1/materiais", json=dados).status_code == 201
    assert cliente.post("/api/v1/empresas/1/materiais", json=dados).status_code == 409
