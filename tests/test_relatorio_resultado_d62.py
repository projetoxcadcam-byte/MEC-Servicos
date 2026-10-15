"""Relatório reservado: precisão, histórico, exportação completa e snapshot."""
import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import event, select
from test_despesas_administracao_d61 import (
    despesas, precificacao, comercial, ambiente, modelo_acessos, entrar, registrar,
    estornar, resultado_d61, evento_fin, FIN, DES,
)
from test_janelas_d57 import estado
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.formacao_preco import FormacaoPreco
from backend.app.models.despesa_administracao import DespesaAdministracao
from backend.app.models.empresa import Empresa
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.intermediacao import CicloIntermediacao

pytestmark = pytest.mark.acesso_real
REL = DES + '/resultado/relatorio'
CSV = DES + '/resultado/csv'

def filtros(**kw):
    hoje = datetime.now(timezone.utc).date()
    return {'inicio': str(hoje - timedelta(days=1)), 'fim': str(hoje + timedelta(days=1)), **kw}

def obter(http, **kw):
    r = http.get(REL, params=filtros(**kw))
    assert r.status_code == 200, r.text
    assert r.headers['cache-control'] == 'no-store'
    return r.json()

def exportar(http, rel, **kw):
    return http.get(CSV, params={'inicio': rel['inicio'], 'fim': rel['fim'], 'versao': rel['versao'], **kw})

def linhas(r):
    assert r.status_code == 200, r.text
    assert r.content.startswith(b'\xef\xbb\xbf')
    return list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig')), delimiter=';'))

def clonar(banco, objeto, **trocas):
    dados = {c.name: getattr(objeto, c.name) for c in objeto.__table__.columns}
    copia = type(objeto)(**{**dados, **trocas})
    banco.add(copia)
    return copia

def test_despesas_reais_estornos_previsao_e_prejuizo_sem_gravacoes(despesas):
    http, _, sessoes, _, cid = despesas
    d = registrar(http, cid, valor='400.01').json()
    antes = estado(sessoes)
    r = obter(http)
    assert r['total'] == 1 and r['liquidadas'] == 0
    assert r['totais'] == resultado_d61(http).json()['totais']
    assert r['totais']['resultado_apos_despesas'] == '-100.01'
    assert r['totais']['resultado_previsto'] == '250.00'
    assert r['totais']['resultado_liquidado_apos_despesas'] == '0.00'
    assert r['despesas_confirmadas'] == 1 and r['despesas_estornadas'] == 0
    assert r['despesas'][0]['referencia'] == 'COMPROVANTE-RESERVADO-D61'
    csv_linhas = linhas(exportar(http, r))
    resumo = next(l for l in csv_linhas if l['Tipo de registro'] == 'Resumo do período')
    assert resumo['Resultado após despesas pagas (R$)'] == '-100,01'
    assert estado(sessoes) == antes
    assert estornar(http, cid, d['despesa_id'], registro_interno='Correção reservada do relatório D62').status_code == 200
    r = obter(http)
    assert r['totais']['despesas_pagas'] == '0.00' and r['totais']['resultado_apos_despesas'] == '300.00'
    assert r['valor_estornado'] == '400.01' and r['despesas_estornadas'] == 1
    assert r['despesas'][0]['motivo_estorno'] == 'Correção reservada do relatório D62'
    assert r['despesas'][0]['referencia_estorno'] == 'ESTORNO-RESERVADO-D61'
    assert next(l for l in linhas(exportar(http, r)) if l['Tipo de registro'] == 'Despesa')['Estado da despesa'] == 'Estornada'

def test_json_csv_restritos_ao_adm_e_contexto_exige_mesma_sessao(despesas):
    http, _, sessoes, _, cid = despesas
    assert registrar(http, cid).status_code == 200
    r = obter(http)
    antes = estado(sessoes)
    for perfil in ('cliente', 'fornecedor'):
        entrar(http, perfil)
        for rota, params in ((REL, filtros()), (CSV, {**filtros(), 'versao': r['versao']})):
            resposta = http.get(rota, params=params, headers={'X-MEC-PERFIL': 'admin'})
            assert resposta.status_code == 403
            assert 'COMPROVANTE-RESERVADO' not in resposta.text and 'custo_fornecedor' not in resposta.text
    http.cookies.clear()
    assert http.get(REL, params=filtros()).status_code == 401
    assert exportar(http, r).status_code == 401
    entrar(http, 'admin')
    for rota, params in ((REL, filtros()), (CSV, {**filtros(), 'versao': r['versao']})):
        assert http.get(rota, params=params, headers={'X-MEC-Despesas-Contexto': '999:admin:0'}).status_code == 409
    assert estado(sessoes) == antes

