"""Relatório e CSV da mesma leitura de contratos, liquidação e despesas."""
import csv
import hmac
import io
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import and_, select
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.despesa_administracao import DespesaAdministracao, EventoDespesaAdministracao
from backend.app.models.formacao_preco import FormacaoPreco
from backend.app.services.formacao_preco import moeda, sha
from backend.app.services.relatorio_administrativo import celula_csv
from backend.app.services.resultado_administracao import ServicoResultadoAdministracao

CAMPOS = (
    ('venda_cliente', 'Venda ao cliente (R$)'), ('custo_fornecedor', 'Custo do fornecedor (R$)'),
    ('ganho_bruto_previsto', 'Ganho bruto previsto (R$)'), ('despesas_previstas', 'Despesas previstas (R$)'),
    ('resultado_previsto', 'Resultado previsto (R$)'), ('ganho_bruto_confirmado', 'Ganho bruto confirmado (R$)'),
    ('despesas_pagas', 'Despesas pagas (R$)'), ('resultado_apos_despesas', 'Resultado após despesas pagas (R$)'),
    ('resultado_liquidado_apos_despesas', 'Resultado liquidado após despesas (R$)'),
)
CATEGORIAS = {'coleta': 'Coleta', 'transporte': 'Transporte', 'frete': 'Frete', 'embalagem': 'Embalagem', 'inspecao': 'Inspeção', 'outros': 'Outros'}

