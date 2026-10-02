from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos
from backend.app.api.rotas.ordens_servico import roteador as original
from backend.app.api.rotas.portal_ordens_servico import roteador as ordens
from backend.app.api.rotas.portal_producao import roteador as producao
from backend.app.api.rotas.portal_entregas import roteador as portal
from backend.app.api.rotas.entregas import roteador as entregas_original
from backend.app.api.rotas.etapas_producao import roteador as etapas
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.entrega import EntregaServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico

CLIENTE = "/api/v1/portal-cliente"
FORNECEDOR = "/api/v1/portal-fornecedor"


def novo_contrato(banco, numero, cliente=1, fornecedor=2, situacao="ativa"):
    pedido = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,
        dimensao_x_maxima_mm=500, dimensao_y_maxima_mm=300, dimensao_z_maxima_mm=250,
        tolerancia_requerida_mm=Decimal("0.0200"), quantidade=5, status="encerrada", observacoes="Pedido D28.")
    banco.add(pedido)
    banco.flush()
    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=numero, empresa_fornecedora_id=fornecedor,
        valor_total=Decimal("1250.50"), prazo_dias=15, validade_dias=10, status="aceita",
        decidida_por_empresa_id=cliente, encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None))
    banco.add(cotacao)
    banco.flush()
    contrato = ContratacaoServico(id=numero, solicitacao_id=numero, cotacao_id=numero,
        empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, valor_total=Decimal("1250.50"),
        prazo_dias=15, status=situacao, observacoes="Termos da contratação D28.")
    banco.add(contrato)
    banco.flush()
    return contrato


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'portal_entregas_teste.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def chaves(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ServicoArquivoTecnico, "STORAGE_ROOT", tmp_path)
    with sessoes() as banco:
        banco.add_all([
            Empresa(id=1, razao_social="Cliente D28", documento="cliente-d28-1", tipo_empresa="cliente"),
            Empresa(id=2, razao_social="Fornecedor D28", documento="fornecedor-d28-2", tipo_empresa="fornecedor"),
            Empresa(id=3, razao_social="Outro Fornecedor", documento="fornecedor-d28-3", tipo_empresa="fornecedor"),
            Empresa(id=4, razao_social="Empresa Ambos", documento="ambos-d28-4", tipo_empresa="ambos"),
            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-d28-5", tipo_empresa="cliente"),
            ProcessoFabricacao(id=1, codigo="cnc-d28", nome="Usinagem CNC"),
            Material(id=1, codigo="al6061-d28", nome="Alumínio 6061"),
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
    for roteador in (arquivos, original, ordens, etapas, producao, entregas_original, portal):
        app.include_router(roteador, prefix="/api/v1")
    app.dependency_overrides[obter_banco] = banco_teste
    try:
        with TestClient(app) as http:
            yield http, sessoes
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()



def gerar(http, contrato=1, cliente=1):
    return http.post(f"{CLIENTE}/contratacoes/{contrato}/ordem-servico", json={"empresa_cliente_id":cliente})


def iniciar(http, oid, fornecedor=2):
    return http.post(f"{FORNECEDOR}/ordens-servico/{oid}/iniciar", json={"empresa_fornecedora_id":fornecedor})


def etapa(http, oid, valor="pronto_para_envio", fornecedor=2, ultima=0):
    return http.post(f"{FORNECEDOR}/producao/{oid}/etapas",json={"empresa_fornecedora_id":fornecedor,
        "etapa":valor,"ultima_etapa_id":ultima,"observacoes":"Etapa para entrega D28."})


def preparar(http, contrato=1, cliente=1, fornecedor=2):
    oid=gerar(http,contrato,cliente).json()["id"]
    assert iniciar(http,oid,fornecedor).status_code == 200
    eid=etapa(http,oid,fornecedor=fornecedor).json()["id"]
    return oid,eid


def detalhe(http, oid, perfil="cliente", empresa=1):
    return http.get(f"/api/v1/portal-{perfil}/entregas/{oid}",params={
        "empresa_cliente_id" if perfil=="cliente" else "empresa_fornecedora_id":empresa})


def listar(http, perfil="cliente", empresa=1, **extra):
    return http.get(f"/api/v1/portal-{perfil}/entregas",params={
        "empresa_cliente_id" if perfil=="cliente" else "empresa_fornecedora_id":empresa,**extra})


def registrar(http,oid,eid,fornecedor=2,ultima=0,**extra):
    return http.post(f"{FORNECEDOR}/entregas/{oid}/registrar",json={"empresa_fornecedora_id":fornecedor,
        "ultima_etapa_id":eid,"ultima_entrega_id":ultima,"observacoes":"Peças entregues com identificação.",**extra})


def decidir(http,oid,entrega,acao="aceitar",cliente=1,**extra):
    return http.post(f"{CLIENTE}/entregas/{oid}/{entrega}/{acao}",json={"empresa_cliente_id":cliente,**extra})


def test_lista_ordens_sem_entrega_e_consulta_apenas_donos(ambiente):
    http,_=ambiente
    oid=gerar(http).json()["id"]
    item=listar(http).json()["itens"][0]
    assert item == listar(http,"fornecedor",2).json()["itens"][0]
    assert item["id"] == oid and item["ultima_entrega_id"]==item["total_entregas"]==0
    assert item["ultima_entrega_status"] is None and item["entrega_pendente_id"] is None
    assert listar(http,"cliente",5).json()["total"]==0
    assert listar(http,"fornecedor",3).json()["total"]==0
    assert detalhe(http,oid,"cliente",5).status_code == 404
    assert detalhe(http,oid,"fornecedor",3).status_code == 404


def test_fluxo_entrega_aceite_conclui_ordem_e_encerra_contratacao(ambiente):
    http,sessoes=ambiente
    oid,eid=preparar(http)
    resposta=registrar(http,oid,eid)
    assert resposta.status_code==201
    entrega=resposta.json();did=entrega["id"]
    assert entrega["status"]=="entregue" and entrega["entregue_em"] and entrega["aceita_em"] is None
    antes=detalhe(http,oid).json()
    assert antes==detalhe(http,oid,"fornecedor",2).json()
    assert antes["ordem"]["status"]=="em_execucao" and antes["ordem"]["contratacao_status"]=="ativa"
    assert antes["ordem"]["entrega_pendente_id"]==did and antes["historico"]==[entrega]
    aceita=decidir(http,oid,did)
    assert aceita.status_code==200 and aceita.json()["status"]=="aceita"
    assert aceita.json()["aceita_em"] and aceita.json()["recusada_em"] is None
    dados=detalhe(http,oid).json()
    assert dados["ordem"]["status"]=="concluida" and dados["ordem"]["contratacao_status"]=="encerrada"
    assert dados["ordem"]["total_entregas"]==1 and dados["ordem"]["entrega_pendente_id"] is None
    assert listar(http,"fornecedor",2).json()["itens"][0]["ultima_entrega_status"]=="aceita"
    with sessoes() as banco:
        ordem=banco.get(OrdemServico,oid);contrato=banco.get(ContratacaoServico,1)
        assert ordem.concluida_em==contrato.encerrada_em==banco.get(EntregaServico,did).aceita_em
        assert str(ordem.valor_total)=="1250.50" and ordem.quantidade==5 and ordem.prazo_dias==15
        assert banco.scalars(select(EtapaProducao)).one().id==eid


@pytest.mark.parametrize("motivo",[None,"","   "])
def test_recusa_sem_motivo_nao_muda_entrega_ordem_ou_contrato(ambiente,motivo):
    http,_=ambiente
    oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    assert decidir(http,oid,did,"recusar",motivo=motivo).status_code==422
    dados=detalhe(http,oid).json()
    assert dados["historico"][0]["status"]=="entregue" and dados["historico"][0]["recusada_em"] is None
    assert dados["ordem"]["status"]=="em_execucao" and dados["ordem"]["contratacao_status"]=="ativa"


def test_recusa_correcao_nova_entrega_e_aceite_preservam_os_registros(ambiente):
    http,_=ambiente
    oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    recusada=decidir(http,oid,did,"recusar",motivo="  Corrigir identificação das peças.  ")
    assert recusada.status_code==200 and recusada.json()["motivo_recusa"]=="Corrigir identificação das peças."
    dados=detalhe(http,oid).json()
    assert dados["ordem"]["status"]=="em_execucao" and dados["ordem"]["contratacao_status"]=="ativa"
    assert dados["ordem"]["entrega_pendente_id"] is None
    assert registrar(http,oid,eid).status_code==409
    nova=registrar(http,oid,eid,ultima=did,observacoes="Identificação corrigida.")
    assert nova.status_code==201
    assert decidir(http,oid,nova.json()["id"]).status_code==200
    historico=detalhe(http,oid).json()["historico"]
    assert [e["status"] for e in historico]==["recusada","aceita"]
    assert historico[0]["observacoes"]=="Peças entregues com identificação."
    assert historico[0]["motivo_recusa"]=="Corrigir identificação das peças." and historico[0]["recusada_em"]
    assert historico[1]["observacoes"]=="Identificação corrigida."


@pytest.mark.parametrize("situacao",["aberta","concluida","cancelada"])
def test_ordem_fora_de_execucao_nao_recebe_entrega(ambiente,situacao):
    http,sessoes=ambiente;oid=gerar(http).json()["id"]
    with sessoes() as banco:
        banco.get(OrdemServico,oid).status=situacao;banco.commit()
    assert registrar(http,oid,0).status_code==409
    assert detalhe(http,oid).json()["historico"]==[]


def test_exige_ultima_etapa_pronto_para_envio(ambiente):
    http,_=ambiente;oid=gerar(http).json()["id"];iniciar(http,oid)
    assert registrar(http,oid,0).status_code==409
    eid=etapa(http,oid).json()["id"]
    outra=etapa(http,oid,"em_acabamento",ultima=eid).json()["id"]
    assert registrar(http,oid,eid).json()["detail"]=="producao_alterada_atualize"
    assert registrar(http,oid,outra).json()["detail"]=="ordem_servico_nao_esta_pronta_para_entrega"
    assert detalhe(http,oid).json()["historico"]==[]


def test_nao_aceita_revisao_de_producao_antiga_mesmo_que_esteja_pronta(ambiente):
    http,_=ambiente;oid,eid=preparar(http)
    outra=etapa(http,oid,ultima=eid).json()["id"]
    assert registrar(http,oid,eid).status_code==409
    assert registrar(http,oid,outra).status_code==201


def test_entrega_pendente_impede_novo_registro_e_repeticao_do_envio(ambiente):
    http,_=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    assert registrar(http,oid,eid).json()["detail"]=="entregas_alteradas_atualize"
    assert registrar(http,oid,eid,ultima=did).json()["detail"]=="entrega_pendente_ja_existe"
    assert detalhe(http,oid).json()["ordem"]["total_entregas"]==1


@pytest.mark.parametrize("empresa,codigo",[(3,404),(1,403),(999,404)])
def test_outro_fornecedor_ou_perfil_nao_pode_entregar(ambiente,empresa,codigo):
    http,_=ambiente;oid,eid=preparar(http)
    assert registrar(http,oid,eid,fornecedor=empresa).status_code==codigo
    assert detalhe(http,oid).json()["historico"]==[]


@pytest.mark.parametrize("empresa,codigo",[(5,404),(2,403),(999,404)])
def test_outro_cliente_ou_perfil_nao_pode_decidir(ambiente,empresa,codigo):
    http,_=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    assert decidir(http,oid,did,cliente=empresa).status_code==codigo
    assert decidir(http,oid,did,"recusar",cliente=empresa,motivo="Teste.").status_code==codigo
    assert detalhe(http,oid).json()["historico"][0]["status"]=="entregue"


@pytest.mark.parametrize("campos",[{"ultima_etapa_id":-1},{"ultima_entrega_id":-1},{"empresa_fornecedora_id":0},
    {"observacoes":"x"*5001},{"empresa_cliente_id":1},{"status":"aceita"}])
def test_campos_invalidos_do_registro_nao_gravam(ambiente,campos):
    http,_=ambiente;oid,eid=preparar(http)
    assert registrar(http,oid,eid,**campos).status_code==422
    assert detalhe(http,oid).json()["historico"]==[]


def test_decisao_valida_campos_e_papel_e_exige_versoes_no_registro(ambiente):
    http,_=ambiente;oid,eid=preparar(http)
    assert http.post(f"{FORNECEDOR}/entregas/{oid}/registrar",json={"empresa_fornecedora_id":2}).status_code==422
    did=registrar(http,oid,eid).json()["id"]
    for campos in ({"motivo":"x"*5001},{"empresa_fornecedora_id":2},{"status":"aceita"}):
        assert decidir(http,oid,did,"recusar",**campos).status_code==422
    assert http.post(f"{FORNECEDOR}/entregas/{oid}/{did}/aceitar",json={"empresa_cliente_id":1}).status_code==404
    assert http.post(f"{CLIENTE}/entregas/{oid}/registrar",json={"empresa_fornecedora_id":2}).status_code==404


@pytest.mark.parametrize("parametros,codigo",[({},422),({"empresa_cliente_id":0},422),
    ({"empresa_cliente_id":1,"limite":101},422),({"empresa_cliente_id":1,"deslocamento":-1},422),
    ({"empresa_cliente_id":2},403),({"empresa_cliente_id":999},404)])
def test_consulta_valida_empresa_e_paginacao(ambiente,parametros,codigo):
    http,_=ambiente
    assert http.get(CLIENTE+"/entregas",params=parametros).status_code==codigo


@pytest.mark.parametrize("situacao",["cancelada","encerrada"])
def test_contrato_finalizado_bloqueia_registro_e_decisoes_preservando_historico(ambiente,situacao):
    http,sessoes=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    with sessoes() as banco:
        banco.get(ContratacaoServico,1).status=situacao;banco.commit()
    assert registrar(http,oid,eid,ultima=did).status_code==409
    assert decidir(http,oid,did).status_code==409
    assert decidir(http,oid,did,"recusar",motivo="Correção.").status_code==409
    assert detalhe(http,oid).json()["historico"][0]["status"]=="entregue"


def test_nao_mistura_entregas_de_outra_ordem_e_resumos_paginados(ambiente):
    http,_=ambiente;a,ea=preparar(http);b,eb=preparar(http,5)
    da=registrar(http,a,ea).json()["id"];db=registrar(http,b,eb).json()["id"]
    assert decidir(http,a,db).status_code==404
    assert decidir(http,b,da,"recusar",motivo="Correção.").status_code==404
    assert detalhe(http,a).json()["ordem"]["entrega_pendente_id"]==da
    assert detalhe(http,b).json()["ordem"]["entrega_pendente_id"]==db
    p1=listar(http,limite=1).json();p2=listar(http,deslocamento=1,limite=1).json()
    assert p1["total"]==p2["total"]==2
    assert p1["itens"][0]["id"]==b and p2["itens"][0]["id"]==a


@pytest.mark.parametrize("acao",["aceitar","recusar"])
def test_entrega_decidida_nao_recebe_nova_decisao(ambiente,acao):
    http,_=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    assert decidir(http,oid,did,acao,motivo="Correção.").status_code==200
    assert decidir(http,oid,did,"aceitar").status_code==409
    assert decidir(http,oid,did,"recusar",motivo="Outra decisão.").status_code==409


def test_entregas_antigas_do_d11_aparecem_sem_migracao(ambiente):
    http,_=ambiente;oid,eid=preparar(http)
    antiga=http.post(f"/api/v1/ordens-servico/{oid}/entregas",json={"empresa_fornecedora_id":2,"observacoes":"Anterior ao D28."})
    assert antiga.status_code==201
    assert detalhe(http,oid).json()["historico"]==[antiga.json()]
    assert decidir(http,oid,antiga.json()["id"],"recusar",motivo="Corrigir.").status_code==200
    assert registrar(http,oid,eid,ultima=antiga.json()["id"]).status_code==201


def test_empresa_ambos_utiliza_cada_perfil(ambiente):
    http,sessoes=ambiente
    with sessoes() as banco:
        novo_contrato(banco,6,cliente=4,fornecedor=4);banco.commit()
    oid,eid=preparar(http,6,4,4);did=registrar(http,oid,eid,fornecedor=4).json()["id"]
    assert listar(http,"cliente",4).json()["total"]==listar(http,"fornecedor",4).json()["total"]==1
    assert decidir(http,oid,did,cliente=4).status_code==200


def test_duas_sessoes_com_mesma_revisao_criam_so_uma_entrega(ambiente):
    from concurrent.futures import ThreadPoolExecutor
    http,_=ambiente;oid,eid=preparar(http)
    with ThreadPoolExecutor(max_workers=2) as executor:
        respostas=list(executor.map(lambda _:registrar(http,oid,eid),range(2)))
    assert sorted(r.status_code for r in respostas)==[201,409]
    assert detalhe(http,oid).json()["ordem"]["total_entregas"]==1


def test_aceite_e_recusa_concorrentes_resultam_em_uma_so_decisao(ambiente):
    from concurrent.futures import ThreadPoolExecutor
    http,sessoes=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()["id"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        respostas=list(executor.map(lambda acao:decidir(http,oid,did,acao,motivo="Corrigir."),("aceitar","recusar")))
    assert sorted(r.status_code for r in respostas)==[200,409]
    with sessoes() as banco:
        entrega=banco.get(EntregaServico,did);ordem=banco.get(OrdemServico,oid);contrato=banco.get(ContratacaoServico,1)
        if entrega.status=="aceita":
            assert entrega.aceita_em and entrega.recusada_em is None
            assert ordem.status=="concluida" and contrato.status=="encerrada"
        else:
            assert entrega.status=="recusada" and entrega.recusada_em and entrega.aceita_em is None
            assert ordem.status=="em_execucao" and contrato.status=="ativa"
