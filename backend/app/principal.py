from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError

from backend.app.api.rotas.avaliacoes_perfis import roteador as roteador_avaliacoes_perfis
from backend.app.api.rotas.painel_perfis import roteador as roteador_painel_perfis
from backend.app.api.rotas.cotacoes_cliente import roteador as roteador_cotacoes_cliente
from backend.app.api.rotas.formacao_preco import roteador as roteador_formacao_preco
from backend.app.api.rotas.despesa_administracao import roteador as roteador_despesas_administracao
from backend.app.api.rotas.resultado_administracao import roteador as roteador_resultado_administracao
from backend.app.api.rotas.notificacoes import roteador as roteador_notificacoes
from backend.app.services.eventos_notificacoes import instalar_captura
from backend.app.api.rotas.contratacao_admin import roteador as roteador_contratacao_admin
from backend.app.api.rotas.comercial_admin import roteador as roteador_comercial
from backend.app.api.rotas.documentacao_cotacao import roteador as roteador_documentacao
from backend.app.api.rotas.preparacao_pdf import roteador as roteador_preparacao_pdf
from backend.app.api.rotas.empresas_operacoes import roteador as roteador_empresas_operacoes
from backend.app.api.rotas.autenticacao import roteador as roteador_autenticacao
from backend.app.api.rotas.intermediacao import roteador as roteador_intermediacao
from backend.app.api.rotas.financeiro_administrativo import roteador as roteador_financeiro
from backend.app.api.rotas.relatorio_administrativo import roteador as roteador_relatorio
from backend.app.api.rotas.resumo_gerencial import roteador as roteador_gerencial
from backend.app.api.rotas.comparativo_gerencial import roteador as roteador_comparativo
from backend.app.api.rotas.extrato_financeiro import roteador as roteador_extrato
from backend.app.api.rotas.central_pendencias import roteador as roteador_pendencias
from backend.app.api.rotas.relatorio_empresas import roteador as roteador_empresas
from backend.app.api.rotas.relatorio_periodo import roteador as roteador_periodo
from backend.app.api.rotas.painel_administrativo import roteador as roteador_painel
from backend.app.core.permissoes_acesso import autorizar_requisicao
from backend.app.core.privacidade_acesso import PrivacidadePortais, erro_validacao_acesso

from backend.app.api.roteador import roteador_api
from backend.app.core.configuracao import configuracoes
from backend.app.database.inicializacao import inicializar_banco


instalar_captura()


@asynccontextmanager
async def ciclo_vida(_: FastAPI) -> AsyncIterator[None]:
    inicializar_banco()
    from backend.app.database.sessao import SessaoLocal
    from backend.app.models.formacao_preco import ConfiguracaoPreco
    from backend.app.services.formacao_preco import REVISION
    with SessaoLocal() as banco:
        cfg=banco.get(ConfiguracaoPreco,1)
        try:valida=cfg is not None and cfg.revision==REVISION and len(bytes.fromhex(cfg.segredo_verificacao))==32
        except ValueError:valida=False
        if not valida:
            raise RuntimeError('Conclua a instalação D60 antes de iniciar este backend.')
    from backend.app.models.despesa_administracao import ConfiguracaoDespesas
    from backend.app.services.despesa_administracao import REVISION as REVISION_D61
    with SessaoLocal() as banco:
        cfg=banco.get(ConfiguracaoDespesas,1)
        if cfg is None or cfg.revision!=REVISION_D61:
            raise RuntimeError("Conclua a instalação D61 antes de iniciar este backend.")
    yield


def criar_aplicacao() -> FastAPI:
    aplicacao = FastAPI(
        title=configuracoes.nome_aplicacao,
        version=configuracoes.versao_aplicacao,
        debug=False,
        lifespan=ciclo_vida,
    )

    aplicacao.include_router(
        roteador_api,
        prefix=configuracoes.prefixo_api,
        dependencies=[Depends(autorizar_requisicao)],
    )
    aplicacao.include_router(roteador_intermediacao, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_financeiro, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_painel, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_relatorio, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_periodo, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_empresas, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_pendencias, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_gerencial, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_comparativo, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_extrato, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_documentacao, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_preparacao_pdf, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_empresas_operacoes, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_comercial, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_contratacao_admin, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_notificacoes, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_avaliacoes_perfis, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_painel_perfis, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_cotacoes_cliente, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_formacao_preco, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_resultado_administracao, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.include_router(roteador_despesas_administracao, prefix=configuracoes.prefixo_api, dependencies=[Depends(autorizar_requisicao)])
    aplicacao.state.prefixo_api_acesso = configuracoes.prefixo_api
    aplicacao.include_router(roteador_autenticacao, prefix=configuracoes.prefixo_api)
    aplicacao.add_middleware(PrivacidadePortais)
    aplicacao.add_exception_handler(RequestValidationError, erro_validacao_acesso)

    @aplicacao.get("/", tags=["sistema"])
    async def raiz() -> dict[str, str]:
        return {
            "nome": configuracoes.nome_aplicacao,
            "versao": configuracoes.versao_aplicacao,
            "status": "em_execucao",
        }

    return aplicacao


app = criar_aplicacao()
