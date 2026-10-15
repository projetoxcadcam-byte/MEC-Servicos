"""Totais completos e cinco registros recentes da empresa da sessão."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.portal_fornecedor import ServicoPortalFornecedor


class ServicoPainelPerfis:
    def __init__(self, banco: Session, usuario: UsuarioAcesso):
        if usuario.perfil not in {"cliente", "fornecedor"} or not usuario.empresa_id or usuario.usuario_id <= 0:
            raise HTTPException(403, detail="painel_exige_perfil_da_empresa")
        self.banco, self.usuario = banco, usuario

    def contexto(self):
        u = self.usuario
        return f"{u.usuario_id}:{u.perfil}:{u.empresa_id}"

    def _contagem(self, modelo, status, escopo):
        linhas = self.banco.execute(select(status, func.count()).select_from(modelo).where(escopo).group_by(status)).all()
        por_status = {s: n for s, n in linhas}
        return {"total": sum(por_status.values()), "por_status": por_status}

    def consultar(self):
        # SELECT sozinho não inicia a transação no driver SQLite legado.
        # Contagens e listas devem refletir a mesma fotografia dos registros.
        conexao = self.banco.connection()
        if conexao.dialect.name == "sqlite" and not conexao.connection.driver_connection.in_transaction:
            self.banco.execute(text("BEGIN"))
        agora = datetime.now(timezone.utc)
        perfil, empresa = self.usuario.perfil, self.usuario.empresa_id
        cliente = perfil == "cliente"
        escopo_os = (OrdemServico.empresa_cliente_id if cliente else OrdemServico.empresa_fornecedora_id) == empresa
        escopo_contrato = (ContratacaoServico.empresa_cliente_id if cliente else ContratacaoServico.empresa_fornecedora_id) == empresa
        escopo_solicitacao = SolicitacaoServico.empresa_cliente_id == empresa
        if cliente:
            escopo_cotacao = CotacaoFornecedor.solicitacao_id.in_(select(SolicitacaoServico.id).where(escopo_solicitacao))
        else:
            escopo_cotacao = CotacaoFornecedor.empresa_fornecedora_id == empresa
        # O projeto utiliza SQLite. A validade exibida é calculada na consulta,
        # sem gravar expiração nem emitir notificações durante a leitura.
        expirada = func.julianday(agora.replace(tzinfo=None)) >= func.julianday(CotacaoFornecedor.criada_em) + CotacaoFornecedor.validade_dias
        status_cotacao = case(((CotacaoFornecedor.status == "enviada") & expirada, "expirada"), else_=CotacaoFornecedor.status)
        from backend.app.services.precos_portais import ativa, visibilidade_cliente
        if cliente and ativa(self.banco):escopo_cotacao=escopo_cotacao & visibilidade_cliente()
        totais_cotacoes = self._contagem(CotacaoFornecedor, status_cotacao, escopo_cotacao)
        totais_os = self._contagem(OrdemServico, OrdemServico.status, escopo_os)
        totais_contratos = self._contagem(ContratacaoServico, ContratacaoServico.status, escopo_contrato)

        ultima = (select(EtapaProducao.id).where(EtapaProducao.ordem_servico_id == OrdemServico.id)
                  .order_by(EtapaProducao.id.desc()).limit(1).correlate(OrdemServico).scalar_subquery())
        ordens = self.banco.execute(select(
            OrdemServico.id, OrdemServico.solicitacao_id, OrdemServico.contratacao_id, OrdemServico.status,
            ProcessoFabricacao.nome.label("processo_nome"), Material.nome.label("material_nome"), OrdemServico.criada_em,
            EtapaProducao.etapa.label("etapa_atual"), EtapaProducao.criada_em.label("etapa_atual_em"))
            .join(ProcessoFabricacao, ProcessoFabricacao.id == OrdemServico.processo_id)
            .join(Material, Material.id == OrdemServico.material_id)
            .outerjoin(EtapaProducao, EtapaProducao.id == ultima)
            .where(escopo_os).order_by(OrdemServico.id.desc()).limit(5)).mappings().all()
        solicitacoes, cotacoes, totais_solicitacoes, oportunidades = [], [], None, None
        if cliente:
            totais_solicitacoes = self._contagem(SolicitacaoServico, SolicitacaoServico.status, escopo_solicitacao)
            solicitacoes = self.banco.execute(select(
                SolicitacaoServico.id, SolicitacaoServico.status, SolicitacaoServico.quantidade, SolicitacaoServico.criada_em,
                ProcessoFabricacao.nome.label("processo_nome"), Material.nome.label("material_nome"))
                .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)
                .join(Material, Material.id == SolicitacaoServico.material_id)
                .where(escopo_solicitacao).order_by(SolicitacaoServico.id.desc()).limit(5)).mappings().all()
        else:
            # Mesmas regras de compatibilidade, documentação e proposta já
            # enviada da janela Oportunidades; o total não depende da página.
            oportunidades = ServicoPortalFornecedor(self.banco).listar_oportunidades(empresa, 0, 1).total
            cotacoes = self.banco.execute(select(CotacaoFornecedor.id, CotacaoFornecedor.solicitacao_id,
                status_cotacao.label("status"), CotacaoFornecedor.valor_total, CotacaoFornecedor.criada_em)
                .where(escopo_cotacao).order_by(CotacaoFornecedor.id.desc()).limit(5)).mappings().all()
        return {"contexto": self.contexto(), "perfil": perfil, "empresa_id": empresa, "consultado_em": agora,
                "solicitacoes": totais_solicitacoes, "cotacoes": totais_cotacoes, "contratacoes": totais_contratos,
                "ordens": totais_os, "oportunidades": oportunidades, "solicitacoes_recentes": solicitacoes,
                "cotacoes_recentes": cotacoes, "ordens_recentes": ordens}
