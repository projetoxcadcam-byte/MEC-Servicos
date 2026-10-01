from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.entrega import EntregaServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.repositories.entrega import RepositorioEntrega
from backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao


class OrdemServicoNaoEncontradaParaEntrega(Exception): pass
class EntregaNaoEncontrada(Exception): pass
class EmpresaFornecedoraNaoPodeEntregar(Exception): pass
class EmpresaClienteNaoPodeDecidirEntrega(Exception): pass
class OrdemServicoNaoPodeReceberEntrega(Exception): pass
class OrdemServicoNaoEstaProntaParaEntrega(Exception): pass
class EntregaPendenteJaExiste(Exception): pass
class EntregaNaoEstaPendente(Exception): pass
class MotivoRecusaObrigatorio(Exception): pass


class ServicoEntrega:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioEntrega(banco)

    @staticmethod
    def _agora_utc_sem_fuso() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _ordem(self, ordem_servico_id: int) -> OrdemServico:
        item = self.banco.get(OrdemServico, ordem_servico_id)
        if item is None:
            raise OrdemServicoNaoEncontradaParaEntrega
        return item

    def _entrega(self, entrega_id: int) -> EntregaServico:
        item = self.repositorio.buscar(entrega_id)
        if item is None:
            raise EntregaNaoEncontrada
        return item

    def _validar_pronta_para_entrega(self, ordem: OrdemServico) -> None:
        if ordem.status in {"concluida", "cancelada"} or ordem.status != "em_execucao":
            raise OrdemServicoNaoPodeReceberEntrega
        stmt = (
            select(EtapaProducao)
            .where(EtapaProducao.ordem_servico_id == ordem.id)
            .order_by(EtapaProducao.id.desc())
            .limit(1)
        )
        etapa_atual = self.banco.scalar(stmt)
        if etapa_atual is None or etapa_atual.etapa != "pronto_para_envio":
            raise OrdemServicoNaoEstaProntaParaEntrega

    def registrar(self, ordem_servico_id: int, dados: EntregaServicoCriacao) -> EntregaServico:
        ordem = self._ordem(ordem_servico_id)
        if ordem.empresa_fornecedora_id != dados.empresa_fornecedora_id:
            raise EmpresaFornecedoraNaoPodeEntregar
        self._validar_pronta_para_entrega(ordem)
        if self.repositorio.pendente_por_ordem(ordem.id) is not None:
            raise EntregaPendenteJaExiste
        agora = self._agora_utc_sem_fuso()
        item = EntregaServico(
            ordem_servico_id=ordem.id,
            empresa_fornecedora_id=ordem.empresa_fornecedora_id,
            empresa_cliente_id=ordem.empresa_cliente_id,
            status="entregue",
            observacoes=dados.observacoes,
            criada_em=agora,
            entregue_em=agora,
        )
        return self.repositorio.criar(item)

    def obter(self, entrega_id: int) -> EntregaServico:
        return self._entrega(entrega_id)

    def listar(self, ordem_servico_id: int) -> list[EntregaServico]:
        self._ordem(ordem_servico_id)
        return self.repositorio.listar_por_ordem(ordem_servico_id)

    def aceitar(self, ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao) -> EntregaServico:
        ordem = self._ordem(ordem_servico_id)
        if ordem.empresa_cliente_id != dados.empresa_cliente_id:
            raise EmpresaClienteNaoPodeDecidirEntrega
        item = self._entrega(entrega_id)
        if item.ordem_servico_id != ordem.id:
            raise EntregaNaoEncontrada
        if item.status != "entregue":
            raise EntregaNaoEstaPendente
        agora = self._agora_utc_sem_fuso()
        item.status = "aceita"
        item.aceita_em = agora
        ordem.status = "concluida"
        ordem.concluida_em = agora
        contratacao = self.banco.get(ContratacaoServico, ordem.contratacao_id)
        if contratacao is not None and contratacao.status == "ativa":
            contratacao.status = "encerrada"
            contratacao.encerrada_em = agora
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def recusar(self, ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao) -> EntregaServico:
        ordem = self._ordem(ordem_servico_id)
        if ordem.empresa_cliente_id != dados.empresa_cliente_id:
            raise EmpresaClienteNaoPodeDecidirEntrega
        item = self._entrega(entrega_id)
        if item.ordem_servico_id != ordem.id:
            raise EntregaNaoEncontrada
        if item.status != "entregue":
            raise EntregaNaoEstaPendente
        if not dados.motivo:
            raise MotivoRecusaObrigatorio
        item.status = "recusada"
        item.motivo_recusa = dados.motivo
        item.recusada_em = self._agora_utc_sem_fuso()
        self.banco.commit()
        self.banco.refresh(item)
        return item
