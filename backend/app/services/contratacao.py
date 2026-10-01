from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.contratacao import RepositorioContratacao
from backend.app.schemas.contratacao import ContratacaoCriacao


class ContratacaoSolicitacaoNaoEncontrada(LookupError):
    pass


class ContratacaoCotacaoNaoEncontrada(LookupError):
    pass


class ContratacaoCotacaoNaoAceita(ValueError):
    pass


class ContratacaoSolicitacaoNaoAberta(ValueError):
    pass


class ContratacaoEmpresaNaoPodeContratar(PermissionError):
    pass


class ContratacaoJaExiste(ValueError):
    pass


class ContratacaoNaoEncontrada(LookupError):
    pass


class ContratacaoNaoAtiva(ValueError):
    pass


class ServicoContratacao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioContratacao(banco)

    @staticmethod
    def _agora_utc_sem_fuso() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def criar(
        self,
        solicitacao_id: int,
        dados: ContratacaoCriacao,
    ) -> ContratacaoServico:
        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)
        if solicitacao is None:
            raise ContratacaoSolicitacaoNaoEncontrada(solicitacao_id)

        if solicitacao.empresa_cliente_id != dados.empresa_cliente_id:
            raise ContratacaoEmpresaNaoPodeContratar(dados.empresa_cliente_id)

        if self.repositorio.buscar_por_solicitacao(solicitacao_id) is not None:
            raise ContratacaoJaExiste(solicitacao_id)

        if solicitacao.status != "aberta":
            raise ContratacaoSolicitacaoNaoAberta(solicitacao_id)

        cotacao = self.banco.get(CotacaoFornecedor, dados.cotacao_id)
        if cotacao is None or cotacao.solicitacao_id != solicitacao_id:
            raise ContratacaoCotacaoNaoEncontrada(dados.cotacao_id)

        if cotacao.status != "aceita":
            raise ContratacaoCotacaoNaoAceita(dados.cotacao_id)

        if cotacao.decidida_por_empresa_id != dados.empresa_cliente_id:
            raise ContratacaoEmpresaNaoPodeContratar(dados.empresa_cliente_id)

        contratacao = ContratacaoServico(
            solicitacao_id=solicitacao_id,
            cotacao_id=cotacao.id,
            empresa_cliente_id=solicitacao.empresa_cliente_id,
            empresa_fornecedora_id=cotacao.empresa_fornecedora_id,
            valor_total=cotacao.valor_total,
            prazo_dias=cotacao.prazo_dias,
            observacoes=dados.observacoes,
            status="ativa",
        )

        solicitacao.status = "encerrada"

        try:
            return self.repositorio.criar(contratacao)
        except IntegrityError as exc:
            self.banco.rollback()
            raise ContratacaoJaExiste(solicitacao_id) from exc

    def obter(self, solicitacao_id: int) -> ContratacaoServico:
        contratacao = self.repositorio.buscar_por_solicitacao(solicitacao_id)
        if contratacao is None:
            raise ContratacaoNaoEncontrada(solicitacao_id)
        return contratacao

    def cancelar(
        self,
        solicitacao_id: int,
        empresa_cliente_id: int,
    ) -> ContratacaoServico:
        contratacao = self.repositorio.buscar_por_solicitacao(solicitacao_id)
        if contratacao is None:
            raise ContratacaoNaoEncontrada(solicitacao_id)

        if contratacao.empresa_cliente_id != empresa_cliente_id:
            raise ContratacaoEmpresaNaoPodeContratar(empresa_cliente_id)

        if contratacao.status != "ativa":
            raise ContratacaoNaoAtiva(contratacao.id)

        contratacao.status = "cancelada"
        contratacao.cancelada_em = self._agora_utc_sem_fuso()
        self.banco.commit()
        self.banco.refresh(contratacao)
        return contratacao
