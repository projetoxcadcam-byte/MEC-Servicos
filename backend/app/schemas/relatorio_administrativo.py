from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict
from backend.app.schemas.financeiro_administrativo import MovimentoFinanceiro
from backend.app.schemas.painel_administrativo import ItemPainel


class CadastroRelatorio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cotacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    quantidade: int | None
    prazo_dias: int
    processo: str | None
    material: str | None
    observacoes_contratacao: str | None
    contratada_em: str
    encerrada_em: str | None
    cancelada_em: str | None
    ordem_criada_em: str | None
    ordem_iniciada_em: str | None
    ordem_concluida_em: str | None
    ordem_cancelada_em: str | None


class RegistroRelatorio(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origem: Literal["producao", "intermediacao", "financeiro"]
    registro_id: int
    versao: int | None = None
    data_utc: str
    acao: str
    descricao: str
    situacao: str | None = None
    responsavel: str | None = None
    usuario_admin_id: int | None = None
    empresa_fornecedora_id: int | None = None
    pagamento_id: int | None = None
    repasse_id: int | None = None
    valor: Decimal | None = None
    quantidade: int | None = None
    referencia: str | None = None
    registro_interno: str | None = None
    parecer_tecnico: str | None = None


class RelatorioContratacao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gerado_em: str
    resumo: ItemPainel
    cadastro: CadastroRelatorio
    recebimentos: list[MovimentoFinanceiro]
    repasses: list[MovimentoFinanceiro]
    linha_tempo: list[RegistroRelatorio]
    avisos: list[str]
