"""D46 com contas reais: entrega, duas origens, comentários e confirmação concorrente."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from test_financeiro_administrativo_d32 import contas_d32, ambiente_d32, entrar, SENHA

from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso
from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.avaliacao_perfil import AutoriaAvaliacaoCliente, AvaliacaoAdministrativa
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.notificacao import NotificacaoPerfil
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico

pytestmark = pytest.mark.acesso_real
BASE = "/api/v1"
COMENTARIO = "Reservado D46: privado@interno.local 11999999999"


def rota(perfil):
    return BASE + ("/administracao" if perfil == "admin" else "/portal-" + perfil) + "/avaliacoes"


def detalhe(http, perfil="cliente", cid=1):
    r = http.get(rota(perfil) + f"/{cid}")
    assert r.status_code == 200, r.text
    return r.json()["item"]


def corpo(http, perfil="cliente", cid=1, **campos):
    return {"nota": 5, "comentario": COMENTARIO, "versao": detalhe(http, perfil, cid)["versao"],
            "chave_operacao": str(uuid4()), **campos}


def registrar(http, perfil="cliente", cid=1, dados=None, **campos):
    r = http.post(rota(perfil) + f"/{cid}", json=dados or corpo(http, perfil, cid, **campos))
    assert r.status_code == 201, r.text
    return r.json()


def quantidade(sessoes, modelo):
    with sessoes() as b:
        return b.scalar(select(func.count()).select_from(modelo))


def test_duas_notas_independentes_e_medias_separadas(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    entrar(http, "cliente"); cliente = registrar(http)
    assert cliente["item"]["cliente"]["nota"] == 5
    assert cliente["item"]["admin"] is None
    assert cliente["item"]["pode_avaliar"] is False
    entrar(http, "admin"); admin = registrar(http, "admin", nota=3, comentario="Parecer interno ADM")
    assert admin["item"]["cliente"]["comentario"] == COMENTARIO
    assert admin["item"]["admin"]["nota"] == 3
    for origem, esperado in (("cliente", "5.00"), ("admin", "3.00")):
        r = http.get(rota("admin") + "/ranking", params={"origem": origem}).json()
        item = next(i for i in r["itens"] if i["empresa_id"] == 4)
        assert item["media"] == esperado and item["quantidade"] == 1 and item["posicao"] == 1
    assert quantidade(sessoes, AvaliacaoOficina) == quantidade(sessoes, AvaliacaoAdministrativa) == 1
    assert quantidade(sessoes, AutoriaAvaliacaoCliente) == 1


def test_anonimo_csrf_perfil_e_contexto_antigo(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    for p in ("cliente", "admin", "fornecedor"):
        assert http.get(rota(p)).status_code == 401
    entrar(http, "cliente"); d = corpo(http)
    assert http.post(rota("cliente") + "/1", json=d, headers={"X-MEC-CSRF": "errado"}).status_code == 403
    assert http.get(rota("admin")).status_code == 403
    assert http.get(rota("fornecedor")).status_code == 403
    assert http.get(rota("cliente"), headers={"X-MEC-AVALIACOES-CONTEXTO": "outra-aba"}).status_code == 409
    assert http.post(rota("cliente") + "/1", json=d, headers={"X-MEC-AVALIACOES-CONTEXTO": "outra-aba"}).status_code == 409
    assert quantidade(sessoes, AvaliacaoOficina) == 0
    entrar(http, "admin")
    assert http.get(rota("cliente")).status_code == 403
    assert http.post(rota("cliente") + "/1", json=d).status_code == 403


@pytest.mark.parametrize("extra", [{"nota": 0}, {"nota": 6}, {"nota": True}, {"nota": 2.5}, {"nota": "5"},
    {"comentario": "x" * 2001}, {"comentario": 123}, {"usuario_id": 99}, {"empresa_cliente_id": 6},
    {"empresa_fornecedora_id": 8}, {"perfil": "admin"}, {"versao": "errada"}, {"chave_operacao": "errada"}])
def test_corpo_estrito_e_identidade_do_servidor(ambiente_d32, extra):
    http, sessoes, _ = ambiente_d32
    entrar(http, "cliente")
    r = http.post(rota("cliente") + "/1", json={**corpo(http), **extra})
    assert r.status_code in (403, 422), r.text
    assert quantidade(sessoes, AvaliacaoOficina) == 0


@pytest.mark.parametrize("perfil", ["cliente", "fornecedor"])
def test_empresa_alheia_nao_lista_obtem_ou_avalia(ambiente_d32, perfil):
    http, sessoes, _ = ambiente_d32
    entrar(http, perfil)
    d = http.get(rota(perfil)).json()
    assert [i["contratacao_id"] for i in d["itens"]] == [1]
    assert http.get(rota(perfil) + "/2").status_code == 404
    assert http.get(rota(perfil), params={"contratacao_id": 2}).json()["itens"] == []
    r = http.post(rota(perfil) + "/2", json={"nota": 5, "versao": "a"*64, "chave_operacao": str(uuid4())})
    assert r.status_code == (404 if perfil == "cliente" else 405)
    assert http.get(rota(perfil), params={"empresa_id": 6}).status_code == 403
    assert quantidade(sessoes, AvaliacaoOficina) == 0


@pytest.mark.parametrize("campo,estado,motivo", [("ordem", "em_execucao", "aguardando_conclusao_da_ordem"),
    ("ordem", "cancelada", "aguardando_conclusao_da_ordem"), ("contrato", "cancelada", "contratacao_cancelada"),
    ("ciclo", "aprovado_para_entrega", "aguardando_entrega_ao_cliente"), ("ciclo", "retrabalho", "aguardando_entrega_ao_cliente"),
    ("ciclo", "cancelado", "aguardando_entrega_ao_cliente")])
def test_entrega_e_conclusao_obrigatorias(ambiente_d32, campo, estado, motivo):
    http, sessoes, _ = ambiente_d32
    with sessoes() as b:
        item = b.get(OrdemServico, 1) if campo == "ordem" else b.get(ContratacaoServico, 1) if campo == "contrato" else b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == 1))
        item.status = estado; b.commit()
    for p in ("cliente", "admin"):
        entrar(http, p); d = detalhe(http, p)
        assert not d["pode_avaliar"] and d["motivo_disponibilidade"] == motivo
        assert http.get(rota(p), params={"situacao": "disponiveis"}).json()["total"] == (1 if p == "admin" else 0)
        assert http.post(rota(p) + "/1", json=corpo(http, p)).status_code == 409
    assert quantidade(sessoes, AvaliacaoOficina) == quantidade(sessoes, AvaliacaoAdministrativa) == 0


def test_financeiro_aberto_nao_impede_nota_apos_entrega(ambiente_d32):
    http, _, _ = ambiente_d32
    entrar(http, "cliente")
    assert detalhe(http)["status_contratacao"] == "ativa"
    assert registrar(http)["item"]["cliente"]["nota"] == 5


def test_fluxo_antigo_exige_os_concluida_e_contrato_encerrado(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    with sessoes() as b:
        b.delete(b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == 1))); b.commit()
    entrar(http, "cliente")
    assert detalhe(http)["motivo_disponibilidade"] == "aguardando_entrega_ao_cliente"
    with sessoes() as b:
        b.get(ContratacaoServico, 1).status = "encerrada"; b.commit()
    assert registrar(http)["item"]["cliente"]["nota"] == 5


def test_versao_antiga_recusa_sem_gravar_avisos(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    entrar(http, "cliente"); dados = corpo(http)
    with sessoes() as b:
        b.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == 1)).versao += 1; b.commit()
    assert http.post(rota("cliente") + "/1", json=dados).status_code == 409
    assert quantidade(sessoes, AvaliacaoOficina) == quantidade(sessoes, NotificacaoPerfil) == 0


def test_repeticao_segura_e_chave_divergente(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    entrar(http, "cliente"); dados = corpo(http)
    a = registrar(http, dados=dados); b = registrar(http, dados=dados)
    assert a["item"] == b["item"] and not a["repetida"] and b["repetida"]
    assert quantidade(sessoes, AvaliacaoOficina) == 1
    assert quantidade(sessoes, NotificacaoPerfil) == 2
    assert http.post(rota("cliente") + "/1", json={**dados, "nota": 3}).status_code == 409
    assert http.post(rota("cliente") + "/1", json={**dados, "chave_operacao": str(uuid4())}).status_code == 409


def test_privacidade_autor_admin_fornecedor_e_notificacoes(ambiente_d32):
    http, sessoes, app = ambiente_d32
    entrar(http, "cliente"); registrar(http)
    entrar(http, "admin"); registrar(http, "admin", nota=4, comentario="SEGREDO-ADM")
    d = detalhe(http, "admin")
    assert d["cliente"]["autor"]["usuario_id"] == 2 and d["admin"]["autor"]["usuario_id"] == 1
    entrar(http, "cliente"); d = detalhe(http)
    assert d["cliente"]["comentario"] == COMENTARIO
    assert "comentario" not in d["admin"] and "autor" not in d["admin"]
    acesso = ArmazenamentoAcesso(app.state.caminho_acessos)
    acesso.criar_usuario("Outro cliente", "outro@d46.local", "cliente", 2, SENHA, deve_alterar_senha=False)
    r = http.post(BASE + "/autenticacao/entrar", json={"email": "outro@d46.local", "senha": SENHA})
    assert r.status_code == 200
    d = detalhe(http)
    assert "comentario" not in d["cliente"]
    entrar(http, "fornecedor"); d = detalhe(http, "fornecedor")
    assert d["cliente"]["nota"] == 5 and d["admin"]["nota"] == 4 and not d["pode_avaliar"]
    bruto = str(d) + str(http.get(rota("fornecedor")).json())
    assert all(x not in bruto for x in ("comentario", "autor", "chave_operacao", "SEGREDO", COMENTARIO, "Empresa secreta"))
    for p, destino in (("cliente", "/cliente/avaliacoes?contratacao=1"), ("fornecedor", "/fornecedor/avaliacoes?contratacao=1"), ("admin", "/admin/avaliacoes?contratacao=1")):
        entrar(http, p); r = http.get(BASE + "/notificacoes").json()
        assert all(n["destino"] == destino for n in r["itens"])
        assert len(r["itens"]) == (2 if p == "fornecedor" else 1)
        assert all(x not in str(r) for x in ("SEGREDO", COMENTARIO, "11999999999", "Operador reservado"))


@pytest.mark.parametrize("origens", [("cliente", "cliente"), ("admin", "admin"), ("cliente", "admin")])
def test_concorrencia_uma_nota_por_origem(ambiente_d32, origens):
    _, sessoes, app = ambiente_d32
    clientes = [TestClient(app), TestClient(app)]
    for c, p in zip(clientes, origens): entrar(c, p)
    dados = [corpo(c, p) for c, p in zip(clientes, origens)]
    barreira = Barrier(2)
    def enviar(i):
        barreira.wait()
        return clientes[i].post(rota(origens[i]) + "/1", json=dados[i]).status_code
    try:
        with ThreadPoolExecutor(max_workers=2) as pool: respostas = list(pool.map(enviar, range(2)))
    finally:
        for c in clientes: c.close()
    assert sorted(respostas) == ([201, 409] if origens[0] == origens[1] else [201, 201])
    assert quantidade(sessoes, AvaliacaoOficina) == (1 if "cliente" in origens else 0)
    assert quantidade(sessoes, AvaliacaoAdministrativa) == (1 if "admin" in origens else 0)


def test_falha_desfaz_nota_autoria_e_avisos(ambiente_d32):
    http, sessoes, app = ambiente_d32
    entrar(http, "cliente"); dados = corpo(http)
    def falhar(*_): raise RuntimeError("falha após captura")
    event.listen(AutoriaAvaliacaoCliente, "after_insert", falhar)
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            entrar(c, "cliente")
            assert c.post(rota("cliente") + "/1", json=dados).status_code == 500
    finally:
        event.remove(AutoriaAvaliacaoCliente, "after_insert", falhar)
    assert quantidade(sessoes, AvaliacaoOficina) == quantidade(sessoes, AutoriaAvaliacaoCliente) == quantidade(sessoes, NotificacaoPerfil) == 0
    assert not registrar(http, dados=dados)["repetida"]


def test_historico_cliente_preservado_sem_autoria_inventada(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    with sessoes() as b:
        b.add(AvaliacaoOficina(contratacao_id=1, ordem_servico_id=1, empresa_cliente_id=2,
            empresa_fornecedora_id=4, nota=2, comentario=COMENTARIO, criada_em=datetime(2026, 10, 1, tzinfo=timezone.utc))); b.commit()
    entrar(http, "cliente"); d = detalhe(http)
    assert d["cliente"]["historica"] and d["cliente"]["nota"] == 2 and "comentario" not in d["cliente"]
    assert not d["pode_avaliar"] and quantidade(sessoes, AutoriaAvaliacaoCliente) == 0
    entrar(http, "admin"); d = detalhe(http, "admin")
    assert d["cliente"]["autor"] is None and d["cliente"]["comentario"] == COMENTARIO
    assert registrar(http, "admin")["item"]["cliente"]["nota"] == 2
    assert http.get(rota("admin") + "/ranking", params={"origem": "cliente"}).json()["itens"][0]["media"] == "2.00"


def test_paginacao_ranking_sem_multiplicar_avaliacoes(ambiente_d32):
    http, sessoes, _ = ambiente_d32
    with sessoes() as b:
        # Várias contratações do mesmo fornecedor, com ambas as notas: a média
        # não pode sofrer uma junção N x M entre as origens.
        for cid, nota in ((1, 5), (3, 3), (4, 4)):
            if cid != 1:
                b.add(SolicitacaoServico(id=cid, empresa_cliente_id=2, processo_id=1, material_id=1,
                    dimensao_x_maxima_mm=10, dimensao_y_maxima_mm=10, dimensao_z_maxima_mm=10,
                    tolerancia_requerida_mm=Decimal("0.1"), quantidade=1, status="aberta")); b.flush()
                b.add(CotacaoFornecedor(id=cid, solicitacao_id=cid, empresa_fornecedora_id=4,
                    valor_total=100, prazo_dias=1, validade_dias=1, status="aceita")); b.flush()
                b.add(ContratacaoServico(id=cid, solicitacao_id=cid, cotacao_id=cid, empresa_cliente_id=2,
                    empresa_fornecedora_id=4, valor_total=100, prazo_dias=1, status="encerrada")); b.flush()
                b.add(OrdemServico(id=cid, contratacao_id=cid, solicitacao_id=cid, cotacao_id=cid,
                    empresa_cliente_id=2, empresa_fornecedora_id=4, processo_id=1, material_id=1,
                    quantidade=1, valor_total=100, prazo_dias=1, status="concluida")); b.flush()
            b.add(AvaliacaoOficina(contratacao_id=cid, ordem_servico_id=cid, empresa_cliente_id=2,
                empresa_fornecedora_id=4, nota=nota))
            b.add(AvaliacaoAdministrativa(contratacao_id=cid, ordem_servico_id=cid, empresa_cliente_id=2,
                empresa_fornecedora_id=4, nota=2, criada_em="2026-10-08T12:00:00+00:00", usuario_id=1,
                nome_autor="Admin", chave_operacao=str(uuid4()), resumo_operacao="a"*64))
        b.add(Empresa(id=9, razao_social="Ambos sem notas", documento="ambos-d46", tipo_empresa="ambos")); b.commit()
    entrar(http, "admin")
    for origem, media in (("cliente", "4.00"), ("admin", "2.00")):
        r = http.get(rota("admin") + "/ranking", params={"origem": origem, "limite": 1}).json()
        assert r["total"] == 3 and len(r["itens"]) == 1
        assert r["itens"][0]["quantidade"] == 3 and r["itens"][0]["media"] == media
        assert http.get(rota("admin") + "/ranking", params={"origem": origem, "inicio": 1, "limite": 1}).json()["itens"][0]["media"] is None
    entrar(http, "cliente")
    d = http.get(rota("cliente"), params={"limite": 1}).json()
    assert d["total"] == 3 and len(d["itens"]) == 1
    assert detalhe(http, cid=1)["contratacao_id"] == 1
    entrar(http, "fornecedor")
    r = http.get(rota("fornecedor") + "/ranking")
    assert r.status_code == 403
    d = detalhe(http, "fornecedor")
    assert d["cliente"]["nota"] == 5
    assert all(x not in str(d) for x in ("media", "posicao", "total_fornecedores", "Empresa secreta", "Ambos sem notas", "razao_social"))


@pytest.mark.parametrize("params", [{"situacao": "invalida"}, {"limite": 0}, {"limite": 101}, {"inicio": -1}, {"contratacao_id": 0}, {"ordem_servico_id": -1}])
def test_filtros_invalidos(ambiente_d32, params):
    http, _, _ = ambiente_d32
    entrar(http, "cliente")
    assert http.get(rota("cliente"), params=params).status_code == 422
