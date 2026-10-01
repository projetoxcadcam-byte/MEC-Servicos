from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao, EntregaServicoLeitura
from backend.app.services.entrega import (
    EmpresaClienteNaoPodeDecidirEntrega,
    EmpresaFornecedoraNaoPodeEntregar,
    EntregaNaoEncontrada,
    EntregaNaoEstaPendente,
    EntregaPendenteJaExiste,
    MotivoRecusaObrigatorio,
    OrdemServicoNaoEncontradaParaEntrega,
    OrdemServicoNaoEstaProntaParaEntrega,
    OrdemServicoNaoPodeReceberEntrega,
    ServicoEntrega,
)

roteador = APIRouter(tags=["entregas"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post("/ordens-servico/{ordem_servico_id}/entregas", response_model=EntregaServicoLeitura, status_code=status.HTTP_201_CREATED)
def registrar_entrega(ordem_servico_id: int, dados: EntregaServicoCriacao, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).registrar(ordem_servico_id, dados)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc
    except EmpresaFornecedoraNaoPodeEntregar as exc:
        raise HTTPException(403, "empresa_nao_e_fornecedora_da_ordem_servico") from exc
    except OrdemServicoNaoPodeReceberEntrega as exc:
        raise HTTPException(409, "ordem_servico_nao_pode_receber_entrega") from exc
    except OrdemServicoNaoEstaProntaParaEntrega as exc:
        raise HTTPException(409, "ordem_servico_nao_esta_pronta_para_entrega") from exc
    except EntregaPendenteJaExiste as exc:
        raise HTTPException(409, "entrega_pendente_ja_existe") from exc


@roteador.get("/ordens-servico/{ordem_servico_id}/entregas", response_model=list[EntregaServicoLeitura])
def listar_entregas(ordem_servico_id: int, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).listar(ordem_servico_id)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc


@roteador.get("/ordens-servico/{ordem_servico_id}/entregas/{entrega_id}", response_model=EntregaServicoLeitura)
def obter_entrega(ordem_servico_id: int, entrega_id: int, banco: SessaoBanco):
    try:
        item = ServicoEntrega(banco).obter(entrega_id)
        if item.ordem_servico_id != ordem_servico_id:
            raise EntregaNaoEncontrada
        return item
    except EntregaNaoEncontrada as exc:
        raise HTTPException(404, "entrega_nao_encontrada") from exc


@roteador.post("/ordens-servico/{ordem_servico_id}/entregas/{entrega_id}/aceitar", response_model=EntregaServicoLeitura)
def aceitar_entrega(ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).aceitar(ordem_servico_id, entrega_id, dados)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc
    except EmpresaClienteNaoPodeDecidirEntrega as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_ordem_servico") from exc
    except EntregaNaoEncontrada as exc:
        raise HTTPException(404, "entrega_nao_encontrada") from exc
    except EntregaNaoEstaPendente as exc:
        raise HTTPException(409, "entrega_nao_esta_pendente") from exc


@roteador.post("/ordens-servico/{ordem_servico_id}/entregas/{entrega_id}/recusar", response_model=EntregaServicoLeitura)
def recusar_entrega(ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).recusar(ordem_servico_id, entrega_id, dados)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc
    except EmpresaClienteNaoPodeDecidirEntrega as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_ordem_servico") from exc
    except EntregaNaoEncontrada as exc:
        raise HTTPException(404, "entrega_nao_encontrada") from exc
    except EntregaNaoEstaPendente as exc:
        raise HTTPException(409, "entrega_nao_esta_pendente") from exc
    except MotivoRecusaObrigatorio as exc:
        raise HTTPException(422, "motivo_recusa_obrigatorio") from exc
