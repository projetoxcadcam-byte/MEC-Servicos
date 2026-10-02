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
from backend.app.api.rotas.contratacoes import roteador as contratacoes
from backend.app.api.rotas.portal_contratacoes import roteador as portal
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico

CLIENTE = "/api/v1/portal-cliente"
FORNECEDOR = "/api/v1/portal-fornecedor"


def nova_solicitacao(banco, numero, cliente=1):
    solicitacao = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,
        dimensao_x_maxima_mm=Decimal("500"), dimensao_y_maxima_mm=Decimal("300"),
        dimensao_z_maxima_mm=Decimal("250"), tolerancia_requerida_mm=Decimal("0.0200"),
        quantidade=5, observacoes="Solicitação de teste.")
    banco.add(solicitacao)
    banco.flush()
    return solicitacao


def nova_cotacao(banco, numero, solicitacao, fornecedor=2, decisor=1, status="aceita"):
    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=solicitacao, empresa_fornecedora_id=fornecedor,
        valor_total=Decimal("1250.50"), prazo_dias=15, validade_dias=10, status=status,
        observacoes="Observações da proposta.", decidida_por_empresa_id=decisor if status == "aceita" else None,
        encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None) if status == "aceita" else None)
    banco.add(cotacao)
    banco.flush()
    return cotacao


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
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
            Empresa(id=3, razao_social="Outro Fornecedor", documento="fornecedor-3", tipo_empresa="fornecedor"),
            Empresa(id=4, razao_social="Empresa Ambos", documento="ambos-4", tipo_empresa="ambos"),
            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-5", tipo_empresa="cliente"),
            ProcessoFabricacao(id=1, codigo="cnc-d25", nome="Usinagem CNC"),
            Material(id=1, codigo="al6061-d25", nome="Alumínio 6061"),
        ])
        banco.commit()
        for numero, cliente in ((1, 1), (2, 5), (3, 1), (4, 1)):
            nova_solicitacao(banco, numero, cliente)
        nova_cotacao(banco, 1, 1)
        nova_cotacao(banco, 2, 2, fornecedor=3, decisor=5)
        nova_cotacao(banco, 3, 3, fornecedor=3, status="enviada")
        nova_cotacao(banco, 4, 4, decisor=5)
        banco.commit()

    def banco_teste():
        with sessoes() as banco:
            yield banco

    app = FastAPI()
    for roteador in (arquivos, contratacoes, portal):
        app.include_router(roteador, prefix="/api/v1")
    app.dependency_overrides[obter_banco] = banco_teste
    try:
        with TestClient(app) as cliente:
            yield cliente, sessoes
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def candidatas(http, cliente=1, **pagina):
    return http.get(CLIENTE + "/cotacoes-aceitas", params={"empresa_cliente_id": cliente, **pagina})


def contratar(http, solicitacao=1, cotacao=1, cliente=1, **campos):
    return http.post(f"{CLIENTE}/solicitacoes/{solicitacao}/contratacao", json={
        "empresa_cliente_id": cliente, "cotacao_id": cotacao, "observacoes": "Termos da contratação.", **campos,
    })


def listar(http, perfil="cliente", empresa=1, **pagina):
    return http.get(f"/api/v1/portal-{perfil}/contratacoes", params={
        "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id": empresa, **pagina,
    })


def test_candidatas_so_aceitas_pelo_dono_e_com_nomes(ambiente):
    http, _ = ambiente
    pagina = candidatas(http).json()
    assert pagina["total"] == 1
    item = pagina["itens"][0]
    assert item["id"] == 1 and item["fornecedor_razao_social"] == "Fornecedor Teste"
    assert item["solicitacao"]["cliente_razao_social"] == "Cliente Teste"
    assert item["solicitacao"]["processo_nome"] == "Usinagem CNC"
    assert item["solicitacao"]["material_nome"] == "Alumínio 6061"
    assert [item["id"] for item in candidatas(http, 5).json()["itens"]] == [2]


