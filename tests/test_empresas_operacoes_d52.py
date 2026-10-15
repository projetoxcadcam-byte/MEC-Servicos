"""Cadastro real por empresa, seleção atômica e preservação da compatibilidade técnica."""
from decimal import Decimal
import json
import pytest
from sqlalchemy import select, text
from backend.app.models.empresa import Empresa
from backend.app.models.operacao_empresa import OperacaoEmpresa
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.compatibilidade import RepositorioCompatibilidade
from backend.app.services.portal_fornecedor import ServicoPortalFornecedor
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload
from test_preparacao_pdf_d48 import desenho

pytestmark=pytest.mark.acesso_real
URL=BASE+"/administracao/empresas"


def corpo(**campos):
    return dict(razao_social="Empresa D52",documento="98765432000199",tipo_empresa="fornecedor",operacoes=["dobra","solda_tig","pintura_po"],**campos)


def criar(http, **alteracoes):
    dados=corpo();dados.update(alteracoes)
    entrar(http,"admin");r=http.post(URL,json=dados);assert r.status_code==201,r.text
    return r.json()


def banco(sessoes):
    with sessoes() as s:
        tabelas=s.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).scalars().all()
        return {t:[tuple(v) for v in s.execute(text('SELECT * FROM "'+t+'" ORDER BY rowid'))] for t in tabelas if t!="sqlite_sequence"}


def test_consultar_catalogo_e_empresas_nao_cadastra_operacoes_automaticamente(ambiente):
    http,_,sessoes,_=ambiente;antes=banco(sessoes);entrar(http,"admin")
    catalogo=http.get(URL+"/catalogo-operacoes");assert catalogo.status_code==200,catalogo.text
    codigos={v["codigo"] for v in catalogo.json()["itens"]}
    assert {"cnc-d30","dobra","solda_tig","pintura_po"}.issubset(codigos)
    lista=http.get(URL).json();assert lista["total"]==4
    fornecedor=http.get(URL+"/4").json();assert fornecedor["operacoes"][0]["codigo"]=="cnc-d30"
    assert fornecedor["operacoes"][0]["capacidade"]["dimensao_x_maxima_mm"]=="500.000"
    assert fornecedor["materiais"][0]["material_id"]==1
    assert banco(sessoes)==antes


@pytest.mark.parametrize("tipo",["fornecedor","ambos"])
def test_cadastro_associa_servicos_somente_a_empresa_escolhida(ambiente,tipo):
    http,_,sessoes,_=ambiente;antes=banco(sessoes);d=criar(http,tipo_empresa=tipo)
    assert {v["codigo"] for v in d["operacoes"]}=={"dobra","solda_tig","pintura_po"}
    assert all(v["capacidade"] is None for v in d["operacoes"])
    assert d["empresa"]["tipo_empresa"]==tipo
    assert http.get(URL+"/8").json()["operacoes"]==[]
    depois=banco(sessoes)
    for nome,valores in antes.items():
        if nome not in {"empresas","operacoes_empresa","processos_fabricacao"}:assert depois[nome]==valores,nome
    assert depois["capacidades_fornecedor"]==antes["capacidades_fornecedor"]
    assert http.get(URL+"/"+str(d["empresa"]["id"])).json()==d


def test_cliente_so_e_cadastrado_sem_operacoes_de_fornecimento(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http,tipo_empresa="cliente",operacoes=[])
    assert d["operacoes"]==[]
    antes=banco(sessoes)
    r=http.post(URL,json={**corpo(),"documento":"98765432000299","tipo_empresa":"cliente"})
    assert r.status_code==422 and banco(sessoes)==antes


@pytest.mark.parametrize("alteracoes",[
    {"operacoes":[]},{"operacoes":["dobra","dobra"]},{"operacoes":["dobra","inexistente"]},
    {"operacoes":[None]},{"operacoes":["x"*61]},{"operacoes":"dobra"},
    {"documento":"123"},{"razao_social":" "},{"perfil":"admin"},
])
def test_cadastro_invalido_nao_deixa_empresa_ou_catalogo_parcial(ambiente,alteracoes):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes)
    dados=corpo();dados.update(alteracoes);r=http.post(URL,json=dados)
    assert r.status_code==422,r.text
    assert banco(sessoes)==antes


