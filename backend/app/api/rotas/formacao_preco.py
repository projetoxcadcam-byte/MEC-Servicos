from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.formacao_preco import AnalisePrecoCliente, ConferenciaPreco, RegistroPreco
from backend.app.services.formacao_preco import ServicoFormacaoPreco

roteador=APIRouter(tags=['formacao-do-preco-e-analise'])
Banco=Annotated[Session,Depends(obter_banco)]
Identificador=Annotated[int,Path(gt=0,le=9_999_999_999_999)]

def servico(request,response,banco,perfil):
    u=request.state.usuario_acesso
    if u.perfil!=perfil:raise HTTPException(403,detail='perfil_diverge_da_sessao')
    s=ServicoFormacaoPreco(banco,u)
    recebido=request.headers.get('x-mec-preco-contexto')
    if recebido is not None and recebido!=s.contexto():raise HTTPException(409,detail='contexto_precificacao_alterado')
    response.headers['Cache-Control']='no-store';return s

@roteador.get('/administracao/formacao-preco/cotacoes/{cotacao_id}')
def obter(cotacao_id:Identificador,request:Request,response:Response,banco:Banco):
    return servico(request,response,banco,'admin').obter(cotacao_id)

@roteador.post('/administracao/formacao-preco/cotacoes/{cotacao_id}/conferir')
def conferir(cotacao_id:Identificador,dados:ConferenciaPreco,request:Request,response:Response,banco:Banco):
    return servico(request,response,banco,'admin').conferir(cotacao_id,dados)

@roteador.post('/administracao/formacao-preco/cotacoes/{cotacao_id}/registrar')
def registrar(cotacao_id:Identificador,dados:RegistroPreco,request:Request,response:Response,banco:Banco):
    return servico(request,response,banco,'admin').registrar(cotacao_id,dados)

@roteador.post('/portal-cliente/cotacoes/{cotacao_id}/analise')
def analisar(cotacao_id:Identificador,dados:AnalisePrecoCliente,request:Request,response:Response,banco:Banco,
             empresa_cliente_id:int=Query(gt=0)):
    s=servico(request,response,banco,'cliente')
    if empresa_cliente_id!=s.usuario.empresa_id:raise HTTPException(403,detail='empresa_diverge_da_sessao')
    return s.analisar(cotacao_id,dados)
