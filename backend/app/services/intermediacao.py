from __future__ import annotations

import re
from datetime import UTC, datetime
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.intermediacao import CicloIntermediacao, EventoIntermediacao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.schemas.intermediacao import (
    ConsultaPortalIntermediacao, ContratacaoParaIntermediacao, EventoAdministrativoLeitura,
    EventoPortalIntermediacao, InicioIntermediacao, IntermediacaoDetalhe, IntermediacaoPagina,
    OrdemIntermediacaoLeitura, RegistroIntermediacao,
)

TRANSICOES = {
    "aguardando_material": {"receber_material": "material_recebido"},
    "material_recebido": {"encaminhar_material": "material_encaminhado"},
    "material_encaminhado": {"solicitar_coleta": "coleta_solicitada"},
    "coleta_solicitada": {"receber_pecas": "pecas_recebidas"},
    "pecas_recebidas": {"iniciar_avaliacao": "em_avaliacao"},
    "em_avaliacao": {"aprovar_pecas": "aprovado_para_entrega", "solicitar_retrabalho": "retrabalho"},
    "retrabalho": {"encaminhar_retrabalho": "retrabalho_encaminhado"},
    "retrabalho_encaminhado": {"solicitar_coleta": "coleta_solicitada"},
    "aprovado_para_entrega": {"entregar_cliente": "entregue_cliente"},
}
FINAIS = {"entregue_cliente", "cancelado"}


def instante() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def exigir_admin(usuario: UsuarioAcesso) -> None:
    if usuario.perfil != "admin":
        raise HTTPException(403, detail="acao_exclusiva_da_administracao")


def proteger_ciclo_legado(banco: Session, caminho: str, metodo: str, usuario: UsuarioAcesso) -> None:
    """Impede que caminhos anteriores encerrem um ciclo administrado pelo D31."""
    if metodo not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    def travar(oid: int) -> None:
        if usuario.perfil == "fornecedor":
            propria = banco.scalar(select(OrdemServico.id).where(OrdemServico.id == oid,
                OrdemServico.empresa_fornecedora_id == usuario.empresa_id))
            if propria is None:
                raise HTTPException(404, detail="ordem_servico_nao_encontrada")
        banco.execute(update(OrdemServico).where(OrdemServico.id == oid).values(status=OrdemServico.status),
                      execution_options={"synchronize_session": False})
        banco.expire_all()
    ordem = re.fullmatch(r"/(?:portal-(?:cliente|fornecedor)/)?ordens-servico/([1-9]\d*)/(concluir|cancelar)", caminho)
    entrega = re.fullmatch(r"/ordens-servico/([1-9]\d*)/entregas(?:/[1-9]\d*/(?:aceitar|recusar))?", caminho)
    portal_entrega = re.fullmatch(r"/portal-(?:cliente|fornecedor)/entregas/([1-9]\d*)/.*", caminho)
    alvo = ordem or entrega or portal_entrega
    if alvo: travar(int(alvo[1]))
    if alvo and banco.scalar(select(CicloIntermediacao.id).where(CicloIntermediacao.ordem_servico_id == int(alvo[1]))):
        raise HTTPException(409, detail="ordem_usa_intermediacao_administrativa")
    contrato = re.fullmatch(r"/contratacoes(?:-servico)?/([1-9]\d*)/(?:cancelar|encerrar)", caminho)
    if contrato:
        banco.execute(update(ContratacaoServico).where(ContratacaoServico.id == int(contrato[1])).values(
            status=ContratacaoServico.status), execution_options={"synchronize_session": False})
        banco.expire_all()
    if contrato and banco.scalar(select(CicloIntermediacao.id).join(OrdemServico,
            OrdemServico.id == CicloIntermediacao.ordem_servico_id).where(
            OrdemServico.contratacao_id == int(contrato[1]), CicloIntermediacao.status.not_in(FINAIS))):
        raise HTTPException(409, detail="ordem_usa_intermediacao_administrativa")
    contrato_solicitacao = re.fullmatch(r"/solicitacoes-servico/([1-9]\d*)/contratacao/(?:cancelar|encerrar)", caminho)
    if contrato_solicitacao:
        banco.execute(update(ContratacaoServico).where(ContratacaoServico.solicitacao_id == int(contrato_solicitacao[1])).values(
            status=ContratacaoServico.status), execution_options={"synchronize_session": False})
        banco.expire_all()
    if contrato_solicitacao and banco.scalar(select(CicloIntermediacao.id).join(OrdemServico,
            OrdemServico.id == CicloIntermediacao.ordem_servico_id).where(
            OrdemServico.solicitacao_id == int(contrato_solicitacao[1]), CicloIntermediacao.status.not_in(FINAIS))):
        raise HTTPException(409, detail="ordem_usa_intermediacao_administrativa")
    producao = re.fullmatch(r"/(?:portal-fornecedor/ordens-servico/([1-9]\d*)/iniciar|"
                            r"portal-fornecedor/producao/([1-9]\d*)/etapas|ordens-servico/([1-9]\d*)/(?:iniciar|etapas-producao))", caminho)
    if producao:
        oid = int(next(v for v in producao.groups() if v is not None))
        travar(oid)
        ciclo = banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == oid))
        if ciclo and ciclo.status not in {"material_encaminhado", "retrabalho_encaminhado"}:
            raise HTTPException(409, detail="producao_aguarda_encaminhamento_administrativo")


