from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.preparacao_pdf import PrepararPdf, PreparacaoPdfResposta
from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
from backend.app.schemas.historico_campos_pdf import GuardarHistoricoPdf
from backend.app.services.historico_campos_pdf import ServicoHistoricoCamposPdf

roteador = APIRouter(prefix="/administracao/preparacao-pdf", tags=["preparação de PDF para cotação"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


def servico(banco, request):
    s = ServicoPreparacaoPdf(banco)
    s.exigir_admin(request.state.usuario_acesso)
    return s


@roteador.get("/historico-campos")
def historico_campos(banco: SessaoBanco, request: Request):
    return ServicoHistoricoCamposPdf(banco).listar(request.state.usuario_acesso)


@roteador.post("/historico-campos")
def guardar_historico_campos(dados: GuardarHistoricoPdf, banco: SessaoBanco, request: Request):
    return ServicoHistoricoCamposPdf(banco).guardar(dados, request.state.usuario_acesso)


@roteador.get("/arquivos/{arquivo_id}")
def informacoes(arquivo_id: int, banco: SessaoBanco, request: Request):
    from backend.app.services.motor_pdf_cotacao import informacoes as ler
    s = servico(banco, request)
    item = s.original(arquivo_id)
    return {**ler(s.conteudo_original(arquivo_id)), "arquivo_id": item.id, "sha256": item.sha256,
            "preparacoes": s.listar(arquivo_id)}


@roteador.get("/arquivos/{arquivo_id}/paginas/{pagina}")
def imagem_original(arquivo_id: int, pagina: int, banco: SessaoBanco, request: Request,
                    sha256: str = Query(pattern=r"^[a-f0-9]{64}$")):
    from backend.app.services.motor_pdf_cotacao import imagem_pagina
    s = servico(banco, request)
    return Response(imagem_pagina(s.conteudo_original(arquivo_id, sha256), pagina), media_type="image/png")


@roteador.post("/arquivos/{arquivo_id}", response_model=PreparacaoPdfResposta)
def preparar(arquivo_id: int, dados: PrepararPdf, banco: SessaoBanco, request: Request):
    return servico(banco, request).criar(arquivo_id, dados, request.state.usuario_acesso)


@roteador.get("/versoes/{preparacao_id}/download", response_class=FileResponse)
def baixar(preparacao_id: int, banco: SessaoBanco, request: Request):
    s = servico(banco, request)
    p = s.obter(preparacao_id)
    return FileResponse(s.caminho(p), media_type="application/pdf", filename=f"mec-arquivo-{p.arquivo_id}-versao-{p.versao}.pdf")


@roteador.get("/versoes/{preparacao_id}/paginas/{pagina}")
def imagem_preparada(preparacao_id: int, pagina: int, banco: SessaoBanco, request: Request):
    from backend.app.services.motor_pdf_cotacao import imagem_pagina
    s = servico(banco, request)
    p = s.obter(preparacao_id)
    return Response(imagem_pagina(s.caminho(p).read_bytes(), pagina), media_type="image/png")
