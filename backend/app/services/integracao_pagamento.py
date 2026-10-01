from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.integracoes.pagamento import GatewayPagamentoFake, validar_assinatura_webhook
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.evento_gateway_pagamento import EventoGatewayPagamento
from backend.app.models.intencao_pagamento import IntencaoPagamento
from backend.app.repositories.intencao_pagamento import RepositorioEventoGatewayPagamento, RepositorioIntencaoPagamento
from backend.app.schemas.intencao_pagamento import IntencaoPagamentoCriacao, WebhookPagamento
from backend.app.schemas.pagamento import PagamentoContratacaoCriacao
from backend.app.services.pagamento import ServicoPagamento

CENTAVO = Decimal("0.01")
FORMAS_PAGAMENTO = {"pix", "transferencia", "boleto", "cartao", "dinheiro", "outro"}
EVENTOS = {"payment.succeeded", "payment.failed", "payment.cancelled"}


class IntegracaoContratacaoNaoEncontrada(LookupError):
    pass


class IntegracaoEmpresaNaoPodeIniciar(PermissionError):
    pass


class IntegracaoFormaInvalida(ValueError):
    pass


class IntegracaoContratacaoNaoPodeReceber(ValueError):
    pass


class IntegracaoValorAcimaDoSaldo(ValueError):
    pass


class IntegracaoIdempotencyInvalida(ValueError):
    pass


class IntegracaoIntencaoNaoEncontrada(LookupError):
    pass


class IntegracaoEventoInvalido(ValueError):
    pass


class IntegracaoProvedorNaoSuportado(ValueError):
    pass


class IntegracaoAssinaturaInvalida(PermissionError):
    pass


class IntegracaoPagamentoNaoPodeSerConfirmado(ValueError):
    pass


class ServicoIntegracaoPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioIntencaoPagamento(banco)
        self.eventos = RepositorioEventoGatewayPagamento(banco)
        self.gateway = GatewayPagamentoFake()

    @staticmethod
    def _agora() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _moeda(valor: Decimal) -> Decimal:
        return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    def _contratacao(self, contratacao_id: int) -> ContratacaoServico:
        item = self.banco.get(ContratacaoServico, contratacao_id)
        if item is None:
            raise IntegracaoContratacaoNaoEncontrada
        return item

    def iniciar(self, contratacao_id: int, dados: IntencaoPagamentoCriacao, idempotency_key: str) -> tuple[IntencaoPagamento, bool]:
        if not idempotency_key.strip():
            raise IntegracaoIdempotencyInvalida
        existente = self.repositorio.buscar_por_idempotency(idempotency_key)
        if existente is not None:
            return existente, True

        contratacao = self._contratacao(contratacao_id)
        if contratacao.empresa_cliente_id != dados.empresa_cliente_id:
            raise IntegracaoEmpresaNaoPodeIniciar
        if self.banco.get(Empresa, dados.empresa_cliente_id) is None:
            raise IntegracaoEmpresaNaoPodeIniciar
        if contratacao.status == "cancelada":
            raise IntegracaoContratacaoNaoPodeReceber
        if dados.forma_pagamento not in FORMAS_PAGAMENTO:
            raise IntegracaoFormaInvalida

        _, valor_contratado, total_pago, _, _ = ServicoPagamento(self.banco).resumo(contratacao_id)
        saldo = self._moeda(valor_contratado - total_pago)
        valor = self._moeda(dados.valor)
        if valor > saldo or saldo <= Decimal("0.00"):
            raise IntegracaoValorAcimaDoSaldo

        cobranca = self.gateway.criar_cobranca(
            valor=str(valor), forma_pagamento=dados.forma_pagamento, idempotency_key=idempotency_key
        )
        agora = self._agora()
        item = IntencaoPagamento(
            contratacao_id=contratacao.id,
            empresa_cliente_id=contratacao.empresa_cliente_id,
            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,
            valor=valor,
            forma_pagamento=dados.forma_pagamento,
            provedor=cobranca.provedor,
            idempotency_key=idempotency_key,
            external_payment_id=cobranca.external_payment_id,
            checkout_url=cobranca.checkout_url,
            status="aguardando_pagamento",
            observacoes=dados.observacoes,
            criada_em=agora,
            atualizada_em=agora,
        )
        return self.repositorio.criar(item), False

    def obter(self, intencao_id: int) -> IntencaoPagamento:
        item = self.repositorio.buscar(intencao_id)
        if item is None:
            raise IntegracaoIntencaoNaoEncontrada
        return item

    def webhook(self, provedor: str, dados: WebhookPagamento, assinatura: str) -> tuple[IntencaoPagamento, bool]:
        if provedor != "fake":
            raise IntegracaoProvedorNaoSuportado
        payload = dados.model_dump()
        if not validar_assinatura_webhook(payload, assinatura):
            raise IntegracaoAssinaturaInvalida
        if dados.tipo_evento not in EVENTOS:
            raise IntegracaoEventoInvalido

        existente_evento = self.eventos.buscar(provedor, dados.evento_id)
        if existente_evento is not None:
            return self.obter(existente_evento.intencao_pagamento_id), True

        item = self.repositorio.buscar_por_external_id(dados.external_payment_id)
        if item is None:
            raise IntegracaoIntencaoNaoEncontrada
        agora = self._agora()
        if item.provedor != provedor:
            raise IntegracaoProvedorNaoSuportado

        if dados.tipo_evento == "payment.succeeded":
            if item.status == "paga":
                raise IntegracaoPagamentoNaoPodeSerConfirmado
            if item.status != "aguardando_pagamento":
                raise IntegracaoPagamentoNaoPodeSerConfirmado
            pagamento = ServicoPagamento(self.banco).registrar(
                item.contratacao_id,
                PagamentoContratacaoCriacao(
                    empresa_cliente_id=item.empresa_cliente_id,
                    valor=item.valor,
                    forma_pagamento=item.forma_pagamento,
                    observacoes=f"Pagamento via gateway {item.provedor}; intent={item.id}.",
                ),
            )
            item.pagamento_id = pagamento.id
            item.status = "paga"
            item.paga_em = agora
        elif dados.tipo_evento == "payment.failed":
            if item.status != "aguardando_pagamento":
                raise IntegracaoPagamentoNaoPodeSerConfirmado
            item.status = "falhou"
        else:
            if item.status != "aguardando_pagamento":
                raise IntegracaoPagamentoNaoPodeSerConfirmado
            item.status = "cancelada"
            item.cancelada_em = agora

        item.atualizada_em = agora
        evento = EventoGatewayPagamento(
            provedor=provedor,
            evento_id=dados.evento_id,
            intencao_pagamento_id=item.id,
            external_payment_id=item.external_payment_id,
            tipo_evento=dados.tipo_evento,
            status_processamento="processado",
            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            recebido_em=agora,
            processado_em=agora,
        )
        self.banco.add(evento)
        self.banco.commit()
        self.banco.refresh(item)
        return item, False
