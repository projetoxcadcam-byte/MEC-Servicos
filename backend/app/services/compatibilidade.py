from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.empresa import Empresa
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.compatibilidade import RepositorioCompatibilidade
from backend.app.schemas.solicitacao import SolicitacaoServicoCriacao


class EmpresaNaoCliente(ValueError):
    pass


class ProcessoSolicitacaoNaoEncontrado(LookupError):
    pass


class MaterialSolicitacaoNaoEncontrado(LookupError):
    pass


class SolicitacaoNaoEncontrada(LookupError):
    pass


class ServicoCompatibilidade:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioCompatibilidade(banco)

    def criar_solicitacao(
        self,
        dados: SolicitacaoServicoCriacao,
    ) -> SolicitacaoServico:
        empresa = self.banco.get(Empresa, dados.empresa_cliente_id)
        if empresa is None:
            raise SolicitacaoNaoEncontrada(dados.empresa_cliente_id)

        if empresa.tipo_empresa not in {"cliente", "ambos"}:
            raise EmpresaNaoCliente(dados.empresa_cliente_id)

        from backend.app.models.material import Material
        from backend.app.models.processo import ProcessoFabricacao

        if self.banco.get(ProcessoFabricacao, dados.processo_id) is None:
            raise ProcessoSolicitacaoNaoEncontrado(dados.processo_id)

        if self.banco.get(Material, dados.material_id) is None:
            raise MaterialSolicitacaoNaoEncontrado(dados.material_id)

        solicitacao = SolicitacaoServico(
            empresa_cliente_id=dados.empresa_cliente_id,
            processo_id=dados.processo_id,
            material_id=dados.material_id,
            dimensao_x_maxima_mm=dados.dimensao_x_maxima_mm,
            dimensao_y_maxima_mm=dados.dimensao_y_maxima_mm,
            dimensao_z_maxima_mm=dados.dimensao_z_maxima_mm,
            tolerancia_requerida_mm=dados.tolerancia_requerida_mm,
            quantidade=dados.quantidade,
            observacoes=dados.observacoes,
        )

        try:
            return self.repositorio.criar_solicitacao(solicitacao)
        except IntegrityError:
            self.banco.rollback()
            raise

    def obter_solicitacao(self, solicitacao_id: int) -> SolicitacaoServico:
        solicitacao = self.repositorio.obter_solicitacao(solicitacao_id)
        if solicitacao is None:
            raise SolicitacaoNaoEncontrada(solicitacao_id)
        return solicitacao

    def listar_solicitacoes_por_cliente(
        self,
        empresa_cliente_id: int,
    ) -> list[SolicitacaoServico]:
        return self.repositorio.listar_solicitacoes_por_cliente(
            empresa_cliente_id
        )

    def listar_fornecedores_compativeis(
        self,
        solicitacao_id: int,
    ) -> list[tuple[Empresa, object]]:
        solicitacao = self.obter_solicitacao(solicitacao_id)
        return self.repositorio.listar_fornecedores_compativeis(solicitacao)
