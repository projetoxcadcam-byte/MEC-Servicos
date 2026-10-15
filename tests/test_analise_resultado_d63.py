"""Análise ADM: precisão, agrupamentos, liquidação, filtros, sigilo e CSV."""
import csv
import io
from datetime import datetime
import pytest
from sqlalchemy import event, select
from test_relatorio_resultado_d62 import (
    despesas, precificacao, comercial, ambiente, modelo_acessos, entrar, registrar,
    estornar, evento_fin, FIN, DES, clonar, estado, filtros,
    ContratacaoServico, CotacaoFornecedor, SolicitacaoServico, FormacaoPreco,
    DespesaAdministracao, Empresa, OrdemServico, CicloIntermediacao,
)

pytestmark = pytest.mark.acesso_real
ANA = DES + '/resultado/analise'

def obter(http, **kw):
    r = http.get(ANA, params=filtros(**kw))
    assert r.status_code == 200, r.text
    assert r.headers['cache-control'] == 'no-store'
    assert r.headers['x-mec-despesas-contexto'] == r.json()['contexto']
    return r.json()

def exportar(http, r, **kw):
    return http.get(ANA + '/csv', params={'inicio': r['inicio'], 'fim': r['fim'], 'versao': r['versao'],
        **{k: v for k, v in r['filtros'].items() if v is not None}, **kw})

def linhas(r):
    assert r.status_code == 200, r.text
    assert r.content.startswith(b'\xef\xbb\xbf')
    return list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))

@pytest.fixture
def carteira(despesas):
    http, _, sessoes, _, cid = despesas
    assert registrar(http, cid, valor='400.01').status_code == 200
    est = registrar(http, cid, valor='0.02').json()
    assert estornar(http, cid, est['despesa_id']).status_code == 200
    with sessoes() as b:
        o = b.scalar(select(OrdemServico).where(OrdemServico.contratacao_id == cid)); o.status = 'concluida'
        b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == o.id)).status = 'entregue_cliente'
        b.commit()
    assert http.post(FIN + f'/{cid}/iniciar', json={'registro_interno': 'Liquidação para análise D63'}).status_code == 201
    assert evento_fin(http, cid, 'recebimento', valor='1800.00').status_code == 201
    assert evento_fin(http, cid, 'repasse', valor='1500.00').status_code == 201
    with sessoes() as b:
        c = b.get(ContratacaoServico, cid); c.criada_em = datetime(2026, 6, 30, 23, 59, 59)
        q = b.get(CotacaoFornecedor, c.cotacao_id); s = b.get(SolicitacaoServico, c.solicitacao_id); p = b.get(FormacaoPreco, c.cotacao_id)
        d = b.scalar(select(DespesaAdministracao).where(DespesaAdministracao.contratacao_id == cid, DespesaAdministracao.status == 'confirmada'))
        clonar(b, b.get(Empresa, 2), id=202, documento='CLIENTE-D63-202')
        clonar(b, b.get(Empresa, 4), id=204, documento='FORNECEDOR-D63-204')
        b.flush()
        for novo, cli, forn, data, valor in ((100, 202, 4, datetime(2026, 7, 1), 50002), (101, 2, 204, datetime(2026, 10, 10), 1)):
            clonar(b, s, id=novo, empresa_cliente_id=cli)
            clonar(b, q, id=novo, solicitacao_id=novo, empresa_fornecedora_id=forn)
            clonar(b, c, id=novo, solicitacao_id=novo, cotacao_id=novo, empresa_cliente_id=cli, empresa_fornecedora_id=forn, criada_em=data, status='ativa')
            b.flush()
            clonar(b, p, cotacao_id=novo, solicitacao_id=novo, contratacao_id=novo, empresa_cliente_id=cli)
            clonar(b, d, id=novo, contratacao_id=novo, valor_centavos=valor)
        b.commit()
    return despesas

def periodo(http, **kw):
    return obter(http, inicio='2026-06-30', fim='2026-10-10', **kw)

