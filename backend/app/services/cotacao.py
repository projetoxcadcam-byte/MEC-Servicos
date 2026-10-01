from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.cotacao import RepositorioCotacao
from backend.app.schemas.cotacao import CotacaoCriacao
from backend.app.services.compatibilidade import ServicoCompatibilidade


class CotacaoSolicitacaoNaoEncontrada(LookupError):
    pass


class CotacaoEmpresaNaoEncontrada(LookupError):
    pass


class CotacaoEmpresaNaoFornecedor(ValueError):
    pass


class CotacaoFornecedorIncompativel(ValueError):
    pass


class CotacaoDuplicada(ValueError):
    pass


class CotacaoNaoEncontrada(LookupError):
    pass


class CotacaoNaoPendente(ValueError):
    pass


class CotacaoExpirada(ValueError):
    pass


class EmpresaNaoPodeDecidir(PermissionError):
    pass


class SolicitacaoJaPossuiCotacaoAceita(ValueError):
    pass


class ServicoCotacao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioCotacao(banco)

    @staticmethod
    def _agora_utc_sem_fuso() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalizar_data(data: datetime) -> datetime:
        if data.tzinfo is None:
            return data
        return data.astimezone(timezone.utc).replace(tzinfo=None)

    def _atualizar_expiradas(self, solicitacao_id: int) -> None:
        agora = self._agora_utc_sem_fuso()
        alterou = False

        for cotacao in self.repositorio.listar_pendentes(solicitacao_id):
            criada = self._normalizar_data(cotacao.criada_em)
            vencimento = criada + timedelta(days=cotacao.validade_dias)
            if agora >= vencimento:
                cotacao.status = "expirada"
                cotacao.encerrada_em = agora
                cotacao.decidida_por_empresa_id = None
                alterou = True

        if alterou:
            self.banco.commit()

    def criar(
        self,
        solicitacao_id: int,
        dados: CotacaoCriacao,
    ) -> CotacaoFornecedor:
        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)
        if solicitacao is None:
            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)

        self._atualizar_expiradas(solicitacao_id)

        if self.repositorio.listar_aceitas(solicitacao_id):
            raise SolicitacaoJaPossuiCotacaoAceita(solicitacao_id)

        empresa = self.banco.get(Empresa, dados.empresa_fornecedora_id)
        if empresa is None:
            raise CotacaoEmpresaNaoEncontrada(
                dados.empresa_fornecedora_id
            )

        if empresa.tipo_empresa not in {"fornecedor", "ambos"}:
            raise CotacaoEmpresaNaoFornecedor(
                dados.empresa_fornecedora_id
            )

        fornecedores_compativeis = (
            ServicoCompatibilidade(self.banco)
            .listar_fornecedores_compativeis(solicitacao_id)
        )
        ids_compativeis = {
            fornecedor.id
            for fornecedor, _capacidade in fornecedores_compativeis
        }

        if empresa.id not in ids_compativeis:
            raise CotacaoFornecedorIncompativel(
                dados.empresa_fornecedora_id
            )

        cotacao = CotacaoFornecedor(
            solicitacao_id=solicitacao_id,
            empresa_fornecedora_id=dados.empresa_fornecedora_id,
            valor_total=dados.valor_total,
            prazo_dias=dados.prazo_dias,
            validade_dias=dados.validade_dias,
            observacoes=dados.observacoes,
        )

        try:
            return self.repositorio.criar(cotacao)
        except IntegrityError as exc:
            self.banco.rollback()
            raise CotacaoDuplicada from exc

    def listar(
        self,
        solicitacao_id: int,
    ) -> list[CotacaoFornecedor]:
        if self.banco.get(SolicitacaoServico, solicitacao_id) is None:
            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)

        self._atualizar_expiradas(solicitacao_id)
        return self.repositorio.listar_por_solicitacao(solicitacao_id)

    def _validar_decisor(
        self,
        solicitacao: SolicitacaoServico,
        empresa_cliente_id: int,
    ) -> None:
        if solicitacao.empresa_cliente_id != empresa_cliente_id:
            raise EmpresaNaoPodeDecidir(empresa_cliente_id)

        empresa = self.banco.get(Empresa, empresa_cliente_id)
        if empresa is None:
            raise EmpresaNaoPodeDecidir(empresa_cliente_id)

    def aceitar(
        self,
        solicitacao_id: int,
        cotacao_id: int,
        empresa_cliente_id: int,
    ) -> CotacaoFornecedor:
        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)
        if solicitacao is None:
            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)

        self._validar_decisor(solicitacao, empresa_cliente_id)
        self._atualizar_expiradas(solicitacao_id)

        cotacao = self.repositorio.buscar(solicitacao_id, cotacao_id)
        if cotacao is None:
            raise CotacaoNaoEncontrada(cotacao_id)

        if cotacao.status == "expirada":
            raise CotacaoExpirada(cotacao_id)
        if cotacao.status != "enviada":
            raise CotacaoNaoPendente(cotacao_id)

        outras_aceitas = [
            item
            for item in self.repositorio.listar_aceitas(solicitacao_id)
            if item.id != cotacao_id
        ]
        if outras_aceitas:
            raise SolicitacaoJaPossuiCotacaoAceita(solicitacao_id)

        agora = self._agora_utc_sem_fuso()
        cotacao.status = "aceita"
        cotacao.encerrada_em = agora
        cotacao.decidida_por_empresa_id = empresa_cliente_id

        for outra in self.repositorio.listar_pendentes(solicitacao_id):
            if outra.id == cotacao.id:
                continue
            outra.status = "recusada"
            outra.encerrada_em = agora
            outra.decidida_por_empresa_id = empresa_cliente_id

        self.banco.commit()
        self.banco.refresh(cotacao)
        return cotacao

    def recusar(
        self,
        solicitacao_id: int,
        cotacao_id: int,
        empresa_cliente_id: int,
    ) -> CotacaoFornecedor:
        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)
        if solicitacao is None:
            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)

        self._validar_decisor(solicitacao, empresa_cliente_id)
        self._atualizar_expiradas(solicitacao_id)

        cotacao = self.repositorio.buscar(solicitacao_id, cotacao_id)
        if cotacao is None:
            raise CotacaoNaoEncontrada(cotacao_id)

        if cotacao.status == "expirada":
            raise CotacaoExpirada(cotacao_id)
        if cotacao.status != "enviada":
            raise CotacaoNaoPendente(cotacao_id)

        agora = self._agora_utc_sem_fuso()
        cotacao.status = "recusada"
        cotacao.encerrada_em = agora
        cotacao.decidida_por_empresa_id = empresa_cliente_id

        self.banco.commit()
        self.banco.refresh(cotacao)
        return cotacao
