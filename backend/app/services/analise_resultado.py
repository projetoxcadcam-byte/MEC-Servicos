"""Grupos por mês e empresa, com centavos inteiros e uma única leitura SQL."""
import csv
import hmac
import io
from datetime import datetime, timezone
from fastapi import HTTPException
from backend.app.services.formacao_preco import moeda, sha
from backend.app.services.relatorio_administrativo import celula_csv
from backend.app.services.relatorio_resultado import CAMPOS
from backend.app.services.resultado_administracao import ServicoResultadoAdministracao

def centavos_exatos(valor):
    # Valores canônicos produzidos pelo cálculo D60/D61; nenhuma conversão float.
    sinal = -1 if valor.startswith('-') else 1
    inteiro, decimal = valor.lstrip('-').split('.')
    return sinal * (int(inteiro) * 100 + int(decimal))

def vazio():
    return {k: 0 for k, _ in CAMPOS}

def grupo(chave, nome, empresa_id=None):
    return dict(chave=chave, nome=nome, empresa_id=empresa_id, total=0, liquidadas=0, totais=vazio())

def acumular(g, c):
    g['total'] += 1
    g['liquidadas'] += int(c['liquidado'])
    for k, _ in CAMPOS:
        g['totais'][k] += centavos_exatos(c[k])

def finalizar(g):
    return {**g, 'totais': {k: moeda(v) for k, v in g['totais'].items()}}

