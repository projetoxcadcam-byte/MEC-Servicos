"""Resumo dos portais, sem identidade da contraparte ou notas comparativas."""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class ContagemPainel(BaseModel):
    total: int = Field(ge=0)
    por_status: dict[str, int]


class SolicitacaoPainel(BaseModel):
    id: int
    status: str
    processo_nome: str
    material_nome: str
    quantidade: int
    criada_em: datetime


class CotacaoPainel(BaseModel):
    id: int
    solicitacao_id: int
    status: str
    valor_total: Decimal
    criada_em: datetime


class OrdemPainel(BaseModel):
    id: int
    solicitacao_id: int
    contratacao_id: int
    status: str
    processo_nome: str
    material_nome: str
    etapa_atual: str | None
    etapa_atual_em: datetime | None
    criada_em: datetime


class PainelPerfisLeitura(BaseModel):
    contexto: str
    perfil: Literal["cliente", "fornecedor"]
    empresa_id: int
    consultado_em: datetime
    solicitacoes: ContagemPainel | None
    cotacoes: ContagemPainel
    contratacoes: ContagemPainel
    ordens: ContagemPainel
    oportunidades: int | None = Field(ge=0)
    solicitacoes_recentes: list[SolicitacaoPainel] = Field(max_length=5)
    cotacoes_recentes: list[CotacaoPainel] = Field(max_length=5)
    ordens_recentes: list[OrdemPainel] = Field(max_length=5)
