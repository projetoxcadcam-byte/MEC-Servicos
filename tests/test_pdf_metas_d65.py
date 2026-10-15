"""PDF das metas: escala física, valores, sigilo, versão e leitura pura."""
from copy import deepcopy
from io import BytesIO
import pytest
from pypdf import PdfReader
from test_metas_resultado_d64 import (
    metas,despesas,precificacao,comercial,ambiente,modelo_acessos,
    definir,retirar,comparar,liquidar,registrar,estornar,entrar,estado,METAS,ANO,
)
from backend.app.services.pdf_metas_resultado import gerar_pdf_metas

pytestmark=pytest.mark.acesso_real
PDF=METAS+'/pdf'

def baixar(http,r,**kw):return http.get(PDF,params={'ano':r['ano'],'versao':r['versao'],**kw})

def ler(resposta):
    assert resposta.status_code==200,resposta.text
    assert resposta.content.startswith(b'%PDF-') and resposta.headers['content-type']=='application/pdf'
    assert resposta.headers['cache-control']=='no-store'
    return PdfReader(BytesIO(resposta.content))

def texto(reader):return '\n'.join(p.extract_text() for p in reader.pages)

def conferir_escala(reader):
    fontes=[]
    for p in reader.pages:
        assert float(p.mediabox.width)==pytest.approx(841.89,abs=.1)
        assert float(p.mediabox.height)==pytest.approx(595.28,abs=.1)
        p.extract_text(visitor_text=lambda t,cm,tm,font,size:fontes.append(size) if t.strip() else None)
        assert 'Uso exclusivo do ADM' in p.extract_text() and 'Página ' in p.extract_text()
    assert min(fontes)>=8

def test_pdf_a4_horizontal_grafico_doze_meses_e_valores_do_csv(metas):
    http,_,sessoes,_,cid=metas
    assert definir(http,valor='2000.00').status_code==200
    assert registrar(http,cid,valor='50.01').status_code==200
    r=comparar(http);antes=estado(sessoes);resposta=baixar(http,r);reader=ler(resposta);conferir_escala(reader)
    t=texto(reader)
    for m in r['meses']:assert m['nome'] in t,m['nome']
    for v in ('2.000,00','-2.000,00','0,00%','249,99','250,00','50,01','Sem meta','Meta e resultado dos serviços liquidados','Abaixo da meta','Mês futuro','Comparação mensal'):
        assert v in t,v
    assert resposta.headers['x-mec-despesas-contexto']==r['contexto'] and resposta.headers['x-mec-relatorio-versao']==r['versao']
    assert f'MEC_SERVICOS_METAS_RESULTADO_{ANO}.pdf' in resposta.headers['content-disposition']
    assert estado(sessoes)==antes

def test_pdf_metas_restrito_tres_perfis_e_contexto_real(metas):
    http,_,sessoes,_,_=metas;r=comparar(http);antes=estado(sessoes)
    for perfil in ('cliente','fornecedor'):
        entrar(http,perfil);r2=baixar(http,r)
        assert r2.status_code==403 and not r2.content.startswith(b'%PDF-') and 'Meta total' not in r2.text
    http.cookies.clear();assert baixar(http,r).status_code==401
    entrar(http,'admin')
    assert http.get(PDF,params={'ano':ANO,'versao':r['versao']},headers={'X-MEC-Despesas-Contexto':'999:admin:0'}).status_code==409
    assert estado(sessoes)==antes

def test_pdf_antigo_recusado_apos_meta_despesa_estorno_e_liquidacao(metas):
    http,_,sessoes,_,cid=metas;r=comparar(http)
    assert definir(http,valor='2000.00').status_code==200 and baixar(http,r).status_code==409
    r=comparar(http);d=registrar(http,cid,valor='400.01').json();assert baixar(http,r).status_code==409
    r=comparar(http);liquidar(http,sessoes,cid);assert baixar(http,r).status_code==409
    r=comparar(http);t=texto(ler(baixar(http,r)));assert '-100,01' in t and '-5,00%' in t and '-2.100,01' in t
    assert estornar(http,cid,d['despesa_id']).status_code==200 and baixar(http,r).status_code==409
    r=comparar(http);assert retirar(http).status_code==200 and baixar(http,r).status_code==409
    assert 'Sem meta' in texto(ler(baixar(http,comparar(http))))

def test_pdf_filtros_repetidos_invalidos_e_ano_vazio(metas):
    http=metas[0];r=comparar(http)
    for kwargs in ({'ano':1899},{'ano':9999},{'mes':'2026-10'},{'limite':1},{'versao':'invalida'}):assert baixar(http,r,**kwargs).status_code==422
    assert http.get(PDF,params={'ano':ANO}).status_code==422
    assert http.get(PDF,params=[('ano',ANO),('versao',r['versao']),('ano',ANO)]).status_code==422
    vazio=comparar(http,1900);reader=ler(baixar(http,vazio));conferir_escala(reader);t=texto(reader)
    assert 'Sem meta' in t and 'R$ 0,00' in t and '01/1900' in t and '12/1900' in t

def test_pdf_valores_grandes_e_negativos_sem_reduzir_texto(metas):
    r=deepcopy(comparar(metas[0]));r['meta_total']='11999999999999.88';r['meses_com_meta']=12
    for m in r['meses']:
        m.update(meta='999999999999.99',diferenca='-1000000000100.00',atingimento_percentual='-0.00',situacao='abaixo')
        m['totais'].update(resultado_liquidado_apos_despesas='-100.01',resultado_previsto='999999999999.99',despesas_pagas='1000000000100.00',resultado_apos_despesas='-100.01')
    reader=PdfReader(BytesIO(gerar_pdf_metas(r)));conferir_escala(reader);t=texto(reader)
    assert '12/' in t and '999.999.999.999,99' in t and '-100,01' in t
    assert len(reader.pages)>=2 and len(reader.pages)<6