def test_criacao_reutiliza_d8_copia_valores_e_chega_aos_dois_portais(ambiente):
    http, sessoes = ambiente
    resposta = contratar(http, valor_total="0.01", prazo_dias=1)
    assert resposta.status_code == 201
    contrato = resposta.json()
    assert contrato["valor_total"] == "1250.50" and contrato["prazo_dias"] == 15
    assert contrato["status"] == "ativa" and contrato["observacoes"] == "Termos da contratação."
    assert candidatas(http).json()["total"] == 0
    cliente = listar(http).json()["itens"][0]
    fornecedor = listar(http, "fornecedor", 2).json()["itens"][0]
    assert cliente == fornecedor
    assert cliente["cliente_razao_social"] == "Cliente Teste"
    assert cliente["fornecedor_razao_social"] == "Fornecedor Teste"
    assert cliente["solicitacao"]["status"] == "encerrada"
    with sessoes() as banco:
        assert banco.get(SolicitacaoServico, 1).status == "encerrada"
        assert banco.get(CotacaoFornecedor, 1).status == "aceita"
        assert banco.scalar(select(ContratacaoServico)).valor_total == Decimal("1250.50")


def test_criacao_repetida_nao_duplica_nem_altera_contrato(ambiente):
    http, sessoes = ambiente
    assert contratar(http).status_code == 201
    repetida = contratar(http, observacoes="Tentativa repetida.")
    assert repetida.status_code == 409 and repetida.json()["detail"] == "contratacao_ja_cadastrada"
    with sessoes() as banco:
        itens = banco.scalars(select(ContratacaoServico)).all()
        assert len(itens) == 1 and itens[0].observacoes == "Termos da contratação."


@pytest.mark.parametrize("campos,codigo", [
    ({"cliente": 5}, 403), ({"cotacao": 2}, 404),
    ({"solicitacao": 999}, 404), ({"solicitacao": 3, "cotacao": 3}, 409),
    ({"solicitacao": 4, "cotacao": 4}, 403), ({"cliente": 2}, 403),
])
def test_propostas_invalidas_e_empresa_errada_nao_criam_contratacao(ambiente, campos, codigo):
    http, sessoes = ambiente
    assert contratar(http, **campos).status_code == codigo
    with sessoes() as banco:
        assert banco.scalars(select(ContratacaoServico)).all() == []
        assert banco.get(SolicitacaoServico, 1).status == "aberta"


@pytest.mark.parametrize("situacao", ["encerrada", "cancelada"])
def test_solicitacao_fechada_nao_e_candidata_nem_pode_ser_contratada(ambiente, situacao):
    http, sessoes = ambiente
    with sessoes() as banco:
        banco.get(SolicitacaoServico, 1).status = situacao
        banco.commit()
    assert candidatas(http).json()["total"] == 0
    assert contratar(http).status_code == 409


def test_proposta_ja_aceita_permanece_contratavel_apos_validade_original(ambiente):
    http, sessoes = ambiente
    with sessoes() as banco:
        banco.get(CotacaoFornecedor, 1).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
        banco.commit()
    assert candidatas(http).json()["total"] == 1
    assert contratar(http).status_code == 201


def test_consultas_e_detalhes_limitados_as_empresas_participantes(ambiente):
    http, _ = ambiente
    contrato = contratar(http).json()["id"]
    assert contratar(http, solicitacao=2, cotacao=2, cliente=5).status_code == 201
    assert listar(http).json()["total"] == 1
    assert listar(http, "fornecedor", 2).json()["total"] == 1
    for perfil, parametro, dono, estranho in (("cliente", "empresa_cliente_id", 1, 5), ("fornecedor", "empresa_fornecedora_id", 2, 3)):
        url = f"/api/v1/portal-{perfil}/contratacoes/{contrato}"
        assert http.get(url, params={parametro: dono}).status_code == 200
        assert http.get(url, params={parametro: estranho}).status_code == 404


def test_paginacao_contratos_e_candidatas_sem_perder_contagem(ambiente):
    http, sessoes = ambiente
    with sessoes() as banco:
        for numero in (6, 7):
            nova_solicitacao(banco, numero)
            nova_cotacao(banco, numero, numero)
        banco.commit()
    pagina = candidatas(http, deslocamento=1, limite=1).json()
    assert pagina["total"] == 3 and [i["id"] for i in pagina["itens"]] == [6]
    for numero in (1, 6, 7):
        assert contratar(http, solicitacao=numero, cotacao=numero).status_code == 201
    pagina = listar(http, "fornecedor", 2, deslocamento=1, limite=1).json()
    assert pagina["total"] == 3 and len(pagina["itens"]) == 1
    assert pagina["itens"][0]["solicitacao_id"] == 6
    assert candidatas(http).json()["total"] == 0


