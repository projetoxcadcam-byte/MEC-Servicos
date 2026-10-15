"""Metas do ADM: precisão, escopo, auditoria, atomicidade e concorrência."""
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from test_relatorio_resultado_d62 import (
    despesas,precificacao,comercial,ambiente,modelo_acessos,entrar,registrar,estornar,
    evento_fin,FIN,DES,estado,ContratacaoServico,DespesaAdministracao,OrdemServico,CicloIntermediacao,
)
from backend.app.models.meta_resultado import ConfiguracaoMetas,MetaResultado,EventoMetaResultado
from backend.app.services.meta_resultado import REVISION,percentual

pytestmark=pytest.mark.acesso_real
METAS=DES+'/metas'
HOJE=datetime.now(timezone.utc).date();MES=HOJE.strftime('%Y-%m');ANO=HOJE.year

@pytest.fixture
def metas(despesas):
    with despesas[2]() as b:b.add(ConfiguracaoMetas(id=1,revision=REVISION,ativada_em=datetime.now(timezone.utc).isoformat()));b.commit()
    return despesas

def detalhe(http,mes=MES,**kw):
    r=http.get(METAS+'/'+mes,params=kw);assert r.status_code==200,r.text;return r.json()

def comparar(http,ano=ANO):
    r=http.get(METAS,params={'ano':ano});assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store' and r.headers['x-mec-despesas-contexto']==r.json()['contexto']
    return r.json()

def corpo(http,mes=MES,**kw):
    return {'acao':'definir','valor':'1500.00','versao':detalhe(http,mes)['versao'],'chave_operacao':str(uuid4()),'registro_interno':'Planejamento reservado D64.',**kw}

def definir(http,mes=MES,**kw):return http.post(METAS+'/'+mes,json=corpo(http,mes,**kw))

def retirar(http,mes=MES):return http.post(METAS+'/'+mes,json=corpo(http,mes,acao='retirar',valor=None,registro_interno='Retirada reservada D64.'))

def liquidar(http,sessoes,cid):
    with sessoes() as b:
        o=b.scalar(select(OrdemServico).where(OrdemServico.contratacao_id==cid));o.status='concluida'
        b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==o.id)).status='entregue_cliente';b.commit()
    assert http.post(FIN+f'/{cid}/iniciar',json={'registro_interno':'Controle D64 teste'}).status_code==201
    assert evento_fin(http,cid,'recebimento',valor='1800.00').status_code==201
    assert evento_fin(http,cid,'repasse',valor='1500.00').status_code==201

def mes_da(comp,mes=MES):return next(m for m in comp['meses'] if m['mes']==mes)

def exportar(http,r):return http.get(METAS+'/csv',params={'ano':r['ano'],'versao':r['versao']})

def linhas(r):
    assert r.status_code==200,r.text;assert r.content.startswith(b'\xef\xbb\xbf')
    return list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig')),delimiter=';'))

def test_sem_meta_meta_zero_definir_alterar_retirar_e_historico(metas):
    http,_,sessoes,_,cid=metas;antes=estado(sessoes)
    r=comparar(http);assert r['meses_com_meta']==0 and r['meta_total'] is None and r['atingimento_total_percentual'] is None
    assert len(r['meses'])==12 and mes_da(r)['situacao']=='sem_meta'
    assert definir(http,valor='0.00').status_code==200
    r=comparar(http);m=mes_da(r);assert m['meta']=='0.00' and m['situacao']=='meta_zero' and m['atingimento_percentual'] is None
    assert definir(http,valor='1500.01').status_code==200
    r=comparar(http);m=mes_da(r);assert m['diferenca']=='-1500.01' and m['atingimento_percentual']=='0.00'
    assert r['totais']['resultado_apos_despesas']=='300.00' and r['realizado_com_meta']=='0.00'
    assert definir(http,valor='1500.01').status_code==409
    assert retirar(http).status_code==200 and retirar(http).status_code==409
    d=detalhe(http);assert d['meta']['estado']=='retirada' and d['meta']['valor']=='1500.01'
    assert d['total_eventos']==3 and [e['acao'] for e in d['historico']]==['retirar','definir','definir']
    assert d['historico'][0]['valor_anterior']=='1500.01' and d['historico'][0]['valor_atual'] is None
    assert definir(http,valor='2500').status_code==200
    assert detalhe(http)['historico'][0]['valor_anterior'] is None
    depois=estado(sessoes)
    for k,v in antes.items():
        if k not in {'metas_resultado_administracao','eventos_metas_resultado'}:assert depois[k]==v,k

