from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos
from backend.app.api.rotas.cotacoes import roteador as cotacoes
from backend.app.api.rotas.portal_fornecedor import roteador as portal
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.compatibilidade import RepositorioCompatibilidade
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico

BASE = "/api/v1/portal-fornecedor"


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    # Aplicação sem lifespan: os testes usam somente SQLite e arquivos temporários.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def ativar_chaves_estrangeiras(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ServicoArquivoTecnico, "STORAGE_ROOT", tmp_path)
    with sessoes() as banco:
        banco.add_all([
            Empresa(id=1, razao_social="Cliente Teste", documento="cliente-1", tipo_empresa="cliente"),
            Empresa(id=2, razao_social="Fornecedor Teste", documento="fornecedor-2", tipo_empresa="fornecedor"),
            Empresa(id=3, razao_social="Concorrente Teste", documento="fornecedor-3", tipo_empresa="ambos"),
            Empresa(id=4, razao_social="Fornecedor sem capacidade", documento="fornecedor-4", tipo_empresa="fornecedor"),
            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-5", tipo_empresa="cliente"),
            ProcessoFabricacao(id=1, codigo="cnc", nome="Usinagem CNC"),
            ProcessoFabricacao(id=2, codigo="torno", nome="Torneamento"),
            Material(id=1, codigo="al6061", nome="Alumínio 6061"),
            Material(id=2, codigo="aco1045", nome="Aço 1045"),
        ])
        banco.commit()
        for empresa in (2, 3):
            banco.add(CapacidadeFornecedor(empresa_id=empresa, processo_id=1,
                dimensao_x_maxima_mm=Decimal("800"), dimensao_y_maxima_mm=Decimal("500"),
                dimensao_z_maxima_mm=Decimal("450"), tolerancia_minima_mm=Decimal("0.0200")))
            banco.add(MaterialFornecedor(empresa_id=empresa, material_id=1))
        banco.add(SolicitacaoServico(id=1, empresa_cliente_id=1, processo_id=1, material_id=1,
            dimensao_x_maxima_mm=Decimal("800"), dimensao_y_maxima_mm=Decimal("500"),
            dimensao_z_maxima_mm=Decimal("450"), tolerancia_requerida_mm=Decimal("0.0200"),
            quantidade=10, observacoes="Peça de teste."))
        banco.commit()

    def banco_teste():
        with sessoes() as banco:
            yield banco

    app = FastAPI()
    for roteador in (arquivos, cotacoes, portal):
        app.include_router(roteador, prefix="/api/v1")
    app.dependency_overrides[obter_banco] = banco_teste
    try:
        with TestClient(app) as cliente:
            yield cliente, sessoes
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def listar(cliente, recurso="oportunidades", empresa=2, **pagina):
    return cliente.get(BASE + "/" + recurso, params={"empresa_fornecedora_id": empresa, **pagina})


def enviar(cliente, empresa=2, solicitacao=1, **campos):
    return cliente.post(f"{BASE}/solicitacoes/{solicitacao}/cotacoes", json={
        "empresa_fornecedora_id": empresa, "valor_total": "1250.50", "prazo_dias": 15,
        "validade_dias": 10, "observacoes": "Proposta de teste.", **campos,
    })


def test_oportunidade_com_limites_iguais_traz_cliente_e_catalogos(ambiente):
    cliente, _ = ambiente
    resposta = listar(cliente)
    assert resposta.status_code == 200
    pagina = resposta.json()
    assert pagina["total"] == 1
    item = pagina["itens"][0]
    assert item["id"] == 1 and item["quantidade"] == 10
    assert item["cliente_razao_social"] == "Cliente Teste"
    assert item["processo_nome"] == "Usinagem CNC"
    assert item["material_nome"] == "Alumínio 6061"


