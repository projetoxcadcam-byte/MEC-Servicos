"""D57: consultas das janelas com sessões reais, arquivos e histórico preservados."""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select, text

from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload, liberar
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.services.portal_fornecedor import ServicoPortalFornecedor

pytestmark = pytest.mark.acesso_real

def estado(sessoes):
    with sessoes() as b:
        nomes=b.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")).scalars().all()
        return {n: sorted([repr(tuple(r)) for r in b.execute(text('SELECT * FROM "'+n+'"'))]) for n in nomes}

def vencida(sessoes):
    with sessoes() as b:
        b.add(CotacaoFornecedor(id=9,solicitacao_id=3,empresa_fornecedora_id=4,valor_total='1800.00',prazo_dias=7,
            validade_dias=1,status='enviada',criada_em=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=10)))
        b.commit()

def cotacoes(http, **params):
    return http.get(BASE+'/portal-fornecedor/cotacoes',params={'empresa_fornecedora_id':4,'somente_leitura':True,**params})

def test_central_arquivos_exibe_vencimento_sem_gravar_ou_notificar(ambiente):
    http,_,sessoes,_=ambiente;vencida(sessoes);entrar(http,'fornecedor');antes=estado(sessoes)
    r=cotacoes(http,solicitacao_id=3);assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store'
    assert r.json()['total']==1 and r.json()['itens'][0]['status']=='expirada'
    assert r.json()['itens'][0]['solicitacao']['cliente_razao_social']=='Cliente C-0002'
    assert 'Contato privado' not in r.text and 'Razao Privada' not in r.text
    assert estado(sessoes)==antes
    with sessoes() as b:
        q=b.get(CotacaoFornecedor,9);assert q.status=='enviada' and q.encerrada_em is None

def test_modo_anterior_de_cotacoes_mantem_vencimento_registrado(ambiente):
    http,_,sessoes,_=ambiente;vencida(sessoes);entrar(http,'fornecedor')
    r=http.get(BASE+'/portal-fornecedor/cotacoes',params={'empresa_fornecedora_id':4,'solicitacao_id':3})
    assert r.status_code==200 and r.json()['itens'][0]['status']=='expirada'
    with sessoes() as b:assert b.get(CotacaoFornecedor,9).status=='expirada'

def test_servico_somente_leitura_nao_deixa_alteracoes_pendentes(ambiente):
    _,_,sessoes,_=ambiente;vencida(sessoes);antes=estado(sessoes)
    with sessoes() as b:
        pagina=ServicoPortalFornecedor(b).listar_cotacoes(4,0,20,somente_leitura=True)
        assert next(q for q in pagina.itens if q.id==9).status=='expirada'
        assert not b.dirty and not b.new and not b.deleted
        b.commit()
    assert estado(sessoes)==antes

def test_todas_paginas_de_documentos_mantem_totais_sem_alterar_propostas(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as b:
        for i in range(100,125):
            b.add(SolicitacaoServico(id=i,empresa_cliente_id=2,processo_id=1,material_id=1,dimensao_x_maxima_mm=10,
                dimensao_y_maxima_mm=10,dimensao_z_maxima_mm=10,tolerancia_requerida_mm='0.02',quantidade=1));b.flush()
            b.add(CotacaoFornecedor(id=i,solicitacao_id=i,empresa_fornecedora_id=4,valor_total='100.00',prazo_dias=2,validade_dias=1,status='enviada',
                criada_em=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=5)))
        b.commit()
    entrar(http,'fornecedor');antes=estado(sessoes)
    p1=cotacoes(http,deslocamento=0,limite=20).json();p2=cotacoes(http,deslocamento=20,limite=20).json()
    assert p1['total']==p2['total']==27 and len(p1['itens'])==20 and len(p2['itens'])==7
    assert len({q['id'] for q in p1['itens']+p2['itens']})==27
    assert estado(sessoes)==antes

@pytest.mark.parametrize('perfil',[None,'cliente'])
def test_documentos_fornecedor_exigem_sessao_do_perfil_correto(ambiente,perfil):
    http,_,sessoes,_=ambiente
    if perfil:entrar(http,perfil)
    antes=estado(sessoes);r=cotacoes(http)
    assert r.status_code==(403 if perfil else 401)
    assert 'itens' not in r.text and estado(sessoes)==antes

