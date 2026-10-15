"""Financeiro D32: sessões reais, dinheiro, estornos, concorrência e privacidade."""
from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso
from backend.app.core.permissoes_acesso import autorizar_requisicao
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.financeiro_administrativo import ControleFinanceiro, EventoFinanceiro, RepasseAdministrativo
from backend.app.principal import criar_aplicacao
from backend.app.schemas.financeiro_administrativo import RegistroFinanceiro
from backend.app.services.financeiro_administrativo import ServicoFinanceiroAdministrativo

pytestmark = pytest.mark.acesso_real
BASE = "/api/v1/administracao/financeiro/contratacoes"
SENHA = "Senha-valida-D32-testes!"
INTERNO = "Conferência privada: interno@privado.local telefone 11999999999"


@pytest.fixture(scope="module")
def contas_d32(tmp_path_factory):
    arquivo = tmp_path_factory.mktemp("contas_d32") / "acesso.db"
    acesso = ArmazenamentoAcesso(arquivo); acesso.inicializar()
    for perfil, empresa in (("admin", None), ("cliente", 2), ("fornecedor", 4)):
        acesso.criar_usuario("Operador reservado " + perfil, perfil + "@d32.local", perfil, empresa,
                             SENHA, deve_alterar_senha=False)
    return arquivo


