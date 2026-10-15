from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.schemas.intermediacao import (
    ConsultaPortalIntermediacao, ContratacaoParaIntermediacao, InicioIntermediacao,
    IntermediacaoDetalhe, IntermediacaoPagina, RegistroIntermediacao,
)
from backend.app.schemas.ordem_servico import OrdemServicoCriacao
from backend.app.services.intermediacao import ServicoIntermediacao, exigir_admin
from backend.app.services.ordem_servico import ServicoOrdemServico

roteador = APIRouter(tags=["intermediação administrativa"])
Banco = Annotated[Session, Depends(obter_banco)]
Id = Annotated[int, Path(gt=0)]
EmpresaId = Annotated[int, Query(gt=0)]
ADMIN = "/administracao/intermediacao"


@roteador.get(ADMIN + "/ordens", response_model=IntermediacaoPagina)
def listar(request: Request, banco: Banco, deslocamento: Annotated[int, Query(ge=0)] = 0,
           limite: Annotated[int, Query(ge=1, le=100)] = 20, filtro: str | None = None):
    return ServicoIntermediacao(banco).listar(request.state.usuario_acesso, deslocamento, limite, filtro)


@roteador.get(ADMIN + "/ordens/{ordem_id}", response_model=IntermediacaoDetalhe)
def obter(ordem_id: Id, request: Request, banco: Banco):
    return ServicoIntermediacao(banco).obter(ordem_id, request.state.usuario_acesso)


@roteador.post(ADMIN + "/ordens/{ordem_id}/iniciar", response_model=IntermediacaoDetalhe, status_code=201)
def iniciar(ordem_id: Id, dados: InicioIntermediacao, request: Request, banco: Banco):
    return ServicoIntermediacao(banco).iniciar(ordem_id, dados, request.state.usuario_acesso)


@roteador.post(ADMIN + "/ordens/{ordem_id}/eventos", response_model=IntermediacaoDetalhe, status_code=201)
def registrar(ordem_id: Id, dados: RegistroIntermediacao, request: Request, banco: Banco):
    return ServicoIntermediacao(banco).registrar(ordem_id, dados, request.state.usuario_acesso)


@roteador.get(ADMIN + "/contratacoes-sem-ordem", response_model=list[ContratacaoParaIntermediacao])
def contratacoes(request: Request, banco: Banco):
    return ServicoIntermediacao(banco).contratacoes_sem_ordem(request.state.usuario_acesso)


@roteador.post(ADMIN + "/contratacoes/{contratacao_id}/ordem", response_model=IntermediacaoDetalhe, status_code=201)
def criar_ordem(contratacao_id: Id, dados: InicioIntermediacao, request: Request, banco: Banco):
    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy import select, update
    from backend.app.models.ordem_servico import OrdemServico
    from backend.app.services.ordem_servico import OrdemServicoDuplicada
    exigir_admin(request.state.usuario_acesso)
    travada = banco.execute(update(ContratacaoServico).where(ContratacaoServico.id == contratacao_id,
        ContratacaoServico.status == "ativa").values(status=ContratacaoServico.status),
        execution_options={"synchronize_session": False})
    if travada.rowcount != 1:
        banco.rollback()
        if banco.get(ContratacaoServico, contratacao_id) is None: raise HTTPException(404, detail="contratacao_nao_encontrada")
        raise HTTPException(409, detail="contratacao_nao_esta_ativa")
    banco.expire_all()
    contrato = banco.get(ContratacaoServico, contratacao_id)
    if banco.scalar(select(OrdemServico.id).where(OrdemServico.contratacao_id == contratacao_id)):
        raise HTTPException(409, detail="contratacao_ja_possui_ordem")
    try:
        ordem = ServicoOrdemServico(banco).criar(contratacao_id,
            OrdemServicoCriacao(empresa_cliente_id=contrato.empresa_cliente_id, observacoes=dados.registro_interno))
    except (OrdemServicoDuplicada, IntegrityError):
        banco.rollback(); raise HTTPException(409, detail="contratacao_ja_possui_ordem") from None
    # A criação da ordem usa o contrato existente; o ciclo começa em seguida no painel.
    return ServicoIntermediacao(banco).obter(ordem.id, request.state.usuario_acesso)


@roteador.get("/portal-cliente/intermediacao/{ordem_id}", response_model=ConsultaPortalIntermediacao)
def cliente(ordem_id: Id, empresa_cliente_id: EmpresaId, request: Request, banco: Banco):
    return ServicoIntermediacao(banco).consultar_portal(ordem_id, request.state.usuario_acesso, "cliente", empresa_cliente_id)


@roteador.get("/portal-fornecedor/intermediacao/{ordem_id}", response_model=ConsultaPortalIntermediacao)
def fornecedor(ordem_id: Id, empresa_fornecedora_id: EmpresaId, request: Request, banco: Banco):
    return ServicoIntermediacao(banco).consultar_portal(ordem_id, request.state.usuario_acesso, "fornecedor", empresa_fornecedora_id)
