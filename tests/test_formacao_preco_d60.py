"""D60: preço exato, aprovação, contratação, sigilo e liquidação com sessões reais."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_comercial_administrativo_d43 import comercial, corpo as decisao, decidir, detalhe as comercial_detalhe
from test_documentacao_cotacao_d42 import upload, liberar
from test_janelas_d57 import estado
from backend.app.models.formacao_preco import ConfiguracaoPreco, FormacaoPreco, EventoFormacaoPreco
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.notificacao import NotificacaoPerfil
from backend.app.services.formacao_preco import REVISION

pytestmark=pytest.mark.acesso_real
PRE=BASE+'/administracao/formacao-preco/cotacoes'
CLIENTE=BASE+'/portal-cliente/cotacoes'
FIN=BASE+'/administracao/financeiro/contratacoes'
RESULTADO=BASE+'/administracao/resultado-intermediacao'

@pytest.fixture
def precificacao(comercial):
    http,_,sessoes,_=comercial
    a=upload(http,solicitacao=9);liberar(http,a)
    with sessoes() as b:
        b.add(ConfiguracaoPreco(id=1,revision=REVISION,ativada_em=datetime.now(timezone.utc).isoformat(),segredo_verificacao='ab'*32));b.commit()
    return comercial

def obter(http,q=8):
    r=http.get(PRE+f'/{q}');assert r.status_code==200,r.text;return r.json()

def corpo(http,q=8,modo='percentual',valor='20',despesas='50.00',acao='publicar',**extras):
    d=dict(modo=modo,acrescimo=valor,despesas_previstas=despesas,versao=obter(http,q)['versao'])
    r=http.post(PRE+f'/{q}/conferir',json=d);assert r.status_code==200,r.text
    return {**d,'acao':acao,'conferencia':r.json()['conferencia'],
        'registro_interno':'REGISTRO-RESERVADO-D60 conferência da proposta e acréscimo.','chave_operacao':str(uuid4()),**extras}

def publicar(http,q=8,**kw):
    entrar(http,'admin');r=http.post(PRE+f'/{q}/registrar',json=corpo(http,q,**kw));assert r.status_code==200,r.text;return r

def detalhe_cliente(http,q=8):
    r=http.get(CLIENTE+f'/{q}',params={'empresa_cliente_id':2});assert r.status_code==200,r.text;return r.json()['item']

def aprovar(http,q=8,acao='aprovar',**kw):
    entrar(http,'cliente');d=detalhe_cliente(http,q)
    dados=dict(empresa_cliente_id=2,acao=acao,versao=d['versao_preco'],observacao='Solicito análise da administração.',chave_operacao=str(uuid4()),**kw)
    return http.post(CLIENTE+f'/{q}/analise',params={'empresa_cliente_id':2},json=dados)

def contratar(http):
    entrar(http,'admin');r=decidir(http,decisao(http));assert r.status_code==200,r.text
    p=http.get(BASE+'/administracao/contratacoes/preparacao/9');assert p.status_code==200,p.text
    d=p.json();r=http.post(BASE+'/administracao/contratacoes/preparacao/9/confirmar',json={
        'acao':d['acao_disponivel'],'cotacao_id':8,'versao':d['versao'],'registro_interno':'Contrato conferido D60.','chave_operacao':str(uuid4())})
    assert r.status_code==200,r.text;return r.json()

def resultado(http,**kw):
    agora=datetime.now(timezone.utc).date();return http.get(RESULTADO,params={'inicio':str(agora-timedelta(days=1)),'fim':str(agora+timedelta(days=1)),**kw})

def evento_fin(http,cid,acao,**kw):
    r=http.get(FIN+f'/{cid}');assert r.status_code==200,r.text
    d=dict(acao=acao,versao=r.json()['resumo']['versao'],chave_operacao=str(uuid4()),registro_interno='Conferência financeira D60.',**kw)
    if acao in ('recebimento','repasse'):d.update(forma_pagamento='pix',referencia='TESTE-'+str(uuid4()))
    return http.post(FIN+f'/{cid}/eventos',json=d)

def test_cotacao_fornecedor_primeiro_vai_ao_adm_sem_expor_custo_ao_cliente(precificacao):
    http,_,sessoes,_=precificacao;a=upload(http,solicitacao=3);liberar(http,a);entrar(http,'fornecedor')
    r=http.post(BASE+'/portal-fornecedor/solicitacoes/3/cotacoes',json={'empresa_fornecedora_id':4,'valor_total':'12500.00','prazo_dias':5,'validade_dias':10});assert r.status_code==201,r.text
    qid=r.json()['id'];entrar(http,'cliente');antes=estado(sessoes)
    assert http.get(CLIENTE,params={'empresa_cliente_id':2,'cotacao_id':qid}).json()['total']==0
    assert http.get(CLIENTE+f'/{qid}',params={'empresa_cliente_id':2}).status_code==404
    assert http.get(BASE+'/solicitacoes-servico/3/cotacoes').json()==[]
    assert http.get(BASE+'/portal-cliente/painel',params={'empresa_cliente_id':2}).json()['cotacoes']=={'total':2,'por_status':{'aceita':2}}
    with sessoes() as b:
        ns=b.scalars(select(NotificacaoPerfil).where(NotificacaoPerfil.chave_evento==f'cotacao:{qid}:enviada')).all()
        assert [(n.perfil_destino,n.empresa_destino) for n in ns]==[('admin',0)]
    assert estado(sessoes)==antes

@pytest.mark.parametrize('modo,valor,custo,preco,ganho',[
    ('percentual','20','1500.00','1800.00','300.00'),('valor','300.00','1500.00','1800.00','300.00'),
    ('percentual','0','1500.00','1500.00','0.00'),('percentual','12.5','0.04','0.05','0.01'),
    ('percentual','0.1234','1500.00','1501.85','1.85')])
def test_conferencia_exata_percentual_e_valor_fixo(precificacao,modo,valor,custo,preco,ganho):
    http,_,sessoes,_=precificacao
    with sessoes() as b:b.get(CotacaoFornecedor,8).valor_total=Decimal(custo);b.commit()
    antes=estado(sessoes);dados={'modo':modo,'acrescimo':valor,'despesas_previstas':'50','versao':obter(http)['versao']}
    r=http.post(PRE+'/8/conferir',json=dados);assert r.status_code==200,r.text
    assert r.json()['preco_cliente']==preco and r.json()['acrescimo']==ganho
    assert Decimal(r.json()['resultado_previsto'])==Decimal(ganho)-50
    assert estado(sessoes)==antes

@pytest.mark.parametrize('mudanca',[{'modo':'outro'},{'acrescimo':'-1'},{'acrescimo':'1001'},{'modo':'valor','acrescimo':'1.001'},{'despesas_previstas':'-1'},{'acrescimo':'NaN'},{'custo_fornecedor':'1'},{'usuario_id':999}])
def test_dados_invalidos_nao_gravam_preco(precificacao,mudanca):
    http,_,sessoes,_=precificacao;antes=estado(sessoes)
    dados={'modo':'percentual','acrescimo':'20','despesas_previstas':'0','versao':obter(http)['versao'],**mudanca}
    assert http.post(PRE+'/8/conferir',json=dados).status_code==422
    assert estado(sessoes)==antes

def test_publicacao_exige_documento_integridade_e_conferencia(precificacao):
    http,_,sessoes,_=precificacao;d=corpo(http);antes=estado(sessoes)
    assert http.post(PRE+'/8/registrar',json={**d,'conferencia':'0'*64}).status_code==409
    from backend.app.models.arquivo_tecnico import ArquivoTecnico
    with sessoes() as b:a=b.scalar(select(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id==9));caminho=a.caminho_arquivo
    from pathlib import Path
    Path(caminho).write_bytes(b'PDF alterado')
    assert http.post(PRE+'/8/registrar',json=d).status_code==409 and estado(sessoes)==antes
    d=corpo(http,acao='salvar');assert http.post(PRE+'/8/registrar',json=d).status_code==200
    entrar(http,'cliente');assert http.get(CLIENTE+'/8',params={'empresa_cliente_id':2}).status_code==404

def test_cliente_recebe_apenas_preco_final_e_aprovacao_nao_contrata(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);entrar(http,'cliente');antes=estado(sessoes)
    d=detalhe_cliente(http);assert d['valor_total']=='1800.00' and d['pode_analisar'] and d['analise_cliente']=='publicada'
    r=http.get(BASE+'/solicitacoes-servico/9/cotacoes');assert r.status_code==200 and [c['valor_total'] for c in r.json()]==['1800.00']
    for r in (r,http.get(CLIENTE,params={'empresa_cliente_id':2,'cotacao_id':8}),http.get(CLIENTE+'/8',params={'empresa_cliente_id':2})):
        for segredo in ('custo_centavos','custo_fornecedor','acrescimo','REGISTRO-RESERVADO','despesas_previstas','resultado_previsto','1500.00','1275.55'):assert segredo not in r.text
    assert estado(sessoes)==antes
    r=aprovar(http);assert r.status_code==200,r.text
    with sessoes() as b:
        assert b.get(CotacaoFornecedor,8).status=='enviada'
        assert b.scalar(select(ContratacaoServico.id).where(ContratacaoServico.solicitacao_id==9)) is None
        assert b.get(FormacaoPreco,8).estado=='aprovada_cliente'
        ns=b.scalars(select(NotificacaoPerfil).where(NotificacaoPerfil.chave_evento.like('preco-d60:%'))).all()
        assert sorted(n.perfil_destino for n in ns)==['admin','cliente']
        assert all('acrescimo' not in n.mensagem and '1500.00' not in n.mensagem for n in ns)

@pytest.mark.parametrize('perfil',[None,'cliente','fornecedor'])
def test_preco_resultado_e_historico_sao_exclusivos_do_adm(precificacao,perfil):
    http,_,sessoes,_=precificacao;http.headers.pop('X-MEC-CSRF',None);http.cookies.clear()
    if perfil:entrar(http,perfil)
    antes=estado(sessoes)
    for url in (PRE+'/8',RESULTADO):
        r=http.get(url,params={'inicio':'2026-01-01','fim':'2026-12-31'},headers={'X-Perfil':'admin'})
        assert r.status_code==(403 if perfil else 401) and 'custo_fornecedor' not in r.text
    assert http.post(PRE+'/8/conferir',json={}).status_code==(403 if perfil else 401)
    assert estado(sessoes)==antes

def test_aceite_e_rotas_legadas_nao_pulam_aprovacao(precificacao):
    http,_,sessoes,_=precificacao;antes=estado(sessoes)
    assert decidir(http,decisao(http)).status_code==409
    assert http.post(BASE+'/solicitacoes-servico/9/cotacoes/8/aceitar',json={'empresa_cliente_id':2}).status_code==409
    assert http.post(BASE+'/solicitacoes-servico/9/contratacao',json={'empresa_cliente_id':2,'cotacao_id':8}).status_code==409
    assert estado(sessoes)==antes
    publicar(http);assert decidir(http,decisao(http)).status_code==409
    assert aprovar(http).status_code==200;entrar(http,'admin');assert decidir(http,decisao(http)).status_code==200

def test_revisao_recusa_nova_publicacao_e_preco_alterado_invalidam_aprovacao(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http,acao='revisar').status_code==200
    entrar(http,'admin');assert decidir(http,decisao(http)).status_code==409
    publicar(http,modo='valor',valor='450');entrar(http,'cliente');assert detalhe_cliente(http)['valor_total']=='1950.00'
    assert aprovar(http,acao='recusar').status_code==200
    publicar(http,modo='valor',valor='300');entrar(http,'cliente');d=detalhe_cliente(http)
    publicar(http,valor='25');entrar(http,'cliente');antes=estado(sessoes)
    r=http.post(CLIENTE+'/8/analise',params={'empresa_cliente_id':2},json={'empresa_cliente_id':2,'acao':'aprovar','versao':d['versao_preco'],'chave_operacao':str(uuid4())})
    assert r.status_code==409 and estado(sessoes)==antes
    assert aprovar(http).status_code==200;publicar(http,acao='salvar');entrar(http,'admin');assert decidir(http,decisao(http)).status_code==409
    entrar(http,'cliente');assert http.get(CLIENTE+'/8',params={'empresa_cliente_id':2}).status_code==404

def test_um_orcamento_publicado_por_solicitacao_e_tokens_antigos_recusados(precificacao):
    http,_,sessoes,_=precificacao;d=corpo(http);publicar(http)
    antes=estado(sessoes);assert http.post(PRE+'/8/registrar',json=d).status_code==409
    assert http.post(PRE+'/9/registrar',json=corpo(http,q=9)).status_code==409 and estado(sessoes)==antes
    publicar(http,acao='retirar');publicar(http,q=9);entrar(http,'cliente')
    assert http.get(CLIENTE,params={'empresa_cliente_id':2,'solicitacao_id':9}).json()['itens'][0]['id']==9

@pytest.mark.parametrize('mudanca',['custo','quantidade','vencida'])
def test_condicoes_alteradas_e_expiracao_bloqueiam_analise_e_aceite(precificacao,mudanca):
    http,_,sessoes,_=precificacao;publicar(http);entrar(http,'cliente');d=detalhe_cliente(http)
    with sessoes() as b:
        if mudanca=='custo':b.get(CotacaoFornecedor,8).valor_total=Decimal('1600')
        elif mudanca=='quantidade':b.get(SolicitacaoServico,9).quantidade=20
        else:b.get(CotacaoFornecedor,8).criada_em=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=20)
        b.commit()
    antes=estado(sessoes);r=http.post(CLIENTE+'/8/analise',params={'empresa_cliente_id':2},json={'empresa_cliente_id':2,'acao':'aprovar','versao':d['versao_preco'],'chave_operacao':str(uuid4())})
    assert r.status_code==409 and estado(sessoes)==antes and not detalhe_cliente(http)['pode_analisar']

def test_csrf_contexto_empresa_e_operador_nao_podem_ser_forjados(precificacao):
    http,_,sessoes,_=precificacao;d=corpo(http);token=http.headers.pop('X-MEC-CSRF');antes=estado(sessoes)
    assert http.post(PRE+'/8/registrar',json=d).status_code==403;http.headers['X-MEC-CSRF']=token
    assert http.post(PRE+'/8/registrar',json=d,headers={'Origin':'https://outro.local'}).status_code==403
    assert http.post(PRE+'/8/registrar',json=d,headers={'X-MEC-Preco-Contexto':'999:admin:0'}).status_code==409
    assert estado(sessoes)==antes
    publicar(http);entrar(http,'cliente');d=detalhe_cliente(http);antes=estado(sessoes)
    corpo_a=dict(empresa_cliente_id=2,acao='aprovar',versao=d['versao_preco'],chave_operacao=str(uuid4()))
    for params in ({},{'empresa_cliente_id':6},[('empresa_cliente_id',2),('empresa_cliente_id',2)]):
        assert http.post(CLIENTE+'/8/analise',params=params,json=corpo_a).status_code==403
    assert http.post(CLIENTE+'/8/analise',params={'empresa_cliente_id':2},json={**corpo_a,'empresa_cliente_id':6}).status_code==403
    assert http.post(CLIENTE+'/8/analise',params={'empresa_cliente_id':2},json={**corpo_a,'perfil':'admin'}).status_code==403
    assert estado(sessoes)==antes

def test_repeticao_publicacao_e_analise_nao_duplicam_eventos_ou_notificacoes(precificacao):
    http,_,sessoes,_=precificacao;d=corpo(http);a=http.post(PRE+'/8/registrar',json=d);assert a.status_code==200,a.text
    antes=estado(sessoes);b=http.post(PRE+'/8/registrar',json=d);assert b.json()==a.json() and estado(sessoes)==antes
    assert http.post(PRE+'/8/registrar',json={**d,'registro_interno':'Outro registro'}).status_code==409
    entrar(http,'cliente');q=detalhe_cliente(http);d=dict(empresa_cliente_id=2,acao='aprovar',versao=q['versao_preco'],chave_operacao=str(uuid4()))
    a=http.post(CLIENTE+'/8/analise',params={'empresa_cliente_id':2},json=d);assert a.status_code==200,a.text
    antes=estado(sessoes);b=http.post(CLIENTE+'/8/analise',params={'empresa_cliente_id':2},json=d)
    assert a.json()==b.json() and estado(sessoes)==antes

def test_concorrencia_publicacao_da_mesma_versao_e_atomica(precificacao):
    http,_,sessoes,app=precificacao;d=corpo(http);cookie=dict(http.cookies);headers=dict(http.headers)
    def enviar(i):
        h=TestClient(app);h.cookies.update(cookie);h.headers.update(headers)
        try:return h.post(PRE+'/8/registrar',json={**d,'chave_operacao':str(uuid4())})
        finally:h.close()
    with ThreadPoolExecutor(max_workers=2) as t:r=list(t.map(enviar,range(2)))
    assert sorted(a.status_code for a in r)==[200,409]
    with sessoes() as b:
        assert b.get(FormacaoPreco,8).versao==1 and len(b.scalars(select(EventoFormacaoPreco)).all())==1
        assert len(b.scalars(select(NotificacaoPerfil).where(NotificacaoPerfil.chave_evento.like('preco-d60:%'))).all())==1

def test_falha_na_auditoria_reverte_preco_e_publicacao(precificacao):
    http,_,sessoes,_=precificacao;d=corpo(http);antes=estado(sessoes)
    def falhar(*args):raise IntegrityError('teste',{},Exception('Falha isolada'))
    event.listen(EventoFormacaoPreco,'before_insert',falhar)
    try:
        with pytest.raises(IntegrityError):http.post(PRE+'/8/registrar',json=d)
    finally:event.remove(EventoFormacaoPreco,'before_insert',falhar)
    assert estado(sessoes)==antes

def test_contratacao_copia_venda_guarda_custo_e_portais_mantem_sigilo(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http).status_code==200;contrato=contratar(http)
    cid,oid=contrato['contratacao_id'],contrato['ordem_servico_id']
    with sessoes() as b:
        assert b.get(ContratacaoServico,cid).valor_total==b.get(OrdemServico,oid).valor_total==Decimal('1800')
        p=b.get(FormacaoPreco,8);assert p.estado=='contratada' and p.contratacao_id==cid and p.custo_centavos==150000
        assert b.get(CotacaoFornecedor,8).valor_total==Decimal('1500')
        for antigo in (1,2,4):assert b.get(ContratacaoServico,antigo).valor_total==Decimal('1500')
    for perfil,valor in [('cliente','1800.00'),('fornecedor','1500.00')]:
        entrar(http,perfil);params={f'empresa_{"cliente" if perfil=="cliente" else "fornecedora"}_id':2 if perfil=='cliente' else 4}
        for rota,id_alvo in [('contratacoes',cid),('ordens-servico',oid),('producao',oid),('financeiro',cid)]:
            r=http.get(BASE+f'/portal-{perfil}/{rota}/{id_alvo}',params=params);assert r.status_code==200,r.text
            assert '1800.00' not in r.text if perfil=='fornecedor' else True
            assert all(s not in r.text for s in ('acrescimo','custo_fornecedor','REGISTRO-RESERVADO','despesas_previstas','resultado_previsto'))
            if rota in ('contratacoes','financeiro'):assert valor in r.text
    entrar(http,'admin');assert http.post(PRE+'/8/registrar',json={'modo':'valor','acrescimo':'5','despesas_previstas':'0','versao':obter(http)['versao'],'conferencia':'a'*64,'acao':'publicar','chave_operacao':str(uuid4()),'registro_interno':'Mudança proibida'}).status_code==409

def test_financeiro_recebe_venda_repasse_so_custo_e_resultado_confirma_apos_liquidacao(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http).status_code==200;c=contratar(http);cid,oid=c['contratacao_id'],c['ordem_servico_id']
    assert http.post(FIN+f'/{cid}/iniciar',json={'registro_interno':'Controle financeiro conferido.'}).status_code==201
    d=resultado(http).json();assert d['total']==1 and d['totais']['ganho_bruto_previsto']=='300.00' and d['totais']['resultado_previsto']=='250.00' and d['totais']['ganho_bruto_confirmado']=='0.00'
    assert evento_fin(http,cid,'recebimento',valor='1000').status_code==201
    assert evento_fin(http,cid,'repasse',valor='1000').status_code==409
    with sessoes() as b:
        b.get(OrdemServico,oid).status='concluida';ciclo=b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==oid));ciclo.status='entregue_cliente';b.commit()
    assert evento_fin(http,cid,'repasse',valor='1000').status_code==201
    assert evento_fin(http,cid,'repasse',valor='500').status_code==409
    assert evento_fin(http,cid,'recebimento',valor='800').status_code==201
    assert evento_fin(http,cid,'repasse',valor='501').status_code==409
    assert evento_fin(http,cid,'repasse',valor='500').status_code==201
    d=http.get(FIN+f'/{cid}').json();assert d['resumo']['saldo_cliente']==d['resumo']['saldo_fornecedor']=='0.00'
    assert d['resumo']['valor_contratado']=='1800.00' and d['resumo']['valor_fornecedor']=='1500.00' and d['resumo']['disponivel_repasse']=='0.00'
    assert d['acoes_permitidas'].count('encerrar')==1
    assert resultado(http).json()['totais']['ganho_bruto_confirmado']=='300.00'
    assert evento_fin(http,cid,'encerrar').status_code==201
    from backend.app.services.painel_administrativo import ServicoPainelAdministrativo
    with sessoes() as b:
        l=b.execute(ServicoPainelAdministrativo(b)._consulta().where(ContratacaoServico.id==cid)).first()
        item=ServicoPainelAdministrativo._item(l);assert item.situacao=='concluida' and not item.pendencias and item.saldo_fornecedor==0
    for perfil,valor in [('cliente','1800.00'),('fornecedor','1500.00')]:
        entrar(http,perfil);r=http.get(BASE+f'/portal-{perfil}/financeiro/{cid}',params={f'empresa_{"cliente" if perfil=="cliente" else "fornecedora"}_id':2 if perfil=='cliente' else 4})
        assert r.status_code==200 and r.json()['valor_contratado']==valor and r.json()['saldo']=='0.00'
    entrar(http,'admin');assert evento_fin(http,cid,'reabrir').status_code==201
    assert evento_fin(http,cid,'estornar_repasse',movimento_id=d['repasses'][-1]['id'],referencia='ESTORNO-D60').status_code==201
    assert resultado(http).json()['totais']['ganho_bruto_confirmado']=='0.00'

def test_pagina_do_cliente_ordena_preco_publicado_e_totais_ignoram_rascunhos(precificacao):
    http,_,sessoes,_=precificacao;publicar(http,q=9,modo='valor',valor='700')
    entrar(http,'cliente');antes=estado(sessoes);r=http.get(CLIENTE,params={'empresa_cliente_id':2,'ordenacao':'valor','limite':1})
    assert r.status_code==200 and r.json()['total']==3 and r.json()['itens'][0]['valor_total']=='1500.00'
    p=http.get(CLIENTE,params={'empresa_cliente_id':2,'ordenacao':'valor','deslocamento':2,'limite':1}).json()
    assert p['itens'][0]['valor_total']=='1975.55' and p['itens'][0]['id']==9 and estado(sessoes)==antes

def test_publicacao_expirada_nao_impede_adm_publicar_outra_proposta_valida(precificacao):
    http,_,sessoes,_=precificacao;publicar(http)
    with sessoes() as b:b.get(CotacaoFornecedor,8).criada_em=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=20);b.commit()
    publicar(http,q=9);entrar(http,'cliente');assert not detalhe_cliente(http,8)['pode_analisar'] and detalhe_cliente(http,9)['pode_analisar']

def test_contratacao_concorrente_nao_expoe_venda_na_lista_do_fornecedor(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http).status_code==200
    engine=sessoes.kw['bind']
    with engine.connect() as c:c.exec_driver_sql('PRAGMA journal_mode=WAL')
    entrar(http,'fornecedor');feito=[]
    def gravar(c,cur,s,p,ctx,m):
        if not feito and s.startswith('SELECT formacoes_preco_cotacao.contratacao_id'):
            feito.append(True)
            with sessoes() as b:
                b.add(ContratacaoServico(id=99,solicitacao_id=9,cotacao_id=8,empresa_cliente_id=2,empresa_fornecedora_id=4,valor_total=Decimal('1800'),prazo_dias=7,status='ativa'));b.flush()
                pre=b.get(FormacaoPreco,8);pre.estado='contratada';pre.contratacao_id=99;b.get(CotacaoFornecedor,8).status='aceita';b.commit()
    event.listen(engine,'after_cursor_execute',gravar)
    try:
        r=http.get(BASE+'/portal-fornecedor/contratacoes',params={'empresa_fornecedora_id':4})
        assert r.status_code==200,r.text
        assert feito and r.json()['total']==2 and '1800.00' not in r.text
    finally:event.remove(engine,'after_cursor_execute',gravar)
    r=http.get(BASE+'/portal-fornecedor/contratacoes',params={'empresa_fornecedora_id':4})
    assert r.json()['total']==3 and r.json()['itens'][0]['id']==99 and r.json()['itens'][0]['valor_total']=='1500.00' and '1800.00' not in r.text

def test_resultado_periodo_totais_paginacao_e_historico_sem_gravacoes(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http).status_code==200;contratar(http);antes=estado(sessoes)
    r=resultado(http,deslocamento=100);assert r.status_code==200,r.text;d=r.json()
    assert d['total']==1 and d['itens']==[] and d['totais']['ganho_bruto_previsto']=='300.00'
    assert resultado(http,inicio='2026-10-14',fim='2026-10-13').status_code==422
    assert resultado(http,inicio='1900-01-01',fim='9999-12-31').status_code==422
    assert estado(sessoes)==antes

def test_historico_aceito_legado_sem_data_encerramento_continua_visivel(precificacao):
    http,_,sessoes,_=precificacao
    with sessoes() as b:b.get(CotacaoFornecedor,1).encerrada_em=None;b.commit()
    entrar(http,'cliente');antes=estado(sessoes)
    r=http.get(CLIENTE+'/1',params={'empresa_cliente_id':2});assert r.status_code==200 and r.json()['item']['valor_total']=='1500.00'
    assert r.json()['item']['analise_cliente'] is None and not r.json()['item']['pode_analisar'] and estado(sessoes)==antes

def test_revisao_da_documentacao_invalida_aprovacao_e_exige_nova_publicacao(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http).status_code==200;entrar(http,'admin')
    from test_documentacao_cotacao_d42 import corpo as corpo_doc, DOC
    from backend.app.models.arquivo_tecnico import ArquivoTecnico
    with sessoes() as b:
        a=b.scalar(select(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id==9));d={'id':a.id,'sha256':a.sha256}
    r=http.post(DOC+f'/arquivos/{d["id"]}/eventos',json=corpo_doc(d,acao='bloquear',versao=1));assert r.status_code==200,r.text
    antes=estado(sessoes);assert decidir(http,decisao(http)).status_code==409 and estado(sessoes)==antes
    r=http.post(DOC+f'/arquivos/{d["id"]}/eventos',json=corpo_doc(d,acao='liberar',versao=2));assert r.status_code==200,r.text
    assert decidir(http,decisao(http)).status_code==409
    publicar(http);assert aprovar(http).status_code==200;entrar(http,'admin');assert decidir(http,decisao(http)).status_code==200

def test_revisao_apos_aceite_antes_contratacao_nao_trava_fluxo_nem_altera_custo(precificacao):
    http,_,sessoes,_=precificacao;publicar(http);assert aprovar(http).status_code==200;entrar(http,'admin');assert decidir(http,decisao(http)).status_code==200
    publicar(http,modo='valor',valor='450');entrar(http,'admin')
    p=http.get(BASE+'/administracao/contratacoes/preparacao/9');assert p.status_code==200 and p.json()['acao_disponivel'] is None
    assert p.json()['motivo_indisponivel']=='orcamento_cliente_aguarda_aprovacao'
    entrar(http,'cliente');d=detalhe_cliente(http);assert d['pode_analisar'] and d['status']=='aceita' and d['valor_total']=='1950.00'
    assert aprovar(http).status_code==200;entrar(http,'admin')
    r=http.get(BASE+'/administracao/contratacoes/preparacao/9');assert r.json()['acao_disponivel']=='contratar_e_abrir_os'
    dados=r.json();r=http.post(BASE+'/administracao/contratacoes/preparacao/9/confirmar',json={'acao':dados['acao_disponivel'],'cotacao_id':8,'versao':dados['versao'],'registro_interno':'Conferência após revisão do preço.','chave_operacao':str(uuid4())})
    assert r.status_code==200,r.text
    with sessoes() as b:
        assert b.get(ContratacaoServico,r.json()['contratacao_id']).valor_total==Decimal('1950.00')
        assert b.get(CotacaoFornecedor,8).valor_total==Decimal('1500.00') and b.get(CotacaoFornecedor,8).status=='aceita'
