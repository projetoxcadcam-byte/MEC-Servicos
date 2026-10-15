"""Preserva estados e cotas, remove recursos privados e recusa divergência visual."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from contextlib import closing
import math
import pytest
from fastapi import HTTPException
from PIL import ImageChops
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, DecodedStreamObject, ContentStream, NumberObject
from reportlab.pdfgen import canvas
from backend.app.schemas.preparacao_pdf import AreaCarimbo
from backend.app.services import motor_pdf_cotacao as motor
from test_carimbo_compacto_d48_fix2 import campos, exemplo, LOGO
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload
from test_preparacao_pdf_d48 import contagens, pedido


def fluxo(dados):
    w = PdfWriter()
    p = w.add_blank_page(width=800, height=600)
    fonte = w._add_object(DictionaryObject({NameObject('/Type'):NameObject('/Font'), NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')}))
    p[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): fonte})})
    streams=[]
    for data in dados:
        s=DecodedStreamObject();s.set_data(data);streams.append(w._add_object(s))
    p[NameObject('/Contents')] = ArrayObject(streams)
    b=BytesIO();w.write(b)
    return b.getvalue()


def area():
    return AreaCarimbo(pagina=1,x=40/800,y=465/600,largura=550/800,altura=115/600,campos=campos())


def imprimir_pdf(transformacoes=True):
    # Global cm fora de q/Q e estados distribuídos em vários streams, como
    # arquivos de impressão CAD. Não contém o desenho privado do cliente.
    inicial=b'0.75 0 0 -0.75 0 600 cm\nq\n'
    tecnico=b'''q 1 0 0 1 240 160 cm
0 0 120 240 re S
BT /F1 14 Tf 1 0 0 -1 0 0 Tm (COTA 5.00) Tj ET
q 0 1 -1 0 130 0 cm
0 0 m 240 0 l S
BT /F1 14 Tf 1 0 0 -1 40 -8 Tm (25.30) Tj ET
Q
q 0 -1 1 0 -20 240 cm
0 0 m 240 0 l S
BT /F1 14 Tf 1 0 0 -1 45 -8 Tm (21.9) Tj ET
Q Q
'''
    legenda=b'''q
BT /F1 14 Tf 1 0 0 -1 65 685 Tm (CLIENTE CONFIDENCIAL) Tj ET
BT /F1 12 Tf 1 0 0 -1 65 710 Tm (projeto@privado.local) Tj ET
60 650 700 110 re S
Q Q
'''
    return fluxo([inicial,tecnico,legenda] if transformacoes else [b'1 0 0 1 0 0 cm q\n',b'BT /F1 12 Tf 1 0 0 1 60 300 Tm (COTA 25.30) Tj ET\n',b'BT /F1 12 Tf 1 0 0 1 60 100 Tm (CLIENTE CONFIDENCIAL) Tj ET Q\n'])


def imagem(dados, pagina=0):
    with pdfium.PdfDocument(dados) as doc, closing(doc[pagina]) as p:
        return motor._imagem_comparacao(p,2)


def fora_igual(original,saida,a):
    antes,depois=imagem(original),imagem(saida)
    try:
        d=ImageChops.difference(antes,depois)
        try:
            w,h=800,600
            d.paste((0,0,0),(math.floor(a.x*w*2)-1,math.floor(a.y*h*2)-1,math.ceil((a.x+a.largura)*w*2)+1,math.ceil((a.y+a.altura)*h*2)+1))
            assert d.getbbox() is None
        finally:d.close()
    finally:antes.close();depois.close()


@pytest.mark.parametrize('transformacoes',[True,False])
def test_cotas_rotacionadas_e_estados_entre_streams_permanecem(transformacoes):
    original=imprimir_pdf(transformacoes);a=area()
    saida=motor.preparar(original,[a],LOGO,'ARQUIVO-1')
    fora_igual(original,saida,a)
    txt=PdfReader(BytesIO(saida)).pages[0].extract_text()
    assert 'CLIENTE CONFIDENCIAL' not in txt and 'privado.local' not in txt
    assert '25.30' in txt
    if transformacoes:assert '21.9' in txt and '5.00' in txt
    # Conteúdo ainda vetorial e pilha de estados válida em todos os pontos.
    ops=PdfReader(BytesIO(saida)).pages[0].get_contents().operations
    nivel=0
    for _,op in ops:
        if op==b'q':nivel+=1
        if op==b'Q':nivel-=1
        assert nivel>=0
    assert nivel==0 and any(op==b'S' for _,op in ops)
    original_ops=PdfReader(BytesIO(original)).pages[0].get_contents().operations
    for operador in (b'cm',b'Tm'):
        fonte=[a for a,op in original_ops if op==operador]
        final=[a for a,op in ops if op==operador]
        assert final[:len(fonte)]==fonte


def test_geracao_nao_depende_da_regravacao_pdfium(monkeypatch):
    def proibido(*args,**kw):raise AssertionError('Regravação de objetos proibida')
    monkeypatch.setattr(pdfium.PdfPage,'gen_content',proibido)
    original=imprimir_pdf();assert motor.preparar(original,[area()],LOGO,'ARQUIVO-1').startswith(b'%PDF-')


@pytest.mark.parametrize('operador',[b"'",b'"'])
def test_elimina_caracteres_privados_preservando_parametros_de_texto(operador):
    prefixo=b'BT /F1 12 Tf 1 0 0 1 60 100 Tm 14 TL '
    mostrar=b'(CLIENTE CONFIDENCIAL) ' if operador==b"'" else b'2 1 (CLIENTE CONFIDENCIAL) '
    original=fluxo([prefixo+mostrar+operador+b' ET\nBT 1 0 0 1 60 300 Tm (COTA 25.30) Tj ET\n'])
    a=area();saida=motor.preparar(original,[a],LOGO,'ARQUIVO-1')
    fora_igual(original,saida,a)
    assert 'CLIENTE CONFIDENCIAL' not in PdfReader(BytesIO(saida)).pages[0].extract_text()


def test_bloco_texto_compartilhado_nao_apaga_cota_fora_da_legenda():
    original=fluxo([b'BT /F1 12 Tf 1 0 0 1 60 100 Tm (CLIENTE CONFIDENCIAL) Tj 0 200 Td (COTA 25.30) Tj ET\n'])
    with pytest.raises(HTTPException) as e:motor.preparar(original,[area()],LOGO,'ARQUIVO-1')
    assert e.value.detail=='area_corta_bloco_texto'


@pytest.mark.parametrize('conteudo',[b'Q\n',b'q\n',b'BT\n',b'ET\n',b'(CLIENTE) Tj\n'])
def test_estados_incompletos_sao_recusados(conteudo):
    original=fluxo([conteudo])
    with pytest.raises(HTTPException) as e:motor.preparar(original,[area()],LOGO,'ARQUIVO-1')
    assert e.value.detail=='pdf_estrutura_nao_suportada'


def test_divergencia_fora_da_area_e_recusada(monkeypatch):
    original,a=exemplo();carimbo=motor.carimbo
    def adulterado(*args,**kwargs):
        overlay=PdfReader(BytesIO(carimbo(*args,**kwargs)))
        b=BytesIO();c=canvas.Canvas(b,pagesize=(842,595));c.drawString(50,400,'COTA DESLOCADA');c.showPage();c.save()
        w=PdfWriter();p=w.add_page(overlay.pages[0]);p.merge_page(PdfReader(b).pages[0]);out=BytesIO();w.write(out);return out.getvalue()
    monkeypatch.setattr(motor,'carimbo',adulterado)
    with pytest.raises(HTTPException) as e:motor.preparar(original,[a],LOGO,'ARQUIVO-1')
    assert e.value.detail=='pdf_divergencia_fora_legenda'


def test_imagem_e_formulario_removidos_nao_permanecem_embutidos():
    original,a=exemplo();r=PdfReader(BytesIO(original));w=PdfWriter();p=w.add_page(r.pages[0])
    form=DecodedStreamObject();form.set_data(b'BT /F1 8 Tf 1 0 0 1 3 3 Tm (CLIENTE EMBUTIDO) Tj ET')
    form.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),NameObject('/BBox'):ArrayObject([NumberObject(v) for v in [0,0,100,20]]),NameObject('/Resources'):DictionaryObject({NameObject('/Font'):p['/Resources']['/Font']})})
    p['/Resources'][NameObject('/XObject')]=DictionaryObject({NameObject('/LogoPrivado'):w._add_object(form)})
    cs=p.get_contents();cs.operations += [([],b'q'),([NumberObject(v) for v in [1,0,0,1,300,45]],b'cm'),([NameObject('/LogoPrivado')],b'Do'),([],b'Q')]
    p.replace_contents(cs);out=BytesIO();w.write(out)
    saida=motor.preparar(out.getvalue(),[a],LOGO,'ARQUIVO-1')
    assert b'CLIENTE EMBUTIDO' not in saida
    assert '/LogoPrivado' not in PdfReader(BytesIO(saida)).pages[0]['/Resources']['/XObject']
    fora_igual(out.getvalue(),saida,AreaCarimbo(pagina=1,x=a.x*842/800,y=a.y*595/600,largura=a.largura*842/800,altura=a.altura*595/600,campos=campos()))


@pytest.mark.acesso_real
def test_comparacao_recusada_nao_cria_versao_ou_publicacao(ambiente,monkeypatch):
    http,_,sessoes,_=ambiente
    from test_preparacao_pdf_d48 import desenho
    arquivo=upload(http,conteudo=desenho());entrar(http,'admin')
    def recusar(*args,**kw):raise HTTPException(422,detail='pdf_divergencia_fora_legenda')
    monkeypatch.setattr(motor,'_conferir_preservacao_visual',recusar)
    r=http.post(BASE+f'/administracao/preparacao-pdf/arquivos/{arquivo["id"]}',json=pedido(arquivo))
    assert r.status_code==422 and r.json()['detail']=='pdf_divergencia_fora_legenda'
    assert contagens(sessoes)==(0,0,0)


def test_recurso_compartilhado_nao_e_removido_da_pagina_nao_editada():
    r=PdfReader(BytesIO(imprimir_pdf(False)));w=PdfWriter();p=w.add_page(r.pages[0])
    form=DecodedStreamObject();form.set_data(b"BT /F1 8 Tf 1 0 0 1 3 3 Tm (OBJETO COMPARTILHADO) Tj ET")
    form.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),NameObject('/BBox'):ArrayObject([NumberObject(v) for v in [0,0,100,20]]),NameObject('/Resources'):DictionaryObject({NameObject('/Font'):p['/Resources']['/Font']})})
    recursos=DictionaryObject(p['/Resources']);recursos[NameObject('/XObject')]=DictionaryObject({NameObject('/Compartilhado'):w._add_object(form)})
    ref=w._add_object(recursos);p[NameObject('/Resources')]=ref
    s=p.get_contents();s.operations += [([],b'q'),([NumberObject(v) for v in [1,0,0,1,300,65]],b'cm'),([NameObject('/Compartilhado')],b'Do'),([],b'Q')];p.replace_contents(s)
    segunda=w.add_blank_page(width=800,height=600);segunda[NameObject('/Resources')]=ref
    conteudo=DecodedStreamObject();conteudo.set_data(b'q 1 0 0 1 60 300 cm /Compartilhado Do Q')
    segunda[NameObject('/Contents')]=w._add_object(conteudo);buf=BytesIO();w.write(buf)
    original=buf.getvalue();saida=motor.preparar(original,[area()],LOGO,'ARQUIVO-1')
    antes,depois=imagem(original,1),imagem(saida,1)
    try:
        d=ImageChops.difference(antes,depois)
        try:assert d.getbbox() is None
        finally:d.close()
    finally:antes.close();depois.close()
    paginas=PdfReader(BytesIO(saida)).pages
    assert '/Compartilhado' not in paginas[0]['/Resources']['/XObject']
    assert '/Compartilhado' in paginas[1]['/Resources']['/XObject']


def test_geometria_do_logo_removido_nao_fica_oculta_no_stream():
    original=fluxo([b"q 61 65 m 117 74 l 61 83 l h f Q q 50 300 m 100 300 l S Q"])
    saida=motor.preparar(original,[area()],LOGO,'ARQUIVO-1')
    ops=PdfReader(BytesIO(saida)).pages[0].get_contents().operations
    assert not any(op==b'm' and list(a)==[61,65] for a,op in ops)
    assert not any(op==b'l' and list(a)==[117,74] for a,op in ops)
    assert any(op==b'm' and list(a)==[50,300] for a,op in ops)
    fora_igual(original,saida,area())
