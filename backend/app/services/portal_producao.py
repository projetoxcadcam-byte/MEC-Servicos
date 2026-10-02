from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, aliased

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.schemas.etapa_producao import EtapaProducaoLeitura
from backend.app.schemas.portal_producao import (
    AcompanhamentoPortalLeitura, OrdemProducaoLeitura, ProducaoPortalPagina,
)
from backend.app.services.etapa_producao import ServicoEtapaProducao
from backend.app.services.portal_contratacoes import Perfil
from backend.app.services.portal_ordens_servico import ServicoPortalOrdens


class ServicoPortalProducao:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.ordens = ServicoPortalOrdens(banco)

    def _consulta(self):
        resumo = select(EtapaProducao.ordem_servico_id.label("ordem_id"),
                        func.max(EtapaProducao.id).label("ultima_id"),
                        func.count(EtapaProducao.id).label("quantidade")).group_by(EtapaProducao.ordem_servico_id).subquery()
        atual = aliased(EtapaProducao)
        return self.ordens._consulta().add_columns(atual.etapa, atual.id, atual.criada_em, resumo.c.quantidade).outerjoin(
            resumo, resumo.c.ordem_id == OrdemServico.id).outerjoin(atual, atual.id == resumo.c.ultima_id)

    def _ordem(self, linha) -> OrdemProducaoLeitura:
        etapa, etapa_id, instante, quantidade = linha[-4:]
        return OrdemProducaoLeitura(**self.ordens._ordem(linha[:-4]).model_dump(),
            etapa_atual=etapa, ultima_etapa_id=etapa_id or 0, etapa_atual_em=instante, total_atualizacoes=quantidade or 0)

    def listar(self, empresa: int, perfil: Perfil, deslocamento: int, limite: int) -> ProducaoPortalPagina:
        self.ordens.contratos.validar_empresa(empresa, perfil)
        consulta = self._consulta().where(self.ordens._dono(empresa, perfil))
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return ProducaoPortalPagina(itens=[self._ordem(linha) for linha in linhas], total=total,
                                  deslocamento=deslocamento, limite=limite)

    def obter(self, ordem_id: int, empresa: int, perfil: Perfil) -> AcompanhamentoPortalLeitura:
        self.ordens.contratos.validar_empresa(empresa, perfil)
        linha = self.banco.execute(self._consulta().where(OrdemServico.id == ordem_id, self.ordens._dono(empresa, perfil))).first()
        if linha is None:
            raise HTTPException(404, detail="ordem_servico_nao_encontrada")
        ordem = self._ordem(linha)
        historico = [EtapaProducaoLeitura.model_validate(item) for item in ServicoEtapaProducao(self.banco).listar(ordem_id)]
        ultima = historico[-1] if historico else None
        ordem = ordem.model_copy(update={"etapa_atual": ultima.etapa if ultima else None,
            "ultima_etapa_id": ultima.id if ultima else 0, "etapa_atual_em": ultima.criada_em if ultima else None,
            "total_atualizacoes": len(historico)})
        return AcompanhamentoPortalLeitura(ordem=ordem, etapa_atual=ordem.etapa_atual,
                                          ultima_etapa_id=ordem.ultima_etapa_id, historico=historico)

    def preparar_registro(self, ordem_id: int, empresa: int, ultima_etapa_id: int) -> None:
        ordem = self.ordens.obter(ordem_id, empresa, "fornecedor")
        if ordem.contratacao_status != "ativa":
            raise HTTPException(409, detail="contratacao_nao_esta_ativa")
        if ordem.status not in {"aberta", "em_execucao"}:
            raise HTTPException(409, detail="ordem_servico_nao_pode_atualizar_producao")
        contrato_ativo = select(ContratacaoServico.id).where(
            ContratacaoServico.id == OrdemServico.contratacao_id, ContratacaoServico.status == "ativa",
            ContratacaoServico.empresa_fornecedora_id == empresa).correlate(OrdemServico).exists()
        # A atualização sem mudança de estado serializa registros desta ordem
        # com outras atualizações do portal e as ações de execução do D26.
        travada = self.banco.execute(update(OrdemServico).where(
            OrdemServico.id == ordem_id, OrdemServico.empresa_fornecedora_id == empresa,
            OrdemServico.status.in_(("aberta", "em_execucao")), contrato_ativo,
        ).values(status=OrdemServico.status), execution_options={"synchronize_session": False})
        if travada.rowcount != 1:
            self.banco.rollback()
            raise HTTPException(409, detail="ordem_servico_alterada_atualize")
        atual_id = self.banco.scalar(select(func.max(EtapaProducao.id)).where(EtapaProducao.ordem_servico_id == ordem_id)) or 0
        if atual_id != ultima_etapa_id:
            self.banco.rollback()
            raise HTTPException(409, detail="producao_alterada_atualize")
