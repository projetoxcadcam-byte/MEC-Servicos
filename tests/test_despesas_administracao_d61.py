"""Despesas reais: sigilo, valores exatos, auditoria, concorrência e resultado."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event,select
from sqlalchemy.exc import IntegrityError
from test_formacao_preco_d60 import precificacao,comercial,ambiente,modelo_acessos,entrar,publicar,aprovar,contratar,resultado,evento_fin,BASE,FIN
from test_janelas_d57 import estado
from backend.app.models.despesa_administracao import ConfiguracaoDespesas,DespesaAdministracao,EventoDespesaAdministracao
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.services.despesa_administracao import REVISION

pytestmark=pytest.mark.acesso_real
DES=BASE+'/administracao/despesas'
@pytest.fixture
def despesas(precificacao):
    http,_,sessoes,_=precificacao
    with sessoes() as b:b.add(ConfiguracaoDespesas(id=1,revision=REVISION,ativada_em=datetime.now(timezone.utc).isoformat()));b.commit()
    publicar(http);assert aprovar(http).status_code==200;c=contratar(http)
    return (*precificacao,c['contratacao_id'])
def obter(http,cid,**kw):
    r=http.get(DES+f'/contratacoes/{cid}',params=kw);assert r.status_code==200,r.text;return r.json()
def corpo(http,cid,**kw):
    return {'versao':obter(http,cid)['versao'],'chave_operacao':str(uuid4()),'categoria':'coleta','descricao':'Coleta teste interno D61','valor':'50.00',
        'paga_em':str(datetime.now(timezone.utc).date()),'referencia':'COMPROVANTE-RESERVADO-D61','registro_interno':'DESPESA-RESERVADA-D61 conferida.',**kw}
def registrar(http,cid,**kw):return http.post(DES+f'/contratacoes/{cid}',json=corpo(http,cid,**kw))
def estornar(http,cid,did,**kw):
    d={'versao':obter(http,cid)['versao'],'chave_operacao':str(uuid4()),'referencia':'ESTORNO-RESERVADO-D61','registro_interno':'Correção da despesa interna.',**kw}
    return http.post(DES+f'/contratacoes/{cid}/despesas/{did}/estornar',json=d)
def resultado_d61(http,**kw):
    hoje=datetime.now(timezone.utc).date();return http.get(DES+'/resultado',params={'inicio':str(hoje-timedelta(days=1)),'fim':str(hoje+timedelta(days=1)),**kw})

def test_registrar_estornar_sem_modificar_negocio_ou_previsao(despesas):
    http,_,sessoes,_,cid=despesas;antes=estado(sessoes)
    r=registrar(http,cid);assert r.status_code==200,r.text
    d=obter(http,cid);assert d['despesas_confirmadas']=='50.00' and d['despesas_previstas']=='50.00' and d['resultado_apos_despesas']=='250.00'
    assert d['itens'][0]['status']=='confirmada' and d['historico'][0]['acao']=='registrar'
    assert estornar(http,cid,r.json()['despesa_id']).status_code==200
    d=obter(http,cid);assert d['despesas_confirmadas']=='0.00' and d['despesas_previstas']=='50.00'
    assert d['itens'][0]['status']=='estornada' and d['itens'][0]['referencia']=='COMPROVANTE-RESERVADO-D61'
    depois=estado(sessoes)
    for k,v in antes.items():
        if k not in {'despesas_administracao','eventos_despesas_administracao'}:assert depois[k]==v,k

@pytest.mark.parametrize('campo,valor',[
 ('valor','0'),('valor','-1'),('valor','0.001'),('valor','NaN'),('valor','Infinity'),('valor','1000000000000.00'),
 ('categoria','sem_categoria'),('paga_em','1899-12-31'),('paga_em','não é data'),('paga_em','9999-01-01'),
 ('referencia','   '),('registro_interno','  '),('descricao',' '),('usuario_admin_id',999),('status','estornada')])
def test_campos_invalidos_nao_gravam(despesas,campo,valor):
    http,_,sessoes,_,cid=despesas;antes=estado(sessoes)
    r=http.post(DES+f'/contratacoes/{cid}',json=corpo(http,cid,**{campo:valor}))
    assert r.status_code in (403,422),r.text
    assert estado(sessoes)==antes

def test_repeticao_e_versao_antiga(despesas):
    http,_,sessoes,_,cid=despesas;d=corpo(http,cid);r=http.post(DES+f'/contratacoes/{cid}',json=d);assert r.status_code==200
    antes=estado(sessoes);assert http.post(DES+f'/contratacoes/{cid}',json=d).json()==r.json();assert estado(sessoes)==antes
    assert http.post(DES+f'/contratacoes/{cid}',json={**d,'valor':'51.00'}).status_code==409
    assert http.post(DES+f'/contratacoes/{cid}',json={**d,'chave_operacao':str(uuid4())}).status_code==409

def test_estorno_unico_e_despesa_de_outra_contratacao_recusada(despesas):
    http,_,_,_,cid=despesas;r=registrar(http,cid);did=r.json()['despesa_id']
    assert http.post(DES+f'/contratacoes/1/despesas/{did}/estornar',json={'versao':'a'*64,'chave_operacao':str(uuid4()),'referencia':'test','registro_interno':'test'}).status_code==409
    assert estornar(http,cid,did).status_code==200
    assert estornar(http,cid,did).status_code==409
    assert estornar(http,cid,999).status_code==404

def test_tres_perfis_csrf_contexto_e_sem_notificacao(despesas):
    http,_,sessoes,_,cid=despesas;d=corpo(http,cid);antes=estado(sessoes)
    t=http.headers.pop('X-MEC-CSRF');assert http.post(DES+f'/contratacoes/{cid}',json=d).status_code==403;http.headers['X-MEC-CSRF']=t
    assert http.post(DES+f'/contratacoes/{cid}',json=d,headers={'Origin':'https://outro.local'}).status_code==403
    assert http.get(DES+f'/contratacoes/{cid}',headers={'X-MEC-Despesas-Contexto':'999:admin:0'}).status_code==409
    assert registrar(http,cid).status_code==200
    assert estado(sessoes)['notificacoes_perfis']==antes['notificacoes_perfis']
    for perfil in ('cliente','fornecedor'):
        entrar(http,perfil)
        for url in (DES+f'/contratacoes/{cid}',DES+'/resultado'):
            r=http.get(url);assert r.status_code==403 and 'COMPROVANTE-RESERVADO' not in r.text
        assert http.post(DES+f'/contratacoes/{cid}',json=d).status_code==403
        params={'empresa_cliente_id':2} if perfil=='cliente' else {'empresa_fornecedora_id':4}
        r=http.get(BASE+f'/portal-{perfil}/financeiro/{cid}',params=params);assert r.status_code==200
        assert 'DESPESA-RESERVADA' not in r.text and 'despesas' not in r.text
    http.cookies.clear();assert http.get(DES+f'/contratacoes/{cid}').status_code==401

def test_concorrencia_mesma_versao_registra_apenas_uma(despesas):
    http,_,sessoes,app,cid=despesas;d=corpo(http,cid);cookies=dict(http.cookies);headers=dict(http.headers)
    def enviar(_):
        h=TestClient(app);h.cookies.update(cookies);h.headers.update(headers)
        try:return h.post(DES+f'/contratacoes/{cid}',json={**d,'chave_operacao':str(uuid4())})
        finally:h.close()
    with ThreadPoolExecutor(max_workers=2) as e:r=list(e.map(enviar,range(2)))
    assert sorted(a.status_code for a in r)==[200,409]
    with sessoes() as b:assert len(b.scalars(select(DespesaAdministracao)).all())==1 and len(b.scalars(select(EventoDespesaAdministracao)).all())==1

def test_falha_auditoria_reverte_despesa(despesas):
    http,_,sessoes,_,cid=despesas;d=corpo(http,cid);antes=estado(sessoes)
    def falhar(*args):raise IntegrityError('teste',{},Exception('falha isolada'))
    event.listen(EventoDespesaAdministracao,'before_insert',falhar)
    try:
        with pytest.raises(IntegrityError):http.post(DES+f'/contratacoes/{cid}',json=d)
    finally:event.remove(EventoDespesaAdministracao,'before_insert',falhar)
    assert estado(sessoes)==antes

def test_resultado_exato_com_prejuizo_liquidacao_e_estorno(despesas):
    http,_,sessoes,_,cid=despesas;r=registrar(http,cid,valor='400.01');assert r.status_code==200,r.text
    d=resultado_d61(http).json();assert d['totais']['despesas_pagas']=='400.01' and d['totais']['resultado_apos_despesas']=='-100.01'
    assert d['totais']['resultado_liquidado_apos_despesas']=='0.00' and not d['itens'][0]['liquidado']
    assert resultado(http).json()['totais']['resultado_previsto']=='250.00'
    with sessoes() as b:
        o=b.scalar(select(OrdemServico).where(OrdemServico.contratacao_id==cid));o.status='concluida'
        c=b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==o.id));c.status='entregue_cliente';b.commit()
    assert http.post(FIN+f'/{cid}/iniciar',json={'registro_interno':'Controle D61 teste'}).status_code==201
    assert evento_fin(http,cid,'recebimento',valor='1800.00').status_code==201
    assert evento_fin(http,cid,'repasse',valor='1500.00').status_code==201
    d=resultado_d61(http).json();assert d['totais']['resultado_liquidado_apos_despesas']=='-100.01'
    assert estornar(http,cid,r.json()['despesa_id']).status_code==200
    assert resultado_d61(http).json()['totais']['resultado_liquidado_apos_despesas']=='300.00'
    with sessoes() as b:
        from backend.app.models.financeiro_administrativo import RepasseAdministrativo
        rep=b.scalar(select(RepasseAdministrativo).where(RepasseAdministrativo.contratacao_id==cid));rid=rep.id
    assert evento_fin(http,cid,'estornar_repasse',movimento_id=rid,referencia='Estorno D61').status_code==201
    assert resultado_d61(http).json()['totais']['resultado_liquidado_apos_despesas']=='0.00'

def test_totais_paginacao_leitura_pura_e_contrato_antigo(despesas):
    http,_,sessoes,_,cid=despesas
    for i in range(3):assert registrar(http,cid,valor='0.01',descricao=f'Despesa paga {i}').status_code==200
    antes=estado(sessoes)
    d=obter(http,cid,limite=1,deslocamento=1);assert d['total']==3 and len(d['itens'])==1 and d['despesas_confirmadas']=='0.03'
    d=resultado_d61(http,limite=1,deslocamento=1).json();assert d['itens']==[] and d['total']==1 and d['totais']['despesas_pagas']=='0.03'
    assert http.get(DES+'/contratacoes/1').status_code==409
    assert http.get(DES+'/contratacoes/999').status_code==404
    assert estado(sessoes)==antes

def test_cancelada_impede_nova_despesa_mas_permite_estorno(despesas):
    http,_,sessoes,_,cid=despesas;r=registrar(http,cid)
    with sessoes() as b:b.get(ContratacaoServico,cid).status='cancelada';b.commit()
    assert not obter(http,cid)['pode_registrar'] and registrar(http,cid).status_code==409
    assert estornar(http,cid,r.json()['despesa_id']).status_code==200

@pytest.mark.parametrize('params',[{'inicio':'2026-10-14','fim':'2026-10-13'},{'inicio':'1900-01-01','fim':'2026-10-13'},{'inicio':'2026-10-13','fim':'9999-12-31'},{'inicio':'2026-10-13','fim':'2026-10-13','limite':0}])
def test_filtros_resultado_invalidos(despesas,params):
    assert despesas[0].get(DES+'/resultado',params=params).status_code==422
