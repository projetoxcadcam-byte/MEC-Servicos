from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao, EntregaServicoLeitura
from backend.app.schemas.portal_producao import OrdemProducaoLeitura


class OrdemEntregaLeitura(OrdemProducaoLeitura):
    ultima_entrega_id: int
    ultima_entrega_status: str | None
    ultima_entrega_em: datetime | None
    total_entregas: int
    entrega_pendente_id: int | None


class EntregasPortalPagina(BaseModel):
    itens: list[OrdemEntregaLeitura]
    total: int
    deslocamento: int
    limite: int


class EntregasPortalLeitura(BaseModel):
    ordem: OrdemEntregaLeitura
    historico: list[EntregaServicoLeitura]


class EntregaPortalCriacao(EntregaServicoCriacao):
    model_config = ConfigDict(extra="forbid")
    observacoes: str | None = Field(default=None, max_length=5000)
    ultima_entrega_id: int = Field(ge=0)
    ultima_etapa_id: int = Field(ge=0)


class EntregaPortalDecisao(EntregaServicoDecisao):
    model_config = ConfigDict(extra="forbid")
    motivo: str | None = Field(default=None, max_length=5000)