class ServicoIntermediacao:
    def __init__(self, banco: Session):
        self.banco = banco

    def _consulta(self):
        cliente = aliased(Empresa); fornecedor = aliased(Empresa)
        ultima = select(func.max(EtapaProducao.id)).where(
            EtapaProducao.ordem_servico_id == OrdemServico.id).correlate(OrdemServico).scalar_subquery()
        etapa = aliased(EtapaProducao)
        return select(OrdemServico, ContratacaoServico, cliente.razao_social, fornecedor.razao_social,
                      CicloIntermediacao, etapa.etapa).join(ContratacaoServico,
            ContratacaoServico.id == OrdemServico.contratacao_id).join(cliente,
            cliente.id == OrdemServico.empresa_cliente_id).join(fornecedor,
            fornecedor.id == OrdemServico.empresa_fornecedora_id).outerjoin(CicloIntermediacao,
            CicloIntermediacao.ordem_servico_id == OrdemServico.id).outerjoin(etapa, etapa.id == ultima)

    @staticmethod
    def _leitura(linha) -> OrdemIntermediacaoLeitura:
        ordem, contrato, cliente, fornecedor, ciclo, etapa = linha
        return OrdemIntermediacaoLeitura(ordem_servico_id=ordem.id, solicitacao_id=ordem.solicitacao_id,
            contratacao_id=ordem.contratacao_id, empresa_cliente_id=ordem.empresa_cliente_id,
            empresa_fornecedora_id=ordem.empresa_fornecedora_id, cliente=cliente, fornecedor=fornecedor,
            quantidade=ordem.quantidade, ordem_status=ordem.status, contratacao_status=contrato.status,
            producao_etapa=etapa, ciclo_id=ciclo.id if ciclo else None, status=ciclo.status if ciclo else None,
            versao=ciclo.versao if ciclo else 0, atualizado_em=ciclo.atualizado_em if ciclo else None,
            pode_iniciar=not ciclo and ordem.status in {"aberta", "em_execucao"} and contrato.status == "ativa")

    def listar(self, usuario: UsuarioAcesso, deslocamento: int, limite: int, filtro: str | None) -> IntermediacaoPagina:
        exigir_admin(usuario)
        consulta = self._consulta()
        if filtro == "sem_ciclo": consulta = consulta.where(CicloIntermediacao.id.is_(None))
        elif filtro == "em_andamento": consulta = consulta.where(CicloIntermediacao.status.not_in(FINAIS))
        elif filtro == "finalizados": consulta = consulta.where(CicloIntermediacao.status.in_(FINAIS))
        elif filtro not in {None, "todos"}: raise HTTPException(422, detail="filtro_intermediacao_invalido")
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return IntermediacaoPagina(itens=[self._leitura(linha) for linha in linhas], total=total, deslocamento=deslocamento, limite=limite)

    def obter(self, ordem_id: int, usuario: UsuarioAcesso) -> IntermediacaoDetalhe:
        exigir_admin(usuario)
        linha = self.banco.execute(self._consulta().where(OrdemServico.id == ordem_id)).first()
        if linha is None: raise HTTPException(404, detail="ordem_servico_nao_encontrada")
        ordem = self._leitura(linha); ciclo = linha[4]
        eventos = self.banco.scalars(select(EventoIntermediacao).where(
            EventoIntermediacao.ciclo_id == ciclo.id).order_by(EventoIntermediacao.versao)).all() if ciclo else []
        acoes = list(TRANSICOES.get(ciclo.status, {})) if ciclo else []
        if ciclo and ciclo.status not in FINAIS:
            acoes.append("cancelar")
        if ciclo and (ordem.ordem_status not in {"aberta", "em_execucao"} or ordem.contratacao_status != "ativa"):
            acoes = []
        return IntermediacaoDetalhe(ordem=ordem, acoes_permitidas=acoes,
            historico=[EventoAdministrativoLeitura.model_validate(item) for item in eventos])

    def _travar_ordem(self, ordem_id: int) -> OrdemServico:
        # Escrita sem mudança de estado serializa com início/produção e decisões anteriores.
        ativa = select(ContratacaoServico.id).where(ContratacaoServico.id == OrdemServico.contratacao_id,
            ContratacaoServico.status == "ativa").correlate(OrdemServico).exists()
        alterada = self.banco.execute(update(OrdemServico).where(OrdemServico.id == ordem_id,
            OrdemServico.status.in_(("aberta", "em_execucao")), ativa).values(status=OrdemServico.status),
            execution_options={"synchronize_session": False})
        if alterada.rowcount != 1:
            self.banco.rollback()
            if self.banco.get(OrdemServico, ordem_id) is None: raise HTTPException(404, detail="ordem_servico_nao_encontrada")
            raise HTTPException(409, detail="ordem_sem_condicoes_para_intermediacao")
        self.banco.expire_all()
        return self.banco.get(OrdemServico, ordem_id)

    def iniciar(self, ordem_id: int, dados: InicioIntermediacao, usuario: UsuarioAcesso) -> IntermediacaoDetalhe:
        exigir_admin(usuario)
        self._travar_ordem(ordem_id)
        if self.banco.scalar(select(CicloIntermediacao.id).where(CicloIntermediacao.ordem_servico_id == ordem_id)):
            self.banco.rollback(); raise HTTPException(409, detail="ciclo_ja_iniciado")
        agora = instante()
        ciclo = CicloIntermediacao(ordem_servico_id=ordem_id, status="aguardando_material", versao=1,
                                  criado_em=agora, atualizado_em=agora)
        try:
            self.banco.add(ciclo); self.banco.flush()
            self.banco.add(EventoIntermediacao(ciclo_id=ciclo.id, versao=1, acao="iniciar_ciclo", status_anterior=None,
                status_resultante=ciclo.status, usuario_admin_id=usuario.usuario_id, administrador_nome=usuario.nome,
                registro_interno=dados.registro_interno, criado_em=agora))
            self.banco.commit()
        except IntegrityError:
            self.banco.rollback(); raise HTTPException(409, detail="ciclo_ja_iniciado") from None
        return self.obter(ordem_id, usuario)

    def registrar(self, ordem_id: int, dados: RegistroIntermediacao, usuario: UsuarioAcesso) -> IntermediacaoDetalhe:
        exigir_admin(usuario)
        ordem = self._travar_ordem(ordem_id)
        ciclo = self.banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == ordem_id))
        def recusar(detalhe: str):
            self.banco.rollback(); raise HTTPException(409, detail=detalhe)
        if ciclo is None: recusar("inicie_intermediacao_primeiro")
        if dados.versao != ciclo.versao: recusar("intermediacao_alterada_atualize")
        destino = "cancelado" if dados.acao == "cancelar" and ciclo.status not in FINAIS else TRANSICOES.get(ciclo.status, {}).get(dados.acao)
        if destino is None: recusar("etapa_intermediacao_incompativel")
        if dados.acao in {"receber_pecas", "aprovar_pecas", "entregar_cliente"} and dados.quantidade_conferida != ordem.quantidade:
            recusar("confira_quantidade_total_da_ordem")
        if dados.acao in {"aprovar_pecas", "solicitar_retrabalho"} and not dados.parecer_tecnico:
            recusar("parecer_tecnico_obrigatorio")
        if dados.acao in {"encaminhar_material", "receber_pecas", "encaminhar_retrabalho", "entregar_cliente"} and not dados.referencia:
            recusar("referencia_comprovante_obrigatoria")
        ultima = self.banco.scalar(select(EtapaProducao).where(EtapaProducao.ordem_servico_id == ordem_id).order_by(EtapaProducao.id.desc()).limit(1))
        etapa_coleta = ciclo.ultima_etapa_coleta_id
        if dados.acao == "solicitar_coleta":
            if ultima is None or ultima.etapa != "pronto_para_envio" or ultima.id <= etapa_coleta:
                recusar("fornecedor_precisa_informar_pronto_para_coleta")
            etapa_coleta = ultima.id
        if dados.acao == "encaminhar_retrabalho":
            etapa_coleta = ultima.id if ultima else etapa_coleta
        anterior = ciclo.status; nova_versao = ciclo.versao + 1; agora = instante()
        atualizada = self.banco.execute(update(CicloIntermediacao).where(CicloIntermediacao.id == ciclo.id,
            CicloIntermediacao.versao == dados.versao, CicloIntermediacao.status == anterior).values(
            status=destino, versao=nova_versao, atualizado_em=agora, ultima_etapa_coleta_id=etapa_coleta),
            execution_options={"synchronize_session": False})
        if atualizada.rowcount != 1: recusar("intermediacao_alterada_atualize")
        self.banco.add(EventoIntermediacao(ciclo_id=ciclo.id, versao=nova_versao, acao=dados.acao,
            status_anterior=anterior, status_resultante=destino, usuario_admin_id=usuario.usuario_id,
            administrador_nome=usuario.nome, registro_interno=dados.registro_interno, referencia=dados.referencia,
            parecer_tecnico=dados.parecer_tecnico, quantidade_conferida=dados.quantidade_conferida, criado_em=agora))
        # A conclusão da OS acontece somente após a entrega física registrada pela administração.
        if dados.acao == "entregar_cliente":
            ordem.status = "concluida"; ordem.concluida_em = datetime.now(UTC).replace(tzinfo=None)
        elif dados.acao == "cancelar":
            ordem.status = "cancelada"; ordem.cancelada_em = datetime.now(UTC).replace(tzinfo=None)
        try: self.banco.commit()
        except IntegrityError:
            self.banco.rollback(); raise HTTPException(409, detail="intermediacao_alterada_atualize") from None
        self.banco.expire_all()
        return self.obter(ordem_id, usuario)

    def consultar_portal(self, ordem_id: int, usuario: UsuarioAcesso, perfil: str, empresa: int) -> ConsultaPortalIntermediacao:
        if usuario.perfil != perfil or usuario.empresa_id != empresa:
            raise HTTPException(403, detail="empresa_diverge_da_sessao")
        dono = OrdemServico.empresa_cliente_id if perfil == "cliente" else OrdemServico.empresa_fornecedora_id
        ordem = self.banco.scalar(select(OrdemServico).where(OrdemServico.id == ordem_id, dono == empresa))
        if ordem is None: raise HTTPException(404, detail="ordem_servico_nao_encontrada")
        ciclo = self.banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == ordem_id))
        eventos = self.banco.scalars(select(EventoIntermediacao).where(EventoIntermediacao.ciclo_id == ciclo.id).order_by(
            EventoIntermediacao.versao)).all() if ciclo else []
        # DTO fechado: nenhum campo livre, identidade administrativa ou comprovante sai para os portais.
        return ConsultaPortalIntermediacao(ordem_servico_id=ordem_id, status=ciclo.status if ciclo else None,
            atualizado_em=ciclo.atualizado_em if ciclo else None, historico=[EventoPortalIntermediacao(
            acao=item.acao, status_resultante=item.status_resultante, criado_em=item.criado_em) for item in eventos])

    def contratacoes_sem_ordem(self, usuario: UsuarioAcesso) -> list[ContratacaoParaIntermediacao]:
        exigir_admin(usuario)
        cliente = aliased(Empresa); fornecedor = aliased(Empresa)
        linhas = self.banco.execute(select(ContratacaoServico, cliente.razao_social, fornecedor.razao_social).join(
            cliente, cliente.id == ContratacaoServico.empresa_cliente_id).join(fornecedor,
            fornecedor.id == ContratacaoServico.empresa_fornecedora_id).where(ContratacaoServico.status == "ativa",
            ~select(OrdemServico.id).where(OrdemServico.contratacao_id == ContratacaoServico.id).exists()).order_by(
            ContratacaoServico.id.desc()).limit(100)).all()
        return [ContratacaoParaIntermediacao(id=c.id, solicitacao_id=c.solicitacao_id, cliente=cl, fornecedor=fo) for c, cl, fo in linhas]
