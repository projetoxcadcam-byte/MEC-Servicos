from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.rotas.ordens_servico import criar_ordem_servico
from backend.app.database.sessao import obter_banco
from backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta
from backend.app.schemas.ordem_servico import OrdemServicoCriacao, OrdemServicoLeitura
from backend.app.schemas.portal_ordens_servico import (
    ContratacoesParaOrdemPagina, OrdemFornecedorAcao, OrdemPortalLeitura, OrdensPortalPagina,
)
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.portal_contratacoes import Perfil, ServicoPortalContratacoes
from backend.app.services.portal_ordens_servico import ServicoPortalOrdens

roteador = APIRouter(tags=["ordens de serviço dos portais"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]
EmpresaId = Annotated[int, Query(gt=0)]
RecursoId = Annotated[int, Path(gt=0)]
Deslocamento = Annotated[int, Query(ge=0)]
Limite = Annotated[int, Query(ge=1, le=100)]


@roteador.get("/portal-cliente/contratacoes-para-ordem", response_model=ContratacoesParaOrdemPagina)
def contratacoes_para_ordem(banco: SessaoBanco, empresa_cliente_id: EmpresaId,
                           deslocamento: Deslocamento = 0, limite: Limite = 20) -> ContratacoesParaOrdemPagina:
    return ServicoPortalOrdens(banco).contratacoes_para_gerar(empresa_cliente_id, deslocamento, limite)


@roteador.post("/portal-cliente/contratacoes/{contratacao_id}/ordem-servico",
               response_model=OrdemServicoLeitura, status_code=status.HTTP_201_CREATED)
def gerar_ordem(contratacao_id: RecursoId, dados: OrdemServicoCriacao, banco: SessaoBanco) -> OrdemServicoLeitura:
    ServicoPortalContratacoes(banco).validar_empresa(dados.empresa_cliente_id, "cliente")
    return criar_ordem_servico(contratacao_id, dados, banco)


@roteador.get("/portal-cliente/ordens-servico", response_model=OrdensPortalPagina)
def listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,
                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> OrdensPortalPagina:
    return ServicoPortalOrdens(banco).listar(empresa_cliente_id, "cliente", deslocamento, limite)


@roteador.get("/portal-fornecedor/ordens-servico", response_model=OrdensPortalPagina)
def listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,
                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> OrdensPortalPagina:
    return ServicoPortalOrdens(banco).listar(empresa_fornecedora_id, "fornecedor", deslocamento, limite)


@roteador.get("/portal-cliente/ordens-servico/{ordem_id}", response_model=OrdemPortalLeitura)
def obter_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> OrdemPortalLeitura:
    return ServicoPortalOrdens(banco).obter(ordem_id, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/ordens-servico/{ordem_id}", response_model=OrdemPortalLeitura)
def obter_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> OrdemPortalLeitura:
    return ServicoPortalOrdens(banco).obter(ordem_id, empresa_fornecedora_id, "fornecedor")


@roteador.post("/portal-fornecedor/ordens-servico/{ordem_id}/iniciar", response_model=OrdemPortalLeitura)
def iniciar(ordem_id: RecursoId, dados: OrdemFornecedorAcao, banco: SessaoBanco) -> OrdemPortalLeitura:
    return ServicoPortalOrdens(banco).executar(ordem_id, dados.empresa_fornecedora_id, "iniciar")


@roteador.post("/portal-fornecedor/ordens-servico/{ordem_id}/concluir", response_model=OrdemPortalLeitura)
def concluir(ordem_id: RecursoId, dados: OrdemFornecedorAcao, banco: SessaoBanco) -> OrdemPortalLeitura:
    return ServicoPortalOrdens(banco).executar(ordem_id, dados.empresa_fornecedora_id, "concluir")


def _arquivos(ordem_id: int, banco: Session, empresa: int, perfil: Perfil) -> list[ArquivoTecnicoResposta]:
    ordem = ServicoPortalOrdens(banco).obter(ordem_id, empresa, perfil)
    return [ArquivoTecnicoResposta.model_validate(item) for item in ServicoArquivoTecnico(banco).listar(ordem.solicitacao_id)]


def _download(ordem_id: int, arquivo_id: int, banco: Session, empresa: int, perfil: Perfil) -> FileResponse:
    ordem = ServicoPortalOrdens(banco).obter(ordem_id, empresa, perfil)
    servico = ServicoArquivoTecnico(banco)
    arquivo = servico.obter(arquivo_id)
    if arquivo.solicitacao_id != ordem.solicitacao_id:
        raise HTTPException(404, detail="arquivo_tecnico_nao_encontrado")
    return FileResponse(servico.caminho_seguro(arquivo), media_type=arquivo.content_type or "application/octet-stream",
                        filename=arquivo.nome_original)


@roteador.get("/portal-cliente/ordens-servico/{ordem_id}/arquivos", response_model=list[ArquivoTecnicoResposta])
def arquivos_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> list[ArquivoTecnicoResposta]:
    return _arquivos(ordem_id, banco, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/ordens-servico/{ordem_id}/arquivos", response_model=list[ArquivoTecnicoResposta])
def arquivos_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> list[ArquivoTecnicoResposta]:
    return _arquivos(ordem_id, banco, empresa_fornecedora_id, "fornecedor")


@roteador.get("/portal-cliente/ordens-servico/{ordem_id}/arquivos/{arquivo_id}/download")
def baixar_cliente(ordem_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> FileResponse:
    return _download(ordem_id, arquivo_id, banco, empresa_cliente_id, "cliente")


@roteador.get("/portal-fornecedor/ordens-servico/{ordem_id}/arquivos/{arquivo_id}/download")
def baixar_fornecedor(ordem_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> FileResponse:
    return _download(ordem_id, arquivo_id, banco, empresa_fornecedora_id, "fornecedor")
