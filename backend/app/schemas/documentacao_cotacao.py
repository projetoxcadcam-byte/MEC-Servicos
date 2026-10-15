from __future__ import annotations

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RegistroDocumentacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acao: Literal["liberar", "bloquear"]
    versao: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    registro_interno: str = Field(min_length=3, max_length=2000)
    revisado_sem_contatos: bool = False
    chave_operacao: UUID
    preparacao_pdf_id: int | None = Field(default=None, gt=0)


class EventoDocumentacao(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    versao: int
    acao: str
    registro_interno: str
    administrador_nome: str
    criado_em: str
    versao_pdf_preparada: int | None = None


class ArquivoDocumentacao(BaseModel):
    id: int
    solicitacao_id: int
    nome_original: str
    extensao: str
    tamanho_bytes: int
    sha256: str
    versao: int
    liberado: bool
    conteudo_valido: bool
    ativo: bool
    historico: list[EventoDocumentacao]
    preparacao_pdf_publicada_id: int | None = None
    versao_pdf_publicada: int | None = None


class SolicitacaoDocumentacao(BaseModel):
    id: int
    cliente: str
    processo: str
    material: str
    quantidade: int
    status: str
    arquivos_ativos: int
    arquivos_disponiveis: int
    arquivos: list[ArquivoDocumentacao]


class PaginaDocumentacao(BaseModel):
    itens: list[SolicitacaoDocumentacao]
    total: int
    deslocamento: int
    limite: int
