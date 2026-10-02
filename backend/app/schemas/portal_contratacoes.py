from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.contratacao import ContratacaoLeitura
from backend.app.schemas.cotacao import CotacaoLeitura
from backend.app.schemas.solicitacao import SolicitacaoServicoLeitura


class SolicitacaoContratacaoLeitura(SolicitacaoServicoLeitura):
    cliente_razao_social: str
    processo_nome: str
    material_nome: str


class CotacaoParaContratarLeitura(CotacaoLeitura):
    fornecedor_razao_social: str
    solicitacao: SolicitacaoContratacaoLeitura


class ContratacaoPortalLeitura(ContratacaoLeitura):
    cliente_razao_social: str
    fornecedor_razao_social: str
    solicitacao: SolicitacaoContratacaoLeitura


class CotacoesParaContratarPagina(BaseModel):
    itens: list[CotacaoParaContratarLeitura]
    total: int
    deslocamento: int
    limite: int


class ContratacoesPortalPagina(BaseModel):
    itens: list[ContratacaoPortalLeitura]
    total: int
    deslocamento: int
    limite: int