def test_filtros_invalidos_repetidos_e_paginacao_nao_sao_ignorados(despesas):
    http, _, sessoes, _, _ = despesas
    rel = obter(http)
    antes = estado(sessoes)
    invalidos = [
        {'inicio': '2026-10-15', 'fim': '2026-10-14'}, {'inicio': '1900-01-01'},
        {'inicio': '1899-12-31'}, {'fim': '9999-12-31'}, {'fim': 'não é uma data'},
        {'limite': '1'}, {'deslocamento': '20'}, {'empresa_cliente_id': '2'},
    ]
    for params in invalidos:
        assert http.get(REL, params=filtros(**params)).status_code == 422
        assert exportar(http, rel, **params).status_code == 422
    for rota in (REL, CSV):
        params = list(filtros().items()) + [('inicio', '2026-10-01')]
        if rota == CSV: params.append(('versao', rel['versao']))
        assert http.get(rota, params=params).status_code == 422
    assert http.get(CSV, params=filtros()).status_code == 422
    assert exportar(http, rel, versao='não é versão').status_code == 422
    assert estado(sessoes) == antes

def test_relatorio_e_csv_todas_paginas_com_dinheiro_exato_e_consultas_em_lote(despesas):
    http, _, sessoes, _, cid = despesas
    assert registrar(http, cid, valor='0.01').status_code == 200
    engine = sessoes.kw['bind']
    def consultar_contando():
        comandos = []
        def contar(cx, cur, sql, params, ctx, muitos): comandos.append(sql.strip().split()[0].upper())
        event.listen(engine, 'before_cursor_execute', contar)
        try: r = obter(http)
        finally: event.remove(engine, 'before_cursor_execute', contar)
        assert set(comandos) <= {'SELECT', 'BEGIN'}
        return r, comandos.count('SELECT')
    _, consultas_antes = consultar_contando()
    with sessoes() as b:
        c = b.get(ContratacaoServico, cid)
        q = b.get(CotacaoFornecedor, c.cotacao_id)
        s = b.get(SolicitacaoServico, c.solicitacao_id)
        p = b.get(FormacaoPreco, c.cotacao_id)
        d = b.scalar(select(DespesaAdministracao).where(DespesaAdministracao.contratacao_id == cid))
        for novo in range(100, 122):
            clonar(b, s, id=novo)
            clonar(b, q, id=novo, solicitacao_id=novo)
            clonar(b, c, id=novo, solicitacao_id=novo, cotacao_id=novo)
            b.flush()
            clonar(b, p, cotacao_id=novo, solicitacao_id=novo, contratacao_id=novo)
            clonar(b, d, id=novo, contratacao_id=novo)
        b.commit()
    antes = estado(sessoes)
    r, consultas_depois = consultar_contando()
    assert consultas_depois == consultas_antes
    assert r['total'] == 23 and len(r['itens']) == len(r['despesas']) == 23
    assert r['totais']['despesas_pagas'] == '0.23'
    assert r['totais']['venda_cliente'] == '41400.00'
    assert r['totais']['resultado_apos_despesas'] == '6899.77'
    pagina = resultado_d61(http, deslocamento=20, limite=1).json()
    assert len(pagina['itens']) == 1 and pagina['totais'] == r['totais']
    dados = linhas(exportar(http, r))
    assert len([d for d in dados if d['Tipo de registro'] == 'Contratação']) == 23
    assert len([d for d in dados if d['Tipo de registro'] == 'Despesa']) == 23
    assert len([d for d in dados if d['Tipo de registro'] == 'Resumo do período']) == 1
    assert estado(sessoes) == antes

def test_periodo_criacao_contrato_inclui_despesa_posterior_e_exclui_cancelada(despesas):
    http, _, sessoes, _, cid = despesas
    assert registrar(http, cid, paga_em='2026-10-14').status_code == 200
    with sessoes() as b: b.get(ContratacaoServico, cid).criada_em = datetime(2026, 10, 2, 23, 59, 59); b.commit()
    r = obter(http, inicio='2026-10-02', fim='2026-10-02')
    assert r['total'] == 1 and r['despesas'][0]['paga_em'] == '2026-10-14'
    assert r['totais']['despesas_pagas'] == '50.00'
    assert obter(http, inicio='2026-10-03', fim='2026-10-03')['total'] == 0
    with sessoes() as b: b.get(ContratacaoServico, cid).status = 'cancelada'; b.commit()
    antes = estado(sessoes)
    r = obter(http, inicio='2026-10-02', fim='2026-10-02')
    assert r['total'] == 0 and r['despesas'] == [] and r['totais']['despesas_pagas'] == '0.00'
    assert len(linhas(exportar(http, r))) == 1
    assert estado(sessoes) == antes