def test_grupos_mensais_mes_vazio_nomes_iguais_e_centavos_exatos(carteira):
    http, _, sessoes, _, _ = carteira
    antes = estado(sessoes)
    r = periodo(http)
    assert r['total'] == r['total_periodo'] == 3 and r['liquidadas'] == 1
    assert r['totais']['venda_cliente'] == '5400.00' and r['totais']['custo_fornecedor'] == '4500.00'
    assert r['totais']['despesas_pagas'] == '900.04' and r['totais']['resultado_apos_despesas'] == '-0.04'
    assert r['totais']['resultado_previsto'] == '750.00' and r['totais']['resultado_liquidado_apos_despesas'] == '-100.01'
    assert [g['chave'] for g in r['meses']] == ['2026-06','2026-07','2026-08','2026-09','2026-10']
    assert [g['total'] for g in r['meses']] == [1,1,0,0,1]
    assert [g['totais']['resultado_apos_despesas'] for g in r['meses']] == ['-100.01','-200.02','0.00','0.00','299.99']
    assert len(r['clientes']) == len(r['fornecedores']) == 2
    assert {g['empresa_id'] for g in r['clientes']} == {2,202}
    assert len({g['nome'] for g in r['clientes']}) == 1
    assert {g['empresa_id'] for g in r['fornecedores']} == {4,204}
    assert r['totais'] == http.get(DES+'/resultado/relatorio',params={'inicio':r['inicio'],'fim':r['fim']}).json()['totais']
    dados = linhas(exportar(http,r))
    assert len([d for d in dados if d['Tipo de registro']=='Contratação']) == 3
    assert len([d for d in dados if d['Tipo de registro']=='Mês']) == 5
    assert dados[0]['Resultado após despesas pagas (R$)'] == '-0,04'
    assert estado(sessoes) == antes

def test_filtros_empresa_e_liquidacao_mantem_opcoes_do_periodo(carteira):
    http = carteira[0]
    r = periodo(http, empresa_cliente_id=202, empresa_fornecedora_id=4, liquidacao='aguardando')
    assert r['total'] == 1 and r['itens'][0]['contratacao_id'] == 100
    assert r['totais']['resultado_apos_despesas'] == '-200.02'
    assert len(r['opcoes_clientes']) == len(r['opcoes_fornecedores']) == 2
    assert len(linhas(exportar(http,r))) == 9  # resumo + cinco meses + cliente + fornecedor + contrato
    assert exportar(http,r,liquidacao='todas').status_code == 409
    r = periodo(http,liquidacao='liquidadas')
    assert r['total'] == r['liquidadas'] == 1 and r['totais']['resultado_liquidado_apos_despesas'] == '-100.01'
    r = periodo(http,empresa_cliente_id=202,empresa_fornecedora_id=204)
    assert r['total'] == 0 and r['clientes'] == r['fornecedores'] == []
    assert all(g['total']==0 for g in r['meses'])
    vazio = obter(http,inicio='1900-01-01',fim='1900-01-01')
    assert vazio['total_periodo'] == 0 and len(vazio['meses']) == 1 and vazio['opcoes_clientes'] == []

def test_json_csv_sigilo_real_contexto_e_anonimo(despesas):
    http, _, sessoes, _, _ = despesas
    r = obter(http); antes = estado(sessoes)
    for perfil in ('cliente','fornecedor'):
        entrar(http,perfil)
        for url,p in ((ANA,filtros()),(ANA+'/csv',{**filtros(),'versao':r['versao']})):
            resposta = http.get(url,params=p,headers={'X-MEC-PERFIL':'admin','X-MEC-EMPRESA-ID':'0'})
            assert resposta.status_code == 403 and 'custo_fornecedor' not in resposta.text and 'opcoes_clientes' not in resposta.text
    http.cookies.clear()
    assert http.get(ANA,params=filtros()).status_code == 401
    assert exportar(http,r).status_code == 401
    entrar(http,'admin')
    assert http.get(ANA,params=filtros(),headers={'X-MEC-Despesas-Contexto':'999:admin:0'}).status_code == 409
    assert exportar(http,r,empresa_cliente_id=999).status_code == 422
    assert estado(sessoes) == antes

def test_filtros_invalidos_repetidos_e_desconhecidos_recusados(despesas):
    http = despesas[0]
    for trocas in ({'inicio':'2026-10-15','fim':'2026-10-14'}, {'inicio':'1900-01-01','fim':'2026-10-14'},
        {'empresa_cliente_id':0}, {'empresa_fornecedora_id':-1}, {'empresa_cliente_id':999},
        {'liquidacao':'sim'}, {'limite':1}, {'versao':'a'*64}, {'fim':'9999-12-31'}):
        assert http.get(ANA,params=filtros(**trocas)).status_code == 422, trocas
    assert http.get(ANA,params=[*filtros().items(),('inicio',filtros()['inicio'])]).status_code == 422
    assert http.get(ANA+'/csv',params=filtros(versao='invalida')).status_code == 422

