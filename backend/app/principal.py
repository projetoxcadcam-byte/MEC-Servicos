from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.roteador import roteador_api
from backend.app.core.configuracao import configuracoes
from backend.app.database.inicializacao import inicializar_banco


@asynccontextmanager
async def ciclo_vida(_: FastAPI) -> AsyncIterator[None]:
    inicializar_banco()
    yield


def criar_aplicacao() -> FastAPI:
    aplicacao = FastAPI(
        title=configuracoes.nome_aplicacao,
        version=configuracoes.versao_aplicacao,
        debug=configuracoes.modo_debug,
        lifespan=ciclo_vida,
    )

    aplicacao.include_router(
        roteador_api,
        prefix=configuracoes.prefixo_api,
    )

    @aplicacao.get("/", tags=["sistema"])
    async def raiz() -> dict[str, str]:
        return {
            "nome": configuracoes.nome_aplicacao,
            "versao": configuracoes.versao_aplicacao,
            "status": "em_execucao",
        }

    return aplicacao


app = criar_aplicacao()