@pytest.mark.parametrize("campo,valor", [
    ("dimensao_x_maxima_mm", "800.001"), ("dimensao_y_maxima_mm", "500.001"),
    ("dimensao_z_maxima_mm", "450.001"), ("tolerancia_requerida_mm", "0.0199"),
    ("processo_id", 2), ("material_id", 2),
])
def test_oportunidades_seguem_compatibilidade_e_envio_rejeita_incompativel(ambiente, campo, valor):
    cliente, sessoes = ambiente
    with sessoes() as banco:
        solicitacao = banco.get(SolicitacaoServico, 1)
        setattr(solicitacao, campo, valor if campo.endswith("_id") else Decimal(valor))
        banco.commit()
        assert all(empresa.id != 2 for empresa, _ in RepositorioCompatibilidade(banco).listar_fornecedores_compativeis(solicitacao))
    assert listar(cliente).json()["total"] == 0
    resposta = enviar(cliente)
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "fornecedor_nao_compativel_com_a_solicitacao"


@pytest.mark.parametrize("status", ["encerrada", "cancelada"])
def test_solicitacao_encerrada_sai_das_oportunidades_e_nao_recebe_proposta(ambiente, status):
    cliente, sessoes = ambiente
    with sessoes() as banco:
        banco.get(SolicitacaoServico, 1).status = status
        banco.commit()
    assert listar(cliente).json()["total"] == 0
    resposta = enviar(cliente)
    assert resposta.status_code == 409 and resposta.json()["detail"] == "solicitacao_nao_esta_aberta"


def test_envio_aparece_no_cliente_impede_duplicidade_e_preserva_dados(ambiente):
    cliente, sessoes = ambiente
    criada = enviar(cliente)
    assert criada.status_code == 201
    item = criada.json()
    assert item["valor_total"] == "1250.50" and item["status"] == "enviada"
    assert item["observacoes"] == "Proposta de teste."
    assert listar(cliente).json()["total"] == 0
    repetida = enviar(cliente)
    assert repetida.status_code == 409
    assert repetida.json()["detail"] == "cotacao_ja_cadastrada_para_este_fornecedor"
    recebidas = cliente.get("/api/v1/solicitacoes-servico/1/cotacoes").json()
    assert [cotacao["id"] for cotacao in recebidas] == [item["id"]]
    minhas = listar(cliente, "cotacoes").json()
    assert minhas["total"] == 1
    assert minhas["itens"][0]["solicitacao"]["cliente_razao_social"] == "Cliente Teste"
    with sessoes() as banco:
        assert len(banco.scalars(select(CotacaoFornecedor)).all()) == 1


def test_fornecedor_recebe_so_proprias_propostas_e_cliente_decide(ambiente):
    cliente, _ = ambiente
    a = enviar(cliente).json()
    b = enviar(cliente, empresa=3).json()
    assert [item["id"] for item in listar(cliente, "cotacoes").json()["itens"]] == [a["id"]]
    assert [item["id"] for item in listar(cliente, "cotacoes", empresa=3).json()["itens"]] == [b["id"]]
    caminho = f'/api/v1/solicitacoes-servico/1/cotacoes/{a["id"]}/aceitar'
    assert cliente.post(caminho, json={"empresa_cliente_id": 5}).status_code == 403
    aceita = cliente.post(caminho, json={"empresa_cliente_id": 1})
    assert aceita.status_code == 200 and aceita.json()["status"] == "aceita"
    assert listar(cliente, "cotacoes", empresa=3).json()["itens"][0]["status"] == "recusada"
    assert listar(cliente, empresa=3).json()["total"] == 0


def test_aceite_por_outro_fornecedor_bloqueia_oportunidade_e_novo_envio(ambiente):
    cliente, _ = ambiente
    cotacao = enviar(cliente, empresa=3).json()
    assert cliente.post(f'/api/v1/solicitacoes-servico/1/cotacoes/{cotacao["id"]}/aceitar', json={"empresa_cliente_id": 1}).status_code == 200
    assert listar(cliente).json()["total"] == 0
    resposta = enviar(cliente)
    assert resposta.status_code == 409 and resposta.json()["detail"] == "solicitacao_ja_possui_cotacao_aceita"


def test_validade_utc_e_historico_sem_reenvio(ambiente):
    cliente, sessoes = ambiente
    cotacao = enviar(cliente, validade_dias=1).json()
    with sessoes() as banco:
        banco.get(CotacaoFornecedor, cotacao["id"]).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        banco.commit()
    item = listar(cliente, "cotacoes").json()["itens"][0]
    assert item["status"] == "expirada" and item["encerrada_em"] is not None
    assert item["decidida_por_empresa_id"] is None
    assert listar(cliente).json()["total"] == 0
    assert enviar(cliente).status_code == 409


