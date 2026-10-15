from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.rotas.cotacoes import criar_cotacao
from backend.app.database.sessao import obter_banco
from backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta
from backend.app.schemas.cotacao import CotacaoCriacao, CotacaoLeitura
from backend.app.schemas.portal_fornecedor import CotacoesFornecedorLeitura, OportunidadesFornecedorLeitura
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.portal_fornecedor import ServicoPortalFornecedor
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao

roteador = APIRouter(prefix="/portal-fornecedor", tags=["portal do fornecedor"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]
EmpresaFornecedor = Annotated[int, Query(gt=0)]


@roteador.get("/oportunidades", response_model=OportunidadesFornecedorLeitura)
def listar_oportunidades(
    banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor,
    deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100),
    solicitacao_id: int | None = Query(default=None, gt=0),
) -> OportunidadesFornecedorLeitura:
    return ServicoPortalFornecedor(banco).listar_oportunidades(empresa_fornecedora_id, deslocamento, limite, solicitacao_id)


@roteador.get("/cotacoes", response_model=CotacoesFornecedorLeitura)
def listar_minhas_cotacoes(
    banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor,
    deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100),
    solicitacao_id: int | None = Query(default=None, gt=0),
    somente_leitura: bool = False,
) -> CotacoesFornecedorLeitura:
    return ServicoPortalFornecedor(banco).listar_cotacoes(empresa_fornecedora_id, deslocamento, limite, solicitacao_id, somente_leitura=somente_leitura)


@roteador.post("/solicitacoes/{solicitacao_id}/cotacoes", response_model=CotacaoLeitura, status_code=status.HTTP_201_CREATED)
def enviar_cotacao(solicitacao_id: int, dados: CotacaoCriacao, banco: SessaoBanco) -> CotacaoLeitura:
    ServicoPortalFornecedor(banco).validar_envio(solicitacao_id, dados.empresa_fornecedora_id)
    return criar_cotacao(solicitacao_id, dados, banco)


@roteador.get("/solicitacoes/{solicitacao_id}/arquivos", response_model=list[ArquivoTecnicoResposta])
def listar_arquivos(solicitacao_id: int, banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor) -> list[ArquivoTecnicoResposta]:
    ServicoPortalFornecedor(banco).validar_acesso_arquivos(solicitacao_id, empresa_fornecedora_id)
    documentos = ServicoDocumentacaoCotacao(banco)
    from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
    pdfs = ServicoPreparacaoPdf(banco)
    resposta = []
    for item in documentos.listar_liberados(solicitacao_id):
        p = pdfs.publicado(item.id)
        campos = {"nome_original": f"Arquivo tecnico {item.id}{item.extensao}"}
        if p:
            campos.update(sha256=p.sha256, tamanho_bytes=p.tamanho_bytes, content_type="application/pdf")
        resposta.append(ArquivoTecnicoResposta.model_validate(item).model_copy(update=campos))
    return resposta


@roteador.get("/arquivos/{arquivo_id}/download", response_class=FileResponse)
def baixar_arquivo(arquivo_id: int, banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor) -> FileResponse:
    arquivos = ServicoArquivoTecnico(banco)
    item = arquivos.obter(arquivo_id)
    ServicoPortalFornecedor(banco).validar_acesso_arquivos(item.solicitacao_id, empresa_fornecedora_id)
    ServicoDocumentacaoCotacao(banco).exigir_acesso(item.solicitacao_id, item.id)
    from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
    pdfs = ServicoPreparacaoPdf(banco)
    p = pdfs.publicado(item.id)
    if p:
        return FileResponse(pdfs.caminho(p), media_type="application/pdf", filename=f"arquivo-tecnico-{item.id}.pdf")
    return FileResponse(arquivos.caminho_seguro(item), media_type="application/octet-stream", filename=f"arquivo-tecnico-{item.id}{item.extensao}")
