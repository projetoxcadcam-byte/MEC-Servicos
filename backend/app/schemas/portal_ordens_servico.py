from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.ordem_servico import OrdemServicoLeitura
from backend.app.schemas.portal_contratacoes import ContratacaoPortalLeitura, SolicitacaoContratacaoLeitura


class OrdemPortalLeitura(OrdemServicoLeitura):
    cliente_razao_social: str
    fornecedor_razao_social: str
    processo_nome: str
    material_nome: str
    contratacao_status: str
    solicitacao: SolicitacaoContratacaoLeitura


class OrdensPortalPagina(BaseModel):
    itens: list[OrdemPortalLeitura]
    total: int
    deslocamento: int
    limite: int


class ContratacoesParaOrdemPagina(BaseModel):
    itens: list[ContratacaoPortalLeitura]
    total: int
    deslocamento: int
    limite: int


class OrdemFornecedorAcao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empresa_fornecedora_id: int = Field(gt=0)
