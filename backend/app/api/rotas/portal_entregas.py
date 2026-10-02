from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from backend.app.api.rotas.entregas import aceitar_entrega, recusar_entrega, registrar_entrega
from backend.app.database.sessao import obter_banco
from backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao, EntregaServicoLeitura
from backend.app.schemas.portal_entregas import (
    EntregaPortalCriacao, EntregaPortalDecisao, EntregasPortalLeitura, EntregasPortalPagina,
)
from backend.app.services.portal_entregas import ServicoPortalEntregas

roteador = APIRouter(tags=["entregas e aceite dos portais"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]
EmpresaId = Annotated[int, Query(gt=0)]
RecursoId = Annotated[int, Path(gt=0)]
Deslocamento = Annotated[int, Query(ge=0)]
Limite = Annotated[int, Query(ge=1, le=100)]


@roteador.get("/portal-cliente/entregas", response_model=EntregasPortalPagina)
def listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,
                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> EntregasPortalPagina:
    return ServicoPortalEntregas(banco).listar(empresa_cliente_id, "cliente", deslocamento, limite)


@roteador.get("/portal-fornecedor/entregas", response_model=EntregasPortalPagina)
def listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,
                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> EntregasPortalPagina:
    return ServicoPortalEntregas(banco).listar(empresa_fornecedora_id, "fornecedor", deslocamento, limite)


@roteador.get("/portal-cliente/entregas/{ordem_id}", response_model=EntregasPortalLeitura)
def obter_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> EntregasPortalLeitura:
    return ServicoPortalEntregas(banco).obter(ordem_id, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/entregas/{ordem_id}", response_model=EntregasPortalLeitura)
def obter_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> EntregasPortalLeitura:
    return ServicoPortalEntregas(banco).obter(ordem_id, empresa_fornecedora_id, "fornecedor")


@roteador.post("/portal-fornecedor/entregas/{ordem_id}/registrar",
               response_model=EntregaServicoLeitura, status_code=status.HTTP_201_CREATED)
def registrar(ordem_id: RecursoId, dados: EntregaPortalCriacao, banco: SessaoBanco):
    try:
        ServicoPortalEntregas(banco).preparar_registro(ordem_id, dados.empresa_fornecedora_id,
                                                    dados.ultima_entrega_id, dados.ultima_etapa_id)
        return registrar_entrega(ordem_id, EntregaServicoCriacao(
            empresa_fornecedora_id=dados.empresa_fornecedora_id, observacoes=dados.observacoes), banco)
    except HTTPException:
        banco.rollback()
        raise


@roteador.post("/portal-cliente/entregas/{ordem_id}/{entrega_id}/aceitar", response_model=EntregaServicoLeitura)
def aceitar(ordem_id: RecursoId, entrega_id: RecursoId, dados: EntregaPortalDecisao, banco: SessaoBanco):
    try:
        ServicoPortalEntregas(banco).preparar_decisao(ordem_id, entrega_id, dados.empresa_cliente_id)
        return aceitar_entrega(ordem_id, entrega_id, EntregaServicoDecisao(
            empresa_cliente_id=dados.empresa_cliente_id), banco)
    except HTTPException:
        banco.rollback()
        raise


@roteador.post("/portal-cliente/entregas/{ordem_id}/{entrega_id}/recusar", response_model=EntregaServicoLeitura)
def recusar(ordem_id: RecursoId, entrega_id: RecursoId, dados: EntregaPortalDecisao, banco: SessaoBanco):
    try:
        if not dados.motivo:
            raise HTTPException(422, detail="motivo_recusa_obrigatorio")
        ServicoPortalEntregas(banco).preparar_decisao(ordem_id, entrega_id, dados.empresa_cliente_id)
        return recusar_entrega(ordem_id, entrega_id, EntregaServicoDecisao(
            empresa_cliente_id=dados.empresa_cliente_id, motivo=dados.motivo), banco)
    except HTTPException:
        banco.rollback()
        raise
