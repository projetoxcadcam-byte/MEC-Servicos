from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.empresa import EmpresaCriacao, EmpresaLeitura
from backend.app.services.empresa import (
    DocumentoEmpresaDuplicado,
    EmpresaNaoEncontrada,
    ServicoEmpresa,
)

roteador = APIRouter(prefix="/empresas", tags=["empresas"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post("", response_model=EmpresaLeitura, status_code=status.HTTP_201_CREATED)
def criar_empresa(
    dados: EmpresaCriacao,
    banco: SessaoBanco,
) -> EmpresaLeitura:
    servico = ServicoEmpresa(banco)
    try:
        empresa = servico.criar(dados)
    except DocumentoEmpresaDuplicado as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="documento_da_empresa_ja_cadastrado",
        ) from exc
    return EmpresaLeitura.model_validate(empresa)


@roteador.get("", response_model=list[EmpresaLeitura])
def listar_empresas(
    banco: SessaoBanco,
    deslocamento: int = Query(default=0, ge=0),
    limite: int = Query(default=100, ge=1, le=200),
) -> list[EmpresaLeitura]:
    servico = ServicoEmpresa(banco)
    return [
        EmpresaLeitura.model_validate(empresa)
        for empresa in servico.listar(
            deslocamento=deslocamento,
            limite=limite,
        )
    ]


@roteador.get("/{empresa_id}", response_model=EmpresaLeitura)
def obter_empresa(
    empresa_id: int,
    banco: SessaoBanco,
) -> EmpresaLeitura:
    servico = ServicoEmpresa(banco)
    try:
        empresa = servico.obter(empresa_id)
    except EmpresaNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa_nao_encontrada",
        ) from exc
    return EmpresaLeitura.model_validate(empresa)
