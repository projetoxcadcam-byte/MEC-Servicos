"""D36: grupos por ID e papel, reconciliação, paginação e consultas sem gravação."""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
import io
import pytest
from sqlalchemy import event
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico
from test_painel_administrativo_d33 import (
    ambiente_d33, contas_d33, contrato, entrar, evento_financeiro, fotografia,
    recebimento, repasse, Empresa, FINANCEIRO,
)

pytestmark = pytest.mark.acesso_real
EMPRESAS = "/api/v1/administracao/relatorios/empresas"
PERIODO = "/api/v1/administracao/relatorios/periodo"


def consultar(http, **params):
    r = http.get(EMPRESAS, params=params)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()


def exportado(http, **params):
    r = http.get(EMPRESAS + "/csv", params=params)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert "text/csv" in r.headers["content-type"] and r.headers["cache-control"] == "no-store"
    assert "MEC_SERVICOS_RELATORIO_EMPRESAS.csv" in r.headers["content-disposition"]
    linhas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert all(len(l) == 25 for l in linhas)
    return list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))


def criar(banco, cid, data="2026-10-02T16:44:48", cliente=2, fornecedor=4, **opcoes):
    oid = contrato(banco, cid, **opcoes)
    c = banco.get(ContratacaoServico, cid)
    c.criada_em = datetime.fromisoformat(data); c.empresa_cliente_id = cliente; c.empresa_fornecedora_id = fornecedor
    banco.get(SolicitacaoServico, cid).empresa_cliente_id = cliente
    banco.get(CotacaoFornecedor, cid).empresa_fornecedora_id = fornecedor
    o = banco.get(OrdemServico, oid)
    if o: o.empresa_cliente_id = cliente; o.empresa_fornecedora_id = fornecedor


def empresas(banco):
    banco.add_all([Empresa(id=6, razao_social="Empresa repetida", documento="cliente-d36-6", tipo_empresa="ambos"),
                   Empresa(id=7, razao_social="Empresa repetida", documento="fornecedor-d36-7", tipo_empresa="ambos")])
    banco.get(Empresa, 2).razao_social = "Empresa repetida"
    banco.get(Empresa, 4).razao_social = "Empresa repetida"
    banco.flush()


