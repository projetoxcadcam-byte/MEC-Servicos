from __future__ import annotations

import csv
import io
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.app.schemas.relatorio_empresas import ConsultaEmpresas, FiltrosEmpresas, GrupoEmpresa, ItemEmpresa
from backend.app.services.financeiro_administrativo import centavos, moeda
from backend.app.services.intermediacao import exigir_admin, instante
from backend.app.services.painel_administrativo import FILTROS, ServicoPainelAdministrativo
from backend.app.services.relatorio_administrativo import celula_csv, data_utc
from backend.app.services.relatorio_periodo import validar_data


class ServicoRelatorioEmpresas:
    def __init__(self, banco: Session):
        self.banco = banco

    def _dados(self, usuario, agrupamento, data_inicial, data_final, filtro, busca, empresa_id):
        exigir_admin(usuario)
        if (agrupamento not in {"clientes", "fornecedores"} or filtro not in FILTROS or len(busca) > 120
                or (empresa_id is not None and (type(empresa_id) is not int or empresa_id <= 0))):
            raise HTTPException(422, detail="filtro_empresas_invalido")
        inicial, final = validar_data(data_inicial), validar_data(data_final)
        if inicial and final and inicial > final:
            raise HTTPException(422, detail="filtro_empresas_invalido")
        filtros = FiltrosEmpresas(agrupamento=agrupamento, data_inicial=inicial, data_final=final,
            filtro=filtro, busca=busca.strip(), empresa_id=empresa_id)
        painel = ServicoPainelAdministrativo(self.banco)
        # Um SELECT em lote fornece os identificadores reais das empresas e os
        # mesmos acumulados e pendências do D33. Nenhum GET altera os registros.
        with self.banco.no_autoflush:
            linhas = self.banco.execute(painel._consulta()).all()
        itens = []
        for linha in linhas:
            contrato = linha[0]
            identificador = contrato.empresa_cliente_id if agrupamento == "clientes" else contrato.empresa_fornecedora_id
            if empresa_id is not None and identificador != empresa_id:
                continue
            criada = data_utc(contrato.criada_em)
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
            elif filtro != "todas" and item.situacao != {
                    "verificar": "verificar", "concluidas": "concluida", "canceladas": "cancelada"}[filtro]:
                continue
            if filtros.busca and not painel._corresponde(item, filtros.busca):
                continue
            itens.append(ItemEmpresa(**item.model_dump(), contratada_em=criada,
                empresa_cliente_id=contrato.empresa_cliente_id, empresa_fornecedora_id=contrato.empresa_fornecedora_id))
        return filtros, itens

    @staticmethod
    def _grupos(filtros, itens):
        agrupados = {}
        for item in itens:
            identificador, nome = ((item.empresa_cliente_id, item.cliente) if filtros.agrupamento == "clientes"
                else (item.empresa_fornecedora_id, item.fornecedor))
            if identificador not in agrupados:
                agrupados[identificador] = (nome, [])
            agrupados[identificador][1].append(item)
        grupos = [GrupoEmpresa(empresa_id=identificador, empresa=nome,
            valor_contratado=moeda(sum(centavos(i.valor_contratado) for i in contratos)),
            indicadores=ServicoPainelAdministrativo._indicadores(contratos))
            for identificador, (nome, contratos) in agrupados.items()]
        # A comparação usa centavos, com desempate estável por nome e ID.
        return sorted(grupos, key=lambda g: (-centavos(g.valor_contratado), g.empresa.casefold(), g.empresa_id))

    @classmethod
    def _montar(cls, filtros, itens, deslocamento, deslocamento_itens, limite):
        grupos = cls._grupos(filtros, itens)
        return ConsultaEmpresas(filtros=filtros, indicadores=ServicoPainelAdministrativo._indicadores(itens),
            valor_contratado=moeda(sum(centavos(i.valor_contratado) for i in itens)),
            grupos=grupos[deslocamento:deslocamento + limite],
            empresa_selecionada=grupos[0] if filtros.empresa_id is not None and grupos else None,
            itens=itens[deslocamento_itens:deslocamento_itens + limite] if filtros.empresa_id is not None else [],
            total_empresas=len(grupos), total_contratacoes=len(itens), deslocamento=deslocamento,
            deslocamento_itens=deslocamento_itens, limite=limite, gerado_em=instante())

    def consultar(self, usuario, agrupamento="clientes", data_inicial="", data_final="", filtro="todas",
                  busca="", empresa_id=None, deslocamento=0, deslocamento_itens=0, limite=20):
        exigir_admin(usuario)
        if deslocamento < 0 or deslocamento_itens < 0 or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtro_empresas_invalido")
        filtros, itens = self._dados(usuario, agrupamento, data_inicial, data_final, filtro, busca, empresa_id)
        return self._montar(filtros, itens, deslocamento, deslocamento_itens, limite)

    def exportar(self, usuario, agrupamento="clientes", data_inicial="", data_final="", filtro="todas",
                 busca="", empresa_id=None) -> bytes:
        filtros, itens = self._dados(usuario, agrupamento, data_inicial, data_final, filtro, busca, empresa_id)
        grupos = self._grupos(filtros, itens)
        consulta = self._montar(filtros, itens, 0, 0, 100)
        colunas = ["Tipo de registro", "Campo", "Informação", "Agrupamento", "Empresa ID", "Empresa",
            "Contratação", "OS", "Contratada em UTC", "Cliente ID", "Cliente", "Fornecedor ID", "Fornecedor",
            "Situação no painel", "Financeiro", "Quantidade de contratações", "Valor contratado",
            "Recebido confirmado", "Repassado confirmado", "Saldo de clientes com controle aberto",
            "Saldo de fornecedores com controle aberto", "Disponível para repasse",
            "Com pendência operacional", "Com pendência financeira", "Para conferência"]
        saida = io.StringIO(newline="")
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(colunas)
        def dinheiro(valor: Decimal):
            return format(valor, ".2f").replace(".", ",")
        def escrever(tipo, **valores):
            escritor.writerow([celula_csv({"Tipo de registro": tipo, **valores}.get(c)) for c in colunas])
        for campo, valor in [("Consulta gerada em UTC", consulta.gerado_em), ("Agrupar por", filtros.agrupamento),
                ("Data inicial UTC", filtros.data_inicial), ("Data final UTC", filtros.data_final),
                ("Exibir", filtros.filtro), ("Busca", filtros.busca), ("Empresa selecionada ID", filtros.empresa_id),
                ("Empresa selecionada", consulta.empresa_selecionada.empresa if consulta.empresa_selecionada else None),
                ("Critério do período", "Data de criação da contratação em UTC, com os dois dias incluídos."),
                ("Critério dos valores", "Acumulados atuais das contratações selecionadas; movimentos estornados excluídos."),
                ("Critério dos saldos", "Somente controles financeiros abertos, conforme o painel administrativo."),
                ("Critério dos grupos", "Empresas separadas pelo ID e pela participação como cliente ou fornecedor."),
                ("Abrangência", "Todas as empresas e contratações correspondentes aos filtros; não apenas a página visível.")]:
            escrever("Filtro", **{"Campo": campo, "Informação": valor})
        def totais(valor, i):
            return {"Quantidade de contratações": i.total_contratacoes, "Valor contratado": dinheiro(valor),
                "Recebido confirmado": dinheiro(i.recebimentos_confirmados), "Repassado confirmado": dinheiro(i.repasses_confirmados),
                "Saldo de clientes com controle aberto": dinheiro(i.saldo_clientes_controles_abertos),
                "Saldo de fornecedores com controle aberto": dinheiro(i.saldo_fornecedores_controles_abertos),
                "Disponível para repasse": dinheiro(i.disponivel_repasses), "Com pendência operacional": i.acompanhamento_operacional,
                "Com pendência financeira": i.pendencias_financeiras, "Para conferência": i.para_conferencia}
        escrever("Total", **{"Agrupamento": filtros.agrupamento, **totais(consulta.valor_contratado, consulta.indicadores)})
        escrever("Indicador", **{"Campo": "Empresas selecionadas", "Informação": len(grupos)})
        for grupo in grupos:
            escrever("Empresa", **{"Agrupamento": filtros.agrupamento, "Empresa ID": grupo.empresa_id,
                "Empresa": grupo.empresa, **totais(grupo.valor_contratado, grupo.indicadores)})
        for item in itens:
            aberto = item.financeiro_status == "aberto"
            identificador, nome = ((item.empresa_cliente_id, item.cliente) if filtros.agrupamento == "clientes"
                else (item.empresa_fornecedora_id, item.fornecedor))
            escrever("Contratação", **{"Agrupamento": filtros.agrupamento, "Empresa ID": identificador, "Empresa": nome,
                "Contratação": item.contratacao_id, "OS": item.ordem_servico_id, "Contratada em UTC": item.contratada_em,
                "Cliente ID": item.empresa_cliente_id, "Cliente": item.cliente, "Fornecedor ID": item.empresa_fornecedora_id,
                "Fornecedor": item.fornecedor, "Situação no painel": item.situacao, "Financeiro": item.financeiro_status,
                "Quantidade de contratações": 1, "Valor contratado": dinheiro(item.valor_contratado),
                "Recebido confirmado": dinheiro(item.total_recebido), "Repassado confirmado": dinheiro(item.total_repassado),
                "Saldo de clientes com controle aberto": dinheiro(item.saldo_cliente) if aberto else "",
                "Saldo de fornecedores com controle aberto": dinheiro(item.saldo_fornecedor) if aberto else "",
                "Disponível para repasse": dinheiro(item.disponivel_repasse) if aberto else "",
                "Com pendência operacional": int(any(p.area == "operacional" for p in item.pendencias)),
                "Com pendência financeira": int(any(p.area == "financeira" for p in item.pendencias)),
                "Para conferência": int(item.situacao == "verificar")})
        return saida.getvalue().encode("utf-8-sig")
