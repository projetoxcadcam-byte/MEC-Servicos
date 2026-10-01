from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.ordem_servico import RepositorioOrdemServico
from backend.app.schemas.ordem_servico import OrdemServicoAcao, OrdemServicoCriacao


class OrdemServicoNaoEncontrada(Exception):
    pass


class ContratacaoNaoEncontradaParaOS(Exception):
    pass


class ContratacaoNaoAtiva(Exception):
    pass


class EmpresaNaoPodeOperarOS(Exception):
    pass


class OrdemServicoDuplicada(Exception):
    pass


class OrdemServicoNaoPodeSerIniciada(Exception):
    pass


class OrdemServicoNaoPodeSerConcluida(Exception):
    pass


class OrdemServicoNaoPodeSerCancelada(Exception):
    pass


class ServicoOrdemServico:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioOrdemServico(banco)

    def _contratacao(self, contratacao_id: int) -> ContratacaoServico:
        item = self.banco.get(ContratacaoServico, contratacao_id)
        if item is None:
            raise ContratacaoNaoEncontradaParaOS
        return item

    @staticmethod
    def _cliente_contratacao(item: ContratacaoServico, empresa_id: int) -> None:
        if item.empresa_cliente_id != empresa_id:
            raise EmpresaNaoPodeOperarOS

    @staticmethod
    def _cliente_ordem(item: OrdemServico, empresa_id: int) -> None:
        if item.empresa_cliente_id != empresa_id:
            raise EmpresaNaoPodeOperarOS

    def criar(self, contratacao_id: int, dados: OrdemServicoCriacao) -> OrdemServico:
        contratacao = self._contratacao(contratacao_id)
        self._cliente_contratacao(contratacao, dados.empresa_cliente_id)

        if contratacao.status != "ativa":
            raise ContratacaoNaoAtiva

        if self.repositorio.buscar_por_contratacao(contratacao_id) is not None:
            raise OrdemServicoDuplicada

        solicitacao = self.banco.get(SolicitacaoServico, contratacao.solicitacao_id)
        if solicitacao is None:
            raise ContratacaoNaoEncontradaParaOS

        ordem = OrdemServico(
            contratacao_id=contratacao.id,
            solicitacao_id=contratacao.solicitacao_id,
            cotacao_id=contratacao.cotacao_id,
            empresa_cliente_id=contratacao.empresa_cliente_id,
            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,
            processo_id=solicitacao.processo_id,
            material_id=solicitacao.material_id,
            quantidade=solicitacao.quantidade,
            valor_total=contratacao.valor_total,
            prazo_dias=contratacao.prazo_dias,
            status="aberta",
            observacoes=contratacao.observacoes,
        )
        try:
            return self.repositorio.criar(ordem)
        except IntegrityError as exc:
            self.banco.rollback()
            raise OrdemServicoDuplicada from exc

    def obter(self, ordem_id: int) -> OrdemServico:
        item = self.repositorio.buscar(ordem_id)
        if item is None:
            raise OrdemServicoNaoEncontrada
        return item

    def listar(self) -> list[OrdemServico]:
        return self.repositorio.listar()

    def iniciar(self, ordem_id: int, dados: OrdemServicoAcao) -> OrdemServico:
        item = self.obter(ordem_id)
        self._cliente_ordem(item, dados.empresa_cliente_id)
        if item.status != "aberta":
            raise OrdemServicoNaoPodeSerIniciada
        item.status = "em_execucao"
        item.iniciada_em = datetime.utcnow()
        if dados.observacoes is not None:
            item.observacoes = dados.observacoes
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def concluir(self, ordem_id: int, dados: OrdemServicoAcao) -> OrdemServico:
        item = self.obter(ordem_id)
        self._cliente_ordem(item, dados.empresa_cliente_id)
        if item.status != "em_execucao":
            raise OrdemServicoNaoPodeSerConcluida
        item.status = "concluida"
        item.concluida_em = datetime.utcnow()
        if dados.observacoes is not None:
            item.observacoes = dados.observacoes
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def cancelar(self, ordem_id: int, dados: OrdemServicoAcao) -> OrdemServico:
        item = self.obter(ordem_id)
        self._cliente_ordem(item, dados.empresa_cliente_id)
        if item.status in {"concluida", "cancelada"}:
            raise OrdemServicoNaoPodeSerCancelada
        item.status = "cancelada"
        item.cancelada_em = datetime.utcnow()
        if dados.observacoes is not None:
            item.observacoes = dados.observacoes
        self.banco.commit()
        self.banco.refresh(item)
        return item
