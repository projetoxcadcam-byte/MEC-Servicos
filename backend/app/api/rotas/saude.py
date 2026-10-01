from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.configuracao import configuracoes

roteador = APIRouter(tags=["sistema"])


@roteador.get("/saude")
async def saude() -> dict[str, str]:
    return {
        "status": "ok",
        "servico": configuracoes.nome_aplicacao,
        "versao": configuracoes.versao_aplicacao,
    }