def test_documento_duplicado_nao_muda_empresa_ou_servicos(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http);antes=banco(sessoes)
    r=http.post(URL,json={**corpo(),"operacoes":["montagem"]})
    assert r.status_code==409 and banco(sessoes)==antes
    assert http.get(URL+"/"+str(d["empresa"]["id"])).json()==d


def test_versao_antiga_nao_sobrescreve_operacoes_de_outra_tela(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http);url=URL+f'/{d["empresa"]["id"]}/operacoes'
    r=http.put(url,json={"versao":d["versao"],"operacoes":["dobra","montagem"]});assert r.status_code==200,r.text
    nova=r.json();assert nova["versao"]!=d["versao"]
    antes=banco(sessoes)
    assert http.put(url,json={"versao":d["versao"],"operacoes":["retifica"]}).status_code==409
    assert banco(sessoes)==antes
    assert http.get(URL+f'/{d["empresa"]["id"]}').json()==nova
    assert {v["codigo"] for v in nova["operacoes"]}=={"dobra","montagem"}
    with sessoes() as s:
        assert s.scalar(select(OperacaoEmpresa.ativo).join(ProcessoFabricacao).where(ProcessoFabricacao.codigo=="solda_tig")) is False


def test_salvar_mesma_selecao_e_inocuo_e_nao_duplica_vinculos(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http);antes=banco(sessoes)
    r=http.put(URL+f'/{d["empresa"]["id"]}/operacoes',json={"versao":d["versao"],"operacoes":[v["codigo"] for v in d["operacoes"]]})
    assert r.status_code==200 and r.json()==d and banco(sessoes)==antes


