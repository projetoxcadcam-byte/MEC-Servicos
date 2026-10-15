"""D34: relatório e CSV reais, histórico preservado e acesso administrativo."""
from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
import io
import sqlite3
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.financeiro_administrativo import EventoFinanceiro
from backend.app.models.intermediacao import CicloIntermediacao, EventoIntermediacao
from backend.app.services.relatorio_administrativo import ServicoRelatorioAdministrativo, celula_csv
from test_painel_administrativo_d33 import (
    ambiente_d33, contas_d33, contrato, entrar, evento_financeiro, fotografia,
    recebimento, repasse, FINANCEIRO, AGORA,
)

pytestmark = pytest.mark.acesso_real
RELATORIO = "/api/v1/administracao/relatorios/contratacoes/"


def consultar(http, cid=1):
    resposta = http.get(RELATORIO + str(cid))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def linhas_csv(http, cid=1):
    resposta = http.get(RELATORIO + str(cid) + "/csv")
    assert resposta.status_code == 200, resposta.text
    assert resposta.content.startswith(b"\xef\xbb\xbf")
    return list(csv.DictReader(io.StringIO(resposta.content.decode("utf-8-sig")), delimiter=";"))


def test_exige_sessao_e_administrador_no_json_e_no_csv(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3); banco.commit()
    for caminho in (RELATORIO + "1", RELATORIO + "1/csv"):
        assert http.get(caminho).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        for caminho in (RELATORIO + "1", RELATORIO + "1/csv"):
            resposta = http.get(caminho, params={"perfil": "admin", "empresa_cliente_id": 2, "empresa_fornecedora_id": 4})
            assert resposta.status_code == 403
            assert "Cliente Mecânico" not in resposta.text and "Oficina" not in resposta.text
    entrar(http)
    assert consultar(http)["resumo"]["ordem_servico_id"] == 3
    assert linhas_csv(http)


def test_servico_recusa_perfil_antes_de_acessar_banco():
    with pytest.raises(HTTPException) as falha:
        ServicoRelatorioAdministrativo(None).obter(1, SimpleNamespace(perfil="cliente"))
    assert falha.value.status_code == 403


@pytest.mark.parametrize("cid", ["0", "-1", "abc", "10000000000000"])
def test_identificador_invalido_nao_produz_relatorio(ambiente_d33, cid):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(RELATORIO + cid).status_code == 422
    assert http.get(RELATORIO + cid + "/csv").status_code == 422


