from __future__ import annotations

import calendar
import csv
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
import io
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.app.schemas.comparativo_gerencial import (
    ConsultaComparativo, FiltrosComparativo, MedidaComparativa, ResumoPeriodoComparativo,
)
from backend.app.services.intermediacao import exigir_admin, instante
from backend.app.services.painel_administrativo import FILTROS
from backend.app.services.relatorio_administrativo import celula_csv
from backend.app.services.relatorio_empresas import ServicoRelatorioEmpresas
from backend.app.services.relatorio_periodo import validar_data
from backend.app.services.resumo_gerencial import ServicoResumoGerencial

MEDIDAS = (
    ("total_contratacoes", "Contratações", "quantidade"),
    ("em_andamento", "Em andamento", "quantidade"),
    ("concluidas", "Concluídas", "quantidade"),
    ("canceladas", "Canceladas", "quantidade"),
    ("para_conferencia", "Para conferência", "quantidade"),
    ("financeiros_encerrados", "Financeiros encerrados", "quantidade"),
    ("controles_abertos", "Controles abertos", "quantidade"),
    ("contratacoes_com_pendencias", "Contratações com pendências", "quantidade"),
    ("pendencias_operacionais", "Pendências operacionais", "quantidade"),
    ("pendencias_financeiras", "Pendências financeiras", "quantidade"),
    ("pendencias_conferencia", "Pendências de conferência", "quantidade"),
    ("valor_contratado", "Valor contratado", "valor"),
    ("recebido_confirmado", "Recebido confirmado", "valor"),
    ("repassado_confirmado", "Repassado confirmado", "valor"),
    ("saldo_clientes", "Saldo a receber com controle aberto", "valor"),
    ("saldo_fornecedores", "Saldo a repassar com controle aberto", "valor"),
    ("disponivel_repasses", "Disponível para repasse", "valor"),
)


def periodos_padrao():
    agora = datetime.now(UTC)
    ano, mes = agora.year, agora.month
    ano_a, mes_a = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    def intervalo(a, m):
        return f"{a:04d}-{m:02d}-01", f"{a:04d}-{m:02d}-{calendar.monthrange(a, m)[1]:02d}"
    return (*intervalo(ano_a, mes_a), *intervalo(ano, mes))