class ServicoAnaliseResultado:
    def __init__(self, despesas):
        self.despesas = despesas

    def obter(self, inicio, fim, empresa_cliente_id=None, empresa_fornecedora_id=None, liquidacao='todas'):
        if liquidacao not in ('todas', 'liquidadas', 'aguardando'):
            raise HTTPException(422, detail='filtro_liquidacao_resultado_invalido')
        r = ServicoResultadoAdministracao(self.despesas.banco, self.despesas.usuario).consultar(
            inicio, fim, 0, None, incluir_despesas=True, identificar_empresas=True)
        # As opções pertencem ao período completo; selecionar uma empresa não
        # esconde a outra opção nem junta empresas que compartilham o mesmo nome.
        def opcoes(campo, nome):
            nomes = {c[campo]: c[nome] for c in r['itens']}
            return [dict(id=i, nome=n) for i, n in sorted(nomes.items(), key=lambda x: (x[1].casefold(), x[0]))]
        clientes, fornecedores = opcoes('empresa_cliente_id', 'cliente'), opcoes('empresa_fornecedora_id', 'fornecedor')
        for selecionado, lista in ((empresa_cliente_id, clientes), (empresa_fornecedora_id, fornecedores)):
            if selecionado is not None and selecionado not in {e['id'] for e in lista}:
                raise HTTPException(422, detail='empresa_fora_do_periodo_resultado')
        itens = [c for c in r['itens'] if
            (empresa_cliente_id is None or c['empresa_cliente_id'] == empresa_cliente_id) and
            (empresa_fornecedora_id is None or c['empresa_fornecedora_id'] == empresa_fornecedora_id) and
            (liquidacao == 'todas' or c['liquidado'] == (liquidacao == 'liquidadas'))]
        meses = {}
        ano, mes = inicio.year, inicio.month
        while (ano, mes) <= (fim.year, fim.month):
            chave = f'{ano:04d}-{mes:02d}'
            meses[chave] = grupo(chave, f'{mes:02d}/{ano:04d}')
            ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
        gc, gf, resumo = {}, {}, grupo('resumo', 'Resumo da seleção')
        for c in itens:
            acumular(resumo, c)
            acumular(meses[c['criada_em'][:7]], c)
            for grupos, campo, nome in ((gc, 'empresa_cliente_id', 'cliente'), (gf, 'empresa_fornecedora_id', 'fornecedor')):
                eid = c[campo]
                if eid not in grupos:
                    grupos[eid] = grupo(str(eid), c[nome], eid)
                acumular(grupos[eid], c)
        def empresas(grupos):
            return [finalizar(g) for g in sorted(grupos.values(), key=lambda g: (g['nome'].casefold(), g['empresa_id']))]
        analise = dict(contexto=r['contexto'], inicio=r['inicio'], fim=r['fim'], base_periodo=r['base_periodo'],
            filtros=dict(empresa_cliente_id=empresa_cliente_id, empresa_fornecedora_id=empresa_fornecedora_id, liquidacao=liquidacao),
            opcoes_clientes=clientes, opcoes_fornecedores=fornecedores, total_periodo=r['total'],
            total=resumo['total'], liquidadas=resumo['liquidadas'], totais=finalizar(resumo)['totais'],
            meses=[finalizar(g) for g in meses.values()], clientes=empresas(gc), fornecedores=empresas(gf), itens=itens)
        # Uma mudança no conjunto, filtros ou valores invalida a exportação.
        analise['versao'] = hmac.new(self.despesas.segredo, sha(analise).encode(), 'sha256').hexdigest()
        analise['gerado_em'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return analise

    def exportar(self, inicio, fim, versao, **filtros):
        r = self.obter(inicio, fim, **filtros)
        if not hmac.compare_digest(versao, r['versao']):
            raise HTTPException(409, detail='analise_resultado_alterada_atualize')
        titulos = [t for _, t in CAMPOS]
        colunas = ['Tipo de registro', 'Período inicial', 'Período final', 'Consulta em UTC',
            'Filtro cliente ID', 'Filtro fornecedor ID', 'Filtro liquidação', 'Mês da contratação',
            'Empresa ID', 'Empresa', 'Contratações', 'Liquidadas', 'Contratação', 'OS',
            'Cliente ID', 'Cliente', 'Fornecedor ID', 'Fornecedor', 'Criada em UTC', 'Liquidação', *titulos]
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=';', lineterminator='\r\n')
        escritor.writerow(colunas)
        def escrever(tipo, valores, dados):
            linha = {'Tipo de registro': tipo, 'Período inicial': r['inicio'], 'Período final': r['fim'],
                'Consulta em UTC': r['gerado_em'], 'Filtro cliente ID': r['filtros']['empresa_cliente_id'],
                'Filtro fornecedor ID': r['filtros']['empresa_fornecedora_id'], 'Filtro liquidação': r['filtros']['liquidacao'],
                **dados, **{t: valores[k] for k, t in CAMPOS}}
            escritor.writerow([linha.get(c, '').replace('.', ',') if c in titulos else celula_csv(linha.get(c)) for c in colunas])
        escrever('Resumo da seleção', r['totais'], {'Contratações': r['total'], 'Liquidadas': r['liquidadas']})
        for tipo, grupos in (('Mês', r['meses']), ('Cliente', r['clientes']), ('Fornecedor', r['fornecedores'])):
            for g in grupos:
                escrever(tipo, g['totais'], {'Mês da contratação': g['chave'] if tipo == 'Mês' else '',
                    'Empresa ID': g['empresa_id'], 'Empresa': g['nome'] if tipo != 'Mês' else '',
                    'Contratações': g['total'], 'Liquidadas': g['liquidadas']})
        for c in r['itens']:
            escrever('Contratação', c, {'Contratação': c['contratacao_id'], 'OS': c['ordem_servico_id'],
                'Cliente ID': c['empresa_cliente_id'], 'Cliente': c['cliente'],
                'Fornecedor ID': c['empresa_fornecedora_id'], 'Fornecedor': c['fornecedor'],
                'Criada em UTC': c['criada_em'], 'Mês da contratação': c['criada_em'][:7],
                'Liquidação': 'Liquidada' if c['liquidado'] else 'Aguardando liquidação'})
        return '\ufeff' + saida.getvalue(), r['versao']