def test_capacidade_legada_nao_e_apagada_ao_editar_operacoes(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");d=http.get(URL+"/4").json();antes=banco(sessoes)
    assert http.put(URL+"/4/operacoes",json={"versao":d["versao"],"operacoes":["dobra"]}).status_code==409
    assert banco(sessoes)==antes
    r=http.put(URL+"/4/operacoes",json={"versao":d["versao"],"operacoes":["cnc-d30","dobra"]})
    assert r.status_code==200,r.text
    assert banco(sessoes)["capacidades_fornecedor"]==antes["capacidades_fornecedor"]
    assert {v["codigo"] for v in r.json()["operacoes"]}=={"cnc-d30","dobra"}


def test_busca_paginada_nao_limita_catalogo_e_resumo_de_operacoes(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http)
    with sessoes() as s:
        s.add_all([Empresa(razao_social=f"Extra {i}",documento=f"doc-extra-{i}",tipo_empresa="cliente") for i in range(23)]);s.commit()
    lista=http.get(URL,params={"limite":2}).json();assert len(lista["itens"])==2 and lista["total"]==28
    url=URL;lista=http.get(url,params={"busca":d["empresa"]["documento"],"limite":1}).json()
    assert lista["total"]==1 and set(lista["itens"][0]["operacoes"])=={"Dobra","Solda TIG","Pintura a pó"}
    assert http.get(URL,params={"tipo":"fornecedor"}).json()["total"]==3
    assert http.get(URL,params={"busca":"%"}).json()["total"]==0


def test_registrar_limites_reais_reutiliza_a_capacidade_tecnica_existente(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http,operacoes=["dobra"]);empresa_id=d["empresa"]["id"];processo=d["operacoes"][0]["processo_id"]
    dados=dict(versao=d["versao"],processo_id=processo,dimensao_x_maxima_mm="200",dimensao_y_maxima_mm="100",dimensao_z_maxima_mm="50",tolerancia_minima_mm="0.05")
    r=http.post(URL+f'/{empresa_id}/capacidade',json=dados);assert r.status_code==200,r.text
    assert r.json()["operacoes"][0]["capacidade"]["dimensao_x_maxima_mm"]=="200.000"
    antes=banco(sessoes);assert http.post(URL+f'/{empresa_id}/capacidade',json=dados).status_code==409
    assert banco(sessoes)==antes
    with sessoes() as s:
        registro=s.scalar(select(CapacidadeFornecedor).where(CapacidadeFornecedor.empresa_id==empresa_id))
        assert registro.processo_id==processo and registro.tolerancia_minima_mm==Decimal("0.0500")


@pytest.mark.parametrize("alteracao",[{"dimensao_x_maxima_mm":"0"},{"tolerancia_minima_mm":"NaN"},{"processo_id":1},{"versao":"a"*64}])
def test_capacidade_invalida_ou_nao_declarada_nao_altera_limites(ambiente,alteracao):
    http,_,sessoes,_=ambiente;d=criar(http,operacoes=["dobra"]);dados=dict(versao=d["versao"],processo_id=d["operacoes"][0]["processo_id"],dimensao_x_maxima_mm="200",dimensao_y_maxima_mm="100",dimensao_z_maxima_mm="50",tolerancia_minima_mm="0.05")
    dados.update(alteracao);antes=banco(sessoes)
    r=http.post(URL+f'/{d["empresa"]["id"]}/capacidade',json=dados);assert r.status_code in {409,422},r.text
    assert banco(sessoes)==antes


def test_processos_existentes_mantem_nome_codigo_id_e_limites(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as s:s.add(ProcessoFabricacao(codigo="solda-antiga",nome="Solda TIG"));s.commit()
    entrar(http,"admin");opcoes=http.get(URL+"/catalogo-operacoes").json()["itens"]
    assert sum(v["nome"]=="Solda TIG" for v in opcoes)==1
    d=criar(http,operacoes=["solda-antiga"])
    assert d["operacoes"][0]["codigo"]=="solda-antiga"
    with sessoes() as s:assert s.scalar(select(ProcessoFabricacao.codigo).where(ProcessoFabricacao.nome=="Solda TIG"))=="solda-antiga"


@pytest.mark.parametrize("perfil",[None,"cliente","fornecedor"])
def test_outros_perfis_nao_consultam_ou_alteram_cadastro_administrativo(ambiente,perfil):
    http,_,sessoes,_=ambiente
    if perfil:entrar(http,perfil)
    else:http.cookies.clear()
    antes=banco(sessoes)
    for metodo,url,dados in [("GET",URL,None),("GET",URL+"/catalogo-operacoes",None),("GET",URL+"/4",None),("POST",URL,corpo()),("PUT",URL+"/4/operacoes",{"versao":"a"*64,"operacoes":["dobra"]})]:
        r=http.request(metodo,url,json=dados,headers={"X-Perfil":"admin"});assert r.status_code==(403 if perfil else 401),r.text
    assert banco(sessoes)==antes


def test_csrf_invalido_nao_cria_empresa_ou_processos(ambiente):
    http,_,sessoes,_=ambiente;entrar(http,"admin");antes=banco(sessoes)
    r=http.post(URL,json=corpo(),headers={"X-MEC-CSRF":"invalido"})
    assert r.status_code==403 and banco(sessoes)==antes


def test_operacao_declarada_so_fica_compativel_com_limites_e_material_reais(ambiente):
    http,_,sessoes,_=ambiente;d=criar(http,operacoes=["dobra"]);empresa_id=d["empresa"]["id"];processo_id=d["operacoes"][0]["processo_id"]
    with sessoes() as s:
        solicitacao=SolicitacaoServico(id=20,empresa_cliente_id=2,processo_id=processo_id,material_id=1,
            dimensao_x_maxima_mm=150,dimensao_y_maxima_mm=80,dimensao_z_maxima_mm=30,
            tolerancia_requerida_mm=Decimal("0.05"),quantidade=1,status="aberta")
        s.add(solicitacao);s.commit()
    def compativeis():
        with sessoes() as s:
            return [empresa.id for empresa,_ in RepositorioCompatibilidade(s).listar_fornecedores_compativeis(s.get(SolicitacaoServico,20))]
    assert compativeis()==[]
    dados=dict(versao=d["versao"],processo_id=processo_id,dimensao_x_maxima_mm="200",dimensao_y_maxima_mm="100",dimensao_z_maxima_mm="50",tolerancia_minima_mm="0.05")
    r=http.post(URL+f'/{empresa_id}/capacidade',json=dados);assert r.status_code==200,r.text
    assert compativeis()==[]
    r=http.post(BASE+f'/empresas/{empresa_id}/materiais',json={"material_id":1});assert r.status_code==201,r.text
    assert compativeis()==[empresa_id]
    with sessoes() as s:s.get(SolicitacaoServico,20).dimensao_x_maxima_mm=201;s.commit()
    assert compativeis()==[]
