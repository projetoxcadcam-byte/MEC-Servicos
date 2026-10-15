"""D40: movimentos reais, datas UTC, estornos independentes e consulta administrativa sem gravação."""
from __future__ import annotations

import csv
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal
import io
import sqlite3
import pytest
from sqlalchemy import event
from backend.app.models.financeiro_administrativo import RepasseAdministrativo
from backend.app.models.pagamento import PagamentoContratacao
from test_painel_administrativo_d33 import (
    ambiente_d33, contas_d33, entrar, evento_financeiro, fotografia, Empresa, FINANCEIRO,
)
from test_relatorio_empresas_d36 import criar

pytestmark = pytest.mark.acesso_real
EXTRATO = "/api/v1/administracao/financeiro/extrato"
PERIODO = {"data_inicial": "2026-10-01", "data_final": "2026-10-31"}


def receber(banco, cid=1, valor="12500.00", data="2026-10-05T20:00:00", estorno=None):
    p = PagamentoContratacao(contratacao_id=cid, empresa_cliente_id=2, empresa_fornecedora_id=4,
        valor=Decimal(valor), forma_pagamento="pix", status="cancelado" if estorno else "confirmado",
        paga_em=datetime.fromisoformat(data), cancelada_em=datetime.fromisoformat(estorno) if estorno else None)
    banco.add(p); banco.flush(); return p


def repassar(banco, cid=1, valor=1250000, data="2026-10-05T21:00:00Z", estorno=None):
    p = RepasseAdministrativo(contratacao_id=cid, valor_centavos=valor, forma_pagamento="transferencia",
        status="estornado" if estorno else "confirmado", registrado_em=data, estornado_em=estorno)
    banco.add(p); banco.flush(); return p


def consultar(http, **params):
    r = http.get(EXTRATO, params={**PERIODO, **params})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def exportado(http, **params):
    r = http.get(EXTRATO + "/csv", params={**PERIODO, **params})
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf") and "text/csv" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-store" and "MEC_SERVICOS_EXTRATO_FINANCEIRO.csv" in r.headers["content-disposition"]
    texto = r.content.decode("utf-8-sig")
    assert all(len(l) == 30 for l in csv.reader(io.StringIO(texto), delimiter=";"))
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def test_sessao_admin_real_obrigatoria_json_csv_e_nao_vaza(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco, 1); receber(banco); banco.commit()
    for rota in (EXTRATO, EXTRATO + "/csv"):
        assert http.get(rota).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for rota in (EXTRATO, EXTRATO + "/csv"):
            r = http.get(rota, params={"perfil": "admin", "empresa_id": 2})
            assert r.status_code == 403 and "12500" not in r.text and "Cliente Mecânico" not in r.text
    entrar(http); assert http.post(EXTRATO).status_code == 405


def test_vazio_zeros_csv_completo_sem_gravar(ambiente_d33):
    http, _, engine = ambiente_d33; entrar(http); antes = fotografia(engine)
    d = consultar(http)
    assert d["total"] == 0 and d["itens"] == []
    assert all(Decimal(v) == 0 for v in d["resumo"].values())
    linhas = exportado(http)
    assert len([l for l in linhas if l["Tipo de registro"] == "Total"]) == 1
    assert not any(l["Tipo de registro"] == "Movimento" for l in linhas)
    assert fotografia(engine) == antes