def test_resultado_liquidado_percentuais_negativos_e_despesa_posterior(metas):
    http,_,sessoes,_,cid=metas
    assert definir(http,valor='200.00').status_code==200
    liquidar(http,sessoes,cid)
    r=comparar(http);m=mes_da(r);assert m['atingimento_percentual']=='150.00' and m['diferenca']=='100.00' and m['situacao']=='alcancada'
    d=registrar(http,cid,valor='400.01').json()
    r=comparar(http);m=mes_da(r);assert m['totais']['resultado_liquidado_apos_despesas']=='-100.01'
    assert m['atingimento_percentual']=='-50.01' and m['diferenca']=='-300.01' and m['situacao']=='abaixo'
    assert m['totais']['resultado_previsto']=='250.00'
    assert estornar(http,cid,d['despesa_id']).status_code==200
    assert mes_da(comparar(http))['atingimento_percentual']=='150.00'
    with sessoes() as b:b.get(ContratacaoServico,cid).criada_em=datetime(2026,6,30,23,59,59);b.commit()
    assert definir(http,mes='2026-06',valor='100.00').status_code==200
    m=mes_da(comparar(http,2026),'2026-06');assert m['totais']['resultado_liquidado_apos_despesas']=='300.00'
    assert registrar(http,cid,valor='50.01').status_code==200
    m=mes_da(comparar(http,2026),'2026-06');assert m['totais']['resultado_liquidado_apos_despesas']=='249.99' and m['atingimento_percentual']=='249.99'
    assert percentual(-1,200)=='-0.50' and percentual(1,300)=='0.33' and percentual(1,0) is None

def test_totais_so_comparam_meses_com_meta_e_csv_exato(metas):
    http,_,sessoes,_,cid=metas;liquidar(http,sessoes,cid)
    outro=f'{ANO}-01' if MES!=f'{ANO}-01' else f'{ANO}-02'
    assert definir(http,mes=outro,valor='100.01').status_code==200
    r=comparar(http);assert r['totais']['resultado_liquidado_apos_despesas']=='300.00' and r['realizado_com_meta']=='0.00'
    assert r['meta_total']=='100.01' and r['diferenca_total']=='-100.01' and r['atingimento_total_percentual']=='0.00'
    assert definir(http,valor='200.00').status_code==200
    r=comparar(http);assert r['meses_com_meta']==2 and r['meta_total']=='300.01' and r['realizado_com_meta']=='300.00'
    assert r['diferenca_total']=='-0.01' and r['atingimento_total_percentual']=='100.00'
    antes=estado(sessoes);dados=linhas(exportar(http,r));assert len(dados)==13
    assert dados[0]['Meta (R$)']=='300,01' and dados[0]['Diferença da meta (R$)']=='-0,01'
    sem=next(d for d in dados[1:] if d['Situação']=='Sem meta');assert sem['Meta (R$)']==sem['Atingimento (%)']==''
    assert estado(sessoes)==antes

def test_versao_idempotencia_mes_divergente_e_exportacao_antiga(metas):
    http,_,sessoes,_,cid=metas;comparacao=comparar(http);d=corpo(http)
    r=http.post(METAS+'/'+MES,json=d);assert r.status_code==200
    antes=estado(sessoes);assert http.post(METAS+'/'+MES,json=d).json()==r.json() and estado(sessoes)==antes
    assert http.post(METAS+'/'+MES,json={**d,'valor':'1501.00'}).status_code==409
    assert http.post(METAS+'/'+MES,json={**d,'chave_operacao':str(uuid4())}).status_code==409
    outro=f'{ANO+1}-01';assert http.post(METAS+'/'+outro,json={**d,'chave_operacao':str(uuid4())}).status_code==409
    assert exportar(http,comparacao).status_code==409
    r=comparar(http);assert comparar(http)['versao']==r['versao']
    assert retirar(http).status_code==200;assert definir(http).status_code==200
    assert exportar(http,r).status_code==409  # mesmo valor, revisão diferente
    r=comparar(http);assert registrar(http,cid).status_code==200;assert exportar(http,r).status_code==409
    assert exportar(http,comparar(http)).status_code==200