@pytest.fixture()
def ambiente_d32(tmp_path, contas_d32):
    engine = create_engine("sqlite:///" + str(tmp_path / "negocio.db"), connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def chaves_estrangeiras(conexao, _): conexao.execute("PRAGMA foreign_keys=ON")
    sessoes = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessoes() as banco:
        banco.add_all([Empresa(id=i, razao_social="Empresa secreta " + str(i), documento="doc-d32-"+str(i), tipo_empresa=p)
            for i,p in ((2,"cliente"),(4,"fornecedor"),(6,"cliente"),(8,"fornecedor"))])
        banco.add_all([ProcessoFabricacao(id=1,codigo="cnc-d32",nome="Usinagem CNC"), Material(id=1,codigo="al-d32",nome="Alumínio")]); banco.commit()
        for cid,cliente,fornecedor in ((1,2,4),(2,6,8)):
            banco.add(SolicitacaoServico(id=cid,empresa_cliente_id=cliente,processo_id=1,material_id=1,
                dimensao_x_maxima_mm=100,dimensao_y_maxima_mm=100,dimensao_z_maxima_mm=100,
                tolerancia_requerida_mm=Decimal("0.02"),quantidade=10,status="aberta")); banco.flush()
            banco.add(CotacaoFornecedor(id=cid,solicitacao_id=cid,empresa_fornecedora_id=fornecedor,
                valor_total=Decimal("12500.00"),prazo_dias=15,validade_dias=10,status="aceita")); banco.flush()
            banco.add(ContratacaoServico(id=cid,solicitacao_id=cid,cotacao_id=cid,empresa_cliente_id=cliente,
                empresa_fornecedora_id=fornecedor,valor_total=Decimal("12500.00"),prazo_dias=15,status="ativa")); banco.flush()
            banco.add(OrdemServico(id=cid,contratacao_id=cid,solicitacao_id=cid,cotacao_id=cid,empresa_cliente_id=cliente,
                empresa_fornecedora_id=fornecedor,processo_id=1,material_id=1,quantidade=10,
                valor_total=Decimal("12500.00"),prazo_dias=15,status="concluida")); banco.flush()
            banco.add(CicloIntermediacao(ordem_servico_id=cid,status="entregue_cliente",versao=8,
                criado_em="2026-10-05T12:00:00Z",atualizado_em="2026-10-05T12:00:00Z"))
        banco.commit()
    arquivo = tmp_path / "acessos.db"; shutil.copy2(contas_d32, arquivo)
    app = criar_aplicacao(); app.state.caminho_acessos = arquivo
    def banco_teste():
        with sessoes() as banco: yield banco
    app.dependency_overrides[obter_banco] = banco_teste
    assert autorizar_requisicao not in app.dependency_overrides
    http = TestClient(app)
    try: yield http, sessoes, app
    finally: http.close(); app.dependency_overrides.clear(); engine.dispose()


def entrar(http, perfil="admin"):
    r = http.post("/api/v1/autenticacao/entrar", json={"email":perfil+"@d32.local","senha":SENHA})
    assert r.status_code == 200, r.text
    http.headers["X-MEC-CSRF"] = r.json()["csrf"]


def iniciar(http, cid=1):
    r = http.post(f"{BASE}/{cid}/iniciar", json={"registro_interno":INTERNO})
    assert r.status_code == 201, r.text
    return r.json()


def corpo(acao="recebimento", versao=1, **extras):
    dados = {"acao":acao,"versao":versao,"chave_operacao":str(uuid4()),"registro_interno":INTERNO}
    if acao in {"recebimento","repasse"}: dados.update(valor="12500.00",forma_pagamento="pix",referencia="PROVA-"+str(uuid4()))
    elif acao.startswith("estornar_"): dados.update(movimento_id=1,referencia="ESTORNO-"+str(uuid4()))
    return {**dados,**extras}


def registrar(http, dados, cid=1, esperado=201):
    r = http.post(f"{BASE}/{cid}/eventos", json=dados)
    assert r.status_code == esperado, r.text
    return r


def pronto(http):
    iniciar(http); registrar(http,corpo()); registrar(http,corpo("repasse",2))


def test_exige_sessao_admin_csrf_e_identidade_servidor(ambiente_d32):
    http,_,_=ambiente_d32
    assert http.get(BASE).status_code == 401
    for perfil in ("cliente","fornecedor"):
        entrar(http,perfil)
        assert http.get(BASE).status_code == 403
        assert http.post(BASE+"/1/iniciar",json={"registro_interno":INTERNO}).status_code == 403
    entrar(http)
    assert http.post(BASE+"/1/iniciar",json={"registro_interno":INTERNO},headers={"X-MEC-CSRF":"falso"}).status_code==403
    assert http.post(BASE+"/1/iniciar",json={"registro_interno":INTERNO,"usuario_admin_id":999}).status_code==422


def test_inicio_aproveita_pagamentos_antigos_sem_alterar(ambiente_d32):
    http,sessoes,_=ambiente_d32
    with sessoes() as banco:
        antigo=PagamentoContratacao(contratacao_id=1,empresa_cliente_id=2,empresa_fornecedora_id=4,
            valor=Decimal("5000.13"),forma_pagamento="pix",status="confirmado",observacoes=INTERNO)
        cancelado=PagamentoContratacao(contratacao_id=1,empresa_cliente_id=2,empresa_fornecedora_id=4,
            valor=Decimal("3000.00"),forma_pagamento="pix",status="cancelado",observacoes=INTERNO)
        banco.add_all([antigo,cancelado]); banco.commit()
        valores=[(p.id,p.valor,p.status,p.observacoes) for p in (antigo,cancelado)]
    entrar(http); r=iniciar(http)
    assert r["resumo"]["total_recebido"]=="5000.13" and r["resumo"]["saldo_cliente"]=="7499.87"
    assert len(r["recebimentos"])==2 and len(r["historico"])==1
    with sessoes() as banco:
        assert [(p.id,p.valor,p.status,p.observacoes) for p in banco.scalars(select(PagamentoContratacao))]==valores
    assert http.post(BASE+"/1/iniciar",json={"registro_interno":INTERNO}).status_code==409


def test_recebimentos_parciais_exatos_e_resumo_d12(ambiente_d32):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http)
    registrar(http,corpo(valor="0.13")); r=registrar(http,corpo(versao=2,valor="12499.87"))
    assert r.json()["resumo"]["total_recebido"]=="12500.00" and r.json()["resumo"]["saldo_cliente"]=="0.00"
    antigo=http.get("/api/v1/contratacoes/1/financeiro").json()
    assert Decimal(str(antigo["total_pago"]))==Decimal("12500.00")
    registrar(http,corpo(versao=3,valor="0.01"),esperado=409)
    with sessoes() as banco: assert banco.scalar(select(func.count()).select_from(PagamentoContratacao))==2


