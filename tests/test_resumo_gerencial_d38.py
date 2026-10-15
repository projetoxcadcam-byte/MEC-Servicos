"""D38: reconciliação anual/mensal, situações atuais, ações e consultas sem gravação."""
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
GERENCIAL = "/api/v1/administracao/relatorios/gerencial"


def consultar(http, **params):
    r = http.get(GERENCIAL, params=params)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def exportado(http, **params):
    r = http.get(GERENCIAL + "/csv", params=params)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert "text/csv" in r.headers["content-type"] and r.headers["cache-control"] == "no-store"
    assert "MEC_SERVICOS_RESUMO_GERENCIAL_MENSAL.csv" in r.headers["content-disposition"]
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert all(len(l) == 34 for l in linhas)
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))


def test_json_e_csv_exigem_sessao_admin_real(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco, 1); banco.commit()
    for rota in (GERENCIAL, GERENCIAL + "/csv"):
        assert http.get(rota).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for rota in (GERENCIAL, GERENCIAL + "/csv"):
            r = http.get(rota, params={"ano": 2026, "mes": 10, "perfil": "admin", "empresa_id": 2})
            assert r.status_code == 403 and "Cliente Mecânico" not in r.text and "resumo_ano" not in r.text


def test_vazio_mostra_doze_meses_e_calendario_correto(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    d = consultar(http)
    assert d["filtros"]["ano"] == datetime.now(UTC).year
    assert d["resumo_mes"] is None and d["itens"] == [] and d["total"] == 0
    assert [m["mes"] for m in d["meses"]] == list(range(1, 13))
    assert all(m["valor_contratado"] == "0.00" and m["indicadores"]["total_contratacoes"] == 0 for m in d["meses"])
    for ano, final in ((2024, "2024-02-29"), (2026, "2026-02-28"), (9999, "9999-02-28")):
        d = consultar(http, ano=ano, mes=2)
        assert d["resumo_mes"]["data_final"] == final and d["resumo_mes"]["indicadores"]["total_contratacoes"] == 0
        linhas = exportado(http, ano=ano, mes=2)
        assert len([l for l in linhas if l["Tipo de registro"] == "Mês"]) == 12
        assert not [l for l in linhas if l["Tipo de registro"] == "Contratação"]


def test_os3_encerrada_aparece_em_outubro_com_historico_e_sem_pendencias(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, os_id=3, status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        recebimento(banco, 1, "1250.00", "cancelado"); recebimento(banco, 1, "12500.00"); repasse(banco, 1, 1250000)
        banco.commit()
    entrar(http); antes = fotografia(engine)
    d = consultar(http, ano=2026, mes=10, busca="OS #03")
    a, m = d["resumo_ano"], d["resumo_mes"]
    assert a["valor_contratado"] == m["valor_contratado"] == "12500.00"
    assert m["indicadores"]["total_contratacoes"] == m["indicadores"]["contratacoes_concluidas"] == m["indicadores"]["financeiros_encerrados"] == 1
    assert m["indicadores"]["recebimentos_confirmados"] == m["indicadores"]["repasses_confirmados"] == "12500.00"
    assert m["contratacoes_com_pendencias"] == m["pendencias_operacionais"] == m["pendencias_financeiras"] == m["pendencias_conferencia"] == 0
    assert d["itens"][0]["contratacao_id"] == 1 and d["itens"][0]["ordem_servico_id"] == 3
    assert all(x["indicadores"]["total_contratacoes"] == 0 for x in d["meses"] if x["mes"] != 10)
    linhas = exportado(http, ano=2026, mes=10, busca="OS #03")
    c = next(l for l in linhas if l["Tipo de registro"] == "Contratação")
    assert c["OS"] == "3" and c["Financeiro"] == "encerrado" and c["Valor contratado"] == "12500,00"
    assert c["Recebido confirmado"] == c["Repassado confirmado"] == "12500,00" and c["Códigos de pendências"] == ""
    assert c["Saldo de clientes com controle aberto"] == c["Disponível para repasse"] == ""
    assert fotografia(engine) == antes


def test_meses_reconciliam_centavos_situacoes_saldos_e_acoes_do_d37(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-01-02T12:00:00", valor="0.10", ordem_status="concluida", ciclo="entregue_cliente", controle="aberto")
        criar(banco, 2, "2026-02-02T12:00:00", valor="0.20", ciclo="material_recebido", controle="aberto")
        criar(banco, 3, "2026-02-03T12:00:00", valor="0.30", status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        criar(banco, 4, "2026-03-01T12:00:00", valor="0.40", status="cancelada", com_os=False)
        criar(banco, 5, "2026-03-02T12:00:00", valor="0.50", status="encerrada", ciclo="material_recebido", controle="encerrado")
        for cid, valor in ((1, "0.07"), (2, "0.05"), (3, "0.30"), (5, "0.50")): recebimento(banco, cid, valor)
        for cid, valor in ((1, 3), (3, 30), (5, 50)): repasse(banco, cid, valor)
        recebimento(banco, 1, "99.99", "cancelado"); repasse(banco, 1, 9999, "estornado"); banco.commit()
    entrar(http); d = consultar(http, ano=2026); a = d["resumo_ano"]
    assert a["valor_contratado"] == "1.50"
    i = a["indicadores"]
    assert i["recebimentos_confirmados"] == "0.92" and i["repasses_confirmados"] == "0.83"
    assert i["saldo_clientes_controles_abertos"] == "0.18" and i["saldo_fornecedores_controles_abertos"] == "0.27"
    assert i["disponivel_repasses"] == "0.04"
    assert a["em_andamento"] == 2 and i["contratacoes_concluidas"] == i["contratacoes_canceladas"] == i["para_conferencia"] == i["financeiros_encerrados"] == 1
    assert a["contratacoes_com_pendencias"] == 3
    assert a["pendencias_operacionais"] == 1 and a["pendencias_financeiras"] == 4 and a["pendencias_conferencia"] == 1
    for campo in i:
        assert sum(Decimal(str(m["indicadores"][campo])) for m in d["meses"]) == Decimal(str(i[campo])), campo
    for campo in ("valor_contratado", "em_andamento", "contratacoes_com_pendencias", "pendencias_operacionais", "pendencias_financeiras", "pendencias_conferencia"):
        assert sum(Decimal(str(m[campo])) for m in d["meses"]) == Decimal(str(a[campo])), campo
    fila = http.get("/api/v1/administracao/pendencias", params={"data_inicial": "2026-01-01", "data_final": "2026-12-31"}).json()
    assert fila["total_contratacoes"] == a["contratacoes_com_pendencias"] and fila["total_pendencias"] == 6
    assert all(fila[c] == a[c] for c in ("pendencias_operacionais", "pendencias_financeiras", "pendencias_conferencia"))


def test_ano_mes_situacao_busca_e_detalhe_vazio_preservam_resumo_anual(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2025-12-31T23:59:59.999999")
        criar(banco, 2, "2026-01-01T00:00:00", status="encerrada", ordem_status="concluida")
        criar(banco, 3, "2026-01-31T23:59:59.999999")
        criar(banco, 4, "2026-12-31T23:59:59.999999", status="cancelada", com_os=False)
        criar(banco, 5, "2027-01-01T00:00:00"); banco.commit()
    entrar(http)
    d = consultar(http, ano=2026)
    assert d["resumo_ano"]["indicadores"]["total_contratacoes"] == 3
    assert d["meses"][0]["indicadores"]["total_contratacoes"] == 2 and d["meses"][11]["indicadores"]["total_contratacoes"] == 1
    c = consultar(http, ano=2026, filtro="concluidas", busca="OS #102", mes=1)
    assert c["total"] == 1 and c["itens"][0]["contratacao_id"] == 2
    vazio = consultar(http, ano=2026, filtro="concluidas", busca="OS #102", mes=10)
    assert vazio["total"] == 0 and vazio["itens"] == [] and vazio["resumo_ano"] == c["resumo_ano"]
    assert consultar(http, ano=2026, busca="Contratação #3", mes=1)["total"] == 1
    assert consultar(http, ano=2026, busca="oficina mecanica alfa")["resumo_ano"]["indicadores"]["total_contratacoes"] == 3
    assert consultar(http, ano=2026, filtro="operacionais")["resumo_ano"]["indicadores"]["total_contratacoes"] == 1
    assert consultar(http, ano=2026, filtro="canceladas", mes=12)["itens"][0]["contratacao_id"] == 4


def test_meses_e_anos_usam_datas_utc_inclusive_em_limites_de_fuso(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 4): criar(banco, cid)
        banco.commit()
    with engine.begin() as banco:
        for cid, data in ((1, "2026-01-01T00:30:00+01:00"), (2, "2026-12-31T23:30:00-01:00"), (3, "2026-01-01T00:30:00-01:00")):
            banco.exec_driver_sql("UPDATE contratacoes_servico SET criada_em=? WHERE id=?", (data, cid))
    entrar(http)
    for ano, mes, cid in ((2025, 12, 1), (2027, 1, 2), (2026, 1, 3)):
        d = consultar(http, ano=ano, mes=mes)
        assert d["total"] == d["resumo_ano"]["indicadores"]["total_contratacoes"] == 1
        assert d["itens"][0]["contratacao_id"] == cid
        assert d["itens"][0]["contratada_em"].startswith(str(ano))


def test_paginacao_nao_limita_meses_valores_anuais_nem_csv(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 27): criar(banco, cid, valor="10.01")
        criar(banco, 27, "2026-02-01T12:00:00", valor="10.01"); banco.commit()
    entrar(http)
    a = consultar(http, ano=2026, mes=10); b = consultar(http, ano=2026, mes=10, deslocamento=20)
    assert a["total"] == b["total"] == 26 and len(a["itens"]) == 20 and len(b["itens"]) == 6
    assert a["resumo_ano"] == b["resumo_ano"] and a["meses"] == b["meses"] and a["resumo_mes"] == b["resumo_mes"]
    assert a["resumo_ano"]["valor_contratado"] == "270.27" and a["resumo_mes"]["valor_contratado"] == "260.26"
    assert [c["contratacao_id"] for c in a["itens"]] == list(range(26, 6, -1))
    for mes, qtd in ((None, 27), (10, 26), (2, 1), (3, 0)):
        params = {"ano": 2026, "deslocamento": 20, "limite": 1}
        if mes: params["mes"] = mes
        linhas = exportado(http, **params)
        contratos = [l for l in linhas if l["Tipo de registro"] == "Contratação"]
        assert len(contratos) == qtd and len({l["Contratação"] for l in contratos}) == qtd
        assert sum(Decimal(l["Valor contratado"].replace(",", ".")) for l in contratos) == Decimal("10.01") * qtd
        assert next(l for l in linhas if l["Tipo de registro"] == "Total anual")["Valor contratado"] == "270,27"
        assert len([l for l in linhas if l["Tipo de registro"] == "Mês"]) == 12


@pytest.mark.parametrize("params", [
    {"ano": 0}, {"ano": -1}, {"ano": 10000}, {"ano": "2026.5"}, {"ano": "dois mil"}, {"ano": ""},
    {"mes": 0}, {"mes": 13}, {"mes": "10.5"}, {"filtro": "ativas"}, {"busca": "a" * 121},
    {"deslocamento": -1}, {"limite": 0}, {"limite": 101},
])
def test_filtros_invalidos_recusados(ambiente_d33, params):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(GERENCIAL, params=params).status_code == 422
    if not any(k in params for k in ("deslocamento", "limite")):
        assert http.get(GERENCIAL + "/csv", params=params).status_code == 422


@pytest.mark.parametrize("campo", ["ano", "filtro", "busca", "mes", "deslocamento", "limite"])
def test_query_repetida_recusada_em_json_e_csv(ambiente_d33, campo):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (GERENCIAL, GERENCIAL + "/csv"):
        assert http.get(rota + "?" + campo + "=1&" + campo + "=2").status_code == 422


def test_csv_preserva_acentos_campos_multilinha_e_escapa_formulas(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        banco.get(Empresa, 2).razao_social = '=SOMA(1;2)\n"Cliente Mecânico"'
        banco.get(Empresa, 4).razao_social = 'Oficina; Mecânica\n"Alfa"'
        criar(banco, 1); banco.commit()
    entrar(http)
    linhas = exportado(http, ano=2026, mes=10)
    c = next(l for l in linhas if l["Tipo de registro"] == "Contratação")
    assert c["Cliente"].startswith("'=SOMA") and "Cliente Mecânico" in c["Cliente"]
    assert c["Fornecedor"] == 'Oficina; Mecânica\n"Alfa"'
    assert c["Cliente ID"] == "2" and c["Fornecedor ID"] == "4"


def test_fluxo_real_apos_estorno_e_encerramento_permanece_no_mes_da_contratacao(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2025-09-30T12:00:00", os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    inicial = consultar(http, ano=2025, mes=9)
    assert inicial["resumo_mes"]["pendencias_financeiras"] == 1
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Simulação D38; não há operação bancária."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4); evento_financeiro(http, "encerrar", 5)
    antes = fotografia(engine)
    d = consultar(http, ano=2025, mes=9, busca="OS #3")
    assert d["resumo_mes"]["indicadores"]["recebimentos_confirmados"] == d["resumo_mes"]["indicadores"]["repasses_confirmados"] == "12500.00"
    assert d["resumo_mes"]["indicadores"]["financeiros_encerrados"] == 1 and d["resumo_mes"]["contratacoes_com_pendencias"] == 0
    assert consultar(http, ano=2026, busca="OS #3")["resumo_ano"]["indicadores"]["total_contratacoes"] == 0
    exportado(http, ano=2025, mes=9, busca="OS #3")
    assert fotografia(engine) == antes


def test_um_select_para_doze_meses_detalhe_e_exportacao(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 31): criar(banco, cid, f"2026-{1 + cid % 12:02d}-02T12:00:00")
        banco.commit()
    entrar(http); comandos = []
    def capturar(_, __, comando, *args): comandos.append(comando)
    event.listen(engine, "before_cursor_execute", capturar)
    try:
        consultar(http, ano=2026, mes=10)
        assert len(comandos) == 1 and comandos[0].lstrip().upper().startswith("SELECT")
        comandos.clear(); exportado(http, ano=2026, mes=10)
        assert len(comandos) == 1 and comandos[0].lstrip().upper().startswith("SELECT")
    finally:
        event.remove(engine, "before_cursor_execute", capturar)
