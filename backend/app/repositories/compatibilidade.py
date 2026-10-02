from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.solicitacao import SolicitacaoServico


class RepositorioCompatibilidade:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def obter_solicitacao(self, solicitacao_id: int) -> SolicitacaoServico | None:
        return self.banco.get(SolicitacaoServico, solicitacao_id)

    def criar_solicitacao(self, solicitacao: SolicitacaoServico) -> SolicitacaoServico:
        self.banco.add(solicitacao)
        self.banco.commit()
        self.banco.refresh(solicitacao)
        return solicitacao

    def listar_solicitacoes_por_cliente(
        self,
        empresa_cliente_id: int,
    ) -> list[SolicitacaoServico]:
        consulta = (
            select(SolicitacaoServico)
            .where(
                SolicitacaoServico.empresa_cliente_id == empresa_cliente_id
            )
            .order_by(SolicitacaoServico.id.desc())
        )
        return list(self.banco.scalars(consulta).all())

    def listar_fornecedores_compativeis(
        self,
        solicitacao: SolicitacaoServico,
    ) -> list[tuple[Empresa, CapacidadeFornecedor]]:
        consulta = (
            select(Empresa, CapacidadeFornecedor)
            .join(
                CapacidadeFornecedor,
                CapacidadeFornecedor.empresa_id == Empresa.id,
            )
            .join(
                MaterialFornecedor,
                MaterialFornecedor.empresa_id == Empresa.id,
            )
            .where(
                Empresa.tipo_empresa.in_(("fornecedor", "ambos")),
                CapacidadeFornecedor.processo_id == solicitacao.processo_id,
                MaterialFornecedor.material_id == solicitacao.material_id,
                CapacidadeFornecedor.dimensao_x_maxima_mm
                >= solicitacao.dimensao_x_maxima_mm,
                CapacidadeFornecedor.dimensao_y_maxima_mm
                >= solicitacao.dimensao_y_maxima_mm,
                CapacidadeFornecedor.dimensao_z_maxima_mm
                >= solicitacao.dimensao_z_maxima_mm,
                CapacidadeFornecedor.tolerancia_minima_mm
                <= solicitacao.tolerancia_requerida_mm,
            )
            .order_by(Empresa.id)
        )
        return list(self.banco.execute(consulta).all())
