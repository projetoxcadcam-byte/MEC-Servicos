from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.empresas_operacoes import EmpresaComOperacoesCriacao, OperacoesEmpresaAtualizacao, CapacidadeEmpresaRegistro, MaterialEmpresaVinculo
from backend.app.services.empresas_operacoes import ServicoEmpresasOperacoes

roteador=APIRouter(prefix="/administracao/empresas",tags=["empresas e operações"])
SessaoBanco=Annotated[Session,Depends(obter_banco)]
IdEmpresa=Annotated[int,Path(gt=0)]

@roteador.get("/catalogo-operacoes")
def catalogo(banco:SessaoBanco,request:Request):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).catalogo()

@roteador.get("/catalogo-materiais")
def catalogo_materiais(banco:SessaoBanco,request:Request,deslocamento:int=Query(default=0,ge=0),limite:int=Query(default=200,ge=1,le=200)):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).catalogo_materiais(deslocamento,limite)

@roteador.get("")
def listar(banco:SessaoBanco,request:Request,busca:str=Query(default="",max_length=120),
    tipo:Literal["cliente","fornecedor","ambos"]|None=None,deslocamento:int=Query(default=0,ge=0,le=1_000_000),limite:int=Query(default=20,ge=1,le=100)):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).listar(busca.strip(),tipo,deslocamento,limite)

@roteador.post("",status_code=201)
def criar(dados:EmpresaComOperacoesCriacao,banco:SessaoBanco,request:Request):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).criar(dados)

@roteador.get("/{empresa_id}")
def detalhe(empresa_id:IdEmpresa,banco:SessaoBanco,request:Request):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).detalhe(empresa_id)

@roteador.put("/{empresa_id}/operacoes")
def atualizar(empresa_id:IdEmpresa,dados:OperacoesEmpresaAtualizacao,banco:SessaoBanco,request:Request):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).atualizar(empresa_id,dados)

@roteador.post("/{empresa_id}/capacidade")
def registrar_capacidade(empresa_id:IdEmpresa,dados:CapacidadeEmpresaRegistro,banco:SessaoBanco,request:Request):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).registrar_capacidade(empresa_id,dados)

@roteador.post("/{empresa_id}/materiais")
def vincular_material(empresa_id:IdEmpresa,dados:MaterialEmpresaVinculo,banco:SessaoBanco,request:Request):
    return ServicoEmpresasOperacoes(banco,request.state.usuario_acesso).vincular_material(empresa_id,dados)
