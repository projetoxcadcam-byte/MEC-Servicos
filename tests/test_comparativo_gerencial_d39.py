"""D39: coortes UTC, diferenças exatas, acesso real, CSV completo e leitura sem gravação."""
from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal
import io
import pytest
from sqlalchemy import event
from test_painel_administrativo_d33 import (
    ambiente_d33, contas_d33, entrar, evento_financeiro, fotografia, recebimento, repasse, Empresa, FINANCEIRO,
)
from test_relatorio_empresas_d36 import criar

pytestmark = pytest.mark.acesso_real
COMPARATIVO = "/api/v1/administracao/relatorios/comparativo"
PERIODOS = {"a_inicial": "2026-09-01", "a_final": "2026-09-30", "b_inicial": "2026-10-01", "b_final": "2026-10-31"}


def consultar(http, **params):
    r = http.get(COMPARATIVO, params={**PERIODOS, **params})
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def exportado(http, **params):
    r = http.get(COMPARATIVO + "/csv", params={**PERIODOS, **params})
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf") and "text/csv" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-store"
    assert "MEC_SERVICOS_COMPARATIVO_GERENCIAL.csv" in r.headers["content-disposition"]
    texto = r.content.decode("utf-8-sig")
    assert all(len(l) == 38 for l in csv.reader(io.StringIO(texto), delimiter=";"))
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def medida(d, codigo):
    return next(m for m in d["medidas"] if m["codigo"] == codigo)


def test_json_csv_exigem_admin_real_e_nao_vazam_valores(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco, 1); banco.commit()
    for rota in (COMPARATIVO, COMPARATIVO + "/csv"):
        assert http.get(rota, params=PERIODOS).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for rota in (COMPARATIVO, COMPARATIVO + "/csv"):
            r = http.get(rota, params={**PERIODOS, "perfil": "admin", "empresa_id": 2})
            assert r.status_code == 403 and "Cliente Mecânico" not in r.text and "resumo_a" not in r.text
    entrar(http); assert http.post(COMPARATIVO, json=PERIODOS).status_code == 405


