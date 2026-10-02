from backend.app.api.rotas.portal_entregas import roteador as roteador_portal_entregas
from backend.app.api.rotas.portal_producao import roteador as roteador_portal_producao
from backend.app.api.rotas.portal_ordens_servico import roteador as roteador_portal_ordens_servico
from backend.app.api.rotas.portal_contratacoes import roteador as roteador_portal_contratacoes
from backend.app.api.rotas.portal_fornecedor import roteador as roteador_portal_fornecedor
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
from backend.app.api.rotas.contratacoes import roteador as roteador_contratacoes
from backend.app.api.rotas.ordens_servico import roteador as ordens_servico_router
from backend.app.api.rotas.etapas_producao import roteador as roteador_etapas_producao
roteador_api.include_router(roteador_contratacoes)
roteador_api.include_router(ordens_servico_router)
roteador_api.include_router(roteador_etapas_producao)
from backend.app.api.rotas.entregas import roteador as roteador_entregas
roteador_api.include_router(roteador_entregas)
from backend.app.api.rotas.pagamentos import roteador as roteador_pagamentos
roteador_api.include_router(roteador_pagamentos)
from backend.app.api.rotas.integracao_pagamentos import roteador as roteador_integracao_pagamentos
roteador_api.include_router(roteador_integracao_pagamentos)
from backend.app.api.rotas.avaliacoes import roteador as roteador_avaliacoes
roteador_api.include_router(roteador_avaliacoes)
from backend.app.api.rotas.ranking_fornecedores import roteador as roteador_ranking_fornecedores
roteador_api.include_router(roteador_ranking_fornecedores)
from backend.app.api.rotas.arquivos_tecnicos import roteador as roteador_arquivos_tecnicos
roteador_api.include_router(roteador_arquivos_tecnicos)
roteador_api.include_router(roteador_portal_fornecedor)
roteador_api.include_router(roteador_portal_contratacoes)
roteador_api.include_router(roteador_portal_ordens_servico)
roteador_api.include_router(roteador_portal_producao)
roteador_api.include_router(roteador_portal_entregas)
