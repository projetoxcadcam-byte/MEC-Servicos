"""Modo local: entrada por conta, sessão real e permissões D31 preservadas."""
from __future__ import annotations

from decimal import Decimal
import shutil
import sqlite3

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, COOKIE_SESSAO
from backend.app.core.modo_teste_local import modo_teste_disponivel
from backend.app.core.permissoes_acesso import autorizar_requisicao
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import criar_aplicacao

pytestmark = pytest.mark.acesso_real
BASE = "/api/v1"
SENHA = "Senha-apenas-do-banco-temporario-D31!"


class ClienteLoopback:
    """Simula a origem TCP local no transporte ASGI, sem trocar dependências."""
    def __init__(self, app, endereco="127.0.0.1"):
        self.app = app
        self.endereco = endereco

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope = {**scope, "client": (self.endereco, 50000)}
        await self.app(scope, receive, send)


@pytest.fixture(scope="module")
def modelo_teste_local(tmp_path_factory):
    destino = tmp_path_factory.mktemp("modelo_local_fix2") / "acessos.db"
    servico = ArmazenamentoAcesso(destino); servico.inicializar()
    for nome, email, perfil, empresa in [("Administrador", "admin@fix2.local", "admin", None),
            ("Cliente", "cliente@fix2.local", "cliente", 2), ("Fornecedor D7", "fornecedor@fix2.local", "fornecedor", 4),
            ("oficina mecanica", "oficina1@fix2.local", "fornecedor", 1)]:
        servico.criar_usuario(nome, email, perfil, empresa, SENHA)
    return destino


@pytest.fixture()
def ambiente_local(tmp_path, monkeypatch, modelo_teste_local):
    monkeypatch.setenv("MEC_MODO_TESTE_LOCAL", "1")
    monkeypatch.setenv("MEC_AMBIENTE", "desenvolvimento")
    engine = create_engine("sqlite:///" + str(tmp_path / "negocio.db"), connect_args={"check_same_thread": False})
    sessoes = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessoes() as banco:
        banco.add_all([Empresa(id=i, razao_social="Razão privada " + str(i), documento="doc-fix2-" + str(i), tipo_empresa=p)
            for i, p in [(1,"fornecedor"),(2,"cliente"),(4,"fornecedor")]])
        banco.add_all([ProcessoFabricacao(id=1,codigo="cnc-fix2",nome="Usinagem CNC"), Material(id=1,codigo="al-fix2",nome="Alumínio")]); banco.flush()
        for oid, fornecedor in [(1,4),(2,4),(3,1)]:
            banco.add(SolicitacaoServico(id=oid,empresa_cliente_id=2,processo_id=1,material_id=1,
                dimensao_x_maxima_mm=100,dimensao_y_maxima_mm=100,dimensao_z_maxima_mm=100,
                tolerancia_requerida_mm=Decimal("0.02"),quantidade=10,status="aberta")); banco.flush()
            banco.add(CotacaoFornecedor(id=oid,solicitacao_id=oid,empresa_fornecedora_id=fornecedor,
                valor_total=1000,prazo_dias=10,validade_dias=10,status="aceita")); banco.flush()
            banco.add(ContratacaoServico(id=oid,solicitacao_id=oid,cotacao_id=oid,empresa_cliente_id=2,
                empresa_fornecedora_id=fornecedor,valor_total=1000,prazo_dias=10,status="ativa")); banco.flush()
            banco.add(OrdemServico(id=oid,contratacao_id=oid,solicitacao_id=oid,cotacao_id=oid,
                empresa_cliente_id=2,empresa_fornecedora_id=fornecedor,processo_id=1,material_id=1,
                quantidade=10,valor_total=1000,prazo_dias=10,status="aberta" if oid==3 else "concluida")); banco.flush()
        banco.commit()
    acesso = tmp_path / "acessos.db"; shutil.copy2(modelo_teste_local, acesso)
    app = criar_aplicacao(); app.state.caminho_acessos = acesso
    def obter_teste():
        with sessoes() as banco: yield banco
    app.dependency_overrides[obter_banco] = obter_teste
    assert autorizar_requisicao not in app.dependency_overrides
    http = TestClient(ClienteLoopback(app), base_url="http://localhost:8000")
    try: yield http, ArmazenamentoAcesso(acesso), sessoes, app
    finally: http.close(); app.dependency_overrides.clear(); engine.dispose()