def percentual(a: Decimal, b: Decimal):
    if a == 0:
        return Decimal("0.00") if b == 0 else None
    with localcontext() as contexto:
        contexto.prec = max(40, len(a.as_tuple().digits) + len(b.as_tuple().digits) + 10)
        return ((b - a) * 100 / a).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ServicoComparativoGerencial:
    def __init__(self, banco: Session):
        self.banco = banco

    def _dados(self, usuario, a_inicial, a_final, b_inicial, b_final, filtro, busca, periodo):
        exigir_admin(usuario)
        datas = (a_inicial, a_final, b_inicial, b_final)
        if all(v is None for v in datas):
            datas = periodos_padrao()
        if (filtro not in FILTROS or not isinstance(busca, str) or len(busca) > 120
                or periodo not in {None, "a", "b"} or any(not isinstance(v, str) or not v for v in datas)):
            raise HTTPException(422, detail="filtro_comparativo_invalido")
        try:
            a_inicial, a_final, b_inicial, b_final = (validar_data(v) for v in datas)
        except HTTPException:
            raise HTTPException(422, detail="filtro_comparativo_invalido") from None
        if a_inicial > a_final or b_inicial > b_final:
            raise HTTPException(422, detail="filtro_comparativo_invalido")
        anteriores, itens = ServicoRelatorioEmpresas(self.banco)._dados(usuario, "clientes",
            min(a_inicial, b_inicial), max(a_final, b_final), filtro, busca, None)
        # Um SELECT fornece ambos os períodos na mesma fotografia. Filtros,
        # acumulados e pendências seguem os critérios D33/D36/D38 existentes.
        itens.sort(key=lambda c: (c.contratada_em, c.contratacao_id), reverse=True)
        a = [c for c in itens if a_inicial <= c.contratada_em[:10] <= a_final]
        b = [c for c in itens if b_inicial <= c.contratada_em[:10] <= b_final]
        filtros = FiltrosComparativo(a_inicial=a_inicial, a_final=a_final,
            b_inicial=b_inicial, b_final=b_final, filtro=anteriores.filtro, busca=anteriores.busca, periodo=periodo)
        return filtros, a, b

    @staticmethod
    def _valores(resumo):
        i = resumo.indicadores
        valores = {"total_contratacoes": i.total_contratacoes, "em_andamento": resumo.em_andamento,
            "concluidas": i.contratacoes_concluidas, "canceladas": i.contratacoes_canceladas,
            "para_conferencia": i.para_conferencia, "financeiros_encerrados": i.financeiros_encerrados,
            "controles_abertos": i.controles_abertos, "contratacoes_com_pendencias": resumo.contratacoes_com_pendencias,
            "pendencias_operacionais": resumo.pendencias_operacionais, "pendencias_financeiras": resumo.pendencias_financeiras,
            "pendencias_conferencia": resumo.pendencias_conferencia, "valor_contratado": resumo.valor_contratado,
            "recebido_confirmado": i.recebimentos_confirmados, "repassado_confirmado": i.repasses_confirmados,
            "saldo_clientes": i.saldo_clientes_controles_abertos, "saldo_fornecedores": i.saldo_fornecedores_controles_abertos,
            "disponivel_repasses": i.disponivel_repasses}
        return {k: Decimal(v) for k, v in valores.items()}

    @classmethod
    def _montar(cls, filtros, a, b, deslocamento, limite):
        resumo_a = ResumoPeriodoComparativo(**ServicoResumoGerencial._resumo(a).model_dump(),
            data_inicial=filtros.a_inicial, data_final=filtros.a_final)
        resumo_b = ResumoPeriodoComparativo(**ServicoResumoGerencial._resumo(b).model_dump(),
            data_inicial=filtros.b_inicial, data_final=filtros.b_final)
        va, vb = cls._valores(resumo_a), cls._valores(resumo_b)
        medidas = [MedidaComparativa(codigo=c, descricao=d, tipo=t, valor_a=va[c], valor_b=vb[c],
            diferenca=vb[c] - va[c], variacao_percentual=percentual(va[c], vb[c])) for c, d, t in MEDIDAS]
        detalhe = a if filtros.periodo == "a" else b if filtros.periodo == "b" else []
        return ConsultaComparativo(filtros=filtros, resumo_a=resumo_a, resumo_b=resumo_b,
            medidas=medidas, periodos_sobrepostos=filtros.a_inicial <= filtros.b_final and filtros.b_inicial <= filtros.a_final,
            contratacoes_em_ambos=len({c.contratacao_id for c in a} & {c.contratacao_id for c in b}),
            itens=detalhe[deslocamento:deslocamento + limite], total=len(detalhe), deslocamento=deslocamento,
            limite=limite, gerado_em=instante())

    def consultar(self, usuario, a_inicial=None, a_final=None, b_inicial=None, b_final=None,
                  filtro="todas", busca="", periodo=None, deslocamento=0, limite=20):
        exigir_admin(usuario)
        if type(deslocamento) is not int or deslocamento < 0 or type(limite) is not int or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtro_comparativo_invalido")
        filtros, a, b = self._dados(usuario, a_inicial, a_final, b_inicial, b_final, filtro, busca, periodo)
        return self._montar(filtros, a, b, deslocamento, limite)

    def exportar(self, usuario, a_inicial=None, a_final=None, b_inicial=None, b_final=None,
                 filtro="todas", busca="", periodo=None):
        filtros, a, b = self._dados(usuario, a_inicial, a_final, b_inicial, b_final, filtro, busca, periodo)
        consulta = self._montar(filtros, a, b, 0, 100)
        colunas = ["Tipo de registro", "Campo", "Informação", "Período", "Data inicial UTC", "Data final UTC",
            "Indicador", "Unidade", "Valor A", "Valor B", "Diferença B - A", "Variação (%)",
            "Contratação", "OS", "Contratada em UTC", "Cliente ID", "Cliente", "Fornecedor ID", "Fornecedor",
            "Situação no painel", "Financeiro", *[d for _, d, _ in MEDIDAS]]
        numericas = {"Valor A", "Valor B", "Diferença B - A", "Variação (%)", *[d for _, d, _ in MEDIDAS]}
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def numero(v, tipo="valor"):
            return format(v, ".2f" if tipo == "valor" else ".0f").replace(".", ",")
        def escrever(tipo, **valores):
            registro = {"Tipo de registro": tipo, **valores}
            # Somente células numéricas calculadas admitem sinal negativo.
            # Campos livres continuam neutralizados contra fórmulas do CSV.
            escritor.writerow([registro.get(c, "") if c in numericas else celula_csv(registro.get(c)) for c in colunas])
        for campo, valor in [("Consulta gerada em UTC", consulta.gerado_em), ("A inicial UTC", filtros.a_inicial),
                ("A final UTC", filtros.a_final), ("B inicial UTC", filtros.b_inicial), ("B final UTC", filtros.b_final),
                ("Exibir", filtros.filtro), ("Busca", filtros.busca), ("Período detalhado na tela", filtros.periodo),
                ("Critério dos períodos", "Criação da contratação em UTC, com os dois dias incluídos."),
                ("Critério dos valores", "Valores e situações atuais por contratação; acumulados excluem estornos e saldos consideram controles abertos."),
                ("Diferença", "B menos A. O sinal indica aumento ou redução; não classifica o resultado como bom ou ruim."),
                ("Percentual", "(B - A) / A vezes 100; duas casas, arredondamento meio para cima. A e B zerados: 0%. A zero e B diferente: sem base."),
                ("Períodos sobrepostos", "Sim" if consulta.periodos_sobrepostos else "Não"),
                ("Contratações em ambos", consulta.contratacoes_em_ambos),
                ("Abrangência", "Ambos os períodos completos, incluindo todas as páginas do detalhamento."),
                ("Somar registros", "Compare A e B separadamente. Não some Indicador, Total e Contratação. Em sobreposição, o mesmo contrato pertence aos dois grupos.")]:
            escrever("Filtro", **{"Campo": campo, "Informação": valor})
        for m in consulta.medidas:
            escrever("Indicador", **{"Indicador": m.descricao, "Unidade": "R$" if m.tipo == "valor" else "Quantidade",
                "Valor A": numero(m.valor_a, m.tipo), "Valor B": numero(m.valor_b, m.tipo),
                "Diferença B - A": numero(m.diferenca, m.tipo),
                "Variação (%)": "" if m.variacao_percentual is None else numero(m.variacao_percentual)})
        def totais(resumo):
            valores = self._valores(resumo)
            return {d: numero(valores[c], t) for c, d, t in MEDIDAS}
        for codigo, resumo, itens in [("A", consulta.resumo_a, a), ("B", consulta.resumo_b, b)]:
            periodo_csv = {"Período": codigo, "Data inicial UTC": resumo.data_inicial, "Data final UTC": resumo.data_final}
            escrever("Total", **periodo_csv, **totais(resumo))
            for c in itens:
                valores = totais(ServicoResumoGerencial._resumo([c]))
                if c.financeiro_status != "aberto":
                    for campo in ("Saldo a receber com controle aberto", "Saldo a repassar com controle aberto", "Disponível para repasse"):
                        valores[campo] = ""
                escrever("Contratação", **periodo_csv, **valores, **{"Contratação": c.contratacao_id,
                    "OS": c.ordem_servico_id, "Contratada em UTC": c.contratada_em, "Cliente ID": c.empresa_cliente_id,
                    "Cliente": c.cliente, "Fornecedor ID": c.empresa_fornecedora_id, "Fornecedor": c.fornecedor,
                    "Situação no painel": c.situacao, "Financeiro": c.financeiro_status})
        return saida.getvalue().encode("utf-8-sig")
