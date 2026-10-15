"""D35: período UTC, reconciliação, CSV completo e consultas sem gravação."""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
import io
import pytest
from sqlalchemy import event
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from test_painel_administrativo_d33 import (
    ambiente_d33, contas_d33, contrato, entrar, evento_financeiro, fotografia,
    recebimento, repasse, FINANCEIRO,
)

pytestmark = pytest.mark.acesso_real
PERIODO = "/api/v1/administracao/relatorios/periodo"


def consultar(http, **params):
    r = http.get(PERIODO, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def exportado(http, **params):
    r = http.get(PERIODO + "/csv", params=params)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert "text/csv" in r.headers["content-type"] and r.headers["cache-control"] == "no-store"
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))


def criar(banco, cid, data, **opcoes):
    contrato(banco, cid, **opcoes)
    banco.get(ContratacaoServico, cid).criada_em = datetime.fromisoformat(data)


def test_json_e_csv_exigem_sessao_administrativa(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco, 1, "2026-10-02T16:44:48"); banco.commit()
    for rota in (PERIODO, PERIODO + "/csv"):
        assert http.get(rota).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for rota in (PERIODO, PERIODO + "/csv"):
            r = http.get(rota, params={"perfil": "admin", "empresa_cliente_id": 2})
            assert r.status_code == 403
            assert "Cliente Mecânico" not in r.text and "indicadores" not in r.text