@pytest.mark.parametrize("valor",["0","-1","1.001","NaN","Infinity","1000000000000.00"])
def test_rejeita_valores_invalidos_sem_movimentar(ambiente_d32,valor):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http)
    registrar(http,corpo(valor=valor),esperado=422)
    with sessoes() as banco: assert banco.scalar(select(func.count()).select_from(PagamentoContratacao))==0


def test_idempotencia_referencia_e_versao(ambiente_d32):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http)
    dados=corpo(valor="5000.00"); registrar(http,dados); r=registrar(http,dados)
    assert r.json()["resumo"]["versao"]==2 and r.json()["resumo"]["total_recebido"]=="5000.00"
    registrar(http,{**dados,"valor":"4000.00"},esperado=409)
    registrar(http,corpo(versao=2,valor="5000.00",referencia=dados["referencia"]),esperado=409)
    registrar(http,corpo(versao=1,valor="5000.00"),esperado=409)
    with sessoes() as banco:
        assert banco.scalar(select(func.count()).select_from(PagamentoContratacao))==1
        assert banco.scalar(select(func.count()).select_from(EventoFinanceiro))==2


@pytest.mark.parametrize("status",[None,"aprovado_para_entrega","em_avaliacao","cancelado"])
def test_repasse_exige_entrega_final_d31(ambiente_d32,status):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http); registrar(http,corpo())
    with sessoes() as banco:
        ciclo=banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==1))
        if status is None:banco.delete(ciclo)
        else:ciclo.status=status
        banco.commit()
    registrar(http,corpo("repasse",2),esperado=409)


def test_repasse_exige_os_concluida_e_fundos(ambiente_d32):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http)
    registrar(http,corpo("repasse"),esperado=409)
    registrar(http,corpo(valor="5000.00"))
    registrar(http,corpo("repasse",2,valor="5000.01"),esperado=409)
    with sessoes() as banco: banco.get(OrdemServico,1).status="em_execucao"; banco.commit()
    registrar(http,corpo("repasse",2,valor="5000.00"),esperado=409)
    with sessoes() as banco: banco.get(OrdemServico,1).status="concluida"; banco.commit()
    r=registrar(http,corpo("repasse",2,valor="5000.00"))
    assert r.json()["resumo"]["total_repassado"]=="5000.00" and r.json()["resumo"]["disponivel_repasse"]=="0.00"


def test_estornos_preservam_registros_e_cobertura(ambiente_d32):
    http,sessoes,_=ambiente_d32; entrar(http); pronto(http)
    registrar(http,corpo("estornar_recebimento",3),esperado=409)
    r=registrar(http,corpo("estornar_repasse",3)); assert r.json()["resumo"]["saldo_fornecedor"]=="12500.00"
    registrar(http,corpo("estornar_repasse",4),esperado=409)
    r=registrar(http,corpo("estornar_recebimento",4)); assert r.json()["resumo"]["saldo_cliente"]=="12500.00"
    with sessoes() as banco:
        assert banco.get(PagamentoContratacao,1).status=="cancelado"
        assert banco.get(RepasseAdministrativo,1).status=="estornado"
        assert banco.scalar(select(func.count()).select_from(EventoFinanceiro))==5


def test_movimento_de_outra_contratacao_nao_e_estornado(ambiente_d32):
    http,_,_=ambiente_d32; entrar(http); iniciar(http,1); iniciar(http,2)
    registrar(http,corpo(),cid=2)
    registrar(http,corpo("estornar_recebimento"),cid=1,esperado=404)


