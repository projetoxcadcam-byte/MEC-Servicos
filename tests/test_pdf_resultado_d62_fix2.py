"""PDF físico, privado, completo e vinculado à versão consultada."""
from io import BytesIO
from copy import deepcopy
import pytest
from pypdf import PdfReader
from test_relatorio_resultado_d62 import despesas, precificacao, comercial, ambiente, modelo_acessos, obter, filtros, estado
from test_despesas_administracao_d61 import registrar, estornar, entrar, DES
from backend.app.services.pdf_resultado import gerar_pdf_resultado

PDF = DES + '/resultado/pdf'
pytestmark = pytest.mark.acesso_real

def baixar(http, r, **kw):
    return http.get(PDF, params={'inicio':r['inicio'],'fim':r['fim'],'versao':r['versao'],**kw})

def ler(r):
    assert r.status_code == 200, r.text
    assert r.content.startswith(b'%PDF-') and r.headers['content-type'] == 'application/pdf'
    assert r.headers['cache-control'] == 'no-store'
    return PdfReader(BytesIO(r.content))

def texto(reader):
    return '\n'.join(p.extract_text() for p in reader.pages)

def test_pdf_a4_horizontal_completo_com_valores_exatos_e_sem_gravar(despesas):
    http,_,sessoes,_,cid = despesas
    assert registrar(http,cid,valor='400.01').status_code == 200
    r = obter(http);antes=estado(sessoes);resposta=baixar(http,r);reader=ler(resposta)
    for pagina in reader.pages:
        assert float(pagina.mediabox.width) == pytest.approx(841.89,abs=.1)
        assert float(pagina.mediabox.height) == pytest.approx(595.28,abs=.1)
    t=texto(reader)
    for v in ('1.800,00','1.500,00','400,01','-100,01','250,00','COMPROVANTE-RESERVADO-D61','Coleta teste interno D61','Uso exclusivo do ADM'):
        assert v in t,v
    assert f'#{cid}' in t and 'Página 1' in t and 'Aguardando liquidação' in t
    assert resposta.headers['x-mec-relatorio-versao']==r['versao']
    assert resposta.headers['x-mec-despesas-contexto']==r['contexto']
    assert 'MEC_SERVICOS_RESULTADO_ADMIN_' in resposta.headers['content-disposition']
    assert estado(sessoes)==antes

def test_pdf_tres_perfis_anonimo_e_contexto_divergente(despesas):
    http,_,sessoes,_,cid=despesas
    assert registrar(http,cid).status_code==200
    r=obter(http);antes=estado(sessoes)
    for perfil in ('cliente','fornecedor'):
        entrar(http,perfil);res=baixar(http,r)
        assert res.status_code==403 and not res.content.startswith(b'%PDF-') and 'COMPROVANTE-RESERVADO' not in res.text
    http.cookies.clear();assert baixar(http,r).status_code==401
    entrar(http,'admin')
    assert http.get(PDF,params={**filtros(),'versao':r['versao']},headers={'X-MEC-Despesas-Contexto':'999:admin:0'}).status_code==409
    assert estado(sessoes)==antes

def test_pdf_antigo_recusado_apos_gasto_e_estorno(despesas):
    http,_,_,_,cid=despesas;r=obter(http)
    d=registrar(http,cid).json();assert baixar(http,r).status_code==409
    r=obter(http);assert '50,00' in texto(ler(baixar(http,r)))
    assert estornar(http,cid,d['despesa_id'],registro_interno='Motivo interno do estorno PDF').status_code==200
    assert baixar(http,r).status_code==409
    t=texto(ler(baixar(http,obter(http))))
    assert 'Estornada' in t and 'Motivo interno do estorno PDF' in t

def test_pdf_recusa_filtros_ambiguos_e_exporta_periodo_vazio(despesas):
    http=despesas[0];r=obter(http)
    for params in ({'fim':'9999-12-31'},{'limite':1},{'deslocamento':20},{'versao':'invalida'}):
        assert baixar(http,r,**params).status_code==422
    assert http.get(PDF,params=filtros()).status_code==422
    assert http.get(PDF,params=[*filtros().items(),('versao',r['versao']),('inicio','2026-10-01')]).status_code==422
    r=obter(http,inicio='1900-01-01',fim='1900-01-01')
    t=texto(ler(baixar(http,r)));assert 'Nenhuma contratação' in t and 'R$ 0,00' in t

def test_pdf_multipagina_nao_reduz_e_conserva_ultima_contratacao(despesas):
    r=obter(despesas[0]);base=r['itens'][0];r=deepcopy(r)
    r['itens']=[{**base,'contratacao_id':i,'cliente':'Cliente completo '+str(i),'fornecedor':'Fornecedor '+str(i)} for i in range(100,160)]
    r['total']=len(r['itens'])
    for k in r['totais']:r['totais'][k]=str(__import__('decimal').Decimal(base[k])*60)
    reader=PdfReader(BytesIO(gerar_pdf_resultado(r)));assert len(reader.pages)>3
    t=texto(reader);assert '#159' in t and 'Cliente completo 159' in t
    assert all('MEC-Serviços' in p.extract_text() and 'Página ' in p.extract_text() for p in reader.pages)
    fontes=[]
    for p in reader.pages:p.extract_text(visitor_text=lambda t,cm,tm,font,size:fontes.append(size) if t.strip() else None)
    assert min(fontes)>=8

def test_pdf_texto_longo_e_marcacao_literal_sem_erro_de_paginacao(despesas):
    http,_,_,_,cid=despesas
    assert registrar(http,cid,descricao='<b>Descrição literal</b>',registro_interno='Informação longa de teste. '*70+'FIM-DO-REGISTRO-LONGO').status_code==200
    reader=ler(baixar(http,obter(http)));t=texto(reader)
    assert len(reader.pages)>=3
    assert '<b>Descrição literal</b>' in t and 'FIM-DO-REGISTRO-LONGO' in t
