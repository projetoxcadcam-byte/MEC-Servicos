"""Catálogo editável, serviços combinados por página e compatibilidade das cópias anteriores."""
from io import BytesIO
import hashlib
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from pypdf import PdfReader
from backend.app.schemas.preparacao_pdf import CamposCarimbo
from backend.app.services.motor_pdf_cotacao import carimbo
from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload
from test_preparacao_pdf_d48 import desenho, pedido, criar, liberar, contagens, PDF, PORTAL, LOGO
from test_carimbo_compacto_d48_fix2 import exemplo, campos


def basicos(**novos):
    return {**campos(), "dureza": "", "tratamento_termico": "", "revestimento": "",
            "revisao": "", "tolerancias_gerais": "", **novos}


@pytest.mark.parametrize("operacoes,textos", [
    (["usinagem"], ["Usinagem"]), (["dobra"], ["Dobra"]),
    (["solda_mig_mag"], ["Solda MIG/MAG"]), (["pintura_po"], ["Pintura a po"]),
    (["usinagem", "dobra", "solda_tig", "pintura_liquida"], ["Usinagem", "Dobra", "Solda TIG", "Pintura liquida"]),
    (["corte_laser", "calandragem", "montagem"], ["Corte a laser", "Calandragem", "Montagem"]),
])
def test_operacoes_informadas_entram_na_legenda_sem_especificacoes_inventadas(operacoes, textos):
    _, area = exemplo(478, 115)
    area.campos = CamposCarimbo(**basicos(material="Alumínio 6061", operacoes_servico=operacoes))
    pagina = PdfReader(BytesIO(carimbo(842, 595, area, LOGO, "ARQUIVO-TESTE"))).pages[0]
    texto = " ".join(pagina.extract_text().split())
    for valor in textos: assert valor in texto
    assert "Operacoes:" in texto and "Alumínio 6061" in texto
    for valor in ("Tolerancias:", "Sobremetal:", "Dureza:", "Somente desbaste", "Tratamento:"):
        assert valor not in texto


@pytest.mark.parametrize("valor", [
    ["servico_desconhecido"], ["dobra", "dobra"],
    ["usinagem", "torneamento", "fresamento", "furacao", "rosqueamento", "mandrilamento", "chaveta", "retifica", "dobra"],
    "dobra", {"dobra": True}, [None], [1], None,
])
def test_operacoes_invalidas_sao_recusadas(valor):
    with pytest.raises(ValidationError): CamposCarimbo(**basicos(operacoes_servico=valor))


@pytest.mark.parametrize("material", ["Bronze", "Acetal / POM", "Aço inox AISI 316L", "Material próprio QA, conforme desenho"])
def test_material_livre_continua_editavel(material):
    _, area = exemplo(478,115)
    area.campos = CamposCarimbo(**basicos(material=material, operacoes_servico=["usinagem"]))
    texto = " ".join(PdfReader(BytesIO(carimbo(842,595,area,LOGO,"ARQUIVO-TESTE"))).pages[0].extract_text().split())
    assert material in texto


def test_dados_antigos_nao_recebem_operacoes_retroativas():
    dados = CamposCarimbo(**campos())
    assert dados.operacoes_servico == [] and "operacoes_servico" not in dados.dados_persistentes()
    assert dados.dados_persistentes() == campos()


def test_operacoes_e_observacoes_longas_nao_sao_cortadas_para_caber():
    _, area = exemplo(318,94)
    area.campos = CamposCarimbo(**basicos(operacoes_servico=["usinagem","dobra","solda_tig","pintura_po"],
        observacoes_servico="Requisitos definidos: " + "Manter notas e especificacoes. " * 5))
    with pytest.raises(HTTPException) as erro: carimbo(842,595,area,LOGO,"ARQUIVO-TESTE")
    assert erro.value.detail == "texto_nao_cabe_no_carimbo"


