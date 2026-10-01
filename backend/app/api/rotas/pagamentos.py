from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.pagamento import (
    PagamentoContratacaoCancelamento,
    PagamentoContratacaoCriacao,
    PagamentoContratacaoLeitura,
    ResumoFinanceiroLeitura,
)
from backend.app.services.pagamento import (
    PagamentoAcimaDoSaldo,
    PagamentoContratacaoEmpresaNaoEncontrada,
    PagamentoContratacaoNaoEncontrada,
    PagamentoContratacaoNaoPodeReceber,
    PagamentoEmpresaNaoPodeCancelar,
    PagamentoEmpresaNaoPodePagar,
    PagamentoFormaInvalida,
    PagamentoJaCancelado,
    PagamentoNaoEncontrado,
    PagamentoNaoPodeSerCancelado,
    ServicoPagamento,
)

roteador = APIRouter(prefix="/contratacoes", tags=["pagamentos"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


def _erro(exc: Exception) -> None:
    raise exc


@roteador.post("/{contratacao_id}/pagamentos", response_model=PagamentoContratacaoLeitura, status_code=status.HTTP_201_CREATED)
def registrar_pagamento(contratacao_id: int, dados: PagamentoContratacaoCriacao, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).registrar(contratacao_id, dados)
    except PagamentoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc
    except PagamentoEmpresaNaoPodePagar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except PagamentoContratacaoEmpresaNaoEncontrada as exc:
        raise HTTPException(404, "empresa_cliente_nao_encontrada") from exc
    except PagamentoContratacaoNaoPodeReceber as exc:
        raise HTTPException(409, "contratacao_nao_pode_receber_pagamento") from exc
    except PagamentoFormaInvalida as exc:
        raise HTTPException(422, "forma_pagamento_invalida") from exc
    except PagamentoAcimaDoSaldo as exc:
        raise HTTPException(409, "pagamento_acima_do_saldo") from exc


@roteador.get("/{contratacao_id}/pagamentos", response_model=list[PagamentoContratacaoLeitura])
def listar_pagamentos(contratacao_id: int, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).listar(contratacao_id)
    except PagamentoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc


@roteador.get("/{contratacao_id}/financeiro", response_model=ResumoFinanceiroLeitura)
def resumo_financeiro(contratacao_id: int, banco: SessaoBanco):
    try:
        contratacao, valor_contratado, total_pago, status_pagamento, pagamentos = ServicoPagamento(banco).resumo(contratacao_id)
    except PagamentoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc
    return ResumoFinanceiroLeitura(
        contratacao_id=contratacao.id,
        valor_contratado=valor_contratado,
        total_pago=total_pago,
        saldo=valor_contratado - total_pago,
        status_pagamento=status_pagamento,
        pagamentos=pagamentos,
    )


@roteador.get("/pagamentos/{pagamento_id}", response_model=PagamentoContratacaoLeitura)
def obter_pagamento(pagamento_id: int, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).obter(pagamento_id)
    except PagamentoNaoEncontrado as exc:
        raise HTTPException(404, "pagamento_nao_encontrado") from exc


@roteador.post("/pagamentos/{pagamento_id}/cancelar", response_model=PagamentoContratacaoLeitura)
def cancelar_pagamento(pagamento_id: int, dados: PagamentoContratacaoCancelamento, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).cancelar(pagamento_id, dados.empresa_cliente_id)
    except PagamentoNaoEncontrado as exc:
        raise HTTPException(404, "pagamento_nao_encontrado") from exc
    except PagamentoEmpresaNaoPodeCancelar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except PagamentoEmpresaNaoPodePagar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except PagamentoJaCancelado as exc:
        raise HTTPException(409, "pagamento_ja_cancelado") from exc
    except PagamentoNaoPodeSerCancelado as exc:
        raise HTTPException(409, "pagamento_nao_pode_ser_cancelado") from exc
