from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.cotacao import CotacaoLeitura
from backend.app.schemas.portal_fornecedor import (
    CotacaoFornecedorLeitura,
    CotacoesFornecedorLeitura,
    OportunidadesFornecedorLeitura,
    SolicitacaoFornecedorLeitura,
)
from backend.app.schemas.solicitacao import SolicitacaoServicoLeitura
from backend.app.services.cotacao import ServicoCotacao


class ServicoPortalFornecedor:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def validar_fornecedor(self, empresa_id: int) -> Empresa:
        empresa = self.banco.get(Empresa, empresa_id)
        if empresa is None:
            raise HTTPException(404, detail="empresa_fornecedora_nao_encontrada")
        if empresa.tipo_empresa not in {"fornecedor", "ambos"}:
            raise HTTPException(409, detail="empresa_nao_e_fornecedora")
        return empresa

    @staticmethod
    def _compativel(empresa_id: int):
        # Mesmas comparações do RepositorioCompatibilidade, com os eixos na
        # ordem cadastrada. EXISTS impede que vínculos multipliquem resultados.
        return (
            select(CapacidadeFornecedor.id)
            .join(MaterialFornecedor, MaterialFornecedor.empresa_id == CapacidadeFornecedor.empresa_id)
            .where(
                CapacidadeFornecedor.empresa_id == empresa_id,
                CapacidadeFornecedor.processo_id == SolicitacaoServico.processo_id,
                MaterialFornecedor.material_id == SolicitacaoServico.material_id,
                CapacidadeFornecedor.dimensao_x_maxima_mm >= SolicitacaoServico.dimensao_x_maxima_mm,
                CapacidadeFornecedor.dimensao_y_maxima_mm >= SolicitacaoServico.dimensao_y_maxima_mm,
                CapacidadeFornecedor.dimensao_z_maxima_mm >= SolicitacaoServico.dimensao_z_maxima_mm,
                CapacidadeFornecedor.tolerancia_minima_mm <= SolicitacaoServico.tolerancia_requerida_mm,
            )
            .correlate(SolicitacaoServico)
            .exists()
        )

    @staticmethod
    def _nomes(consulta):
        return (
            consulta
            .join(Empresa, Empresa.id == SolicitacaoServico.empresa_cliente_id)
            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)
            .join(Material, Material.id == SolicitacaoServico.material_id)
        )

    @staticmethod
    def _solicitacao(item, cliente: str, processo: str, material: str) -> SolicitacaoFornecedorLeitura:
        return SolicitacaoFornecedorLeitura(
            **SolicitacaoServicoLeitura.model_validate(item).model_dump(),
            cliente_razao_social=cliente,
            processo_nome=processo,
            material_nome=material,
        )

    def listar_oportunidades(self, empresa_id: int, deslocamento: int, limite: int) -> OportunidadesFornecedorLeitura:
        self.validar_fornecedor(empresa_id)
        ja_enviou = select(CotacaoFornecedor.id).where(
            CotacaoFornecedor.solicitacao_id == SolicitacaoServico.id,
            CotacaoFornecedor.empresa_fornecedora_id == empresa_id,
        ).correlate(SolicitacaoServico).exists()
        possui_aceita = select(CotacaoFornecedor.id).where(
            CotacaoFornecedor.solicitacao_id == SolicitacaoServico.id,
            CotacaoFornecedor.status == "aceita",
        ).correlate(SolicitacaoServico).exists()
        filtros = (
            SolicitacaoServico.status == "aberta", self._compativel(empresa_id),
            ~ja_enviou, ~possui_aceita,
        )
        contagem = self._nomes(select(func.count()).select_from(SolicitacaoServico)).where(*filtros)
        total = self.banco.scalar(contagem) or 0
        consulta = self._nomes(select(
            SolicitacaoServico, Empresa.razao_social, ProcessoFabricacao.nome, Material.nome,
        )).where(*filtros).order_by(SolicitacaoServico.id.desc()).offset(deslocamento).limit(limite)
        itens = [self._solicitacao(*linha) for linha in self.banco.execute(consulta).all()]
        return OportunidadesFornecedorLeitura(itens=itens, total=total, deslocamento=deslocamento, limite=limite)

    def listar_cotacoes(self, empresa_id: int, deslocamento: int, limite: int) -> CotacoesFornecedorLeitura:
        self.validar_fornecedor(empresa_id)
        filtros = CotacaoFornecedor.empresa_fornecedora_id == empresa_id
        contagem = self._nomes(
            select(func.count()).select_from(CotacaoFornecedor)
            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)
        ).where(filtros)
        total = self.banco.scalar(contagem) or 0
        consulta = self._nomes(
            select(CotacaoFornecedor, SolicitacaoServico, Empresa.razao_social, ProcessoFabricacao.nome, Material.nome)
            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)
        ).where(filtros).order_by(CotacaoFornecedor.id.desc()).offset(deslocamento).limit(limite)
        linhas = self.banco.execute(consulta).all()
        agora = ServicoCotacao._agora_utc_sem_fuso()
        alterou = False
        for cotacao, *_ in linhas:
            if cotacao.status == "enviada" and agora >= ServicoCotacao._normalizar_data(cotacao.criada_em) + timedelta(days=cotacao.validade_dias):
                cotacao.status = "expirada"
                cotacao.encerrada_em = agora
                cotacao.decidida_por_empresa_id = None
                alterou = True
        if alterou:
            self.banco.commit()
        itens = [CotacaoFornecedorLeitura(
            **CotacaoLeitura.model_validate(cotacao).model_dump(),
            solicitacao=self._solicitacao(item, cliente, processo, material),
        ) for cotacao, item, cliente, processo, material in linhas]
        return CotacoesFornecedorLeitura(itens=itens, total=total, deslocamento=deslocamento, limite=limite)

    def validar_envio(self, solicitacao_id: int, empresa_id: int) -> None:
        self.validar_fornecedor(empresa_id)
        item = self.banco.get(SolicitacaoServico, solicitacao_id)
        if item is None:
            raise HTTPException(404, detail="solicitacao_nao_encontrada")
        if item.status != "aberta":
            raise HTTPException(409, detail="solicitacao_nao_esta_aberta")
        # Compatibilidade, aceite prévio e duplicidade são conferidos pelo
        # serviço de cotações existente no momento de gravar a proposta.

    def validar_acesso_arquivos(self, solicitacao_id: int, empresa_id: int) -> None:
        self.validar_fornecedor(empresa_id)
        if self.banco.get(SolicitacaoServico, solicitacao_id) is None:
            raise HTTPException(404, detail="solicitacao_nao_encontrada")
        possui_cotacao = self.banco.scalar(select(CotacaoFornecedor.id).where(
            CotacaoFornecedor.solicitacao_id == solicitacao_id,
            CotacaoFornecedor.empresa_fornecedora_id == empresa_id,
        ).limit(1))
        compativel = self.banco.scalar(select(SolicitacaoServico.id).where(
            SolicitacaoServico.id == solicitacao_id, self._compativel(empresa_id),
        ))
        if possui_cotacao is None and compativel is None:
            raise HTTPException(403, detail="fornecedor_sem_acesso_a_solicitacao")