def test_central_arquivos_nao_troca_empresa_com_query_ou_cabecalho(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'fornecedor');antes=estado(sessoes)
    r=cotacoes(http,empresa_fornecedora_id=8);assert r.status_code==403
    r=http.get(BASE+'/portal-fornecedor/cotacoes',params={'empresa_fornecedora_id':8,'somente_leitura':True},headers={'X-Perfil':'admin'})
    assert r.status_code==403 and 'itens' not in r.text
    assert estado(sessoes)==antes

def test_filtros_da_central_de_documentos_validados(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'fornecedor');antes=estado(sessoes)
    for params in ({'somente_leitura':'talvez'},{'solicitacao_id':0},{'deslocamento':-1},{'limite':101}):
        assert cotacoes(http,**params).status_code==422
    assert estado(sessoes)==antes

def test_download_da_janela_respeita_liberacao_e_bloqueio(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http);liberar(http,a);entrar(http,'fornecedor');antes=estado(sessoes)
    lista=http.get(BASE+'/portal-fornecedor/solicitacoes/3/arquivos',params={'empresa_fornecedora_id':4})
    assert lista.status_code==200 and [v['id'] for v in lista.json()]==[a['id']]
    r=http.get(BASE+f"/portal-fornecedor/arquivos/{a['id']}/download",params={'empresa_fornecedora_id':4})
    assert r.status_code==200 and r.content.startswith(b'%PDF')
    assert 'privado' not in lista.text and 'privado' not in r.headers['content-disposition']
    assert estado(sessoes)==antes
    liberar(http,a,acao='bloquear',versao=1);entrar(http,'fornecedor');antes=estado(sessoes)
    assert http.get(BASE+'/portal-fornecedor/solicitacoes/3/arquivos',params={'empresa_fornecedora_id':4}).status_code==403
    assert http.get(BASE+f"/portal-fornecedor/arquivos/{a['id']}/download",params={'empresa_fornecedora_id':4}).status_code==403
    assert estado(sessoes)==antes

def test_producao_administrativa_lista_e_historico_sem_gravar(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as b:
        b.add_all([EtapaProducao(id=10,ordem_servico_id=4,empresa_fornecedora_id=4,etapa='aguardando_material',observacoes='Material em preparação'),
                   EtapaProducao(id=11,ordem_servico_id=4,empresa_fornecedora_id=4,etapa='em_usinagem',observacoes='Usinagem iniciada')]);b.commit()
    entrar(http,'admin');antes=estado(sessoes)
    r=http.get(BASE+'/administracao/ordens-servico',params={'ordem_servico_id':4});assert r.status_code==200,r.text
    assert r.json()['total']==1 and r.json()['itens'][0]['ordem_servico_id']==4
    r=http.get(BASE+'/ordens-servico/4/acompanhamento-producao');assert r.status_code==200
    assert r.json()['etapa_atual']=='em_usinagem' and [e['id'] for e in r.json()['historico']]==[10,11]
    assert r.json()['historico'][1]['observacoes']=='Usinagem iniciada'
    assert estado(sessoes)==antes

@pytest.mark.parametrize('perfil',[None,'cliente','fornecedor'])
def test_janela_producao_administrativa_bloqueia_outros_perfis(ambiente,perfil):
    http,_,sessoes,_=ambiente
    if perfil:entrar(http,perfil)
    antes=estado(sessoes)
    for caminho in ('/administracao/ordens-servico','/ordens-servico/4/acompanhamento-producao'):
        r=http.get(BASE+caminho,headers={'X-Perfil':'admin'});assert r.status_code==(403 if perfil else 401)
        assert 'historico' not in r.text and 'itens' not in r.text
    assert estado(sessoes)==antes

def test_producao_sem_etapa_preserva_historico_vazio(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'admin');antes=estado(sessoes)
    r=http.get(BASE+'/ordens-servico/4/acompanhamento-producao');assert r.status_code==200
    assert r.json()['etapa_atual'] is None and r.json()['historico']==[]
    assert http.get(BASE+'/ordens-servico/9999/acompanhamento-producao').status_code==404
    assert estado(sessoes)==antes
