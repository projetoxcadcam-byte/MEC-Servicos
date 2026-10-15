from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

Forma = Literal["pix", "transferencia", "boleto", "cartao", "dinheiro", "outro"]
Acao = Literal["recebimento", "repasse", "estornar_recebimento", "estornar_repasse", "encerrar", "reabrir"]


class InicioFinanceiro(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    registro_interno: str = Field(min_length=3, max_length=2000)


class RegistroFinanceiro(InicioFinanceiro):
    acao: Acao
    versao: int = Field(strict=True, gt=0)
    chave_operacao: UUID
    valor: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    forma_pagamento: Forma | None = None
    referencia: str | None = Field(default=None, min_length=3, max_length=200)
    movimento_id: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def conferir_campos(self):
        novo = self.acao in {"recebimento", "repasse"}
        estorno = self.acao.startswith("estornar_")
        if novo and (self.valor is None or self.forma_pagamento is None or self.referencia is None):
            raise ValueError("Informe valor, forma de pagamento e referência do comprovante.")
        if estorno and (self.movimento_id is None or self.referencia is None):
            raise ValueError("Informe o movimento e a referência do estorno.")
        if not novo and (self.valor is not None or self.forma_pagamento is not None):
            raise ValueError("Esta ação não recebe valor ou forma de pagamento.")
        if not estorno and self.movimento_id is not None:
            raise ValueError("Esta ação não recebe movimento anterior.")
        if not novo and not estorno and self.referencia is not None:
            raise ValueError("Encerramento e reabertura usam apenas o registro interno.")
        return self


class ResumoFinanceiro(BaseModel):
    contratacao_id: int
    ordem_servico_id: int | None
    contratacao_status: str
    valor_contratado: Decimal
    valor_fornecedor: Decimal
    acrescimo_administracao: Decimal
    total_recebido: Decimal
    saldo_cliente: Decimal
    total_repassado: Decimal
    saldo_fornecedor: Decimal
    disponivel_repasse: Decimal
    entrega_concluida: bool
    status: str
    versao: int
    atualizado_em: str | None
    cliente: str
    fornecedor: str
    pode_iniciar: bool


class MovimentoFinanceiro(BaseModel):
    id: int
    tipo: str
    valor: Decimal
    forma_pagamento: str
    status: str
    registrado_em: str
    estornado_em: str | None


class EventoFinanceiroLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    versao: int
    acao: str
    pagamento_id: int | None
    repasse_id: int | None
    valor_centavos: int | None
    usuario_admin_id: int
    administrador_nome: str
    registro_interno: str
    referencia: str | None
    criado_em: str


class DetalheFinanceiro(BaseModel):
    resumo: ResumoFinanceiro
    acoes_permitidas: list[str]
    recebimentos: list[MovimentoFinanceiro]
    repasses: list[MovimentoFinanceiro]
    historico: list[EventoFinanceiroLeitura]


class PaginaFinanceiro(BaseModel):
    itens: list[ResumoFinanceiro]
    total: int
    deslocamento: int
    limite: int


class ConsultaFinanceiroPortal(BaseModel):
    contratacao_id: int
    ordem_servico_id: int | None
    valor_contratado: Decimal
    total_confirmado: Decimal
    saldo: Decimal
    status: str
    entrega_concluida: bool
    movimentos: list[MovimentoFinanceiro]


class PaginaFinanceiroPortal(BaseModel):
    itens: list[ConsultaFinanceiroPortal]
    total: int
    deslocamento: int
    limite: int
