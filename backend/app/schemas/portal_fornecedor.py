from __future__ import annotations

from pydantic import BaseModel

from backend.app.schemas.cotacao import CotacaoLeitura
from backend.app.schemas.solicitacao import SolicitacaoServicoLeitura


class SolicitacaoFornecedorLeitura(SolicitacaoServicoLeitura):
    cliente_razao_social: str
    processo_nome: str
    material_nome: str


class CotacaoFornecedorLeitura(CotacaoLeitura):
    solicitacao: SolicitacaoFornecedorLeitura


class OportunidadesFornecedorLeitura(BaseModel):
    itens: list[SolicitacaoFornecedorLeitura]
    total: int
    deslocamento: int
    limite: int


class CotacoesFornecedorLeitura(BaseModel):
    itens: list[CotacaoFornecedorLeitura]
    total: int
    deslocamento: int
    limite: int
