from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, aliased

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.ordem_servico import OrdemServicoLeitura
from backend.app.schemas.portal_ordens_servico import (
    ContratacoesParaOrdemPagina, OrdemPortalLeitura, OrdensPortalPagina,
)
from backend.app.services.portal_contratacoes import Perfil, ServicoPortalContratacoes


class ServicoPortalOrdens:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.contratos = ServicoPortalContratacoes(banco)

    @staticmethod
    def _dono(empresa_id: int, perfil: Perfil):
        coluna = OrdemServico.empresa_cliente_id if perfil == "cliente" else OrdemServico.empresa_fornecedora_id
        return coluna == empresa_id

    @staticmethod
    def _consulta():
        cliente, fornecedor = aliased(Empresa), aliased(Empresa)
        processo_pedido, material_pedido = aliased(ProcessoFabricacao), aliased(Material)
        return (
            select(OrdemServico, ContratacaoServico.status, SolicitacaoServico,
                   cliente.razao_social, fornecedor.razao_social, ProcessoFabricacao.nome, Material.nome,
                   processo_pedido.nome, material_pedido.nome)
            .join(ContratacaoServico, ContratacaoServico.id == OrdemServico.contratacao_id)
            .join(SolicitacaoServico, SolicitacaoServico.id == OrdemServico.solicitacao_id)
            .join(cliente, cliente.id == OrdemServico.empresa_cliente_id)
            .join(fornecedor, fornecedor.id == OrdemServico.empresa_fornecedora_id)
            .join(ProcessoFabricacao, ProcessoFabricacao.id == OrdemServico.processo_id)
            .join(Material, Material.id == OrdemServico.material_id)
            .join(processo_pedido, processo_pedido.id == SolicitacaoServico.processo_id)
            .join(material_pedido, material_pedido.id == SolicitacaoServico.material_id)
        )

    @staticmethod
    def _ordem(linha) -> OrdemPortalLeitura:
        ordem, contrato_status, solicitacao, cliente, fornecedor, processo, material, processo_pedido, material_pedido = linha
        return OrdemPortalLeitura(
            **OrdemServicoLeitura.model_validate(ordem).model_dump(),
            cliente_razao_social=cliente, fornecedor_razao_social=fornecedor,
            processo_nome=processo, material_nome=material, contratacao_status=contrato_status,
            solicitacao=ServicoPortalContratacoes._solicitacao(solicitacao, cliente, processo_pedido, material_pedido),
        )

    def listar(self, empresa_id: int, perfil: Perfil, deslocamento: int, limite: int) -> OrdensPortalPagina:
        self.contratos.validar_empresa(empresa_id, perfil)
        consulta = self._consulta().where(self._dono(empresa_id, perfil))
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return OrdensPortalPagina(itens=[self._ordem(linha) for linha in linhas], total=total,
                                 deslocamento=deslocamento, limite=limite)

    def obter(self, ordem_id: int, empresa_id: int, perfil: Perfil) -> OrdemPortalLeitura:
        self.contratos.validar_empresa(empresa_id, perfil)
        linha = self.banco.execute(self._consulta().where(
            OrdemServico.id == ordem_id, self._dono(empresa_id, perfil),
        )).first()
        if linha is None:
            raise HTTPException(404, detail="ordem_servico_nao_encontrada")
        return self._ordem(linha)

    def contratacoes_para_gerar(self, empresa_id: int, deslocamento: int, limite: int) -> ContratacoesParaOrdemPagina:
        self.contratos.validar_empresa(empresa_id, "cliente")
        existe = select(OrdemServico.id).where(
            OrdemServico.contratacao_id == ContratacaoServico.id,
        ).correlate(ContratacaoServico).exists()
        consulta = self.contratos._consulta_contratacoes().where(
            ContratacaoServico.empresa_cliente_id == empresa_id, ContratacaoServico.status == "ativa", ~existe,
        )
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(ContratacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return ContratacoesParaOrdemPagina(itens=[self.contratos._contratacao(linha) for linha in linhas],
                                          total=total, deslocamento=deslocamento, limite=limite)

    def executar(self, ordem_id: int, empresa_id: int, acao: Literal["iniciar", "concluir"]) -> OrdemPortalLeitura:
        ordem = self.obter(ordem_id, empresa_id, "fornecedor")
        if ordem.contratacao_status != "ativa":
            raise HTTPException(409, detail="contratacao_nao_esta_ativa")
        antes, depois, campo, erro = (
            ("aberta", "em_execucao", "iniciada_em", "ordem_servico_nao_pode_ser_iniciada") if acao == "iniciar"
            else ("em_execucao", "concluida", "concluida_em", "ordem_servico_nao_pode_ser_concluida")
        )
        if ordem.status != antes:
            raise HTTPException(409, detail=erro)
        contrato_ativo = select(ContratacaoServico.id).where(
            ContratacaoServico.id == OrdemServico.contratacao_id,
            ContratacaoServico.status == "ativa",
            ContratacaoServico.empresa_fornecedora_id == empresa_id,
        ).correlate(OrdemServico).exists()
        resultado = self.banco.execute(update(OrdemServico).where(
            OrdemServico.id == ordem_id, OrdemServico.empresa_fornecedora_id == empresa_id,
            OrdemServico.status == antes, contrato_ativo,
        ).values(**{ "status": depois, campo: datetime.now(timezone.utc).replace(tzinfo=None) }),
            execution_options={"synchronize_session": False})
        if resultado.rowcount != 1:
            self.banco.rollback()
            raise HTTPException(409, detail="ordem_servico_alterada_atualize")
        self.banco.commit()
        self.banco.expire_all()
        return self.obter(ordem_id, empresa_id, "fornecedor")
