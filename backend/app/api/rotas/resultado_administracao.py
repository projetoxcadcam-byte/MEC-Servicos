from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.services.resultado_administracao import ServicoResultadoAdministracao

roteador=APIRouter(prefix='/administracao/resultado-intermediacao',tags=['resultado-da-administracao'])
@roteador.get('')
def consultar(request:Request,response:Response,banco:Annotated[Session,Depends(obter_banco)],inicio:Annotated[date,Query(ge=date(1900,1,1),le=date(9999,12,30))],fim:Annotated[date,Query(ge=date(1900,1,1),le=date(9999,12,30))],
              deslocamento:int=Query(default=0,ge=0,le=1_000_000),limite:int=Query(default=20,ge=1,le=100)):
    response.headers['Cache-Control']='no-store'
    return ServicoResultadoAdministracao(banco,request.state.usuario_acesso).consultar(inicio,fim,deslocamento,limite)
