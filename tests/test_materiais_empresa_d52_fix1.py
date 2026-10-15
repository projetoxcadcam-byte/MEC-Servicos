"""Material aceito: catálogo disponível, criação explícita e vínculos atômicos por empresa."""
import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.services.catalogo_materiais_empresa import MATERIAIS_PADRAO
from test_acesso_d30 import ambiente, modelo_acessos, entrar
from test_empresas_operacoes_d52 import banco, URL

pytestmark=pytest.mark.acesso_real
CATALOGO=URL+"/catalogo-materiais"


def codigo(nome):
    return next(c for c,n in MATERIAIS_PADRAO.items() if n==nome)


def vincular(http,empresa=4,versao=None,**escolha):
    if versao is None:versao=http.get(URL+f"/{empresa}").json()["versao"]
    return http.post(URL+f"/{empresa}/materiais",json=dict(versao=versao,**escolha))


def test_lista_pronta_disponivel_sem_cadastrar_ou_associar_automaticamente(ambiente):
    http,_,sessoes,_=ambiente;antes=banco(sessoes);entrar(http,"admin")
    r=http.get(CATALOGO);assert r.status_code==200,r.text
    nomes={v["nome"] for v in r.json()["itens"]}
    assert {"Aço carbono SAE 1045","Alumínio 6061","Aço inox AISI 316L","Nylon / PA6","Bronze"}<=nomes
    assert len(MATERIAIS_PADRAO)==50 and banco(sessoes)==antes


