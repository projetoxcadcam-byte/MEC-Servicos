from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.models.financeiro_administrativo import ControleFinanceiro, EventoFinanceiro, RepasseAdministrativo
from backend.app.schemas.financeiro_administrativo import (
    ConsultaFinanceiroPortal, DetalheFinanceiro, EventoFinanceiroLeitura, MovimentoFinanceiro,
    PaginaFinanceiro, PaginaFinanceiroPortal, ResumoFinanceiro,
)
from backend.app.services.intermediacao import exigir_admin, instante


def centavos(valor) -> int:
    numero = Decimal(str(valor)) * 100
    if not numero.is_finite() or numero != numero.to_integral_value():
        raise HTTPException(409, detail="valor_financeiro_inconsistente")
    return int(numero)


def moeda(valor: int) -> Decimal:
    return (Decimal(valor) / 100).quantize(Decimal("0.01"))


def bloquear_pagamento_legado(banco: Session, contratacao_id: int) -> None:
    # A mesma trava usada pelo D32 evita uma gravação antiga concorrente ao início.
    banco.execute(update(ContratacaoServico).where(ContratacaoServico.id == contratacao_id)
                  .values(status=ContratacaoServico.status), execution_options={"synchronize_session": False})
    banco.expire_all()
    if banco.get(ControleFinanceiro, contratacao_id):
        raise HTTPException(409, detail="contratacao_usa_financeiro_administrativo")


def proteger_financeiro_legado(banco: Session, caminho: str, metodo: str) -> None:
    if metodo not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    alvo = re.fullmatch(r"/contratacoes(?:-servico)?/([1-9]\d*)/(?:cancelar|encerrar)", caminho)
    solicitacao = re.fullmatch(r"/solicitacoes-servico/([1-9]\d*)/contratacao/(?:cancelar|encerrar)", caminho)
    if alvo:
        bloquear_pagamento_legado(banco, int(alvo[1]))
    elif solicitacao:
        banco.execute(update(ContratacaoServico).where(ContratacaoServico.solicitacao_id == int(solicitacao[1]))
                      .values(status=ContratacaoServico.status), execution_options={"synchronize_session": False})
        banco.expire_all()
        cid = banco.scalar(select(ContratacaoServico.id).where(ContratacaoServico.solicitacao_id == int(solicitacao[1])))
        if cid and banco.get(ControleFinanceiro, cid):
            raise HTTPException(409, detail="contratacao_usa_financeiro_administrativo")


