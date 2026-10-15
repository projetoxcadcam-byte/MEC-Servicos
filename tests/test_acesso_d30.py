"""D30: integração com autenticação real, sem substituição de permissões."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import time
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, COOKIE_SESSAO
from backend.app.core.permissoes_acesso import autorizar_requisicao
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.entrega import EntregaServico
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import criar_aplicacao
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico

pytestmark = pytest.mark.acesso_real
SENHA = "Senha-de-teste-D30!"
NOVA = "Outra-senha-D30-valida!"
BASE = "/api/v1"


@pytest.fixture(scope="module")
def modelo_acessos(tmp_path_factory):
    caminho = tmp_path_factory.mktemp("modelo_acessos_d30") / "acessos.db"
    acesso = ArmazenamentoAcesso(caminho); acesso.inicializar()
    for nome, perfil, empresa in (("Admin", "admin", None), ("Cliente", "cliente", 2), ("Fornecedor", "fornecedor", 4)):
        acesso.criar_usuario(nome, perfil + "@teste.local", perfil, empresa, SENHA, deve_alterar_senha=False)
    return caminho


@pytest.fixture()
def ambiente(tmp_path, monkeypatch, modelo_acessos):
    engine = create_engine(f"sqlite:///{tmp_path / 'negocio.db'}", connect_args={"check_same_thread": False})
    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(ServicoArquivoTecnico, "STORAGE_ROOT", tmp_path / "arquivos")
    with sessoes() as banco:
        banco.add_all([Empresa(id=i, razao_social=f"Razao Privada {i}", documento=f"doc-{i}", tipo_empresa=perfil)
            for i, perfil in ((2,"cliente"),(4,"fornecedor"),(6,"cliente"),(8,"fornecedor"))])
        banco.add_all([ProcessoFabricacao(id=1,codigo="cnc-d30",nome="Usinagem CNC"),Material(id=1,codigo="al-d30",nome="Alumínio 6061")])
        banco.commit()
        for i, cliente in ((1,2),(2,6),(3,2),(4,2)):
            banco.add(SolicitacaoServico(id=i,empresa_cliente_id=cliente,processo_id=1,material_id=1,
                dimensao_x_maxima_mm=100,dimensao_y_maxima_mm=100,dimensao_z_maxima_mm=100,
                tolerancia_requerida_mm=Decimal("0.02"),quantidade=5,status="aberta",observacoes="Contato privado: privado@empresa.local"))
        banco.add_all([CapacidadeFornecedor(empresa_id=4,processo_id=1,dimensao_x_maxima_mm=500,
            dimensao_y_maxima_mm=500,dimensao_z_maxima_mm=500,tolerancia_minima_mm=Decimal("0.01")),
            MaterialFornecedor(empresa_id=4,material_id=1)])
        banco.commit()
        for i, cliente, fornecedor in ((1,2,4),(2,6,8),(4,2,4)):
            banco.add(CotacaoFornecedor(id=i,solicitacao_id=i,empresa_fornecedora_id=fornecedor,valor_total=Decimal("1500"),
                prazo_dias=15,validade_dias=10,status="aceita",encerrada_em=datetime(2026,10,2),decidida_por_empresa_id=cliente))
            banco.flush()
            banco.add(ContratacaoServico(id=i,solicitacao_id=i,cotacao_id=i,empresa_cliente_id=cliente,
                empresa_fornecedora_id=fornecedor,valor_total=Decimal("1500"),prazo_dias=15,status="encerrada" if i==1 else "ativa"))
            banco.flush()
            banco.add(OrdemServico(id=i,contratacao_id=i,solicitacao_id=i,cotacao_id=i,empresa_cliente_id=cliente,
                empresa_fornecedora_id=fornecedor,processo_id=1,material_id=1,quantidade=5,
                valor_total=Decimal("1500"),prazo_dias=15,status="concluida" if i==1 else "aberta"))
        banco.flush()
        banco.add(EntregaServico(id=1,ordem_servico_id=1,empresa_cliente_id=2,empresa_fornecedora_id=4,
            status="aceita",entregue_em=datetime(2026,10,2),aceita_em=datetime(2026,10,2),observacoes="Entrega antiga privada"))
        banco.commit()
    acesso_path = tmp_path / "acessos.db"; shutil.copy2(modelo_acessos, acesso_path)
    acesso = ArmazenamentoAcesso(acesso_path)
    app = criar_aplicacao(); app.state.caminho_acessos = acesso_path
    def banco_teste():
        with sessoes() as banco:
            yield banco
    app.dependency_overrides[obter_banco] = banco_teste
    assert autorizar_requisicao not in app.dependency_overrides
    http = TestClient(app)
    try:
        yield http, acesso, sessoes, app
    finally:
        http.close(); app.dependency_overrides.clear(); engine.dispose()


def entrar(http, perfil="cliente", senha=SENHA):
    resposta = http.post(BASE + "/autenticacao/entrar",json={"email":perfil+"@teste.local","senha":senha})
    assert resposta.status_code == 200, resposta.text
    http.headers["X-MEC-CSRF"] = resposta.json()["csrf"]
    return resposta


def test_rotas_da_aplicacao_exigem_sessao_real(ambiente):
    http,_,_,app = ambiente
    verificadas = 0
    for caminho, metodos in app.openapi()["paths"].items():
        if not caminho.startswith(BASE + "/") or caminho.startswith(BASE + "/autenticacao/"):
            continue
        if caminho in {BASE+"/saude", BASE+"/banco-dados/saude"}:
            continue
        concreto = re.sub(r"\{[^}]+\}","1",caminho)
        for metodo in metodos:
            if metodo not in {"get","post","put","patch","delete","head"}: continue
            resposta = http.request(metodo,concreto,json={} if metodo != "get" else None)
            assert resposta.status_code == 401, (metodo,caminho,resposta.text)
            verificadas += 1
    assert verificadas >= 40


def test_cookie_falso_e_cabecalho_de_perfil_nao_autorizam(ambiente):
    http,_,_,_ = ambiente
    http.cookies.set(COOKIE_SESSAO,"inventada")
    assert http.get(BASE+"/empresas",headers={"X-Perfil":"admin","X-Empresa-Id":"2"}).status_code == 401


def test_login_cookie_hash_vinculo_empresa_e_rotacao(ambiente):
    http,acesso,_,_ = ambiente
    resposta = entrar(http,"fornecedor"); usuario=resposta.json()["usuario"]
    assert usuario["id"] == usuario["empresa_id"] == 4 and usuario["usuario_id"] == 3
    cookie=resposta.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1" in cookie
    token=http.cookies.get(COOKIE_SESSAO)
    with sqlite3.connect(acesso.caminho) as banco:
        armazenado=banco.execute("SELECT token_hash FROM sessoes_acesso").fetchone()[0]
        assert armazenado == hashlib.sha256(token.encode()).hexdigest() and armazenado != token
        senha_hash=banco.execute("SELECT senha_hash FROM usuarios_acesso WHERE perfil='fornecedor'").fetchone()[0]
        assert "600000" in senha_hash and SENHA not in senha_hash
    entrar(http,"fornecedor")
    assert http.cookies.get(COOKIE_SESSAO) != token
    with pytest.raises(Exception) as falha: acesso.obter_sessao(token)
    assert falha.value.status_code == 401


def test_erros_login_genericos_limite_persistente_e_origem(ambiente):
    http,_,_,_ = ambiente
    for email in ["cliente@teste.local","inexistente@teste.local"]:
        resposta=http.post(BASE+"/autenticacao/entrar",json={"email":email,"senha":"incorreta"})
        assert resposta.status_code==401 and resposta.json()=={"detail":"email_ou_senha_invalidos"}
    for _ in range(4):
        assert http.post(BASE+"/autenticacao/entrar",json={"email":"cliente@teste.local","senha":"incorreta"}).status_code==401
    assert http.post(BASE+"/autenticacao/entrar",json={"email":"cliente@teste.local","senha":SENHA}).status_code==429
    assert http.post(BASE+"/autenticacao/entrar",json={"email":"admin@teste.local","senha":SENHA},headers={"Origin":"https://site-alheio.local"}).status_code==403


@pytest.mark.parametrize("origem",["null","https://site-alheio.local"])
def test_mutacao_exige_origem_e_csrf(ambiente,origem):
    http,_,_,_ = ambiente; entrar(http,"admin")
    assert http.post(BASE+"/autenticacao/sair",json={},headers={"Origin":origem}).status_code==403
    assert http.post(BASE+"/autenticacao/sair",json={},headers={"X-MEC-CSRF":"errado"}).status_code==403
    http.headers.pop("X-MEC-CSRF")
    assert http.post(BASE+"/autenticacao/sair",json={}).status_code==403
    assert http.get(BASE+"/autenticacao/sessao").status_code==200


def test_logout_expiracao_e_desativacao_revogam_sessao(ambiente):
    http,acesso,_,_ = ambiente; entrar(http)
    token=http.cookies.get(COOKIE_SESSAO)
    assert http.post(BASE+"/autenticacao/sair",json={}).status_code==200
    http.cookies.set(COOKIE_SESSAO,token,path="/api/v1")
    assert http.get(BASE+"/autenticacao/sessao").status_code==401
    http.cookies.clear(); entrar(http)
    with sqlite3.connect(acesso.caminho) as banco: banco.execute("UPDATE sessoes_acesso SET expira_em=?",(time.time()-1,))
    assert http.get(BASE+"/autenticacao/sessao").status_code==401
    entrar(http); acesso.definir_ativo(2,False)
    assert http.get(BASE+"/autenticacao/sessao").status_code==401


def test_senha_inicial_bloqueia_negocio_e_alteracao_revoga_sessoes(ambiente):
    http,acesso,_,_ = ambiente
    acesso.redefinir_senha(2,NOVA); entrar(http,senha=NOVA)
    assert http.get(BASE+"/materiais").json()=={"detail":"troca_senha_inicial_obrigatoria"}
    assert http.get(BASE+"/autenticacao/sessao").json()["usuario"]["deve_alterar_senha"] is True
    assert http.post(BASE+"/autenticacao/alterar-senha",json={"senha_atual":"errada","nova_senha":SENHA}).status_code==401
    assert http.post(BASE+"/autenticacao/alterar-senha",json={"senha_atual":NOVA,"nova_senha":NOVA}).status_code==422
    token=http.cookies.get(COOKIE_SESSAO)
    assert http.post(BASE+"/autenticacao/alterar-senha",json={"senha_atual":NOVA,"nova_senha":SENHA}).status_code==200
    with pytest.raises(Exception) as falha: acesso.obter_sessao(token)
    assert falha.value.status_code==401
    assert entrar(http).json()["usuario"]["deve_alterar_senha"] is False


@pytest.mark.parametrize("perfil,campo,outra",[("cliente","empresa_cliente_id",6),("fornecedor","empresa_fornecedora_id",8)])
def test_empresa_query_caminho_e_perfil_vinculados_a_sessao(ambiente,perfil,campo,outra):
    http,_,_,_ = ambiente; entrar(http,perfil)
    propria=2 if perfil=="cliente" else 4
    url=BASE+f"/portal-{perfil}/entregas"
    assert http.get(url,params={campo:propria}).status_code==200
    assert http.get(url,params={campo:outra}).status_code==403
    assert http.get(url,params=[(campo,propria),(campo,propria)]).status_code==403
    assert http.get(url).status_code==403
    assert http.get(url+"/2",params={campo:propria}).status_code==404
    assert http.get(BASE+"/empresas").status_code==403
    assert http.get(BASE+f"/empresas/{outra}").status_code==403
    assert http.get(BASE+f"/empresas/{propria}").status_code==200
    oposto="fornecedor" if perfil=="cliente" else "cliente"
    assert http.get(BASE+f"/portal-{oposto}/entregas",params={"empresa_cliente_id":2,"empresa_fornecedora_id":4}).status_code==403


@pytest.mark.parametrize("perfil",["cliente","fornecedor"])
@pytest.mark.parametrize("url",[
    "/ordens-servico/1/entregas", "/ordens-servico/1/entregas/1/aceitar", "/ordens-servico/1/entregas/1/recusar",
    "/portal-cliente/entregas/1/1/aceitar", "/portal-cliente/entregas/1/1/recusar", "/portal-fornecedor/entregas/1/registrar",
    "/portal-fornecedor/ordens-servico/1/concluir", "/portal-cliente/contratacoes/1/ordem-servico",
    "/solicitacoes-servico/1/cotacoes/1/aceitar", "/solicitacoes-servico/1/cotacoes/1/recusar",
    "/portal-cliente/solicitacoes/1/contratacao",
])
def test_decisoes_e_rotas_legadas_sao_administrativas_sem_alterar_historico(ambiente,perfil,url):
    http,_,sessoes,_ = ambiente; entrar(http,perfil)
    resposta=http.post(BASE+url,json={"empresa_cliente_id":2,"empresa_fornecedora_id":4,"motivo":"Teste"})
    assert resposta.status_code==403
    with sessoes() as banco:
        assert banco.get(OrdemServico,1).status=="concluida"
        assert banco.get(EntregaServico,1).status=="aceita"
        assert banco.get(ContratacaoServico,1).status=="encerrada"


def test_fornecedor_proposta_real_e_campo_empresa_falso(ambiente):
    http,_,sessoes,_ = ambiente; entrar(http,"fornecedor")
    from apoio_documentacao_d42 import preparar_documentacao_qa
    with sessoes() as banco: preparar_documentacao_qa(banco, 3)
    dados={"empresa_fornecedora_id":8,"valor_total":"1000","prazo_dias":10,"validade_dias":10,"observacoes":"Proposta privada"}
    url=BASE+"/portal-fornecedor/solicitacoes/3/cotacoes"
    assert http.post(url,json=dados).status_code==403
    dados["empresa_fornecedora_id"]=4
    assert http.post(url,json={**dados,"role":"admin"}).status_code==403
    resposta=http.post(url,json=dados)
    assert resposta.status_code==201 and resposta.json()["empresa_fornecedora_id"]==4
    assert http.get(BASE+"/portal-fornecedor/ordens-servico/2",params={"empresa_fornecedora_id":4}).status_code==404


def test_fornecedor_inicia_ordem_e_informa_coleta_sem_concluir_ou_entregar(ambiente):
    http,_,sessoes,_ = ambiente; entrar(http,"fornecedor")
    inicio=BASE+"/portal-fornecedor/ordens-servico/4/iniciar"
    assert http.post(inicio,json={"empresa_fornecedora_id":8}).status_code==403
    assert http.post(inicio,json={"empresa_fornecedora_id":4}).status_code==200
    etapa=http.post(BASE+"/portal-fornecedor/producao/4/etapas",json={"empresa_fornecedora_id":4,
        "ultima_etapa_id":0,"etapa":"pronto_para_envio","observacoes":"Pronto para coleta pela administração"})
    assert etapa.status_code==201 and etapa.json()["etapa"]=="pronto_para_envio"
    assert http.post(BASE+"/portal-fornecedor/ordens-servico/4/concluir",json={"empresa_fornecedora_id":4}).status_code==403
    assert http.post(BASE+"/portal-fornecedor/entregas/4/registrar",json={"empresa_fornecedora_id":4,
        "ultima_etapa_id":etapa.json()["id"],"ultima_entrega_id":0}).status_code==403
    with sessoes() as banco:
        assert banco.get(OrdemServico,4).status=="em_execucao"
        assert banco.get(ContratacaoServico,4).status=="ativa"


@pytest.mark.parametrize("extensao",["zip","RAR"])
def test_cliente_upload_multipart_download_e_desvinculo_proprios(ambiente,extensao):
    http,_,_,_ = ambiente; entrar(http)
    conteudo=b"Arquivo comprimido de teste D30"; files={"file":("pecas."+extensao,conteudo,"application/octet-stream")}
    assert http.post(BASE+"/solicitacoes-servico/2/arquivos-tecnicos",files=files).status_code==404
    resposta=http.post(BASE+"/solicitacoes-servico/1/arquivos-tecnicos",files=files)
    assert resposta.status_code==201, resposta.text
    arquivo=resposta.json(); assert arquivo.get("caminho_arquivo") is None
    aid=arquivo["id"]
    assert http.get(BASE+f"/arquivos-tecnicos/{aid}/download").content==conteudo
    assert http.delete(BASE+f"/arquivos-tecnicos/{aid}").status_code==204


def test_fornecedor_nao_recebe_arquivos_sem_revisao_admin(ambiente):
    http,_,_,_ = ambiente; entrar(http,"fornecedor")
    for url in ["/portal-fornecedor/solicitacoes/1/arquivos","/portal-fornecedor/arquivos/1/download",
        "/portal-fornecedor/contratacoes/1/arquivos","/portal-fornecedor/ordens-servico/1/arquivos","/arquivos-tecnicos/1/download"]:
        assert http.get(BASE+url,params={"empresa_fornecedora_id":4}).status_code==403


@pytest.mark.parametrize("perfil,campo,empresa,proibido,codigo",[("cliente","empresa_cliente_id",2,"Razao Privada 4","Fornecedor F-0004"),
    ("fornecedor","empresa_fornecedora_id",4,"Razao Privada 2","Cliente C-0002")])
def test_privacidade_codigos_observacoes_e_historico(ambiente,perfil,campo,empresa,proibido,codigo):
    http,_,_,_ = ambiente; entrar(http,perfil)
    resposta=http.get(BASE+f"/portal-{perfil}/entregas/1",params={campo:empresa})
    assert resposta.status_code==200 and resposta.headers["cache-control"]=="no-store"
    assert proibido not in resposta.text and "privado@empresa.local" not in resposta.text and codigo in resposta.text
    assert resposta.json()["historico"][0]["status"]=="aceita"
    assert resposta.json()["historico"][0]["observacoes"] is None
    own=http.get(BASE+f"/empresas/{empresa}")
    assert own.json()["documento"]==f"doc-{empresa}"


def test_administrador_gerencia_contas_e_redefinicao_invalida_sessao(ambiente):
    http,acesso,_,_ = ambiente; entrar(http)
    token=http.cookies.get(COOKIE_SESSAO)
    assert http.get(BASE+"/autenticacao/usuarios").status_code==403
    entrar(http,"admin")
    dados={"nome":"Outro operador","email":"outro@teste.local","perfil":"cliente","empresa_id":2,"senha":NOVA}
    criada=http.post(BASE+"/autenticacao/usuarios",json=dados)
    assert criada.status_code==201 and criada.json()["usuario_id"]!=criada.json()["empresa_id"]
    assert "senha_hash" not in http.get(BASE+"/autenticacao/usuarios").text
    assert http.post(BASE+"/autenticacao/usuarios",json={**dados,"email":"falso@teste.local","empresa_id":4}).status_code==422
    assert http.patch(BASE+"/autenticacao/usuarios/1/ativo",json={"ativo":False}).status_code==409
    assert http.post(BASE+"/autenticacao/usuarios/2/redefinir-senha",json={"nova_senha":NOVA}).status_code==200
    with pytest.raises(Exception) as falha: acesso.obter_sessao(token)
    assert falha.value.status_code==401


def test_validacao_acesso_nao_repete_senha_e_https_cookie_seguro(ambiente):
    http,_,_,app = ambiente
    resposta=http.post(BASE+"/autenticacao/entrar",json={"email":"admin@teste.local","senha":"SEGREDO"*100,"role":"admin"})
    assert resposta.status_code==422 and "SEGREDO" not in resposta.text
    with TestClient(app,base_url="https://testserver") as seguro:
        cookie=entrar(seguro,"admin").headers["set-cookie"].lower()
        assert "secure" in cookie


def test_configuracao_ausente_e_rota_nova_nao_abrem_acesso(ambiente,tmp_path):
    http,_,_,app = ambiente
    novo=APIRouter()
    @novo.get("/futuro")
    def futuro(): return {"email":"nao-compartilhar@teste.local"}
    app.include_router(novo,prefix=BASE,dependencies=[Depends(autorizar_requisicao)])
    entrar(http)
    assert http.get(BASE+"/futuro").status_code==403
    app.state.caminho_acessos=tmp_path/"inexistente.db"
    assert http.post(BASE+"/autenticacao/entrar",json={"email":"admin@teste.local","senha":SENHA}).status_code==503


def test_json_recursivo_remove_contatos_antes_de_responder():
    from backend.app.core.armazenamento_acesso import UsuarioAcesso
    from backend.app.core.privacidade_acesso import dados_portal
    dados={"itens":[{"empresa_fornecedora_id":4,"fornecedor_razao_social":"Telefone da Oficina","telefone":"123456",
        "observacoes":"whatsapp 987","caminho_arquivo":"C:/privado","quantidade":5,"aninhado":{"email":"oficina@teste.local"}}]}
    filtrado=json.dumps(dados_portal(dados,UsuarioAcesso(2,"Cliente","cliente@teste.local","cliente",2,False)))
    assert "oficina@teste.local" not in filtrado and "whatsapp 987" not in filtrado and "C:/privado" not in filtrado
    assert "Fornecedor F-0004" in filtrado and '"quantidade": 5' in filtrado