def test_csv_antigo_recusado_apos_despesa_estorno_liquidacao_e_cancelamento(despesas):
    http, _, sessoes, _, cid = despesas
    r = obter(http); assert obter(http)['versao']==r['versao']
    d = registrar(http,cid).json();assert exportar(http,r).status_code == 409
    r = obter(http);assert estornar(http,cid,d['despesa_id']).status_code==200
    assert exportar(http,r).status_code==409
    r = obter(http)
    with sessoes() as b:
        o=b.scalar(select(OrdemServico).where(OrdemServico.contratacao_id==cid));o.status='concluida'
        b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id==o.id)).status='entregue_cliente';b.commit()
    assert http.post(FIN+f'/{cid}/iniciar',json={'registro_interno':'Liquidação D63'}).status_code==201
    assert evento_fin(http,cid,'recebimento',valor='1800.00').status_code==201
    assert evento_fin(http,cid,'repasse',valor='1500.00').status_code==201
    assert exportar(http,r).status_code==409
    r=obter(http);assert r['liquidadas']==1
    with sessoes() as b:b.get(ContratacaoServico,cid).status='cancelada';b.commit()
    assert exportar(http,r).status_code==409
    assert obter(http)['total']==0

def test_csv_todas_empresas_e_contratos_sem_n_mais_um(despesas):
    http, _, sessoes, _, cid = despesas
    def contar():
        sql=[]
        def anotar(cx,cur,comando,params,ctx,muitos):sql.append(comando.strip().split()[0].upper())
        engine=sessoes.kw['bind'];event.listen(engine,'before_cursor_execute',anotar)
        try:r=obter(http)
        finally:event.remove(engine,'before_cursor_execute',anotar)
        assert set(sql)<={'SELECT','BEGIN'}
        return r,sql.count('SELECT')
    _,n=contar()
    with sessoes() as b:
        c=b.get(ContratacaoServico,cid);q=b.get(CotacaoFornecedor,c.cotacao_id);s=b.get(SolicitacaoServico,c.solicitacao_id);p=b.get(FormacaoPreco,c.cotacao_id)
        for novo in range(100,123):
            clonar(b,b.get(Empresa,4),id=novo+500,documento=f'FORN-D63-{novo}',razao_social=f'Oficina {novo}')
            clonar(b,s,id=novo);clonar(b,q,id=novo,solicitacao_id=novo,empresa_fornecedora_id=novo+500)
            clonar(b,c,id=novo,solicitacao_id=novo,cotacao_id=novo,empresa_fornecedora_id=novo+500);b.flush()
            clonar(b,p,cotacao_id=novo,solicitacao_id=novo,contratacao_id=novo)
        b.commit()
    antes=estado(sessoes);r,n2=contar();assert n==n2
    assert r['total']==24 and len(r['fornecedores'])==24
    assert r['totais']['venda_cliente']=='43200.00'
    dados=linhas(exportar(http,r));assert len([d for d in dados if d['Tipo de registro']=='Fornecedor'])==24
    assert len([d for d in dados if d['Tipo de registro']=='Contratação'])==24
    assert estado(sessoes)==antes

def test_csv_neutraliza_formula_nomes_e_preserva_negativo_numerico(despesas):
    http, _, sessoes, _, cid=despesas
    assert registrar(http,cid,valor='400.01').status_code==200
    with sessoes() as b:
        b.get(Empresa,2).razao_social='\ufeff =COMANDO()'
        b.get(Empresa,4).razao_social='+COMANDO(); "aspas"\nOficina';b.commit()
    r=obter(http);dados=linhas(exportar(http,r))
    contrato=next(d for d in dados if d['Tipo de registro']=='Contratação')
    assert contrato['Cliente']=="'\ufeff =COMANDO()" and contrato['Fornecedor'].startswith("'+COMANDO()")
    assert contrato['Resultado após despesas pagas (R$)']=='-100,01'
    assert next(d for d in dados if d['Tipo de registro']=='Cliente')['Empresa']=="'\ufeff =COMANDO()"

def test_uma_leitura_coerente_durante_despesa_concorrente(despesas):
    http, _, sessoes, _, cid=despesas
    assert registrar(http,cid).status_code==200
    engine=sessoes.kw['bind']
    with engine.connect() as cx:cx.exec_driver_sql('PRAGMA journal_mode=WAL')
    feito=[]
    def gravar(cx,cur,sql,params,ctx,muitos):
        if not feito and sql.startswith('SELECT contratacoes_servico.id') and 'sum(despesas_administracao.valor_centavos)' in sql:
            feito.append(True)
            with sessoes() as b:b.scalar(select(DespesaAdministracao)).valor_centavos=9001;b.commit()
    event.listen(engine,'after_cursor_execute',gravar)
    try:r=obter(http)
    finally:event.remove(engine,'after_cursor_execute',gravar)
    assert feito and r['totais']['despesas_pagas']=='50.00'
    assert r['meses'][0]['totais']['despesas_pagas']==r['clientes'][0]['totais']['despesas_pagas']==r['fornecedores'][0]['totais']['despesas_pagas']=='50.00'
    assert obter(http)['totais']['despesas_pagas']=='90.01'
