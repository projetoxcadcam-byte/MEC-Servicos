"""D48: PDF real, autenticação real e publicação explícita de versão."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import hashlib
import pytest
from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from sqlalchemy import select
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload, corpo, oportunidades
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.documentacao_cotacao import EventoArquivoCotacao
from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao, PublicacaoPdfCotacao
from backend.app.schemas.preparacao_pdf import PrepararPdf
from backend.app.schemas.documentacao_cotacao import RegistroDocumentacao
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao
from backend.app.services.motor_pdf_cotacao import preparar, imagem_pagina

pytestmark = pytest.mark.acesso_real
PDF = BASE + '/administracao/preparacao-pdf'
DOC = BASE + '/administracao/documentacao-cotacao'
PORTAL = BASE + '/portal-fornecedor'
LOGO = Path(__file__).resolve().parents[1] / 'backend/app/assets/mec_logo_pdf.png'
ADMIN = UsuarioAcesso(1, 'Admin QA', 'admin@teste.local', 'admin', None, False)


def desenho(paginas=1):
    b=BytesIO();c=canvas.Canvas(b,pagesize=(800,600),invariant=1)
    c.setTitle('CLIENTE CONFIDENCIAL');c.setAuthor('DESENHISTA PRIVADO')
    for n in range(paginas):
        c.setFont('Helvetica',11);c.drawString(60,300,f'VISTA {n+1} - COTA 12.50 ±0.01')
        c.line(60,280,350,280);c.circle(200,380,40);c.rect(390,15,395,155)
        c.drawString(405,135,'CLIENTE CONFIDENCIAL - contato@privado.local')
        c.drawString(405,115,'DESENHISTA PRIVADO');c.drawString(405,95,'MATERIAL ORIGINAL TYRAX ESR');c.showPage()
    c.save();return b.getvalue()


def pedido(a, versao=0, **kw):
    return {'sha256':a['sha256'],'versao_liberacao':versao,'registro_interno':'Campos conferidos no desenho original.',
        'chave_operacao':str(uuid4()),'paginas':[{'pagina':1,'x':389/800,'y':429/600,'largura':397/800,'altura':157/600,
        'campos':{'descricao':'CAVIDADE SUPERIOR','codigo_tecnico':'0002','material':'TYRAX ESR','quantidade':20,
            'dureza':'56/58 HRC','tratamento_termico':'TEMP./REV.','revestimento':'---','escala':'2 : 1',
            'unidade':'mm','revisao':'--','tolerancias_gerais':"Geral ±0.1; 0.00 ±0.01; angular ±0°15'"}}],**kw}


def criar(http,a,**kw):
    entrar(http,'admin');r=http.post(PDF+f'/arquivos/{a["id"]}',json=pedido(a,**kw));assert r.status_code==200,r.text;return r.json()


def liberar(http,a,p=None,versao=0):
    entrar(http,'admin');r=http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,versao=versao,**({'preparacao_pdf_id':p['id']} if p else {})))
    assert r.status_code==200,r.text;return r.json()


def contagens(sessoes):
    with sessoes() as b:return tuple(len(b.scalars(select(t)).all()) for t in (PreparacaoPdfCotacao,PublicacaoPdfCotacao,EventoArquivoCotacao))


def test_preparacao_retem_especificacoes_remove_identidade_e_publica_somente_apos_revisao(ambiente):
    http,_,sessoes,_=ambiente;original=desenho();a=upload(http,conteudo=original);p=criar(http,a)
    assert p['versao']==1 and p['sha256_original']==a['sha256'] and oportunidades(http)['total']==0 and contagens(sessoes)==(1,0,0)
    entrar(http,'admin');r=http.get(PDF+f'/versoes/{p["id"]}/download');assert r.status_code==200
    neutro=r.content;txt=PdfReader(BytesIO(neutro)).pages[0].extract_text()
    for s in ['VISTA 1','COTA 12.50 ±0.01','TYRAX ESR','20','56/58 HRC','TEMP./REV.','±0.1','±0.01','2 : 1']:assert s in txt,s
    for s in ['CLIENTE CONFIDENCIAL','DESENHISTA PRIVADO','contato@privado.local']:assert s not in txt
    assert 'PRIVADO' not in str(PdfReader(BytesIO(neutro)).metadata)
    assert r.headers['cache-control']=='no-store' and r.headers['x-content-type-options']=='nosniff'
    info=http.get(PDF+f'/arquivos/{a["id"]}').json();assert info['paginas']==[dict(pagina=1,largura=800.,altura=600.)] and len(info['preparacoes'])==1
    for rota in [f'/arquivos/{a["id"]}/paginas/1?sha256={a["sha256"]}',f'/versoes/{p["id"]}/paginas/1']:
        r=http.get(PDF+rota);assert r.status_code==200 and r.content.startswith(b'\x89PNG') and r.headers['cache-control']=='no-store'
    d=liberar(http,a,p);assert d['preparacao_pdf_publicada_id']==p['id'] and d['versao_pdf_publicada']==1 and oportunidades(http)['total']==1
    lista=http.get(PORTAL+'/solicitacoes/3/arquivos',params={'empresa_fornecedora_id':4}).json()
    assert lista[0]['sha256']==p['sha256'] and lista[0]['tamanho_bytes']==len(neutro)
    assert 'registro_interno' not in str(lista) and 'PRIVADO' not in str(lista)
    r=http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={'empresa_fornecedora_id':4});assert r.content==neutro and r.content!=original
    entrar(http,'cliente');assert http.get(BASE+f'/arquivos-tecnicos/{a["id"]}/download').content==original
    with sessoes() as b:assert Path(b.get(ArquivoTecnico,a['id']).caminho_arquivo).read_bytes()==original
    assert contagens(sessoes)==(1,1,1)


@pytest.mark.parametrize('perfil',[None,'cliente','fornecedor'])
def test_preparacao_download_previa_e_historico_exigem_admin_real(ambiente,perfil):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());p=criar(http,a)
    if perfil:entrar(http,perfil)
    else:http.cookies.clear()
    esperado=403 if perfil else 401
    for rota in [f'/arquivos/{a["id"]}',f'/arquivos/{a["id"]}/paginas/1?sha256={a["sha256"]}',f'/versoes/{p["id"]}/download',f'/versoes/{p["id"]}/paginas/1']:
        assert http.get(PDF+rota,headers={'X-Perfil':'admin'}).status_code==esperado
    assert http.post(PDF+f'/arquivos/{a["id"]}',json=pedido(a),headers={'X-Perfil':'admin'}).status_code==esperado
    assert contagens(sessoes)==(1,0,0)


def test_csrf_sha_versao_e_perfil_forjado_nao_gravam(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());entrar(http,'admin');url=PDF+f'/arquivos/{a["id"]}'
    for dados,cabecalho,status in [(pedido(a),{'X-MEC-CSRF':'errado'},403),(pedido(a,sha256='f'*64),{},409),(pedido(a,versao_liberacao=2),{},409),(pedido(a,perfil='admin'),{},422)]:
        assert http.post(url,json=dados,headers=cabecalho).status_code==status
    assert contagens(sessoes)==(0,0,0)


def test_idempotencia_nao_duplica_pdf_nem_permite_corpo_divergente(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());entrar(http,'admin');url=PDF+f'/arquivos/{a["id"]}';dados=pedido(a)
    p=http.post(url,json=dados).json();assert http.post(url,json=dados).json()['id']==p['id']
    assert http.post(url,json={**dados,'registro_interno':'Outro registro.'}).status_code==409 and contagens(sessoes)==(1,0,0)
    with sessoes() as b:assert len(list(ServicoPreparacaoPdf(b).pasta.glob('*.pdf')))==1


def test_nova_copia_nao_muda_publicacao_e_reliberacao_preserva_historico(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());p=criar(http,a);liberar(http,a,p);q=criar(http,a,versao=1)
    assert q['id']!=p['id'] and q['versao']==2 and oportunidades(http)['total']==1
    r=http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={'empresa_fornecedora_id':4});assert hashlib.sha256(r.content).hexdigest()==p['sha256']
    d=liberar(http,a,q,versao=1);assert d['versao']==2 and d['preparacao_pdf_publicada_id']==q['id'] and len(d['historico'])==2 and contagens(sessoes)==(2,2,2)
    assert [h['versao_pdf_preparada'] for h in d['historico']]==[2,1]
    entrar(http,'admin');assert http.get(PDF+f'/versoes/{p["id"]}/download').status_code==200
    assert http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,versao=2,preparacao_pdf_id=q['id'])).status_code==409


def test_liberacao_idempotente_compara_preparacao_e_dados(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());p=criar(http,a);q=criar(http,a);entrar(http,'admin')
    dados=corpo(a,preparacao_pdf_id=p['id']);url=DOC+f'/arquivos/{a["id"]}/eventos'
    assert http.post(url,json=dados).status_code==200 and http.post(url,json=dados).status_code==200
    assert http.post(url,json={**dados,'preparacao_pdf_id':q['id']}).status_code==409 and contagens(sessoes)==(2,1,1)


def test_nao_publica_copia_de_outro_arquivo_ou_original_desvinculado(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());b=upload(http,conteudo=desenho());p=criar(http,a)
    assert http.post(DOC+f'/arquivos/{b["id"]}/eventos',json=corpo(b,preparacao_pdf_id=p['id'])).status_code==409
    entrar(http,'cliente');assert http.delete(BASE+f'/arquivos-tecnicos/{a["id"]}').status_code==204
    entrar(http,'admin');assert http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,preparacao_pdf_id=p['id'])).status_code==409
    assert contagens(sessoes)==(1,0,0)


@pytest.mark.parametrize('dano',['ausente','bytes','fora'])
def test_copia_liberada_danificada_nunca_retorna_original(ambiente,tmp_path,dano):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());p=criar(http,a);liberar(http,a,p)
    with sessoes() as b:
        preparado=b.get(PreparacaoPdfCotacao,p['id']);path=Path(preparado.caminho_arquivo)
        if dano=='ausente':path.unlink()
        elif dano=='bytes':path.write_bytes(b'x'*preparado.tamanho_bytes)
        else:
            externo=tmp_path/'externo.pdf';externo.write_bytes(path.read_bytes());preparado.caminho_arquivo=str(externo);b.commit()
    assert oportunidades(http)['total']==0
    assert http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={'empresa_fornecedora_id':4}).status_code==403
    assert http.get(PORTAL+'/solicitacoes/3/arquivos',params={'empresa_fornecedora_id':4}).status_code==403
    entrar(http,'admin');assert http.get(PDF+f'/versoes/{p["id"]}/download').status_code==409
    assert not http.get(DOC,params={'solicitacao_id':3}).json()['itens'][0]['arquivos'][0]['liberado'] and contagens(sessoes)==(1,1,1)


def test_pdf_original_revisado_continua_funcionando(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());liberar(http,a)
    assert oportunidades(http)['total']==1 and http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={'empresa_fornecedora_id':4}).content==desenho()
    assert contagens(sessoes)==(0,0,1)


@pytest.mark.parametrize('caso',['pagina','duplicada','nan','fora','zero','pequena','corta_texto','campo_longo','simbolo','vazio'])
def test_selecao_invalida_recusa_sem_copia_ou_registro(ambiente,caso):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());entrar(http,'admin');dados=pedido(a);area=dados['paginas'][0]
    if caso=='pagina':area['pagina']=2
    elif caso=='duplicada':dados['paginas'].append(area.copy())
    elif caso=='nan':area['x']='NaN'
    elif caso=='fora':area['x']=.9
    elif caso=='zero':area['largura']=0
    elif caso=='pequena':area['largura']=.1
    elif caso=='corta_texto':area['x']=450/800;area['largura']=.42
    elif caso=='campo_longo':area['campos']['descricao']='X'*80
    elif caso=='simbolo':area['campos']['material']='中文'
    else:area['campos']['material']='   '
    r=http.post(PDF+f'/arquivos/{a["id"]}',json=dados);assert r.status_code==422,(caso,r.text)
    assert contagens(sessoes)==(0,0,0)
    with sessoes() as b:assert not list(ServicoPreparacaoPdf(b).pasta.glob('*.pdf'))


@pytest.mark.parametrize('caso',['invalido','protegido','rotacao','recorte','anotacao','formulario'])
def test_pdf_nao_suportado_recusa_sem_gravar(ambiente,caso):
    from pypdf.generic import DictionaryObject,NameObject,ArrayObject,TextStringObject
    http,_,sessoes,_=ambiente;w=PdfWriter();w.append(BytesIO(desenho()))
    if caso=='protegido':w.encrypt('senha')
    elif caso=='rotacao':w.pages[0].rotate(90)
    elif caso=='recorte':w.pages[0].cropbox.lower_left=(2,2)
    elif caso=='anotacao':w.pages[0][NameObject('/Annots')]=ArrayObject([DictionaryObject({NameObject('/Subtype'):NameObject('/Text')})])
    elif caso=='formulario':w._root_object[NameObject('/AcroForm')]=DictionaryObject({NameObject('/Fields'):ArrayObject([DictionaryObject({NameObject('/FT'):NameObject('/Tx'),NameObject('/T'):TextStringObject('Cliente')})])})
    buf=BytesIO();w.write(buf);a=upload(http,conteudo=buf.getvalue() if caso!='invalido' else b'%PDF-1.4\ninvalido\n%%EOF');entrar(http,'admin')
    assert http.get(PDF+f'/arquivos/{a["id"]}').status_code==422
    assert http.post(PDF+f'/arquivos/{a["id"]}',json=pedido(a)).status_code==422 and contagens(sessoes)==(0,0,0)


def test_varias_paginas_somente_configuradas_mudam_e_metadados_nao_sao_copiados():
    original=desenho(2);area=PrepararPdf(**pedido({'sha256':hashlib.sha256(original).hexdigest()})).paginas[0]
    w=PdfWriter();w.append(BytesIO(original));w.add_attachment('contato.txt',b'CLIENTE PRIVADO');w.add_js("app.alert('cliente');");w.add_metadata({'/Author':'CLIENTE PRIVADO'});buf=BytesIO();w.write(buf)
    saida=preparar(buf.getvalue(),[area],LOGO,'ARQUIVO-1');r=PdfReader(BytesIO(saida))
    assert len(r.pages)==2 and r.pages[0].mediabox==r.pages[1].mediabox
    assert 'CLIENTE CONFIDENCIAL' not in r.pages[0].extract_text() and 'CLIENTE CONFIDENCIAL' in r.pages[1].extract_text() and 'VISTA 2' in r.pages[1].extract_text()
    assert not r.attachments and '/Names' not in r.trailer['/Root'] and '/OpenAction' not in r.trailer['/Root'] and 'CLIENTE PRIVADO' not in str(r.metadata)
    with pytest.raises(HTTPException) as e:imagem_pagina(saida,3)
    assert e.value.status_code==404


def test_reliberacao_concorrente_impede_preparacao_com_versao_antiga(ambiente,monkeypatch):
    import backend.app.services.motor_pdf_cotacao as motor
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());real=motor.preparar
    def alterar(*args,**kw):
        saida=real(*args,**kw)
        with sessoes() as b:ServicoDocumentacaoCotacao(b).registrar(a['id'],RegistroDocumentacao(**corpo(a)),ADMIN)
        return saida
    monkeypatch.setattr(motor,'preparar',alterar);entrar(http,'admin')
    assert http.post(PDF+f'/arquivos/{a["id"]}',json=pedido(a)).status_code==409 and contagens(sessoes)==(0,0,1)


def test_preparacoes_concorrentes_mesma_chave_sao_uma_unica_versao(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());dados=PrepararPdf(**pedido(a))
    def criar_em_sessao(_):
        with sessoes() as b:return ServicoPreparacaoPdf(b).criar(a['id'],dados,ADMIN).id
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(criar_em_sessao,range(2)))
    assert ids[0]==ids[1] and contagens(sessoes)==(1,0,0)
    with sessoes() as b:assert len(list(ServicoPreparacaoPdf(b).pasta.glob('*.pdf')))==1
