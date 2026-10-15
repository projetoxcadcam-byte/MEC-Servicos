from datetime import datetime,timedelta,timezone
from decimal import Decimal
import pytest
from test_despesas_administracao_d61 import precificacao,comercial,ambiente,modelo_acessos,entrar,DES
from test_formacao_preco_d60 import publicar,aprovar,contratar
from test_janelas_d57 import estado
from backend.app.models.despesa_administracao import ConfiguracaoDespesas
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.services.despesa_administracao import REVISION
from sqlalchemy import select

@pytest.fixture
def visibilidade(precificacao):
    http,_,sessoes,_=precificacao
    agora=datetime.now(timezone.utc).replace(tzinfo=None)
    with sessoes() as b:
        b.add(ConfiguracaoDespesas(id=1,revision=REVISION,ativada_em=agora.isoformat()+'Z'))
        for c in b.scalars(select(ContratacaoServico)):c.criada_em=agora
        for s in b.scalars(select(SolicitacaoServico)):s.criada_em=agora
        b.commit()
    return precificacao
def consulta(http,**kw):
    hoje=datetime.now(timezone.utc).date()
    return http.get(DES+'/resultado',params={'inicio':str(hoje-timedelta(days=1)),'fim':str(hoje+timedelta(days=1)),**kw})

def test_pedido_aprovado_sem_contrato_e_historico_sao_visiveis_sem_alterar_totais(visibilidade):
    http,_,sessoes,_=visibilidade;publicar(http);assert aprovar(http).status_code==200;entrar(http,'admin');antes=estado(sessoes)
    r=consulta(http);assert r.status_code==200,r.text;d=r.json()
    assert d['total']==0 and d['totais']['venda_cliente']=='0.00'
    p=next(p for p in d['acompanhamento']['pedidos']['itens'] if p['cotacao_id']==8)
    assert p['solicitacao_id']==9 and p['etapa']=='aprovada_cliente' and p['valor_cliente']=='1800.00'
    assert d['acompanhamento']['historico_anterior']['total']==3
    assert {c['contratacao_id'] for c in d['acompanhamento']['historico_anterior']['itens']}=={1,2,4}
    assert estado(sessoes)==antes

def test_confirmar_contrato_tira_pedido_da_fila_e_atualiza_resultado(visibilidade):
    http,_,_,_=visibilidade;publicar(http);assert aprovar(http).status_code==200;c=contratar(http)
    d=consulta(http).json();assert d['total']==1 and d['itens'][0]['contratacao_id']==c['contratacao_id']
    assert all(p['solicitacao_id']!=9 for p in d['acompanhamento']['pedidos']['itens'])
    assert all(h['contratacao_id']!=c['contratacao_id'] for h in d['acompanhamento']['historico_anterior']['itens'])
    assert d['totais']['ganho_bruto_previsto']=='300.00'

def test_paginacao_independente_e_periodo_filtram_consulta_completa(visibilidade):
    http,_,sessoes,_=visibilidade;antes=estado(sessoes)
    d=consulta(http,limite=1).json();assert len(d['acompanhamento']['historico_anterior']['itens'])==1
    total=d['acompanhamento']['pedidos']['total'];assert total>=2 and len(d['acompanhamento']['pedidos']['itens'])==1
    outro=consulta(http,limite=1,pedidos_deslocamento=100,historico_deslocamento=100).json()
    assert outro['acompanhamento']['pedidos']['itens']==[] and outro['acompanhamento']['pedidos']['total']==total
    assert outro['acompanhamento']['historico_anterior']['itens']==[] and outro['acompanhamento']['historico_anterior']['total']==3
    d=consulta(http,inicio='1900-01-01',fim='1900-01-01').json();assert not d['acompanhamento']['pedidos']['itens'] and not d['acompanhamento']['historico_anterior']['itens']
    assert estado(sessoes)==antes

def test_expiracao_e_solicitacao_sem_proposta_nao_criam_decisao(visibilidade):
    http,_,sessoes,_=visibilidade
    with sessoes() as b:b.get(CotacaoFornecedor,8).criada_em=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=99);b.commit()
    antes=estado(sessoes);d=consulta(http).json();p=d['acompanhamento']['pedidos']['itens']
    assert next(x for x in p if x['cotacao_id']==8)['etapa']=='expirada'
    assert any(x['cotacao_id'] is None and x['etapa']=='sem_proposta' for x in p)
    assert estado(sessoes)==antes

@pytest.mark.parametrize('perfil',['cliente','fornecedor'])
def test_novas_listas_exclusivas_administracao(visibilidade,perfil):
    http,_,sessoes,_=visibilidade;entrar(http,perfil);antes=estado(sessoes);r=consulta(http)
    assert r.status_code==403 and 'acompanhamento' not in r.text and estado(sessoes)==antes
