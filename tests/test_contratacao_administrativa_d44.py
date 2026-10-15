"""D44: confirmação real, transação completa, concorrência, material e privacidade."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_comercial_administrativo_d43 import comercial, corpo as corpo_decisao, decidir, retrato
from test_documentacao_cotacao_d42 import upload, liberar
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.contratacao_admin import EventoContratacaoAdmin
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.documentacao_cotacao import LiberacaoArquivoCotacao
from backend.app.models.intermediacao import CicloIntermediacao, EventoIntermediacao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.contratacao import ContratacaoCriacao
from backend.app.schemas.contratacao_admin import ConfirmacaoContratacaoAdmin
from backend.app.schemas.ordem_servico import OrdemServicoCriacao
from backend.app.services.contratacao import ServicoContratacao, ContratacaoJaExiste, ContratacaoSolicitacaoNaoAberta
from backend.app.services.contratacao_admin import ServicoContratacaoAdmin
from backend.app.services.ordem_servico import ServicoOrdemServico, OrdemServicoDuplicada

pytestmark = pytest.mark.acesso_real
ADM = BASE + "/administracao"
PRE = ADM + "/contratacoes/preparacao/9"


@pytest.fixture
def contratacao_admin(comercial):
    http, acesso, sessoes, app = comercial
    arquivo = upload(http, nome="desenho-conferido.pdf", solicitacao=9)
    liberar(http, arquivo)
    r = decidir(http, corpo_decisao(http))
    assert r.status_code == 200, r.text
    return http, acesso, sessoes, app


def preparacao(http):
    r = http.get(PRE)
    assert r.status_code == 200, r.text
    return r.json()


def corpo(http, **extras):
    d = preparacao(http)
    return {"acao": d["acao_disponivel"] or "contratar_e_abrir_os", "cotacao_id": 8, "versao": d["versao"],
        "registro_interno": "CONFERENCIA-INTERNA-D44: proposta, desenho e lote aprovados.",
        "observacoes_execucao": "Fresar o lote conforme o desenho aprovado.", "chave_operacao": str(uuid4()), **extras}


def confirmar(http, dados=None):
    return http.post(PRE + "/confirmar", json=dados or corpo(http))


def test_conferencia_aceite_documento_e_leituras_nao_gravam(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    antes = retrato(sessoes)
    d = preparacao(http)
    assert d["acao_disponivel"] == "contratar_e_abrir_os" and d["contratacao"] is None
    assert d["cotacao"]["id"] == 8 and d["cotacao"]["status"] == "aceita"
    assert d["cotacao"]["valor_total"] == "1500.00" and d["cotacao"]["prazo_dias"] == 7
    assert d["solicitacao"]["quantidade"] == 10 and d["arquivos"][0]["liberado"]
    assert d["historico"] == [] and len(d["versao"]) == 64
    for url in (ADM + "/contratacoes", ADM + "/ordens-servico", ADM + "/contratacoes/1"):
        assert http.get(url).status_code == 200
    assert retrato(sessoes) == antes


def test_confirmacao_copia_proposta_cria_os_ciclo_eventos_e_preserva_historicos(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    antes = retrato(sessoes)
    r = confirmar(http); assert r.status_code == 200, r.text
    res = r.json(); assert res["etapa_administrativa"] == "aguardando_material" and res["ordem_status"] == "aberta"
    with sessoes() as b:
        c = b.get(ContratacaoServico, res["contratacao_id"]); o = b.get(OrdemServico, res["ordem_servico_id"])
        q = b.get(CotacaoFornecedor, 8); s = b.get(SolicitacaoServico, 9)
        assert c.valor_total == o.valor_total == q.valor_total and c.prazo_dias == o.prazo_dias == 7
        assert c.empresa_cliente_id == o.empresa_cliente_id == s.empresa_cliente_id == 2
        assert c.empresa_fornecedora_id == o.empresa_fornecedora_id == q.empresa_fornecedora_id == 4
        assert o.quantidade == s.quantidade == 10 and o.processo_id == s.processo_id and o.material_id == s.material_id
        assert c.observacoes == o.observacoes == "Fresar o lote conforme o desenho aprovado."
        assert s.status == "encerrada" and q.status == "aceita" and o.iniciada_em is None
        ciclo = b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == o.id))
        assert ciclo.status == "aguardando_material" and ciclo.versao == 1
        audit = b.get(EventoContratacaoAdmin, res["evento_id"])
        e = b.scalar(select(EventoIntermediacao).where(EventoIntermediacao.ciclo_id == ciclo.id))
        assert audit.usuario_admin_id > 0 and e.usuario_admin_id == audit.usuario_admin_id
        assert e.acao == "iniciar_ciclo" and e.registro_interno == audit.registro_interno
    depois = retrato(sessoes)
    alterados = {"solicitacoes_servico", "contratacoes_servico", "ordens_servico", "ciclos_intermediacao", "eventos_intermediacao", "eventos_contratacoes_admin"}
    assert {n: v for n, v in depois.items() if n not in alterados} == {n: v for n, v in antes.items() if n not in alterados}
    for n in alterados - {"solicitacoes_servico"}:
        assert depois[n][:len(antes[n])] == antes[n]
    d = preparacao(http)
    assert d["acao_disponivel"] is None and d["contratacao"]["id"] == res["contratacao_id"]
    assert d["historico"][0]["ordem_servico_id"] == res["ordem_servico_id"]
    assert d["historico"][0]["registro_interno"].startswith("CONFERENCIA-INTERNA-D44")


@pytest.mark.parametrize("perfil", [None, "cliente", "fornecedor"])
def test_rotas_administrativas_recusam_anonimo_e_outros_perfis(contratacao_admin, perfil):
    http, _, sessoes, _ = contratacao_admin
    dados = corpo(http); antes = retrato(sessoes)
    if perfil: entrar(http, perfil)
    else: http.cookies.clear(); http.headers.pop("X-MEC-CSRF", None)
    esperado = 401 if perfil is None else 403
    for url in (PRE, ADM + "/contratacoes", ADM + "/contratacoes/1", ADM + "/ordens-servico"):
        assert http.get(url).status_code == esperado
    assert confirmar(http, dados).status_code == esperado and retrato(sessoes) == antes


def test_csrf_origem_e_corpo_nao_permitido_preservam_banco(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    dados = corpo(http); antes = retrato(sessoes)
    assert http.post(PRE + "/confirmar", json=dados, headers={"X-MEC-CSRF": "falso"}).status_code == 403
    assert http.post(PRE + "/confirmar", json=dados, headers={"Origin": "https://invalido.local"}).status_code == 403
    for extras in ({"usuario_admin_id": 999}, {"empresa_cliente_id": 7}, {"valor_total": "10.00"}, {"quantidade": 1}, {"perfil": "admin"}):
        assert confirmar(http, {**dados, **extras}).status_code == 422
    assert confirmar(http, {**dados, "registro_interno": "   "}).status_code == 422
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("url,params", [
    ("contratacoes", {"solicitacao_id": 0}), ("contratacoes", {"contratacao_id": -1}),
    ("contratacoes", {"status": "aberta"}), ("contratacoes", {"limite": 101}),
    ("contratacoes", {"deslocamento": -1}), ("ordens-servico", {"ordem_servico_id": 0}),
    ("ordens-servico", {"status": "ativa"}), ("ordens-servico", {"limite": 0}),
])
def test_filtros_invalidos_recusados(contratacao_admin, url, params):
    http, _, sessoes, _ = contratacao_admin; antes = retrato(sessoes)
    assert http.get(ADM + "/" + url, params=params).status_code == 422 and retrato(sessoes) == antes


def test_paginacao_filtros_e_documentos_nao_multiplicam_contratacao(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    a = upload(http, nome="segundo-desenho.pdf", solicitacao=9); liberar(http, a)
    r = confirmar(http); assert r.status_code == 200, r.text
    res = r.json(); antes = retrato(sessoes)
    p = http.get(ADM + "/contratacoes", params={"solicitacao_id": 9, "status": "ativa"}).json()
    assert p["total"] == 1 and p["itens"][0]["id"] == res["contratacao_id"]
    p = http.get(ADM + "/ordens-servico", params={"ordem_servico_id": res["ordem_servico_id"], "status": "aberta"}).json()
    assert p["total"] == 1 and p["itens"][0]["etapa_administrativa"] == "aguardando_material"
    p1 = http.get(ADM + "/contratacoes", params={"limite": 1}).json()
    p2 = http.get(ADM + "/contratacoes", params={"limite": 1, "deslocamento": 1}).json()
    assert p1["total"] == p2["total"] and p1["total"] > 1 and p1["itens"][0]["id"] != p2["itens"][0]["id"]
    assert http.get(ADM + "/contratacoes", params={"solicitacao_id": 9999}).json()["total"] == 0
    assert http.get(ADM + "/contratacoes/9999").status_code == http.get(ADM + "/contratacoes/preparacao/9999").status_code == 404
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("mudanca", ["valor", "quantidade", "documento", "revogacao", "novo_arquivo"])
def test_analise_antiga_recusada_sem_criar_contratacao(contratacao_admin, mudanca):
    http, _, sessoes, _ = contratacao_admin; dados = corpo(http)
    with sessoes() as b:
        if mudanca == "valor": b.get(CotacaoFornecedor, 8).valor_total = "1999.99"
        elif mudanca == "quantidade": b.get(SolicitacaoServico, 9).quantidade = 11
        elif mudanca == "revogacao": b.scalar(select(LiberacaoArquivoCotacao).join(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id == 9)).disponivel = False
        elif mudanca == "documento":
            a = b.scalar(select(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id == 9))
            Path(a.caminho_arquivo).write_bytes(b"desenho alterado fora do banco")
        b.commit()
    if mudanca == "novo_arquivo": upload(http, nome="nova-revisao.pdf", solicitacao=9); entrar(http, "admin")
    antes = retrato(sessoes)
    r = confirmar(http, dados)
    assert r.status_code == 409 and r.json()["detail"] == "preparacao_contratacao_alterada_atualize"
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("situacao", ["sem_documento", "sem_aceite", "duas_aceitas", "cancelada", "vinculo"])
def test_preparacao_sem_condicoes_nao_recebe_confirmacao(contratacao_admin, situacao):
    http, _, sessoes, _ = contratacao_admin
    with sessoes() as b:
        if situacao == "sem_documento": b.scalar(select(LiberacaoArquivoCotacao).join(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id == 9)).disponivel = False
        elif situacao == "sem_aceite": b.get(CotacaoFornecedor, 8).status = "enviada"
        elif situacao == "duas_aceitas": b.get(CotacaoFornecedor, 9).status = "aceita"
        elif situacao == "cancelada": b.get(SolicitacaoServico, 9).status = "cancelada"
        elif situacao == "vinculo": b.get(CotacaoFornecedor, 8).decidida_por_empresa_id = 7
        b.commit()
    assert preparacao(http)["acao_disponivel"] is None
    antes = retrato(sessoes); assert confirmar(http).status_code == 409 and retrato(sessoes) == antes


def test_contratacao_legada_ativa_sem_os_abre_ordem_sem_recriar_contrato(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    with sessoes() as b:
        c = ServicoContratacao(b).criar(9, ContratacaoCriacao(empresa_cliente_id=2, cotacao_id=8, observacoes="Instrução contratada anteriormente."))
        cid = c.id
    antes = retrato(sessoes)
    assert preparacao(http)["acao_disponivel"] == "abrir_os"
    r = confirmar(http, corpo(http, observacoes_execucao=None)); assert r.status_code == 200, r.text
    assert r.json()["contratacao_id"] == cid
    depois = retrato(sessoes)
    assert depois["contratacoes_servico"] == antes["contratacoes_servico"] and depois["solicitacoes_servico"] == antes["solicitacoes_servico"]
    with sessoes() as b:
        assert b.get(OrdemServico, r.json()["ordem_servico_id"]).observacoes == "Instrução contratada anteriormente."
    assert confirmar(http, corpo(http, acao="abrir_os", observacoes_execucao=None)).status_code == 409


def test_repeticao_mesma_chave_nao_cria_segunda_os_e_corpo_diferente_recusado(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin; dados = corpo(http)
    r1 = confirmar(http, dados); assert r1.status_code == 200, r1.text
    antes = retrato(sessoes)
    r2 = confirmar(http, dados); assert r2.status_code == 200 and r2.json() == r1.json()
    assert confirmar(http, {**dados, "registro_interno": "Outro motivo"}).status_code == 409
    assert confirmar(http, {**dados, "observacoes_execucao": "Outra instrução"}).status_code == 409
    assert confirmar(http, {**dados, "chave_operacao": str(uuid4())}).status_code == 409
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("mesma_chave", [False, True])
def test_confirmações_concorrentes_produzem_uma_contratacao_os_e_ciclo(contratacao_admin, mesma_chave):
    http, _, sessoes, app = contratacao_admin; dados = corpo(http)
    def executar(chave):
        h = TestClient(app)
        try:
            h.cookies.update(http.cookies); h.headers.update(http.headers)
            return confirmar(h, {**dados, "chave_operacao": chave})
        finally: h.close()
    chaves = [dados["chave_operacao"], dados["chave_operacao"] if mesma_chave else str(uuid4())]
    with ThreadPoolExecutor(max_workers=2) as pool: rs = list(pool.map(executar, chaves))
    assert sorted(r.status_code for r in rs) == ([200, 200] if mesma_chave else [200, 409])
    if mesma_chave: assert rs[0].json() == rs[1].json()
    with sessoes() as b:
        cs = b.scalars(select(ContratacaoServico).where(ContratacaoServico.solicitacao_id == 9)).all()
        os = b.scalars(select(OrdemServico).where(OrdemServico.solicitacao_id == 9)).all()
        assert len(cs) == len(os) == 1
        assert len(b.scalars(select(EventoContratacaoAdmin).where(EventoContratacaoAdmin.solicitacao_id == 9)).all()) == 1
        assert len(b.scalars(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == os[0].id)).all()) == 1


@pytest.mark.parametrize("modelo", [OrdemServico, CicloIntermediacao, EventoIntermediacao, EventoContratacaoAdmin])
def test_falha_na_gravacao_desfaz_toda_a_confirmacao(contratacao_admin, modelo):
    http, _, sessoes, _ = contratacao_admin; dados = corpo(http); antes = retrato(sessoes)
    def falhar(*args): raise IntegrityError("insert", {}, Exception("Falha isolada D44"))
    event.listen(modelo, "before_insert", falhar)
    try: r = confirmar(http, dados)
    finally: event.remove(modelo, "before_insert", falhar)
    assert r.status_code == 409 and retrato(sessoes) == antes


def test_rota_antiga_concorrente_nao_duplica_nem_sobrescreve_contratacao(contratacao_admin):
    http, _, sessoes, app = contratacao_admin; dados = corpo(http)
    def nova():
        h = TestClient(app)
        try:
            h.cookies.update(http.cookies); h.headers.update(http.headers)
            return confirmar(h, dados).status_code
        finally: h.close()
    def antiga():
        with sessoes() as b:
            try: ServicoContratacao(b).criar(9, ContratacaoCriacao(empresa_cliente_id=2, cotacao_id=8)); return 200
            except (ContratacaoJaExiste, ContratacaoSolicitacaoNaoAberta): return 409
    with ThreadPoolExecutor(max_workers=2) as pool: rs = list(pool.map(lambda fn: fn(), [nova, antiga]))
    assert sorted(rs) == [200, 409]
    with sessoes() as b:
        assert len(b.scalars(select(ContratacaoServico).where(ContratacaoServico.solicitacao_id == 9)).all()) == 1


def test_rota_antiga_concorrente_nao_duplica_os_de_contrato_existente(contratacao_admin):
    http, _, sessoes, app = contratacao_admin
    with sessoes() as b: cid = ServicoContratacao(b).criar(9, ContratacaoCriacao(empresa_cliente_id=2, cotacao_id=8)).id
    dados = corpo(http, observacoes_execucao=None)
    def nova():
        h = TestClient(app)
        try:
            h.cookies.update(http.cookies); h.headers.update(http.headers)
            return confirmar(h, dados).status_code
        finally: h.close()
    def antiga():
        with sessoes() as b:
            try: ServicoOrdemServico(b).criar(cid, OrdemServicoCriacao(empresa_cliente_id=2)); return 200
            except OrdemServicoDuplicada: return 409
    with ThreadPoolExecutor(max_workers=2) as pool: rs = list(pool.map(lambda fn: fn(), [nova, antiga]))
    assert sorted(rs) == [200, 409]
    with sessoes() as b: assert len(b.scalars(select(OrdemServico).where(OrdemServico.contratacao_id == cid)).all()) == 1


def test_portais_recebem_contrato_sem_motivo_interno_e_producao_aguarda_material(contratacao_admin):
    http, _, _, _ = contratacao_admin
    r = confirmar(http); assert r.status_code == 200, r.text
    cid, oid = r.json()["contratacao_id"], r.json()["ordem_servico_id"]
    for perfil, campo, empresa in [("cliente", "empresa_cliente_id", 2), ("fornecedor", "empresa_fornecedora_id", 4)]:
        entrar(http, perfil)
        for url in (f"/portal-{perfil}/contratacoes/{cid}", f"/portal-{perfil}/ordens-servico/{oid}", f"/portal-{perfil}/intermediacao/{oid}"):
            res = http.get(BASE + url, params={campo: empresa})
            assert res.status_code == 200, res.text
            contraparte = "Razao Privada 4" if perfil == "cliente" else "Razao Privada 2"
            assert "CONFERENCIA-INTERNA-D44" not in res.text and contraparte not in res.text
    inicio = BASE + f"/portal-fornecedor/ordens-servico/{oid}/iniciar"
    assert http.post(inicio, json={"empresa_fornecedora_id": 4}).status_code == 409
    entrar(http, "admin")
    d31 = ADM + f"/intermediacao/ordens/{oid}/eventos"
    assert http.post(d31, json={"acao": "receber_material", "versao": 1, "registro_interno": "Recebido pela administração."}).status_code == 201
    assert http.post(d31, json={"acao": "encaminhar_material", "versao": 2, "registro_interno": "Material encaminhado ao fornecedor.", "referencia": "Comprovante de encaminhamento."}).status_code == 201
    entrar(http, "fornecedor")
    assert http.post(inicio, json={"empresa_fornecedora_id": 4}).status_code == 200


def test_servico_nao_aceita_admin_sem_id_real(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    dados = ConfirmacaoContratacaoAdmin(**corpo(http)); antes = retrato(sessoes)
    from fastapi import HTTPException
    with sessoes() as b:
        with pytest.raises(HTTPException) as e:
            ServicoContratacaoAdmin(b).confirmar(9, dados, UsuarioAcesso(0, "Admin falso", "x@x.local", "admin", None, False))
        assert e.value.status_code == 403
    assert retrato(sessoes) == antes
