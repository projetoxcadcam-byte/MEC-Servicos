from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos
from backend.app.api.rotas.ordens_servico import roteador as original
from backend.app.api.rotas.portal_ordens_servico import roteador as portal
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.portal_ordens_servico import ServicoPortalOrdens

CLIENTE = "/api/v1/portal-cliente"
FORNECEDOR = "/api/v1/portal-fornecedor"


def novo_contrato(banco, numero, cliente=1, fornecedor=2, situacao="ativa"):
    pedido = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,
        dimensao_x_maxima_mm=500, dimensao_y_maxima_mm=300, dimensao_z_maxima_mm=250,
        tolerancia_requerida_mm=Decimal("0.0200"), quantidade=5, status="encerrada", observacoes="Pedido D26.")
    banco.add(pedido)
    banco.flush()
    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=numero, empresa_fornecedora_id=fornecedor,
        valor_total=Decimal("1250.50"), prazo_dias=15, validade_dias=10, status="aceita",
        decidida_por_empresa_id=cliente, encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None))
    banco.add(cotacao)
    banco.flush()
    contrato = ContratacaoServico(id=numero, solicitacao_id=numero, cotacao_id=numero,
        empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, valor_total=Decimal("1250.50"),
        prazo_dias=15, status=situacao, observacoes="Termos da contratação D26.")
    banco.add(contrato)
    banco.flush()
    return contrato


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def chaves(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ServicoArquivoTecnico, "STORAGE_ROOT", tmp_path)
    with sessoes() as banco:
        banco.add_all([
            Empresa(id=1, razao_social="Cliente D26", documento="cliente-d26-1", tipo_empresa="cliente"),
            Empresa(id=2, razao_social="Fornecedor D26", documento="fornecedor-d26-2", tipo_empresa="fornecedor"),
            Empresa(id=3, razao_social="Outro Fornecedor", documento="fornecedor-d26-3", tipo_empresa="fornecedor"),
            Empresa(id=4, razao_social="Empresa Ambos", documento="ambos-d26-4", tipo_empresa="ambos"),
            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-d26-5", tipo_empresa="cliente"),
            ProcessoFabricacao(id=1, codigo="cnc-d26", nome="Usinagem CNC"),
            Material(id=1, codigo="al6061-d26", nome="Alumínio 6061"),
        ])
        banco.commit()
        novo_contrato(banco, 1)
        novo_contrato(banco, 2, cliente=5, fornecedor=3)
        novo_contrato(banco, 3, situacao="cancelada")
        novo_contrato(banco, 4, situacao="encerrada")
        novo_contrato(banco, 5)
        banco.commit()

    def banco_teste():
        with sessoes() as banco:
            yield banco

    app = FastAPI()
    for roteador in (arquivos, original, portal):
        app.include_router(roteador, prefix="/api/v1")
    app.dependency_overrides[obter_banco] = banco_teste
    try:
        with TestClient(app) as http:
            yield http, sessoes
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def gerar(http, contrato=1, cliente=1, **extra):
    return http.post(f"{CLIENTE}/contratacoes/{contrato}/ordem-servico", json={"empresa_cliente_id": cliente, **extra})


def listar(http, perfil="cliente", empresa=1, **extra):
    return http.get(f"/api/v1/portal-{perfil}/ordens-servico", params={
        "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id": empresa, **extra,
    })


def candidatas(http, cliente=1, **extra):
    return http.get(CLIENTE + "/contratacoes-para-ordem", params={"empresa_cliente_id": cliente, **extra})


def agir(http, ordem, acao="iniciar", fornecedor=2):
    return http.post(f"{FORNECEDOR}/ordens-servico/{ordem}/{acao}", json={"empresa_fornecedora_id": fornecedor})


def test_candidatas_ativas_da_empresa_com_nomes_e_paginacao(ambiente):
    http, _ = ambiente
    pagina = candidatas(http, limite=1).json()
    assert pagina["total"] == 2 and pagina["itens"][0]["id"] == 5
    item = candidatas(http, deslocamento=1, limite=1).json()["itens"][0]
    assert item["id"] == 1 and item["fornecedor_razao_social"] == "Fornecedor D26"
    assert item["solicitacao"]["processo_nome"] == "Usinagem CNC"
    assert [item["id"] for item in candidatas(http, 5).json()["itens"]] == [2]