def test_sigilo_tres_perfis_csrf_contexto_e_sem_efeitos_financeiros(metas):
    http,_,sessoes,_,cid=metas;d=corpo(http);antes=estado(sessoes)
    csrf=http.headers.pop('X-MEC-CSRF');assert http.post(METAS+'/'+MES,json=d).status_code==403;http.headers['X-MEC-CSRF']=csrf
    assert http.post(METAS+'/'+MES,json=d,headers={'Origin':'https://outro.local'}).status_code==403
    assert http.get(METAS,params={'ano':ANO},headers={'X-MEC-Despesas-Contexto':'999:admin:0'}).status_code==409
    assert definir(http).status_code==200;comp=comparar(http)
    for perfil in ('cliente','fornecedor'):
        entrar(http,perfil)
        for url,params in ((METAS,{'ano':ANO}),(METAS+'/'+MES,{}),(METAS+'/csv',{'ano':ANO,'versao':comp['versao']})):
            r=http.get(url,params=params,headers={'X-MEC-PERFIL':'admin'});assert r.status_code==403 and 'Planejamento reservado' not in r.text and 'meta_total' not in r.text
        assert http.post(METAS+'/'+MES,json=d).status_code==403
    http.cookies.clear();assert http.get(METAS,params={'ano':ANO}).status_code==401
    entrar(http,'admin')
    depois=estado(sessoes)
    for k,v in antes.items():
        if k not in {'metas_resultado_administracao','eventos_metas_resultado'}:assert depois[k]==v,k

def test_invalidos_nao_gravam_e_ativacao_ausente(despesas):
    http,_,sessoes,_,_=despesas
    assert http.get(METAS,params={'ano':ANO}).status_code==503
    with sessoes() as b:b.add(ConfiguracaoMetas(id=1,revision=REVISION,ativada_em=datetime.now(timezone.utc).isoformat()));b.commit()
    d=corpo(http);antes=estado(sessoes)
    for kw in ({'valor':'-1'},{'valor':'0.001'},{'valor':'NaN'},{'valor':'1000000000000.00'},{'valor':None},
        {'acao':'retirar','valor':'1'},{'acao':'apagar'},{'registro_interno':'  '},{'usuario_admin_id':999}):
        assert http.post(METAS+'/'+MES,json={**d,**kw}).status_code==422,kw
    for mes in ('2026-00','2026-13','2026-1','1899-12','9999-01'):
        assert http.get(METAS+'/'+mes).status_code==422,mes
    for params in ({'ano':1899},{'ano':9999},{'ano':ANO,'cliente':2},[('ano',ANO),('ano',ANO)]):assert http.get(METAS,params=params).status_code==422
    assert http.get(METAS+'/'+MES,params={'limite':0}).status_code==422
    assert http.get(METAS+'/csv',params={'ano':ANO,'versao':'invalida'}).status_code==422
    assert estado(sessoes)==antes

def test_concorrencia_mesma_versao_e_rollback_da_auditoria(metas):
    http,_,sessoes,app,_=metas;d=corpo(http);cookies=dict(http.cookies);headers=dict(http.headers)
    def enviar(i):
        h=TestClient(app)
        try:
            h.cookies.update(cookies);h.headers.update(headers)
            return h.post(METAS+'/'+MES,json={**d,'valor':str(1500+i),'chave_operacao':str(uuid4())})
        finally:h.close()
    with ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(enviar,range(2)))
    assert sorted(x.status_code for x in r)==[200,409]
    with sessoes() as b:assert len(b.scalars(select(MetaResultado)).all())==len(b.scalars(select(EventoMetaResultado)).all())==1
    d=corpo(http,valor='2500.00');antes=estado(sessoes)
    def falhar(*a):raise IntegrityError('teste',{},Exception('Auditoria isolada recusada'))
    event.listen(EventoMetaResultado,'before_insert',falhar)
    try:
        with pytest.raises(IntegrityError):http.post(METAS+'/'+MES,json=d)
    finally:event.remove(EventoMetaResultado,'before_insert',falhar)
    assert estado(sessoes)==antes

def test_historico_paginado_leitura_pura_e_snapshot_de_metas(metas):
    http,_,sessoes,_,_=metas
    for v in range(23):assert definir(http,valor=str(v)).status_code==200
    d=detalhe(http,deslocamento=20,limite=3);assert d['total_eventos']==23 and len(d['historico'])==3
    assert [e['versao'] for e in d['historico']]==[3,2,1]
    antes=estado(sessoes);r=comparar(http);assert r['meta_total']=='22.00';assert exportar(http,r).status_code==200 and estado(sessoes)==antes
    engine=sessoes.kw['bind']
    with engine.connect() as cx:cx.exec_driver_sql('PRAGMA journal_mode=WAL')
    feito=[]
    def mudar(cx,cur,sql,params,ctx,muitos):
        if not feito and sql.startswith('SELECT contratacoes_servico.id') and 'sum(despesas_administracao.valor_centavos)' in sql:
            feito.append(True)
            with sessoes() as b:b.get(MetaResultado,MES).valor_centavos=2300;b.commit()
    event.listen(engine,'after_cursor_execute',mudar)
    try:r=comparar(http)
    finally:event.remove(engine,'after_cursor_execute',mudar)
    assert feito and r['meta_total']=='22.00';assert comparar(http)['meta_total']=='23.00'
