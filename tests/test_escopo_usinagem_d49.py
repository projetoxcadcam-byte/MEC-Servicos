"""Escopo por página, legado idempotente e publicação explícita da nova cópia."""
from io import BytesIO
import hashlib
import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from backend.app.schemas.preparacao_pdf import AreaCarimbo, CamposCarimbo
from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao
from backend.app.services.motor_pdf_cotacao import carimbo
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload
from test_preparacao_pdf_d48 import desenho, pedido, criar, liberar, contagens, PDF, PORTAL, LOGO
from test_carimbo_compacto_d48_fix2 import exemplo, campos


@pytest.mark.parametrize("escopo,label", [
    ("desbaste", "Somente desbaste"), ("acabamento", "Somente acabamento"),
    ("peca_completa", "Peca completa")])
def test_escopo_sem_tolerancias_ou_sobremetal_inventados(escopo, label):
    _, a = exemplo(318, 94)
    dados = campos()
    for nome in ("dureza", "tratamento_termico", "revestimento", "revisao", "tolerancias_gerais"):
        dados.pop(nome)
    dados["escopo_servico"] = escopo
    a.campos = CamposCarimbo(**dados)
    pdf = carimbo(842, 595, a, LOGO, "ARQUIVO-1")
    texto = PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert label in texto and "FORMADUR 2083" in texto
    assert "Sobremetal:" not in texto and "Tolerancias:" not in texto and "Dureza:" not in texto
    assert "49 - 51 HRC" not in texto and "±0.01" not in texto


@pytest.mark.parametrize("largura,altura", [(320,96), (550,112), (320,132)])
def test_escopo_e_dados_informados_legiveis_dentro_da_legenda(largura, altura):
    _, a = exemplo(largura-2, altura-2)
    a.campos = CamposCarimbo(**{**campos(), "descricao": "INSERTO", "escopo_servico": "desbaste",
        "sobremetal": "0,5 mm nas faces", "observacoes_servico": "Sem tratamento termico.",
        "dureza": "", "tratamento_termico": "", "revestimento": "", "revisao": "A", "tolerancias_gerais": ""})
    pagina = PdfReader(BytesIO(carimbo(842,595,a,LOGO,"ARQUIVO-1"))).pages[0]
    valores = []
    def visitar(t, cm, tm, fonte, tamanho):
        valor = t.strip()
        if not valor: return
        x, y = tm[4], tm[5]
        font = "Helvetica-Bold" if fonte and "Bold" in str(fonte.get("/BaseFont")) else "Helvetica"
        assert x >= a.x*842-0.001
        assert x+stringWidth(valor,font,tamanho) <= (a.x+a.largura)*842+0.001
        assert 595-(a.y+a.altura)*595 < y-tamanho*.25 < y+tamanho <= 595-a.y*595
        if "Somente" in valor or "Sobremetal:" in valor or "FORMADUR" in valor:
            assert tamanho == 7.2
        valores.append(valor)
    pagina.extract_text(visitor_text=visitar)
    texto = " ".join(valores)
    assert "Somente desbaste; Sobremetal: 0,5 mm nas faces" in texto
    assert "Observacoes: Sem tratamento termico." in texto and "Revisao: A" in texto


@pytest.mark.parametrize("campo,valor", [("escopo_servico","ambos"), ("escopo_servico",""),
    ("sobremetal","x"*81), ("observacoes_servico","x"*181), ("sobremetal","1 mm\x00"),
    ("observacoes_servico","中文")])
def test_campos_incompativeis_sao_recusados(campo, valor):
    with pytest.raises(ValidationError): CamposCarimbo(**{**campos(), campo: valor})


def test_servico_longo_e_recusado_sem_cortar_informacoes():
    _, a = exemplo(318,94)
    a.campos = CamposCarimbo(**{**campos(), "escopo_servico":"desbaste",
        "observacoes_servico":"Operacoes acordadas: " + "Face inferior e superior. "*6})
    with pytest.raises(HTTPException) as erro: carimbo(842,595,a,LOGO,"ARQUIVO-1")
    assert erro.value.detail == "texto_nao_cabe_no_carimbo"


