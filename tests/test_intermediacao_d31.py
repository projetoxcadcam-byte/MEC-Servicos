"""Integração D31 com sessões reais: etapas, privacidade, histórico e versões."""
from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso
from backend.app.core.permissoes_acesso import autorizar_requisicao
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.entrega import EntregaServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.intermediacao import CicloIntermediacao, EventoIntermediacao
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import criar_aplicacao

pytestmark = pytest.mark.acesso_real
BASE = "/api/v1/administracao/intermediacao"
SENHA = "Senha-valida-D31-testes!"
INTERNO = "Observação privada com telefone 11999999999 e email interno@privado.local"


@pytest.fixture(scope="module")
def modelo_d31(tmp_path_factory):
    arquivo = tmp_path_factory.mktemp("modelo_d31") / "acesso.db"
    acesso = ArmazenamentoAcesso(arquivo); acesso.inicializar()
    for perfil, empresa in (("admin", None), ("cliente", 2), ("fornecedor", 4)):
        acesso.criar_usuario("Nome " + perfil, perfil + "@d31.local", perfil, empresa, SENHA, deve_alterar_senha=False)
    return arquivo


@pytest.fixture()
def ambiente_d31(tmp_path, modelo_d31):
    engine = create_engine("sqlite:///" + str(tmp_path / "negocio.db"), connect_args={"check_same_thread": False})
    sessoes = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessoes() as banco:
        banco.add_all([Empresa(id=i, razao_social="Razão reservada " + str(i), documento="doc-d31-"+str(i), tipo_empresa=p)
                       for i, p in ((2,"cliente"),(4,"fornecedor"),(6,"cliente"),(8,"fornecedor"))])
        banco.add_all([ProcessoFabricacao(id=1,codigo="cnc-d31",nome="Usinagem CNC"),Material(id=1,codigo="al-d31",nome="Alumínio")]); banco.commit()
        for oid, cliente, fornecedor, status in ((1,2,4,"aberta"),(2,6,8,"aberta"),(3,2,4,"concluida"),(4,2,4,"aberta")):
            banco.add(SolicitacaoServico(id=oid, empresa_cliente_id=cliente, processo_id=1, material_id=1,
                dimensao_x_maxima_mm=100,dimensao_y_maxima_mm=100,dimensao_z_maxima_mm=100,
                tolerancia_requerida_mm=Decimal("0.02"),quantidade=5,status="aberta")); banco.flush()
            banco.add(CotacaoFornecedor(id=oid,solicitacao_id=oid,empresa_fornecedora_id=fornecedor,valor_total=1000,prazo_dias=10,validade_dias=10,status="aceita")); banco.flush()
            banco.add(ContratacaoServico(id=oid,solicitacao_id=oid,cotacao_id=oid,empresa_cliente_id=cliente,empresa_fornecedora_id=fornecedor,valor_total=1000,prazo_dias=10,status="ativa")); banco.flush()
            if oid != 4:
                banco.add(OrdemServico(id=oid,contratacao_id=oid,solicitacao_id=oid,cotacao_id=oid,
                    empresa_cliente_id=cliente,empresa_fornecedora_id=fornecedor,processo_id=1,material_id=1,
                    quantidade=5,valor_total=1000,prazo_dias=10,status=status))
        banco.flush()
        banco.add(EntregaServico(id=1,ordem_servico_id=3,empresa_cliente_id=2,empresa_fornecedora_id=4,status="aceita",observacoes=INTERNO)); banco.commit()
    arquivo = tmp_path / "acessos.db"; shutil.copy2(modelo_d31, arquivo)
    app = criar_aplicacao(); app.state.caminho_acessos = arquivo
    def obter_teste():
        with sessoes() as banco: yield banco
    app.dependency_overrides[obter_banco] = obter_teste
    assert autorizar_requisicao not in app.dependency_overrides
    http = TestClient(app)
    try: yield http, sessoes, app
    finally: http.close(); app.dependency_overrides.clear(); engine.dispose()


def entrar(http, perfil="admin"):
    r = http.post("/api/v1/autenticacao/entrar", json={"email":perfil+"@d31.local", "senha":SENHA})
    assert r.status_code == 200, r.text
    http.headers["X-MEC-CSRF"] = r.json()["csrf"]