@pytest.mark.parametrize("status", ["cancelada", "encerrada"])
def test_historico_conserva_status_e_nao_libera_nova_contratacao(ambiente, status):
    http, sessoes = ambiente
    identificador = contratar(http).json()["id"]
    with sessoes() as banco:
        item = banco.get(ContratacaoServico, identificador)
        item.status = status
        setattr(item, "cancelada_em" if status == "cancelada" else "encerrada_em", datetime.now(timezone.utc).replace(tzinfo=None))
        banco.commit()
    for perfil, empresa in (("cliente", 1), ("fornecedor", 2)):
        assert listar(http, perfil, empresa).json()["itens"][0]["status"] == status
    assert candidatas(http).json()["total"] == 0
    assert contratar(http).status_code == 409


@pytest.mark.parametrize("url,parametros,codigo", [
    (CLIENTE + "/contratacoes", {}, 422),
    (CLIENTE + "/cotacoes-aceitas", {"empresa_cliente_id": 0}, 422),
    (CLIENTE + "/contratacoes", {"empresa_cliente_id": 2}, 403),
    (FORNECEDOR + "/contratacoes", {"empresa_fornecedora_id": 1}, 403),
    (FORNECEDOR + "/contratacoes", {"empresa_fornecedora_id": 999}, 404),
    (CLIENTE + "/contratacoes", {"empresa_cliente_id": 1, "limite": 101}, 422),
    (CLIENTE + "/contratacoes", {"empresa_cliente_id": 1, "deslocamento": -1}, 422),
])
def test_consultas_exigem_empresa_valida_e_paginacao_limitada(ambiente, url, parametros, codigo):
    http, _ = ambiente
    assert http.get(url, params=parametros).status_code == codigo


def test_empresa_ambos_pode_consultar_nos_dois_perfis(ambiente):
    http, _ = ambiente
    assert listar(http, "cliente", 4).status_code == 200
    assert listar(http, "fornecedor", 4).status_code == 200
    assert candidatas(http, 4).status_code == 200


@pytest.mark.parametrize("extensao,conteudo", [("ZIP", b"PK\x03\x04conteudo-zip"), ("rar", b"Rar!\x1a\x07conteudo-rar")])
def test_arquivos_zip_rar_acessiveis_so_aos_participantes_e_desvinculo_respeitado(ambiente, extensao, conteudo):
    http, _ = ambiente
    contrato = contratar(http).json()["id"]
    enviada = http.post("/api/v1/solicitacoes-servico/1/arquivos-tecnicos", files={"file": (f"pecas.{extensao}", conteudo, "application/octet-stream")})
    assert enviada.status_code == 201
    arquivo = enviada.json()["id"]
    for perfil, parametro, dono, estranho in (("cliente", "empresa_cliente_id", 1, 5), ("fornecedor", "empresa_fornecedora_id", 2, 3)):
        url = f"/api/v1/portal-{perfil}/contratacoes/{contrato}/arquivos"
        assert [i["id"] for i in http.get(url, params={parametro: dono}).json()] == [arquivo]
        assert http.get(url, params={parametro: estranho}).status_code == 404
        download = f"{url}/{arquivo}/download"
        assert http.get(download, params={parametro: dono}).content == conteudo
        assert http.get(download, params={parametro: estranho}).status_code == 404
    assert http.delete(f"/api/v1/arquivos-tecnicos/{arquivo}").status_code == 204
    url = f"{FORNECEDOR}/contratacoes/{contrato}/arquivos"
    assert http.get(url, params={"empresa_fornecedora_id": 2}).json() == []
    assert http.get(f"{url}/{arquivo}/download", params={"empresa_fornecedora_id": 2}).status_code == 404


def test_arquivo_de_outra_solicitacao_nao_pode_ser_baixado_por_contrato_proprio(ambiente):
    http, _ = ambiente
    contrato = contratar(http).json()["id"]
    arquivo = http.post("/api/v1/solicitacoes-servico/2/arquivos-tecnicos", files={"file": ("outra.pdf", b"pdf-outro-cliente", "application/pdf")}).json()["id"]
    url = f"{FORNECEDOR}/contratacoes/{contrato}/arquivos/{arquivo}/download"
    resposta = http.get(url, params={"empresa_fornecedora_id": 2})
    assert resposta.status_code == 404 and resposta.json()["detail"] == "arquivo_tecnico_nao_encontrado"


def test_observacoes_excessivas_nao_gravam_contrato(ambiente):
    http, _ = ambiente
    assert contratar(http, observacoes="x" * 5001).status_code == 422
    assert listar(http).json()["total"] == 0
