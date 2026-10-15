"""Carimbo baixo: preservação visual, texto legível e publicação explícita."""
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import hashlib
import math
import pytest
from PIL import ImageChops
import pypdfium2 as pdfium
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from backend.app.schemas.preparacao_pdf import AreaCarimbo
from backend.app.services.motor_pdf_cotacao import preparar, carimbo
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload, corpo, oportunidades
from test_preparacao_pdf_d48 import contagens

LOGO = Path(__file__).resolve().parents[1] / 'backend/app/assets/mec_logo_pdf.png'
PDF = BASE + '/administracao/preparacao-pdf'
DOC = BASE + '/administracao/documentacao-cotacao'
PORTAL = BASE + '/portal-fornecedor'

def campos():
    return dict(descricao='INSERTO DE SAIDA DE GASES', codigo_tecnico='P0002',
        material='FORMADUR 2083', quantidade=18, dureza='49 - 51 HRC',
        tratamento_termico='TEMP./REVEN.', revestimento='--', escala='3 : 1',
        unidade='mm', revisao='A', tolerancias_gerais="Geral ±0.1; 0.00 ±0.01; angular ±0°15'")

def exemplo(largura=550, altura=112):
    w, h, x, y = 842, 595, 40, 20
    b = BytesIO(); c = canvas.Canvas(b, pagesize=(w, h), invariant=1)
    c.setFont('Helvetica', 10)
    c.drawString(x, y + altura + 16, '#1 = DEMAIS DIMENSOES CONFORME MODELAMENTO 3D.')
    c.drawString(60, 300, 'COTA 14.9 - USINAR MONTADO COM A POSICAO 1')
    c.line(60, 280, 350, 280); c.circle(230, 370, 30)
    c.rect(x, y, largura, altura)
    c.drawString(x + 8, y + altura - 18, 'CLIENTE CONFIDENCIAL')
    c.drawString(x + 8, y + altura - 34, 'projeto - contato@cliente.local')
    c.showPage(); c.save()
    a = AreaCarimbo(pagina=1, x=(x-1)/w, y=(h-y-altura-1)/h,
        largura=(largura+2)/w, altura=(altura+2)/h, campos=campos())
    return b.getvalue(), a

@pytest.mark.parametrize('largura,altura', [(550,112),(500,100),(450,96),(320,96),(320,132),(450,150)])
def test_legenda_baixa_mantem_todas_as_especificacoes(largura, altura):
    original, area = exemplo(largura, altura)
    saida = preparar(original, [area], LOGO, 'ARQUIVO-1')
    texto = PdfReader(BytesIO(saida)).pages[0].extract_text()
    for valor in campos().values(): assert str(valor) in texto
    assert '#1 = DEMAIS DIMENSOES' in texto and 'COTA 14.9' in texto
    assert 'CLIENTE CONFIDENCIAL' not in texto and 'contato@cliente.local' not in texto

@pytest.mark.parametrize('altura', [96, 112, 131.999, 132, 150])
def test_modelo_nao_pinta_fora_da_area_selecionada(altura):
    original, a = exemplo(500, altura)
    saida = preparar(original, [a], LOGO, 'ARQUIVO-1')
    def imagem(dados):
        with pdfium.PdfDocument(dados) as doc:
            bitmap = doc[0].render(scale=2)
            try:
                im = bitmap.to_pil(); copia = im.convert("RGB"); im.close(); return copia
            finally: bitmap.close()
    antes, depois = imagem(original), imagem(saida)
    # Margem de um pixel para o antialiasing das bordas exatamente selecionadas.
    x0,y0 = math.floor(a.x*842*2)-1, math.floor(a.y*595*2)-1
    x1,y1 = math.ceil((a.x+a.largura)*842*2)+1, math.ceil((a.y+a.altura)*595*2)+1
    diferenca = ImageChops.difference(antes,depois)
    diferenca.paste((0,0,0),(x0,y0,x1,y1))
    assert diferenca.getbbox() is None
    antes.close(); depois.close(); diferenca.close()

@pytest.mark.parametrize('altura', [96, 100, 112, 132])
def test_textos_do_carimbo_nao_sao_reduzidos_ou_cortados(altura):
    _, a = exemplo(550, altura)
    pagina = PdfReader(BytesIO(carimbo(842, 595, a, LOGO, 'ARQUIVO-1'))).pages[0]
    encontrados = []
    def texto(t, cm, tm, font, size):
        valor = t.strip()
        if not valor: return
        x, y = tm[4], tm[5]
        limite_x = (a.x+a.largura)*842
        assert x >= a.x*842-0.001
        assert x+stringWidth(valor, 'Helvetica-Bold' if font and 'Bold' in str(font.get('/BaseFont')) else 'Helvetica', size) <= limite_x+0.001
        assert 595-(a.y+a.altura)*595 < y-size*.25 < y+size <= 595-a.y*595
        if valor in map(str, campos().values()): assert size == 7.2
        encontrados.append(valor)
    pagina.extract_text(visitor_text=texto)
    assert 'FORMADUR 2083' in encontrados

@pytest.mark.parametrize('largura,altura', [(319,112),(550,95),(100,50)])
def test_area_sem_espaco_legivel_e_recusada(largura, altura):
    _, a = exemplo(largura-2, altura-2)
    with pytest.raises(HTTPException) as erro: carimbo(842,595,a,LOGO,'ARQUIVO-1')
    assert erro.value.detail == 'area_carimbo_muito_pequena'

def test_texto_longo_nao_e_truncado_para_forcar_carimbo_compacto():
    _, a = exemplo(318,94)
    a.campos.descricao = 'W' * 80
    with pytest.raises(HTTPException) as erro: carimbo(842,595,a,LOGO,'ARQUIVO-1')
    assert erro.value.detail == 'texto_nao_cabe_no_carimbo'

@pytest.mark.acesso_real
def test_legenda_a4_compacta_e_publicada_so_apos_revisao(ambiente):
    http, _, sessoes, _ = ambiente
    original, a = exemplo()
    arquivo = upload(http, conteudo=original)
    entrar(http, 'admin')
    dados = dict(sha256=arquivo['sha256'], versao_liberacao=0, paginas=[a.model_dump()],
        registro_interno='Legenda baixa e especificações conferidas.', chave_operacao=str(uuid4()))
    r = http.post(PDF+f'/arquivos/{arquivo["id"]}', json=dados)
    assert r.status_code == 200, r.text
    p = r.json()
    assert contagens(sessoes) == (1,0,0) and oportunidades(http)['total'] == 0
    entrar(http,'admin'); copia = http.get(PDF+f'/versoes/{p["id"]}/download').content
    assert hashlib.sha256(copia).hexdigest() == p['sha256']
    r = http.post(DOC+f'/arquivos/{arquivo["id"]}/eventos',json=corpo(arquivo,preparacao_pdf_id=p['id']))
    assert r.status_code == 200 and r.json()['preparacao_pdf_publicada_id'] == p['id']
    assert oportunidades(http)['total'] == 1
    assert http.get(PORTAL+f'/arquivos/{arquivo["id"]}/download',params={'empresa_fornecedora_id':4}).content == copia
    entrar(http,'cliente'); assert http.get(BASE+f'/arquivos-tecnicos/{arquivo["id"]}/download').content == original
