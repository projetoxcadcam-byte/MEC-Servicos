from __future__ import annotations

import csv
import io
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.app.schemas.central_pendencias import AcaoPendencia, ConsultaPendencias, FiltrosPendencias, ItemPendencia
from backend.app.services.financeiro_administrativo import centavos, moeda
from backend.app.services.intermediacao import exigir_admin, instante
from backend.app.services.painel_administrativo import ServicoPainelAdministrativo
from backend.app.services.relatorio_administrativo import celula_csv
from backend.app.services.relatorio_empresas import ServicoRelatorioEmpresas

ACOES = {
    "criar_ordem": ("operacional", "Criar ordem de serviço"),
    "iniciar_intermediacao": ("operacional", "Iniciar intermediação"),
    "receber_material": ("operacional", "Receber material"),
    "encaminhar_material": ("operacional", "Encaminhar material ao fornecedor"),
    "acompanhar_producao": ("operacional", "Acompanhar produção"),
    "solicitar_coleta": ("operacional", "Solicitar coleta"),
    "receber_pecas": ("operacional", "Receber peças"),
    "iniciar_avaliacao": ("operacional", "Iniciar avaliação"),
    "avaliar_pecas": ("operacional", "Avaliar peças"),
    "encaminhar_retrabalho": ("operacional", "Encaminhar retrabalho"),
    "entregar_cliente": ("operacional", "Entregar ao cliente"),
    "iniciar_financeiro": ("financeira", "Iniciar controle financeiro"),
    "receber_cliente": ("financeira", "Conferir recebimento do cliente"),
    "repasse_aguarda_entrega": ("financeira", "Conferir entrega antes do repasse"),
    "repasse_aguarda_recebimento": ("financeira", "Conferir cobertura antes do repasse"),
    "repassar_fornecedor": ("financeira", "Conferir repasse ao fornecedor"),
    "encerrar_financeiro": ("financeira", "Conferir encerramento financeiro"),
    "conferir_valores": ("conferencia", "Conferir valores e cobertura"),
    "conferir_valor_contratado": ("conferencia", "Conferir valor do controle financeiro"),
    "conferir_encerramento": ("conferencia", "Conferir situações de encerramento"),
    "conferir_financeiro_encerrado": ("conferencia", "Conferir financeiro encerrado"),
    "conferir_entrega": ("conferencia", "Conferir situação da entrega"),
    "conferir_cancelamento": ("conferencia", "Conferir situação de cancelamento"),
    "conferir_ordem_anterior": ("conferencia", "Conferir ordem do fluxo anterior"),
}


