"""D58: totais completos, empresas isoladas e leitura coerente sem gravação."""
from datetime import datetime, timedelta, timezone
import sqlite3
import pytest
from sqlalchemy import event, select

from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_janelas_d57 import estado
from test_documentacao_cotacao_d42 import upload, liberar
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.painel_perfis import ServicoPainelPerfis

pytestmark = pytest.mark.acesso_real


def painel(http, perfil, **kw):
    campo = 'empresa_cliente_id' if perfil == 'cliente' else 'empresa_fornecedora_id'
    return http.get(BASE+f'/portal-{perfil}/painel', params={campo: 2 if perfil == 'cliente' else 4, **kw})


def muitos(sessoes, quantidade=25):
    with sessoes() as b:
        for i in range(100, 100+quantidade):
            status = ('aberta','em_execucao','concluida','cancelada')[(i-100)%4]
            b.add(SolicitacaoServico(id=i,empresa_cliente_id=2,processo_id=1,material_id=1,dimensao_x_maxima_mm=10,
                dimensao_y_maxima_mm=10,dimensao_z_maxima_mm=10,tolerancia_requerida_mm='0.02',quantidade=1));b.flush()
            b.add(CotacaoFornecedor(id=i,solicitacao_id=i,empresa_fornecedora_id=4,valor_total='100.00',prazo_dias=2,
                validade_dias=1,status='aceita'));b.flush()
            b.add(ContratacaoServico(id=i,solicitacao_id=i,cotacao_id=i,empresa_cliente_id=2,empresa_fornecedora_id=4,
                valor_total='100.00',prazo_dias=2,status='ativa'));b.flush()
            b.add(OrdemServico(id=i,contratacao_id=i,solicitacao_id=i,cotacao_id=i,empresa_cliente_id=2,empresa_fornecedora_id=4,
                processo_id=1,material_id=1,quantidade=1,valor_total='100.00',prazo_dias=2,status=status))
        b.commit()


@pytest.mark.parametrize('perfil', ['cliente','fornecedor'])
def test_totais_sao_da_empresa_inteira_e_listas_tem_cinco_registros(ambiente, perfil):
    http,_,sessoes,_ = ambiente;muitos(sessoes);u=entrar(http,perfil).json()['usuario'];antes=estado(sessoes)
    r=painel(http,perfil);assert r.status_code==200,r.text;p=r.json()
    assert r.headers['cache-control']=='no-store' and r.headers['x-content-type-options']=='nosniff'
    assert p['contexto']==f"{u['usuario_id']}:{perfil}:{u['empresa_id']}" and p['empresa_id']==u['empresa_id']
    assert p['ordens']=={'total':27,'por_status':{'aberta':8,'em_execucao':6,'concluida':7,'cancelada':6}}
    assert p['contratacoes']=={'total':27,'por_status':{'ativa':26,'encerrada':1}}
    assert p['cotacoes']=={'total':27,'por_status':{'aceita':27}}
    assert [o['id'] for o in p['ordens_recentes']]==[124,123,122,121,120]
    if perfil=='cliente':
        assert p['solicitacoes']=={'total':28,'por_status':{'aberta':28}}
        assert [s['id'] for s in p['solicitacoes_recentes']]==[124,123,122,121,120]
        assert p['cotacoes_recentes']==[] and p['oportunidades'] is None
    else:
        assert p['solicitacoes'] is None and p['solicitacoes_recentes']==[] and p['oportunidades']==0
        assert [c['id'] for c in p['cotacoes_recentes']]==[124,123,122,121,120]
    assert 'Razao Privada' not in r.text and 'Contato privado' not in r.text
    for campo in ('ranking','posicao','media','documento','email','observacoes','registro_interno','razao_social'):
        assert '"'+campo+'"' not in r.text
    assert estado(sessoes)==antes


