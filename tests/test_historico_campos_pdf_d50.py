"""Histórico persistente por ADM, campos válidos e consultas sem alterar PDFs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import json
import pytest
from sqlalchemy import select
from backend.app.models.historico_campos_pdf import HistoricoCampoPdf
from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.schemas.historico_campos_pdf import GuardarHistoricoPdf, LIMITES
from backend.app.services.historico_campos_pdf import ServicoHistoricoCamposPdf
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE, SENHA
from test_preparacao_pdf_d48 import pedido, desenho, contagens
from test_documentacao_cotacao_d42 import upload

pytestmark = pytest.mark.acesso_real
URL = BASE+"/administracao/preparacao-pdf/historico-campos"

def guardar(http, campo, valor):
    r=http.post(URL,json={"itens":[{"campo":campo,"valor":valor}]})
    assert r.status_code==200,r.text
    return r.json()


def test_digitacao_sem_gerar_pdf_persiste_e_reaparece_apos_nova_sessao(ambiente):
    http,_,sessoes,_=ambiente; entrar(http,"admin")
    assert all(not v for v in http.get(URL).json()["campos"].values())
    guardar(http,"material","FORMADUR 2083");guardar(http,"sobremetal","0,5 mm nas faces")
    http.cookies.clear(); entrar(http,"admin")
    campos=http.get(URL).json()["campos"]
    assert campos["material"]==["FORMADUR 2083"] and campos["sobremetal"]==["0,5 mm nas faces"]
    assert contagens(sessoes)==(0,0,0)


def test_valor_recente_sobe_na_lista_sem_duplicatas_por_caixa_ou_espacos(ambiente):
    http,_,sessoes,_=ambiente; entrar(http,"admin")
    guardar(http,"material","  Formadur  2083  ");guardar(http,"material","TYRAX ESR")
    guardar(http,"material","FORMADUR 2083")
    assert http.get(URL).json()["campos"]["material"]==["FORMADUR 2083","TYRAX ESR"]
    with sessoes() as db: assert len(db.scalars(select(HistoricoCampoPdf)).all())==2


def test_campos_nao_se_misturam_e_texto_multilinha_e_preservado(ambiente):
    http,_,_,_=ambiente; entrar(http,"admin")
    guardar(http,"descricao","INSERTO");guardar(http,"material","INSERTO")
    texto="Face A: desbaste.\nFace B: sem usinagem."
    guardar(http,"observacoes_servico",texto)
    campos=http.get(URL).json()["campos"]
    assert campos["descricao"]==campos["material"]==["INSERTO"]
    assert campos["observacoes_servico"]==[texto] and campos["tratamento_termico"]==[]


def test_historico_exclusivo_do_adm_da_sessao_sem_id_forjado(ambiente):
    http,acesso,_,_=ambiente; entrar(http,"admin");guardar(http,"material","MATERIAL ADMIN 1")
    acesso.criar_usuario("Outro ADM","outro@teste.local","admin",None,SENHA,deve_alterar_senha=False)
    r=http.post(BASE+"/autenticacao/entrar",json={"email":"outro@teste.local","senha":SENHA})
    assert r.status_code==200;http.headers["X-MEC-CSRF"]=r.json()["csrf"]
    assert http.get(URL,params={"usuario_admin_id":1}).json()["campos"]["material"]==[]
    guardar(http,"material","MATERIAL ADMIN 2")
    entrar(http,"admin");assert http.get(URL).json()["campos"]["material"]==["MATERIAL ADMIN 1"]
    assert http.post(URL,json={"usuario_admin_id":2,"itens":[{"campo":"material","valor":"FORJADO"}]}).status_code==422


@pytest.mark.parametrize("perfil",[None,"cliente","fornecedor"])
def test_outros_perfis_nao_leem_nem_gravam_historico(ambiente,perfil):
    http,_,sessoes,_=ambiente
    if perfil: entrar(http,perfil)
    else: http.cookies.clear()
    esperado=403 if perfil else 401
    assert http.get(URL,headers={"X-Perfil":"admin"}).status_code==esperado
    assert http.post(URL,json={"itens":[{"campo":"material","valor":"TYRAX"}]},headers={"X-Perfil":"admin"}).status_code==esperado
    with sessoes() as db: assert not db.scalars(select(HistoricoCampoPdf)).all()


def test_csrf_invalido_recusa_sem_gravar(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin")
    assert http.post(URL,json={"itens":[{"campo":"material","valor":"TYRAX"}]},headers={"X-MEC-CSRF":"errado"}).status_code==403
    with sessoes() as db:assert not db.scalars(select(HistoricoCampoPdf)).all()


@pytest.mark.parametrize("campo,valor",[("material",""),("material","x"*51),("material","中文"),
    ("descricao","x\x00"),("quantidade","0"),("quantidade","1.5"),("quantidade","1000001"),
    ("registro_interno","Segredo"),("sha256","a"*64),("escopo_servico","desbaste")])
def test_valores_invalidos_e_campos_internos_nao_entram_no_historico(ambiente,campo,valor):
    http,_,sessoes,_=ambiente;entrar(http,"admin")
    r=http.post(URL,json={"itens":[{"campo":"material","valor":"Valor valido"},{"campo":campo,"valor":valor}]})
    assert r.status_code==422,r.text
    with sessoes() as db:assert not db.scalars(select(HistoricoCampoPdf)).all()


def test_lote_completo_e_quantidade_normalizada_sem_publicacao(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin")
    valores={campo:("0018" if campo=="quantidade" else "Valor "+campo[:3]) for campo in LIMITES}
    r=http.post(URL,json={"itens":[{"campo":k,"valor":v} for k,v in valores.items()]})
    assert r.status_code==200 and r.json()["guardados"]==13
    campos=http.get(URL).json()["campos"]
    assert campos["quantidade"]==["18"] and contagens(sessoes)==(0,0,0)


def test_duas_abas_salvam_um_unico_valor(ambiente):
    _,_,sessoes,_=ambiente;dados=GuardarHistoricoPdf(itens=[{"campo":"material","valor":"TYRAX ESR"}])
    admin=UsuarioAcesso(1,"Admin","admin@teste.local","admin",None,False)
    def salvar(_):
        with sessoes() as db:return ServicoHistoricoCamposPdf(db).guardar(dados,admin)
    with ThreadPoolExecutor(max_workers=2) as pool:resultados=list(pool.map(salvar,range(2)))
    assert resultados==[{"guardados":1},{"guardados":1}]
    with sessoes() as db:assert len(db.scalars(select(HistoricoCampoPdf)).all())==1


def test_configuracoes_antigas_alimentam_sugestoes_sem_modificar_versoes(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http,conteudo=desenho());dados=pedido(a)
    configuracao=json.dumps(dados["paginas"],ensure_ascii=False)
    with sessoes() as db:
        registros=[]
        for versao,autor,cfg in [(1,1,configuracao),(2,99,configuracao),(3,1,'corrompido')]:
            p=PreparacaoPdfCotacao(arquivo_id=a["id"],versao=versao,sha256_original=a["sha256"],sha256="b"*64,
                tamanho_bytes=1,caminho_arquivo="inexistente.pdf",configuracao_json=cfg,
                registro_interno="SEGREDO INTERNO",usuario_admin_id=autor,administrador_nome="ADM",criado_em=f"2026-10-09T10:00:0{versao}Z",
                chave_operacao=str(uuid4()),pedido_sha256="c"*64)
            db.add(p);registros.append(p)
        db.commit();antes=[p.configuracao_json for p in registros]
    entrar(http,"admin");r=http.get(URL);assert r.status_code==200,r.text
    campos=r.json()["campos"]
    assert campos["material"]==["TYRAX ESR"] and campos["quantidade"]==["20"]
    assert "SEGREDO" not in r.text and "registro_interno" not in campos and "sha256" not in campos
    with sessoes() as db:
        assert [p.configuracao_json for p in db.scalars(select(PreparacaoPdfCotacao).order_by(PreparacaoPdfCotacao.id))]==antes
        assert not db.scalars(select(HistoricoCampoPdf)).all()


def test_historico_nao_descarta_valores_antigos(ambiente):
    http,_,_,_=ambiente;entrar(http,"admin")
    r=http.post(URL,json={"itens":[{"campo":"material","valor":f"Material {n}"} for n in range(120)]})
    assert r.status_code==200,r.text
    assert len(http.get(URL).json()["campos"]["material"])==120