def test_vazio_ambos_os_periodos_sem_numeros_ficticios(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    for periodo in (None, "a", "b"):
        d = consultar(http, **({"periodo": periodo} if periodo else {}))
        assert d["total"] == 0 and d["itens"] == [] and d["contratacoes_em_ambos"] == 0
        assert d["periodos_sobrepostos"] is False and len(d["medidas"]) == 17
        assert all(Decimal(m[c]) == 0 for m in d["medidas"] for c in ("valor_a", "valor_b", "diferenca", "variacao_percentual"))
    linhas = exportado(http)
    assert len([l for l in linhas if l["Tipo de registro"] == "Total"]) == 2
    assert len([l for l in linhas if l["Tipo de registro"] == "Indicador"]) == 17
    assert not any(l["Tipo de registro"] == "Contratação" for l in linhas)


@pytest.mark.parametrize("agora,esperadas", [
    ((2026, 1, 15), ("2025-12-01", "2025-12-31", "2026-01-01", "2026-01-31")),
    ((2024, 3, 3), ("2024-02-01", "2024-02-29", "2024-03-01", "2024-03-31")),
    ((2026, 10, 6), ("2026-09-01", "2026-09-30", "2026-10-01", "2026-10-31")),
])
def test_periodos_padrao_mes_anterior_e_atual_utc(ambiente_d33, monkeypatch, agora, esperadas):
    from backend.app.services import comparativo_gerencial as servico
    class Relogio(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return datetime(*agora, tzinfo=UTC)
    monkeypatch.setattr(servico, "datetime", Relogio)
    http, _, _ = ambiente_d33; entrar(http)
    r = http.get(COMPARATIVO); assert r.status_code == 200
    assert tuple(r.json()["filtros"][c] for c in PERIODOS) == esperadas
    assert http.get(COMPARATIVO + "/csv").status_code == 200


def test_os3_outubro_base_vazia_e_inversao_das_diferencas(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-10-02T16:44:48", os_id=3, status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        recebimento(banco, 1, "1250.00", "cancelado"); recebimento(banco, 1, "12500.00"); repasse(banco, 1, 1250000)
        banco.commit()
    antes = fotografia(engine); entrar(http)
    d = consultar(http, busca="OS #03", filtro="concluidas", periodo="b")
    assert d["total"] == 1 and d["itens"][0]["ordem_servico_id"] == 3
    assert d["resumo_a"]["indicadores"]["total_contratacoes"] == 0
    assert d["resumo_b"]["indicadores"]["financeiros_encerrados"] == 1
    for codigo in ("valor_contratado", "recebido_confirmado", "repassado_confirmado"):
        m = medida(d, codigo)
        assert m["valor_a"] == "0.00" and m["valor_b"] == m["diferenca"] == "12500.00"
        assert m["variacao_percentual"] is None
    for codigo in ("saldo_clientes", "saldo_fornecedores", "disponivel_repasses", "contratacoes_com_pendencias"):
        assert Decimal(medida(d, codigo)["valor_b"]) == 0
    inverso = consultar(http, a_inicial=PERIODOS["b_inicial"], a_final=PERIODOS["b_final"],
        b_inicial=PERIODOS["a_inicial"], b_final=PERIODOS["a_final"], busca="OS #3")
    assert medida(inverso, "valor_contratado")["diferenca"] == "-12500.00"
    assert medida(inverso, "valor_contratado")["variacao_percentual"] == "-100.00"
    csv_inverso = exportado(http, a_inicial=PERIODOS["b_inicial"], a_final=PERIODOS["b_final"],
        b_inicial=PERIODOS["a_inicial"], b_final=PERIODOS["a_final"], busca="OS #3")
    assert next(l for l in csv_inverso if l["Indicador"] == "Valor contratado")["Diferença B - A"] == "-12500,00"
    assert fotografia(engine) == antes


def test_percentuais_arredondados_e_centavos_sem_multiplicacao(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid, dia, valor in [(1, "2026-09-02", "0.32"), (2, "2026-10-02", "0.33")]:
            criar(banco, cid, dia + "T12:00:00", valor=valor, controle="aberto", ordem_status="concluida", ciclo="entregue_cliente")
        for v in ["0.01", "0.03", "0.05"]: recebimento(banco, 1, v)
        for v in ["0.02", "0.04", "0.06"]: recebimento(banco, 2, v)
        recebimento(banco, 2, "99.99", "cancelado")
        repasse(banco, 1, 1); repasse(banco, 1, 2); repasse(banco, 2, 4); repasse(banco, 2, 9999, "estornado")
        banco.commit()
    entrar(http); d = consultar(http)
    assert medida(d, "valor_contratado")["diferenca"] == "0.01"
    assert medida(d, "valor_contratado")["variacao_percentual"] == "3.13"
    assert medida(d, "recebido_confirmado")["valor_a"] == "0.09"
    assert medida(d, "recebido_confirmado")["valor_b"] == "0.12"
    assert medida(d, "recebido_confirmado")["variacao_percentual"] == "33.33"
    assert medida(d, "repassado_confirmado")["valor_a"] == "0.03"
    assert medida(d, "repassado_confirmado")["valor_b"] == "0.04"
    assert medida(d, "saldo_clientes")["diferenca"] == "-0.02"
    assert medida(d, "disponivel_repasses")["diferenca"] == "0.02"


def test_situacoes_e_pendencias_reconciliam_d38_d37_por_periodo(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-09-02T12:00:00", com_os=False)
        criar(banco, 2, "2026-09-03T12:00:00", controle="aberto", ciclo="material_recebido")
        criar(banco, 3, "2026-10-02T12:00:00", status="cancelada", com_os=False)
        criar(banco, 4, "2026-10-03T12:00:00", status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        recebimento(banco, 4, "12500.00"); repasse(banco, 4, 1250000)
        criar(banco, 5, "2026-10-04T12:00:00", status="encerrada", controle="encerrado")
        recebimento(banco, 5, "12500.00"); repasse(banco, 5, 1250000); banco.commit()
    entrar(http); d = consultar(http)
    for p, mes in (("a", 9), ("b", 10)):
        anterior = http.get("/api/v1/administracao/relatorios/gerencial", params={"ano": 2026, "mes": mes}).json()["resumo_mes"]
        r = d["resumo_" + p]
        for campo in ("indicadores", "valor_contratado", "em_andamento", "contratacoes_com_pendencias", "pendencias_operacionais", "pendencias_financeiras", "pendencias_conferencia"):
            assert r[campo] == anterior[campo]
        fila = http.get("/api/v1/administracao/pendencias", params={"data_inicial": PERIODOS[p + "_inicial"], "data_final": PERIODOS[p + "_final"]}).json()
        assert fila["total_contratacoes"] == r["contratacoes_com_pendencias"]
        assert fila["total_pendencias"] == sum(r[c] for c in ("pendencias_operacionais", "pendencias_financeiras", "pendencias_conferencia"))
    assert d["resumo_b"]["indicadores"]["financeiros_encerrados"] == 1
    assert d["resumo_b"]["indicadores"]["para_conferencia"] == 1


def test_datas_utc_limites_inclusivos_e_lacuna_excluida(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 7): criar(banco, cid)
        banco.commit()
    datas = ["2024-02-29T00:00:00", "2024-02-29T23:59:59.999999", "2024-03-01T00:30:00+01:00",
             "2024-03-02T23:30:00-01:00", "2024-03-02T23:59:59.999999", "2024-03-01T12:00:00"]
    with engine.begin() as banco:
        for cid, data in enumerate(datas, 1):
            banco.exec_driver_sql("UPDATE contratacoes_servico SET criada_em=? WHERE id=?", (data, cid))
    entrar(http)
    p = {"a_inicial": "2024-02-29", "a_final": "2024-02-29", "b_inicial": "2024-03-02", "b_final": "2024-03-02"}
    a = consultar(http, **p, periodo="a"); b = consultar(http, **p, periodo="b")
    assert {c["contratacao_id"] for c in a["itens"]} == {1, 2, 3}
    assert {c["contratacao_id"] for c in b["itens"]} == {5}
    assert medida(a, "total_contratacoes")["diferenca"] == "-2"
    assert not a["periodos_sobrepostos"]


def test_sobreposicao_identica_e_parcial_conta_uma_vez_em_cada_grupo(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid, dia in [(1, "2026-09-01"), (2, "2026-09-30"), (3, "2026-10-02")]:
            criar(banco, cid, dia + "T12:00:00", valor="10.01")
        banco.commit()
    entrar(http)
    d = consultar(http, b_inicial="2026-09-30")
    assert d["periodos_sobrepostos"] is True and d["contratacoes_em_ambos"] == 1
    assert medida(d, "total_contratacoes")["valor_a"] == medida(d, "total_contratacoes")["valor_b"] == "2"
    linhas = exportado(http, b_inicial="2026-09-30")
    for p, ids in [("A", {1, 2}), ("B", {2, 3})]:
        grupo = [l for l in linhas if l["Tipo de registro"] == "Contratação" and l["Período"] == p]
        assert {int(l["Contratação"]) for l in grupo} == ids and len(grupo) == 2
        assert sum(Decimal(l["Valor contratado"].replace(",", ".")) for l in grupo) == Decimal("20.02")
    igual = consultar(http, b_inicial=PERIODOS["a_inicial"], b_final=PERIODOS["a_final"])
    assert igual["contratacoes_em_ambos"] == 2
    assert all(Decimal(m["diferenca"]) == Decimal(m["variacao_percentual"]) == 0 for m in igual["medidas"])


def test_paginas_nao_limitam_totais_diferencas_ou_csv_ambos_periodos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 27): criar(banco, cid, "2026-09-30T12:00:00", valor="10.01")
        for cid in range(27, 30): criar(banco, cid, "2026-10-02T12:00:00", valor="10.01")
        banco.commit()
    entrar(http)
    a = consultar(http, periodo="a"); pagina = consultar(http, periodo="a", deslocamento=20)
    assert a["total"] == pagina["total"] == 26 and len(a["itens"]) == 20 and len(pagina["itens"]) == 6
    assert a["medidas"] == pagina["medidas"] and a["resumo_b"] == pagina["resumo_b"]
    assert [c["contratacao_id"] for c in a["itens"]] == list(range(26, 6, -1))
    linhas = exportado(http, periodo="a", deslocamento=20, limite=1)
    for p, qtd, total in (("A", 26, "260,26"), ("B", 3, "30,03")):
        contratos = [l for l in linhas if l["Tipo de registro"] == "Contratação" and l["Período"] == p]
        assert len(contratos) == len({l["Contratação"] for l in contratos}) == qtd
        assert next(l for l in linhas if l["Tipo de registro"] == "Total" and l["Período"] == p)["Valor contratado"] == total
    assert consultar(http, periodo="a", deslocamento=999)["itens"] == []
    assert consultar(http)["itens"] == [] and consultar(http)["total"] == 0


def test_busca_e_situacao_aplicadas_igualmente_ao_par_de_periodos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-09-02T12:00:00", status="encerrada", ordem_status="concluida", ciclo="entregue_cliente")
        criar(banco, 2, "2026-10-02T12:00:00", status="encerrada", ordem_status="concluida", ciclo="entregue_cliente")
        criar(banco, 3, "2026-10-02T12:00:00", com_os=False, status="cancelada")
        banco.commit()
    entrar(http)
    d = consultar(http, filtro="concluidas", busca="  oficina mecanica alfa  ")
    assert d["filtros"]["busca"] == "oficina mecanica alfa"
    assert medida(d, "total_contratacoes")["valor_a"] == medida(d, "total_contratacoes")["valor_b"] == "1"
    os = consultar(http, busca="OS #102", periodo="b")
    assert os["total"] == 1 and os["itens"][0]["contratacao_id"] == 2
    assert os["resumo_a"]["indicadores"]["total_contratacoes"] == 0
    assert consultar(http, filtro="canceladas", periodo="b")["itens"][0]["contratacao_id"] == 3


@pytest.mark.parametrize("params", [
    {"a_inicial": ""}, {"a_final": "2026-08-31"}, {"b_inicial": "2026-11-01"},
    {"a_inicial": "2026-02-30"}, {"b_final": "2026-04-31"}, {"a_inicial": "02/09/2026"},
    {"a_inicial": "0000-01-01"}, {"b_final": "10000-01-01"}, {"a_inicial": "2026-9-1"},
    {"filtro": "ativas"}, {"busca": "x" * 121}, {"periodo": "c"}, {"deslocamento": -1}, {"limite": 0}, {"limite": 101},
])
def test_filtros_invalidos_recusados(ambiente_d33, params):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(COMPARATIVO, params={**PERIODOS, **params}).status_code == 422
    if not any(c in params for c in ("deslocamento", "limite")):
        assert http.get(COMPARATIVO + "/csv", params={**PERIODOS, **params}).status_code == 422


@pytest.mark.parametrize("campo", [*PERIODOS, "filtro", "busca", "periodo", "deslocamento", "limite"])
def test_queries_repetidas_recusadas_em_json_e_csv(ambiente_d33, campo):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (COMPARATIVO, COMPARATIVO + "/csv"):
        assert http.get(rota + "?" + campo + "=1&" + campo + "=2").status_code == 422


def test_periodos_parciais_recusados_e_anos_extremos_aceitos(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (COMPARATIVO, COMPARATIVO + "/csv"):
        assert http.get(rota, params={"a_inicial": "2026-09-01"}).status_code == 422
    d = consultar(http, a_inicial="0001-01-01", a_final="0001-01-01", b_inicial="9999-12-31", b_final="9999-12-31")
    assert d["resumo_a"]["data_inicial"] == "0001-01-01" and d["total"] == 0


def test_csv_escapa_textos_livres_e_preserva_diferencas_negativas_numericas(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        banco.get(Empresa, 2).razao_social = '=HYPERLINK("x"); Cliente\nMecânico'
        banco.get(Empresa, 4).razao_social = ' \t@SUM(1); Oficina "Alfa"'
        criar(banco, 1, "2026-09-02T12:00:00", com_os=False, valor="10.01"); banco.commit()
    antes = fotografia(engine); entrar(http)
    linhas = exportado(http)
    contrato = next(l for l in linhas if l["Tipo de registro"] == "Contratação")
    assert contrato["Cliente"].startswith("'=") and contrato["Fornecedor"].startswith("' \t@")
    assert contrato["OS"] == contrato["Saldo a receber com controle aberto"] == ""
    dinheiro = next(l for l in linhas if l["Indicador"] == "Valor contratado")
    assert dinheiro["Diferença B - A"] == "-10,01" and dinheiro["Variação (%)"] == "-100,00"
    assert fotografia(engine) == antes


def test_um_select_por_requisicao_para_ambos_os_periodos_sem_gravacoes(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-09-02T12:00:00"); criar(banco, 2); banco.commit()
    entrar(http); antes = fotografia(engine); comandos = []
    def capturar(_, __, comando, *args): comandos.append(comando)
    event.listen(engine, "before_cursor_execute", capturar)
    try:
        consultar(http, periodo="a"); consultar(http, periodo="b"); exportado(http)
    finally: event.remove(engine, "before_cursor_execute", capturar)
    assert len(comandos) == 3 and all(c.lstrip().upper().startswith("SELECT") for c in comandos)
    assert fotografia(engine) == antes


def test_eventos_reais_atualizam_acumulados_sem_mudar_periodo_da_contratacao(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-09-02T12:00:00", os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Simulação D39."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4); evento_financeiro(http, "encerrar", 5)
    antes = fotografia(engine)
    d = consultar(http, busca="OS #3")
    assert d["resumo_a"]["indicadores"]["financeiros_encerrados"] == 1
    assert medida(d, "recebido_confirmado")["valor_a"] == medida(d, "repassado_confirmado")["valor_a"] == "12500.00"
    assert d["resumo_b"]["indicadores"]["total_contratacoes"] == 0
    exportado(http, busca="OS #3"); assert fotografia(engine) == antes
