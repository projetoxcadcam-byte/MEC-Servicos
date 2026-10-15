"""D47: comparação privada, médias exatas, propostas válidas e leitura sem mutações."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import sqlite3

import pytest
from sqlalchemy import event, select
from test_comercial_administrativo_d43 import comercial, ambiente, modelo_acessos, entrar, COM, corpo, decidir
from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.avaliacao_perfil import AvaliacaoAdministrativa
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.comercial_admin import EventoDecisaoCotacaoAdmin

pytestmark = pytest.mark.acesso_real
URL = COM + "/solicitacoes/9/comparacao"


def retrato(sessoes):
    caminho = Path(sessoes.kw["bind"].url.database)
    with sqlite3.connect(caminho.as_uri() + "?mode=ro", uri=True) as b:
        tabelas = [n for (n,) in b.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: b.execute('SELECT * FROM "' + n.replace('"', '""') + '" ORDER BY rowid').fetchall() for n in tabelas}


@pytest.fixture
def propostas(comercial):
    http, acesso, sessoes, app = comercial
    with sessoes() as b:
        b.add(Empresa(id=10, razao_social="Fornecedor sem notas", documento="d47-fornecedor", tipo_empresa="fornecedor"))
        b.flush()
        b.add(CotacaoFornecedor(id=10, solicitacao_id=9, empresa_fornecedora_id=10,
            valor_total=Decimal("900.13"), prazo_dias=4, validade_dias=5, status="enviada"))
        for cid, fornecedor, cliente, nota_cliente, nota_admin in [(1,4,2,5,4), (4,4,2,1,5), (2,8,6,4,3)]:
            b.add(AvaliacaoOficina(contratacao_id=cid, ordem_servico_id=cid, empresa_cliente_id=cliente,
                empresa_fornecedora_id=fornecedor, nota=nota_cliente, comentario="COMENTARIO-PRIVADO-D47"))
            b.add(AvaliacaoAdministrativa(contratacao_id=cid, ordem_servico_id=cid, empresa_cliente_id=cliente,
                empresa_fornecedora_id=fornecedor, nota=nota_admin, comentario="REGISTRO-INTERNO-D47",
                usuario_id=1, nome_autor="AUTOR-PRIVADO-D47", chave_operacao=str(uuid4()),
                resumo_operacao="a"*64, criada_em="2026-10-08T12:00:00Z"))
        b.commit()
    return http, acesso, sessoes, app


def consultar(http, **params):
    r = http.get(URL, params=params)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


@pytest.mark.parametrize("perfil", [None, "cliente", "fornecedor"])
def test_comparacao_exige_administrador_mesmo_com_perfil_forjado(propostas, perfil):
    http, _, sessoes, _ = propostas
    antes = retrato(sessoes)
    if perfil: entrar(http, perfil)
    else: http.cookies.clear()
    r = http.get(URL, headers={"X-Perfil":"admin"}, params={"perfil":"admin", "empresa_fornecedora_id":4})
    assert r.status_code == (401 if perfil is None else 403)
    assert "media" not in r.json() and "itens" not in r.json()
    assert retrato(sessoes) == antes


def test_medias_independentes_historico_completo_e_consulta_sem_gravar(propostas):
    http, _, sessoes, _ = propostas
    antes = retrato(sessoes)
    dados = consultar(http)
    assert dados["contexto"] == "1:admin:0"
    assert dados["versao"] == http.get(COM + "/solicitacoes/9").json()["versao"]
    assert dados["cotacoes_total"] == dados["cotacoes_disponiveis"] == dados["total"] == 3
    assert dados["menor_valor_disponivel"] == "900.13" and dados["menor_prazo_disponivel"] == 4
    itens = {q["cotacao_id"]: q for q in dados["itens"]}
    assert itens[8]["notas_cliente"] == {"quantidade":2,"media":"3.00"}
    assert itens[8]["notas_admin"] == {"quantidade":2,"media":"4.50"}
    assert itens[9]["notas_cliente"] == {"quantidade":1,"media":"4.00"}
    assert itens[9]["notas_admin"] == {"quantidade":1,"media":"3.00"}
    assert itens[10]["notas_cliente"] == itens[10]["notas_admin"] == {"quantidade":0,"media":None}
    assert all(x not in str(dados) for x in ("COMENTARIO-PRIVADO", "REGISTRO-INTERNO", "AUTOR-PRIVADO", "chave_operacao"))
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("ordem,ids", [("valor",[10,9,8]), ("prazo",[10,8,9]), ("nota_cliente",[9,8,10]), ("nota_admin",[8,9,10])])
def test_ordenacoes_nao_misturam_origens_e_sem_notas_ficam_apos_avaliados(propostas, ordem, ids):
    http, _, sessoes, _ = propostas
    antes = retrato(sessoes)
    assert [q["cotacao_id"] for q in consultar(http, ordenacao=ordem)["itens"]] == ids
    assert retrato(sessoes) == antes


def test_paginacao_preserva_resumos_e_nao_repete_propostas(propostas):
    http, _, _, _ = propostas
    paginas = [consultar(http, limite=1, deslocamento=i) for i in range(4)]
    assert [p["itens"][0]["cotacao_id"] for p in paginas[:3]] == [10,9,8]
    assert paginas[3]["itens"] == []
    for p in paginas:
        assert p["total"] == 3 and p["menor_valor_disponivel"] == "900.13" and p["menor_prazo_disponivel"] == 4


@pytest.mark.parametrize("params", [{"ordenacao":"ranking"}, {"escopo":"abertas"}, {"deslocamento":-1},
    {"deslocamento":1000001}, {"limite":0}, {"limite":101}])
def test_filtros_invalidos_recusados(propostas, params):
    http, _, sessoes, _ = propostas
    antes = retrato(sessoes)
    assert http.get(URL, params=params).status_code == 422
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("sid,codigo", [(0,422), (-1,422), (99999,404)])
def test_identificadores_invalidos_ou_ausentes(propostas, sid, codigo):
    http, _, _, _ = propostas
    assert http.get(COM + f"/solicitacoes/{sid}/comparacao").status_code == codigo


def test_contexto_de_outra_aba_recusado(propostas):
    http, _, sessoes, _ = propostas
    antes = retrato(sessoes)
    r = http.get(URL, headers={"X-MEC-COMERCIAL-CONTEXTO":"2:cliente:2"})
    assert r.status_code == 409 and r.json()["detail"] == "contexto_comercial_alterado"
    assert retrato(sessoes) == antes


def test_expiracao_e_historico_sao_lidos_sem_mudar_o_status_registrado(propostas):
    http, _, sessoes, _ = propostas
    with sessoes() as b:
        b.get(CotacaoFornecedor, 10).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
        b.get(CotacaoFornecedor, 9).status = "recusada"
        b.commit()
    antes = retrato(sessoes)
    assert [q["cotacao_id"] for q in consultar(http)["itens"]] == [8]
    todas = consultar(http, escopo="todas")
    assert todas["cotacoes_disponiveis"] == 1 and todas["menor_valor_disponivel"] == "1500.00"
    expirada = next(q for q in todas["itens"] if q["cotacao_id"] == 10)
    assert expirada["status"] == "expirada" and not expirada["pode_decidir"]
    with sessoes() as b: assert b.get(CotacaoFornecedor,10).status == "enviada"
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("bloqueio", ["aceita", "encerrada", "contratada"])
def test_solicitacao_sem_decisao_disponivel_mantem_historico(propostas, bloqueio):
    from backend.app.models.solicitacao import SolicitacaoServico
    http, _, sessoes, _ = propostas
    sid = 9
    if bloqueio == "contratada": sid = 1
    else:
        with sessoes() as b:
            if bloqueio == "aceita": b.get(CotacaoFornecedor,8).status = "aceita"
            else: b.get(SolicitacaoServico,9).status = "encerrada"
            b.commit()
    r = http.get(COM + f"/solicitacoes/{sid}/comparacao", params={"escopo":"todas"})
    assert r.status_code == 200
    dados = r.json()
    assert dados["cotacoes_disponiveis"] == 0 and dados["menor_valor_disponivel"] is None
    assert dados["itens"] and not any(q["pode_decidir"] for q in dados["itens"])


def test_comparar_nao_aceita_proposta_e_confirmacao_existente_mantem_auditoria(propostas):
    http, _, sessoes, _ = propostas
    antes = retrato(sessoes)
    comp = consultar(http)
    assert retrato(sessoes) == antes
    # O ADM pode escolher outra proposta, independentemente da primeira na ordenação.
    dados = corpo(http, versao=comp["versao"])
    r = decidir(http, dados, cotacao=8)
    assert r.status_code == 200 and r.json()["cotacoes_recusadas"] == [9,10]
    assert decidir(http, dados, cotacao=8).json() == r.json()
    assert consultar(http)["itens"] == []
    with sessoes() as b:
        assert len(list(b.scalars(select(EventoDecisaoCotacaoAdmin)))) == 1
    depois = retrato(sessoes)
    for tabela in ("avaliacoes_oficina", "avaliacoes_administrativas", "contratacoes_servico", "ordens_servico"):
        assert antes[tabela] == depois[tabela]


def test_valor_alterado_invalida_versao_da_comparacao_sem_decidir(propostas):
    http, _, sessoes, _ = propostas
    comp = consultar(http)
    with sessoes() as b: b.get(CotacaoFornecedor,8).valor_total = Decimal("1123.45"); b.commit()
    antes = retrato(sessoes)
    assert consultar(http)["versao"] != comp["versao"]
    assert decidir(http, corpo(http, versao=comp["versao"])).status_code == 409
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("extras", [0,28])
def test_numero_de_consultas_independe_de_quantidade_de_fornecedores(propostas, extras):
    http, _, sessoes, _ = propostas
    with sessoes() as b:
        for i in range(11,11+extras):
            b.add(Empresa(id=i, razao_social=f"Fornecedor {i}", documento=f"d47-{i}", tipo_empresa="fornecedor")); b.flush()
            b.add(CotacaoFornecedor(id=i, solicitacao_id=9, empresa_fornecedora_id=i, valor_total=Decimal("1250.00"), prazo_dias=8, validade_dias=10))
        b.commit()
    consultas = []
    def capturar(_, __, statement, *resto):
        if statement.lstrip().upper().startswith("SELECT"): consultas.append(statement)
    engine = sessoes.kw["bind"]
    event.listen(engine,"before_cursor_execute",capturar)
    try: dados = consultar(http, limite=1)
    finally: event.remove(engine,"before_cursor_execute",capturar)
    assert len(consultas) == 4 and dados["total"] == 3+extras
    assert dados["menor_valor_disponivel"] == "900.13"


def test_comparacao_usa_mesma_leitura_para_preco_e_medias_com_gravacao_concorrente(propostas):
    http, _, sessoes, _ = propostas
    caminho = Path(sessoes.kw["bind"].url.database)
    with sqlite3.connect(caminho) as b: b.execute("PRAGMA journal_mode=WAL")
    alterou = False
    def alterar(_, __, statement, *resto):
        nonlocal alterou
        if not alterou and statement.lstrip().upper().startswith("SELECT"):
            alterou = True
            with sqlite3.connect(caminho) as b:
                b.execute("UPDATE cotacoes_fornecedor SET valor_total=1100.33 WHERE id=8")
                b.execute("UPDATE avaliacoes_oficina SET nota=1 WHERE contratacao_id=1")
    engine = sessoes.kw["bind"]
    event.listen(engine,"after_cursor_execute",alterar)
    try: primeira = consultar(http)
    finally: event.remove(engine,"after_cursor_execute",alterar)
    antiga = next(q for q in primeira["itens"] if q["cotacao_id"] == 8)
    assert antiga["valor_total"] == "1500.00" and antiga["notas_cliente"]["media"] == "3.00"
    nova = next(q for q in consultar(http)["itens"] if q["cotacao_id"] == 8)
    assert nova["valor_total"] == "1100.33" and nova["notas_cliente"]["media"] == "1.00"
