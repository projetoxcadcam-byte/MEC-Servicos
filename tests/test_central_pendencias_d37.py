"""D37: filas atuais, valores por contratação única, destinos e preservação."""
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
CENTRAL = "/api/v1/administracao/pendencias"


def consultar(http, **params):
    r = http.get(CENTRAL, params=params)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def exportado(http, **params):
    r = http.get(CENTRAL + "/csv", params=params)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert "text/csv" in r.headers["content-type"] and r.headers["cache-control"] == "no-store"
    assert "MEC_SERVICOS_CENTRAL_PENDENCIAS.csv" in r.headers["content-disposition"]
    t = r.content.decode("utf-8-sig")
    assert all(len(l) == 25 for l in csv.reader(io.StringIO(t), delimiter=";"))
    return list(csv.DictReader(io.StringIO(t), delimiter=";"))


def criar(banco, cid=1, data="2026-10-02T16:44:48", **opcoes):
    contrato(banco, cid, **opcoes); banco.get(ContratacaoServico, cid).criada_em = datetime.fromisoformat(data)


def test_json_csv_exigem_administrador_real(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco); banco.commit()
    for rota in (CENTRAL, CENTRAL + "/csv"): assert http.get(rota).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for rota in (CENTRAL, CENTRAL + "/csv"):
            r = http.get(rota, params={"perfil": "admin", "empresa_id": 2})
            assert r.status_code == 403 and "indicadores" not in r.text and "Cliente Mecânico" not in r.text


