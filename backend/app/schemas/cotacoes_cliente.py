from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class CotacaoConsultaCliente(BaseModel):
    id: int
    solicitacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    status: str
    valor_total: Decimal
    prazo_dias: int
    validade_dias: int
    criada_em: datetime
    vencimento_em: datetime
    encerrada_em: datetime | None
    solicitacao_status: str
    processo_nome: str
    material_nome: str
    quantidade: int
    contratacao_id: int | None
    ordem_servico_id: int | None
    analise_cliente: str | None = None
    pode_analisar: bool = False
    versao_preco: str | None = None


class CotacoesConsultaClientePagina(BaseModel):
    contexto: str
    empresa_id: int
    consultado_em: datetime
    total: int
    por_status: dict[str, int]
    deslocamento: int
    limite: int
    itens: list[CotacaoConsultaCliente]


class CotacaoConsultaClienteDetalhe(BaseModel):
    contexto: str
    empresa_id: int
    consultado_em: datetime
    item: CotacaoConsultaCliente