def entrar_local(http, usuario_id):
    r = http.post(BASE+"/autenticacao/teste-local/entrar", json={"usuario_id":usuario_id}, headers={"X-MEC-TESTE-LOCAL":"1"})
    assert r.status_code == 200, r.text
    http.headers["X-MEC-CSRF"] = r.json()["csrf"]
    return r


def test_modo_desligado_nao_lista_contas_nem_permite_entrada(ambiente_local, monkeypatch):
    http,_,_,_ = ambiente_local
    monkeypatch.setenv("MEC_MODO_TESTE_LOCAL", "0")
    assert http.get(BASE+"/autenticacao/teste-local").json() == {"ativo":False,"contas":[]}
    assert http.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":1},headers={"X-MEC-TESTE-LOCAL":"1"}).status_code == 403
    assert http.get(BASE+"/empresas").status_code == 401


def test_lista_contas_ativas_sem_senha_e_entrada_da_oficina(ambiente_local):
    http,acesso,_,_ = ambiente_local
    with sqlite3.connect(acesso.caminho) as banco:
        antes = banco.execute("SELECT * FROM usuarios_acesso ORDER BY id").fetchall()
    r = http.get(BASE+"/autenticacao/teste-local")
    assert r.status_code == 200 and r.json()["ativo"] is True
    assert {c["usuario_id"] for c in r.json()["contas"]} == {1,2,3,4}
    assert "senha_hash" not in r.text and SENHA not in r.text
    r = entrar_local(http,4)
    assert r.json()["usuario"]["empresa_id"] == 1 and r.json()["usuario"]["teste_local"] is True
    assert r.json()["usuario"]["deve_alterar_senha"] is False
    assert "httponly" in r.headers["set-cookie"].lower()
    sessao = http.get(BASE+"/autenticacao/sessao")
    assert sessao.json()["usuario"]["teste_local"] is True
    with sqlite3.connect(acesso.caminho) as banco:
        assert banco.execute("SELECT * FROM usuarios_acesso ORDER BY id").fetchall() == antes
        assert banco.execute("SELECT acao FROM auditoria_acesso ORDER BY id DESC LIMIT 1").fetchone()[0] == "entrar_teste_local"
    r = http.get(BASE+"/portal-fornecedor/producao",params={"empresa_fornecedora_id":1})
    assert r.status_code == 200, r.text
    assert [o["id"] for o in r.json()["itens"]] == [3]
    assert "Razão privada 2" not in r.text


def test_cada_fornecedor_ve_suas_ordens_e_nao_vira_admin(ambiente_local):
    http,_,_,_ = ambiente_local
    entrar_local(http,3)
    r = http.get(BASE+"/portal-fornecedor/producao",params={"empresa_fornecedora_id":4})
    assert r.status_code == 200 and {o["id"] for o in r.json()["itens"]} == {1,2}
    assert http.get(BASE+"/portal-fornecedor/producao/3",params={"empresa_fornecedora_id":4}).status_code == 404
    assert http.get(BASE+"/portal-fornecedor/producao",params={"empresa_fornecedora_id":1}).status_code == 403
    assert http.get(BASE+"/administracao/intermediacao/ordens").status_code == 403


def test_trocar_perfil_revoga_token_anterior_e_exige_csrf(ambiente_local):
    http,acesso,_,_ = ambiente_local
    entrar_local(http,4)
    anterior = http.cookies.get(COOKIE_SESSAO)
    entrar_local(http,1)
    with pytest.raises(Exception) as erro: acesso.obter_sessao(anterior)
    assert erro.value.status_code == 401
    assert http.get(BASE+"/administracao/intermediacao/ordens").status_code == 200
    assert http.post(BASE+"/autenticacao/sair",json={},headers={"X-MEC-CSRF":"incorreto"}).status_code == 403
    assert http.post(BASE+"/autenticacao/sair",json={}).status_code == 200
    assert http.get(BASE+"/autenticacao/sessao").status_code == 401