class ServicoCentralPendencias:
    def __init__(self, banco: Session):
        self.banco = banco

    def _dados(self, usuario, data_inicial, data_final, filtro, busca, area, acao):
        exigir_admin(usuario)
        if area not in {"todas", "operacional", "financeira", "conferencia"} or (acao and acao not in ACOES):
            raise HTTPException(422, detail="filtro_pendencias_invalido")
        # A consulta D36 reutiliza os critérios e a fotografia única do D33.
        anteriores, contratos = ServicoRelatorioEmpresas(self.banco)._dados(
            usuario, "clientes", data_inicial, data_final, filtro, busca, None)
        filtros = FiltrosPendencias(data_inicial=anteriores.data_inicial, data_final=anteriores.data_final,
            filtro=anteriores.filtro, busca=anteriores.busca, area=area, acao=acao)
        itens = []
        for contrato in contratos:
            for pendencia in contrato.pendencias:
                if (area != "todas" and pendencia.area != area) or (acao and pendencia.codigo != acao):
                    continue
                destino = "relatorio" if pendencia.area == "conferencia" else (
                    "intermediacao" if pendencia.area == "operacional" or pendencia.codigo == "repasse_aguarda_entrega" else "financeiro")
                if destino == "relatorio": caminho = "/admin/relatorios?contratacao=" + str(contrato.contratacao_id)
                elif destino == "financeiro": caminho = "/admin/pagamentos?contratacao=" + str(contrato.contratacao_id)
                else:
                    caminho = "/admin/intermediacao?" + ("ordem=" + str(contrato.ordem_servico_id)
                        if contrato.ordem_servico_id else "contratacao=" + str(contrato.contratacao_id))
                itens.append(ItemPendencia(contratacao=contrato, pendencia=pendencia,
                    acao=ACOES.get(pendencia.codigo, (pendencia.area, pendencia.descricao))[1], caminho=caminho, destino=destino))
        itens.sort(key=lambda i: (i.contratacao.contratada_em, i.contratacao.contratacao_id, i.pendencia.area, i.pendencia.codigo))
        return filtros, itens

    @staticmethod
    def _contratos(itens):
        return list({i.contratacao.contratacao_id: i.contratacao for i in itens}.values())

    @classmethod
    def _montar(cls, filtros, itens, deslocamento, limite):
        contratos = cls._contratos(itens)
        return ConsultaPendencias(filtros=filtros,
            catalogo_acoes=[AcaoPendencia(codigo=c, area=a, rotulo=r) for c, (a, r) in sorted(ACOES.items(), key=lambda p: (p[1][0], p[1][1]))],
            itens=itens[deslocamento:deslocamento + limite], total_pendencias=len(itens), total_contratacoes=len(contratos),
            pendencias_operacionais=sum(i.pendencia.area == "operacional" for i in itens),
            pendencias_financeiras=sum(i.pendencia.area == "financeira" for i in itens),
            pendencias_conferencia=sum(i.pendencia.area == "conferencia" for i in itens),
            indicadores=ServicoPainelAdministrativo._indicadores(contratos),
            valor_contratado=moeda(sum(centavos(c.valor_contratado) for c in contratos)),
            deslocamento=deslocamento, limite=limite, gerado_em=instante())

    def consultar(self, usuario, data_inicial="", data_final="", filtro="todas", busca="", area="todas", acao="", deslocamento=0, limite=20):
        exigir_admin(usuario)
        if deslocamento < 0 or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtro_pendencias_invalido")
        filtros, itens = self._dados(usuario, data_inicial, data_final, filtro, busca, area, acao)
        return self._montar(filtros, itens, deslocamento, limite)

    def exportar(self, usuario, data_inicial="", data_final="", filtro="todas", busca="", area="todas", acao="") -> bytes:
        filtros, itens = self._dados(usuario, data_inicial, data_final, filtro, busca, area, acao)
        consulta = self._montar(filtros, itens, 0, 100)
        colunas = ["Tipo de registro", "Campo", "Informação", "Área", "Código da ação", "Ação", "Orientação", "Destino",
            "Contratação", "OS", "Contratada em UTC", "Cliente ID", "Cliente", "Fornecedor ID", "Fornecedor",
            "Situação no painel", "Financeiro", "Quantidade de pendências", "Quantidade de contratações",
            "Valor contratado", "Recebido confirmado", "Repassado confirmado", "Saldo de clientes com controle aberto",
            "Saldo de fornecedores com controle aberto", "Disponível para repasse"]
        saida = io.StringIO(newline=""); escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def escrever(tipo, **valores):
            escritor.writerow([celula_csv({"Tipo de registro": tipo, **valores}.get(c)) for c in colunas])
        def dinheiro(v): return format(v, ".2f").replace(".", ",")
        for campo, valor in [("Consulta gerada em UTC", consulta.gerado_em), ("Data inicial UTC", filtros.data_inicial),
                ("Data final UTC", filtros.data_final), ("Exibir", filtros.filtro), ("Busca", filtros.busca), ("Área", filtros.area), ("Ação", filtros.acao),
                ("Critério do período", "Data de criação da contratação em UTC, com os dois dias incluídos."),
                ("Critério da fila", "Pendências atuais calculadas pelo painel administrativo; uma linha por ação."),
                ("Critério dos valores", "Cada contratação soma uma vez. Acumulados atuais, excluídos movimentos estornados."),
                ("Critério dos saldos", "Somente controles financeiros abertos, conforme o painel administrativo."),
                ("Abrangência", "Todas as pendências e contratações dos filtros aplicados; não apenas a página visível."),
                ("Ordenação", "Data da contratação da mais antiga à mais recente, seguida de ID, área e ação.")]:
            escrever("Filtro", **{"Campo": campo, "Informação": valor})
        i = consulta.indicadores
        escrever("Total", **{"Quantidade de pendências": consulta.total_pendencias, "Quantidade de contratações": consulta.total_contratacoes,
            "Valor contratado": dinheiro(consulta.valor_contratado), "Recebido confirmado": dinheiro(i.recebimentos_confirmados),
            "Repassado confirmado": dinheiro(i.repasses_confirmados), "Saldo de clientes com controle aberto": dinheiro(i.saldo_clientes_controles_abertos),
            "Saldo de fornecedores com controle aberto": dinheiro(i.saldo_fornecedores_controles_abertos), "Disponível para repasse": dinheiro(i.disponivel_repasses)})
        for area, qtd in [("operacional", consulta.pendencias_operacionais), ("financeira", consulta.pendencias_financeiras), ("conferencia", consulta.pendencias_conferencia)]:
            escrever("Área", **{"Área": area, "Quantidade de pendências": qtd})
        def contexto(c):
            return {"Contratação": c.contratacao_id, "OS": c.ordem_servico_id, "Contratada em UTC": c.contratada_em,
                "Cliente ID": c.empresa_cliente_id, "Cliente": c.cliente, "Fornecedor ID": c.empresa_fornecedora_id,
                "Fornecedor": c.fornecedor, "Situação no painel": c.situacao, "Financeiro": c.financeiro_status}
        for item in itens:
            escrever("Pendência", **{**contexto(item.contratacao), "Área": item.pendencia.area, "Código da ação": item.pendencia.codigo,
                "Ação": item.acao, "Orientação": item.pendencia.descricao, "Destino": item.caminho, "Quantidade de pendências": 1})
        for c in self._contratos(itens):
            aberto = c.financeiro_status == "aberto"
            escrever("Contratação", **{**contexto(c), "Quantidade de contratações": 1, "Valor contratado": dinheiro(c.valor_contratado),
                "Recebido confirmado": dinheiro(c.total_recebido), "Repassado confirmado": dinheiro(c.total_repassado),
                "Saldo de clientes com controle aberto": dinheiro(c.saldo_cliente) if aberto else "",
                "Saldo de fornecedores com controle aberto": dinheiro(c.saldo_fornecedor) if aberto else "",
                "Disponível para repasse": dinheiro(c.disponivel_repasse) if aberto else ""})
        return saida.getvalue().encode("utf-8-sig")