def test_gerar_copia_d9_e_e_visivel_so_aos_donos(ambiente):
    http, sessoes = ambiente
    resposta = gerar(http, valor_total="0.01", prazo_dias=1, quantidade=99, empresa_fornecedora_id=3)
    assert resposta.status_code == 201
    ordem = resposta.json()
    assert ordem["status"] == "aberta" and ordem["valor_total"] == "1250.50"
    assert ordem["prazo_dias"] == 15 and ordem["quantidade"] == 5 and ordem["empresa_fornecedora_id"] == 2
    assert ordem["observacoes"] == "Termos da contratação D26."
    cliente = listar(http).json()["itens"][0]
    fornecedor = listar(http, "fornecedor", 2).json()["itens"][0]
    assert cliente == fornecedor and cliente["cliente_razao_social"] == "Cliente D26"
    assert cliente["fornecedor_razao_social"] == "Fornecedor D26"
    assert cliente["contratacao_status"] == "ativa" and cliente["processo_nome"] == "Usinagem CNC"
    assert listar(http, "cliente", 5).json()["total"] == 0
    assert listar(http, "fornecedor", 3).json()["total"] == 0
    assert [item["id"] for item in candidatas(http).json()["itens"]] == [5]
    with sessoes() as banco:
        assert banco.get(ContratacaoServico, 1).status == "ativa"
        assert banco.get(SolicitacaoServico, 1).status == "encerrada"


@pytest.mark.parametrize("situacao", ["aberta", "em_execucao", "concluida", "cancelada"])
def test_ordem_existente_em_qualquer_status_impede_nova_ordem(ambiente, situacao):
    http, sessoes = ambiente
    ordem = gerar(http).json()
    with sessoes() as banco:
        banco.get(OrdemServico, ordem["id"]).status = situacao
        banco.commit()
    assert [item["id"] for item in candidatas(http).json()["itens"]] == [5]
    repetida = gerar(http)
    assert repetida.status_code == 409
    assert repetida.json()["detail"] == "ordem_servico_ja_cadastrada_para_esta_contratacao"
    with sessoes() as banco:
        assert len(banco.scalars(select(OrdemServico)).all()) == 1


@pytest.mark.parametrize("contrato,cliente,codigo", [(2,1,403),(1,2,403),(999,1,404),(3,1,409),(4,1,409)])
def test_criacao_com_empresa_ou_contrato_invalido_nao_altera_banco(ambiente, contrato, cliente, codigo):
    http, sessoes = ambiente
    assert gerar(http, contrato, cliente).status_code == codigo
    with sessoes() as banco:
        assert banco.scalars(select(OrdemServico)).all() == []


@pytest.mark.parametrize("perfil,empresa,codigo", [("cliente",999,404),("fornecedor",999,404),("cliente",2,403),("fornecedor",1,403)])
def test_consulta_exige_empresa_existente_do_perfil(ambiente, perfil, empresa, codigo):
    http, _ = ambiente
    assert listar(http, perfil, empresa).status_code == codigo


@pytest.mark.parametrize("parametros", [{}, {"empresa_cliente_id":0}, {"empresa_cliente_id":1,"limite":101},
                                      {"empresa_cliente_id":1,"deslocamento":-1}])
def test_consulta_valida_parametros(ambiente, parametros):
    http, _ = ambiente
    assert http.get(CLIENTE + "/ordens-servico", params=parametros).status_code == 422


def test_detalhe_e_paginacao_nao_expoem_ordem_de_outra_empresa(ambiente):
    http, _ = ambiente
    primeira = gerar(http).json()["id"]
    segunda = gerar(http, 5).json()["id"]
    assert listar(http, limite=1).json()["itens"][0]["id"] == segunda
    assert listar(http, deslocamento=1, limite=1).json()["itens"][0]["id"] == primeira
    for perfil, empresa in (("cliente",5),("fornecedor",3)):
        param = "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id"
        assert http.get(f"/api/v1/portal-{perfil}/ordens-servico/{primeira}", params={param:empresa}).status_code == 404


