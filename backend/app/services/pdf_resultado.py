"""PDF em dimensões físicas, sem depender da escala de impressão do navegador."""
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import HTTPException
from backend.app.services.relatorio_resultado import CAMPOS, CATEGORIAS

def reais(valor):
    return 'R$ ' + format(Decimal(valor), ',.2f').replace(',', '|').replace('.', ',').replace('|', '.')

def data(valor):
    return datetime.fromisoformat(valor.replace('Z', '+00:00')).strftime('%d/%m/%Y, %H:%M:%S') + ' UTC'

def gerar_pdf_resultado(r):
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, LongTable
    except ImportError:
        raise HTTPException(503, detail='dependencia_pdf_d48_ausente') from None
    fontes = Path(reportlab.__file__).resolve().parent / 'fonts'
    normal, negrito = 'Helvetica', 'Helvetica-Bold'
    if (fontes / 'Vera.ttf').is_file() and (fontes / 'VeraBd.ttf').is_file():
        normal, negrito = 'MecResultado62', 'MecResultado62-Bold'
        if normal not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(normal, str(fontes / 'Vera.ttf')))
            pdfmetrics.registerFont(TTFont(negrito, str(fontes / 'VeraBd.ttf')))
            pdfmetrics.registerFontFamily(normal, normal=normal, bold=negrito)
    azul, cinza, linha = colors.HexColor('#17324f'), colors.HexColor('#526577'), colors.HexColor('#ced8e2')
    estilos = {
        'texto': ParagraphStyle('texto62', fontName=normal, fontSize=9, leading=13, textColor=azul, spaceAfter=5, splitLongWords=True),
        'titulo': ParagraphStyle('titulo62', fontName=negrito, fontSize=18, leading=22, textColor=azul, spaceAfter=7),
        'secao': ParagraphStyle('secao62', fontName=negrito, fontSize=11, leading=15, textColor=azul, spaceBefore=13, spaceAfter=6, keepWithNext=True),
        'celula': ParagraphStyle('celula62', fontName=normal, fontSize=8.5, leading=12, textColor=azul, alignment=TA_LEFT, splitLongWords=True),
        'cabecalho': ParagraphStyle('cabecalho62', fontName=negrito, fontSize=8.5, leading=12, textColor=azul, splitLongWords=True),
        'nota': ParagraphStyle('nota62', fontName=normal, fontSize=8, leading=11, textColor=cinza, spaceAfter=6),
    }
    def p(valor, estilo='celula'):
        return Paragraph(escape(str(valor)).replace('\n', '<br/>'), estilos[estilo])
    largura_pagina, altura_pagina = landscape(A4)
    margem = 14 * mm
    largura = largura_pagina - 2 * margem - 12
    saida = BytesIO()
    doc = SimpleDocTemplate(saida, pagesize=(largura_pagina, altura_pagina), leftMargin=margem, rightMargin=margem,
        topMargin=13 * mm, bottomMargin=15 * mm, title='MEC-Serviços - Resultado da administração',
        author='MEC-Serviços', pageCompression=1)
    partes = [p('MEC-Serviços | Administração | Uso exclusivo do ADM', 'nota'),
        p('Relatório do resultado da administração', 'titulo'),
        p(f"{r['inicio'][8:10]}/{r['inicio'][5:7]}/{r['inicio'][:4]} a {r['fim'][8:10]}/{r['fim'][5:7]}/{r['fim'][:4]} | {r['total']} contratações | {r['liquidadas']} liquidadas", 'texto'),
        p('Consulta: ' + data(r['gerado_em']), 'nota'), Spacer(1, 4)]
    indicadores = []
    for k, titulo in CAMPOS:
        indicador = Paragraph(escape(titulo.removesuffix(' (R$)')) + '<br/><font size="12"><b>' + escape(reais(r['totais'][k])) + '</b></font>', estilos['texto'])
        indicadores.append(indicador)
    resumo = Table([indicadores[i:i+3] for i in range(0, 9, 3)], colWidths=[largura / 3] * 3, hAlign='LEFT')
    resumo.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f4f8')),
        ('BOX', (0, 0), (-1, -1), .5, linha), ('INNERGRID', (0, 0), (-1, -1), .5, linha),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    partes.append(resumo)
    partes.extend([p('Critérios da consulta', 'secao'), p(
        'O período considera a criação da contratação em UTC. As despesas desses serviços entram em todas as datas de pagamento, inclusive quando registradas depois do período. A consulta acompanha o resultado dos serviços; o período não filtra o fluxo de caixa.', 'texto'), p(
        'Entram contratações ativas ou encerradas com preço formado pela administração. Despesas previstas são orçamento interno; despesas pagas somam gastos confirmados e excluem estornos. A liquidação exige entrega concluída, recebimento integral e repasse integral do custo, sem divergência. Novos gastos e estornos podem alterar o resultado.', 'texto')])
    def tabela(titulos, registros, pesos):
        dados = [[p(t, 'cabecalho') for t in titulos]] + [[p(v) for v in reg] for reg in registros]
        t = LongTable(dados, colWidths=[largura * v / sum(pesos) for v in pesos], repeatRows=1,
            hAlign='LEFT', splitByRow=1, splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9eff5')),
            ('LINEBELOW', (0, 0), (-1, 0), .6, linha), ('LINEBELOW', (0, 1), (-1, -1), .35, linha),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
        return t
    def contrato(c):
        return f"#{c['contratacao_id']}\n" + (f"OS #{c['ordem_servico_id']}" if c['ordem_servico_id'] else 'Sem OS')
    partes.append(p('Formação do resultado por contratação', 'secao'))
    if r['itens']:
        campos = ('venda_cliente', 'custo_fornecedor', 'ganho_bruto_previsto', 'despesas_previstas', 'resultado_previsto')
        partes.append(tabela(['Contratação / OS', 'Cliente / fornecedor', 'Venda ao cliente', 'Custo do fornecedor', 'Ganho bruto previsto', 'Despesas previstas', 'Resultado previsto'],
            [[contrato(c), c['cliente'] + '\n' + c['fornecedor'], *(reais(c[k]) for k in campos)] for c in r['itens']], [10, 20, 14, 14, 14, 14, 14]))
        partes.append(p('Despesas e liquidação por contratação', 'secao'))
        campos = ('despesas_pagas', 'resultado_apos_despesas', 'ganho_bruto_confirmado', 'resultado_liquidado_apos_despesas')
        partes.append(tabela(['Contratação / OS', 'Despesas pagas', 'Resultado após despesas pagas', 'Ganho bruto confirmado', 'Resultado liquidado após despesas', 'Liquidação'],
            [[contrato(c), *(reais(c[k]) for k in campos), 'Liquidada' if c['liquidado'] else 'Conferir valores e entrega' if c['situacao'] == 'verificar' else 'Aguardando liquidação'] for c in r['itens']], [10, 17, 21, 17, 21, 18]))
        partes.append(p('Criação das contratações (UTC): ' + '; '.join(f"#{c['contratacao_id']}: {data(c['criada_em'])}" for c in r['itens']), 'nota'))
    else:
        partes.append(p('Nenhuma contratação com preço formado neste período.', 'texto'))
    partes.extend([p('Despesas registradas nos serviços do período', 'secao'), p(
        f"{r['despesas_confirmadas']} confirmadas | {r['despesas_estornadas']} estornadas. Valor dos estornos: {reais(r['valor_estornado'])}. Os estornos ficam no histórico e não compõem as despesas pagas.", 'texto')])
    if r['despesas']:
        registros = []
        for d in r['despesas']:
            notas = f"Comprovante: {d['referencia']}\nRegistro: {d['registro_interno']}\nRegistrada por {d['administrador_nome']} em {data(d['criada_em'])}"
            if d['status'] == 'estornada':
                notas += '\nMotivo do estorno: ' + (d['motivo_estorno'] or 'Consultar histórico da despesa')
                notas += '\nReferência do estorno: ' + (d['referencia_estorno'] or 'Consultar histórico')
                if d['estornada_em']: notas += '\nEstornada em: ' + data(d['estornada_em'])
            registros.append([f"Contratação #{d['contratacao_id']}\nDespesa #{d['id']}", d['paga_em'][8:10] + '/' + d['paga_em'][5:7] + '/' + d['paga_em'][:4] + '\n' + CATEGORIAS[d['categoria']],
                d['descricao'], reais(d['valor']), 'Confirmada' if d['status'] == 'confirmada' else 'Estornada', notas])
        partes.append(tabela(['Contratação / despesa', 'Pagamento / categoria', 'Descrição', 'Valor', 'Estado', 'Referência e registro interno'], registros, [12, 13, 20, 13, 11, 31]))
    else:
        partes.append(p('Nenhuma despesa registrada nessas contratações.', 'texto'))
    partes.extend([Spacer(1, 10), p('Resultado reservado à administração. Não substitui a apuração contábil nem inclui gastos ainda não registrados.', 'nota')])
    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setStrokeColor(linha); canvas.line(margem, 11 * mm, largura_pagina - margem, 11 * mm)
        canvas.setFillColor(cinza); canvas.setFont(normal, 8)
        canvas.drawString(margem, 7 * mm, 'MEC-Serviços | Administração | Uso exclusivo do ADM')
        canvas.drawRightString(largura_pagina - margem, 7 * mm, 'Página ' + str(documento.page))
        canvas.restoreState()
    doc.build(partes, onFirstPage=rodape, onLaterPages=rodape)
    return saida.getvalue()