def iniciar(http, oid=1):
    r = http.post(f"{BASE}/ordens/{oid}/iniciar", json={"registro_interno":INTERNO})
    assert r.status_code == 201, r.text
    return r.json()


def registrar(http, acao, versao, oid=1, esperado=201, **extras):
    r = http.post(f"{BASE}/ordens/{oid}/eventos", json={"acao":acao,"versao":versao,"registro_interno":INTERNO, **extras})
    assert r.status_code == esperado, r.text
    return r


def produzir(sessoes, etapa="pronto_para_envio", oid=1):
    with sessoes() as banco:
        banco.add(EtapaProducao(ordem_servico_id=oid,empresa_fornecedora_id=4,etapa=etapa,observacoes=INTERNO)); banco.commit()


def ate_avaliacao(http, sessoes):
    iniciar(http); registrar(http,"receber_material",1); registrar(http,"encaminhar_material",2,referencia="Documento material")
    produzir(sessoes); registrar(http,"solicitar_coleta",3)
    registrar(http,"receber_pecas",4,referencia="Documento coleta",quantidade_conferida=5)
    registrar(http,"iniciar_avaliacao",5)


def test_anonimo_nao_admin_csrf_e_corpo_sem_perfil(ambiente_d31):
    http,_,_ = ambiente_d31
    assert http.get(BASE+"/ordens").status_code == 401
    assert http.post(BASE+"/ordens/1/iniciar",json={}).status_code == 401
    for perfil in ("cliente","fornecedor"):
        entrar(http,perfil)
        assert http.get(BASE+"/ordens").status_code == 403
        assert http.post(BASE+"/ordens/1/iniciar",json={"registro_interno":INTERNO}).status_code == 403
    entrar(http)
    assert http.post(BASE+"/ordens/1/iniciar",json={"registro_interno":INTERNO},headers={"X-MEC-CSRF":"falso"}).status_code == 403
    assert http.post(BASE+"/ordens/1/iniciar",json={"registro_interno":INTERNO,"usuario_admin_id":999}).status_code == 422


def test_ciclo_completo_e_entrega_conclui_somente_os(ambiente_d31):
    http,sessoes,_ = ambiente_d31; entrar(http)
    ate_avaliacao(http,sessoes)
    registrar(http,"aprovar_pecas",6,quantidade_conferida=5,parecer_tecnico="Dimensões e acabamento conferidos.")
    with sessoes() as banco: assert banco.get(OrdemServico,1).status == "aberta"
    r = registrar(http,"entregar_cliente",7,quantidade_conferida=5,referencia="Comprovante final")
    d = r.json(); assert d["ordem"]["status"] == "entregue_cliente" and d["ordem"]["ordem_status"] == "concluida"
    assert d["acoes_permitidas"] == [] and len(d["historico"]) == 8
    assert all(e["usuario_admin_id"] == 1 and e["administrador_nome"] == "Nome admin" and e["criado_em"].endswith("Z") for e in d["historico"])
    with sessoes() as banco:
        assert banco.get(OrdemServico,1).concluida_em is not None
        assert banco.get(ContratacaoServico,1).status == "ativa"
        assert banco.get(EntregaServico,1).status == "aceita"
    registrar(http,"entregar_cliente",8,esperado=409,quantidade_conferida=5,referencia="Repetida")


def test_bloqueia_saltos_quantidade_parecer_e_coleta_prematura(ambiente_d31):
    http,sessoes,_ = ambiente_d31; entrar(http); iniciar(http)
    registrar(http,"entregar_cliente",1,esperado=409)
    registrar(http,"receber_material",1); registrar(http,"encaminhar_material",2,esperado=409)
    registrar(http,"encaminhar_material",2,referencia="Documento")
    registrar(http,"solicitar_coleta",3,esperado=409)
    produzir(sessoes,"em_usinagem"); registrar(http,"solicitar_coleta",3,esperado=409)
    produzir(sessoes); registrar(http,"solicitar_coleta",3)
    registrar(http,"receber_pecas",4,quantidade_conferida=4,referencia="Coleta",esperado=409)
    registrar(http,"receber_pecas",4,quantidade_conferida=5,referencia="Coleta")
    registrar(http,"iniciar_avaliacao",5)
    registrar(http,"aprovar_pecas",6,quantidade_conferida=5,esperado=409)
    registrar(http,"solicitar_retrabalho",6,esperado=409)
    with sessoes() as banco:
        ciclo=banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==1))
        assert ciclo.versao==6 and ciclo.status=="em_avaliacao"
        assert len(banco.scalars(select(EventoIntermediacao)).all())==6


