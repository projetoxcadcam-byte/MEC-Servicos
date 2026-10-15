from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.relatorio_administrativo import CadastroRelatorio, RegistroRelatorio, RelatorioContratacao
from backend.app.services.financeiro_administrativo import ServicoFinanceiroAdministrativo, moeda
from backend.app.services.intermediacao import ServicoIntermediacao, exigir_admin, instante
from backend.app.services.painel_administrativo import ServicoPainelAdministrativo

ACOES = {
    "iniciar_ciclo": "Iniciar ciclo administrativo", "receber_material": "Receber material",
    "encaminhar_material": "Encaminhar material ao fornecedor", "solicitar_coleta": "Solicitar coleta das peças",
    "receber_pecas": "Receber peças", "iniciar_avaliacao": "Iniciar avaliação das peças",
    "aprovar_pecas": "Aprovar peças para entrega", "solicitar_retrabalho": "Solicitar retrabalho",
    "encaminhar_retrabalho": "Encaminhar peças para retrabalho", "entregar_cliente": "Concluir entrega ao cliente e OS",
    "cancelar": "Cancelar ciclo e OS", "iniciar": "Iniciar controle financeiro",
    "recebimento": "Registrar recebimento do cliente", "repasse": "Registrar repasse ao fornecedor",
    "estornar_recebimento": "Estornar recebimento", "estornar_repasse": "Estornar repasse",
    "encerrar": "Encerrar financeiro e contratação", "reabrir": "Reabrir financeiro e contratação",
}
ETAPAS = {"aguardando_material": "Aguardando material", "em_usinagem": "Em usinagem",
          "em_solda_dobra": "Em solda/dobra", "em_acabamento": "Em acabamento", "pronto_para_envio": "Pronto para coleta"}
ORIGENS = {"producao": "Produção", "intermediacao": "Intermediação", "financeiro": "Financeiro"}


def data_utc(valor) -> str | None:
    if valor is None:
        return None
    try:
        data = valor if isinstance(valor, datetime) else datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if data.tzinfo is None:
            data = data.replace(tzinfo=UTC)
        return data.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError):
        raise HTTPException(409, detail="data_relatorio_inconsistente") from None


def celula_csv(valor) -> str:
    texto = "" if valor is None else str(valor)
    # Neutraliza fórmulas em campos livres, incluindo prefixos de espaço/BOM.
    inicio = 0
    while inicio < len(texto) and (texto[inicio].isspace() or texto[inicio] == "\ufeff"):
        inicio += 1
    if (inicio < len(texto) and texto[inicio] in "=+-@") or texto.startswith(("\t", "\r", "\n")):
        return "'" + texto
    return texto


