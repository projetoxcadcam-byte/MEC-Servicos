from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from backend.app.api.rotas.etapas_producao import registrar_etapa_producao
from backend.app.database.sessao import obter_banco
from backend.app.schemas.etapa_producao import EtapaProducaoCriacao, EtapaProducaoLeitura
from backend.app.schemas.portal_producao import AcompanhamentoPortalLeitura, EtapaPortalCriacao, ProducaoPortalPagina
from backend.app.services.portal_producao import ServicoPortalProducao

roteador = APIRouter(tags=["acompanhamento de produção dos portais"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]
EmpresaId = Annotated[int, Query(gt=0)]
RecursoId = Annotated[int, Path(gt=0)]
Deslocamento = Annotated[int, Query(ge=0)]
Limite = Annotated[int, Query(ge=1, le=100)]


@roteador.get("/portal-cliente/producao", response_model=ProducaoPortalPagina)
def listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,
                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> ProducaoPortalPagina:
    return ServicoPortalProducao(banco).listar(empresa_cliente_id, "cliente", deslocamento, limite)


@roteador.get("/portal-fornecedor/producao", response_model=ProducaoPortalPagina)
def listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,
                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> ProducaoPortalPagina:
    return ServicoPortalProducao(banco).listar(empresa_fornecedora_id, "fornecedor", deslocamento, limite)


@roteador.get("/portal-cliente/producao/{ordem_id}", response_model=AcompanhamentoPortalLeitura)
def obter_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> AcompanhamentoPortalLeitura:
    return ServicoPortalProducao(banco).obter(ordem_id, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/producao/{ordem_id}", response_model=AcompanhamentoPortalLeitura)
def obter_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> AcompanhamentoPortalLeitura:
    return ServicoPortalProducao(banco).obter(ordem_id, empresa_fornecedora_id, "fornecedor")


@roteador.post("/portal-fornecedor/producao/{ordem_id}/etapas",
               response_model=EtapaProducaoLeitura, status_code=status.HTTP_201_CREATED)
def registrar(ordem_id: RecursoId, dados: EtapaPortalCriacao, banco: SessaoBanco) -> EtapaProducaoLeitura:
    ServicoPortalProducao(banco).preparar_registro(ordem_id, dados.empresa_fornecedora_id, dados.ultima_etapa_id)
    criacao = EtapaProducaoCriacao(empresa_fornecedora_id=dados.empresa_fornecedora_id,
                                 etapa=dados.etapa, observacoes=dados.observacoes)
    return registrar_etapa_producao(ordem_id, criacao, banco)
