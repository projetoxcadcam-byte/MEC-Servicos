"""Metas em A4 horizontal, com gráfico vetorial e tabela da mesma consulta."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import HTTPException
from backend.app.services.analise_resultado import centavos_exatos
from backend.app.services.pdf_resultado import reais, data

FASES={'encerrado':'Mês anterior','em_andamento':'Mês em andamento','futuro':'Mês futuro'}
SITUACOES={'sem_meta':'Sem meta','meta_zero':'Meta zero','alcancada':'Meta alcançada','abaixo':'Abaixo da meta'}

def gerar_pdf_metas(r):
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, LongTable, Spacer, PageBreak
        from reportlab.graphics.shapes import Drawing, String, Line, Rect, Circle
    except ImportError:
        raise HTTPException(503,detail='dependencia_pdf_d48_ausente') from None
    normal,negrito='Helvetica','Helvetica-Bold'
    fontes=Path(reportlab.__file__).resolve().parent/'fonts'
    if (fontes/'Vera.ttf').is_file() and (fontes/'VeraBd.ttf').is_file():
        normal,negrito='MecMetas65','MecMetas65-Bold'
        if normal not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(normal,str(fontes/'Vera.ttf')))
            pdfmetrics.registerFont(TTFont(negrito,str(fontes/'VeraBd.ttf')))
            pdfmetrics.registerFontFamily(normal,normal=normal,bold=negrito)
    azul=colors.HexColor('#17324f');cinza=colors.HexColor('#526577');linha=colors.HexColor('#ced8e2')
    cor_meta=colors.HexColor('#849bad');cor_real=colors.HexColor('#2678ba');cor_neg=colors.HexColor('#b7354b')
    estilos={
        'titulo':ParagraphStyle('titulo65',fontName=negrito,fontSize=18,leading=22,textColor=azul,spaceAfter=6),
        'secao':ParagraphStyle('secao65',fontName=negrito,fontSize=11,leading=14,textColor=azul,spaceBefore=9,spaceAfter=5,keepWithNext=True),
        'texto':ParagraphStyle('texto65',fontName=normal,fontSize=9,leading=12,textColor=azul,spaceAfter=4,splitLongWords=True),
        'celula':ParagraphStyle('celula65',fontName=normal,fontSize=8.5,leading=11,textColor=azul,splitLongWords=True),
        'cabecalho':ParagraphStyle('cabecalho65',fontName=negrito,fontSize=8.5,leading=11,textColor=azul,splitLongWords=True),
        'nota':ParagraphStyle('nota65',fontName=normal,fontSize=8,leading=11,textColor=cinza,spaceAfter=4),
    }
    def p(v,estilo='celula'):
        return Paragraph(escape(str(v)).replace('\n','<br/>'),estilos[estilo])
    def dinheiro(v):return 'Sem meta' if v is None else reais(v)
    def porcentagem(v):return '-' if v is None else v.replace('.',',')+'%'
    largura_pagina,altura_pagina=landscape(A4);margem=14*mm;largura=largura_pagina-2*margem-12
    saida=BytesIO();doc=SimpleDocTemplate(saida,pagesize=(largura_pagina,altura_pagina),leftMargin=margem,rightMargin=margem,
        topMargin=13*mm,bottomMargin=15*mm,title=f"MEC-Serviços - Metas do resultado {r['ano']}",author='MEC-Serviços',pageCompression=1)
    partes=[p('MEC-Serviços | Administração | Uso exclusivo do ADM','nota'),p('Metas mensais do resultado','titulo'),
        p(f"Ano {r['ano']} | {r['total']} contratações | {r['liquidadas']} liquidadas | {r['meses_com_meta']} meses com meta",'texto'),
        p('Consulta: '+data(r['consulta_em']),'nota'),Spacer(1,3)]
    indicadores=[('Meta total dos meses com meta',dinheiro(r['meta_total'])),
        ('Resultado liquidado nos meses com meta',reais(r['realizado_com_meta'])),
        ('Atingimento nos meses com meta',porcentagem(r['atingimento_total_percentual'])),
        ('Diferença: liquidado menos meta','-' if r['diferenca_total'] is None else reais(r['diferenca_total'])),
        ('Resultado liquidado de todos os serviços',reais(r['totais']['resultado_liquidado_apos_despesas'])),
        ('Resultado após despesas pagas de todos os serviços',reais(r['totais']['resultado_apos_despesas']))]
    celulas=[Paragraph(escape(t)+'<br/><font size="12"><b>'+escape(v)+'</b></font>',estilos['texto']) for t,v in indicadores]
    resumo=Table([celulas[:3],celulas[3:]],colWidths=[largura/3]*3,hAlign='LEFT')
    resumo.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f0f4f8')),('BOX',(0,0),(-1,-1),.5,linha),
        ('INNERGRID',(0,0),(-1,-1),.5,linha),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),
        ('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    partes.extend([resumo,p('Meta e resultado dos serviços liquidados','secao'),
        p('Cinza: meta definida | Azul: resultado liquidado | Vermelho: resultado negativo.','nota')])
    # Coordenadas de desenho apenas; valores continuam em centavos inteiros.
    valores=[centavos_exatos(v) for m in r['meses'] for v in (m['meta'],m['totais']['resultado_liquidado_apos_despesas']) if v is not None]
    minimo=min([0,*valores]);maximo=max([0,*valores]);amplitude=maximo-minimo or 1
    largura_meta=max(pdfmetrics.stringWidth('Meta: '+dinheiro(m['meta']),normal,8) for m in r['meses'])
    largura_real=max(pdfmetrics.stringWidth('Liquidado: '+reais(m['totais']['resultado_liquidado_apos_despesas']),normal,8) for m in r['meses'])
    esquerda=69;direita=largura-largura_meta-largura_real-30
    def x(v):return esquerda+(v-minimo)*(direita-esquerda)/amplitude
    zero=x(0);alto=251;desenho=Drawing(largura,alto)
    # Formatar o eixo a partir de centavos sem conversão monetária float.
    def monetario(c):
        abs_c=abs(c);return ('-' if c<0 else '')+str(abs_c//100)+'.'+str(abs_c%100).zfill(2)
    desenho.add(String(esquerda,alto-12,reais(monetario(minimo)),fontName=normal,fontSize=8,fillColor=cinza))
    desenho.add(String(direita,alto-12,reais(monetario(maximo)),fontName=normal,fontSize=8,fillColor=cinza,textAnchor='end'))
    for i,m in enumerate(r['meses']):
        y=alto-36-i*18
        desenho.add(String(0,y+3,m['nome'],fontName=normal,fontSize=8.5,fillColor=azul))
        desenho.add(Line(esquerda,y-6,largura,y-6,strokeColor=linha,strokeWidth=.3))
        desenho.add(Line(zero,y-4,zero,y+10,strokeColor=cinza,strokeWidth=.5))
        meta=None if m['meta'] is None else centavos_exatos(m['meta']);real=centavos_exatos(m['totais']['resultado_liquidado_apos_despesas'])
        for valor,yy,cor in ((meta,y+4,cor_meta),(real,y-3,cor_neg if real<0 else cor_real)):
            if valor is None:continue
            if valor==0:desenho.add(Circle(zero,yy+2,1.5,fillColor=cor,strokeColor=None))
            else:desenho.add(Rect(min(zero,x(valor)),yy,max(abs(x(valor)-zero),.4),4,fillColor=cor,strokeColor=None))
        desenho.add(String(largura-largura_real-10,y+4,'Meta: '+dinheiro(m['meta']),fontName=normal,fontSize=8,fillColor=cinza,textAnchor='end'))
        desenho.add(String(largura,y+4,'Liquidado: '+reais(m['totais']['resultado_liquidado_apos_despesas']),fontName=normal,fontSize=8,fillColor=cor_neg if real<0 else azul,textAnchor='end'))
    partes.extend([desenho,p('Referência: mês de criação da contratação em UTC. O resultado é atualizado na consulta; despesas de qualquer data e estornos seguem vinculados ao serviço de origem.','nota'),
        p('Atingimento e diferença anuais consideram apenas meses com meta ativa. Sem meta e meta zero não calculam percentual.','nota'),PageBreak(),
        p(f"Comparação mensal | {r['ano']}",'titulo'),p('Consulta: '+data(r['consulta_em']),'nota'),
        p('Liquidação: entrega, recebimento e repasse integrais, sem divergência. Despesas confirmadas excluem estornos. Metas são planejamento interno; previsto e após despesas pagas ficam separados do liquidado. A consulta não representa fluxo de caixa nem fechamento contábil.','nota')])
    titulos=['Mês / fase','Serviços / liquidados','Meta','Resultado liquidado','Diferença','Atingimento / situação','Resultado previsto','Despesas pagas','Resultado após despesas pagas']
    linhas=[]
    for m in r['meses']:
        linhas.append([m['nome']+'\n'+FASES[m['fase']],str(m['total'])+' / '+str(m['liquidadas']),dinheiro(m['meta']),
            reais(m['totais']['resultado_liquidado_apos_despesas']),'-' if m['diferenca'] is None else reais(m['diferenca']),
            porcentagem(m['atingimento_percentual'])+'\n'+SITUACOES[m['situacao']],reais(m['totais']['resultado_previsto']),
            reais(m['totais']['despesas_pagas']),reais(m['totais']['resultado_apos_despesas'])])
    tabela=LongTable([[p(t,'cabecalho') for t in titulos]]+[[p(v) for v in row] for row in linhas],
        colWidths=[largura*v/100 for v in (10,9,11,12,11,12,12,9,14)],repeatRows=1,hAlign='LEFT',splitByRow=1,splitInRow=1)
    tabela.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eff5')),('LINEBELOW',(0,0),(-1,0),.6,linha),
        ('LINEBELOW',(0,1),(-1,-1),.35,linha),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),
        ('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    partes.append(tabela)
    def rodape(canvas,documento):
        canvas.saveState();canvas.setStrokeColor(linha);canvas.line(margem,11*mm,largura_pagina-margem,11*mm)
        canvas.setFillColor(cinza);canvas.setFont(normal,8);canvas.drawString(margem,7*mm,'MEC-Serviços | Administração | Uso exclusivo do ADM')
        canvas.drawRightString(largura_pagina-margem,7*mm,'Página '+str(documento.page));canvas.restoreState()
    doc.build(partes,onFirstPage=rodape,onLaterPages=rodape);return saida.getvalue()
