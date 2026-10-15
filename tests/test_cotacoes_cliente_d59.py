"""D59: contagens e consulta do cliente independentes da decisão administrativa."""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import event, select
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_janelas_d57 import estado
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico

pytestmark=pytest.mark.acesso_real
API=BASE+'/portal-cliente/cotacoes'


def consulta(http, **params):
    return http.get(API,params={'empresa_cliente_id':2,**params})


def propostas(sessoes, quantidade=25):
    with sessoes() as b:
        for i in range(100,100+quantidade):
            b.add(SolicitacaoServico(id=i,empresa_cliente_id=2,processo_id=1,material_id=1,dimensao_x_maxima_mm=10,
                dimensao_y_maxima_mm=10,dimensao_z_maxima_mm=10,tolerancia_requerida_mm='0.02',quantidade=1));b.flush()
            b.add(CotacaoFornecedor(id=i,solicitacao_id=i,empresa_fornecedora_id=4,valor_total=str(100+(i%3)),prazo_dias=2+(i%4),
                validade_dias=10,status='enviada',observacoes='Contato fornecedor privado'))
        b.commit()


def test_conta_propostas_validas_sem_permitir_decisao_e_sem_limitar_a_pagina(ambiente):
    http,_,sessoes,_=ambiente;propostas(sessoes);u=entrar(http,'cliente').json()['usuario'];antes=estado(sessoes)
    r=consulta(http);assert r.status_code==200,r.text;p=r.json()
    assert p['contexto']==f"{u['usuario_id']}:cliente:2"
    assert p['total']==27 and p['por_status']=={'aceita':2,'enviada':25} and len(p['itens'])==20
    assert [c['id'] for c in p['itens']]==list(range(124,104,-1))
    p2=consulta(http,deslocamento=20).json();assert p2['total']==27 and len(p2['itens'])==7
    assert len({c['id'] for c in p['itens']+p2['itens']})==27
    painel=http.get(BASE+'/portal-cliente/painel',params={'empresa_cliente_id':2}).json()
    assert painel['cotacoes']=={'total':p['total'],'por_status':p['por_status']}
    assert r.headers['cache-control']=='no-store' and r.headers['x-content-type-options']=='nosniff'
    for palavra in ['Contato fornecedor privado','Razao Privada','ranking','media','observacoes','registro_interno','email','documento']:
        assert palavra not in r.text
    assert estado(sessoes)==antes


def test_busca_encontra_solicitacao_alem_da_primeira_centena(ambiente):
    http,_,sessoes,_=ambiente;propostas(sessoes,105);entrar(http,'cliente');antes=estado(sessoes)
    r=consulta(http,solicitacao_id=204);assert r.status_code==200 and r.json()['total']==1
    assert r.json()['itens'][0]['id']==204 and r.json()['itens'][0]['empresa_cliente_id']==2
    assert consulta(http,cotacao_id=204).json()['total']==1
    assert consulta(http,solicitacao_id=203,cotacao_id=204).json()['total']==0
    assert consulta(http,cotacao_id=2).json()['total']==0
    assert consulta(http,solicitacao_id=2).status_code==404
    assert consulta(http,solicitacao_id=3).json()['total']==0
    assert estado(sessoes)==antes


def test_ordenacao_e_filtro_sao_aplicados_antes_da_paginacao(ambiente):
    http,_,sessoes,_=ambiente;propostas(sessoes);entrar(http,'cliente');antes=estado(sessoes)
    for ordem,campo in [('valor','valor_total'),('prazo','prazo_dias')]:
        a=consulta(http,ordenacao=ordem,limite=20).json();b=consulta(http,ordenacao=ordem,deslocamento=20,limite=20).json()
        itens=a['itens']+b['itens'];valores=[(float(c[campo]),c['id']) for c in itens]
        assert valores==sorted(valores) and len(set(c['id'] for c in itens))==27
    p=consulta(http,situacao='enviada').json();assert p['total']==25 and p['por_status']=={'enviada':25}
    assert consulta(http,situacao='aceita').json()['total']==2
    assert consulta(http,situacao='recusada').json()['total']==0
    assert consulta(http,deslocamento=1000).json()['itens']==[]
    assert estado(sessoes)==antes


def test_vencimento_utc_coerente_em_filtros_contagem_e_detalhe_sem_gravar(ambiente,monkeypatch):
    http,_,sessoes,_=ambiente;agora=datetime(2026,10,13,9,30,tzinfo=timezone.utc)
    class Fixa(datetime):
        @classmethod
        def now(cls,tz=None):return agora
    monkeypatch.setattr('backend.app.services.cotacoes_cliente.datetime',Fixa)
    with sessoes() as b:
        b.add(CotacaoFornecedor(id=9,solicitacao_id=3,empresa_fornecedora_id=4,valor_total='12500.00',prazo_dias=10,
            validade_dias=1,status='enviada',criada_em=agora.replace(tzinfo=None)-timedelta(days=1)));b.commit()
    entrar(http,'cliente');antes=estado(sessoes)
    p=consulta(http).json();assert p['por_status']=={'aceita':2,'expirada':1}
    assert consulta(http,situacao='enviada').json()['total']==0
    item=consulta(http,situacao='expirada').json()['itens'][0];assert item['id']==9
    d=http.get(API+'/9',params={'empresa_cliente_id':2}).json()
    assert d['item']==item and item['vencimento_em']=='2026-10-13T09:30:00Z'
    assert item['encerrada_em'] is None and item['valor_total']=='12500.00'
    with sessoes() as b:assert b.get(CotacaoFornecedor,9).status=='enviada'
    assert estado(sessoes)==antes