def test_contratacao_inexistente_nao_cai_em_outro_registro(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: contrato(banco, os_id=3); banco.commit()
    entrar(http)
    for sufixo in ("", "/csv"):
        r = http.get(RELATORIO + "999" + sufixo)
        assert r.status_code == 404 and r.json()["detail"] == "contratacao_nao_encontrada"


def test_contratacao_sem_os_mantem_cadastro_sem_inventar_eventos(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: contrato(banco, com_os=False); banco.commit()
    antes = fotografia(engine); entrar(http); r = consultar(http)
    assert r["resumo"]["ordem_servico_id"] is None and r["linha_tempo"] == []
    assert r["cadastro"]["quantidade"] == 10 and r["cadastro"]["processo"] == "Usinagem CNC"
    assert r["resumo"]["financeiro_status"] == "sem_controle"
    assert any("Sem ordem" in a for a in r["avisos"])
    assert fotografia(engine) == antes


@pytest.mark.parametrize("estado", ["encerrada", "cancelada"])
def test_historico_anterior_nao_gera_divida_ou_evento_novo(ambiente_d33, estado):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, status=estado, ordem_status="concluida" if estado == "encerrada" else "cancelada")
        recebimento(banco, 1, "1250.00"); banco.commit()
    antes = fotografia(engine); entrar(http); r = consultar(http)
    assert r["resumo"]["pendencias"] == [] and r["linha_tempo"] == []
    assert r["recebimentos"][0]["valor"] == "1250.00"
    assert any("não criam nova pendência" in a for a in r["avisos"])
    linhas_csv(http)
    assert fotografia(engine) == antes


def test_estorno_correcao_repasse_encerramento_e_reabertura_reais(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Início do teste D34."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4); evento_financeiro(http, "encerrar", 5)
    antes = fotografia(engine); r = consultar(http)
    s = r["resumo"]
    assert s["contratacao_id"] == 1 and s["ordem_servico_id"] == 3 and s["financeiro_status"] == "encerrado"
    assert s["total_recebido"] == s["total_repassado"] == "12500.00"
    assert s["saldo_cliente"] == s["saldo_fornecedor"] == "0.00"
    assert r["recebimentos"][0]["status"] == "estornado" and r["recebimentos"][0]["valor"] == "1250.00"
    acoes = [e["acao"] for e in r["linha_tempo"] if e["origem"] == "financeiro"]
    assert acoes == ["iniciar", "recebimento", "estornar_recebimento", "recebimento", "repasse", "encerrar"]
    assert r["cadastro"]["encerrada_em"] is not None
    csv_itens = linhas_csv(http)
    assert len([l for l in csv_itens if l["Tipo de registro"] == "Evento"]) == 6
    assert any(l["Situação"] == "estornado" and l["Valor em reais"] == "1250,00" for l in csv_itens)
    assert fotografia(engine) == antes
    evento_financeiro(http, "reabrir", 6)
    novo = consultar(http)
    assert novo["resumo"]["financeiro_status"] == "aberto" and novo["resumo"]["ordem_status"] == "concluida"
    assert novo["linha_tempo"][-1]["acao"] == "reabrir"
    assert len(novo["recebimentos"]) == 2 and novo["cadastro"]["encerrada_em"] is None


def test_eventos_reais_intermediacao_retrabalho_e_entrega(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: contrato(banco, os_id=3); banco.commit()
    entrar(http); endpoint = "/api/v1/administracao/intermediacao/ordens/3"
    r = http.post(endpoint + "/iniciar", json={"registro_interno": "Início do ciclo D34."})
    assert r.status_code == 201, r.text
    versao = 1
    for acao in ["receber_material", "encaminhar_material", "solicitar_coleta", "receber_pecas", "iniciar_avaliacao",
                 "solicitar_retrabalho", "encaminhar_retrabalho", "solicitar_coleta", "receber_pecas",
                 "iniciar_avaliacao", "aprovar_pecas", "entregar_cliente"]:
        if acao == "solicitar_coleta":
            with sessoes() as banco:
                banco.add(EtapaProducao(ordem_servico_id=3, empresa_fornecedora_id=4, etapa="pronto_para_envio",
                    observacoes="Lote pronto para coleta D34.")); banco.commit()
        dados = {"acao": acao, "versao": versao, "registro_interno": "Registro D34 de " + acao,
                 "referencia": "COMPROVANTE-D34-" + str(versao)}
        if acao in {"receber_pecas", "aprovar_pecas", "entregar_cliente"}: dados["quantidade_conferida"] = 10
        if acao in {"solicitar_retrabalho", "aprovar_pecas"}: dados["parecer_tecnico"] = "Parecer técnico de conferência D34."
        resposta = http.post(endpoint + "/eventos", json=dados)
        assert resposta.status_code == 201, resposta.text
        versao += 1
    antes = fotografia(engine); rel = consultar(http)
    hist = [e for e in rel["linha_tempo"] if e["origem"] == "intermediacao"]
    assert len(hist) == 13 and any(e["acao"] == "solicitar_retrabalho" for e in hist)
    assert hist[-1]["acao"] == "entregar_cliente" and hist[-1]["quantidade"] == 10
    assert all(e["usuario_admin_id"] and e["responsavel"] for e in hist)
    assert rel["resumo"]["entrega_concluida"] is True
    assert len([e for e in rel["linha_tempo"] if e["origem"] == "producao"]) == 2
    assert fotografia(engine) == antes


def test_linha_tempo_ordena_fusos_versoes_e_ids_sem_misturar_origens(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3, ciclo="material_recebido", controle="aberto")
        ciclo = banco.query(CicloIntermediacao).one()
        banco.add(EtapaProducao(id=1, ordem_servico_id=3, empresa_fornecedora_id=4, etapa="em_usinagem", criada_em=datetime(2026, 10, 5, 13)))
        banco.add(EventoIntermediacao(id=1, ciclo_id=ciclo.id, versao=1, acao="iniciar_ciclo", status_resultante="aguardando_material",
            usuario_admin_id=1, administrador_nome="Administrador histórico", registro_interno="Primeiro evento real.",
            criado_em="2026-10-05T09:00:00-03:00"))
        banco.add(EventoIntermediacao(id=2, ciclo_id=ciclo.id, versao=2, acao="receber_material", status_anterior="aguardando_material",
            status_resultante="material_recebido", usuario_admin_id=1, administrador_nome="Administrador histórico",
            registro_interno="Segundo evento real.", criado_em="2026-10-05T12:00:00Z"))
        banco.add(EventoFinanceiro(id=1, contratacao_id=1, versao=1, acao="iniciar", usuario_admin_id=1,
            administrador_nome="Administrador histórico", registro_interno="Controle real.", criado_em="2026-10-05T13:00:00Z"))
        banco.commit()
    entrar(http); historico = consultar(http)["linha_tempo"]
    assert [(e["origem"], e["registro_id"]) for e in historico] == [("intermediacao", 1), ("intermediacao", 2), ("producao", 1), ("financeiro", 1)]
    assert historico[0]["data_utc"] == "2026-10-05T12:00:00.000000Z"
    assert historico == consultar(http)["linha_tempo"]


def test_dinheiro_exato_e_registros_de_outras_contratacoes_excluidos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3, valor="500.00", ordem_status="concluida", ciclo="entregue_cliente", controle="aberto")
        recebimento(banco, 1, "0.13"); recebimento(banco, 1, "0.29"); recebimento(banco, 1, "12.31", "cancelado")
        repasse(banco, 1, 11); repasse(banco, 1, 7); repasse(banco, 1, 6, "estornado")
        contrato(banco, 2, os_id=4, valor="100.00", controle="aberto")
        recebimento(banco, 2, "100.00")
        banco.add(EtapaProducao(ordem_servico_id=4, empresa_fornecedora_id=4, etapa="em_usinagem", observacoes="Registro exclusivo da OS #4."))
        banco.commit()
    entrar(http); r = consultar(http); s = r["resumo"]
    assert s["total_recebido"] == "0.42" and s["total_repassado"] == "0.18" and s["disponivel_repasse"] == "0.24"
    assert len(r["recebimentos"]) == 3 and len(r["repasses"]) == 3
    assert not any(e["registro_interno"] == "Registro exclusivo da OS #4." for e in r["linha_tempo"])
    linhas = linhas_csv(http)
    assert all(l["Contratação"] == "1" and l["OS"] == "3" for l in linhas)
    assert next(l for l in linhas if l["Campo / ação"] == "Recebido confirmado")["Valor em reais"] == "0,42"


@pytest.mark.parametrize("texto", ["=HYPERLINK(1)", "+COMANDO()", "-COMANDO()", "@SOMA(1)", " \t=1+2", "\ufeff =1+2", "\r\nvalor"])
def test_csv_neutraliza_formulas_e_controles_em_campos_livres(texto):
    assert celula_csv(texto) == "'" + texto


def test_csv_utf8_quotes_quebras_de_linha_e_campos_reais(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3, controle="aberto")
        banco.get(Empresa, 2).razao_social = "=HYPERLINK(\"destino\")"
        banco.get(ContratacaoServico, 1).observacoes = 'Observação; com "aspas"\nE segunda linha.'
        banco.add(EventoFinanceiro(contratacao_id=1, versao=1, acao="iniciar", usuario_admin_id=1,
            administrador_nome="+Administrador", registro_interno="\t=1+1", referencia=" @COMANDO()",
            criado_em=AGORA)); banco.commit()
    entrar(http); linhas = linhas_csv(http)
    assert next(l for l in linhas if l["Campo / ação"] == "Cliente")["Informação"] == "'=HYPERLINK(\"destino\")"
    assert next(l for l in linhas if l["Campo / ação"] == "Observações da contratação")["Informação"] == 'Observação; com "aspas"\nE segunda linha.'
    evento = next(l for l in linhas if l["Tipo de registro"] == "Evento")
    assert evento["Responsável"] == "'+Administrador" and evento["Registro interno"] == "'\t=1+1" and evento["Referência"] == "' @COMANDO()"


def test_csv_headers_sem_cache_nome_controlado_e_sem_endpoint_de_escrita(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco: contrato(banco, os_id=3); banco.commit()
    entrar(http); antes = fotografia(engine)
    r = http.get(RELATORIO + "1/csv")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"] == 'attachment; filename="MEC_SERVICOS_CONTRATACAO_1.csv"'
    for metodo in ("post", "put", "patch", "delete"):
        assert getattr(http, metodo)(RELATORIO + "1/csv").status_code == 405
    assert fotografia(engine) == antes


def test_todas_etapas_sem_limite_de_vinte_e_consulta_sem_escritas(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3)
        for indice in range(55):
            banco.add(EtapaProducao(ordem_servico_id=3, empresa_fornecedora_id=4, etapa="em_usinagem", observacoes="Etapa " + str(indice)))
        banco.commit()
    entrar(http); antes = fotografia(engine); comandos = []
    def capturar(_, __, comando, *args): comandos.append(comando.strip().split()[0].upper())
    event.listen(engine, "before_cursor_execute", capturar)
    try:
        r = consultar(http); linhas_csv(http)
    finally: event.remove(engine, "before_cursor_execute", capturar)
    assert len(r["linha_tempo"]) == 55
    assert set(comandos) <= {"BEGIN", "SELECT"} and comandos.count("BEGIN") == 2
    assert fotografia(engine) == antes


def test_leitura_coerente_quando_ha_gravacao_concorrente(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with engine.connect() as conexao: conexao.exec_driver_sql("PRAGMA journal_mode=WAL")
    with sessoes() as banco:
        contrato(banco, os_id=3, valor="500.00", controle="aberto"); recebimento(banco, 1, "100.00"); banco.commit()
    entrar(http); alterado = False
    def depois(_, __, comando, *args):
        nonlocal alterado
        if not alterado and comando.startswith("SELECT contratacoes_servico.id"):
            alterado = True
            with sqlite3.connect(engine.url.database) as externo:
                externo.execute("UPDATE pagamentos_contratacao SET valor=123.45 WHERE contratacao_id=1"); externo.commit()
    event.listen(engine, "after_cursor_execute", depois)
    try: antigo = consultar(http)
    finally: event.remove(engine, "after_cursor_execute", depois)
    assert alterado
    assert antigo["resumo"]["total_recebido"] == antigo["recebimentos"][0]["valor"] == "100.00"
    atual = consultar(http)
    assert atual["resumo"]["total_recebido"] == atual["recebimentos"][0]["valor"] == "123.45"


def test_divergencia_financeira_aparece_para_conferencia_sem_correcao(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3, valor="100.00", controle="aberto"); recebimento(banco, 1, "101.00"); banco.commit()
    entrar(http); antes = fotografia(engine); r = consultar(http)
    assert r["resumo"]["situacao"] == "verificar"
    assert any(p["codigo"] == "conferir_valores" for p in r["resumo"]["pendencias"])
    assert r["resumo"]["total_recebido"] == "101.00"
    assert fotografia(engine) == antes


def test_data_inconsistente_recusada_sem_alterar_registros(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, controle="aberto")
        banco.add(EventoFinanceiro(contratacao_id=1, versao=1, acao="iniciar", usuario_admin_id=1,
            administrador_nome="Admin", registro_interno="Registro real.", criado_em="data inválida")); banco.commit()
    entrar(http); antes = fotografia(engine)
    for sufixo in ("", "/csv"):
        r = http.get(RELATORIO + "1" + sufixo)
        assert r.status_code == 409 and r.json()["detail"] == "data_relatorio_inconsistente"
    assert fotografia(engine) == antes