def test_desligar_modo_recusa_cookie_de_teste_mas_login_normal_funciona(ambiente_local,monkeypatch):
    http,_,_,_ = ambiente_local
    entrar_local(http,4)
    monkeypatch.setenv("MEC_MODO_TESTE_LOCAL", "0")
    assert http.get(BASE+"/autenticacao/sessao").status_code == 401
    assert http.get(BASE+"/portal-fornecedor/producao",params={"empresa_fornecedora_id":1}).status_code == 401
    http.cookies.clear()
    r = http.post(BASE+"/autenticacao/entrar",json={"email":"oficina1@fix2.local","senha":SENHA})
    assert r.status_code == 200 and r.json()["usuario"]["deve_alterar_senha"] is True
    assert not r.json()["usuario"].get("teste_local", False)
    assert http.get(BASE+"/materiais").json()["detail"] == "troca_senha_inicial_obrigatoria"


def test_conta_desativada_e_empresa_invalida_nao_aceitam_modo_local(ambiente_local):
    http,acesso,sessoes,_ = ambiente_local
    acesso.definir_ativo(4,False)
    assert 4 not in {c["usuario_id"] for c in http.get(BASE+"/autenticacao/teste-local").json()["contas"]}
    assert http.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":4},headers={"X-MEC-TESTE-LOCAL":"1"}).status_code == 403
    with sessoes() as banco:
        banco.get(Empresa,4).tipo_empresa="cliente"; banco.commit()
    assert http.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":3},headers={"X-MEC-TESTE-LOCAL":"1"}).status_code == 403


def test_origem_remota_cabecalho_e_corpo_nao_criam_sessao(ambiente_local):
    http,acesso,_,app = ambiente_local
    assert http.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":4}).status_code == 403
    assert http.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":4},headers={"X-MEC-TESTE-LOCAL":"1","Origin":"https://externo.local"}).status_code == 403
    assert http.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":4,"role":"admin"},headers={"X-MEC-TESTE-LOCAL":"1"}).status_code == 422
    remoto = TestClient(ClienteLoopback(app,"203.0.113.9"), base_url="http://localhost:8000")
    try:
        assert remoto.get(BASE+"/autenticacao/teste-local").json() == {"ativo":False,"contas":[]}
        assert remoto.post(BASE+"/autenticacao/teste-local/entrar",json={"usuario_id":4},headers={"X-MEC-TESTE-LOCAL":"1"}).status_code == 403
    finally: remoto.close()
    with sqlite3.connect(acesso.caminho) as banco:
        assert banco.execute("SELECT COUNT(*) FROM sessoes_acesso").fetchone()[0] == 0


@pytest.mark.parametrize("cliente,host,cabecalhos,ambiente,esperado",[
    ("127.0.0.1","localhost",{},"desenvolvimento",True),
    ("::1","localhost",{},"teste",True),
    ("127.0.0.1","localhost",{"origin":"http://localhost:5173"},"desenvolvimento",True),
    ("203.0.113.9","localhost",{},"desenvolvimento",False),
    ("127.0.0.1","externo.local",{},"desenvolvimento",False),
    ("127.0.0.1","localhost",{"origin":"https://externo.local"},"desenvolvimento",False),
    ("127.0.0.1","localhost",{"origin":"null"},"desenvolvimento",False),
    ("127.0.0.1","localhost",{"x-forwarded-for":"203.0.113.9"},"desenvolvimento",False),
    ("127.0.0.1","localhost",{"sec-fetch-site":"cross-site"},"desenvolvimento",False),
    ("127.0.0.1","localhost",{},"producao",False),
])
def test_guardas_local_e_ambiente(monkeypatch,cliente,host,cabecalhos,ambiente,esperado):
    monkeypatch.setenv("MEC_MODO_TESTE_LOCAL","1")
    monkeypatch.setenv("MEC_AMBIENTE",ambiente)
    request = Request({"type":"http","http_version":"1.1","method":"GET","scheme":"http","path":"/api/v1/autenticacao/teste-local",
        "raw_path":b"/api/v1/autenticacao/teste-local","query_string":b"","root_path":"", "client":(cliente,50000),"server":(host,8000),
        "headers":[(k.encode(),v.encode()) for k,v in cabecalhos.items()]})
    assert modo_teste_disponivel(request) is esperado
