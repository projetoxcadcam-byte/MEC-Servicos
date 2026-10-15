"""D33: painel real, consultas sem gravações, filas e dinheiro exato."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import shutil
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso
from backend.app.core.permissoes_acesso import autorizar_requisicao
from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.financeiro_administrativo import ControleFinanceiro, RepasseAdministrativo
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import criar_aplicacao

pytestmark = pytest.mark.acesso_real
PAINEL = "/api/v1/administracao/painel"
FINANCEIRO = "/api/v1/administracao/financeiro/contratacoes/1"
SENHA = "Senha-local-valida-D33!"
AGORA = "2026-10-05T12:00:00Z"


@pytest.fixture(scope="module")
def contas_d33(tmp_path_factory):
    arquivo = tmp_path_factory.mktemp("contas_d33") / "acesso.db"
    acesso = ArmazenamentoAcesso(arquivo); acesso.inicializar()
    for perfil, empresa in (("admin", None), ("cliente", 2), ("fornecedor", 4)):
        acesso.criar_usuario("Operador D33 " + perfil, perfil + "@d33.local", perfil, empresa, SENHA, deve_alterar_senha=False)
    return arquivo


@pytest.fixture()
def ambiente_d33(tmp_path, contas_d33, monkeypatch):
    monkeypatch.setenv("MEC_MODO_TESTE_LOCAL", "0")
    engine = create_engine("sqlite:///" + str(tmp_path / "negocio.db"), connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def chaves(conexao, _): conexao.execute("PRAGMA foreign_keys=ON")
    sessoes = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessoes() as banco:
        banco.add_all([Empresa(id=2, razao_social="Cliente Mecânico D5", documento="cliente-d33", tipo_empresa="cliente"),
                       Empresa(id=4, razao_social="Oficina Mecânica Alfa", documento="fornecedor-d33", tipo_empresa="fornecedor")])
        banco.add_all([ProcessoFabricacao(id=1, codigo="cnc-d33", nome="Usinagem CNC"), Material(id=1, codigo="al-d33", nome="Alumínio")])
        banco.commit()
    arquivo = tmp_path / "acessos.db"; shutil.copy2(contas_d33, arquivo)
    app = criar_aplicacao(); app.state.caminho_acessos = arquivo
    def banco_teste():
        with sessoes() as banco: yield banco
    app.dependency_overrides[obter_banco] = banco_teste
    assert autorizar_requisicao not in app.dependency_overrides
    http = TestClient(app)
    try: yield http, sessoes, engine
    finally: http.close(); app.dependency_overrides.clear(); engine.dispose()


def entrar(http, perfil="admin"):
    r = http.post("/api/v1/autenticacao/entrar", json={"email": perfil + "@d33.local", "senha": SENHA})
    assert r.status_code == 200, r.text
    http.headers["X-MEC-CSRF"] = r.json()["csrf"]


def contrato(banco, cid=1, *, valor="12500.00", com_os=True, os_id=None, status="ativa", ordem_status="aberta", ciclo=None, controle=None):
    banco.add(SolicitacaoServico(id=cid, empresa_cliente_id=2, processo_id=1, material_id=1, dimensao_x_maxima_mm=100,
        dimensao_y_maxima_mm=100, dimensao_z_maxima_mm=100, tolerancia_requerida_mm=Decimal("0.02"), quantidade=10, status="aberta")); banco.flush()
    banco.add(CotacaoFornecedor(id=cid, solicitacao_id=cid, empresa_fornecedora_id=4, valor_total=Decimal(valor), prazo_dias=15, validade_dias=10, status="aceita")); banco.flush()
    banco.add(ContratacaoServico(id=cid, solicitacao_id=cid, cotacao_id=cid, empresa_cliente_id=2, empresa_fornecedora_id=4,
        valor_total=Decimal(valor), prazo_dias=15, status=status)); banco.flush()
    oid = os_id if os_id is not None else 100 + cid
    if com_os:
        banco.add(OrdemServico(id=oid, contratacao_id=cid, solicitacao_id=cid, cotacao_id=cid, empresa_cliente_id=2,
            empresa_fornecedora_id=4, processo_id=1, material_id=1, quantidade=10, valor_total=Decimal(valor), prazo_dias=15, status=ordem_status)); banco.flush()
        if ciclo:
            banco.add(CicloIntermediacao(ordem_servico_id=oid, status=ciclo, versao=1, criado_em=AGORA, atualizado_em=AGORA)); banco.flush()
    if controle:
        banco.add(ControleFinanceiro(contratacao_id=cid, valor_contratado_centavos=int(Decimal(valor)*100), status=controle,
            versao=1, criado_em=AGORA, atualizado_em=AGORA)); banco.flush()
    return oid


def recebimento(banco, cid, valor, status="confirmado"):
    banco.add(PagamentoContratacao(contratacao_id=cid, empresa_cliente_id=2, empresa_fornecedora_id=4,
        valor=Decimal(valor), forma_pagamento="pix", status=status))


def repasse(banco, cid, centavos, status="confirmado"):
    banco.add(RepasseAdministrativo(contratacao_id=cid, valor_centavos=centavos, forma_pagamento="pix", status=status, registrado_em=AGORA))


def consultar(http, **params):
    r = http.get(PAINEL, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def evento_financeiro(http, acao, versao, **campos):
    dados = {"acao": acao, "versao": versao, "chave_operacao": str(uuid4()), "registro_interno": "Simulação D33; não há operação bancária."}
    if acao in {"recebimento", "repasse"}:
        dados.update(valor="12500.00", forma_pagamento="pix", referencia="TESTE-D33-" + str(uuid4()))
    elif acao.startswith("estornar"):
        dados.update(referencia="ESTORNO-D33-" + str(uuid4()))
    r = http.post(FINANCEIRO + "/eventos", json={**dados, **campos})
    assert r.status_code == 201, r.text
    return r.json()


def fotografia(engine):
    with engine.connect() as banco:
        return {t.name: banco.execute(select(t).order_by(*t.primary_key.columns)).all() for t in Base.metadata.sorted_tables}


def test_sessao_e_perfil_exigidos_sem_vazar_indicadores(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: contrato(banco); banco.commit()
    assert http.get(PAINEL).status_code == 401
    for perfil in ("cliente", "fornecedor"):
        entrar(http, perfil)
        r = http.get(PAINEL, params={"empresa_cliente_id": 2, "perfil": "admin"})
        assert r.status_code == 403 and "indicadores" not in r.text and "Oficina" not in r.text
    entrar(http)
    assert consultar(http)["indicadores"]["total_contratacoes"] == 1


def test_painel_vazio_sem_numeros_ficticios(ambiente_d33):
    http, _, _ = ambiente_d33; entrar(http)
    dados = consultar(http)
    assert dados["itens"] == [] and dados["total"] == 0
    assert all(v in (0, "0.00") for v in dados["indicadores"].values())


def test_fluxo_real_recebimento_estorno_repasse_e_encerramento(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: contrato(banco, os_id=3, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno": "Início da simulação D33."}).status_code == 201
    errado = evento_financeiro(http, "recebimento", 1, valor="1250.00")
    evento_financeiro(http, "estornar_recebimento", 2, movimento_id=errado["recebimentos"][0]["id"])
    evento_financeiro(http, "recebimento", 3); evento_financeiro(http, "repasse", 4)
    antes = consultar(http)
    assert antes["indicadores"]["pendencias_financeiras"] == 1
    assert [p["codigo"] for p in antes["itens"][0]["pendencias"]] == ["encerrar_financeiro"]
    evento_financeiro(http, "encerrar", 5)
    dados = consultar(http, filtro="concluidas", busca="OS #3")
    assert dados["total"] == 1
    item = dados["itens"][0]
    assert item["ordem_servico_id"] == 3 and item["contratacao_id"] == 1
    assert item["situacao"] == "concluida" and item["financeiro_status"] == "encerrado" and item["pendencias"] == []
    assert item["total_recebido"] == item["total_repassado"] == "12500.00"
    assert item["saldo_cliente"] == item["saldo_fornecedor"] == "0.00"
    i = dados["indicadores"]
    assert i["financeiros_encerrados"] == 1 and i["pendencias_financeiras"] == 0
    assert i["recebimentos_confirmados"] == i["repasses_confirmados"] == "12500.00"
    assert i["saldo_clientes_controles_abertos"] == i["saldo_fornecedores_controles_abertos"] == i["disponivel_repasses"] == "0.00"


def test_consultar_e_filtrar_nao_altera_negocio_nem_inicia_controles(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, com_os=False); contrato(banco, 2, ciclo="aguardando_material"); banco.commit()
    antes = fotografia(engine); entrar(http)
    for filtro in ("todas", "operacionais", "financeiras", "concluidas", "canceladas", "verificar"):
        consultar(http, filtro=filtro)
    consultar(http, busca="Oficina", deslocamento=1, limite=1)
    assert fotografia(engine) == antes


def test_indicadores_abrangem_mais_de_uma_pagina_e_independem_da_busca(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 26): contrato(banco, cid, com_os=False)
        banco.commit()
    entrar(http)
    primeira = consultar(http); ultima = consultar(http, deslocamento=20)
    busca = consultar(http, busca="contratação #1")
    assert primeira["total"] == ultima["total"] == 25
    assert len(primeira["itens"]) == 20 and len(ultima["itens"]) == 5
    assert primeira["itens"][0]["contratacao_id"] == 25 and ultima["itens"][-1]["contratacao_id"] == 1
    assert primeira["indicadores"] == ultima["indicadores"] == busca["indicadores"]
    assert busca["total"] == 1 and busca["itens"][0]["contratacao_id"] == 1
    assert primeira["indicadores"]["acompanhamento_operacional"] == 25
    assert primeira["indicadores"]["pendencias_financeiras"] == 25
    assert primeira["indicadores"]["controles_abertos"] == 0


def test_consulta_em_lote_sem_select_por_contratacao(ambiente_d33):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        for cid in range(1, 26): contrato(banco, cid, ciclo="material_recebido")
        banco.commit()
    entrar(http); comandos = []
    def capturar(_, __, comando, *args): comandos.append(comando)
    event.listen(engine, "before_cursor_execute", capturar)
    try: consultar(http)
    finally: event.remove(engine, "before_cursor_execute", capturar)
    assert len(comandos) == 1 and comandos[0].lstrip().upper().startswith("SELECT")


def test_somas_exatas_sem_multiplicacao_e_sem_movimentos_estornados(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, valor="500.00", ordem_status="concluida", ciclo="entregue_cliente", controle="aberto")
        recebimento(banco, 1, "1.13"); recebimento(banco, 1, "2.29"); recebimento(banco, 1, "99.00", "cancelado")
        repasse(banco, 1, 13); repasse(banco, 1, 29); repasse(banco, 1, 9900, "estornado"); banco.commit()
    entrar(http); dados = consultar(http); item = dados["itens"][0]; i = dados["indicadores"]
    assert item["total_recebido"] == i["recebimentos_confirmados"] == "3.42"
    assert item["total_repassado"] == i["repasses_confirmados"] == "0.42"
    assert item["saldo_cliente"] == i["saldo_clientes_controles_abertos"] == "496.58"
    assert item["saldo_fornecedor"] == i["saldo_fornecedores_controles_abertos"] == "499.58"
    assert item["disponivel_repasse"] == i["disponivel_repasses"] == "3.00"


def test_encerrados_e_cancelados_anteriores_nao_geram_pendencias_d32(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, status="encerrada", ordem_status="concluida")
        contrato(banco, 2, status="cancelada", ordem_status="cancelada")
        recebimento(banco, 1, "12500.00"); banco.commit()
    entrar(http); dados = consultar(http)
    assert dados["indicadores"]["contratacoes_concluidas"] == 1
    assert dados["indicadores"]["contratacoes_canceladas"] == 1
    assert dados["indicadores"]["financeiros_encerrados"] == 0
    assert dados["indicadores"]["controles_abertos"] == dados["indicadores"]["pendencias_financeiras"] == 0
    assert dados["indicadores"]["saldo_fornecedores_controles_abertos"] == "0.00"
    assert all(i["financeiro_status"] == "sem_controle" and not i["pendencias"] for i in dados["itens"])


@pytest.mark.parametrize("ciclo,codigo",[(None,"iniciar_intermediacao"),("aguardando_material","receber_material"),
    ("material_recebido","encaminhar_material"),("coleta_solicitada","receber_pecas"),
    ("pecas_recebidas","iniciar_avaliacao"),("em_avaliacao","avaliar_pecas"),
    ("retrabalho","encaminhar_retrabalho"),("aprovado_para_entrega","entregar_cliente")])
def test_proximo_passo_operacional_derivado_do_ciclo(ambiente_d33, ciclo, codigo):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: contrato(banco, ciclo=ciclo); banco.commit()
    entrar(http); dados = consultar(http, filtro="operacionais")
    assert dados["total"] == 1
    assert [p["codigo"] for p in dados["itens"][0]["pendencias"] if p["area"] == "operacional"] == [codigo]


def test_coleta_exige_ultima_producao_pronta_e_ainda_nao_utilizada(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        oid = contrato(banco, ciclo="retrabalho_encaminhado", ordem_status="em_execucao")
        ciclo = banco.scalar(select(CicloIntermediacao)); ciclo.ultima_etapa_coleta_id = 5
        banco.add(EtapaProducao(id=5, ordem_servico_id=oid, empresa_fornecedora_id=4, etapa="pronto_para_envio")); banco.commit()
    entrar(http)
    def operacional(): return [p["codigo"] for p in consultar(http)["itens"][0]["pendencias"] if p["area"] == "operacional"]
    assert operacional() == ["acompanhar_producao"]
    with sessoes() as banco:
        banco.add(EtapaProducao(id=6, ordem_servico_id=oid, empresa_fornecedora_id=4, etapa="pronto_para_envio")); banco.commit()
    assert operacional() == ["solicitar_coleta"]
    with sessoes() as banco:
        banco.add(EtapaProducao(id=7, ordem_servico_id=oid, empresa_fornecedora_id=4, etapa="em_usinagem")); banco.commit()
    assert operacional() == ["acompanhar_producao"]


def test_repasse_disponivel_exige_entrega_d31_e_controle_aberto(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, ciclo="aprovado_para_entrega", ordem_status="em_execucao", controle="aberto")
        recebimento(banco, 1, "12500.00"); banco.commit()
    entrar(http); dados = consultar(http)
    assert dados["indicadores"]["disponivel_repasses"] == "0.00"
    assert "repasse_aguarda_entrega" in [p["codigo"] for p in dados["itens"][0]["pendencias"]]


@pytest.mark.parametrize("tipo,codigo",[("valor","conferir_valor_contratado"),("cobertura","conferir_valores"),
    ("os_anterior","conferir_ordem_anterior"),("cancelamento","conferir_cancelamento"),("estado","conferir_encerramento")])
def test_divergencias_aparecem_para_conferencia_sem_correcao_automatica(ambiente_d33, tipo, codigo):
    http, sessoes, engine = ambiente_d33
    with sessoes() as banco:
        contrato(banco, ciclo=None if tipo == "os_anterior" else "entregue_cliente", ordem_status="concluida", controle="aberto")
        if tipo == "valor": banco.get(ControleFinanceiro, 1).valor_contratado_centavos = 1250001
        elif tipo == "cobertura": repasse(banco, 1, 1)
        elif tipo == "cancelamento":
            banco.get(OrdemServico, 101).status = "cancelada"
            banco.scalar(select(CicloIntermediacao)).status = "cancelado"
        elif tipo == "estado": banco.get(ContratacaoServico, 1).status = "encerrada"
        banco.commit()
    antes = fotografia(engine); entrar(http); dados = consultar(http, filtro="verificar")
    assert dados["total"] == 1 and dados["indicadores"]["para_conferencia"] == 1
    assert codigo in [p["codigo"] for p in dados["itens"][0]["pendencias"]]
    assert dados["indicadores"]["disponivel_repasses"] == "0.00" and fotografia(engine) == antes


def test_busca_por_id_exato_os_e_nomes_com_ou_sem_acentos(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco:
        contrato(banco, os_id=3); contrato(banco, 11, os_id=13); banco.commit()
    entrar(http)
    assert consultar(http, busca="contratacao #1")["total"] == 1
    assert consultar(http, busca="OS #3")["itens"][0]["contratacao_id"] == 1
    assert consultar(http, busca="#1")["total"] == 1
    assert consultar(http, busca="mecanica alfa")["total"] == 2
    assert consultar(http, busca="1 OR 1=1")["total"] == 0


@pytest.mark.parametrize("params",[{"filtro":"inventado"},{"limite":101},{"limite":0},{"deslocamento":-1},{"busca":"a"*121}])
def test_filtros_e_paginacao_invalidos_rejeitados(ambiente_d33, params):
    http, _, _ = ambiente_d33; entrar(http)
    assert http.get(PAINEL, params=params).status_code == 422


def test_reabertura_real_recoloca_financeiro_na_fila_sem_reabrir_os(ambiente_d33):
    http, sessoes, _ = ambiente_d33
    with sessoes() as banco: contrato(banco, ordem_status="concluida", ciclo="entregue_cliente"); banco.commit()
    entrar(http)
    assert http.post(FINANCEIRO + "/iniciar", json={"registro_interno":"Início da simulação D33."}).status_code == 201
    evento_financeiro(http, "recebimento", 1); evento_financeiro(http, "repasse", 2); evento_financeiro(http, "encerrar", 3)
    assert consultar(http, filtro="financeiras")["total"] == 0
    evento_financeiro(http, "reabrir", 4)
    dados = consultar(http, filtro="financeiras"); item = dados["itens"][0]
    assert dados["total"] == 1 and item["contratacao_status"] == "ativa" and item["ordem_status"] == "concluida"
    assert item["total_recebido"] == item["total_repassado"] == "12500.00"
    assert [p["codigo"] for p in item["pendencias"]] == ["encerrar_financeiro"]
