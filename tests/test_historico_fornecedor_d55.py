"""D55: busca global e histórico paginado, administrativos e somente leitura."""
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
import sqlite3

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from test_financeiro_administrativo_d32 import contas_d32, ambiente_d32, entrar
from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, COOKIE_SESSAO
from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.avaliacao_perfil import AvaliacaoAdministrativa
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.avaliacoes_perfis import ServicoAvaliacoesPerfis

pytestmark = pytest.mark.acesso_real
BASE = "/api/v1/administracao/avaliacoes"


def adicionar(banco, cid, fornecedor=4, cliente=2, nota_cliente=3, nota_admin=2):
    if banco.get(ContratacaoServico, cid) is None:
        banco.add(SolicitacaoServico(id=cid, empresa_cliente_id=cliente, processo_id=1, material_id=1,
            dimensao_x_maxima_mm=10, dimensao_y_maxima_mm=10, dimensao_z_maxima_mm=10,
            tolerancia_requerida_mm="0.1", quantidade=1)); banco.flush()
        banco.add(CotacaoFornecedor(id=cid, solicitacao_id=cid, empresa_fornecedora_id=fornecedor,
            valor_total="100.00", prazo_dias=1, validade_dias=1, status="aceita")); banco.flush()
        banco.add(ContratacaoServico(id=cid, solicitacao_id=cid, cotacao_id=cid, empresa_cliente_id=cliente,
            empresa_fornecedora_id=fornecedor, valor_total="100.00", prazo_dias=1, status="encerrada")); banco.flush()
        banco.add(OrdemServico(id=cid, contratacao_id=cid, solicitacao_id=cid, cotacao_id=cid,
            empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, processo_id=1, material_id=1,
            quantidade=1, valor_total="100.00", prazo_dias=1, status="concluida")); banco.flush()
    if nota_cliente is not None:
        banco.add(AvaliacaoOficina(contratacao_id=cid, ordem_servico_id=cid, empresa_cliente_id=cliente,
            empresa_fornecedora_id=fornecedor, nota=nota_cliente, comentario="CLIENTE PRIVADO D55"))
    if nota_admin is not None:
        banco.add(AvaliacaoAdministrativa(contratacao_id=cid, ordem_servico_id=cid, empresa_cliente_id=cliente,
            empresa_fornecedora_id=fornecedor, nota=nota_admin, comentario="ADM PRIVADO D55", criada_em="2026-10-09T18:00:00Z",
            usuario_id=1, nome_autor="Autor administrativo", chave_operacao=str(uuid4()), resumo_operacao="a"*64))


@pytest.fixture
def fornecedores(ambiente_d32):
    http, sessoes, app = ambiente_d32
    with sessoes() as banco:
        banco.get(Empresa, 4).razao_social = "Usinagem Ágil"
        banco.get(Empresa, 8).razao_social = "Dobra Boa"
        for eid in range(100, 125):
            banco.add(Empresa(id=eid, razao_social=f"Oficina Precisão {eid}", documento=f"d55-{eid}",
                tipo_empresa="ambos" if eid == 100 else "fornecedor"))
        banco.flush()
        for cid, nc, na in ((1, 5, 1), (3, 3, 2), (4, 4, 2)):
            adicionar(banco, cid, nota_cliente=nc, nota_admin=na)
        adicionar(banco, 2, fornecedor=8, cliente=6, nota_cliente=4, nota_admin=4)
        banco.commit()
    entrar(http, "admin")
    return http, sessoes, app


