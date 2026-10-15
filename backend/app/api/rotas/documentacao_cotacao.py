from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.documentacao_cotacao import ArquivoDocumentacao, PaginaDocumentacao, RegistroDocumentacao
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao

roteador = APIRouter(prefix="/administracao/documentacao-cotacao", tags=["documentação para cotação"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]

@roteador.get("",response_model=PaginaDocumentacao)
def listar_documentacao(banco:SessaoBanco,solicitacao_id:int|None=Query(default=None,gt=0),
                       deslocamento:int=Query(default=0,ge=0),limite:int=Query(default=20,ge=1,le=100)):
    return ServicoDocumentacaoCotacao(banco).listar(solicitacao_id,deslocamento,limite)

@roteador.post("/arquivos/{arquivo_id}/eventos",response_model=ArquivoDocumentacao)
def registrar_documentacao(arquivo_id:int,dados:RegistroDocumentacao,banco:SessaoBanco,request:Request):
    return ServicoDocumentacaoCotacao(banco).registrar(arquivo_id,dados,request.state.usuario_acesso)