def test_os3_erro1250_estorno_e_correcao12500_preservados(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-09-02T12:00:00", os_id=3, status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        receber(banco, valor="1250.00", estorno="2026-10-05T20:01:00")
        receber(banco, data="2026-10-05T20:02:00"); repassar(banco); banco.commit()
    entrar(http); antes = fotografia(engine); d = consultar(http, busca="OS #03")
    assert d["total"] == 4 and d["resumo"]["total_contratacoes"] == 1
    assert d["resumo"]["recebimentos_brutos"] == "13750.00"
    assert d["resumo"]["estornos_recebimentos"] == "1250.00"
    assert d["resumo"]["recebimentos_liquidos"] == d["resumo"]["repasses_liquidos"] == "12500.00"
    assert d["resumo"]["resultado_periodo"] == "0.00"
    assert {c["ordem_servico_id"] for c in d["itens"]} == {3}
    assert all(c["financeiro_status"] == "encerrado" for c in d["itens"])
    a = next(c for c in d["itens"] if c["tipo"] == "recebimento" and c["movimento_id"] == 1)
    b = next(c for c in d["itens"] if c["tipo"] == "estorno_recebimento")
    assert a["situacao_atual"] == "estornado" and a["efeito_liquido"] == "1250.00"
    assert b["efeito_liquido"] == "-1250.00" and b["data_original_utc"] == a["data_utc"]
    assert b["data_utc"] == a["estornado_em_utc"]
    linhas = exportado(http, busca="OS #3"); assert len([l for l in linhas if l["Tipo de registro"] == "Movimento"]) == 4
    assert next(l for l in linhas if l["Movimento"] == "Estorno de recebimento")["Efeito líquido"] == "-1250,00"
    assert fotografia(engine) == antes


def test_estorno_em_mes_seguinte_nao_apaga_original_e_nao_usa_data_contrato(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2025-01-02T12:00:00")
        receber(banco, valor="10.01", data="2026-09-30T23:59:59", estorno="2026-10-01T00:00:00"); banco.commit()
    entrar(http)
    setembro = consultar(http, data_inicial="2026-09-01", data_final="2026-09-30")
    outubro = consultar(http)
    assert setembro["resumo"]["recebimentos_liquidos"] == "10.01" and setembro["itens"][0]["tipo"] == "recebimento"
    assert outubro["resumo"]["recebimentos_brutos"] == "0.00" and outubro["resumo"]["estornos_recebimentos"] == "10.01"
    assert outubro["resumo"]["recebimentos_liquidos"] == outubro["resumo"]["resultado_periodo"] == "-10.01"
    tudo = consultar(http, data_inicial="", data_final="")
    assert tudo["total"] == 2 and tudo["resumo"]["recebimentos_liquidos"] == "0.00"
    total = next(l for l in exportado(http) if l["Tipo de registro"] == "Total")
    assert total["Recebimentos líquidos"] == total["Resultado do período"] == "-10,01"


def test_estorno_repasse_tem_efeito_positivo_na_propria_data(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, controle="aberto")
        repassar(banco, valor=1599, data="2026-09-30T23:59:59Z", estorno="2026-10-01T00:00:00Z"); banco.commit()
    entrar(http); d = consultar(http)
    assert d["itens"][0]["tipo"] == "estorno_repasse" and d["itens"][0]["efeito_liquido"] == "15.99"
    assert d["resumo"]["repasses_liquidos"] == "-15.99" and d["resumo"]["resultado_periodo"] == "15.99"
    setembro = consultar(http, data_inicial="2026-09-01", data_final="2026-09-30")
    assert setembro["itens"][0]["efeito_liquido"] == "-15.99"


@pytest.mark.parametrize("tipo,total,recebido,repassado,resultado", [
    ("todos", 6, "0.03", "0.07", "-0.04"), ("recebimentos", 3, "0.03", "0.00", "0.03"),
    ("repasses", 3, "0.00", "0.07", "-0.07"), ("estornos", 2, "-0.01", "-0.05", "0.04"),
])
def test_tipos_totais_exatos_sem_multiplicar_recebimentos_repasses(ambiente_d33, tipo, total, recebido, repassado, resultado):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, controle="aberto")
        receber(banco, valor="0.01", estorno="2026-10-06T01:00:00"); receber(banco, valor="0.03")
        repassar(banco, valor=5, estorno="2026-10-06T01:00:00Z"); repassar(banco, valor=7); banco.commit()
    entrar(http); d = consultar(http, tipo=tipo, limite=1)
    assert d["total"] == total and len(d["itens"]) == 1
    assert d["resumo"]["recebimentos_liquidos"] == recebido and d["resumo"]["repasses_liquidos"] == repassado
    assert d["resumo"]["resultado_periodo"] == resultado
    assert len([l for l in exportado(http, tipo=tipo) if l["Tipo de registro"] == "Movimento"]) == total


def test_legado_sem_controle_sem_os_e_controle_encerrado_consultaveis(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, com_os=False); receber(banco, 1, "11.01")
        criar(banco, 2, status="cancelada", controle="aberto"); receber(banco, 2, "22.02")
        criar(banco, 3, status="encerrada", controle="encerrado"); receber(banco, 3, "33.03"); banco.commit()
    entrar(http); d = consultar(http)
    assert d["total"] == 3 and d["resumo"]["recebimentos_liquidos"] == "66.06"
    assert next(c for c in d["itens"] if c["contratacao_id"] == 1)["ordem_servico_id"] is None
    assert {c["financeiro_status"] for c in d["itens"]} == {"sem_controle", "aberto", "encerrado"}


@pytest.mark.parametrize("busca,cids", [("OS #003", {1}), ("Contratação #01", {1}), ("#3", {1}),
    ("OFICINA MECANICA", {1, 2}), ("cliente mecanico", {1, 2}), ("OS #33", set()), ("Contratação #11", set())])
def test_busca_ids_exatos_e_nomes_sem_acentos(ambiente_d33, busca, cids):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, os_id=3); criar(banco, 2); receber(banco, 1); receber(banco, 2); banco.commit()
    entrar(http); assert {c["contratacao_id"] for c in consultar(http, busca=busca)["itens"]} == cids


