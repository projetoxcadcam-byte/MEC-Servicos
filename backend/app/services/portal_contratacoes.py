from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.contratacao import ContratacaoLeitura
from backend.app.schemas.cotacao import CotacaoLeitura
from backend.app.schemas.portal_contratacoes import (
    ContratacaoPortalLeitura, ContratacoesPortalPagina,
    CotacaoParaContratarLeitura, CotacoesParaContratarPagina,
    SolicitacaoContratacaoLeitura,
)
from backend.app.schemas.solicitacao import SolicitacaoServicoLeitura

Perfil = Literal["cliente", "fornecedor"]


class ServicoPortalContratacoes:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def validar_empresa(self, empresa_id: int, perfil: Perfil) -> Empresa:
        empresa = self.banco.get(Empresa, empresa_id)
        if empresa is None:
            raise HTTPException(404, detail=f"empresa_{perfil}_nao_encontrada")
        if empresa.tipo_empresa not in {perfil, "ambos"}:
            raise HTTPException(403, detail=f"empresa_nao_e_{perfil}")
        return empresa

    @staticmethod
    def _solicitacao(item, cliente: str, processo: str, material: str) -> SolicitacaoContratacaoLeitura:
        return SolicitacaoContratacaoLeitura(
            **SolicitacaoServicoLeitura.model_validate(item).model_dump(),
            cliente_razao_social=cliente, processo_nome=processo, material_nome=material,
        )

    @staticmethod
    def _consulta_contratacoes():
        cliente, fornecedor = aliased(Empresa), aliased(Empresa)
        return (
            select(ContratacaoServico, SolicitacaoServico, cliente.razao_social,
                   fornecedor.razao_social, ProcessoFabricacao.nome, Material.nome)
            .join(SolicitacaoServico, SolicitacaoServico.id == ContratacaoServico.solicitacao_id)
            .join(cliente, cliente.id == ContratacaoServico.empresa_cliente_id)
            .join(fornecedor, fornecedor.id == ContratacaoServico.empresa_fornecedora_id)
            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)
            .join(Material, Material.id == SolicitacaoServico.material_id)
        )

    @classmethod
    def _contratacao(cls, linha) -> ContratacaoPortalLeitura:
        contrato, solicitacao, cliente, fornecedor, processo, material = linha
        return ContratacaoPortalLeitura(
            **ContratacaoLeitura.model_validate(contrato).model_dump(),
            cliente_razao_social=cliente, fornecedor_razao_social=fornecedor,
            solicitacao=cls._solicitacao(solicitacao, cliente, processo, material),
        )

    @staticmethod
    def _dono(empresa_id: int, perfil: Perfil):
        coluna = (ContratacaoServico.empresa_cliente_id if perfil == "cliente"
                  else ContratacaoServico.empresa_fornecedora_id)
        return coluna == empresa_id

    def listar_contratacoes(self, empresa_id: int, perfil: Perfil, deslocamento: int, limite: int) -> ContratacoesPortalPagina:
        self.validar_empresa(empresa_id, perfil)
        consulta = self._consulta_contratacoes().where(self._dono(empresa_id, perfil))
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(ContratacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return ContratacoesPortalPagina(
            itens=[self._contratacao(linha) for linha in linhas], total=total,
            deslocamento=deslocamento, limite=limite,
        )

    def obter_contratacao(self, contratacao_id: int, empresa_id: int, perfil: Perfil) -> ContratacaoPortalLeitura:
        self.validar_empresa(empresa_id, perfil)
        consulta = self._consulta_contratacoes().where(
            ContratacaoServico.id == contratacao_id, self._dono(empresa_id, perfil),
        )
        linha = self.banco.execute(consulta).first()
        if linha is None:
            raise HTTPException(404, detail="contratacao_nao_encontrada")
        return self._contratacao(linha)

    def listar_cotacoes_para_contratar(self, empresa_id: int, deslocamento: int, limite: int) -> CotacoesParaContratarPagina:
        self.validar_empresa(empresa_id, "cliente")
        cliente, fornecedor = aliased(Empresa), aliased(Empresa)
        existe = select(ContratacaoServico.id).where(
            ContratacaoServico.solicitacao_id == SolicitacaoServico.id,
        ).correlate(SolicitacaoServico).exists()
        consulta = (
            select(CotacaoFornecedor, SolicitacaoServico, cliente.razao_social,
                   fornecedor.razao_social, ProcessoFabricacao.nome, Material.nome)
            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)
            .join(cliente, cliente.id == SolicitacaoServico.empresa_cliente_id)
            .join(fornecedor, fornecedor.id == CotacaoFornecedor.empresa_fornecedora_id)
            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)
            .join(Material, Material.id == SolicitacaoServico.material_id)
            .where(SolicitacaoServico.empresa_cliente_id == empresa_id,
                   SolicitacaoServico.status == "aberta", CotacaoFornecedor.status == "aceita",
                   CotacaoFornecedor.decidida_por_empresa_id == empresa_id, ~existe)
        )
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(CotacaoFornecedor.id.desc()).offset(deslocamento).limit(limite)).all()
        itens = [CotacaoParaContratarLeitura(
            **CotacaoLeitura.model_validate(cotacao).model_dump(), fornecedor_razao_social=fornecedor_nome,
            solicitacao=self._solicitacao(solicitacao, cliente_nome, processo, material),
        ) for cotacao, solicitacao, cliente_nome, fornecedor_nome, processo, material in linhas]
        return CotacoesParaContratarPagina(itens=itens, total=total, deslocamento=deslocamento, limite=limite)