def obter(http, caminho, **params):
    r = http.get(BASE+caminho, params=params)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def retrato(sessoes):
    with sqlite3.connect(sessoes.kw["bind"].url.database) as banco:
        nomes = [n for (n,) in banco.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {n: banco.execute('SELECT * FROM "'+n.replace('"', '""')+'" ORDER BY rowid').fetchall() for n in nomes}


@pytest.mark.parametrize("busca", ["ÁGIL", "agil", "  usinagem   agil ", "F-4", "f-4", "4"])
def test_busca_por_nome_sem_acento_ou_codigo(fornecedores, busca):
    http, _, _ = fornecedores
    dados = obter(http, "/ranking", busca=busca)
    assert dados["total"] == 1 and dados["total_fornecedores"] == 27
    assert dados["itens"][0]["empresa_id"] == 4 and dados["itens"][0]["media"] == "4.00"


def test_busca_apos_classificacao_preserva_posicao_global_e_origem(fornecedores):
    http, _, _ = fornecedores
    for origem in ("cliente", "admin"):
        todos = obter(http, "/ranking", origem=origem, limite=100)
        filtrado = obter(http, "/ranking", origem=origem, busca="F-8")
        esperado = next(v for v in todos["itens"] if v["empresa_id"] == 8)
        assert filtrado["itens"] == [esperado]
    assert obter(http, "/ranking", origem="cliente", busca="F-8")["itens"][0]["posicao"] == 2
    assert obter(http, "/ranking", origem="admin", busca="F-8")["itens"][0]["posicao"] == 1


def test_busca_considera_todas_as_paginas_e_empresa_mista(fornecedores):
    http, _, _ = fornecedores
    paginas = [obter(http, "/ranking", busca="precisao", inicio=i, limite=20) for i in (0, 20)]
    assert [p["total"] for p in paginas] == [25, 25]
    assert len({q["empresa_id"] for p in paginas for q in p["itens"]}) == 25
    assert obter(http, "/ranking", busca="F-124")["itens"][0]["empresa_id"] == 124
    assert obter(http, "/ranking", busca="F-100")["itens"][0]["posicao"] is None
    assert obter(http, "/ranking", busca="F-100")["itens"][0]["media"] is None


@pytest.mark.parametrize("busca", ["inexistente", "F-2", "F-44", "%' OR 1=1 --"])
def test_busca_literal_vazia_sem_ampliar_escopo(fornecedores, busca):
    http, _, _ = fornecedores
    assert obter(http, "/ranking", busca=busca)["itens"] == []


def test_historico_origens_comentarios_e_autores_apenas_admin(fornecedores):
    http, _, _ = fornecedores
    d = obter(http, "/fornecedores/4/historico")
    assert d["contexto"] == "1:admin:0" and d["total"] == 3
    assert d["fornecedor"]["notas_cliente"] == {"quantidade": 3, "media": "4.00"}
    assert d["fornecedor"]["notas_admin"] == {"quantidade": 3, "media": "1.67"}
    assert [i["contratacao_id"] for i in d["itens"]] == [4, 3, 1]
    assert all(i["fornecedor_codigo"] == "F-4" for i in d["itens"])
    assert all(i["cliente"]["comentario"] == "CLIENTE PRIVADO D55" for i in d["itens"])
    assert all(i["admin"]["autor"]["nome"] == "Autor administrativo" for i in d["itens"])
    assert all(i["cliente"]["historica"] for i in d["itens"])


def test_historico_nao_multiplica_origens_e_totais_nao_dependem_da_pagina(fornecedores):
    http, sessoes, _ = fornecedores
    with sessoes() as banco:
        for cid in range(101, 126): adicionar(banco, cid, nota_cliente=(cid % 5)+1, nota_admin=None if cid % 2 else 4)
        adicionar(banco, 130, nota_cliente=None, nota_admin=5)
        adicionar(banco, 140, nota_cliente=None, nota_admin=None)
        banco.commit()
    primeira = obter(http, "/fornecedores/4/historico", limite=20)
    segunda = obter(http, "/fornecedores/4/historico", inicio=20, limite=20)
    fora = obter(http, "/fornecedores/4/historico", inicio=40, limite=20)
    assert primeira["total"] == segunda["total"] == fora["total"] == 29
    assert primeira["fornecedor"] == segunda["fornecedor"] == fora["fornecedor"]
    ids = [i["contratacao_id"] for d in (primeira, segunda) for i in d["itens"]]
    assert len(ids) == len(set(ids)) == 29 and ids == sorted(ids, reverse=True)
    assert 130 in ids and 140 not in ids and fora["itens"] == []
    for origem in ("cliente", "admin"):
        ranking = obter(http, "/ranking", origem=origem, busca="F-4")["itens"][0]
        assert primeira["fornecedor"]["notas_"+origem] == {"quantidade": ranking["quantidade"], "media": ranking["media"]}


def test_fornecedor_sem_notas_tem_historico_vazio(fornecedores):
    http, _, _ = fornecedores
    d = obter(http, "/fornecedores/100/historico")
    assert d["total"] == 0 and d["itens"] == []
    assert d["fornecedor"]["notas_cliente"] == d["fornecedor"]["notas_admin"] == {"quantidade": 0, "media": None}


@pytest.mark.parametrize("perfil", [None, "cliente", "fornecedor"])
def test_historico_e_busca_exclusivos_admin_sem_perfil_forjado(fornecedores, perfil):
    http, sessoes, _ = fornecedores
    antes = retrato(sessoes)
    if perfil: entrar(http, perfil)
    else: http.cookies.clear()
    for caminho in ("/ranking?busca=F-4", "/fornecedores/4/historico", "/fornecedores/8/historico"):
        r = http.get(BASE+caminho, headers={"X-Perfil": "admin", "X-MEC-AVALIACOES-CONTEXTO": "1:admin:0"})
        assert r.status_code == (403 if perfil else 401)
        assert all(k not in r.json() for k in ("itens", "fornecedor", "media", "posicao"))
    assert retrato(sessoes) == antes


@pytest.mark.parametrize("perfil", ["cliente", "fornecedor"])
def test_servico_do_historico_recusa_portais(fornecedores, perfil):
    http, sessoes, app = fornecedores; entrar(http, perfil)
    usuario = ArmazenamentoAcesso(app.state.caminho_acessos).obter_sessao(http.cookies.get(COOKIE_SESSAO))
    with sessoes() as banco:
        with pytest.raises(HTTPException) as e: ServicoAvaliacoesPerfis(banco, usuario).historico_fornecedor(4, 0, 20)
        assert e.value.status_code == 403


@pytest.mark.parametrize("caminho,params,codigo", [
    ("/ranking", {"busca": "x"*161}, 422),
    ("/fornecedores/0/historico", {}, 422), ("/fornecedores/-1/historico", {}, 422),
    ("/fornecedores/9999/historico", {}, 404), ("/fornecedores/2/historico", {}, 404),
    ("/fornecedores/4/historico", {"inicio": -1}, 422), ("/fornecedores/4/historico", {"inicio": 1000001}, 422),
    ("/fornecedores/4/historico", {"limite": 0}, 422), ("/fornecedores/4/historico", {"limite": 101}, 422),
])
def test_filtros_e_empresa_invalidos_recusados(fornecedores, caminho, params, codigo):
    http, _, _ = fornecedores
    assert http.get(BASE+caminho, params=params).status_code == codigo


def test_contexto_antigo_e_leituras_sem_gravacoes(fornecedores):
    http, sessoes, _ = fornecedores
    antes = retrato(sessoes)
    assert http.get(BASE+"/fornecedores/4/historico", headers={"X-MEC-AVALIACOES-CONTEXTO": "outra-aba"}).status_code == 409
    for origem in ("cliente", "admin"): obter(http, "/ranking", origem=origem, busca="agil")
    obter(http, "/fornecedores/4/historico"); obter(http, "/fornecedores/100/historico")
    assert retrato(sessoes) == antes


def test_resumos_e_itens_na_mesma_leitura_com_gravacao_concorrente(fornecedores):
    http, sessoes, _ = fornecedores
    engine = sessoes.kw["bind"]
    with engine.connect() as c: c.exec_driver_sql("PRAGMA journal_mode=WAL")
    alterado = False
    def depois(conexao, cursor, sql, params, contexto, varios):
        nonlocal alterado
        if not alterado and "sum(avaliacoes_oficina.nota)" in sql.lower():
            alterado = True
            with sqlite3.connect(engine.url.database, timeout=5) as b:
                b.execute("UPDATE avaliacoes_oficina SET nota=1 WHERE empresa_fornecedora_id=4"); b.commit()
    event.listen(engine, "after_cursor_execute", depois)
    try:
        d = obter(http, "/fornecedores/4/historico")
        assert alterado and d["fornecedor"]["notas_cliente"]["media"] == "4.00"
        notas = [i["cliente"]["nota"] for i in d["itens"]]
        assert str((Decimal(sum(notas))/len(notas)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) == "4.00"
    finally: event.remove(engine, "after_cursor_execute", depois)
    assert obter(http, "/fornecedores/4/historico")["fornecedor"]["notas_cliente"]["media"] == "1.00"
