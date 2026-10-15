from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from fastapi import HTTPException
from sqlalchemy import and_, func, select
from backend.app.models.formacao_preco import FormacaoPreco
from sqlalchemy.orm import Session, aliased

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.financeiro_administrativo import ControleFinanceiro, RepasseAdministrativo
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.schemas.painel_administrativo import ConsultaPainel, IndicadoresPainel, ItemPainel, PendenciaPainel
from backend.app.services.financeiro_administrativo import centavos, moeda
from backend.app.services.intermediacao import exigir_admin, instante

FILTROS = {"todas", "operacionais", "financeiras", "verificar", "concluidas", "canceladas"}
ETAPAS = {
    "aguardando_material": ("receber_material", "Aguardar e conferir o recebimento do material."),
    "material_recebido": ("encaminhar_material", "Encaminhar o material ao fornecedor."),
    "coleta_solicitada": ("receber_pecas", "Acompanhar a coleta e conferir o recebimento das peças."),
    "pecas_recebidas": ("iniciar_avaliacao", "Iniciar a avaliação técnica das peças."),
    "em_avaliacao": ("avaliar_pecas", "Conferir as peças e registrar a decisão técnica."),
    "retrabalho": ("encaminhar_retrabalho", "Encaminhar as peças para retrabalho."),
    "aprovado_para_entrega": ("entregar_cliente", "Registrar a entrega das peças aprovadas ao cliente."),
}