def test_retrabalho_exige_nova_producao_e_nova_avaliacao(ambiente_d31):
    http,sessoes,_=ambiente_d31; entrar(http); ate_avaliacao(http,sessoes)
    registrar(http,"solicitar_retrabalho",6,parecer_tecnico="Ajustar acabamento.")
    registrar(http,"encaminhar_retrabalho",7,referencia="Retorno fornecedor")
    registrar(http,"solicitar_coleta",8,esperado=409)
    produzir(sessoes); registrar(http,"solicitar_coleta",8)
    registrar(http,"aprovar_pecas",9,esperado=409,parecer_tecnico="Parecer informado",quantidade_conferida=5)
    registrar(http,"receber_pecas",9,referencia="Coleta retrabalho",quantidade_conferida=5)
    registrar(http,"iniciar_avaliacao",10)
    registrar(http,"aprovar_pecas",11,parecer_tecnico="Lote aprovado.",quantidade_conferida=5)


def test_versao_antiga_e_inicio_duplicado_nao_criam_evento(ambiente_d31):
    http,sessoes,_=ambiente_d31; entrar(http); iniciar(http)
    assert http.post(BASE+"/ordens/1/iniciar",json={"registro_interno":INTERNO}).status_code==409
    registrar(http,"receber_material",1)
    registrar(http,"receber_material",1,esperado=409)
    with sessoes() as banco: assert len(banco.scalars(select(EventoIntermediacao)).all())==2


def test_dois_registros_simultaneos_so_um_e_confirmado(ambiente_d31):
    http,sessoes,app=ambiente_d31; entrar(http); iniciar(http)
    barreira=Barrier(2)
    def registrar_simultaneo():
        cliente=TestClient(app)
        try:
            cliente.cookies.update(http.cookies)
            cliente.headers["X-MEC-CSRF"]=http.headers["X-MEC-CSRF"]
            barreira.wait(timeout=10)
            return cliente.post(BASE+"/ordens/1/eventos",json={"acao":"receber_material","versao":1,"registro_interno":INTERNO}).status_code
        finally:
            cliente.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados=list(pool.map(lambda _: registrar_simultaneo(),range(2)))
    assert sorted(resultados)==[201,409]
    with sessoes() as banco:
        ciclo=banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==1))
        assert ciclo.versao==2 and ciclo.status=="material_recebido"
        assert len(banco.scalars(select(EventoIntermediacao)).all())==2


@pytest.mark.parametrize("perfil,campo,empresa",[("cliente","empresa_cliente_id",2),("fornecedor","empresa_fornecedora_id",4)])
def test_portal_somente_dono_sem_textos_contatos_ou_usuario_admin(ambiente_d31,perfil,campo,empresa):
    http,_,_ = ambiente_d31; entrar(http); iniciar(http); registrar(http,"receber_material",1)
    entrar(http,perfil); url=f"/api/v1/portal-{perfil}/intermediacao"
    r=http.get(url+"/1",params={campo:empresa}); assert r.status_code==200
    assert set(r.json())=={"ordem_servico_id","status","atualizado_em","historico"}
    assert set(r.json()["historico"][0])=={"acao","status_resultante","criado_em"}
    assert "11999999999" not in r.text and "interno@" not in r.text and "Nome admin" not in r.text and "Razão" not in r.text
    assert http.get(url+"/2",params={campo:empresa}).status_code==404
    assert http.get(url+"/1",params={campo:empresa+4}).status_code==403
    assert http.get(url+"/1").status_code==403
    assert http.get(url+"/1",params=[(campo,empresa),(campo,empresa)]).status_code==403
    assert http.post(BASE+"/ordens/1/eventos",json={"acao":"receber_material","versao":2,"registro_interno":INTERNO}).status_code==403