def test_base_vazia_e_os_encerrada_sem_pendencias_nem_valores_ficticios(ambiente_d33):
    http, sessoes, _ = ambiente_d33; entrar(http)
    for vazia in (True, False):
        if not vazia:
            with sessoes() as banco:
                criar(banco, os_id=3, status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
                recebimento(banco, 1, "12500.00"); repasse(banco, 1, 1250000); banco.commit()
        d = consultar(http, busca="OS #3")
        assert d["total_pendencias"] == d["total_contratacoes"] == 0 and d["itens"] == []
        assert d["valor_contratado"] == "0.00"
        assert all(v in (0, "0.00") for v in d["indicadores"].values())
        assert len(d["catalogo_acoes"]) == 24
        linhas = exportado(http, busca="OS #3")
        assert not [l for l in linhas if l["Tipo de registro"] in {"Pendência", "Contratação"}]
        assert next(l for l in linhas if l["Tipo de registro"] == "Total")["Quantidade de pendências"] == "0"


def test_varias_acoes_na_mesma_contratacao_somam_dinheiro_uma_vez(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, os_id=3, ordem_status="concluida", ciclo="entregue_cliente", controle="aberto")
        recebimento(banco, 1, "10000.00"); recebimento(banco, 1, "999.00", "cancelado"); repasse(banco, 1, 55500, "estornado"); banco.commit()
    entrar(http)
    d = consultar(http)
    assert d["total_pendencias"] == d["pendencias_financeiras"] == 2 and d["total_contratacoes"] == 1
    assert d["valor_contratado"] == "12500.00" and d["indicadores"]["recebimentos_confirmados"] == "10000.00"
    assert d["indicadores"]["repasses_confirmados"] == "0.00" and d["indicadores"]["saldo_clientes_controles_abertos"] == "2500.00"
    assert d["indicadores"]["saldo_fornecedores_controles_abertos"] == "12500.00" and d["indicadores"]["disponivel_repasses"] == "10000.00"
    assert {i["pendencia"]["codigo"] for i in d["itens"]} == {"receber_cliente", "repassar_fornecedor"}
    assert all(i["caminho"] == "/admin/pagamentos?contratacao=1" for i in d["itens"])
    linhas = exportado(http)
    movimentos = [l for l in linhas if l["Tipo de registro"] == "Pendência"]
    contratos = [l for l in linhas if l["Tipo de registro"] == "Contratação"]
    assert len(movimentos) == 2 and len(contratos) == 1
    assert all(l["Valor contratado"] == l["Recebido confirmado"] == "" for l in movimentos)
    assert contratos[0]["Valor contratado"] == "12500,00"
    filtrado = consultar(http, area="financeira", acao="receber_cliente")
    assert filtrado["total_pendencias"] == 1 and filtrado["valor_contratado"] == d["valor_contratado"]


def test_destinos_de_criar_os_intermediacao_e_financeiro(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, com_os=False); criar(banco, 2, os_id=3); banco.commit()
    entrar(http)
    d = consultar(http)
    por_acao = {(i["contratacao"]["contratacao_id"], i["pendencia"]["codigo"]): i for i in d["itens"]}
    assert por_acao[(1, "criar_ordem")]["caminho"] == "/admin/intermediacao?contratacao=1"
    assert por_acao[(2, "iniciar_intermediacao")]["caminho"] == "/admin/intermediacao?ordem=3"
    assert por_acao[(2, "iniciar_financeiro")]["caminho"] == "/admin/pagamentos?contratacao=2"
    assert d["total_pendencias"] == 4 and d["total_contratacoes"] == 2 and d["pendencias_operacionais"] == d["pendencias_financeiras"] == 2


def test_repasse_aguardando_entrega_encaminha_intermediacao(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco, os_id=3, ciclo="material_recebido", controle="aberto"); banco.commit()
    entrar(http)
    d = consultar(http, area="financeira", acao="repasse_aguarda_entrega")
    assert d["total_pendencias"] == 1
    assert d["itens"][0]["destino"] == "intermediacao" and d["itens"][0]["caminho"] == "/admin/intermediacao?ordem=3"


def test_divergencia_encaminha_conferencia_sem_corrigir_historico(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: criar(banco, status="encerrada", ciclo="material_recebido", controle="encerrado"); banco.commit()
    entrar(http); antes = fotografia(engine)
    d = consultar(http, area="conferencia")
    assert d["total_pendencias"] == d["pendencias_conferencia"] == 1
    assert d["itens"][0]["pendencia"]["codigo"] == "conferir_financeiro_encerrado"
    assert d["itens"][0]["destino"] == "relatorio" and d["itens"][0]["caminho"] == "/admin/relatorios?contratacao=1"
    exportado(http, area="conferencia"); assert fotografia(engine) == antes


def test_periodo_busca_situacao_area_acao_e_ordem_estavel(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, "2026-10-01T23:59:59.999999", ciclo="material_recebido")
        criar(banco, 2, "2026-10-02T00:00:00", os_id=3, ciclo="material_recebido")
        criar(banco, 3, "2026-10-02T23:59:59.999999", ciclo="aguardando_material")
        criar(banco, 4, "2026-10-03T00:00:00", ciclo="material_recebido"); banco.commit()
    entrar(http)
    d = consultar(http, data_inicial="2026-10-02", data_final="2026-10-02", area="operacional")
    assert [i["contratacao"]["contratacao_id"] for i in d["itens"]] == [2, 3]
    params = {"data_inicial": "2026-10-02", "data_final": "2026-10-02", "filtro": "operacionais", "area": "operacional", "acao": "encaminhar_material", "busca": "OS #3"}
    d = consultar(http, **params)
    assert d["total_contratacoes"] == d["total_pendencias"] == 1 and d["itens"][0]["contratacao"]["contratacao_id"] == 2
    linhas = exportado(http, **params)
    filtros = {l["Campo"]: l["Informação"] for l in linhas if l["Tipo de registro"] == "Filtro"}
    assert filtros["Área"] == "operacional" and filtros["Ação"] == "encaminhar_material" and filtros["Busca"] == "OS #3"
    assert consultar(http, filtro="concluidas")["total_pendencias"] == 0
    assert consultar(http, area="financeira", acao="encaminhar_material")["total_pendencias"] == 0


def test_paginas_csv_completo_e_valores_sem_repeticao(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 27): criar(banco, cid, valor="10.01", com_os=False)
        banco.commit()
    entrar(http)
    d = consultar(http, deslocamento=40)
    assert len(d["itens"]) == 12 and d["total_pendencias"] == 52 and d["total_contratacoes"] == 26
    assert d["valor_contratado"] == "260.26" and d["pendencias_operacionais"] == d["pendencias_financeiras"] == 26
    assert consultar(http, limite=1)["indicadores"] == d["indicadores"]
    linhas = exportado(http, deslocamento=40, limite=1)
    assert len([l for l in linhas if l["Tipo de registro"] == "Pendência"]) == 52
    contratos = [l for l in linhas if l["Tipo de registro"] == "Contratação"]
    assert len(contratos) == 26 and sum(Decimal(l["Valor contratado"].replace(",", ".")) for l in contratos) == Decimal("260.26")
    assert next(l for l in linhas if l["Tipo de registro"] == "Total")["Quantidade de pendências"] == "52"


@pytest.mark.parametrize("params", [
    {"area": "urgente"}, {"acao": "aprovar_automaticamente"}, {"acao": "a" * 71}, {"data_inicial": "2026-02-30"},
    {"data_final": "02/10/2026"}, {"data_inicial": "2026-10-03", "data_final": "2026-10-02"},
    {"filtro": "ativa"}, {"busca": "a" * 121}, {"deslocamento": -1}, {"limite": 0}, {"limite": 101},
])
def test_filtros_invalidos_recusados(ambiente_d33, params):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(CENTRAL, params=params).status_code == 422
    if not any(k in params for k in ("deslocamento", "limite")):
        assert http.get(CENTRAL + "/csv", params=params).status_code == 422


@pytest.mark.parametrize("campo", ["data_inicial", "data_final", "filtro", "busca", "area", "acao", "deslocamento", "limite"])
def test_parametros_repetidos_recusados(ambiente_d33, campo):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (CENTRAL, CENTRAL + "/csv"):
        assert http.get(rota + "?" + campo + "=1&" + campo + "=2").status_code == 422


def test_csv_escapa_formulas_separadores_e_multilinhas(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        banco.get(Empresa, 2).razao_social = '=SOMA(1;2)\n"Cliente Mecânico"'
        banco.get(Empresa, 4).razao_social = "Oficina; Mecânica\nAlfa"
        criar(banco); banco.commit()
    entrar(http)
    linhas = exportado(http)
    for l in linhas:
        if l["Tipo de registro"] in {"Pendência", "Contratação"}:
            assert l["Cliente"].startswith("'=SOMA") and l["Fornecedor"] == "Oficina; Mecânica\nAlfa"


def test_fluxo_real_tira_pendencias_apos_encerrar_sem_gravacao_em_get(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: criar(banco, os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert consultar(http)["itens"][0]["pendencia"]["codigo"] == "iniciar_financeiro"
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Teste D37."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4)
    d = consultar(http)
    assert d["total_pendencias"] == 1 and d["itens"][0]["pendencia"]["codigo"] == "encerrar_financeiro"
    assert d["indicadores"]["recebimentos_confirmados"] == "12500.00"
    evento_financeiro(http, "encerrar", 5); antes = fotografia(engine)
    assert consultar(http)["total_pendencias"] == 0
    assert not [l for l in exportado(http) if l["Tipo de registro"] == "Pendência"]
    assert fotografia(engine) == antes


def test_consultas_em_lote_sem_select_por_pendencia(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 31): criar(banco, cid, com_os=False)
        banco.commit()
    entrar(http); comandos = []
    def registrar(_, __, sql, *args): comandos.append(sql)
    event.listen(engine, "before_cursor_execute", registrar)
    try:
        consultar(http); assert len(comandos) == 1 and comandos[0].lstrip().upper().startswith("SELECT")
        comandos.clear(); exportado(http); assert len(comandos) == 1
    finally: event.remove(engine, "before_cursor_execute", registrar)
