from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco

roteador = APIRouter(tags=["banco de dados"])


@roteador.get("/banco-dados/saude")
def saude_banco(banco: Session = Depends(obter_banco)) -> dict[str, str]:
    try:
        valor = banco.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="banco_de_dados_indisponivel",
        ) from exc

    return {
        "status": "ok",
        "banco": "conectado",
        "sondagem": str(valor),
    }