def test_base_vazia_sem_totais_ficticios(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    d = consultar(http)
    assert d["total"] == 0 and d["itens"] == d["meses"] == [] and d["valor_contratado"] == "0.00"
    assert all(v in (0, "0.00") for v in d["indicadores"].values())
    linhas = exportado(http)
    assert not [r for r in linhas if r["Tipo de registro"] in {"Mês", "Contratação"}]
    assert next(r for r in linhas if r["Tipo de registro"] == "Total")["Quantidade de contratações"] == "0"


def test_limites_incluem_dia_inteiro_e_mes_utc(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid, data in enumerate(["2026-01-30T23:59:59.999999", "2026-01-31T00:00:00",
                "2026-01-31T23:59:59.999999", "2026-02-01T00:00:00"], 1): criar(banco, cid, data)
        banco.commit()
    entrar(http)
    d = consultar(http, data_inicial="2026-01-31", data_final="2026-01-31")
    assert {r["contratacao_id"] for r in d["itens"]} == {2, 3}
    assert d["meses"] == [{"mes": "2026-01", "total_contratacoes": 2, "valor_contratado": "25000.00", "recebido_confirmado": "0.00", "repassado_confirmado": "0.00"}]
    assert consultar(http, data_inicial="2026-02-01")["total"] == 1
    assert consultar(http, data_final="2026-01-30")["total"] == 1
    assert consultar(http, data_final="9999-12-31")["total"] == 4


@pytest.mark.parametrize("params", [
    {"data_inicial": "2026-02-30"}, {"data_final": "2026-2-01"}, {"data_final": "0000-01-01"},
    {"data_inicial": "2026-10-06T00:00:00Z"}, {"data_inicial": " 2026-10-01"},
    {"data_inicial": "2026-10-06", "data_final": "2026-10-01"}, {"filtro": "abc"},
    {"busca": "x" * 121}, {"limite": 0}, {"limite": 101}, {"deslocamento": -1},
])
def test_filtros_invalidos_recusados(ambiente_d33, params):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(PERIODO, params=params).status_code == 422
    if not any(k in params for k in ("limite", "deslocamento")):
        assert http.get(PERIODO + "/csv", params=params).status_code == 422


def test_parametros_repetidos_recusados(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (PERIODO, PERIODO + "/csv"):
        assert http.get(rota + "?data_final=2026-10-01&data_final=2026-10-06").status_code == 422
        assert http.get(rota + "?busca=OS%20%233&busca=OS%20%234").status_code == 422


def test_totais_e_meses_sao_da_selecao_completa_sem_multiplicar_movimentos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-09-30T23:59:59", valor="1.01", controle="aberto")
        recebimento(banco, 1, "0.10"); recebimento(banco, 1, "0.20"); recebimento(banco, 1, "0.50", "cancelado")
        repasse(banco, 1, 7); repasse(banco, 1, 3); repasse(banco, 1, 9, "estornado")
        criar(banco, 2, "2026-10-01T00:00:00", valor="2.02", com_os=False)
        criar(banco, 3, "2026-10-02T16:44:48", valor="3.03", status="cancelada", com_os=False)
        banco.commit()
    entrar(http)
    d = consultar(http, limite=1)
    assert len(d["itens"]) == 1 and d["total"] == 3 and d["valor_contratado"] == "6.06"
    i = d["indicadores"]
    assert i["recebimentos_confirmados"] == "0.30" and i["repasses_confirmados"] == "0.10"
    assert i["saldo_clientes_controles_abertos"] == "0.71" and i["saldo_fornecedores_controles_abertos"] == "0.91"
    assert [m["mes"] for m in d["meses"]] == ["2026-09", "2026-10"]
    assert sum(Decimal(m["valor_contratado"]) for m in d["meses"]) == Decimal(d["valor_contratado"])
    outra = consultar(http, limite=1, deslocamento=2)
    assert outra["indicadores"] == i and outra["meses"] == d["meses"] and outra["itens"][0]["contratacao_id"] == 1
    outubro = consultar(http, data_inicial="2026-10-01")
    assert outubro["valor_contratado"] == "5.05" and outubro["indicadores"]["recebimentos_confirmados"] == "0.00"
    assert consultar(http, filtro="canceladas")["valor_contratado"] == "3.03"


def test_busca_exata_empresa_e_situacoes_combinadas(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-10-02T16:44:48", os_id=3, status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        recebimento(banco, 1, "12500.00"); repasse(banco, 1, 1250000)
        criar(banco, 2, "2026-10-03T10:00:00", com_os=False)
        banco.commit()
    entrar(http)
    for busca in (" OS #3 ", "contratação #1", "mecanico"):
        d = consultar(http, busca=busca, filtro="concluidas", data_inicial="2026-10-02", data_final="2026-10-02")
        assert d["total"] == 1 and d["itens"][0]["contratacao_id"] == 1
        assert d["indicadores"]["financeiros_encerrados"] == 1 and d["valor_contratado"] == "12500.00"
    assert consultar(http, busca="OS #3", filtro="operacionais")["total"] == 0
    assert consultar(http, busca="contratação #2", filtro="financeiras")["total"] == 1
    assert consultar(http, busca="OS #999")["valor_contratado"] == "0.00"


def test_fluxo_real_estorno_e_encerramento_conciliado_com_d34(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-10-02T16:44:48", os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Teste D35."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4); evento_financeiro(http, "encerrar", 5)
    d = consultar(http, busca="OS #3", data_inicial="2026-10-02", data_final="2026-10-02")
    detalhe = http.get("/api/v1/administracao/relatorios/contratacoes/1").json()
    assert d["itens"][0]["total_recebido"] == detalhe["resumo"]["total_recebido"] == "12500.00"
    assert d["indicadores"]["repasses_confirmados"] == "12500.00"
    assert d["indicadores"]["saldo_clientes_controles_abertos"] == d["indicadores"]["saldo_fornecedores_controles_abertos"] == "0.00"
    assert d["itens"][0]["situacao"] == "concluida" and len(detalhe["recebimentos"]) == 2
    linhas = exportado(http, busca="OS #3", data_inicial="2026-10-02", data_final="2026-10-02")
    total = next(r for r in linhas if r["Tipo de registro"] == "Total")
    assert total["Recebido confirmado"] == total["Repassado confirmado"] == "12500,00"
    assert total["Saldo de clientes com controle aberto"] == "0,00"


def test_csv_inclui_todas_paginas_e_protege_textos_sem_mudar_dados(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        banco.get(Empresa, 2).razao_social = '=HYPERLINK("x"); Cliente\nMecânico'
        banco.get(Empresa, 4).razao_social = ' \t@SUM(1); Oficina "Alfa"'
        for cid in range(1, 24): criar(banco, cid, "2026-10-02T12:00:00", com_os=False)
        banco.commit()
    antes = fotografia(engine); entrar(http)
    d = consultar(http, limite=1, deslocamento=20)
    assert d["total"] == 23 and len(d["itens"]) == 1
    assert d["itens"][0]["cliente"].startswith("=")
    linhas = exportado(http, limite=1, deslocamento=20)
    contratos = [r for r in linhas if r["Tipo de registro"] == "Contratação"]
    assert len(contratos) == 23 and {int(r["Contratação"]) for r in contratos} == set(range(1, 24))
    assert all(r["Cliente"].startswith("'=") and r["Fornecedor"].startswith("' \t@") for r in contratos)
    assert all(r["OS"] == r["Saldo de clientes com controle aberto"] == "" for r in contratos)
    assert next(r for r in linhas if r["Tipo de registro"] == "Total")["Quantidade de contratações"] == "23"
    assert all(None not in r for r in linhas) and fotografia(engine) == antes


def test_get_json_csv_uma_consulta_por_requisicao_e_sem_gravacoes(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 27): criar(banco, cid, "2026-10-02T12:00:00", controle="aberto")
        banco.commit()
    entrar(http); antes = fotografia(engine); comandos = []
    def registrar(_, __, sql, ___, ____, _____): comandos.append(sql)
    event.listen(engine, "before_cursor_execute", registrar)
    try:
        consultar(http, limite=1); consultar(http, busca="OS #101", limite=1); exportado(http)
    finally: event.remove(engine, "before_cursor_execute", registrar)
    assert len(comandos) == 3 and all(s.lstrip().upper().startswith("SELECT") for s in comandos)
    assert fotografia(engine) == antes


def test_historico_cancelado_encerrado_sem_controle_nao_cria_saldo_operacional(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-10-02T00:00:00", com_os=False, status="encerrada")
        criar(banco, 2, "2026-10-02T00:00:00", com_os=False, status="cancelada")
        recebimento(banco, 1, "500.00"); banco.commit()
    entrar(http); d = consultar(http)
    assert d["indicadores"]["recebimentos_confirmados"] == "500.00"
    assert d["indicadores"]["saldo_clientes_controles_abertos"] == d["indicadores"]["saldo_fornecedores_controles_abertos"] == "0.00"
    assert d["indicadores"]["pendencias_financeiras"] == 0
    assert all(not r["pendencias"] for r in d["itens"])