@pytest.mark.acesso_real
def test_pedido_antigo_e_operacoes_vazias_mantem_hash_e_versao(ambiente):
    http, _, sessoes, _ = ambiente; arquivo = upload(http, conteudo=desenho()); dados = pedido(arquivo)
    entrar(http,"admin"); url=PDF+f'/arquivos/{arquivo["id"]}'
    r=http.post(url,json=dados); assert r.status_code==200,r.text
    preparacao=r.json(); antigo=hashlib.sha256(json.dumps(dados,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    com_padrao=json.loads(json.dumps(dados)); com_padrao["paginas"][0]["campos"]["operacoes_servico"]=[]
    repetido=http.post(url,json=com_padrao); assert repetido.status_code==200,repetido.text
    assert repetido.json()["id"]==preparacao["id"] and contagens(sessoes)==(1,0,0)
    with sessoes() as db:
        salvo=db.get(PreparacaoPdfCotacao,preparacao["id"])
        assert salvo.pedido_sha256==antigo and salvo.configuracao_json==json.dumps(dados["paginas"],ensure_ascii=False)
    assert repetido.json()["paginas"][0]["campos"]["operacoes_servico"]==[]


@pytest.mark.acesso_real
def test_operacoes_nao_tem_ordem_implicita_e_idempotencia_detecta_mudanca(ambiente):
    http, _, sessoes, _ = ambiente; arquivo=upload(http,conteudo=desenho()); dados=pedido(arquivo)
    dados["paginas"][0]["campos"].update(basicos(operacoes_servico=["pintura_po","dobra","usinagem"]))
    entrar(http,"admin"); url=PDF+f'/arquivos/{arquivo["id"]}'
    r=http.post(url,json=dados); assert r.status_code==200,r.text
    p=r.json(); assert p["paginas"][0]["campos"]["operacoes_servico"]==["usinagem","dobra","pintura_po"]
    dados["paginas"][0]["campos"]["operacoes_servico"].reverse()
    repetido=http.post(url,json=dados); assert repetido.status_code==200,repetido.text
    assert repetido.json()["id"]==p["id"]
    dados["paginas"][0]["campos"]["operacoes_servico"].append("montagem")
    assert http.post(url,json=dados).status_code==409 and contagens(sessoes)==(1,0,0)


@pytest.mark.acesso_real
def test_servicos_distintos_por_pagina_so_sao_publicados_apos_revisao(ambiente):
    http, _, sessoes, _=ambiente; original=desenho(2); arquivo=upload(http,conteudo=original)
    velha=criar(http,arquivo); liberar(http,arquivo,velha)
    anterior=http.get(PORTAL+f'/arquivos/{arquivo["id"]}/download',params={"empresa_fornecedora_id":4}).content
    dados=pedido(arquivo,versao=1,registro_interno="Registro privado D51 de teste.")
    segunda=json.loads(json.dumps(dados["paginas"][0]));segunda["pagina"]=2;dados["paginas"].append(segunda)
    for pagina,operacoes,material in zip(dados["paginas"],(["usinagem","dobra"],["solda_tig","pintura_liquida"]),("Aço carbono SAE 1020","Material próprio QA")):
        pagina["campos"].update(basicos(material=material,operacoes_servico=operacoes))
    entrar(http,"admin");r=http.post(PDF+f'/arquivos/{arquivo["id"]}',json=dados);assert r.status_code==200,r.text
    p=r.json(); assert p["versao"]==2 and contagens(sessoes)==(2,1,1)
    copia=http.get(PDF+f'/versoes/{p["id"]}/download').content;leitor=PdfReader(BytesIO(copia))
    primeira=" ".join(leitor.pages[0].extract_text().split()); segunda=" ".join(leitor.pages[1].extract_text().split())
    assert "Operacoes: Usinagem, Dobra" in primeira and "Solda TIG" not in primeira
    assert "Operacoes: Solda TIG, Pintura liquida" in segunda and "Usinagem" not in segunda
    assert "VISTA 1" in primeira and "VISTA 2" in segunda and "COTA 12.50 ±0.01" in primeira
    assert "Registro privado" not in primeira+segunda
    entrar(http,"fornecedor")
    assert http.get(PORTAL+f'/arquivos/{arquivo["id"]}/download',params={"empresa_fornecedora_id":4}).content==anterior
    liberar(http,arquivo,p,versao=1)
    assert http.get(PORTAL+f'/arquivos/{arquivo["id"]}/download',params={"empresa_fornecedora_id":4}).content==copia
    entrar(http,"cliente")
    assert http.get(BASE+f'/arquivos-tecnicos/{arquivo["id"]}/download').content==original


@pytest.mark.acesso_real
@pytest.mark.parametrize("perfil",[None,"cliente","fornecedor"])
def test_catalogo_nao_amplia_permissao_de_preparar_pdf(ambiente,perfil):
    http, _, sessoes, _=ambiente; arquivo=upload(http,conteudo=desenho());dados=pedido(arquivo)
    dados["paginas"][0]["campos"].update(operacoes_servico=["dobra","solda_tig","pintura_po"])
    if perfil:entrar(http,perfil)
    else:http.cookies.clear()
    assert http.post(PDF+f'/arquivos/{arquivo["id"]}',json=dados,headers={"X-Perfil":"admin"}).status_code==(403 if perfil else 401)
    assert contagens(sessoes)==(0,0,0)