class ServicoFinanceiroAdministrativo:
    def __init__(self, banco: Session):
        self.banco = banco

    def _contrato(self, cid):
        contrato = self.banco.get(ContratacaoServico, cid)
        if contrato is None:
            raise HTTPException(404, detail="contratacao_nao_encontrada")
        return contrato

    def _travar(self, cid):
        self.banco.execute(update(ContratacaoServico).where(ContratacaoServico.id == cid)
            .values(status=ContratacaoServico.status), execution_options={"synchronize_session": False})
        self.banco.expire_all()
        return self._contrato(cid)

    def _recebimentos(self, cid):
        return self.banco.scalars(select(PagamentoContratacao).where(PagamentoContratacao.contratacao_id == cid)
                                 .order_by(PagamentoContratacao.id)).all()

    def _repasses(self, cid):
        return self.banco.scalars(select(RepasseAdministrativo).where(RepasseAdministrativo.contratacao_id == cid)
                                 .order_by(RepasseAdministrativo.id)).all()

    def _resumo(self, contrato):
        cid = contrato.id
        controle = self.banco.get(ControleFinanceiro, cid)
        ordem = self.banco.scalar(select(OrdemServico).where(OrdemServico.contratacao_id == cid))
        ciclo = self.banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == ordem.id)) if ordem else None
        entregue = bool(ordem and ordem.status == "concluida" and ciclo and ciclo.status == "entregue_cliente")
        valor = centavos(contrato.valor_total)
        from backend.app.services.precos_portais import custo_contratacao
        custo = centavos(custo_contratacao(self.banco,contrato))
        recebido = sum(centavos(p.valor) for p in self._recebimentos(cid) if p.status == "confirmado")
        repassado = sum(p.valor_centavos for p in self._repasses(cid) if p.status == "confirmado")
        cliente = self.banco.get(Empresa, contrato.empresa_cliente_id)
        fornecedor = self.banco.get(Empresa, contrato.empresa_fornecedora_id)
        return ResumoFinanceiro(contratacao_id=cid, ordem_servico_id=ordem.id if ordem else None,
            contratacao_status=contrato.status, valor_contratado=moeda(valor), valor_fornecedor=moeda(custo), acrescimo_administracao=moeda(valor-custo), total_recebido=moeda(recebido),
            saldo_cliente=moeda(max(0, valor-recebido)), total_repassado=moeda(repassado),
            saldo_fornecedor=moeda(max(0, custo-repassado)),
            disponivel_repasse=moeda(max(0, min(custo, recebido)-repassado)) if entregue else moeda(0),
            entrega_concluida=entregue, status=controle.status if controle else "sem_controle",
            versao=controle.versao if controle else 0, atualizado_em=controle.atualizado_em if controle else None,
            cliente=cliente.razao_social if cliente else "Empresa indisponível",
            fornecedor=fornecedor.razao_social if fornecedor else "Empresa indisponível",
            pode_iniciar=not controle and contrato.status == "ativa" and recebido <= valor)

    @staticmethod
    def _movimento(item, tipo):
        def data(valor):
            if valor is None: return None
            if isinstance(valor, str): return valor
            return valor.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z") if valor.tzinfo is None else valor.isoformat()
        recebimento = tipo == "recebimento"
        return MovimentoFinanceiro(id=item.id, tipo=tipo,
            valor=item.valor if recebimento else moeda(item.valor_centavos), forma_pagamento=item.forma_pagamento,
            status="estornado" if item.status == "cancelado" else item.status,
            registrado_em=data(item.paga_em if recebimento else item.registrado_em),
            estornado_em=data(item.cancelada_em if recebimento else item.estornado_em))

    def obter(self, cid, usuario):
        exigir_admin(usuario)
        resumo = self._resumo(self._contrato(cid))
        recebimentos, repasses = self._recebimentos(cid), self._repasses(cid)
        acoes = []
        if resumo.status == "aberto" and resumo.contratacao_status == "ativa":
            if resumo.saldo_cliente > 0: acoes.append("recebimento")
            if resumo.disponivel_repasse > 0: acoes.append("repasse")
            if any(p.status == "confirmado" for p in recebimentos): acoes.append("estornar_recebimento")
            if any(p.status == "confirmado" for p in repasses): acoes.append("estornar_repasse")
            if resumo.entrega_concluida and resumo.saldo_cliente == 0 and resumo.saldo_fornecedor == 0:
                acoes.append("encerrar")
        elif resumo.status == "encerrado" and resumo.contratacao_status == "encerrada":
            acoes.append("reabrir")
        eventos = self.banco.scalars(select(EventoFinanceiro).where(EventoFinanceiro.contratacao_id == cid)
                                    .order_by(EventoFinanceiro.versao)).all()
        return DetalheFinanceiro(resumo=resumo, acoes_permitidas=acoes,
            recebimentos=[self._movimento(p, "recebimento") for p in recebimentos],
            repasses=[self._movimento(p, "repasse") for p in repasses],
            historico=[EventoFinanceiroLeitura.model_validate(p) for p in eventos])

    def _listar(self, usuario, deslocamento, limite, perfil=None, empresa_id=None):
        consulta = select(ContratacaoServico)
        if perfil:
            if usuario.perfil != perfil or usuario.empresa_id != empresa_id:
                raise HTTPException(403, detail="empresa_diverge_da_sessao")
            coluna = ContratacaoServico.empresa_cliente_id if perfil == "cliente" else ContratacaoServico.empresa_fornecedora_id
            consulta = consulta.where(coluna == usuario.empresa_id)
        else: exigir_admin(usuario)
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        contratos = self.banco.scalars(consulta.order_by(ContratacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return contratos, total

    def listar(self, usuario, deslocamento, limite):
        contratos, total = self._listar(usuario, deslocamento, limite)
        return PaginaFinanceiro(itens=[self._resumo(c) for c in contratos], total=total, deslocamento=deslocamento, limite=limite)

    def _portal(self, contrato, perfil):
        resumo = self._resumo(contrato)
        recebimento = perfil == "cliente"
        movimentos = self._recebimentos(contrato.id) if recebimento else self._repasses(contrato.id)
        return ConsultaFinanceiroPortal(contratacao_id=contrato.id, ordem_servico_id=resumo.ordem_servico_id,
            valor_contratado=resumo.valor_contratado if recebimento else resumo.valor_fornecedor,
            total_confirmado=resumo.total_recebido if recebimento else resumo.total_repassado,
            saldo=resumo.saldo_cliente if recebimento else resumo.saldo_fornecedor,
            status=resumo.status, entrega_concluida=resumo.entrega_concluida,
            movimentos=[self._movimento(p, "recebimento" if recebimento else "repasse") for p in movimentos])

    def listar_portal(self, usuario, perfil, empresa_id, deslocamento, limite):
        contratos, total = self._listar(usuario, deslocamento, limite, perfil, empresa_id)
        return PaginaFinanceiroPortal(itens=[self._portal(c, perfil) for c in contratos], total=total,
                                     deslocamento=deslocamento, limite=limite)

    def consultar_portal(self, cid, usuario, perfil, empresa_id):
        if usuario.perfil != perfil or usuario.empresa_id != empresa_id:
            raise HTTPException(403, detail="empresa_diverge_da_sessao")
        contrato = self._contrato(cid)
        dono = contrato.empresa_cliente_id if perfil == "cliente" else contrato.empresa_fornecedora_id
        if dono != usuario.empresa_id:
            raise HTTPException(404, detail="contratacao_nao_encontrada")
        return self._portal(contrato, perfil)

    def _evento(self, controle, usuario, acao, registro, **campos):
        evento = EventoFinanceiro(contratacao_id=controle.contratacao_id, versao=controle.versao, acao=acao,
            usuario_admin_id=usuario.usuario_id, administrador_nome=usuario.nome, registro_interno=registro,
            criado_em=controle.atualizado_em, **campos)
        self.banco.add(evento)

    def iniciar(self, cid, dados, usuario):
        exigir_admin(usuario)
        try:
            contrato = self._travar(cid)
            if self.banco.get(ControleFinanceiro, cid):
                raise HTTPException(409, detail="financeiro_ja_iniciado")
            resumo = self._resumo(contrato)
            if not resumo.pode_iniciar:
                raise HTTPException(409, detail="contratacao_sem_condicoes_financeiras")
            agora = instante()
            controle = ControleFinanceiro(contratacao_id=cid, valor_contratado_centavos=centavos(contrato.valor_total),
                versao=1, status="aberto", criado_em=agora, atualizado_em=agora)
            self.banco.add(controle); self.banco.flush()
            self._evento(controle, usuario, "iniciar", dados.registro_interno)
            self.banco.commit()
        except HTTPException:
            self.banco.rollback(); raise
        except IntegrityError:
            self.banco.rollback(); raise HTTPException(409, detail="financeiro_ja_iniciado") from None
        return self.obter(cid, usuario)

    def registrar(self, cid, dados, usuario):
        exigir_admin(usuario)
        digest = hashlib.sha256(json.dumps(dados.model_dump(mode="json", exclude={"versao", "chave_operacao"}),
                                          sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        try:
            contrato = self._travar(cid)
            controle = self.banco.get(ControleFinanceiro, cid)
            if controle is None: raise HTTPException(409, detail="financeiro_nao_iniciado")
            anterior = self.banco.scalar(select(EventoFinanceiro).where(EventoFinanceiro.contratacao_id == cid,
                                          EventoFinanceiro.chave_operacao == str(dados.chave_operacao)))
            if anterior:
                if anterior.resumo_operacao != digest: raise HTTPException(409, detail="chave_financeira_reutilizada")
                self.banco.rollback()
                return self.obter(cid, usuario)
            if controle.versao != dados.versao: raise HTTPException(409, detail="financeiro_alterado_atualize")
            if controle.valor_contratado_centavos != centavos(contrato.valor_total):
                raise HTTPException(409, detail="valor_financeiro_inconsistente")
            if dados.acao == "reabrir":
                if controle.status != "encerrado" or contrato.status != "encerrada":
                    raise HTTPException(409, detail="financeiro_nao_encerrado")
            elif controle.status != "aberto" or contrato.status != "ativa":
                raise HTTPException(409, detail="financeiro_fechado")
            if dados.referencia and self.banco.scalar(select(EventoFinanceiro.id).where(
                    EventoFinanceiro.contratacao_id == cid, EventoFinanceiro.referencia == dados.referencia)):
                raise HTTPException(409, detail="referencia_financeira_duplicada")
            resumo = self._resumo(contrato)
            campos = {}; agora = instante()
            if dados.acao == "recebimento":
                if dados.valor > resumo.saldo_cliente: raise HTTPException(409, detail="recebimento_supera_saldo")
                pagamento = PagamentoContratacao(contratacao_id=cid, empresa_cliente_id=contrato.empresa_cliente_id,
                    empresa_fornecedora_id=contrato.empresa_fornecedora_id, valor=dados.valor,
                    forma_pagamento=dados.forma_pagamento, status="confirmado", paga_em=datetime.now(UTC))
                self.banco.add(pagamento); self.banco.flush()
                campos = {"pagamento_id": pagamento.id, "valor_centavos": centavos(dados.valor)}
            elif dados.acao == "repasse":
                if not resumo.entrega_concluida: raise HTTPException(409, detail="repasse_aguarda_entrega")
                if dados.valor > resumo.disponivel_repasse: raise HTTPException(409, detail="repasse_supera_disponivel")
                repasse = RepasseAdministrativo(contratacao_id=cid, valor_centavos=centavos(dados.valor),
                    forma_pagamento=dados.forma_pagamento, status="confirmado", registrado_em=agora)
                self.banco.add(repasse); self.banco.flush()
                campos = {"repasse_id": repasse.id, "valor_centavos": repasse.valor_centavos}
            elif dados.acao == "estornar_recebimento":
                pagamento = self.banco.get(PagamentoContratacao, dados.movimento_id)
                if pagamento is None or pagamento.contratacao_id != cid:
                    raise HTTPException(404, detail="movimento_financeiro_nao_encontrado")
                if pagamento.status != "confirmado": raise HTTPException(409, detail="movimento_ja_estornado")
                if resumo.total_recebido - pagamento.valor < resumo.total_repassado:
                    raise HTTPException(409, detail="estorno_recebimento_descobre_repasse")
                pagamento.status = "cancelado"; pagamento.cancelada_em = datetime.now(UTC)
                campos = {"pagamento_id": pagamento.id, "valor_centavos": centavos(pagamento.valor)}
            elif dados.acao == "estornar_repasse":
                repasse = self.banco.get(RepasseAdministrativo, dados.movimento_id)
                if repasse is None or repasse.contratacao_id != cid:
                    raise HTTPException(404, detail="movimento_financeiro_nao_encontrado")
                if repasse.status != "confirmado": raise HTTPException(409, detail="movimento_ja_estornado")
                repasse.status = "estornado"; repasse.estornado_em = agora
                campos = {"repasse_id": repasse.id, "valor_centavos": repasse.valor_centavos}
            elif dados.acao == "encerrar":
                if not resumo.entrega_concluida or resumo.saldo_cliente or resumo.saldo_fornecedor:
                    raise HTTPException(409, detail="financeiro_tem_pendencias")
                contrato.status = "encerrada"; contrato.encerrada_em = datetime.now(UTC)
                controle.status = "encerrado"
            elif dados.acao == "reabrir":
                contrato.status = "ativa"; contrato.encerrada_em = None; controle.status = "aberto"
            controle.versao += 1; controle.atualizado_em = agora
            self._evento(controle, usuario, dados.acao, dados.registro_interno,
                chave_operacao=str(dados.chave_operacao), resumo_operacao=digest, referencia=dados.referencia, **campos)
            self.banco.commit()
        except HTTPException:
            self.banco.rollback(); raise
        except IntegrityError:
            self.banco.rollback(); raise HTTPException(409, detail="financeiro_alterado_atualize") from None
        return self.obter(cid, usuario)