def test_csv_recusa_consulta_antiga_apos_gasto_estorno_e_liquidacao(despesas):
    http, _, sessoes, _, cid = despesas
    r = obter(http)
    assert obter(http)['versao'] == r['versao']
    assert exportar(http, r).status_code == 200
    d = registrar(http, cid).json()
    assert exportar(http, r).status_code == 409
    r = obter(http)
    assert estornar(http, cid, d['despesa_id']).status_code == 200
    assert exportar(http, r).status_code == 409
    r = obter(http)
    with sessoes() as b:
        o = b.scalar(select(OrdemServico).where(OrdemServico.contratacao_id == cid)); o.status = 'concluida'
        b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == o.id)).status = 'entregue_cliente'
        b.commit()
    assert http.post(FIN + f'/{cid}/iniciar', json={'registro_interno': 'Controle D62 local'}).status_code == 201
    assert evento_fin(http, cid, 'recebimento', valor='1800.00').status_code == 201
    assert evento_fin(http, cid, 'repasse', valor='1500.00').status_code == 201
    assert exportar(http, r).status_code == 409
    r = obter(http)
    assert r['liquidadas'] == 1 and r['totais']['resultado_liquidado_apos_despesas'] == '300.00'
    csv = exportar(http, r)
    assert csv.status_code == 200
    assert csv.headers['x-mec-relatorio-versao'] == r['versao']
    assert csv.headers['x-mec-despesas-contexto'] == r['contexto']
    assert csv.headers['x-content-type-options'] == 'nosniff'
    assert 'MEC_SERVICOS_RESULTADO_ADMIN_' in csv.headers['content-disposition']

def test_csv_preserva_acentos_aspas_linhas_e_neutraliza_formulas(despesas):
    http, _, sessoes, _, cid = despesas
    assert registrar(http, cid, descricao='Descrição; com "aspas"\nOutra linha.', referencia='=COMANDO()', registro_interno=' \t@COMANDO()').status_code == 200
    with sessoes() as b:
        b.get(Empresa, 2).razao_social = '\ufeff =COMANDO()'
        b.get(Empresa, 4).razao_social = '+COMANDO()'
        b.scalar(select(DespesaAdministracao)).administrador_nome = '-COMANDO()'
        b.commit()
    antes = estado(sessoes)
    dados = linhas(exportar(http, obter(http)))
    c = next(d for d in dados if d['Tipo de registro'] == 'Contratação')
    d = next(d for d in dados if d['Tipo de registro'] == 'Despesa')
    assert c['Cliente'] == "'\ufeff =COMANDO()" and c['Fornecedor'] == "'+COMANDO()"
    assert d['Referência'] == "'=COMANDO()" and d['Registro interno'] == "'@COMANDO()"
    assert d['Registrada por'] == "'-COMANDO()"
    assert d['Descrição'] == 'Descrição; com "aspas"\nOutra linha.'
    assert estado(sessoes) == antes

def test_mesma_leitura_de_saldos_e_despesas_durante_gravacao_concorrente(despesas):
    http, _, sessoes, _, cid = despesas
    assert registrar(http, cid).status_code == 200
    engine = sessoes.kw['bind']
    with engine.connect() as cx: cx.exec_driver_sql('PRAGMA journal_mode=WAL')
    feito = []
    def gravar(cx, cur, sql, params, ctx, muitos):
        if not feito and sql.startswith('SELECT contratacoes_servico.id') and 'sum(despesas_administracao.valor_centavos)' in sql:
            feito.append(True)
            with sessoes() as b:
                d = b.scalar(select(DespesaAdministracao)); d.valor_centavos = 9001; b.commit()
    event.listen(engine, 'after_cursor_execute', gravar)
    try: r = obter(http)
    finally: event.remove(engine, 'after_cursor_execute', gravar)
    assert feito
    assert r['totais']['despesas_pagas'] == '50.00' and r['despesas'][0]['valor'] == '50.00'
    r = obter(http)
    assert r['totais']['despesas_pagas'] == '90.01' and r['despesas'][0]['valor'] == '90.01'