def test_encerrar_reabrir_sem_apagar_os_ou_auditoria(ambiente_d32):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http)
    registrar(http,corpo("encerrar"),esperado=409)
    registrar(http,corpo()); registrar(http,corpo("repasse",2))
    encerramento=corpo("encerrar",3); r=registrar(http,encerramento)
    assert r.json()["resumo"]["status"]=="encerrado" and r.json()["resumo"]["contratacao_status"]=="encerrada"
    registrar(http,encerramento)
    registrar(http,corpo("estornar_repasse",4),esperado=409)
    r=registrar(http,corpo("reabrir",4)); assert r.json()["resumo"]["contratacao_status"]=="ativa"
    registrar(http,corpo("estornar_repasse",5))
    with sessoes() as banco:
        assert banco.get(OrdemServico,1).status=="concluida"
        assert banco.scalar(select(func.count()).select_from(EventoFinanceiro))==6


def test_rotas_antigas_nao_alteram_financeiro_administrado(ambiente_d32):
    http,_,_=ambiente_d32; entrar(http); iniciar(http); registrar(http,corpo(valor="5000.00"))
    assert http.post("/api/v1/contratacoes/1/pagamentos",json={"empresa_cliente_id":2,"valor":"1.00","forma_pagamento":"pix"}).status_code==409
    assert http.post("/api/v1/contratacoes/pagamentos/1/cancelar",json={"empresa_cliente_id":2}).status_code==409
    assert http.post("/api/v1/solicitacoes-servico/1/contratacao/cancelar",json={"empresa_cliente_id":2}).status_code==409


def test_portais_isolam_empresas_e_ocultam_dados_internos(ambiente_d32):
    http,_,_=ambiente_d32; entrar(http); pronto(http)
    for perfil,empresa in (("cliente",2),("fornecedor",4)):
        entrar(http,perfil); base=f"/api/v1/portal-{perfil}/financeiro"; params={"empresa_"+("cliente" if perfil=="cliente" else "fornecedora")+"_id":empresa}
        r=http.get(base,params=params); assert r.status_code==200 and r.json()["total"]==1
        d=http.get(base+"/1",params=params); assert d.status_code==200
        dados=d.json(); assert dados["total_confirmado"]=="12500.00" and len(dados["movimentos"])==1
        assert dados["movimentos"][0]["tipo"]==("recebimento" if perfil=="cliente" else "repasse")
        for segredo in (INTERNO,"Operador reservado","Empresa secreta","referencia","administrador_nome","usuario_admin_id","total_recebido","total_repassado"):
            assert segredo not in d.text
        assert d.headers["cache-control"]=="no-store"
        assert http.get(base+"/2",params=params).status_code==404
        assert http.get(base).status_code==403
        assert http.get(base,params={k:999 for k in params}).status_code==403
        assert http.post(BASE+"/1/eventos",json=corpo()).status_code==403


def test_concorrencia_aplica_somente_uma_versao(ambiente_d32):
    http,sessoes,app=ambiente_d32; entrar(http); iniciar(http)
    with sessoes() as banco:
        from backend.app.core.armazenamento_acesso import COOKIE_SESSAO
        usuario=ArmazenamentoAcesso(app.state.caminho_acessos).obter_sessao(http.cookies.get(COOKIE_SESSAO))
    barreira=Barrier(2)
    def gravar(_):
        from fastapi import HTTPException
        with sessoes() as banco:
            barreira.wait()
            try: ServicoFinanceiroAdministrativo(banco).registrar(1,RegistroFinanceiro(**corpo(valor="8000.00")),usuario); return 201
            except HTTPException as e:return e.status_code
    with ThreadPoolExecutor(max_workers=2) as executor: assert sorted(executor.map(gravar,[1,2]))==[201,409]
    r=http.get(BASE+"/1").json(); assert r["resumo"]["total_recebido"]=="8000.00" and len(r["recebimentos"])==1


def test_limites_pagina_e_valor_contratado_divergente(ambiente_d32):
    http,sessoes,_=ambiente_d32; entrar(http); iniciar(http)
    assert http.get(BASE,params={"limite":101}).status_code==422
    assert http.get(BASE,params={"limite":1}).json()["total"]==2
    with sessoes() as banco:banco.get(ContratacaoServico,1).valor_total=10000; banco.commit()
    registrar(http,corpo(valor="1.00"),esperado=409)
