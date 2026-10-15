"""Comparações de fornecedores são administrativas; portais recebem apenas notas."""
import pytest
from test_financeiro_administrativo_d32 import contas_d32, ambiente_d32, entrar
from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, COOKIE_SESSAO
from backend.app.services.avaliacoes_perfis import ServicoAvaliacoesPerfis
from fastapi import HTTPException

pytestmark = pytest.mark.acesso_real


@pytest.mark.parametrize("perfil", ["cliente", "fornecedor"])
@pytest.mark.parametrize("caminho", [
    "/administracao/avaliacoes/ranking", "/portal-cliente/avaliacoes/ranking",
    "/portal-fornecedor/avaliacoes/ranking", "/fornecedores/ranking",
    "/empresas/4/reputacao", "/empresas/4/avaliacoes",
])
def test_ranking_e_medias_nao_sao_acessiveis_aos_portais(ambiente_d32, perfil, caminho):
    http, _, _ = ambiente_d32
    entrar(http, perfil)
    for origem in ("cliente", "admin"):
        r = http.get("/api/v1" + caminho, params={"origem": origem})
        assert r.status_code == 403, r.text
        assert not any(campo in r.json() for campo in ("itens", "media", "posicao", "total_fornecedores"))
    r = http.get(f"/api/v1/portal-{perfil}/avaliacoes/1")
    assert r.status_code == 200 and r.json()["item"]["contratacao_id"] == 1
    assert not any(campo in r.json()["item"] for campo in ("media", "posicao", "total_fornecedores"))


@pytest.mark.parametrize("perfil", ["cliente", "fornecedor"])
def test_servico_de_ranking_tambem_exige_admin(ambiente_d32, perfil):
    http, sessoes, app = ambiente_d32
    entrar(http, perfil)
    usuario = ArmazenamentoAcesso(app.state.caminho_acessos).obter_sessao(http.cookies.get(COOKIE_SESSAO))
    with sessoes() as banco:
        for origem in ("cliente", "admin"):
            with pytest.raises(HTTPException) as erro:
                ServicoAvaliacoesPerfis(banco, usuario).ranking(origem, 0, 20)
            assert erro.value.status_code == 403
            assert erro.value.detail == "ranking_exclusivo_da_administracao"