class ServicoRelatorioAdministrativo:
    def __init__(self, banco: Session):
        self.banco = banco

    def obter(self, cid: int, usuario) -> RelatorioContratacao:
        exigir_admin(usuario)
        # SQLite legado não inicia uma transação para SELECT. BEGIN mantém as
        # diversas consultas do relatório no mesmo retrato, sem trava de escrita.
        conexao = self.banco.connection()
        if conexao.dialect.name == "sqlite" and not conexao.connection.driver_connection.in_transaction:
            conexao.exec_driver_sql("BEGIN")
        painel = ServicoPainelAdministrativo(self.banco)
        linha = self.banco.execute(painel._consulta().where(ContratacaoServico.id == cid)).first()
        if linha is None:
            raise HTTPException(404, detail="contratacao_nao_encontrada")
        resumo = painel._item(linha)
        contrato, ordem, ciclo = linha[:3]
        solicitacao = self.banco.get(SolicitacaoServico, contrato.solicitacao_id)
        processo = self.banco.get(ProcessoFabricacao, ordem.processo_id if ordem else solicitacao.processo_id) if (ordem or solicitacao) else None
        material = self.banco.get(Material, ordem.material_id if ordem else solicitacao.material_id) if (ordem or solicitacao) else None
        financeiro = ServicoFinanceiroAdministrativo(self.banco).obter(cid, usuario)
        registros = []
        avisos = []
        if ordem:
            etapas = self.banco.execute(select(EtapaProducao, Empresa.razao_social).outerjoin(
                Empresa, Empresa.id == EtapaProducao.empresa_fornecedora_id).where(
                EtapaProducao.ordem_servico_id == ordem.id).order_by(EtapaProducao.id)).all()
            for etapa, fornecedor in etapas:
                registros.append(RegistroRelatorio(origem="producao", registro_id=etapa.id,
                    data_utc=data_utc(etapa.criada_em), acao=etapa.etapa,
                    descricao=ETAPAS.get(etapa.etapa, "Etapa de produção registrada"), situacao=etapa.etapa,
                    responsavel=fornecedor, empresa_fornecedora_id=etapa.empresa_fornecedora_id,
                    registro_interno=etapa.observacoes))
            if not etapas:
                avisos.append("Sem etapas de produção registradas para esta OS.")
            administrativo = ServicoIntermediacao(self.banco).obter(ordem.id, usuario)
            for evento in administrativo.historico:
                registros.append(RegistroRelatorio(origem="intermediacao", registro_id=evento.id,
                    versao=evento.versao, data_utc=data_utc(evento.criado_em), acao=evento.acao,
                    descricao=ACOES.get(evento.acao, "Registro de intermediação"),
                    situacao=evento.status_resultante, responsavel=evento.administrador_nome,
                    usuario_admin_id=evento.usuario_admin_id, quantidade=evento.quantidade_conferida,
                    referencia=evento.referencia, registro_interno=evento.registro_interno,
                    parecer_tecnico=evento.parecer_tecnico))
            if not ciclo or not administrativo.historico:
                avisos.append("Sem eventos de intermediação administrativa registrados para esta OS.")
        else:
            avisos.append("Sem ordem de serviço vinculada a esta contratação.")
        for evento in financeiro.historico:
            registros.append(RegistroRelatorio(origem="financeiro", registro_id=evento.id,
                versao=evento.versao, data_utc=data_utc(evento.criado_em), acao=evento.acao,
                descricao=ACOES.get(evento.acao, "Registro financeiro"), responsavel=evento.administrador_nome,
                usuario_admin_id=evento.usuario_admin_id, pagamento_id=evento.pagamento_id, repasse_id=evento.repasse_id,
                valor=moeda(evento.valor_centavos) if evento.valor_centavos is not None else None,
                referencia=evento.referencia, registro_interno=evento.registro_interno))
        if resumo.financeiro_status == "sem_controle":
            avisos.append("Sem controle financeiro administrativo registrado. Recebimentos anteriores, quando existentes, constam na lista de movimentos.")
            if resumo.contratacao_status in {"encerrada", "cancelada"}:
                avisos.append("Contratação finalizada no histórico anterior. As diferenças de valores refletem os movimentos disponíveis e não criam nova pendência financeira.")
        # Em datas iguais, ordem fixa por origem e versão evita trocar a ordem
        # dos eventos entre consultas; os identificadores são locais à origem.
        prioridade = {"producao": 0, "intermediacao": 1, "financeiro": 2}
        registros.sort(key=lambda r: (r.data_utc, prioridade[r.origem], r.versao or 0, r.registro_id))
        return RelatorioContratacao(gerado_em=instante(), resumo=resumo,
            cadastro=CadastroRelatorio(cotacao_id=contrato.cotacao_id, empresa_cliente_id=contrato.empresa_cliente_id,
                empresa_fornecedora_id=contrato.empresa_fornecedora_id,
                quantidade=ordem.quantidade if ordem else solicitacao.quantidade if solicitacao else None,
                prazo_dias=contrato.prazo_dias, processo=processo.nome if processo else None,
                material=material.nome if material else None, observacoes_contratacao=contrato.observacoes,
                contratada_em=data_utc(contrato.criada_em), encerrada_em=data_utc(contrato.encerrada_em),
                cancelada_em=data_utc(contrato.cancelada_em), ordem_criada_em=data_utc(ordem.criada_em) if ordem else None,
                ordem_iniciada_em=data_utc(ordem.iniciada_em) if ordem else None,
                ordem_concluida_em=data_utc(ordem.concluida_em) if ordem else None,
                ordem_cancelada_em=data_utc(ordem.cancelada_em) if ordem else None),
            recebimentos=financeiro.recebimentos, repasses=financeiro.repasses,
            linha_tempo=registros, avisos=avisos)

    def exportar(self, cid: int, usuario) -> bytes:
        relatorio = self.obter(cid, usuario)
        r, c = relatorio.resumo, relatorio.cadastro
        saida = io.StringIO(newline="")
        colunas = ["Tipo de registro", "Contratação", "OS", "Campo / ação", "Origem", "Registro", "Versão",
                   "Data UTC", "Situação", "Valor em reais", "Forma de pagamento", "Quantidade", "Responsável",
                   "Conta administrativa", "Empresa fornecedora", "Recebimento", "Repasse", "Referência",
                   "Registro interno", "Parecer técnico", "Informação"]
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def escrever(tipo, descricao, **campos):
            valores = {"Tipo de registro": tipo, "Contratação": cid, "OS": r.ordem_servico_id, "Campo / ação": descricao, **campos}
            escritor.writerow([celula_csv(valores.get(nome)) for nome in colunas])
        def dinheiro(valor: Decimal) -> str:
            return format(valor, ".2f").replace(".", ",")
        resumo_textos = {"Consulta gerada em UTC": relatorio.gerado_em, "Cliente": r.cliente, "Fornecedor": r.fornecedor,
            "Empresa cliente": c.empresa_cliente_id, "Empresa fornecedora": c.empresa_fornecedora_id,
            "Solicitação": r.solicitacao_id, "Cotação": c.cotacao_id, "Situação da contratação": r.contratacao_status,
            "Situação da OS": r.ordem_status, "Intermediação": r.etapa_administrativa,
            "Financeiro": r.financeiro_status, "Situação no painel": r.situacao, "Quantidade contratada": c.quantidade,
            "Prazo em dias": c.prazo_dias, "Processo": c.processo, "Material": c.material,
            "Contratada em UTC": c.contratada_em, "Contratação encerrada em UTC": c.encerrada_em,
            "Contratação cancelada em UTC": c.cancelada_em, "OS criada em UTC": c.ordem_criada_em,
            "OS iniciada em UTC": c.ordem_iniciada_em, "OS concluída em UTC": c.ordem_concluida_em,
            "OS cancelada em UTC": c.ordem_cancelada_em, "Observações da contratação": c.observacoes_contratacao}
        for campo, valor in resumo_textos.items():
            escrever("Resumo", campo, **{"Informação": valor})
        for campo, valor in [("Valor contratado", r.valor_contratado), ("Recebido confirmado", r.total_recebido),
                ("Repassado confirmado", r.total_repassado), ("Saldo / diferença do cliente", r.saldo_cliente),
                ("Saldo / diferença do fornecedor", r.saldo_fornecedor), ("Disponível para repasse", r.disponivel_repasse)]:
            escrever("Resumo financeiro", campo, **{"Valor em reais": dinheiro(valor)})
        for pendencia in r.pendencias:
            escrever("Próximo passo", pendencia.descricao, **{"Origem": pendencia.area})
        for aviso in relatorio.avisos:
            escrever("Informação sobre o histórico", aviso)
        for movimento in [*relatorio.recebimentos, *relatorio.repasses]:
            escrever("Movimento", "Recebimento" if movimento.tipo == "recebimento" else "Repasse",
                **{"Origem": "Financeiro", "Registro": movimento.id, "Data UTC": data_utc(movimento.registrado_em),
                   "Situação": movimento.status, "Valor em reais": dinheiro(movimento.valor),
                   "Forma de pagamento": movimento.forma_pagamento,
                   "Informação": "Estornado em UTC: " + data_utc(movimento.estornado_em) if movimento.estornado_em else None})
        for evento in relatorio.linha_tempo:
            escrever("Evento", evento.descricao, **{"Origem": ORIGENS[evento.origem], "Registro": evento.registro_id,
                "Versão": evento.versao, "Data UTC": evento.data_utc, "Situação": evento.situacao,
                "Valor em reais": dinheiro(evento.valor) if evento.valor is not None else None,
                "Quantidade": evento.quantidade, "Responsável": evento.responsavel,
                "Conta administrativa": evento.usuario_admin_id, "Empresa fornecedora": evento.empresa_fornecedora_id,
                "Recebimento": evento.pagamento_id, "Repasse": evento.repasse_id,
                "Referência": evento.referencia, "Registro interno": evento.registro_interno, "Parecer técnico": evento.parecer_tecnico})
        return saida.getvalue().encode("utf-8-sig")
