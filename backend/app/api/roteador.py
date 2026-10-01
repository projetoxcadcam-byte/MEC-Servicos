from fastapi import APIRouter

from backend.app.api.rotas.banco_dados import roteador as roteador_banco
from backend.app.api.rotas.empresas import roteador as roteador_empresas
from backend.app.api.rotas.saude import roteador as roteador_saude
from backend.app.api.rotas.processos import roteador as roteador_processos
from backend.app.api.rotas.materiais import roteador as roteador_materiais
from backend.app.api.rotas.capacidades import roteador as roteador_capacidades
from backend.app.api.rotas.solicitacoes import roteador as roteador_solicitacoes
from backend.app.api.rotas.cotacoes import roteador as roteador_cotacoes

roteador_api = APIRouter()
roteador_api.include_router(roteador_saude)
roteador_api.include_router(roteador_banco)
roteador_api.include_router(roteador_empresas)
roteador_api.include_router(roteador_processos)
roteador_api.include_router(roteador_materiais)
roteador_api.include_router(roteador_capacidades)
roteador_api.include_router(roteador_solicitacoes)
roteador_api.include_router(roteador_cotacoes)
