from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.models.empresa import Empresa
from backend.app.repositories.pagamento import RepositorioPagamento
from backend.app.schemas.pagamento import PagamentoContratacaoCriacao

CENTAVO = Decimal("0.01")
FORMAS_PAGAMENTO = {"pix", "transferencia", "boleto", "cartao", "dinheiro", "outro"}


class PagamentoContratacaoNaoEncontrada(LookupError):
    pass


class PagamentoContratacaoEmpresaNaoEncontrada(LookupError):
    pass


class PagamentoEmpresaNaoPodePagar(PermissionError):
    pass


class PagamentoContratacaoNaoPodeReceber(ValueError):
    pass


class PagamentoFormaInvalida(ValueError):
    pass


class PagamentoAcimaDoSaldo(ValueError):
    pass


class PagamentoJaCancelado(ValueError):
    pass


class PagamentoNaoEncontrado(LookupError):
    pass


class PagamentoEmpresaNaoPodeCancelar(PermissionError):
    pass


class PagamentoNaoPodeSerCancelado(ValueError):
    pass


class ServicoPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioPagamento(banco)

    @staticmethod
    def _agora_utc_sem_fuso() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _moeda(valor: Decimal) -> Decimal:
        return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    def _contratacao(self, contratacao_id: int) -> ContratacaoServico:
        item = self.banco.get(ContratacaoServico, contratacao_id)
        if item is None:
            raise PagamentoContratacaoNaoEncontrada
        return item

    def _validar_empresa_cliente(self, contratacao: ContratacaoServico, empresa_cliente_id: int) -> None:
        if contratacao.empresa_cliente_id != empresa_cliente_id:
            raise PagamentoEmpresaNaoPodePagar
        if self.banco.get(Empresa, empresa_cliente_id) is None:
            raise PagamentoContratacaoEmpresaNaoEncontrada

    def _total_pago(self, contratacao_id: int) -> Decimal:
        pagamentos = self.repositorio.listar_por_contratacao(contratacao_id)
        total = sum(
            (self._moeda(item.valor) for item in pagamentos if item.status == "confirmado"),
            Decimal("0.00"),
        )
        return self._moeda(total)

    def resumo(self, contratacao_id: int) -> tuple[ContratacaoServico, Decimal, Decimal, str, list[PagamentoContratacao]]:
        contratacao = self._contratacao(contratacao_id)
        total_pago = self._total_pago(contratacao_id)
        valor_contratado = self._moeda(contratacao.valor_total)
        saldo = self._moeda(valor_contratado - total_pago)
        if contratacao.status == "cancelada":
            status = "cancelado"
        elif total_pago == Decimal("0.00"):
            status = "pendente"
        elif total_pago < valor_contratado:
            status = "parcial"
        else:
            status = "pago"
        return contratacao, valor_contratado, total_pago, status, self.repositorio.listar_por_contratacao(contratacao_id)

    def registrar(self, contratacao_id: int, dados: PagamentoContratacaoCriacao) -> PagamentoContratacao:
        contratacao = self._contratacao(contratacao_id)
        self._validar_empresa_cliente(contratacao, dados.empresa_cliente_id)

        if contratacao.status == "cancelada":
            raise PagamentoContratacaoNaoPodeReceber
        if dados.forma_pagamento not in FORMAS_PAGAMENTO:
            raise PagamentoFormaInvalida

        valor = self._moeda(dados.valor)
        total_pago = self._total_pago(contratacao_id)
        saldo = self._moeda(contratacao.valor_total - total_pago)
        if valor > saldo:
            raise PagamentoAcimaDoSaldo
        if saldo <= Decimal("0.00"):
            raise PagamentoContratacaoNaoPodeReceber

        agora = self._agora_utc_sem_fuso()
        pagamento = PagamentoContratacao(
            contratacao_id=contratacao.id,
            empresa_cliente_id=contratacao.empresa_cliente_id,
            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,
            valor=valor,
            forma_pagamento=dados.forma_pagamento,
            status="confirmado",
            observacoes=dados.observacoes,
            criada_em=agora,
            paga_em=agora,
        )
        return self.repositorio.criar(pagamento)

    def obter(self, pagamento_id: int) -> PagamentoContratacao:
        item = self.repositorio.buscar(pagamento_id)
        if item is None:
            raise PagamentoNaoEncontrado
        return item

    def listar(self, contratacao_id: int) -> list[PagamentoContratacao]:
        self._contratacao(contratacao_id)
        return self.repositorio.listar_por_contratacao(contratacao_id)

    def cancelar(self, pagamento_id: int, empresa_cliente_id: int) -> PagamentoContratacao:
        item = self.obter(pagamento_id)
        contratacao = self._contratacao(item.contratacao_id)
        self._validar_empresa_cliente(contratacao, empresa_cliente_id)
        if item.status == "cancelado":
            raise PagamentoJaCancelado
        if contratacao.status == "cancelada":
            raise PagamentoNaoPodeSerCancelado
        item.status = "cancelado"
        item.cancelada_em = self._agora_utc_sem_fuso()
        self.banco.commit()
        self.banco.refresh(item)
        return item