def test_fornecedor_inicia_conclui_e_cliente_acompanha_datas_sem_alterar_termos(ambiente):
    http, sessoes = ambiente
    ordem = gerar(http).json()
    iniciada = agir(http, ordem["id"])
    assert iniciada.status_code == 200 and iniciada.json()["status"] == "em_execucao"
    inicio = iniciada.json()["iniciada_em"]
    concluida = agir(http, ordem["id"], "concluir")
    assert concluida.status_code == 200 and concluida.json()["status"] == "concluida"
    assert concluida.json()["iniciada_em"] == inicio and concluida.json()["concluida_em"] is not None
    assert concluida.json()["observacoes"] == ordem["observacoes"]
    assert listar(http).json()["itens"][0]["status"] == "concluida"
    with sessoes() as banco:
        assert banco.get(ContratacaoServico, 1).status == "ativa"
        assert banco.get(CotacaoFornecedor, 1).status == "aceita"


@pytest.mark.parametrize("fornecedor,codigo", [(3,404),(1,403),(999,404)])
def test_acao_rejeita_fornecedor_errado(ambiente, fornecedor, codigo):
    http, sessoes = ambiente
    ordem = gerar(http).json()["id"]
    assert agir(http, ordem, fornecedor=fornecedor).status_code == codigo
    with sessoes() as banco:
        item = banco.get(OrdemServico, ordem)
        assert item.status == "aberta" and item.iniciada_em is None


def test_acao_fornecedor_nao_aceita_identidade_de_cliente_no_corpo(ambiente):
    http, _ = ambiente
    ordem = gerar(http).json()["id"]
    url = f"{FORNECEDOR}/ordens-servico/{ordem}/iniciar"
    assert http.post(url, json={"empresa_cliente_id":1}).status_code == 422
    assert http.post(url, json={"empresa_fornecedora_id":2,"empresa_cliente_id":1}).status_code == 422


@pytest.mark.parametrize("situacao,acao", [("aberta","concluir"),("em_execucao","iniciar"),
                                         ("concluida","iniciar"),("concluida","concluir"),("cancelada","iniciar")])
def test_transicao_invalida_nao_muda_estado_ou_datas(ambiente, situacao, acao):
    http, sessoes = ambiente
    ordem = gerar(http).json()["id"]
    with sessoes() as banco:
        banco.get(OrdemServico, ordem).status = situacao
        banco.commit()
    assert agir(http, ordem, acao).status_code == 409
    with sessoes() as banco:
        item = banco.get(OrdemServico, ordem)
        assert item.status == situacao and item.iniciada_em is None and item.concluida_em is None


def test_repetir_acoes_nao_sobrescreve_datas(ambiente):
    http, _ = ambiente
    ordem = gerar(http).json()["id"]
    inicio = agir(http, ordem).json()["iniciada_em"]
    assert agir(http, ordem).status_code == 409
    fim = agir(http, ordem, "concluir").json()["concluida_em"]
    assert agir(http, ordem, "concluir").status_code == 409
    atual = listar(http).json()["itens"][0]
    assert atual["iniciada_em"] == inicio and atual["concluida_em"] == fim


@pytest.mark.parametrize("situacao", ["cancelada","encerrada"])
def test_contrato_inativo_mantem_historico_mas_bloqueia_execucao(ambiente, situacao):
    http, sessoes = ambiente
    ordem = gerar(http).json()["id"]
    with sessoes() as banco:
        banco.get(ContratacaoServico, 1).status = situacao
        banco.commit()
    assert agir(http, ordem).status_code == 409
    assert listar(http, "fornecedor", 2).json()["itens"][0]["contratacao_status"] == situacao