def test_detalhe_e_vinculos_pertencem_a_mesma_cotacao_da_empresa(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'cliente');antes=estado(sessoes)
    d=http.get(API+'/4',params={'empresa_cliente_id':2});assert d.status_code==200,d.text
    q=d.json()['item'];assert q['id']==q['solicitacao_id']==q['contratacao_id']==q['ordem_servico_id']==4
    assert q['processo_nome']=='Usinagem CNC' and q['material_nome']=='Alumínio 6061'
    assert http.get(API+'/2',params={'empresa_cliente_id':2}).status_code==404
    assert http.get(API+'/999',params={'empresa_cliente_id':2}).status_code==404
    assert http.get(API+'/'+'9'*30,params={'empresa_cliente_id':2}).status_code==422
    assert estado(sessoes)==antes


def test_vinculo_inconsistente_nao_revela_contrato_ou_os_de_outra_empresa(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as b:
        b.get(ContratacaoServico,4).empresa_cliente_id=6;b.get(OrdemServico,4).empresa_cliente_id=6;b.commit()
    entrar(http,'cliente');antes=estado(sessoes)
    q=http.get(API+'/4',params={'empresa_cliente_id':2}).json()['item']
    assert q['contratacao_id'] is None and q['ordem_servico_id'] is None
    assert consulta(http).json()['total']==2 and estado(sessoes)==antes


@pytest.mark.parametrize('perfil',[None,'admin','fornecedor'])
def test_consulta_exige_sessao_real_de_cliente(ambiente,perfil):
    http,_,sessoes,_=ambiente
    if perfil:entrar(http,perfil)
    antes=estado(sessoes)
    for caminho in [API,API+'/4']:
        r=http.get(caminho,params={'empresa_cliente_id':2},headers={'X-Perfil':'cliente'})
        assert r.status_code==(401 if perfil is None else 403) and 'valor_total' not in r.text
    assert estado(sessoes)==antes


def test_query_empresa_duplicada_cabecalho_e_contexto_nao_trocam_acesso(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'cliente');antes=estado(sessoes)
    for params in [{'empresa_cliente_id':6},[('empresa_cliente_id',2),('empresa_cliente_id',2)],{}, {'empresa_cliente_id':2,'empresa_id':6}]:
        for caminho in [API,API+'/4']:
            assert http.get(caminho,params=params,headers={'X-Perfil':'admin','X-Empresa-Id':'6'}).status_code==403
    assert http.get(API,params={'empresa_cliente_id':2},headers={'X-MEC-Cotacoes-Contexto':'999:cliente:2'}).status_code==409
    assert estado(sessoes)==antes


@pytest.mark.parametrize('params',[{'solicitacao_id':0},{'cotacao_id':-1},{'solicitacao_id':10**30},{'cotacao_id':10**30},{'limite':101},{'deslocamento':-1},{'deslocamento':1000001},{'situacao':'invalida'},{'ordenacao':'ranking'}])
def test_filtros_invalidos_recusados_sem_gravar(ambiente,params):
    http,_,sessoes,_=ambiente;entrar(http,'cliente');antes=estado(sessoes)
    assert consulta(http,**params).status_code==422
    assert estado(sessoes)==antes


def test_consultar_nao_libera_acoes_comerciais_legadas_ao_cliente(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'cliente');antes=estado(sessoes)
    assert consulta(http).status_code==200
    for acao in ['aceitar','recusar']:
        r=http.post(BASE+'/solicitacoes-servico/4/cotacoes/4/'+acao,json={'empresa_cliente_id':2})
        assert r.status_code==403
    assert estado(sessoes)==antes


def test_selects_nao_aumentam_com_numero_de_propostas(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'cliente');engine=sessoes.kw['bind'];lista=[]
    def contar(c,cur,s,p,ctx,m):
        if s.lstrip().upper().startswith('SELECT'):lista.append(s)
    event.listen(engine,'before_cursor_execute',contar)
    try:
        assert consulta(http).status_code==200;n=len(lista);assert n<=5
        propostas(sessoes,75);lista.clear();assert consulta(http).status_code==200
        assert len(lista)==n
    finally:event.remove(engine,'before_cursor_execute',contar)


def test_totais_e_pagina_coerentes_apos_gravacao_concorrente(ambiente):
    http,_,sessoes,_=ambiente;engine=sessoes.kw['bind'];feito=[]
    with engine.connect() as c:c.exec_driver_sql('PRAGMA journal_mode=WAL')
    entrar(http,'cliente')
    def gravar(c,cur,s,p,ctx,m):
        if not feito and s.startswith('SELECT CASE WHEN'):
            feito.append(True)
            with sessoes() as b:
                b.add(CotacaoFornecedor(id=9,solicitacao_id=3,empresa_fornecedora_id=4,valor_total='1500',prazo_dias=5,validade_dias=10,status='enviada'));b.commit()
    event.listen(engine,'after_cursor_execute',gravar)
    try:
        r=consulta(http);assert r.status_code==200,r.text;p=r.json()
        assert feito and p['total']==2 and len(p['itens'])==2 and all(q['id']!=9 for q in p['itens'])
    finally:event.remove(engine,'after_cursor_execute',gravar)
    assert consulta(http).json()['total']==3
