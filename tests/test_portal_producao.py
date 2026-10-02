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
from backend.app.api.rotas.portal_ordens_servico import roteador as ordens
from backend.app.api.rotas.portal_producao import roteador as portal
from backend.app.api.rotas.etapas_producao import roteador as etapas
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.portal_ordens_servico import ServicoPortalOrdens
from backend.app.services.portal_producao import ServicoPortalProducao

CLIENTE = "/api/v1/portal-cliente"
FORNECEDOR = "/api/v1/portal-fornecedor"


def novo_contrato(banco, numero, cliente=1, fornecedor=2, situacao="ativa"):
    pedido = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,
        dimensao_x_maxima_mm=500, dimensao_y_maxima_mm=300, dimensao_z_maxima_mm=250,
        tolerancia_requerida_mm=Decimal("0.0200"), quantidade=5, status="encerrada", observacoes="Pedido D27.")
    banco.add(pedido)
    banco.flush()
    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=numero, empresa_fornecedora_id=fornecedor,
        valor_total=Decimal("1250.50"), prazo_dias=15, validade_dias=10, status="aceita",
        decidida_por_empresa_id=cliente, encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None))
    banco.add(cotacao)
    banco.flush()
    contrato = ContratacaoServico(id=numero, solicitacao_id=numero, cotacao_id=numero,
        empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, valor_total=Decimal("1250.50"),
        prazo_dias=15, status=situacao, observacoes="Termos da contratação D27.")
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
            Empresa(id=1, razao_social="Cliente D27", documento="cliente-d27-1", tipo_empresa="cliente"),
            Empresa(id=2, razao_social="Fornecedor D27", documento="fornecedor-d27-2", tipo_empresa="fornecedor"),
            Empresa(id=3, razao_social="Outro Fornecedor", documento="fornecedor-d27-3", tipo_empresa="fornecedor"),
            Empresa(id=4, razao_social="Empresa Ambos", documento="ambos-d27-4", tipo_empresa="ambos"),
            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-d27-5", tipo_empresa="cliente"),
            ProcessoFabricacao(id=1, codigo="cnc-d27", nome="Usinagem CNC"),
            Material(id=1, codigo="al6061-d27", nome="Alumínio 6061"),
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
    for roteador in (arquivos, original, ordens, etapas, portal):
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


def producao(http, perfil="cliente", empresa=1, **extra):
    return http.get(f"/api/v1/portal-{perfil}/producao", params={
        "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id":empresa, **extra,
    })


def detalhe(http, ordem, perfil="cliente", empresa=1):
    return http.get(f"/api/v1/portal-{perfil}/producao/{ordem}", params={
        "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id":empresa,
    })


def registrar(http, ordem, etapa="aguardando_material", fornecedor=2, ultima=0, **extra):
    return http.post(f"{FORNECEDOR}/producao/{ordem}/etapas", json={
        "empresa_fornecedora_id":fornecedor, "etapa":etapa, "ultima_etapa_id":ultima,
        "observacoes":"Material em compra.", **extra,
    })


def test_ordens_sem_etapas_sao_listadas_so_para_os_donos(ambiente):
    http, _ = ambiente
    oid = gerar(http).json()["id"]
    item = producao(http).json()["itens"][0]
    assert item == producao(http,"fornecedor",2).json()["itens"][0]
    assert item["id"] == oid and item["etapa_atual"] is None and item["ultima_etapa_id"] == 0
    assert item["total_atualizacoes"] == 0 and item["etapa_atual_em"] is None
    assert item["fornecedor_razao_social"] == "Fornecedor D27"
    assert producao(http,"cliente",5).json()["total"] == 0
    assert producao(http,"fornecedor",3).json()["total"] == 0
    dados = detalhe(http,oid).json()
    assert dados["historico"] == [] and dados["ordem"]["id"] == oid


@pytest.mark.parametrize("etapa", ["aguardando_material","em_usinagem","em_solda_dobra","em_acabamento","pronto_para_envio"])
def test_etapas_d10_normalizadas_e_preservadas_no_historico(ambiente, etapa):
    http, sessoes = ambiente
    oid = gerar(http).json()["id"]
    resposta = registrar(http,oid,etapa="  " + etapa.upper() + "  ")
    assert resposta.status_code == 201 and resposta.json()["etapa"] == etapa
    novo = resposta.json()
    for perfil,empresa in (("cliente",1),("fornecedor",2)):
        dados = detalhe(http,oid,perfil,empresa).json()
        assert dados["etapa_atual"] == etapa and dados["ultima_etapa_id"] == novo["id"]
        assert dados["historico"][0] == novo
        resumo = producao(http,perfil,empresa).json()["itens"][0]
        assert resumo["total_atualizacoes"] == 1 and resumo["ultima_etapa_id"] == novo["id"]
        assert resumo["etapa_atual_em"] == novo["criada_em"]
    with sessoes() as banco:
        assert banco.get(OrdemServico,oid).status == "aberta"
        assert banco.get(OrdemServico,oid).iniciada_em is None
        assert banco.get(ContratacaoServico,1).status == "ativa"