@pytest.mark.parametrize("empresa,codigo", [(1, 409), (999, 404)])
def test_empresa_cliente_ou_inexistente_nao_opera_portal(ambiente, empresa, codigo):
    cliente, _ = ambiente
    assert listar(cliente, empresa=empresa).status_code == codigo
    assert listar(cliente, "cotacoes", empresa=empresa).status_code == codigo
    assert enviar(cliente, empresa=empresa).status_code == codigo


def test_paginacao_nao_repete_itens_e_valida_limites(ambiente):
    cliente, sessoes = ambiente
    with sessoes() as banco:
        original = banco.get(SolicitacaoServico, 1)
        dados = {campo: getattr(original, campo) for campo in (
            "empresa_cliente_id", "processo_id", "material_id", "dimensao_x_maxima_mm",
            "dimensao_y_maxima_mm", "dimensao_z_maxima_mm", "tolerancia_requerida_mm", "quantidade",
        )}
        banco.add_all([SolicitacaoServico(**dados), SolicitacaoServico(**dados)])
        banco.commit()
    paginas = [listar(cliente, deslocamento=n, limite=1).json() for n in range(3)]
    assert all(pagina["total"] == 3 for pagina in paginas)
    assert [p["itens"][0]["id"] for p in paginas] == [3, 2, 1]
    assert listar(cliente, deslocamento=-1).status_code == 422
    assert listar(cliente, limite=101).status_code == 422
    assert listar(cliente, empresa=0).status_code == 422


@pytest.mark.parametrize("extensao,conteudo", [("ZIP", b"PK\x03\x04arquivo zip"), ("rar", b"Rar!\x1a\x07\x00arquivo rar")])
def test_arquivos_zip_rar_acesso_download_e_desvinculo(ambiente, extensao, conteudo):
    cliente, sessoes = ambiente
    upload = cliente.post("/api/v1/solicitacoes-servico/1/arquivos-tecnicos", files={"file": ("pecas." + extensao, conteudo, "application/octet-stream")})
    assert upload.status_code == 201
    arquivo = upload.json()
    caminho = BASE + "/solicitacoes/1/arquivos"
    assert cliente.get(caminho, params={"empresa_fornecedora_id": 4}).status_code == 403
    itens = cliente.get(caminho, params={"empresa_fornecedora_id": 2}).json()
    assert itens[0]["id"] == arquivo["id"]
    download = BASE + f'/arquivos/{arquivo["id"]}/download'
    assert cliente.get(download, params={"empresa_fornecedora_id": 4}).status_code == 403
    baixado = cliente.get(download, params={"empresa_fornecedora_id": 2})
    assert baixado.status_code == 200 and baixado.content == conteudo
    assert "attachment" in baixado.headers["content-disposition"]
    assert enviar(cliente).status_code == 201
    with sessoes() as banco:
        banco.get(CapacidadeFornecedor, 1).dimensao_x_maxima_mm = Decimal("1")
        banco.commit()
    # Histórico da própria proposta continua acessível após mudança de capacidade.
    assert cliente.get(download, params={"empresa_fornecedora_id": 2}).status_code == 200
    assert cliente.delete(f'/api/v1/arquivos-tecnicos/{arquivo["id"]}').status_code == 204
    assert cliente.get(caminho, params={"empresa_fornecedora_id": 2}).json() == []
    assert cliente.get(download, params={"empresa_fornecedora_id": 2}).status_code == 404


@pytest.mark.parametrize("campos", [
    {"valor_total": "0"}, {"valor_total": "10.123"}, {"prazo_dias": 0},
    {"validade_dias": 3651}, {"observacoes": "x" * 5001},
])
def test_proposta_invalida_nao_grava(ambiente, campos):
    cliente, _ = ambiente
    assert enviar(cliente, **campos).status_code == 422
    assert listar(cliente, "cotacoes").json()["total"] == 0