class ServicoRelatorioResultado:
    def __init__(self, despesas):
        # A construção de ServicoDespesasAdministracao já valida sessão, perfil
        # administrativo e ativações D60/D61. O relatório usa a mesma sessão SQL.
        self.despesas = despesas
        self.banco = despesas.banco

    def obter(self, inicio, fim):
        resultado = ServicoResultadoAdministracao(self.banco, self.despesas.usuario).consultar(
            inicio, fim, 0, None, incluir_despesas=True)
        inicio_utc = datetime.combine(inicio, datetime.min.time())
        fim_utc = datetime.combine(fim + timedelta(days=1), datetime.min.time())
        # Consulta em lote e na transação de leitura aberta pelo resultado.
        # A elegibilidade replica o vínculo cotação/contratação do painel.
        consulta = select(DespesaAdministracao, EventoDespesaAdministracao).join(
            ContratacaoServico, ContratacaoServico.id == DespesaAdministracao.contratacao_id).join(
            FormacaoPreco, and_(FormacaoPreco.contratacao_id == ContratacaoServico.id,
                FormacaoPreco.cotacao_id == ContratacaoServico.cotacao_id, FormacaoPreco.estado == 'contratada')).outerjoin(
            EventoDespesaAdministracao, and_(EventoDespesaAdministracao.despesa_id == DespesaAdministracao.id,
                EventoDespesaAdministracao.acao == 'estornar')).where(
            ContratacaoServico.status.in_(('ativa', 'encerrada')),
            ContratacaoServico.criada_em >= inicio_utc, ContratacaoServico.criada_em < fim_utc).order_by(
            DespesaAdministracao.contratacao_id.desc(), DespesaAdministracao.paga_em.desc(), DespesaAdministracao.id.desc())
        despesas = []
        confirmadas = estornadas = valor_estornado = 0
        for d, estorno in self.banco.execute(consulta):
            if d.status == 'confirmada':
                confirmadas += 1
            else:
                estornadas += 1
                valor_estornado += d.valor_centavos
            despesas.append(dict(id=d.id, contratacao_id=d.contratacao_id, categoria=d.categoria, descricao=d.descricao,
                valor=moeda(d.valor_centavos), paga_em=d.paga_em, status=d.status, referencia=d.referencia,
                registro_interno=d.registro_interno, administrador_nome=d.administrador_nome, criada_em=d.criada_em,
                estornada_em=d.estornada_em, motivo_estorno=estorno.registro_interno if estorno else None,
                referencia_estorno=estorno.referencia if estorno else None))
        relatorio = {k: resultado[k] for k in ('contexto', 'inicio', 'fim', 'base_periodo', 'total', 'totais', 'itens')}
        relatorio.update(liquidadas=sum(i['liquidado'] for i in resultado['itens']), despesas=despesas,
            despesas_confirmadas=confirmadas, despesas_estornadas=estornadas, valor_estornado=moeda(valor_estornado))
        relatorio['versao'] = hmac.new(self.despesas.segredo, sha(relatorio).encode(), 'sha256').hexdigest()
        relatorio['gerado_em'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        return relatorio

    def exportar(self, inicio, fim, versao):
        r = self.obter(inicio, fim)
        if not hmac.compare_digest(versao, r['versao']):
            raise HTTPException(409, detail='relatorio_resultado_alterado_atualize')
        colunas = ['Tipo de registro', 'Período inicial', 'Período final', 'Base do período', 'Consulta em UTC',
            'Contratação', 'OS', 'Cliente', 'Fornecedor', 'Criada em UTC', 'Liquidação', 'Situação',
            *(titulo for _, titulo in CAMPOS), 'Despesa', 'Categoria', 'Descrição', 'Valor da despesa (R$)',
            'Data do pagamento', 'Estado da despesa', 'Referência', 'Registro interno', 'Registrada por',
            'Registrada em UTC', 'Estornada em UTC', 'Motivo do estorno', 'Referência do estorno']
        monetarias = {titulo for _, titulo in CAMPOS} | {'Valor da despesa (R$)'}
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=';', lineterminator='\r\n')
        escritor.writerow(colunas)
        def escrever(tipo, dados):
            linha = {'Tipo de registro': tipo, 'Período inicial': r['inicio'], 'Período final': r['fim'],
                'Base do período': 'Criação da contratação em UTC; despesas de todas as datas vinculadas ao serviço',
                'Consulta em UTC': r['gerado_em'], **dados}
            # Valores monetários são strings exatas produzidas pelo servidor;
            # negativos numéricos continuam números no Excel. Campos livres
            # usam a neutralização de fórmulas já adotada pelos relatórios.
            escritor.writerow([linha.get(c, '').replace('.', ',') if c in monetarias else celula_csv(linha.get(c)) for c in colunas])
        escrever('Resumo do período', {titulo: r['totais'][k] for k, titulo in CAMPOS})
        contratos = {c['contratacao_id']: c for c in r['itens']}
        for c in r['itens']:
            escrever('Contratação', {'Contratação': c['contratacao_id'], 'OS': c['ordem_servico_id'],
                'Cliente': c['cliente'], 'Fornecedor': c['fornecedor'], 'Criada em UTC': c['criada_em'],
                'Liquidação': 'Liquidada' if c['liquidado'] else 'Aguardando liquidação',
                'Situação': 'Conferir valores e entrega' if c['situacao'] == 'verificar' else 'Encerrada' if c['situacao'] == 'concluida' else 'Em andamento',
                **{titulo: c[k] for k, titulo in CAMPOS}})
        for d in r['despesas']:
            c = contratos[d['contratacao_id']]
            escrever('Despesa', {'Contratação': d['contratacao_id'], 'OS': c['ordem_servico_id'],
                'Cliente': c['cliente'], 'Fornecedor': c['fornecedor'], 'Despesa': d['id'],
                'Categoria': CATEGORIAS[d['categoria']], 'Descrição': d['descricao'], 'Valor da despesa (R$)': d['valor'],
                'Data do pagamento': d['paga_em'], 'Estado da despesa': 'Confirmada' if d['status'] == 'confirmada' else 'Estornada',
                'Referência': d['referencia'], 'Registro interno': d['registro_interno'], 'Registrada por': d['administrador_nome'],
                'Registrada em UTC': d['criada_em'], 'Estornada em UTC': d['estornada_em'],
                'Motivo do estorno': d['motivo_estorno'], 'Referência do estorno': d['referencia_estorno']})
        return '\ufeff' + saida.getvalue(), r['versao']
