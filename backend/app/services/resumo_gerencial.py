from __future__ import annotations

import calendar
import csv
from datetime import UTC, datetime
import io
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.app.schemas.resumo_gerencial import ConsultaGerencial, FiltrosGerencial, MesGerencial, ResumoGerencial
from backend.app.services.financeiro_administrativo import centavos, moeda
from backend.app.services.intermediacao import exigir_admin, instante
from backend.app.services.painel_administrativo import FILTROS, ServicoPainelAdministrativo
from backend.app.services.relatorio_administrativo import celula_csv
from backend.app.services.relatorio_empresas import ServicoRelatorioEmpresas


class ServicoResumoGerencial:
    def __init__(self, banco: Session):
        self.banco = banco

    def _dados(self, usuario, ano, filtro, busca, mes):
        exigir_admin(usuario)
        if ano is None:
            ano = datetime.now(UTC).year
        if (type(ano) is not int or not 1 <= ano <= 9999 or filtro not in FILTROS or len(busca) > 120
                or (mes is not None and (type(mes) is not int or not 1 <= mes <= 12))):
            raise HTTPException(422, detail="filtro_gerencial_invalido")
        anteriores, itens = ServicoRelatorioEmpresas(self.banco)._dados(usuario, "clientes",
            f"{ano:04d}-01-01", f"{ano:04d}-12-31", filtro, busca, None)
        # Um SELECT D36 fornece todos os meses, indicadores e detalhes na mesma
        # fotografia. O mês é o da criação UTC, com acumulados e situações atuais.
        itens.sort(key=lambda c: (c.contratada_em, c.contratacao_id), reverse=True)
        return FiltrosGerencial(ano=ano, filtro=anteriores.filtro, busca=anteriores.busca, mes=mes), itens

    @staticmethod
    def _resumo(itens):
        return ResumoGerencial(indicadores=ServicoPainelAdministrativo._indicadores(itens),
            valor_contratado=moeda(sum(centavos(c.valor_contratado) for c in itens)),
            em_andamento=sum(c.situacao == "em_andamento" for c in itens),
            contratacoes_com_pendencias=sum(bool(c.pendencias) for c in itens),
            pendencias_operacionais=sum(p.area == "operacional" for c in itens for p in c.pendencias),
            pendencias_financeiras=sum(p.area == "financeira" for c in itens for p in c.pendencias),
            pendencias_conferencia=sum(p.area == "conferencia" for c in itens for p in c.pendencias))

    @classmethod
    def _montar(cls, filtros, itens, deslocamento, limite):
        grupos = {mes: [] for mes in range(1, 13)}
        for c in itens:
            grupos[int(c.contratada_em[5:7])].append(c)
        meses = [MesGerencial(**cls._resumo(grupos[mes]).model_dump(), mes=mes,
            data_inicial=f"{filtros.ano:04d}-{mes:02d}-01",
            data_final=f"{filtros.ano:04d}-{mes:02d}-{calendar.monthrange(filtros.ano, mes)[1]:02d}")
            for mes in range(1, 13)]
        detalhe = grupos[filtros.mes] if filtros.mes else []
        return ConsultaGerencial(filtros=filtros, resumo_ano=cls._resumo(itens), meses=meses,
            resumo_mes=meses[filtros.mes - 1] if filtros.mes else None,
            itens=detalhe[deslocamento:deslocamento + limite], total=len(detalhe),
            deslocamento=deslocamento, limite=limite, gerado_em=instante())

    def consultar(self, usuario, ano=None, filtro="todas", busca="", mes=None, deslocamento=0, limite=20):
        exigir_admin(usuario)
        if deslocamento < 0 or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtro_gerencial_invalido")
        filtros, itens = self._dados(usuario, ano, filtro, busca, mes)
        return self._montar(filtros, itens, deslocamento, limite)

    def exportar(self, usuario, ano=None, filtro="todas", busca="", mes=None):
        filtros, itens = self._dados(usuario, ano, filtro, busca, mes)
        consulta = self._montar(filtros, itens, 0, 100)
        colunas = ["Tipo de registro", "Campo", "Informação", "Ano", "Mês", "Data inicial UTC", "Data final UTC",
            "Contratação", "OS", "Contratada em UTC", "Cliente ID", "Cliente", "Fornecedor ID", "Fornecedor",
            "Situação no painel", "Financeiro", "Quantidade de contratações", "Em andamento", "Concluídas", "Canceladas",
            "Para conferência", "Financeiros encerrados", "Controles abertos", "Contratações com pendências",
            "Pendências operacionais", "Pendências financeiras", "Pendências de conferência", "Valor contratado",
            "Recebido confirmado", "Repassado confirmado", "Saldo de clientes com controle aberto",
            "Saldo de fornecedores com controle aberto", "Disponível para repasse", "Códigos de pendências"]
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def escrever(tipo, **valores):
            escritor.writerow([celula_csv({"Tipo de registro": tipo, **valores}.get(c)) for c in colunas])
        for campo, valor in [("Consulta gerada em UTC", consulta.gerado_em), ("Ano", filtros.ano),
                ("Exibir", filtros.filtro), ("Busca", filtros.busca), ("Mês detalhado", filtros.mes),
                ("Critério dos meses", "Criação da contratação em UTC, com os 12 meses do ano."),
                ("Critério das situações", "Situações atuais no painel administrativo, com conferência em categoria própria."),
                ("Critério dos valores", "Acumulados atuais por contratação, excluindo movimentos estornados."),
                ("Critério dos saldos", "Somente controles financeiros abertos, conforme o painel administrativo."),
                ("Critério das pendências", "Contratações contadas uma vez; ações contadas por área, conforme o D37."),
                ("Abrangência", "Total anual e 12 meses abrangem o ano filtrado. Contratações detalham o mês escolhido ou o ano inteiro, incluindo todas as páginas."),
                ("Somar registros", "Total anual e Mês já são agregados. Some apenas as linhas Contratação para reconciliar o detalhamento.")]:
            escrever("Filtro", **{"Campo": campo, "Informação": valor})
        def dinheiro(v):
            return format(v, ".2f").replace(".", ",")
        def totais(r):
            i = r.indicadores
            return {"Quantidade de contratações": i.total_contratacoes, "Em andamento": r.em_andamento,
                "Concluídas": i.contratacoes_concluidas, "Canceladas": i.contratacoes_canceladas,
                "Para conferência": i.para_conferencia, "Financeiros encerrados": i.financeiros_encerrados,
                "Controles abertos": i.controles_abertos, "Contratações com pendências": r.contratacoes_com_pendencias,
                "Pendências operacionais": r.pendencias_operacionais, "Pendências financeiras": r.pendencias_financeiras,
                "Pendências de conferência": r.pendencias_conferencia, "Valor contratado": dinheiro(r.valor_contratado),
                "Recebido confirmado": dinheiro(i.recebimentos_confirmados), "Repassado confirmado": dinheiro(i.repasses_confirmados),
                "Saldo de clientes com controle aberto": dinheiro(i.saldo_clientes_controles_abertos),
                "Saldo de fornecedores com controle aberto": dinheiro(i.saldo_fornecedores_controles_abertos),
                "Disponível para repasse": dinheiro(i.disponivel_repasses)}
        escrever("Total anual", **{"Ano": filtros.ano, **totais(consulta.resumo_ano)})
        for m in consulta.meses:
            escrever("Mês", **{"Ano": filtros.ano, "Mês": m.mes, "Data inicial UTC": m.data_inicial,
                "Data final UTC": m.data_final, **totais(m)})
        for c in itens:
            numero = int(c.contratada_em[5:7])
            if filtros.mes and filtros.mes != numero:
                continue
            financeiro = totais(self._resumo([c]))
            if c.financeiro_status != "aberto":
                for campo in ("Saldo de clientes com controle aberto", "Saldo de fornecedores com controle aberto", "Disponível para repasse"):
                    financeiro[campo] = ""
            escrever("Contratação", **{"Ano": filtros.ano, "Mês": numero, "Contratação": c.contratacao_id,
                "OS": c.ordem_servico_id, "Contratada em UTC": c.contratada_em, "Cliente ID": c.empresa_cliente_id,
                "Cliente": c.cliente, "Fornecedor ID": c.empresa_fornecedora_id, "Fornecedor": c.fornecedor,
                "Situação no painel": c.situacao, "Financeiro": c.financeiro_status,
                "Códigos de pendências": ", ".join(p.codigo for p in c.pendencias), **financeiro})
        return saida.getvalue().encode("utf-8-sig")
