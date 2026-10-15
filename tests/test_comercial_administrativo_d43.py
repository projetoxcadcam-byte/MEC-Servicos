"""D43: consulta real, decisão administrativa, concorrência e preservação."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import sqlite3
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from test_documentacao_cotacao_d42 import upload, liberar
from backend.app.models.comercial_admin import EventoDecisaoCotacaoAdmin
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.cotacao import ServicoCotacao, CotacaoNaoPendente, SolicitacaoJaPossuiCotacaoAceita
from backend.app.services.comercial_admin import ServicoComercialAdmin
from backend.app.schemas.comercial_admin import DecisaoComercial
from backend.app.core.armazenamento_acesso import UsuarioAcesso

pytestmark = pytest.mark.acesso_real
COM = BASE + "/administracao/comercial"


@pytest.fixture
def comercial(ambiente):
    http, acesso, sessoes, app = ambiente
    with sessoes() as b:
        original = b.get(SolicitacaoServico, 3)
        dados = {c: getattr(original, c) for c in ("empresa_cliente_id", "processo_id", "material_id",
            "dimensao_x_maxima_mm", "dimensao_y_maxima_mm", "dimensao_z_maxima_mm", "tolerancia_requerida_mm")}
        b.add(SolicitacaoServico(id=9, quantidade=10, observacoes="Desenho e requisito completo do cliente.", **dados))
        b.flush()
        agora = datetime.now(timezone.utc).replace(tzinfo=None)
        b.add_all([CotacaoFornecedor(id=8, solicitacao_id=9, empresa_fornecedora_id=4,
            valor_total=Decimal("1500.00"), prazo_dias=7, validade_dias=10, criada_em=agora, status="enviada", observacoes="Prazo e condições da oficina."),
            CotacaoFornecedor(id=9, solicitacao_id=9, empresa_fornecedora_id=8,
            valor_total=Decimal("1275.55"), prazo_dias=9, validade_dias=12, criada_em=agora, status="enviada")])
        b.commit()
    entrar(http, "admin")
    return http, acesso, sessoes, app


def detalhe(http, sid=9):
    r = http.get(COM + f"/solicitacoes/{sid}")
    assert r.status_code == 200, r.text
    return r.json()


def corpo(http, acao="aceitar", **extras):
    return {"acao": acao, "versao": detalhe(http)["versao"],
        "registro_interno": "Conferência administrativa da proposta e requisitos.",
        "chave_operacao": str(uuid4()), **extras}


def decidir(http, dados, cotacao=8, sid=9):
    return http.post(COM + f"/solicitacoes/{sid}/cotacoes/{cotacao}/decisoes", json=dados)


def estado(sessoes):
    with sessoes() as b:
        return {q.id: (q.status, q.encerrada_em, q.decidida_por_empresa_id) for q in b.scalars(select(CotacaoFornecedor))}, list(b.scalars(select(EventoDecisaoCotacaoAdmin)))


def retrato(sessoes, excluir=()):
    # D45: este retrato verifica o negócio. Avisos e leituras são conferidos na suíte de notificações.
    excluir = (*excluir, "notificacoes_perfis", "leituras_notificacoes")
    banco = Path(sessoes.kw["bind"].url.database)
    with sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True) as c:
        nomes = [n for (n,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: c.execute('SELECT * FROM "' + n.replace('"', '""') + '" ORDER BY rowid').fetchall() for n in nomes if n not in excluir}


def test_consulta_solicitacao_e_cotacao_reais_com_filtro_por_numero(comercial):
    http, _, sessoes, _ = comercial
    antes = retrato(sessoes)
    r = http.get(COM + "/solicitacoes", params={"solicitacao_id": 9})
    assert r.status_code == 200 and r.json()["total"] == 1
    s = r.json()["itens"][0]
    assert s["id"] == 9 and s["cliente"] == "Razao Privada 2" and s["quantidade"] == 10
    assert s["cotacoes_total"] == 2 and s["cotacoes_aceitas"] == 0
    assert s["processo"] == "Usinagem CNC" and s["material"] == "Alumínio 6061"
    r = http.get(COM + "/cotacoes", params={"solicitacao_id": 9, "cotacao_id": 8, "status": "enviada"})
    assert r.status_code == 200 and r.json()["total"] == 1
    q = r.json()["itens"][0]
    assert q["id"] == 8 and q["valor_total"] == "1500.00" and q["prazo_dias"] == 7
    assert q["fornecedor"] == "Razao Privada 4" and q["cliente"] == "Razao Privada 2"
    d = detalhe(http)
    assert len(d["versao"]) == 64 and [q["id"] for q in d["cotacoes"]] == [8, 9]
    assert all(q["pode_decidir"] for q in d["cotacoes"])
    assert retrato(sessoes) == antes


def test_paginacao_e_varios_arquivos_nao_multiplicam_solicitacoes_ou_cotacoes(comercial):
    http, _, _, _ = comercial
    for i in range(2):
        upload(http, nome=f"desenho{i}.pdf", solicitacao=9)
    entrar(http, "admin")
    p1 = http.get(COM + "/solicitacoes", params={"limite": 1}).json()
    p2 = http.get(COM + "/solicitacoes", params={"limite": 1, "deslocamento": 1}).json()
    assert p1["total"] == p2["total"] == 5 and p1["itens"][0]["id"] != p2["itens"][0]["id"]
    s = http.get(COM + "/solicitacoes", params={"solicitacao_id": 9}).json()["itens"][0]
    assert s["arquivos_ativos"] == 2 and s["cotacoes_total"] == 2
    q = http.get(COM + "/cotacoes", params={"solicitacao_id": 9, "limite": 1}).json()
    assert q["total"] == 2 and len(q["itens"]) == 1
    assert len(detalhe(http)["arquivos"]) == 2


@pytest.mark.parametrize("perfil", [None, "cliente", "fornecedor"])
def test_leitura_e_decisao_exigem_sessao_real_de_administrador(comercial, perfil):
    http, _, sessoes, _ = comercial
    dados = corpo(http); antes = retrato(sessoes)
    if perfil: entrar(http, perfil)
    else: http.cookies.clear(); http.headers.pop("X-MEC-CSRF", None)
    esperado = 401 if perfil is None else 403
    for caminho in ("/solicitacoes", "/cotacoes", "/solicitacoes/9"):
        assert http.get(COM + caminho).status_code == esperado
    assert decidir(http, dados).status_code == esperado
    assert retrato(sessoes) == antes


def test_csrf_e_origem_recusam_escrita_sem_alterar_registros(comercial):
    http, _, sessoes, _ = comercial
    dados = corpo(http); antes = retrato(sessoes)
    url = COM + "/solicitacoes/9/cotacoes/8/decisoes"
    assert http.post(url, json=dados, headers={"X-MEC-CSRF": "falso"}).status_code == 403
    assert http.post(url, json=dados, headers={"Origin": "https://outro.invalid"}).status_code == 403
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("alteracao", [
    {"usuario_admin_id": 9999}, {"empresa_cliente_id": 6}, {"perfil": "admin"}, {"acao": "cancelar"},
    {"registro_interno": "  "}, {"versao": "errada"}, {"chave_operacao": "errada"},
])
def test_corpo_validado_e_operador_definido_pelo_servidor(comercial, alteracao):
    http, _, sessoes, _ = comercial
    antes = retrato(sessoes)
    assert decidir(http, corpo(http, **alteracao)).status_code == 422
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("endpoint,params", [
    ("/solicitacoes", {"solicitacao_id": 0}), ("/solicitacoes", {"status": "inventada"}),
    ("/cotacoes", {"cotacao_id": -1}), ("/cotacoes", {"status": "aberta"}),
    ("/cotacoes", {"limite": 101}), ("/solicitacoes", {"deslocamento": -1}),
])
def test_filtros_invalidos_recusados(comercial, endpoint, params):
    http, _, _, _ = comercial
    assert http.get(COM + endpoint, params=params).status_code == 422


def test_aceite_auditado_recusa_demais_pendentes_e_preserva_outros_modulos(comercial):
    http, _, sessoes, _ = comercial
    a = upload(http, solicitacao=9); liberar(http, a); entrar(http, "admin")
    preservado = retrato(sessoes, ("cotacoes_fornecedor", "eventos_decisoes_cotacao_admin"))
    legado = estado(sessoes)[0]
    dados = corpo(http)
    r = decidir(http, dados)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "aceita" and r.json()["cotacoes_recusadas"] == [9]
    qs, eventos = estado(sessoes)
    assert qs[8][0] == "aceita" and qs[9][0] == "recusada"
    assert qs[8][1] == qs[9][1] and qs[8][2] == qs[9][2] == 2
    assert all(qs[i] == legado[i] for i in (1, 2, 4))
    assert len(eventos) == 1 and eventos[0].usuario_admin_id == 1 and eventos[0].administrador_nome == "Admin"
    assert eventos[0].registro_interno == dados["registro_interno"]
    assert retrato(sessoes, ("cotacoes_fornecedor", "eventos_decisoes_cotacao_admin")) == preservado
    d = detalhe(http)
    assert not any(q["pode_decidir"] for q in d["cotacoes"])
    assert d["historico"][0]["cotacoes_recusadas"] == [9]
    assert d["solicitacao"]["contratacao_id"] is None
    entrar(http, "fornecedor")
    r = http.get(BASE + "/portal-fornecedor/cotacoes", params={"empresa_fornecedora_id": 4})
    assert r.status_code == 200 and "Conferência administrativa" not in r.text
    assert "Razao Privada 2" not in r.text


def test_recusa_individual_mantem_a_outra_proposta_disponivel(comercial):
    http, _, sessoes, _ = comercial
    r = decidir(http, corpo(http, "recusar"))
    assert r.status_code == 200 and r.json()["cotacoes_recusadas"] == []
    qs, eventos = estado(sessoes)
    assert qs[8][0] == "recusada" and qs[9][0] == "enviada" and len(eventos) == 1
    assert detalhe(http)["cotacoes"][1]["pode_decidir"]


def test_reenvio_da_mesma_operacao_retorna_o_mesmo_evento(comercial):
    http, _, sessoes, _ = comercial
    dados = corpo(http)
    primeira = decidir(http, dados)
    segunda = decidir(http, dados)
    assert primeira.status_code == segunda.status_code == 200
    assert primeira.json() == segunda.json() and len(estado(sessoes)[1]) == 1
    assert decidir(http, {**dados, "registro_interno": "Outro motivo"}).status_code == 409
    assert decidir(http, {**dados, "acao": "recusar"}).status_code == 409
    assert len(estado(sessoes)[1]) == 1


def test_alteracao_de_valor_e_nova_proposta_invalidam_analise_antiga(comercial):
    http, _, sessoes, _ = comercial
    dados = corpo(http)
    with sessoes() as b:
        b.get(CotacaoFornecedor, 9).valor_total = Decimal("1200.00"); b.commit()
    assert decidir(http, dados).status_code == 409 and not estado(sessoes)[1]
    dados = corpo(http)
    with sessoes() as b:
        b.add(Empresa(id=10, razao_social="Novo fornecedor", documento="doc-10", tipo_empresa="fornecedor")); b.flush()
        b.add(CotacaoFornecedor(id=10, solicitacao_id=9, empresa_fornecedora_id=10, valor_total=1000, prazo_dias=5, validade_dias=10)); b.commit()
    assert decidir(http, dados).status_code == 409
    assert estado(sessoes)[0][8][0] == "enviada" and not estado(sessoes)[1]


def test_expiracao_apenas_exibida_na_leitura_e_bloqueia_aceite(comercial):
    http, _, sessoes, _ = comercial
    with sessoes() as b:
        b.get(CotacaoFornecedor, 8).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=20); b.commit()
    antes = retrato(sessoes)
    d = detalhe(http)
    assert d["cotacoes"][0]["status"] == "expirada" and not d["cotacoes"][0]["pode_decidir"]
    p = http.get(COM + "/cotacoes", params={"solicitacao_id": 9, "status": "expirada"}).json()
    assert p["total"] == 1 and p["itens"][0]["id"] == 8
    assert retrato(sessoes) == antes
    r = decidir(http, corpo(http))
    assert r.status_code == 409 and r.json()["detail"] == "cotacao_expirada"
    assert retrato(sessoes) == antes


def test_aceite_expira_outras_vencidas_sem_recusa_comercial(comercial):
    http, _, sessoes, _ = comercial
    with sessoes() as b:
        b.get(CotacaoFornecedor, 9).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30); b.commit()
    r = decidir(http, corpo(http))
    assert r.status_code == 200 and r.json()["cotacoes_recusadas"] == [] and r.json()["cotacoes_expiradas"] == [9]
    assert estado(sessoes)[0][9][0] == "expirada"


@pytest.mark.parametrize("situacao", ["encerrada", "cancelada"])
def test_solicitacao_fechada_nao_recebe_decisao(comercial, situacao):
    http, _, sessoes, _ = comercial
    with sessoes() as b:
        b.get(SolicitacaoServico, 9).status = situacao; b.commit()
    antes = retrato(sessoes)
    assert decidir(http, corpo(http)).status_code == 409
    assert not any(q["pode_decidir"] for q in detalhe(http)["cotacoes"])
    assert retrato(sessoes) == antes


def test_contratacao_existente_impede_nova_decisao(comercial):
    http, _, sessoes, _ = comercial
    with sessoes() as b:
        b.add(ContratacaoServico(id=9, solicitacao_id=9, cotacao_id=8, empresa_cliente_id=2,
            empresa_fornecedora_id=4, valor_total=1500, prazo_dias=7, status="ativa")); b.commit()
    antes = retrato(sessoes)
    assert decidir(http, corpo(http)).status_code == 409
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("mesma_chave", [False, True])
def test_confirmacoes_concorrentes_produzem_um_unico_aceite(comercial, mesma_chave):
    http, _, sessoes, app = comercial
    dados = corpo(http); cookie = dict(http.cookies); headers = dict(http.headers)
    def chamada(indice):
        outro = TestClient(app)
        try:
            outro.cookies.update(cookie); outro.headers.update(headers)
            return decidir(outro, dados if mesma_chave else {**dados, "chave_operacao": str(uuid4())}, 8 if mesma_chave or indice == 0 else 9)
        finally: outro.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(chamada, (0, 1)))
    assert sorted(r.status_code for r in resultados) == ([200, 200] if mesma_chave else [200, 409])
    if mesma_chave: assert resultados[0].json() == resultados[1].json()
    qs, eventos = estado(sessoes)
    assert sum(qs[i][0] == "aceita" for i in (8, 9)) == 1 and len(eventos) == 1


def test_falha_ao_gravar_evento_reverte_todas_as_decisoes(comercial):
    http, _, sessoes, _ = comercial
    dados = corpo(http); antes = retrato(sessoes); engine = sessoes.kw["bind"]
    def falhar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO eventos_decisoes_cotacao_admin"):
            raise RuntimeError("Falha isolada no registro do evento")
    event.listen(engine, "before_cursor_execute", falhar)
    try:
        with pytest.raises(RuntimeError, match="Falha isolada"):
            decidir(http, dados)
    finally: event.remove(engine, "before_cursor_execute", falhar)
    assert retrato(sessoes) == antes


def test_rota_legada_e_decisao_d43_serializadas_na_mesma_solicitacao(comercial):
    http, _, sessoes, _ = comercial
    dados = DecisaoComercial(**corpo(http))
    usuario = UsuarioAcesso(1, "Admin", "admin@teste.local", "admin", None, False)
    def atual():
        with sessoes() as b:
            try: ServicoComercialAdmin(b).registrar(9, 8, dados, usuario); return "aceita"
            except Exception as e:
                assert getattr(e, "status_code", None) == 409; return "conflito"
    def legado():
        with sessoes() as b:
            try: ServicoCotacao(b).aceitar(9, 9, 2); return "aceita"
            except (CotacaoNaoPendente, SolicitacaoJaPossuiCotacaoAceita): return "conflito"
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(atual), pool.submit(legado)
        assert sorted([a.result(), b.result()]) == ["aceita", "conflito"]
    qs, _ = estado(sessoes)
    assert sum(qs[i][0] == "aceita" for i in (8, 9)) == 1


def test_documentacao_envio_fornecedor_consulta_admin_e_decisao_real(comercial):
    http, _, sessoes, _ = comercial
    with sessoes() as b:
        b.delete(b.get(CotacaoFornecedor, 8)); b.delete(b.get(CotacaoFornecedor, 9)); b.commit()
    a = upload(http, solicitacao=9); liberar(http, a)
    entrar(http, "fornecedor")
    r = http.post(BASE + "/portal-fornecedor/solicitacoes/9/cotacoes", json={
        "empresa_fornecedora_id": 4, "valor_total": "1500.00", "prazo_dias": 7, "validade_dias": 10})
    assert r.status_code == 201, r.text
    cotacao_id = r.json()["id"]
    entrar(http, "admin")
    d = detalhe(http)
    assert d["arquivos"][0]["liberado"] and d["cotacoes"][0]["id"] == cotacao_id
    r = decidir(http, corpo(http), cotacao=cotacao_id)
    assert r.status_code == 200 and r.json()["status"] == "aceita"
