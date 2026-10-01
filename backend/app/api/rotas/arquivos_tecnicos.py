from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico


roteador = APIRouter(tags=["arquivos-tecnicos"])


@roteador.post(
    "/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
    response_model=ArquivoTecnicoResposta,
    status_code=status.HTTP_201_CREATED,
)
async def enviar_arquivo_tecnico(
    solicitacao_id: int,
    file: UploadFile = File(...),
    banco: Session = Depends(obter_banco),
) -> ArquivoTecnicoResposta:
    item = await ServicoArquivoTecnico(banco).criar(solicitacao_id, file)
    return ArquivoTecnicoResposta.model_validate(item)


@roteador.get(
    "/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
    response_model=list[ArquivoTecnicoResposta],
)
def listar_arquivos_tecnicos(
    solicitacao_id: int,
    banco: Session = Depends(obter_banco),
) -> list[ArquivoTecnicoResposta]:
    itens = ServicoArquivoTecnico(banco).listar(solicitacao_id)
    return [ArquivoTecnicoResposta.model_validate(item) for item in itens]


@roteador.get(
    "/arquivos-tecnicos/{arquivo_id}",
    response_model=ArquivoTecnicoResposta,
)
def obter_arquivo_tecnico(
    arquivo_id: int,
    banco: Session = Depends(obter_banco),
) -> ArquivoTecnicoResposta:
    item = ServicoArquivoTecnico(banco).obter(arquivo_id)
    return ArquivoTecnicoResposta.model_validate(item)


@roteador.get(
    "/arquivos-tecnicos/{arquivo_id}/download",
    response_class=FileResponse,
)
def baixar_arquivo_tecnico(
    arquivo_id: int,
    banco: Session = Depends(obter_banco),
) -> FileResponse:
    servico = ServicoArquivoTecnico(banco)
    item = servico.obter(arquivo_id)
    caminho = servico.caminho_seguro(item)

    return FileResponse(
        path=caminho,
        media_type=item.content_type or "application/octet-stream",
        filename=item.nome_original,
    )


@roteador.delete(
    "/arquivos-tecnicos/{arquivo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desvincular_arquivo_tecnico(
    arquivo_id: int,
    banco: Session = Depends(obter_banco),
) -> None:
    ServicoArquivoTecnico(banco).desvincular(arquivo_id)
