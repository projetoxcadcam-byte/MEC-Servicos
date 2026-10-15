from __future__ import annotations

import calendar
import csv
from datetime import UTC, datetime
import io
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import Integer, Numeric, String, cast, literal, select, union_all
from sqlalchemy.orm import Session, aliased
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.financeiro_administrativo import ControleFinanceiro, RepasseAdministrativo
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.schemas.extrato_financeiro import ConsultaExtrato, FiltrosExtrato, ItemExtrato, ResumoExtrato
from backend.app.services.financeiro_administrativo import centavos, moeda
from backend.app.services.intermediacao import exigir_admin, instante
from backend.app.services.painel_administrativo import ServicoPainelAdministrativo
from backend.app.services.relatorio_administrativo import celula_csv, data_utc
from backend.app.services.relatorio_periodo import validar_data

TIPOS = {
    "todos": {"recebimento", "repasse", "estorno_recebimento", "estorno_repasse"},
    "recebimentos": {"recebimento", "estorno_recebimento"},
    "repasses": {"repasse", "estorno_repasse"},
    "estornos": {"estorno_recebimento", "estorno_repasse"},
}
ROTULOS = {"recebimento": "Recebimento", "repasse": "Repasse",
           "estorno_recebimento": "Estorno de recebimento", "estorno_repasse": "Estorno de repasse"}


def periodo_padrao():
    agora = datetime.now(UTC)
    return f"{agora.year:04d}-{agora.month:02d}-01", f"{agora.year:04d}-{agora.month:02d}-{calendar.monthrange(agora.year, agora.month)[1]:02d}"