@pytest.mark.acesso_real
def test_repetir_pedido_da_d48_preserva_digest_configuracao_e_versao(ambiente):
    http,_,sessoes,_ = ambiente
    a = upload(http,conteudo=desenho()); dados = pedido(a); entrar(http,"admin")
    url = PDF+f'/arquivos/{a["id"]}'
    r = http.post(url,json=dados); assert r.status_code==200,r.text
    p = r.json()
    # Corpo e configuração realmente usados antes da introdução dos campos D49.
    antigo = hashlib.sha256(json.dumps(dados,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    configuracao = json.dumps(dados["paginas"],ensure_ascii=False)
    with sessoes() as db:
        registro = db.get(PreparacaoPdfCotacao,p["id"])
        assert registro.pedido_sha256 == antigo and registro.configuracao_json == configuracao
    novo = json.loads(json.dumps(dados))
    novo["paginas"][0]["campos"].update(escopo_servico="conforme_solicitacao",sobremetal="",observacoes_servico="")
    for corpo in (dados, novo):
        r = http.post(url,json=corpo); assert r.status_code==200,r.text
        assert r.json()["id"] == p["id"] and r.json()["paginas"][0]["campos"]["escopo_servico"] == "conforme_solicitacao"
    with sessoes() as db:
        registro = db.get(PreparacaoPdfCotacao,p["id"])
        assert registro.pedido_sha256 == antigo and registro.configuracao_json == configuracao
    novo["paginas"][0]["campos"]["escopo_servico"] = "desbaste"
    assert http.post(url,json=novo).status_code==409 and contagens(sessoes)==(1,0,0)


@pytest.mark.acesso_real
def test_novo_escopo_so_chega_ao_fornecedor_apos_revisao_e_liberacao(ambiente):
    http,_,sessoes,_ = ambiente; original = desenho(); a = upload(http,conteudo=original)
    anterior = criar(http,a); liberar(http,a,anterior)
    bytes_anteriores = http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={"empresa_fornecedora_id":4}).content
    dados = pedido(a,versao=1,registro_interno="Anotacao interna D49 que nao vai ao fornecedor.")
    dados["paginas"][0]["campos"].update(escopo_servico="desbaste",sobremetal="0,5 mm nas faces",
        observacoes_servico="Entregar sem tratamento termico.",tolerancias_gerais="",dureza="",tratamento_termico="",revestimento="")
    entrar(http,"admin"); r = http.post(PDF+f'/arquivos/{a["id"]}',json=dados)
    assert r.status_code==200,r.text
    p = r.json(); assert p["versao"]==2 and p["paginas"][0]["campos"]["tolerancias_gerais"]==""
    copia = http.get(PDF+f'/versoes/{p["id"]}/download').content
    texto = " ".join(PdfReader(BytesIO(copia)).pages[0].extract_text().split())
    assert "Somente desbaste" in texto and "Sobremetal: 0,5 mm nas faces" in texto
    assert "Entregar sem tratamento termico." in texto and "Anotacao interna" not in texto
    assert "COTA 12.50 ±0.01" in texto and "CLIENTE CONFIDENCIAL" not in texto
    assert contagens(sessoes)==(2,1,1)
    entrar(http,"fornecedor")
    assert http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={"empresa_fornecedora_id":4}).content==bytes_anteriores
    liberar(http,a,p,versao=1)
    assert http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={"empresa_fornecedora_id":4}).content==copia
    assert contagens(sessoes)==(2,2,2)
    entrar(http,"cliente")
    assert http.get(BASE+f'/arquivos-tecnicos/{a["id"]}/download').content==original


@pytest.mark.acesso_real
@pytest.mark.parametrize("perfil", [None,"cliente","fornecedor"])
def test_escopo_nao_permite_preparacao_por_outro_perfil(ambiente,perfil):
    http,_,sessoes,_ = ambiente; a=upload(http,conteudo=desenho()); dados=pedido(a)
    dados["paginas"][0]["campos"].update(escopo_servico="desbaste",tolerancias_gerais="")
    if perfil: entrar(http,perfil)
    else: http.cookies.clear()
    assert http.post(PDF+f'/arquivos/{a["id"]}',json=dados,headers={"X-Perfil":"admin"}).status_code==(403 if perfil else 401)
    assert contagens(sessoes)==(0,0,0)


@pytest.mark.acesso_real
def test_paginas_com_servicos_diferentes_mantem_seus_escopos(ambiente):
    http,_,sessoes,_=ambiente; a=upload(http,conteudo=desenho(2)); dados=pedido(a)
    segunda=json.loads(json.dumps(dados["paginas"][0])); segunda["pagina"]=2
    dados["paginas"].append(segunda)
    for pagina,escopo in zip(dados["paginas"],("desbaste","acabamento")):
        pagina["campos"].update(escopo_servico=escopo,tolerancias_gerais="",dureza="",
            tratamento_termico="",revestimento="")
    entrar(http,"admin"); r=http.post(PDF+f'/arquivos/{a["id"]}',json=dados)
    assert r.status_code==200,r.text
    p=r.json(); assert [v["campos"]["escopo_servico"] for v in p["paginas"]]==["desbaste","acabamento"]
    pdf=PdfReader(BytesIO(http.get(PDF+f'/versoes/{p["id"]}/download').content))
    for n,label in enumerate(("Somente desbaste","Somente acabamento")):
        texto=pdf.pages[n].extract_text()
        assert label in texto and f"VISTA {n+1}" in texto
        assert ("Somente acabamento" if n==0 else "Somente desbaste") not in texto
    assert contagens(sessoes)==(1,0,0)
