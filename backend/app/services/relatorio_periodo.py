from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.app.schemas.relatorio_periodo import ConsultaPeriodo, FiltrosPeriodo, ItemPeriodo, MesPeriodo
from backend.app.services.financeiro_administrativo import centavos, moeda
from backend.app.services.intermediacao import exigir_admin, instante
from backend.app.services.painel_administrativo import FILTROS, ServicoPainelAdministrativo
from backend.app.services.relatorio_administrativo import celula_csv, data_utc


def validar_data(valor: str) -> str | None:
    if not valor:
        return None
    try:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", valor):
            raise ValueError
        return date.fromisoformat(valor).isoformat()
    except (ValueError, TypeError):
        raise HTTPException(422, detail="filtro_periodo_invalido") from None


class ServicoRelatorioPeriodo:
    def __init__(self, banco: Session):
        self.banco = banco

    def _dados(self, usuario, data_inicial, data_final, filtro, busca):
        exigir_admin(usuario)
        if filtro not in FILTROS or len(busca) > 120:
            raise HTTPException(422, detail="filtro_periodo_invalido")
        inicial, final = validar_data(data_inicial), validar_data(data_final)
        if inicial and final and inicial > final:
            raise HTTPException(422, detail="filtro_periodo_invalido")
        filtros = FiltrosPeriodo(data_inicial=inicial, data_final=final, filtro=filtro, busca=busca.strip())
        painel = ServicoPainelAdministrativo(self.banco)
        # A mesma consulta em lote do D33, sem consultas adicionais por contrato.
        # Indicadores, meses e página derivam desta única fotografia do banco.
        with self.banco.no_autoflush:
            linhas = self.banco.execute(painel._consulta()).all()
        itens = []
        for linha in linhas:
            criada = data_utc(linha[0].criada_em)
            if criada is None:
                raise HTTPException(409, detail="data_periodo_inconsistente")
            dia = criada[:10]
            if (inicial and dia < inicial) or (final and dia > final):
                continue
            item = painel._item(linha)
            if filtro in {"operacionais", "financeiras"}:
                area = "operacional" if filtro == "operacionais" else "financeira"
                if not any(p.area == area for p in item.pendencias):
                    continue
            elif filtro != "todas":
                if item.situacao != {"verificar": "verificar", "concluidas": "concluida", "canceladas": "cancelada"}[filtro]:
                    continue
            if filtros.busca and not painel._corresponde(item, filtros.busca):
                continue
            itens.append(ItemPeriodo(**item.model_dump(), contratada_em=criada))
        return filtros, itens

    @staticmethod
    def _montar(filtros, itens, deslocamento, limite):
        meses = {}
        total = 0
        for item in itens:
            chave = item.contratada_em[:7]
            valores = meses.setdefault(chave, [0, 0, 0, 0])
            valores[0] += 1
            valores[1] += centavos(item.valor_contratado)
            valores[2] += centavos(item.total_recebido)
            valores[3] += centavos(item.total_repassado)
            total += centavos(item.valor_contratado)
        return ConsultaPeriodo(filtros=filtros,
            indicadores=ServicoPainelAdministrativo._indicadores(itens), valor_contratado=moeda(total),
            meses=[MesPeriodo(mes=mes, total_contratacoes=v[0], valor_contratado=moeda(v[1]),
                recebido_confirmado=moeda(v[2]), repassado_confirmado=moeda(v[3])) for mes, v in sorted(meses.items())],
            itens=itens[deslocamento:deslocamento + limite], total=len(itens),
            deslocamento=deslocamento, limite=limite, gerado_em=instante())

    def consultar(self, usuario, data_inicial="", data_final="", filtro="todas", busca="", deslocamento=0, limite=20):
        exigir_admin(usuario)
        if deslocamento < 0 or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtro_periodo_invalido")
        filtros, itens = self._dados(usuario, data_inicial, data_final, filtro, busca)
        return self._montar(filtros, itens, deslocamento, limite)

    def exportar(self, usuario, data_inicial="", data_final="", filtro="todas", busca="") -> bytes:
        filtros, itens = self._dados(usuario, data_inicial, data_final, filtro, busca)
        consulta = self._montar(filtros, itens, 0, 100)
        colunas = ["Tipo de registro", "Campo", "Informação", "Mês da contratação UTC", "Contratação", "OS",
            "Contratada em UTC", "Cliente", "Fornecedor", "Situação no painel", "Financeiro",
            "Quantidade de contratações", "Valor contratado", "Recebido confirmado", "Repassado confirmado",
            "Saldo de clientes com controle aberto", "Saldo de fornecedores com controle aberto", "Disponível para repasse"]
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def dinheiro(valor: Decimal):
            return format(valor, ".2f").replace(".", ",")
        def escrever(tipo, **valores):
            escritor.writerow([celula_csv({"Tipo de registro": tipo, **valores}.get(c)) for c in colunas])
        for campo, valor in [("Consulta gerada em UTC", consulta.gerado_em), ("Data inicial UTC", filtros.data_inicial),
                ("Data final UTC", filtros.data_final), ("Exibir", filtros.filtro), ("Busca", filtros.busca),
                ("Critério do período", "Data de criação da contratação em UTC, com os dois dias incluídos."),
                ("Critério dos valores", "Acumulados atuais das contratações selecionadas; movimentos estornados excluídos."),
                ("Critério dos saldos", "Somente controles financeiros abertos, conforme o painel administrativo."),
                ("Abrangência", "Todas as contratações correspondentes aos filtros; não apenas a página visível.")]:
            escrever("Filtro", **{"Campo": campo, "Informação": valor})
        i = consulta.indicadores
        escrever("Total", **{"Quantidade de contratações": consulta.total, "Valor contratado": dinheiro(consulta.valor_contratado),
            "Recebido confirmado": dinheiro(i.recebimentos_confirmados), "Repassado confirmado": dinheiro(i.repasses_confirmados),
            "Saldo de clientes com controle aberto": dinheiro(i.saldo_clientes_controles_abertos),
            "Saldo de fornecedores com controle aberto": dinheiro(i.saldo_fornecedores_controles_abertos),
            "Disponível para repasse": dinheiro(i.disponivel_repasses)})
        for campo in ["contratacoes_ativas", "acompanhamento_operacional", "pendencias_financeiras", "para_conferencia",
                "contratacoes_concluidas", "contratacoes_canceladas", "financeiros_encerrados", "controles_abertos"]:
            rotulos = {"contratacoes_ativas": "Contratações ativas", "acompanhamento_operacional": "Em acompanhamento operacional",
                "pendencias_financeiras": "Com pendência financeira", "para_conferencia": "Para conferência",
                "contratacoes_concluidas": "Contratações concluídas", "contratacoes_canceladas": "Contratações canceladas",
                "financeiros_encerrados": "Financeiros encerrados", "controles_abertos": "Controles abertos"}
            escrever("Indicador", **{"Campo": rotulos[campo], "Informação": getattr(i, campo)})
        for mes in consulta.meses:
            escrever("Mês", **{"Mês da contratação UTC": mes.mes, "Quantidade de contratações": mes.total_contratacoes,
                "Valor contratado": dinheiro(mes.valor_contratado), "Recebido confirmado": dinheiro(mes.recebido_confirmado),
                "Repassado confirmado": dinheiro(mes.repassado_confirmado)})
        for item in itens:
            aberto = item.financeiro_status == "aberto"
            escrever("Contratação", **{"Mês da contratação UTC": item.contratada_em[:7], "Contratação": item.contratacao_id,
                "OS": item.ordem_servico_id, "Contratada em UTC": item.contratada_em, "Cliente": item.cliente, "Fornecedor": item.fornecedor,
                "Situação no painel": item.situacao, "Financeiro": item.financeiro_status, "Quantidade de contratações": 1,
                "Valor contratado": dinheiro(item.valor_contratado), "Recebido confirmado": dinheiro(item.total_recebido),
                "Repassado confirmado": dinheiro(item.total_repassado),
                "Saldo de clientes com controle aberto": dinheiro(item.saldo_cliente) if aberto else "",
                "Saldo de fornecedores com controle aberto": dinheiro(item.saldo_fornecedor) if aberto else "",
                "Disponível para repasse": dinheiro(item.disponivel_repasse) if aberto else ""})
        return saida.getvalue().encode("utf-8-sig")