def test_historico_pode_incluir_observacoes_e_etapas_alternativas(ambiente):
    http, _ = ambiente
    oid = gerar(http).json()["id"]
    ids=[]
    for etapa,nota in (("aguardando_material","Material em compra."),("em_solda_dobra","Etapa adequada ao serviço."),("em_acabamento","Acabamento iniciado.")):
        resp = registrar(http,oid,etapa,ultima=ids[-1] if ids else 0,observacoes=nota)
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    dados = detalhe(http,oid).json()
    assert [item["id"] for item in dados["historico"]] == ids
    assert dados["etapa_atual"] == "em_acabamento"
    assert dados["historico"][1]["observacoes"] == "Etapa adequada ao serviço."
    assert dados["ordem"]["total_atualizacoes"] == 3


def test_repeticao_com_versao_antiga_nao_duplica_etapa(ambiente):
    http, sessoes = ambiente
    oid = gerar(http).json()["id"]
    primeira = registrar(http,oid).json()
    repetida = registrar(http,oid)
    assert repetida.status_code == 409 and repetida.json()["detail"] == "producao_alterada_atualize"
    with sessoes() as banco:
        assert len(banco.scalars(select(EtapaProducao)).all()) == 1
    atualizada = registrar(http,oid,ultima=primeira["id"],observacoes="Compra confirmada.")
    assert atualizada.status_code == 201
    assert len(detalhe(http,oid).json()["historico"]) == 2


def test_repetir_mesma_etapa_com_nova_observacao_e_permitido_apos_atualizar(ambiente):
    http, _ = ambiente
    oid = gerar(http).json()["id"]
    primeiro = registrar(http,oid).json()["id"]
    assert registrar(http,oid,ultima=primeiro,observacoes="Material atrasado pelo distribuidor.").status_code == 201
    historico = detalhe(http,oid).json()["historico"]
    assert len(historico) == 2 and historico[0]["observacoes"] != historico[1]["observacoes"]


@pytest.mark.parametrize("fornecedor,codigo", [(3,404),(1,403),(999,404)])
def test_fornecedor_incorreto_nao_pode_registrar(ambiente, fornecedor, codigo):
    http, sessoes = ambiente
    oid = gerar(http).json()["id"]
    assert registrar(http,oid,fornecedor=fornecedor).status_code == codigo
    with sessoes() as banco:
        assert banco.scalars(select(EtapaProducao)).all() == []


@pytest.mark.parametrize("perfil,empresa", [("cliente",5),("fornecedor",3)])
def test_detalhe_de_outra_empresa_nao_expoe_historico(ambiente, perfil, empresa):
    http, _ = ambiente
    oid = gerar(http).json()["id"]
    registrar(http,oid)
    assert detalhe(http,oid,perfil,empresa).status_code == 404


@pytest.mark.parametrize("situacao", ["concluida","cancelada"])
def test_ordem_finalizada_tem_historico_mas_nao_recebe_novos_registros(ambiente, situacao):
    http, sessoes = ambiente
    oid = gerar(http).json()["id"]
    etapa = registrar(http,oid).json()["id"]
    with sessoes() as banco:
        banco.get(OrdemServico,oid).status=situacao
        banco.commit()
    resposta = registrar(http,oid,"em_usinagem",ultima=etapa)
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "ordem_servico_nao_pode_atualizar_producao"
    dados = detalhe(http,oid).json()
    assert len(dados["historico"]) == 1 and dados["ordem"]["status"] == situacao


@pytest.mark.parametrize("situacao", ["cancelada","encerrada"])
def test_contrato_inativo_bloqueia_registro_sem_apagar_historico(ambiente, situacao):
    http, sessoes = ambiente
    oid = gerar(http).json()["id"]
    registrar(http,oid)
    with sessoes() as banco:
        banco.get(ContratacaoServico,1).status=situacao
        banco.commit()
    resp = registrar(http,oid,"em_usinagem",ultima=1)
    assert resp.status_code == 409 and resp.json()["detail"] == "contratacao_nao_esta_ativa"
    assert len(detalhe(http,oid).json()["historico"]) == 1