@pytest.mark.parametrize('perfil',['cliente','fornecedor'])
def test_expiracao_e_calculada_em_utc_sem_alterar_propostas(ambiente,perfil,monkeypatch):
    http,_,sessoes,_=ambiente
    instante=datetime(2026,10,13,9,30,tzinfo=timezone.utc)
    class DataFixa(datetime):
        @classmethod
        def now(cls,tz=None):return instante
    monkeypatch.setattr('backend.app.services.painel_perfis.datetime',DataFixa)
    with sessoes() as b:
        for i, deslocamento, status in ((10,0,'enviada'),(11,-1,'enviada'),(12,1,'enviada'),(13,100,'aceita')):
            b.add(SolicitacaoServico(id=i,empresa_cliente_id=2,processo_id=1,material_id=1,dimensao_x_maxima_mm=10,
                dimensao_y_maxima_mm=10,dimensao_z_maxima_mm=10,tolerancia_requerida_mm='0.02',quantidade=1));b.flush()
            b.add(CotacaoFornecedor(id=i,solicitacao_id=i,empresa_fornecedora_id=4,valor_total='100.00',prazo_dias=2,
                validade_dias=1,status=status,criada_em=instante.replace(tzinfo=None)-timedelta(days=1,seconds=deslocamento)))
        b.commit()
    entrar(http,perfil);antes=estado(sessoes);r=painel(http,perfil);assert r.status_code==200,r.text
    p=r.json();assert p['cotacoes']=={'total':6,'por_status':{'aceita':3,'enviada':1,'expirada':2}}
    assert p['consultado_em']=='2026-10-13T09:30:00Z'
    if perfil=='fornecedor':
        assert {c['id']:c['status'] for c in p['cotacoes_recentes']}[10]=='expirada'
        assert {c['id']:c['status'] for c in p['cotacoes_recentes']}[11]=='enviada'
    assert estado(sessoes)==antes


def test_oportunidades_coincidem_com_documentos_compatibilidade_e_revisao(ambiente):
    http,_,sessoes,_=ambiente
    a=upload(http);liberar(http,a);liberar(http,upload(http));entrar(http,'fornecedor');antes=estado(sessoes)
    assert painel(http,'fornecedor').json()['oportunidades']==1
    op=http.get(BASE+'/portal-fornecedor/oportunidades',params={'empresa_fornecedora_id':4}).json()
    assert op['total']==1 and op['itens'][0]['id']==3
    assert estado(sessoes)==antes
    # Bloquear apenas um documento conserva a solicitação; nenhum arquivo
    # íntegro liberado remove a oportunidade tanto da janela quanto do painel.
    liberar(http,a,acao='bloquear',versao=1)
    with sessoes() as b:
        from backend.app.models.arquivo_tecnico import ArquivoTecnico
        from backend.app.models.documentacao_cotacao import LiberacaoArquivoCotacao
        arquivo=b.scalars(select(ArquivoTecnico).where(ArquivoTecnico.id!=a['id'])).first()
        ServicoArquivoTecnico(b).caminho_seguro(arquivo).write_bytes(b'arquivo corrompido')
    entrar(http,'fornecedor');antes=estado(sessoes)
    assert painel(http,'fornecedor').json()['oportunidades']==0
    assert http.get(BASE+'/portal-fornecedor/oportunidades',params={'empresa_fornecedora_id':4}).json()['total']==0
    assert estado(sessoes)==antes


@pytest.mark.parametrize('perfil',['cliente','fornecedor'])
def test_ultima_etapa_nao_multiplica_os_e_nao_expoe_observacoes(ambiente,perfil):
    http,_,sessoes,_=ambiente
    with sessoes() as b:
        b.add_all([EtapaProducao(id=10,ordem_servico_id=4,empresa_fornecedora_id=4,etapa='aguardando_material',observacoes='email privado'),
                   EtapaProducao(id=11,ordem_servico_id=4,empresa_fornecedora_id=4,etapa='em_usinagem',observacoes='Contato privado')]);b.commit()
    entrar(http,perfil);antes=estado(sessoes);r=painel(http,perfil);assert r.status_code==200,r.text
    p=r.json();assert p['ordens']['total']==2
    o=next(o for o in p['ordens_recentes'] if o['id']==4);assert o['etapa_atual']=='em_usinagem' and o['etapa_atual_em']
    assert next(o for o in p['ordens_recentes'] if o['id']==1)['etapa_atual'] is None
    assert 'Contato privado' not in r.text and 'email privado' not in r.text and estado(sessoes)==antes


@pytest.mark.parametrize('rota',['cliente','fornecedor'])
@pytest.mark.parametrize('perfil',[None,'admin','cliente','fornecedor'])
def test_painel_exige_perfil_exato_da_sessao(ambiente,rota,perfil):
    http,_,sessoes,_=ambiente
    if perfil:entrar(http,perfil)
    antes=estado(sessoes);r=painel(http,rota)
    assert r.status_code==(200 if perfil==rota else 403 if perfil else 401),r.text
    assert estado(sessoes)==antes


@pytest.mark.parametrize('perfil',['cliente','fornecedor'])
def test_nao_troca_empresa_com_query_duplicada_cabecalho_ou_cookie_falso(ambiente,perfil):
    http,_,sessoes,_=ambiente;entrar(http,perfil);antes=estado(sessoes)
    campo='empresa_cliente_id' if perfil=='cliente' else 'empresa_fornecedora_id'
    empresa=2 if perfil=='cliente' else 4;outra=6 if perfil=='cliente' else 8
    for params in ({campo:outra},[(campo,empresa),(campo,empresa)],{campo:empresa,'empresa_id':outra},{}):
        r=http.get(BASE+f'/portal-{perfil}/painel',params=params,headers={'X-Perfil':'admin','X-Empresa-Id':str(outra)})
        assert r.status_code==403,r.text
        assert 'ordens_recentes' not in r.text
    r=painel(http,perfil,**{campo:0});assert r.status_code==403
    assert estado(sessoes)==antes