def texto_busca(valor: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", valor.casefold()) if not unicodedata.combining(c)).strip()


def ultima_data(*valores) -> str | None:
    datas = []
    for valor in valores:
        if not valor:
            continue
        try:
            data = valor if isinstance(valor, datetime) else datetime.fromisoformat(valor.replace("Z", "+00:00"))
            datas.append(data.replace(tzinfo=UTC) if data.tzinfo is None else data.astimezone(UTC))
        except (ValueError, TypeError):
            continue
    return max(datas).isoformat().replace("+00:00", "Z") if datas else None


class ServicoPainelAdministrativo:
    def __init__(self, banco: Session):
        self.banco = banco

    def _consulta(self):
        # Agregados separados evitam multiplicar recebimentos pelos repasses.
        recebimentos = select(PagamentoContratacao.contratacao_id,
            func.sum(PagamentoContratacao.valor).label("valor")).where(
            PagamentoContratacao.status == "confirmado").group_by(PagamentoContratacao.contratacao_id).subquery()
        repasses = select(RepasseAdministrativo.contratacao_id,
            func.sum(RepasseAdministrativo.valor_centavos).label("centavos")).where(
            RepasseAdministrativo.status == "confirmado").group_by(RepasseAdministrativo.contratacao_id).subquery()
        ultima = select(func.max(EtapaProducao.id)).where(
            EtapaProducao.ordem_servico_id == OrdemServico.id).correlate(OrdemServico).scalar_subquery()
        cliente, fornecedor, etapa = aliased(Empresa), aliased(Empresa), aliased(EtapaProducao)
        return select(ContratacaoServico, OrdemServico, CicloIntermediacao, ControleFinanceiro,
            cliente.razao_social, fornecedor.razao_social, recebimentos.c.valor, repasses.c.centavos, etapa, FormacaoPreco.custo_centavos).outerjoin(
            FormacaoPreco, and_(FormacaoPreco.contratacao_id==ContratacaoServico.id,FormacaoPreco.cotacao_id==ContratacaoServico.cotacao_id,FormacaoPreco.estado=='contratada')).join(
            cliente, cliente.id == ContratacaoServico.empresa_cliente_id).join(
            fornecedor, fornecedor.id == ContratacaoServico.empresa_fornecedora_id).outerjoin(
            OrdemServico, OrdemServico.contratacao_id == ContratacaoServico.id).outerjoin(
            CicloIntermediacao, CicloIntermediacao.ordem_servico_id == OrdemServico.id).outerjoin(
            ControleFinanceiro, ControleFinanceiro.contratacao_id == ContratacaoServico.id).outerjoin(
            recebimentos, recebimentos.c.contratacao_id == ContratacaoServico.id).outerjoin(
            repasses, repasses.c.contratacao_id == ContratacaoServico.id).outerjoin(
            etapa, etapa.id == ultima).order_by(ContratacaoServico.id.desc())

    @staticmethod
    def _item(linha) -> ItemPainel:
        contrato, ordem, ciclo, controle, cliente, fornecedor, pagos, repasses, etapa, custo_preco = linha
        valor = centavos(contrato.valor_total)
        custo = custo_preco if custo_preco is not None else valor
        recebido = centavos(pagos or 0)
        repassado = int(repasses or 0)
        saldo_cliente = max(0, valor - recebido)
        saldo_fornecedor = max(0, custo - repassado)
        entregue = bool(ordem and ordem.status == "concluida" and ciclo and ciclo.status == "entregue_cliente")
        pendencias = []
        def incluir(codigo, area, descricao):
            pendencias.append(PendenciaPainel(codigo=codigo, area=area, descricao=descricao))

        # Divergências são sinalizadas para conferência, sem corrigir dados anteriores.
        if recebido > valor or repassado > min(custo, recebido):
            incluir("conferir_valores", "conferencia", "Conferir movimentos que excedem o valor contratado ou a cobertura recebida.")
        if controle and controle.valor_contratado_centavos != valor:
            incluir("conferir_valor_contratado", "conferencia", "Conferir o valor contratado e o valor do controle financeiro.")
        if controle and ((controle.status == "aberto" and contrato.status != "ativa") or
                         (controle.status == "encerrado" and contrato.status != "encerrada")):
            incluir("conferir_encerramento", "conferencia", "Conferir a situação da contratação e do controle financeiro.")
        if controle and controle.status == "encerrado" and (not entregue or saldo_cliente or saldo_fornecedor):
            incluir("conferir_financeiro_encerrado", "conferencia", "Conferir entrega e saldos de um financeiro registrado como encerrado.")
        if ciclo and ((ciclo.status == "entregue_cliente" and (not ordem or ordem.status != "concluida")) or
                      (ordem and ordem.status == "concluida" and ciclo.status != "entregue_cliente")):
            incluir("conferir_entrega", "conferencia", "Conferir a situação da OS e da entrega administrativa.")
        if contrato.status == "ativa" and ordem and (ordem.status == "cancelada" or (ciclo and ciclo.status == "cancelado")):
            incluir("conferir_cancelamento", "conferencia", "Conferir a contratação ativa com OS ou ciclo cancelado.")
        if contrato.status == "ativa" and ordem and ordem.status == "concluida" and not ciclo:
            incluir("conferir_ordem_anterior", "conferencia", "Conferir a ordem concluída no fluxo anterior antes de iniciar novos registros.")

        if pendencias:
            situacao = "verificar"
        elif contrato.status == "cancelada":
            situacao = "cancelada"
        elif contrato.status == "encerrada":
            situacao = "concluida"
        else:
            situacao = "em_andamento"
            if not ordem:
                incluir("criar_ordem", "operacional", "Criar a ordem de serviço para a contratação ativa.")
            elif not ciclo:
                incluir("iniciar_intermediacao", "operacional", "Iniciar o ciclo de intermediação administrativa.")
            elif ciclo.status in {"material_encaminhado", "retrabalho_encaminhado"}:
                pronta = bool(etapa and etapa.etapa == "pronto_para_envio" and etapa.id > ciclo.ultima_etapa_coleta_id)
                incluir("solicitar_coleta" if pronta else "acompanhar_producao", "operacional",
                        "Solicitar a coleta das peças prontas." if pronta else "Acompanhar a produção informada pelo fornecedor.")
            elif ciclo.status in ETAPAS:
                codigo, descricao = ETAPAS[ciclo.status]
                incluir(codigo, "operacional", descricao)
            if not controle:
                incluir("iniciar_financeiro", "financeira", "Conferir os movimentos anteriores e iniciar o controle financeiro.")
            elif controle.status == "aberto":
                if saldo_cliente:
                    incluir("receber_cliente", "financeira", "Conferir e registrar o saldo recebido do cliente.")
                if saldo_fornecedor:
                    if not entregue:
                        incluir("repasse_aguarda_entrega", "financeira", "O repasse aguarda a entrega administrativa ao cliente.")
                    elif min(custo, recebido) > repassado:
                        incluir("repassar_fornecedor", "financeira", "Conferir e registrar o repasse disponível ao fornecedor.")
                    else:
                        incluir("repasse_aguarda_recebimento", "financeira", "O repasse aguarda recebimentos que cubram o valor restante.")
                if entregue and not saldo_cliente and not saldo_fornecedor:
                    incluir("encerrar_financeiro", "financeira", "Conferir e encerrar o financeiro e a contratação.")

        disponivel = max(0, min(custo, recebido) - repassado) if entregue and controle and controle.status == "aberto" and situacao == "em_andamento" else 0
        return ItemPainel(contratacao_id=contrato.id, solicitacao_id=contrato.solicitacao_id,
            ordem_servico_id=ordem.id if ordem else None, cliente=cliente, fornecedor=fornecedor,
            contratacao_status=contrato.status, ordem_status=ordem.status if ordem else None,
            etapa_administrativa=ciclo.status if ciclo else None, etapa_producao=etapa.etapa if etapa else None,
            financeiro_status=controle.status if controle else "sem_controle", situacao=situacao,
            valor_contratado=moeda(valor), total_recebido=moeda(recebido), total_repassado=moeda(repassado),
            saldo_cliente=moeda(saldo_cliente), saldo_fornecedor=moeda(saldo_fornecedor),
            disponivel_repasse=moeda(disponivel), entrega_concluida=entregue, pendencias=pendencias,
            atualizado_em=ultima_data(contrato.criada_em, contrato.encerrada_em, contrato.cancelada_em,
                ordem.criada_em if ordem else None, ordem.concluida_em if ordem else None,
                ordem.cancelada_em if ordem else None, ciclo.atualizado_em if ciclo else None,
                controle.atualizado_em if controle else None, etapa.criada_em if etapa else None))

    @staticmethod
    def _indicadores(itens) -> IndicadoresPainel:
        abertos = [i for i in itens if i.financeiro_status == "aberto"]
        def soma(lista, campo):
            return moeda(sum(centavos(getattr(i, campo)) for i in lista))
        def area(i, nome):
            return any(p.area == nome for p in i.pendencias)
        return IndicadoresPainel(total_contratacoes=len(itens),
            contratacoes_ativas=sum(i.contratacao_status == "ativa" for i in itens),
            acompanhamento_operacional=sum(area(i, "operacional") for i in itens),
            pendencias_financeiras=sum(area(i, "financeira") for i in itens),
            para_conferencia=sum(i.situacao == "verificar" for i in itens),
            contratacoes_concluidas=sum(i.situacao == "concluida" for i in itens),
            contratacoes_canceladas=sum(i.situacao == "cancelada" for i in itens),
            financeiros_encerrados=sum(i.financeiro_status == "encerrado" and i.situacao == "concluida" for i in itens),
            controles_abertos=len(abertos), recebimentos_confirmados=soma(itens, "total_recebido"),
            repasses_confirmados=soma(itens, "total_repassado"),
            saldo_clientes_controles_abertos=soma(abertos, "saldo_cliente"),
            saldo_fornecedores_controles_abertos=soma(abertos, "saldo_fornecedor"),
            disponivel_repasses=soma(abertos, "disponivel_repasse"))

    @staticmethod
    def _corresponde(item, busca):
        termo = texto_busca(busca)
        alvo = re.fullmatch(r"(os|contratacao)\s*#?\s*([0-9]{1,13})", termo)
        if alvo:
            return (item.ordem_servico_id if alvo[1] == "os" else item.contratacao_id) == int(alvo[2])
        numero = re.fullmatch(r"#?([0-9]{1,13})", termo)
        if numero:
            return int(numero[1]) in {item.contratacao_id, item.ordem_servico_id}
        return termo in texto_busca(item.cliente) or termo in texto_busca(item.fornecedor)

    def consultar(self, usuario, filtro="todas", busca="", deslocamento=0, limite=20) -> ConsultaPainel:
        exigir_admin(usuario)
        if filtro not in FILTROS or deslocamento < 0 or not 1 <= limite <= 100 or len(busca) > 120:
            raise HTTPException(422, detail="filtro_painel_invalido")
        busca = busca.strip()
        # Um SELECT oferece a mesma fotografia a indicadores, filtro e página.
        # Consulta em lote; nenhum GET inicia ciclo, movimenta dinheiro ou encerra contratos.
        with self.banco.no_autoflush:
            itens = [self._item(linha) for linha in self.banco.execute(self._consulta()).all()]
        indicadores = self._indicadores(itens)
        if filtro in {"operacionais", "financeiras"}:
            area = "operacional" if filtro == "operacionais" else "financeira"
            itens = [i for i in itens if any(p.area == area for p in i.pendencias)]
        elif filtro != "todas":
            situacao = {"verificar": "verificar", "concluidas": "concluida", "canceladas": "cancelada"}[filtro]
            itens = [i for i in itens if i.situacao == situacao]
        if busca:
            itens = [i for i in itens if self._corresponde(i, busca)]
        return ConsultaPainel(indicadores=indicadores, itens=itens[deslocamento:deslocamento + limite],
            total=len(itens), deslocamento=deslocamento, limite=limite, filtro=filtro, busca=busca, atualizado_em=instante())