def test_selecao_cid_paginacao_estavel_csv_todas_paginas(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1); criar(banco, 2)
        for i in range(25): receber(banco, 1, "0.01")
        receber(banco, 2, "100.00"); banco.commit()
    entrar(http); a = consultar(http, contratacao_id=1); b = consultar(http, contratacao_id=1, deslocamento=20)
    assert a["total"] == b["total"] == 25 and a["resumo"] == b["resumo"]
    assert a["resumo"]["recebimentos_liquidos"] == "0.25"
    ids = [c["movimento_id"] for c in a["itens"] + b["itens"]]
    assert ids == list(range(25, 0, -1))
    linhas = [l for l in exportado(http, contratacao_id=1, deslocamento=20, limite=1) if l["Tipo de registro"] == "Movimento"]
    assert len(linhas) == 25 and {l["Contratação"] for l in linhas} == {"1"}
    assert consultar(http, contratacao_id=999)["total"] == 0
    assert consultar(http, contratacao_id=1, busca="Contratação #2")["total"] == 0


def test_datas_utc_inclusivas_com_offset_e_microssegundos(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, controle="aberto")
        for _ in range(5): receber(banco, valor="0.01")
        repassar(banco, valor=1, data="2024-03-01T00:30:00+01:00"); banco.commit()
    datas = ["2024-02-29T00:00:00", "2024-02-29T23:59:59.999999", "2024-03-01T00:30:00+01:00",
             "2024-02-28T23:59:59.999999", "2024-03-01T00:00:00"]
    with engine.begin() as banco:
        for pid, data in enumerate(datas, 1): banco.exec_driver_sql("UPDATE pagamentos_contratacao SET paga_em=? WHERE id=?", (data, pid))
    entrar(http); d = consultar(http, data_inicial="2024-02-29", data_final="2024-02-29")
    assert d["total"] == 4 and d["resumo"]["recebimentos_brutos"] == "0.03" and d["resumo"]["repasses_brutos"] == "0.01"
    assert all(c["data_utc"].startswith("2024-02-29T") and c["data_utc"].endswith("Z") for c in d["itens"])


@pytest.mark.parametrize("agora,esperadas", [((2024, 2, 15), ("2024-02-01", "2024-02-29")), ((2026, 10, 6), ("2026-10-01", "2026-10-31"))])
def test_padrao_mes_atual_calendario_utc(ambiente_d33, monkeypatch, agora, esperadas):
    from backend.app.services import extrato_financeiro as servico
    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC; return datetime(*agora, tzinfo=UTC)
    monkeypatch.setattr(servico, "datetime", Relogio)
    http, _, _ = ambiente_d33; entrar(http)
    r = http.get(EXTRATO); assert r.status_code == 200
    assert tuple(r.json()["filtros"][c] for c in ("data_inicial", "data_final")) == esperadas
    assert http.get(EXTRATO + "/csv").status_code == 200


def test_limites_abertos_e_anos_extremos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1)
        receber(banco, valor="1.00", data="0001-01-01T00:00:00")
        receber(banco, valor="2.00", data="9999-12-31T23:59:59.999999"); banco.commit()
    entrar(http)
    assert consultar(http, data_inicial="", data_final="")["resumo"]["recebimentos_liquidos"] == "3.00"
    assert consultar(http, data_inicial="", data_final="0001-01-01")["total"] == 1
    assert consultar(http, data_inicial="9999-12-31", data_final="")["total"] == 1
    assert len([l for l in exportado(http, data_inicial="", data_final="") if l["Tipo de registro"] == "Movimento"]) == 2


@pytest.mark.parametrize("param", [{"data_inicial": "2026-02-30"}, {"data_final": "2026-13-01"},
    {"data_inicial": "2026-11-01"}, {"data_inicial": "06/10/2026"}, {"data_inicial": "0000-01-01"},
    {"data_final": "10000-01-01"}, {"tipo": "cancelados"}, {"contratacao_id": 0}, {"busca": "x" * 121},
    {"deslocamento": -1}, {"limite": 101}, {"limite": 0}])
def test_filtros_invalidos_nao_gravam(ambiente_d33, param):
    http, _, engine = ambiente_d33; entrar(http); antes = fotografia(engine)
    assert http.get(EXTRATO, params={**PERIODO, **param}).status_code == 422
    if not ({"limite", "deslocamento"} & param.keys()):
        assert http.get(EXTRATO + "/csv", params={**PERIODO, **param}).status_code == 422
    assert fotografia(engine) == antes


