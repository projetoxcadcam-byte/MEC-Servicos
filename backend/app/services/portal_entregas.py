from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session, aliased

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.entrega import EntregaServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.schemas.entrega import EntregaServicoLeitura
from backend.app.schemas.portal_entregas import EntregasPortalLeitura, EntregasPortalPagina, OrdemEntregaLeitura
from backend.app.services.portal_contratacoes import Perfil
from backend.app.services.portal_producao import ServicoPortalProducao


class ServicoPortalEntregas:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.producao = ServicoPortalProducao(banco)
        self.ordens = self.producao.ordens

    def _consulta(self):
        resumo = select(
            EntregaServico.ordem_servico_id.label("ordem_id"),
            func.max(EntregaServico.id).label("ultima_id"),
            func.count(EntregaServico.id).label("quantidade"),
            func.max(case((EntregaServico.status == "entregue", EntregaServico.id), else_=None)).label("pendente_id"),
        ).group_by(EntregaServico.ordem_servico_id).subquery()
        ultima = aliased(EntregaServico)
        return self.producao._consulta().add_columns(
            ultima.id, ultima.status, ultima.entregue_em, resumo.c.quantidade, resumo.c.pendente_id,
        ).outerjoin(resumo, resumo.c.ordem_id == OrdemServico.id).outerjoin(ultima, ultima.id == resumo.c.ultima_id)

    def _ordem(self, linha) -> OrdemEntregaLeitura:
        entrega_id, situacao, instante, quantidade, pendente_id = linha[-5:]
        return OrdemEntregaLeitura(**self.producao._ordem(linha[:-5]).model_dump(),
            ultima_entrega_id=entrega_id or 0, ultima_entrega_status=situacao,
            ultima_entrega_em=instante, total_entregas=quantidade or 0, entrega_pendente_id=pendente_id)

    def listar(self, empresa: int, perfil: Perfil, deslocamento: int, limite: int) -> EntregasPortalPagina:
        self.ordens.contratos.validar_empresa(empresa, perfil)
        consulta = self._consulta().where(self.ordens._dono(empresa, perfil))
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return EntregasPortalPagina(itens=[self._ordem(linha) for linha in linhas], total=total,
                                   deslocamento=deslocamento, limite=limite)

    def obter(self, ordem_id: int, empresa: int, perfil: Perfil) -> EntregasPortalLeitura:
        self.ordens.contratos.validar_empresa(empresa, perfil)
        linha = self.banco.execute(self._consulta().where(
            OrdemServico.id == ordem_id, self.ordens._dono(empresa, perfil),
        )).first()
        if linha is None:
            raise HTTPException(404, detail="ordem_servico_nao_encontrada")
        ordem = self._ordem(linha)
        itens = self.banco.scalars(select(EntregaServico).where(
            EntregaServico.ordem_servico_id == ordem_id,
            EntregaServico.empresa_cliente_id == ordem.empresa_cliente_id,
            EntregaServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id,
        ).order_by(EntregaServico.id)).all()
        historico = [EntregaServicoLeitura.model_validate(item) for item in itens]
        ultima = historico[-1] if historico else None
        pendente = next((e.id for e in reversed(historico) if e.status == "entregue"), None)
        ordem = ordem.model_copy(update={"ultima_entrega_id": ultima.id if ultima else 0,
            "ultima_entrega_status": ultima.status if ultima else None,
            "ultima_entrega_em": ultima.entregue_em if ultima else None,
            "total_entregas": len(historico), "entrega_pendente_id": pendente})
        return EntregasPortalLeitura(ordem=ordem, historico=historico)

    def _travar_ordem(self, ordem_id: int, empresa: int, perfil: Perfil):
        ordem = self.ordens.obter(ordem_id, empresa, perfil)
        if ordem.contratacao_status != "ativa":
            raise HTTPException(409, detail="contratacao_nao_esta_ativa")
        if ordem.status != "em_execucao":
            raise HTTPException(409, detail="ordem_servico_nao_pode_receber_entrega")
        contrato_ativo = select(ContratacaoServico.id).where(
            ContratacaoServico.id == OrdemServico.contratacao_id,
            ContratacaoServico.status == "ativa",
            ContratacaoServico.empresa_cliente_id == ordem.empresa_cliente_id,
            ContratacaoServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id,
        ).correlate(OrdemServico).exists()
        # Serializa registro/decisão com a produção e a execução da mesma OS.
        travada = self.banco.execute(update(OrdemServico).where(
            OrdemServico.id == ordem_id, self.ordens._dono(empresa, perfil),
            OrdemServico.status == "em_execucao", contrato_ativo,
        ).values(status=OrdemServico.status), execution_options={"synchronize_session": False})
        if travada.rowcount != 1:
            self.banco.rollback()
            raise HTTPException(409, detail="ordem_servico_alterada_atualize")
        contrato = self.banco.execute(update(ContratacaoServico).where(
            ContratacaoServico.id == ordem.contratacao_id, ContratacaoServico.status == "ativa",
            ContratacaoServico.empresa_cliente_id == ordem.empresa_cliente_id,
            ContratacaoServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id,
        ).values(status=ContratacaoServico.status), execution_options={"synchronize_session": False})
        if contrato.rowcount != 1:
            self.banco.rollback()
            raise HTTPException(409, detail="contratacao_nao_esta_ativa")
        return ordem

    def preparar_registro(self, ordem_id: int, empresa: int, ultima_entrega_id: int, ultima_etapa_id: int) -> None:
        self._travar_ordem(ordem_id, empresa, "fornecedor")
        ultima = self.banco.scalar(select(func.max(EntregaServico.id)).where(EntregaServico.ordem_servico_id == ordem_id)) or 0
        etapa = self.banco.scalar(select(EtapaProducao).where(
            EtapaProducao.ordem_servico_id == ordem_id).order_by(EtapaProducao.id.desc()).limit(1))
        if ultima != ultima_entrega_id:
            raise HTTPException(409, detail="entregas_alteradas_atualize")
        if (etapa.id if etapa else 0) != ultima_etapa_id:
            raise HTTPException(409, detail="producao_alterada_atualize")
        if etapa is None or etapa.etapa != "pronto_para_envio":
            raise HTTPException(409, detail="ordem_servico_nao_esta_pronta_para_entrega")
        pendente = self.banco.scalar(select(EntregaServico.id).where(
            EntregaServico.ordem_servico_id == ordem_id, EntregaServico.status == "entregue").limit(1))
        if pendente is not None:
            raise HTTPException(409, detail="entrega_pendente_ja_existe")
        self.banco.expire_all()

    def preparar_decisao(self, ordem_id: int, entrega_id: int, empresa: int) -> None:
        ordem = self.ordens.obter(ordem_id, empresa, "cliente")
        item = self.banco.scalar(select(EntregaServico).where(
            EntregaServico.id == entrega_id, EntregaServico.ordem_servico_id == ordem_id,
            EntregaServico.empresa_cliente_id == empresa,
            EntregaServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id))
        if item is None:
            raise HTTPException(404, detail="entrega_nao_encontrada")
        if item.status != "entregue":
            raise HTTPException(409, detail="entrega_nao_esta_pendente")
        self._travar_ordem(ordem_id, empresa, "cliente")
        travada = self.banco.execute(update(EntregaServico).where(
            EntregaServico.id == entrega_id, EntregaServico.ordem_servico_id == ordem_id,
            EntregaServico.empresa_cliente_id == empresa, EntregaServico.status == "entregue",
        ).values(status=EntregaServico.status), execution_options={"synchronize_session": False})
        if travada.rowcount != 1:
            raise HTTPException(409, detail="entrega_nao_esta_pendente")
        self.banco.expire_all()