def test_resumo_atual_por_ordem_paginacao_e_contagem_nao_misturam_historicos(ambiente):
    http, _ = ambiente
    a=gerar(http).json()["id"]
    b=gerar(http,5).json()["id"]
    aid=registrar(http,a).json()["id"]
    registrar(http,b,"em_usinagem")
    registrar(http,a,"em_acabamento",ultima=aid)
    primeira=producao(http,limite=1).json()
    segunda=producao(http,deslocamento=1,limite=1).json()
    assert primeira["total"] == segunda["total"] == 2
    assert primeira["itens"][0]["id"] == b and primeira["itens"][0]["total_atualizacoes"] == 1
    assert primeira["itens"][0]["etapa_atual"] == "em_usinagem"
    assert segunda["itens"][0]["id"] == a and segunda["itens"][0]["total_atualizacoes"] == 2
    assert segunda["itens"][0]["etapa_atual"] == "em_acabamento"


@pytest.mark.parametrize("campos", [{"etapa":"inexistente"},{"observacoes":"x"*5001},{"ultima_etapa_id":-1},
                                   {"empresa_cliente_id":1},{"empresa_fornecedora_id":0}])
def test_corpo_invalido_nao_grava(ambiente, campos):
    http, sessoes = ambiente
    oid=gerar(http).json()["id"]
    assert registrar(http,oid,**campos).status_code == 422
    with sessoes() as banco:
        assert banco.scalars(select(EtapaProducao)).all() == []


def test_registro_exige_versao_e_empresa_do_fornecedor(ambiente):
    http, _ = ambiente
    oid=gerar(http).json()["id"]
    url=f"{FORNECEDOR}/producao/{oid}/etapas"
    assert http.post(url,json={"empresa_fornecedora_id":2,"etapa":"em_usinagem"}).status_code == 422
    assert http.post(url,json={"empresa_cliente_id":1,"etapa":"em_usinagem","ultima_etapa_id":0}).status_code == 422
    assert http.post(f"{CLIENTE}/producao/{oid}/etapas",json={"etapa":"em_usinagem"}).status_code == 404


@pytest.mark.parametrize("parametros,codigo", [({},422),({"empresa_cliente_id":0},422),
    ({"empresa_cliente_id":1,"limite":101},422),({"empresa_cliente_id":1,"deslocamento":-1},422),
    ({"empresa_cliente_id":2},403),({"empresa_cliente_id":999},404)])
def test_consulta_valida_empresa_e_paginacao(ambiente, parametros, codigo):
    http, _ = ambiente
    assert http.get(CLIENTE+"/producao",params=parametros).status_code == codigo


def test_etapas_do_d10_existente_sao_visiveis_sem_migracao(ambiente):
    http, _ = ambiente
    oid=gerar(http).json()["id"]
    old=http.post(f"/api/v1/ordens-servico/{oid}/etapas-producao",json={
        "empresa_fornecedora_id":2,"etapa":"em_usinagem","observacoes":"Registro anterior ao D27."})
    assert old.status_code == 201
    dados=detalhe(http,oid).json()
    assert dados["historico"][0]==old.json()
    assert dados["ultima_etapa_id"]==old.json()["id"]
    assert registrar(http,oid,"em_acabamento").status_code == 409


def test_empresa_ambos_utiliza_cada_perfil_sem_expor_outros(ambiente):
    http,sessoes=ambiente
    with sessoes() as banco:
        novo_contrato(banco,6,cliente=4,fornecedor=4)
        banco.commit()
    oid=gerar(http,6,4).json()["id"]
    assert registrar(http,oid,fornecedor=4).status_code == 201
    assert producao(http,"cliente",4).json()["total"] == 1
    assert producao(http,"fornecedor",4).json()["total"] == 1


def test_registrar_etapas_em_execucao_e_concluir_no_d26_mantem_historico(ambiente):
    http,_=ambiente
    oid=gerar(http).json()["id"]
    assert agir(http,oid).status_code == 200
    eid=registrar(http,oid,"em_usinagem").json()["id"]
    pronta=registrar(http,oid,"pronto_para_envio",ultima=eid)
    assert pronta.status_code == 201
    assert detalhe(http,oid).json()["ordem"]["status"] == "em_execucao"
    assert agir(http,oid,"concluir").status_code == 200
    dados=detalhe(http,oid).json()
    assert dados["ordem"]["status"] == "concluida"
    assert dados["etapa_atual"] == "pronto_para_envio" and len(dados["historico"]) == 2
