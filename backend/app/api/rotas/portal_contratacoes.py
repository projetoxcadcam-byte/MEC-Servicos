from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.rotas.contratacoes import criar_contratacao
from backend.app.database.sessao import obter_banco
from backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta
from backend.app.schemas.contratacao import ContratacaoCriacao, ContratacaoLeitura
from backend.app.schemas.portal_contratacoes import (
    ContratacaoPortalLeitura, ContratacoesPortalPagina, CotacoesParaContratarPagina,
)
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.portal_contratacoes import Perfil, ServicoPortalContratacoes

roteador = APIRouter(tags=["contratações dos portais"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]
EmpresaId = Annotated[int, Query(gt=0)]
RecursoId = Annotated[int, Path(gt=0)]
Deslocamento = Annotated[int, Query(ge=0)]
Limite = Annotated[int, Query(ge=1, le=100)]


@roteador.get("/portal-cliente/cotacoes-aceitas", response_model=CotacoesParaContratarPagina)
def listar_cotacoes_aceitas(banco: SessaoBanco, empresa_cliente_id: EmpresaId,
                          deslocamento: Deslocamento = 0, limite: Limite = 20) -> CotacoesParaContratarPagina:
    return ServicoPortalContratacoes(banco).listar_cotacoes_para_contratar(empresa_cliente_id, deslocamento, limite)


@roteador.post("/portal-cliente/solicitacoes/{solicitacao_id}/contratacao",
               response_model=ContratacaoLeitura, status_code=status.HTTP_201_CREATED)
def contratar_cotacao(solicitacao_id: RecursoId, dados: ContratacaoCriacao, banco: SessaoBanco) -> ContratacaoLeitura:
    ServicoPortalContratacoes(banco).validar_empresa(dados.empresa_cliente_id, "cliente")
    return criar_contratacao(solicitacao_id, dados, banco)


@roteador.get("/portal-cliente/contratacoes", response_model=ContratacoesPortalPagina)
def listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,
                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> ContratacoesPortalPagina:
    return ServicoPortalContratacoes(banco).listar_contratacoes(empresa_cliente_id, "cliente", deslocamento, limite)


@roteador.get("/portal-fornecedor/contratacoes", response_model=ContratacoesPortalPagina)
def listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,
                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> ContratacoesPortalPagina:
    return ServicoPortalContratacoes(banco).listar_contratacoes(empresa_fornecedora_id, "fornecedor", deslocamento, limite)


@roteador.get("/portal-cliente/contratacoes/{contratacao_id}", response_model=ContratacaoPortalLeitura)
def obter_cliente(contratacao_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> ContratacaoPortalLeitura:
    return ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/contratacoes/{contratacao_id}", response_model=ContratacaoPortalLeitura)
def obter_fornecedor(contratacao_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> ContratacaoPortalLeitura:
    return ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_fornecedora_id, "fornecedor")


def _listar_arquivos(contratacao_id: int, banco: Session, empresa_id: int, perfil: Perfil) -> list[ArquivoTecnicoResposta]:
    item = ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_id, perfil)
    return [ArquivoTecnicoResposta.model_validate(arquivo)
            for arquivo in ServicoArquivoTecnico(banco).listar(item.solicitacao_id)]


def _baixar_arquivo(contratacao_id: int, arquivo_id: int, banco: Session, empresa_id: int, perfil: Perfil) -> FileResponse:
    contrato = ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_id, perfil)
    arquivos = ServicoArquivoTecnico(banco)
    arquivo = arquivos.obter(arquivo_id)
    if arquivo.solicitacao_id != contrato.solicitacao_id:
        raise HTTPException(404, detail="arquivo_tecnico_nao_encontrado")
    return FileResponse(arquivos.caminho_seguro(arquivo),
                        media_type=arquivo.content_type or "application/octet-stream", filename=arquivo.nome_original)


@roteador.get("/portal-cliente/contratacoes/{contratacao_id}/arquivos", response_model=list[ArquivoTecnicoResposta])
def arquivos_cliente(contratacao_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> list[ArquivoTecnicoResposta]:
    return _listar_arquivos(contratacao_id, banco, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/contratacoes/{contratacao_id}/arquivos", response_model=list[ArquivoTecnicoResposta])
def arquivos_fornecedor(contratacao_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> list[ArquivoTecnicoResposta]:
    return _listar_arquivos(contratacao_id, banco, empresa_fornecedora_id, "fornecedor")


@roteador.get("/portal-cliente/contratacoes/{contratacao_id}/arquivos/{arquivo_id}/download", response_class=FileResponse)
def download_cliente(contratacao_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> FileResponse:
    return _baixar_arquivo(contratacao_id, arquivo_id, banco, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/contratacoes/{contratacao_id}/arquivos/{arquivo_id}/download", response_class=FileResponse)
def download_fornecedor(contratacao_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> FileResponse:
    return _baixar_arquivo(contratacao_id, arquivo_id, banco, empresa_fornecedora_id, "fornecedor")