@pytest.mark.parametrize('perfil',['cliente','fornecedor'])
def test_contexto_entre_sessoes_e_senha_inicial_impedem_consulta(ambiente,perfil):
    http,acesso,sessoes,_=ambiente;u=entrar(http,perfil).json()['usuario'];antes=estado(sessoes)
    campo='empresa_cliente_id' if perfil=='cliente' else 'empresa_fornecedora_id'
    caminho=BASE+f'/portal-{perfil}/painel';params={campo:u['empresa_id']}
    assert http.get(caminho,params=params,headers={'X-MEC-Painel-Contexto':'999:admin:0'}).status_code==409
    assert http.get(caminho,params=params,headers={'X-MEC-Painel-Contexto':f"{u['usuario_id']}:{perfil}:{u['empresa_id']}"}).status_code==200
    with sqlite3.connect(acesso.caminho) as b:b.execute('UPDATE usuarios_acesso SET trocar_senha=1 WHERE perfil=?',(perfil,))
    r=http.get(caminho,params=params);assert r.status_code==403 and 'troca_senha_inicial_obrigatoria' in r.text
    assert estado(sessoes)==antes


@pytest.mark.parametrize('perfil',['cliente','fornecedor'])
def test_empresa_sem_servicos_tem_zeros_reais_e_listas_vazias(ambiente,perfil):
    http,acesso,sessoes,_=ambiente
    empresa=6 if perfil=='cliente' else 8
    with sessoes() as b:
        b.query(OrdemServico).filter(OrdemServico.id==2).delete()
        b.query(ContratacaoServico).filter(ContratacaoServico.id==2).delete()
        b.query(CotacaoFornecedor).filter(CotacaoFornecedor.id==2).delete()
        b.query(SolicitacaoServico).filter(SolicitacaoServico.id==2).delete();b.commit()
    with sqlite3.connect(acesso.caminho) as b:b.execute('UPDATE usuarios_acesso SET empresa_id=? WHERE perfil=?',(empresa,perfil))
    entrar(http,perfil);r=painel(http,perfil,**{'empresa_cliente_id' if perfil=='cliente' else 'empresa_fornecedora_id':empresa})
    assert r.status_code==200,r.text;p=r.json()
    assert p['ordens']==p['cotacoes']==p['contratacoes']=={'total':0,'por_status':{}}
    assert p['ordens_recentes']==p['cotacoes_recentes']==p['solicitacoes_recentes']==[]


def test_numero_de_consultas_cliente_independe_da_quantidade_de_servicos(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,'cliente');engine=sessoes.kw['bind'];selecoes=[]
    def contar(c,cur,s,p,ctx,m):
        if s.lstrip().upper().startswith('SELECT'):selecoes.append(s)
    event.listen(engine,'before_cursor_execute',contar)
    try:
        assert painel(http,'cliente').status_code==200;n=len(selecoes);assert n<=9
        muitos(sessoes,75);selecoes.clear();assert painel(http,'cliente').status_code==200
        assert len(selecoes)==n
    finally:event.remove(engine,'before_cursor_execute',contar)


def test_contagem_e_lista_usam_mesma_fotografia_com_gravacao_concorrente(ambiente):
    http,_,sessoes,_=ambiente;engine=sessoes.kw['bind']
    with engine.connect() as c:c.exec_driver_sql('PRAGMA journal_mode=WAL')
    entrar(http,'cliente');feito=[]
    def escrever(c,cur,s,p,ctx,m):
        if not feito and s.startswith('SELECT CASE WHEN'):
            feito.append(True)
            with sessoes() as outra:
                outra.add(SolicitacaoServico(id=100,empresa_cliente_id=2,processo_id=1,material_id=1,dimensao_x_maxima_mm=10,
                    dimensao_y_maxima_mm=10,dimensao_z_maxima_mm=10,tolerancia_requerida_mm='0.02',quantidade=1));outra.commit()
    event.listen(engine,'after_cursor_execute',escrever)
    try:
        r=painel(http,'cliente');assert r.status_code==200,r.text;p=r.json()
        assert feito and p['solicitacoes']['total']==3 and all(s['id']!=100 for s in p['solicitacoes_recentes'])
    finally:event.remove(engine,'after_cursor_execute',escrever)
    assert painel(http,'cliente').json()['solicitacoes']['total']==4
