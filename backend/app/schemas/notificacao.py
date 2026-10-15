from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class NotificacaoLeitura(BaseModel):
    id: int
    assunto: str
    mensagem: str
    destino: str
    perfil_origem: Literal["admin", "cliente", "fornecedor"]
    solicitacao_id: int | None
    contratacao_id: int | None
    ordem_servico_id: int | None
    criada_em: str
    lida_em: str | None


class ResumoNotificacoes(BaseModel):
    usuario_id: int
    perfil: Literal["admin", "cliente", "fornecedor"]
    empresa_id: int | None
    nao_lidas: int
    ultimo_id: int


class PaginaNotificacoes(ResumoNotificacoes):
    itens: list[NotificacaoLeitura]
    proximo_antes_id: int | None


class MarcarNotificacoesLidas(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ate_id: int = Field(ge=0)