def test_acesso_real_sem_vazamento_nem_perfil_por_query(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: criar(banco, 1); banco.commit()
    for rota in (EMPRESAS, EMPRESAS + "/csv"):
        assert http.get(rota).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for rota in (EMPRESAS, EMPRESAS + "/csv"):
            r = http.get(rota, params={"perfil": "admin", "empresa_id": 2, "agrupamento": "clientes"})
            assert r.status_code == 403 and "Cliente Mecânico" not in r.text and "indicadores" not in r.text


def test_base_vazia_e_empresa_sem_correspondencia(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    for params in ({}, {"empresa_id": 999}, {"agrupamento": "fornecedores"}):
        d = consultar(http, **params)
        assert d["total_empresas"] == d["total_contratacoes"] == 0
        assert d["grupos"] == d["itens"] == [] and d["empresa_selecionada"] is None
        assert all(v in (0, "0.00") for v in d["indicadores"].values())
        assert d["valor_contratado"] == "0.00"
        linhas = exportado(http, **params)
        assert not [l for l in linhas if l["Tipo de registro"] in {"Empresa", "Contratação"}]


def test_grupos_por_id_centavos_exatos_estornos_e_papeis(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        empresas(banco)
        criar(banco, 1, valor="0.10", ordem_status="concluida", ciclo="entregue_cliente", controle="aberto")
        criar(banco, 2, fornecedor=7, valor="0.20", controle="aberto", ciclo="material_recebido")
        criar(banco, 3, cliente=6, valor="0.30", status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        for cid, v in ((1, "0.07"), (2, "0.05"), (3, "0.30")): recebimento(banco, cid, v)
        recebimento(banco, 1, "9.99", "cancelado"); repasse(banco, 1, 3); repasse(banco, 3, 30)
        repasse(banco, 1, 999, "estornado"); banco.commit()
    entrar(http)
    c = consultar(http)
    assert c["total_empresas"] == 2 and c["total_contratacoes"] == 3 and c["itens"] == []
    assert [g["empresa_id"] for g in c["grupos"]] == [2, 6]
    assert [g["valor_contratado"] for g in c["grupos"]] == ["0.30", "0.30"]
    assert c["valor_contratado"] == "0.60"
    assert c["indicadores"]["recebimentos_confirmados"] == "0.42"
    assert c["indicadores"]["repasses_confirmados"] == "0.33"
    assert c["indicadores"]["saldo_clientes_controles_abertos"] == "0.18"
    assert c["indicadores"]["saldo_fornecedores_controles_abertos"] == "0.27"
    assert c["indicadores"]["disponivel_repasses"] == "0.04"
    assert c["grupos"][0]["indicadores"]["pendencias_financeiras"] == 2
    f = consultar(http, agrupamento="fornecedores")
    assert f["indicadores"] == c["indicadores"] and f["valor_contratado"] == c["valor_contratado"]
    assert [(g["empresa_id"], g["valor_contratado"]) for g in f["grupos"]] == [(4, "0.40"), (7, "0.20")]
    for campo in ("total_contratacoes", "recebimentos_confirmados", "repasses_confirmados",
                  "saldo_clientes_controles_abertos", "saldo_fornecedores_controles_abertos", "disponivel_repasses"):
        assert sum(Decimal(str(g["indicadores"][campo])) for g in f["grupos"]) == Decimal(str(f["indicadores"][campo]))
    assert consultar(http, agrupamento="fornecedores", empresa_id=2)["total_contratacoes"] == 0


def test_empresa_ambos_nao_mistura_contratacoes_dos_dois_papeis(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        empresas(banco); criar(banco, 1, cliente=6); criar(banco, 2, fornecedor=6); banco.commit()
    entrar(http)
    c = consultar(http, empresa_id=6)
    f = consultar(http, agrupamento="fornecedores", empresa_id=6)
    assert [i["contratacao_id"] for i in c["itens"]] == [1]
    assert [i["contratacao_id"] for i in f["itens"]] == [2]


def test_periodo_situacao_busca_e_empresa_se_combinam(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        empresas(banco)
        criar(banco, 1, "2026-10-02T00:00:00", os_id=3, status="encerrada", ordem_status="concluida", ciclo="entregue_cliente", controle="encerrado")
        recebimento(banco, 1, "12500.00"); repasse(banco, 1, 1250000)
        criar(banco, 2, "2026-10-02T23:59:59.999999", fornecedor=7)
        criar(banco, 3, "2026-10-03T00:00:00", fornecedor=7)
        banco.commit()
    entrar(http)
    params = {"data_inicial": "2026-10-02", "data_final": "2026-10-02", "filtro": "concluidas", "busca": "OS #3"}
    d = consultar(http, agrupamento="fornecedores", empresa_id=4, **params)
    assert d["total_empresas"] == d["total_contratacoes"] == 1
    assert d["itens"][0]["contratacao_id"] == 1 and d["itens"][0]["ordem_servico_id"] == 3
    assert d["empresa_selecionada"]["empresa_id"] == 4 and d["valor_contratado"] == "12500.00"
    p = http.get(PERIODO, params=params).json()
    assert d["indicadores"] == p["indicadores"] and d["valor_contratado"] == p["valor_contratado"]
    assert consultar(http, data_inicial="2026-10-02", data_final="2026-10-02")["total_contratacoes"] == 2
    assert consultar(http, agrupamento="fornecedores", empresa_id=7, **params)["total_contratacoes"] == 0
    linhas = exportado(http, agrupamento="fornecedores", empresa_id=4, **params)
    filtros = {l["Campo"]: l["Informação"] for l in linhas if l["Tipo de registro"] == "Filtro"}
    assert filtros["Empresa selecionada ID"] == "4" and filtros["Busca"] == "OS #3"
    assert filtros["Data inicial UTC"] == filtros["Data final UTC"] == "2026-10-02"


def test_paginas_de_empresas_e_contratacoes_nao_limitam_totais_ou_csv(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 27):
            eid = 10 + cid
            banco.add(Empresa(id=eid, razao_social="Fornecedor " + str(cid), documento="fornecedor-d36-" + str(cid), tipo_empresa="fornecedor")); banco.flush()
            criar(banco, cid, fornecedor=eid, valor="10.01")
        banco.commit()
    entrar(http)
    f = consultar(http, agrupamento="fornecedores", deslocamento=20)
    assert len(f["grupos"]) == 6 and f["total_empresas"] == f["total_contratacoes"] == 26
    assert f["valor_contratado"] == "260.26"
    c = consultar(http, empresa_id=2, deslocamento_itens=20)
    assert len(c["itens"]) == 6 and c["total_empresas"] == 1 and c["total_contratacoes"] == 26
    assert c["empresa_selecionada"]["indicadores"]["total_contratacoes"] == 26
    assert c["indicadores"] == f["indicadores"] and c["valor_contratado"] == f["valor_contratado"]
    linhas = exportado(http, agrupamento="fornecedores", deslocamento=20, limite=1)
    assert len([l for l in linhas if l["Tipo de registro"] == "Empresa"]) == 26
    assert len([l for l in linhas if l["Tipo de registro"] == "Contratação"]) == 26
    total = next(l for l in linhas if l["Tipo de registro"] == "Total")
    assert total["Valor contratado"] == "260,26" and total["Quantidade de contratações"] == "26"
    assert len([l for l in exportado(http, empresa_id=2) if l["Tipo de registro"] == "Contratação"]) == 26


@pytest.mark.parametrize("params", [
    {"agrupamento": "ambos"}, {"empresa_id": "0"}, {"empresa_id": "-1"}, {"empresa_id": "2.5"},
    {"data_inicial": "2026-02-30"}, {"data_final": "02/10/2026"}, {"data_inicial": "2026-10-03", "data_final": "2026-10-02"},
    {"filtro": "ativa"}, {"busca": "a" * 121}, {"deslocamento": -1}, {"deslocamento_itens": -1}, {"limite": 101},
])
def test_filtros_invalidos_recusados(ambiente_d33, params):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(EMPRESAS, params=params).status_code == 422
    if not any(k in params for k in ("deslocamento", "deslocamento_itens", "limite")):
        assert http.get(EMPRESAS + "/csv", params=params).status_code == 422


@pytest.mark.parametrize("campo", ["agrupamento", "empresa_id", "data_inicial", "data_final", "filtro", "busca", "deslocamento", "deslocamento_itens", "limite"])
def test_parametros_repetidos_recusados(ambiente_d33, campo):
    http, _, _ = ambiente_d33; entrar(http)
    for rota in (EMPRESAS, EMPRESAS + "/csv"):
        assert http.get(rota + "?" + campo + "=1&" + campo + "=2").status_code == 422


def test_csv_textos_acentos_separadores_multilinhas_e_formulas(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        banco.get(Empresa, 2).razao_social = '=SOMA(1;2)\n"Cliente Mecânico"'
        banco.get(Empresa, 4).razao_social = "Oficina; Mecânica\nAlfa"
        criar(banco, 1); banco.commit()
    entrar(http)
    linhas = exportado(http)
    grupo = next(l for l in linhas if l["Tipo de registro"] == "Empresa")
    item = next(l for l in linhas if l["Tipo de registro"] == "Contratação")
    assert grupo["Empresa"].startswith("'=SOMA") and "Cliente Mecânico" in grupo["Empresa"]
    assert item["Cliente"].startswith("'=SOMA") and item["Fornecedor"] == "Oficina; Mecânica\nAlfa"


def test_historico_encerrado_ou_cancelado_sem_controle_nao_inventa_saldo(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        criar(banco, 1, status="encerrada", com_os=False)
        criar(banco, 2, status="cancelada", com_os=False); banco.commit()
    entrar(http)
    d = consultar(http)
    assert d["total_contratacoes"] == 2 and d["indicadores"]["pendencias_financeiras"] == 0
    for c in ("saldo_clientes_controles_abertos", "saldo_fornecedores_controles_abertos", "disponivel_repasses"):
        assert d["indicadores"][c] == "0.00" and d["grupos"][0]["indicadores"][c] == "0.00"


def test_ciclo_real_estorno_encerramento_e_preservacao_de_get(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: criar(banco, 1, os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Teste D36."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4); evento_financeiro(http, "encerrar", 5)
    antes = fotografia(engine)
    for agrupamento in ("clientes", "fornecedores"):
        d = consultar(http, agrupamento=agrupamento, busca="OS #3")
        assert d["indicadores"]["recebimentos_confirmados"] == d["indicadores"]["repasses_confirmados"] == "12500.00"
        assert d["indicadores"]["financeiros_encerrados"] == 1 and d["indicadores"]["pendencias_financeiras"] == 0
        exportado(http, agrupamento=agrupamento, busca="OS #3")
    assert fotografia(engine) == antes


def test_um_select_por_consulta_independente_do_numero_de_grupos(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        empresas(banco)
        for cid in range(1, 31): criar(banco, cid, cliente=6 if cid % 2 else 2, fornecedor=7 if cid % 3 else 4)
        banco.commit()
    entrar(http)
    comandos = []
    def registrar(_, __, sql, *args): comandos.append(sql)
    event.listen(engine, "before_cursor_execute", registrar)
    try:
        consultar(http); assert len(comandos) == 1 and comandos[0].lstrip().upper().startswith("SELECT")
        comandos.clear(); exportado(http, agrupamento="fornecedores"); assert len(comandos) == 1
    finally: event.remove(engine, "before_cursor_execute", registrar)
