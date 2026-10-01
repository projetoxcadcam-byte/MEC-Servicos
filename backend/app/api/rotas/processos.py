from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.processo import ProcessoCriacao, ProcessoLeitura
from backend.app.services.capacidade import ProcessoDuplicado, ServicoCatalogoTecnico

roteador = APIRouter(prefix="/processos-fabricacao", tags=["processos de fabricação"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]

@roteador.post("", response_model=ProcessoLeitura, status_code=status.HTTP_201_CREATED)
def criar_processo(dados: ProcessoCriacao, banco: SessaoBanco) -> ProcessoLeitura:
    try:
        processo = ServicoCatalogoTecnico(banco).criar_processo(dados)
    except ProcessoDuplicado as exc:
        raise HTTPException(status_code=409, detail="processo_de_fabricacao_ja_cadastrado") from exc
    return ProcessoLeitura.model_validate(processo)

@roteador.get("", response_model=list[ProcessoLeitura])
def listar_processos(banco: SessaoBanco, deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=100, ge=1, le=200)) -> list[ProcessoLeitura]:
    servico = ServicoCatalogoTecnico(banco)
    return [ProcessoLeitura.model_validate(item) for item in servico.listar_processos(deslocamento, limite)]
