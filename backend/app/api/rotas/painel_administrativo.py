from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.painel_administrativo import ConsultaPainel, FiltroPainel
from backend.app.services.painel_administrativo import ServicoPainelAdministrativo

roteador = APIRouter(tags=["painel administrativo"])
Banco = Annotated[Session, Depends(obter_banco)]


@roteador.get("/administracao/painel", response_model=ConsultaPainel)
def consultar(request: Request, banco: Banco,
              filtro: Annotated[FiltroPainel, Query()] = "todas",
              busca: Annotated[str, Query(max_length=120)] = "",
              deslocamento: Annotated[int, Query(ge=0)] = 0,
              limite: Annotated[int, Query(ge=1, le=100)] = 20):
    return ServicoPainelAdministrativo(banco).consultar(request.state.usuario_acesso, filtro, busca, deslocamento, limite)