def test_aluminio_ja_cadastrado_e_reutilizado_sem_ocultar_outros_materiais(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as s:s.get(Material,1).nome="Alumínio 6061";s.commit()
    antes=banco(sessoes);entrar(http,"admin");itens=http.get(CATALOGO).json()["itens"]
    alum=[v for v in itens if v["nome"]=="Alumínio 6061"]
    assert len(alum)==1 and alum[0]["material_id"]==1 and alum[0]["codigo"]=="al-d30"
    assert any(v["nome"]=="Aço carbono SAE 1045" and v["material_id"] is None for v in itens)
    assert banco(sessoes)==antes


def test_escolha_pronta_cadastra_so_um_material_e_so_na_empresa_escolhida(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes)
    r=vincular(http,codigo_catalogo=codigo("Aço carbono SAE 1045"));assert r.status_code==200,r.text
    assert {v["nome"] for v in r.json()["materiais"]}=={"Alumínio 6061","Aço carbono SAE 1045"}
    depois=banco(sessoes)
    assert len(depois["materiais"])==len(antes["materiais"])+1
    assert len(depois["materiais_fornecedor"])==len(antes["materiais_fornecedor"])+1
    for t in antes:
        if t not in {"materiais","materiais_fornecedor"}:assert depois[t]==antes[t],t
    assert http.get(URL+"/8").json()["materiais"]==[]
    assert http.get(URL+"/4").json()==r.json()


def test_mesmo_material_e_reutilizado_em_duas_empresas_sem_duplicar_catalogo(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin")
    for empresa in (4,8):assert vincular(http,empresa,codigo_catalogo=codigo("Bronze")).status_code==200
    with sessoes() as s:
        materiais=s.scalars(select(Material).where(Material.nome=="Bronze")).all();assert len(materiais)==1
        links=s.scalars(select(MaterialFornecedor).where(MaterialFornecedor.material_id==materiais[0].id)).all()
        assert {v.empresa_id for v in links}=={4,8}


def test_material_existente_mantem_codigo_familia_especificacao_e_outros_vinculos(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as s:
        s.add(Material(id=2,codigo="codigo-local-1045",nome="Aço carbono SAE 1045",familia="Família local",especificacao="Especificação local preservada"));s.commit()
    entrar(http,"admin");antes=banco(sessoes)
    r=vincular(http,codigo_catalogo=codigo("Aço carbono SAE 1045"));assert r.status_code==200,r.text
    assert banco(sessoes)["materiais"]==antes["materiais"]
    assert any(v["material_id"]==2 for v in r.json()["materiais"])


def test_material_proprio_persiste_e_pode_ser_reutilizado_sem_supor_equivalencia(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin")
    r=vincular(http,novo_material="  Material do cliente  XY-27  ");assert r.status_code==200,r.text
    novo=next(v for v in r.json()["materiais"] if v["nome"]=="Material do cliente XY-27")
    r=vincular(http,8,novo_material="material DO cliente XY-27");assert r.status_code==200,r.text
    assert r.json()["materiais"][0]["material_id"]==novo["material_id"]
    r=vincular(http,novo_material="Material do cliente XY-28");assert r.status_code==200,r.text
    assert len(banco(sessoes)["materiais"])==3
    with sessoes() as s:
        m=s.get(Material,novo["material_id"]);assert m.familia is None and m.especificacao is None


@pytest.mark.parametrize("dados",[
    {},{"material_id":1,"codigo_catalogo":"x"},{"material_id":0},{"material_id":True},
    {"novo_material":" "},{"novo_material":"A"},{"novo_material":"M"*161},
    {"novo_material":"nome\ncontrole"},{"codigo_catalogo":"nao-existe"},
    {"novo_material":"Material QA","perfil":"admin"},
])
def test_pedido_invalido_nao_deixa_material_ou_vinculo_parcial(ambiente,dados):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes)
    r=vincular(http,**dados);assert r.status_code==422,r.text
    assert banco(sessoes)==antes


def test_vinculo_repetido_e_versao_antiga_nao_duplicam_material(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");d=http.get(URL+"/4").json()
    r=vincular(http,versao=d["versao"],codigo_catalogo=codigo("Bronze"));assert r.status_code==200
    antes=banco(sessoes)
    assert vincular(http,versao=d["versao"],codigo_catalogo=codigo("Cobre")).status_code==409
    assert vincular(http,codigo_catalogo=codigo("Bronze")).status_code==409
    assert banco(sessoes)==antes
    assert http.put(URL+"/4/operacoes",json={"versao":d["versao"],"operacoes":["cnc-d30","dobra"]}).status_code==409
    assert banco(sessoes)==antes


def test_gravacao_legada_de_material_tambem_invalida_tela_antiga(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");d=http.get(URL+"/8").json()
    r=http.post("/api/v1/empresas/8/materiais",json={"material_id":1});assert r.status_code==201,r.text
    antes=banco(sessoes);assert vincular(http,8,versao=d["versao"],novo_material="Não deve ser cadastrado").status_code==409
    assert banco(sessoes)==antes


@pytest.mark.parametrize("escolha",["pronto","existente","proprio"])
def test_material_inativo_nao_e_oferecido_nem_vinculado(ambiente,escolha):
    http,_,sessoes,_=ambiente
    with sessoes() as s:s.add(Material(id=2,codigo="bronze-local",nome="Bronze",ativo=False));s.commit()
    entrar(http,"admin");antes=banco(sessoes)
    assert not any(v["nome"]=="Bronze" for v in http.get(CATALOGO).json()["itens"])
    dados={"codigo_catalogo":codigo("Bronze")} if escolha=="pronto" else {"material_id":2} if escolha=="existente" else {"novo_material":"Bronze"}
    r=vincular(http,**dados);assert r.status_code==409 and r.json()["detail"]=="material_inativo"
    assert banco(sessoes)==antes


def test_nome_ambiguo_pede_escolha_do_cadastro_existente(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as s:s.add_all([Material(id=2,codigo="bronze-a",nome="Bronze"),Material(id=3,codigo="bronze-b",nome="BRONZE")]);s.commit()
    entrar(http,"admin");antes=banco(sessoes);r=vincular(http,novo_material="bronze")
    assert r.status_code==409 and r.json()["detail"]=="material_nome_ambiguo_selecione_cadastrado"
    assert banco(sessoes)==antes and vincular(http,material_id=2).status_code==200


def test_erro_ao_gravar_vinculo_desfaz_material_criado_na_mesma_transacao(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes);engine=sessoes.kw["bind"]
    def recusar(conexao,cursor,sql,parametros,contexto,muitos):
        if sql.lstrip().upper().startswith("INSERT INTO MATERIAIS_FORNECEDOR"):
            raise IntegrityError(sql,parametros,Exception("Falha isolada do vínculo"))
    event.listen(engine,"before_cursor_execute",recusar)
    try:r=vincular(http,novo_material="Material que deve ser desfeito")
    finally:event.remove(engine,"before_cursor_execute",recusar)
    assert r.status_code==409,r.text
    assert banco(sessoes)==antes


def test_cliente_ou_empresa_ausente_nao_cadastra_material(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes)
    assert vincular(http,2,novo_material="Cliente não fornece").status_code==409
    r=http.post(URL+"/999/materiais",json={"versao":"a"*64,"novo_material":"Empresa ausente"})
    assert r.status_code==404 and banco(sessoes)==antes


@pytest.mark.parametrize("perfil",[None,"cliente","fornecedor"])
def test_materiais_do_cadastro_exigem_sessao_administrativa_real(ambiente,perfil):
    http,_,sessoes,_=ambiente;antes=banco(sessoes)
    if perfil:entrar(http,perfil)
    else:http.cookies.clear()
    assert http.get(CATALOGO,headers={"X-Perfil":"admin"}).status_code==(403 if perfil else 401)
    r=http.post(URL+"/4/materiais",json={"versao":"a"*64,"novo_material":"Tentativa indevida"},headers={"X-Perfil":"admin"})
    assert r.status_code==(403 if perfil else 401) and banco(sessoes)==antes


def test_csrf_invalido_nao_cadastra_material_ou_vinculo(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes);d=http.get(URL+"/4").json()
    r=http.post(URL+"/4/materiais",json={"versao":d["versao"],"novo_material":"CSRF recusado"},headers={"X-MEC-CSRF":"invalido"})
    assert r.status_code==403 and banco(sessoes)==antes


def test_catalogo_paginado_inclui_materiais_apos_a_primeira_pagina(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as s:
        s.add_all([Material(codigo=f"proprio-{i}",nome=f"Material próprio {i:03d}") for i in range(225)]);s.commit()
    entrar(http,"admin");antes=banco(sessoes);itens=[]
    for inicio in (0,200):
        r=http.get(CATALOGO,params={"deslocamento":inicio,"limite":200});assert r.status_code==200
        itens+=r.json()["itens"]
    assert len(itens)==r.json()["total"]==275
    assert len({(v["material_id"],v["codigo"]) for v in itens})==275 and banco(sessoes)==antes
    ultimo=itens[-1];escolha={"material_id":ultimo["material_id"]} if ultimo["material_id"] else {"codigo_catalogo":ultimo["codigo"]}
    assert vincular(http,**escolha).status_code==200
