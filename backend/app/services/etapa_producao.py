from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.repositories.etapa_producao import RepositorioEtapaProducao
from backend.app.schemas.etapa_producao import (
    AcompanhamentoProducaoLeitura,
    EtapaProducaoCriacao,
)


class OrdemServicoNaoEncontradaParaProducao(Exception):
    pass


class EmpresaFornecedoraNaoPodeAtualizarProducao(Exception):
    pass


class OrdemServicoNaoPodeAtualizarProducao(Exception):
    pass


class ServicoEtapaProducao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioEtapaProducao(banco)

    def _ordem(self, ordem_servico_id: int) -> OrdemServico:
        item = self.banco.get(OrdemServico, ordem_servico_id)
        if item is None:
            raise OrdemServicoNaoEncontradaParaProducao
        return item

    @staticmethod
    def _fornecedor_pode_operar(
        ordem: OrdemServico,
        empresa_fornecedora_id: int,
    ) -> None:
        if ordem.empresa_fornecedora_id != empresa_fornecedora_id:
            raise EmpresaFornecedoraNaoPodeAtualizarProducao

    def registrar(
        self,
        ordem_servico_id: int,
        dados: EtapaProducaoCriacao,
    ) -> EtapaProducao:
        ordem = self._ordem(ordem_servico_id)
        self._fornecedor_pode_operar(
            ordem,
            dados.empresa_fornecedora_id,
        )

        if ordem.status in {"concluida", "cancelada"}:
            raise OrdemServicoNaoPodeAtualizarProducao

        item = EtapaProducao(
            ordem_servico_id=ordem.id,
            empresa_fornecedora_id=ordem.empresa_fornecedora_id,
            etapa=dados.etapa,
            observacoes=dados.observacoes,
        )
        return self.repositorio.criar(item)

    def acompanhamento(
        self,
        ordem_servico_id: int,
    ) -> AcompanhamentoProducaoLeitura:
        ordem = self._ordem(ordem_servico_id)
        historico = self.repositorio.listar_por_ordem(ordem.id)
        atual = historico[-1].etapa if historico else None
        return AcompanhamentoProducaoLeitura(
            ordem_servico_id=ordem.id,
            etapa_atual=atual,
            historico=historico,
        )

    def listar(self, ordem_servico_id: int) -> list[EtapaProducao]:
        ordem = self._ordem(ordem_servico_id)
        return self.repositorio.listar_por_ordem(ordem.id)