@pytest.mark.parametrize("chave", ["data_inicial", "data_final", "tipo", "busca", "contratacao_id", "deslocamento", "limite"])
def test_parametros_duplicados_recusados_json_e_csv(ambiente_d33, chave):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (EXTRATO, EXTRATO + "/csv"):
        r = http.get(rota, params=[(chave, "1"), (chave, "2")]); assert r.status_code == 422


def test_movimento_inconsistente_exige_conferencia_sem_inventar_ou_alterar(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: criar(banco, 1); receber(banco); banco.commit()
    entrar(http)
    def fotografia_bruta():
        with closing(sqlite3.connect(engine.url.database)) as banco:
            return list(banco.iterdump())
    for status, data, cancelada in [("cancelado", "2026-10-05T12:00:00", None),
            ("cancelado", "2026-10-05T12:00:00", "2026-10-04T12:00:00"),
            ("confirmado", "2026-10-05T12:00:00", "2026-10-06T12:00:00"),
            ("confirmado", "data-quebrada", None)]:
        with engine.begin() as banco:
            banco.exec_driver_sql("UPDATE pagamentos_contratacao SET status=?, paga_em=?, cancelada_em=?", (status, data, cancelada))
        antes = fotografia_bruta()
        for rota in (EXTRATO, EXTRATO + "/csv"):
            r = http.get(rota, params=PERIODO); assert r.status_code == 409 and r.json()["detail"] == "movimento_extrato_inconsistente"
        assert fotografia_bruta() == antes


def test_csv_textos_livres_protegidos_e_negativos_numericos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, controle="aberto"); repassar(banco, valor=101)
        banco.get(Empresa, 2).razao_social = '  =SUM(1;2) "Cliente"\nÁgua'
        banco.get(Empresa, 4).razao_social = "@Oficina"; banco.commit()
    entrar(http); linhas = exportado(http, busca="@Oficina")
    linha = next(l for l in linhas if l["Tipo de registro"] == "Movimento")
    assert linha["Cliente"].startswith("'  =") and linha["Fornecedor"] == "'@Oficina"
    assert linha["Efeito líquido"] == "-1,01" and linha["Valor"] == "1,01"
    assert next(l for l in linhas if l["Campo"] == "Busca")["Informação"] == "'@Oficina"
    assert next(l for l in linhas if l["Tipo de registro"] == "Total")["Resultado do período"] == "-1,01"


def test_um_select_fornece_fotografia_coerente_com_gravacao_concorrente(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, controle="aberto"); receber(banco, valor="10.00"); repassar(banco, valor=500); banco.commit()
    with engine.connect() as banco: banco.exec_driver_sql("PRAGMA journal_mode=WAL")
    entrar(http); consultas = []
    def observar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            consultas.append(statement)
            with engine.begin() as outro:
                outro.exec_driver_sql("UPDATE pagamentos_contratacao SET status='cancelado', cancelada_em='2026-10-06T12:00:00' WHERE id=1")
    event.listen(engine, "after_cursor_execute", observar)
    try: d = consultar(http, limite=1)
    finally: event.remove(engine, "after_cursor_execute", observar)
    assert len(consultas) == 1 and d["total"] == 2 and d["resumo"]["recebimentos_liquidos"] == "10.00"
    assert d["resumo"]["resultado_periodo"] == "5.00"
    seguinte = consultar(http)
    assert seguinte["total"] == 3 and seguinte["resumo"]["recebimentos_liquidos"] == "0.00"


def test_operacoes_d32_reais_reconciliam_extrato_e_d39(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-10-02T12:00:00", os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    r = http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Teste D40"}); assert r.status_code == 201
    d = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=d["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4); evento_financeiro(http, "encerrar", 5)
    antes = fotografia(engine); d = consultar(http, data_inicial="", data_final="", busca="OS #3")
    assert d["total"] == 4 and d["resumo"]["recebimentos_liquidos"] == d["resumo"]["repasses_liquidos"] == "12500.00"
    resumo = http.get(FINANCEIRO).json()["resumo"]
    assert d["resumo"]["recebimentos_liquidos"] == resumo["total_recebido"] and d["resumo"]["repasses_liquidos"] == resumo["total_repassado"]
    comparativo = http.get("/api/v1/administracao/relatorios/comparativo", params={"a_inicial": "2026-09-01", "a_final": "2026-09-30", "b_inicial": "2026-10-01", "b_final": "2026-10-31", "busca": "OS #3"}).json()
    assert comparativo["resumo_b"]["indicadores"]["recebimentos_confirmados"] == d["resumo"]["recebimentos_liquidos"]
    assert fotografia(engine) == antes