class ServicoExtratoFinanceiro:
    def __init__(self, banco: Session):
        self.banco = banco

    @staticmethod
    def _consulta(contratacao_id):
        # Numeric original e centavos inteiros ficam em colunas separadas:
        # nenhuma multiplicação/divisão financeira em ponto flutuante no SQL.
        pagamentos = select(literal("recebimento").label("origem"), PagamentoContratacao.id.label("movimento_id"),
            PagamentoContratacao.contratacao_id.label("contratacao_id"), PagamentoContratacao.valor.label("valor_recebimento"),
            literal(None, Integer).label("centavos_repasse"), cast(PagamentoContratacao.paga_em, String).label("registrado"),
            cast(PagamentoContratacao.cancelada_em, String).label("estornado"), PagamentoContratacao.status.label("status"),
            PagamentoContratacao.forma_pagamento.label("forma"))
        repasses = select(literal("repasse"), RepasseAdministrativo.id, RepasseAdministrativo.contratacao_id,
            literal(None, Numeric(14, 2)), RepasseAdministrativo.valor_centavos, RepasseAdministrativo.registrado_em,
            RepasseAdministrativo.estornado_em, RepasseAdministrativo.status, RepasseAdministrativo.forma_pagamento)
        movimentos = union_all(pagamentos, repasses).subquery()
        cliente, fornecedor = aliased(Empresa), aliased(Empresa)
        consulta = select(movimentos, OrdemServico.id.label("ordem_servico_id"),
            ContratacaoServico.empresa_cliente_id, ContratacaoServico.empresa_fornecedora_id,
            cliente.razao_social.label("cliente"), fornecedor.razao_social.label("fornecedor"),
            ControleFinanceiro.status.label("financeiro_status")).select_from(movimentos).join(
            ContratacaoServico, ContratacaoServico.id == movimentos.c.contratacao_id).join(
            cliente, cliente.id == ContratacaoServico.empresa_cliente_id).join(
            fornecedor, fornecedor.id == ContratacaoServico.empresa_fornecedora_id).outerjoin(
            OrdemServico, OrdemServico.contratacao_id == ContratacaoServico.id).outerjoin(
            ControleFinanceiro, ControleFinanceiro.contratacao_id == ContratacaoServico.id)
        if contratacao_id is not None:
            consulta = consulta.where(ContratacaoServico.id == contratacao_id)
        return consulta

    def _dados(self, usuario, data_inicial, data_final, tipo, busca, contratacao_id):
        exigir_admin(usuario)
        if (tipo not in TIPOS or not isinstance(busca, str) or len(busca) > 120
                or (contratacao_id is not None and (type(contratacao_id) is not int or contratacao_id <= 0))):
            raise HTTPException(422, detail="filtro_extrato_invalido")
        if data_inicial is None and data_final is None:
            data_inicial, data_final = periodo_padrao()
        if any(v is not None and not isinstance(v, str) for v in (data_inicial, data_final)):
            raise HTTPException(422, detail="filtro_extrato_invalido")
        try:
            inicial, final = validar_data(data_inicial or ""), validar_data(data_final or "")
        except HTTPException:
            raise HTTPException(422, detail="filtro_extrato_invalido") from None
        if inicial and final and inicial > final:
            raise HTTPException(422, detail="filtro_extrato_invalido")
        filtros = FiltrosExtrato(data_inicial=inicial, data_final=final, tipo=tipo, busca=busca.strip(), contratacao_id=contratacao_id)
        # Um SELECT fornece originais, estornos e empresas na mesma fotografia;
        # a quantidade de pagamentos/repasses não multiplica seus valores.
        with self.banco.no_autoflush:
            linhas = self.banco.execute(self._consulta(contratacao_id)).mappings().all()
        itens = []
        for linha in linhas:
            r = dict(linha)
            if filtros.busca and not ServicoPainelAdministrativo._corresponde(SimpleNamespace(**r), filtros.busca):
                continue
            origem = r["origem"]
            if tipo == "recebimentos" and origem != "recebimento" or tipo == "repasses" and origem != "repasse":
                continue
            try:
                original, estorno = data_utc(r["registrado"]), data_utc(r["estornado"])
                valor = centavos(r["valor_recebimento"]) if origem == "recebimento" else r["centavos_repasse"]
                cancelado = r["status"] == ("cancelado" if origem == "recebimento" else "estornado")
                if (not original or type(valor) is not int or valor <= 0
                        or r["status"] not in ({"confirmado", "cancelado"} if origem == "recebimento" else {"confirmado", "estornado"})
                        or (cancelado != bool(estorno)) or (estorno and estorno < original)):
                    raise ValueError
            except (HTTPException, ValueError, TypeError):
                # Não inventa data de estorno nem corrige o registro consultado.
                raise HTTPException(409, detail="movimento_extrato_inconsistente") from None
            eventos = [(origem, original)]
            if cancelado:
                eventos.append(("estorno_" + origem, estorno))
            for movimento, data in eventos:
                if movimento not in TIPOS[tipo] or (inicial and data[:10] < inicial) or (final and data[:10] > final):
                    continue
                positivo = movimento in {"recebimento", "estorno_repasse"}
                itens.append(ItemExtrato(tipo=movimento, movimento_id=r["movimento_id"], contratacao_id=r["contratacao_id"],
                    ordem_servico_id=r["ordem_servico_id"], empresa_cliente_id=r["empresa_cliente_id"],
                    empresa_fornecedora_id=r["empresa_fornecedora_id"], cliente=r["cliente"], fornecedor=r["fornecedor"],
                    financeiro_status=r["financeiro_status"] or "sem_controle", situacao_atual="estornado" if cancelado else "confirmado",
                    data_utc=data, data_original_utc=original, estornado_em_utc=estorno, forma_pagamento=r["forma"],
                    valor=moeda(valor), efeito_liquido=moeda(valor if positivo else -valor)))
        itens.sort(key=lambda c: (c.data_utc, c.contratacao_id, c.movimento_id, c.tipo), reverse=True)
        return filtros, itens

    @staticmethod
    def _montar(filtros, itens, deslocamento, limite):
        totais = {t: 0 for t in ROTULOS}
        for item in itens:
            totais[item.tipo] += centavos(item.valor)
        recebido = totais["recebimento"] - totais["estorno_recebimento"]
        repassado = totais["repasse"] - totais["estorno_repasse"]
        entradas = totais["recebimento"] + totais["estorno_repasse"]
        saidas = totais["repasse"] + totais["estorno_recebimento"]
        resumo = ResumoExtrato(recebimentos_brutos=moeda(totais["recebimento"]),
            estornos_recebimentos=moeda(totais["estorno_recebimento"]), recebimentos_liquidos=moeda(recebido),
            repasses_brutos=moeda(totais["repasse"]), estornos_repasses=moeda(totais["estorno_repasse"]),
            repasses_liquidos=moeda(repassado), entradas=moeda(entradas), saidas=moeda(saidas),
            resultado_periodo=moeda(entradas - saidas), total_movimentos=len(itens),
            total_contratacoes=len({c.contratacao_id for c in itens}))
        return ConsultaExtrato(filtros=filtros, resumo=resumo, itens=itens[deslocamento:deslocamento + limite],
            total=len(itens), deslocamento=deslocamento, limite=limite, gerado_em=instante())

    def consultar(self, usuario, data_inicial=None, data_final=None, tipo="todos", busca="", contratacao_id=None, deslocamento=0, limite=20):
        exigir_admin(usuario)
        if type(deslocamento) is not int or deslocamento < 0 or type(limite) is not int or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtro_extrato_invalido")
        filtros, itens = self._dados(usuario, data_inicial, data_final, tipo, busca, contratacao_id)
        return self._montar(filtros, itens, deslocamento, limite)

    def exportar(self, usuario, data_inicial=None, data_final=None, tipo="todos", busca="", contratacao_id=None):
        filtros, itens = self._dados(usuario, data_inicial, data_final, tipo, busca, contratacao_id)
        consulta = self._montar(filtros, itens, 0, 100)
        colunas = ["Tipo de registro", "Campo", "Informação", "Movimento", "Movimento ID", "Data UTC",
            "Data original UTC", "Estornado em UTC", "Contratação", "OS", "Cliente ID", "Cliente", "Fornecedor ID", "Fornecedor",
            "Financeiro atual", "Situação atual do movimento", "Forma", "Valor", "Efeito líquido", "Recebimentos brutos",
            "Estornos de recebimentos", "Recebimentos líquidos", "Repasses brutos", "Estornos de repasses", "Repasses líquidos",
            "Entradas", "Saídas", "Resultado do período", "Quantidade de movimentos", "Quantidade de contratações"]
        numericas = {"Valor", "Efeito líquido", *colunas[19:]}
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def escrever(tipo_registro, **valores):
            r = {"Tipo de registro": tipo_registro, **valores}
            escritor.writerow([r.get(c, "") if c in numericas else celula_csv(r.get(c)) for c in colunas])
        for campo, valor in [("Gerado em UTC", consulta.gerado_em), ("Data inicial UTC", filtros.data_inicial),
                ("Data final UTC", filtros.data_final), ("Exibir", filtros.tipo), ("Busca", filtros.busca), ("Contratação selecionada", filtros.contratacao_id),
                ("Critério", "Datas reais dos movimentos em UTC, incluindo início e fim. Originais e estornos aparecem nas respectivas datas."),
                ("Sinais", "Recebimento e estorno de repasse: positivo. Repasse e estorno de recebimento: negativo."),
                ("Resultado", "Entradas menos saídas dos registros selecionados; não é saldo bancário nem lucro."),
                ("Abrangência", "Todas as páginas dos filtros aplicados. Não somar os tipos Total e Movimento entre si.")]:
            escrever("Filtro", **{"Campo": campo, "Informação": valor})
        campos = [("recebimentos_brutos", "Recebimentos brutos"), ("estornos_recebimentos", "Estornos de recebimentos"),
            ("recebimentos_liquidos", "Recebimentos líquidos"), ("repasses_brutos", "Repasses brutos"),
            ("estornos_repasses", "Estornos de repasses"), ("repasses_liquidos", "Repasses líquidos"),
            ("entradas", "Entradas"), ("saidas", "Saídas"), ("resultado_periodo", "Resultado do período")]
        def numero(v):
            return format(v, ".2f").replace(".", ",")
        escrever("Total", **{rotulo: numero(getattr(consulta.resumo, campo)) for campo, rotulo in campos},
            **{"Quantidade de movimentos": consulta.total, "Quantidade de contratações": consulta.resumo.total_contratacoes})
        for c in itens:
            escrever("Movimento", **{"Movimento": ROTULOS[c.tipo], "Movimento ID": c.movimento_id, "Data UTC": c.data_utc,
                "Data original UTC": c.data_original_utc, "Estornado em UTC": c.estornado_em_utc, "Contratação": c.contratacao_id,
                "OS": c.ordem_servico_id, "Cliente ID": c.empresa_cliente_id, "Cliente": c.cliente,
                "Fornecedor ID": c.empresa_fornecedora_id, "Fornecedor": c.fornecedor, "Financeiro atual": c.financeiro_status,
                "Situação atual do movimento": c.situacao_atual, "Forma": c.forma_pagamento,
                "Valor": numero(c.valor), "Efeito líquido": numero(c.efeito_liquido)})
        return saida.getvalue().encode("utf-8-sig")
