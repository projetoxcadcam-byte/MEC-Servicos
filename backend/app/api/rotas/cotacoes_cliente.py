from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.cotacoes_cliente import CotacoesConsultaClientePagina, CotacaoConsultaClienteDetalhe
from backend.app.services.cotacoes_cliente import ServicoCotacoesCliente

roteador = APIRouter(prefix='/portal-cliente/cotacoes', tags=['consulta-cotacoes-cliente'])
Banco = Annotated[Session, Depends(obter_banco)]
Empresa = Annotated[int, Query(gt=0)]


def servico(request, response, banco, empresa):
    usuario = request.state.usuario_acesso
    if usuario.perfil != 'cliente' or usuario.empresa_id != empresa:
        raise HTTPException(403, detail='perfil_ou_empresa_diverge_da_sessao')
    s = ServicoCotacoesCliente(banco, usuario)
    contexto = request.headers.get('x-mec-cotacoes-contexto')
    if contexto is not None and contexto != s.contexto():
        raise HTTPException(409, detail='contexto_cotacoes_alterado')
    response.headers['Cache-Control'] = 'no-store'
    return s


@roteador.get('', response_model=CotacoesConsultaClientePagina)
def listar(request: Request, response: Response, banco: Banco, empresa_cliente_id: Empresa,
           solicitacao_id: int | None = Query(default=None, gt=0, le=9_999_999_999_999), cotacao_id: int | None = Query(default=None, gt=0, le=9_999_999_999_999),
           situacao: Literal['todas','enviada','aceita','recusada','expirada','cancelada'] = 'todas',
           ordenacao: Literal['recentes','valor','prazo'] = 'recentes',
           deslocamento: int = Query(default=0, ge=0, le=1_000_000), limite: int = Query(default=20, ge=1, le=100)):
    return servico(request, response, banco, empresa_cliente_id).listar(solicitacao_id, cotacao_id, situacao, ordenacao, deslocamento, limite)


@roteador.get('/{cotacao_id}', response_model=CotacaoConsultaClienteDetalhe)
def obter(cotacao_id: Annotated[int, Path(gt=0, le=9_999_999_999_999)], request: Request, response: Response, banco: Banco, empresa_cliente_id: Empresa):
    return servico(request, response, banco, empresa_cliente_id).obter(cotacao_id)
