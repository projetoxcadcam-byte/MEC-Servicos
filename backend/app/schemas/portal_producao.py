from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.etapa_producao import EtapaProducaoCriacao, EtapaProducaoLeitura
from backend.app.schemas.portal_ordens_servico import OrdemPortalLeitura


class OrdemProducaoLeitura(OrdemPortalLeitura):
    etapa_atual: str | None
    ultima_etapa_id: int
    etapa_atual_em: datetime | None
    total_atualizacoes: int


class ProducaoPortalPagina(BaseModel):
    itens: list[OrdemProducaoLeitura]
    total: int
    deslocamento: int
    limite: int


class AcompanhamentoPortalLeitura(BaseModel):
    ordem: OrdemProducaoLeitura
    etapa_atual: str | None
    ultima_etapa_id: int
    historico: list[EtapaProducaoLeitura]


class EtapaPortalCriacao(EtapaProducaoCriacao):
    model_config = ConfigDict(extra="forbid")
    observacoes: str | None = Field(default=None, max_length=5000)
    ultima_etapa_id: int = Field(ge=0)