def test_alteracao_concorrente_entre_leitura_e_update_nao_e_sobrescrita(ambiente, monkeypatch):
    http, sessoes = ambiente
    ordem = gerar(http).json()["id"]
    obter = ServicoPortalOrdens.obter
    executou = False

    def obter_e_alterar(self, *args):
        nonlocal executou
        leitura = obter(self, *args)
        if not executou:
            executou = True
            with sessoes() as banco:
                banco.execute(update(OrdemServico).where(OrdemServico.id == ordem).values(status="cancelada"))
                banco.commit()
        return leitura

    monkeypatch.setattr(ServicoPortalOrdens, "obter", obter_e_alterar)
    resposta = agir(http, ordem)
    assert resposta.status_code == 409 and resposta.json()["detail"] == "ordem_servico_alterada_atualize"
    with sessoes() as banco:
        assert banco.get(OrdemServico, ordem).status == "cancelada"


def test_empresa_ambos_pode_gerar_e_operar_nos_papeis_corretos(ambiente):
    http, sessoes = ambiente
    with sessoes() as banco:
        novo_contrato(banco, 6, cliente=4, fornecedor=4)
        banco.commit()
    ordem = gerar(http, 6, 4).json()["id"]
    assert listar(http, "cliente", 4).json()["total"] == 1
    assert listar(http, "fornecedor", 4).json()["total"] == 1
    assert agir(http, ordem, fornecedor=4).status_code == 200


def test_snapshot_da_ordem_preserva_processo_material_e_quantidade(ambiente):
    http, sessoes = ambiente
    gerar(http)
    with sessoes() as banco:
        banco.add_all([ProcessoFabricacao(id=2,codigo="outro-d26",nome="Outro Processo"),
                       Material(id=2,codigo="outro-mat-d26",nome="Outro Material")])
        banco.flush()
        pedido = banco.get(SolicitacaoServico,1)
        pedido.processo_id = 2; pedido.material_id = 2; pedido.quantidade = 99
        banco.commit()
    ordem = listar(http).json()["itens"][0]
    assert ordem["processo_nome"] == "Usinagem CNC" and ordem["material_nome"] == "Alumínio 6061"
    assert ordem["quantidade"] == 5
    assert ordem["solicitacao"]["processo_nome"] == "Outro Processo"


@pytest.mark.parametrize("extensao", ["zip","rar"])
def test_arquivos_ativos_somente_da_ordem_e_dos_donos(ambiente, extensao):
    http, _ = ambiente
    ordem = gerar(http).json()["id"]
    arquivo = http.post("/api/v1/solicitacoes-servico/1/arquivos-tecnicos",
        files={"file":(f"peca.{extensao}",b"arquivo D26","application/octet-stream")})
    assert arquivo.status_code == 201
    aid = arquivo.json()["id"]
    outro = http.post("/api/v1/solicitacoes-servico/2/arquivos-tecnicos",
        files={"file":("outro.zip",b"outro","application/zip")}).json()["id"]
    for perfil, empresa in (("cliente",1),("fornecedor",2)):
        base = f"/api/v1/portal-{perfil}/ordens-servico/{ordem}/arquivos"
        params = {"empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id":empresa}
        assert [item["id"] for item in http.get(base, params=params).json()] == [aid]
        assert http.get(f"{base}/{aid}/download",params=params).content == b"arquivo D26"
        assert http.get(f"{base}/{outro}/download",params=params).status_code == 404
        params[next(iter(params))] = 5 if perfil == "cliente" else 3
        assert http.get(base,params=params).status_code == 404
        assert http.get(f"{base}/{aid}/download",params=params).status_code == 404
    assert http.delete(f"/api/v1/arquivos-tecnicos/{aid}").status_code == 204
    base = f"{FORNECEDOR}/ordens-servico/{ordem}/arquivos"
    assert http.get(base,params={"empresa_fornecedora_id":2}).json() == []
    assert http.get(f"{base}/{aid}/download",params={"empresa_fornecedora_id":2}).status_code == 404


def test_rotas_d9_existentes_continuam_funcionando(ambiente):
    http, _ = ambiente
    criada = http.post("/api/v1/contratacoes/1/ordem-servico",json={"empresa_cliente_id":1})
    assert criada.status_code == 201
    oid = criada.json()["id"]
    assert http.post(f"/api/v1/ordens-servico/{oid}/iniciar",json={"empresa_cliente_id":1}).status_code == 200
    assert listar(http,"fornecedor",2).json()["itens"][0]["status"] == "em_execucao"