def test_legado_concluido_nao_recebe_ciclo_e_leituras_preservam_registros(ambiente_d31):
    http,sessoes,_=ambiente_d31; entrar(http)
    d=http.get(BASE+"/ordens/3").json(); assert d["ordem"]["pode_iniciar"] is False and d["historico"]==[]
    assert http.post(BASE+"/ordens/3/iniciar",json={"registro_interno":INTERNO}).status_code==409
    assert http.post(BASE+"/ordens/999/iniciar",json={"registro_interno":INTERNO}).status_code==404
    with sessoes() as banco:
        assert banco.get(OrdemServico,3).status=="concluida" and banco.get(EntregaServico,1).status=="aceita"


def test_rotas_anteriores_nao_encerram_ciclo_novo(ambiente_d31):
    http,_,_=ambiente_d31; entrar(http); iniciar(http)
    for url in ("/ordens-servico/1/concluir","/ordens-servico/1/cancelar","/ordens-servico/1/entregas",
                "/portal-fornecedor/entregas/1/registrar","/portal-cliente/entregas/1/1/aceitar",
                "/solicitacoes-servico/1/contratacao/cancelar"):
        assert http.post("/api/v1"+url,json={}).status_code==409


def test_fornecedor_producao_aguarda_encaminhamento_e_bloqueia_apos_coleta(ambiente_d31):
    http,_,_=ambiente_d31; entrar(http); iniciar(http)
    entrar(http,"fornecedor")
    inicio="/api/v1/portal-fornecedor/ordens-servico/1/iniciar"
    assert http.post(inicio,json={"empresa_fornecedora_id":4}).status_code==409
    entrar(http); registrar(http,"receber_material",1); registrar(http,"encaminhar_material",2,referencia="Material")
    entrar(http,"fornecedor"); assert http.post(inicio,json={"empresa_fornecedora_id":4}).status_code==200
    etapa="/api/v1/portal-fornecedor/producao/1/etapas"
    r=http.post(etapa,json={"empresa_fornecedora_id":4,"ultima_etapa_id":0,"etapa":"pronto_para_envio"})
    assert r.status_code==201
    entrar(http); registrar(http,"solicitar_coleta",3)
    entrar(http,"fornecedor")
    assert http.post(etapa,json={"empresa_fornecedora_id":4,"ultima_etapa_id":r.json()["id"],"etapa":"em_usinagem"}).status_code==409
    assert http.post("/api/v1/portal-fornecedor/ordens-servico/2/iniciar",json={"empresa_fornecedora_id":4}).status_code==404


def test_cancelamento_audita_e_bloqueia_novas_mutacoes(ambiente_d31):
    http,sessoes,_=ambiente_d31; entrar(http); iniciar(http)
    r=registrar(http,"cancelar",1); assert r.json()["ordem"]["status"]=="cancelado"
    with sessoes() as banco:
        assert banco.get(OrdemServico,1).status=="cancelada"
        assert banco.get(OrdemServico,1).cancelada_em is not None
    registrar(http,"receber_material",2,esperado=409)


def test_cria_ordem_apenas_para_contratacao_ativa_sem_ordem(ambiente_d31):
    http,_,_=ambiente_d31; entrar(http)
    lista=http.get(BASE+"/contratacoes-sem-ordem").json(); assert [c["id"] for c in lista]==[4]
    r=http.post(BASE+"/contratacoes/4/ordem",json={"registro_interno":INTERNO}); assert r.status_code==201
    assert r.json()["ordem"]["pode_iniciar"] is True and r.json()["ordem"]["contratacao_id"]==4
    assert http.post(BASE+"/contratacoes/4/ordem",json={"registro_interno":INTERNO}).status_code==409
    assert http.get(BASE+"/ordens",params={"filtro":"todos","limite":1}).json()["total"]==4
    assert http.get(BASE+"/ordens",params={"limite":101}).status_code==422
