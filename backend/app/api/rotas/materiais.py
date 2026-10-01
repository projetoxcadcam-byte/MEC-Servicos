from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.material import MaterialCriacao, MaterialLeitura
from backend.app.services.capacidade import MaterialDuplicado, ServicoCatalogoTecnico

roteador = APIRouter(prefix="/materiais", tags=["materiais"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]

@roteador.post("", response_model=MaterialLeitura, status_code=status.HTTP_201_CREATED)
def criar_material(dados: MaterialCriacao, banco: SessaoBanco) -> MaterialLeitura:
    try:
        material = ServicoCatalogoTecnico(banco).criar_material(dados)
    except MaterialDuplicado as exc:
        raise HTTPException(status_code=409, detail="material_ja_cadastrado") from exc
    return MaterialLeitura.model_validate(material)

@roteador.get("", response_model=list[MaterialLeitura])
def listar_materiais(banco: SessaoBanco, deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=100, ge=1, le=200)) -> list[MaterialLeitura]:
    servico = ServicoCatalogoTecnico(banco)
    return [MaterialLeitura.model_validate(item) for item in servico.listar_materiais(deslocamento, limite)]
