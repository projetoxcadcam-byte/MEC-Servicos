"""Substitui a legenda preservando os operadores e transformações do desenho.

PDFium só mede e renderiza; não regrava o conteúdo das páginas.
Marcas temporárias relacionam os objetos aos operadores originais. A cópia
é recusada se a comparação visual detectar mudanças fora da seleção.
"""
from __future__ import annotations

from contextlib import closing
from io import BytesIO
from pathlib import Path
import math
from PIL import ImageChops
from threading import RLock
import pypdfium2 as pdfium
import pypdfium2.raw as raw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DictionaryObject, NameObject, NumberObject
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from fastapi import HTTPException
from backend.app.schemas.preparacao_pdf import AreaCarimbo
from backend.app.schemas.operacoes_pdf import OPERACOES_PDF

TRAVA_PDFIUM = RLock()
MAX_BYTES = 30 * 1024 * 1024
MAX_PAGINAS = 50
ESCOPOS_SERVICO = {
    "conforme_solicitacao": "Conforme solicitacao",
    "desbaste": "Somente desbaste",
    "acabamento": "Somente acabamento",
    "peca_completa": "Peca completa",
}


def ler_pdf(conteudo: bytes) -> PdfReader:
    if len(conteudo) > MAX_BYTES:
        raise HTTPException(413, detail="pdf_excede_limite_preparacao")
    if not conteudo.startswith(b"%PDF-"):
        raise HTTPException(422, detail="pdf_invalido")
    try:
        leitor = PdfReader(BytesIO(conteudo))
        if leitor.is_encrypted:
            raise HTTPException(422, detail="pdf_protegido_nao_editavel")
        if not 1 <= len(leitor.pages) <= MAX_PAGINAS:
            raise HTTPException(422, detail="pdf_numero_paginas_nao_suportado")
        if leitor.get_fields():
            raise HTTPException(422, detail="pdf_formulario_ou_assinatura_nao_editavel")
        for p in leitor.pages:
            if p.get("/Annots"):
                raise HTTPException(422, detail="pdf_anotado_nao_editavel")
            if (p.rotation or p.cropbox != p.mediabox or float(p.mediabox.left) != 0
                    or float(p.mediabox.bottom) != 0 or float(p.get("/UserUnit", 1)) != 1):
                raise HTTPException(422, detail="pdf_rotacao_ou_recorte_nao_suportado")
            if not 72 <= float(p.mediabox.width) <= 14400 or not 72 <= float(p.mediabox.height) <= 14400:
                raise HTTPException(422, detail="pdf_tamanho_pagina_nao_suportado")
        return leitor
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, detail="pdf_invalido") from None


def informacoes(conteudo: bytes):
    r = ler_pdf(conteudo)
    return {"paginas": [{"pagina": i + 1, "largura": float(p.mediabox.width), "altura": float(p.mediabox.height)} for i, p in enumerate(r.pages)]}


def imagem_pagina(conteudo: bytes, numero: int) -> bytes:
    leitor = ler_pdf(conteudo)
    if numero < 1 or numero > len(leitor.pages):
        raise HTTPException(404, detail="pagina_pdf_nao_encontrada")
    with TRAVA_PDFIUM:
        try:
            with pdfium.PdfDocument(conteudo) as doc:
                p = doc[numero - 1]
                w, h = p.get_size()
                bitmap = p.render(scale=min(2.0, 4000 / max(w, h)))
                try:
                    im = bitmap.to_pil()
                    buf = BytesIO()
                    im.save(buf, format="PNG")
                    im.close()
                    return buf.getvalue()
                finally:
                    bitmap.close()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, detail="pdf_nao_pode_ser_renderizado") from None


def _linhas(texto: str, largura: float, tamanho: float):
    resultado = []
    for paragrafo in texto.replace("\t", " ").splitlines() or [""]:
        atual = ""
        for palavra in paragrafo.split():
            if stringWidth(palavra, "Helvetica", tamanho) > largura:
                raise HTTPException(422, detail="texto_nao_cabe_no_carimbo")
            nova = (atual + " " + palavra).strip()
            if atual and stringWidth(nova, "Helvetica", tamanho) > largura:
                resultado.append(atual)
                atual = palavra
            else:
                atual = nova
        resultado.append(atual)
    return resultado


def carimbo(w: float, h: float, area: AreaCarimbo, logo: Path, codigo: str) -> bytes:
    x, y = area.x * w, h - (area.y + area.altura) * h
    largura, altura = area.largura * w, area.altura * h
    if largura < 320 - 1e-6 or altura < 96 - 1e-6:
        raise HTTPException(422, detail="area_carimbo_muito_pequena")
    saida = BytesIO()
    c = canvas.Canvas(saida, pagesize=(w, h), invariant=1)
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y, largura, altura, fill=1, stroke=0)
    c.setStrokeColorRGB(0.15, 0.21, 0.28)
    c.setLineWidth(0.5)
    c.rect(x + 0.5, y + 0.5, largura - 1, altura - 1, fill=0, stroke=1)
    topo = y + altura
    compacto = altura < 132
    cabecalho = 22 if compacto else 29
    c.drawImage(ImageReader(str(logo)), x + 7, topo - (20 if compacto else 25), width=100 if compacto else 112, height=17 if compacto else 22,
                preserveAspectRatio=True, anchor="c", mask="auto")
    c.setFillColorRGB(0.08, 0.16, 0.25)
    c.setFont("Helvetica-Bold", 7 if compacto else 8)
    c.drawRightString(x + largura - 7, topo - (9 if compacto else 12), "DOCUMENTO TECNICO PARA COTACAO")
    c.setFont("Helvetica", 6)
    c.drawRightString(x + largura - 7, topo - (18 if compacto else 22), codigo)
    campos = area.campos
    linhas = [
        [("DESCRICAO", campos.descricao, .72), ("CODIGO TECNICO", campos.codigo_tecnico or codigo, .28)],
        [("MATERIAL", campos.material, .5), ("QUANTIDADE", str(campos.quantidade), .2), ("DUREZA", campos.dureza or "--", .3)],
        [("TRATAMENTO TERMICO", campos.tratamento_termico or "--", .5), ("REVESTIMENTO", campos.revestimento or "--", .5)],
        [("ESCALA", campos.escala, .3), ("UNIDADE", campos.unidade, .2), ("REVISAO", campos.revisao or "--", .25), ("PAGINA", str(area.pagina), .25)],
        [("TOLERANCIAS GERAIS", campos.tolerancias_gerais or "--", 1.0)],
    ]
    if compacto:
        # Redistribui os mesmos campos; mantém o tamanho do texto e a área escolhida.
        linhas = [
            [("DESCRICAO", campos.descricao, .70), ("CODIGO TECNICO", campos.codigo_tecnico or codigo, .30)],
            [("MATERIAL", campos.material, .44), ("QUANTIDADE", str(campos.quantidade), .15), ("DUREZA", campos.dureza or "--", .26), ("REVISAO", campos.revisao or "--", .15)],
            [("TRATAMENTO TERMICO", campos.tratamento_termico or "--", .36), ("REVESTIMENTO", campos.revestimento or "--", .34), ("ESCALA", campos.escala, .16), ("UNIDADE", campos.unidade, .14)],
            [("TOLERANCIAS GERAIS", campos.tolerancias_gerais or "--", .84), ("PAGINA", str(area.pagina), .16)],
        ]
    tem_escopo = (campos.escopo_servico != "conforme_solicitacao"
                  or bool(campos.sobremetal or campos.observacoes_servico or campos.operacoes_servico))
    if tem_escopo:
        tecnicos = "; ".join(f"{label}: {valor}" for label, valor in (
            ("Dureza", campos.dureza), ("Tratamento", campos.tratamento_termico),
            ("Revestimento", campos.revestimento), ("Revisao", campos.revisao),
            ("Tolerancias", campos.tolerancias_gerais)) if valor)
        servico = "; ".join(v for v in (
            "Operacoes: " + ", ".join(OPERACOES_PDF[v] for v in campos.operacoes_servico) if campos.operacoes_servico else "",
            ESCOPOS_SERVICO[campos.escopo_servico] if campos.escopo_servico != "conforme_solicitacao" or not campos.operacoes_servico else "",
            f"Sobremetal: {campos.sobremetal}" if campos.sobremetal else "",
            f"Observacoes: {campos.observacoes_servico}" if campos.observacoes_servico else "") if v)
        linhas = [
            [("DESCRICAO", campos.descricao, .70), ("CODIGO TECNICO", campos.codigo_tecnico or codigo, .30)],
            [("MATERIAL", campos.material, .42), ("QUANTIDADE", str(campos.quantidade), .21),
             ("ESCALA", campos.escala, .15), ("UNIDADE", campos.unidade, .12), ("PAGINA", str(area.pagina), .10)],
            [("DADOS TECNICOS", tecnicos or "--", 1.0)],
            [("ESCOPO DO SERVICO", servico, 1.0)],
        ]
        alturas = [max(len(_linhas(valor, largura * proporcao - 8, 7.2)) * 8.2 + 8
                       for _, valor, proporcao in colunas) for colunas in linhas]
        restante = altura - cabecalho - sum(alturas)
        if restante < -1e-6:
            raise HTTPException(422, detail="texto_nao_cabe_no_carimbo")
        alturas = [a + max(0, restante) / len(linhas) for a in alturas]
    else:
        # Sem novos campos, conserva a diagramação das cópias anteriores.
        alturas = [(altura - cabecalho) / len(linhas)] * len(linhas)
    atual_y = topo - cabecalho
    for colunas, altura_linha in zip(linhas, alturas):
        c.line(x, atual_y, x + largura, atual_y)
        atual_x = x
        for label, valor, proporcao in colunas:
            l = largura * proporcao
            if atual_x > x:
                c.line(atual_x, atual_y, atual_x, atual_y - altura_linha)
            c.setFont("Helvetica", 5.5)
            c.setFillColorRGB(.25, .3, .35)
            c.drawString(atual_x + 4, atual_y - 7, label)
            tamanho = 7.2
            textos = _linhas(valor, l - 8, tamanho)
            if len(textos) * 8.2 + 8 > altura_linha + 1e-6:
                raise HTTPException(422, detail="texto_nao_cabe_no_carimbo")
            c.setFont("Helvetica", tamanho)
            c.setFillColorRGB(0, 0, 0)
            for i, t in enumerate(textos):
                c.drawString(atual_x + 4, atual_y - 15 - i * 8.2, t)
            atual_x += l
        atual_y -= altura_linha
    c.showPage()
    c.save()
    return saida.getvalue()


PINTURA_CAMINHO = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
MOSTRAR_TEXTO = {b"Tj", b"TJ", b"'", b'"'}
MARCAS_ORIGINAIS = {b"BMC", b"BDC", b"EMC", b"MP", b"DP"}


def _operacoes_marcadas(pagina, leitor):
    """Só a cópia temporária recebe MCIDs. Não modifica matrices cm/Tm ou q/Q."""
    stream = ContentStream(pagina.get("/Contents"), leitor)
    operacoes = [(a, op) for a, op in stream.operations if op not in MARCAS_ORIGINAIS]
    marcadas, grupos = [], {}
    texto = None
    pilha = 0
    for i, (a, op) in enumerate(operacoes):
        if op == b"q":
            pilha += 1
        elif op == b"Q":
            pilha -= 1
            if pilha < 0:
                raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
        if op == b"BT":
            if texto is not None:
                raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
            texto = i
            grupos[i] = b"TEXTO"
        elif op == b"ET" and texto is None:
            raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
        elif op in MOSTRAR_TEXTO and texto is None:
            raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
        elif op in PINTURA_CAMINHO | {b"Do", b"sh", b"INLINE IMAGE"}:
            if texto is not None:
                raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
            grupos[i] = op
        if i in grupos:
            marcadas.append(([NameObject("/MEC"), DictionaryObject({NameObject("/MCID"): NumberObject(i)})], b"BDC"))
        marcadas.append((a, op))
        if op == b"ET":
            texto = None
            marcadas.append(([], b"EMC"))
        elif i in grupos and op != b"BT":
            marcadas.append(([], b"EMC"))
    if texto is not None or pilha:
        raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
    stream.operations = marcadas
    pagina.replace_contents(stream)
    return operacoes, grupos


def _classificar_objetos(documento_marcado, areas, operacoes_paginas):
    remover_paginas = {}
    with pdfium.PdfDocument(documento_marcado) as doc:
        for area in areas:
            with closing(doc[area.pagina - 1]) as pagina:
                w, h = pagina.get_size()
                box = (area.x*w, h-(area.y+area.altura)*h,
                       (area.x+area.largura)*w, h-area.y*h)
                grupos = operacoes_paginas[area.pagina - 1][1]
                situacoes = {}
                for obj in pagina.get_objects(max_depth=1):
                    marca = raw.FPDFPageObj_GetMarkedContentID(obj)
                    if marca not in grupos:
                        raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
                    b = obj.get_bounds()
                    if not all(math.isfinite(v) for v in b):
                        raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
                    contido = box[0] <= b[0] <= b[2] <= box[2] and box[1] <= b[1] <= b[3] <= box[3]
                    cruza = min(b[2], box[2]) > max(b[0], box[0]) and min(b[3], box[3]) > max(b[1], box[1])
                    if cruza and not contido and obj.type != raw.FPDF_PAGEOBJ_PATH:
                        raise HTTPException(422, detail="area_corta_texto_imagem_ou_formulario")
                    situacoes.setdefault(marca, set()).add(contido)
                if any(len(v) > 1 for v in situacoes.values()):
                    # Um BT/ET pode reunir texto dentro e fora da legenda. Não é
                    # seguro apagar só um Tj: o seguinte pode usar sua posição.
                    raise HTTPException(422, detail="area_corta_bloco_texto")
                remover_paginas[area.pagina - 1] = {m for m, v in situacoes.items() if v == {True}}
    return remover_paginas


def _remover_pintura(operacoes, grupos, remover):
    # Elimina também as coordenadas dos objetos retirados. Substituir só S/f
    # por n deixaria o antigo logo vetorial recuperável no conteúdo do PDF.
    construcoes = {b"m", b"l", b"c", b"v", b"y", b"h", b"re"}
    caminho, apagar_geometria, recorte = [], set(), False
    for i, (_, op) in enumerate(operacoes):
        if op in construcoes:
            caminho.append(i)
        if op in {b"W", b"W*"}:
            recorte = True
        if op in PINTURA_CAMINHO | {b"n"}:
            if i in remover and op in PINTURA_CAMINHO:
                if recorte:
                    raise HTTPException(422, detail="pdf_estrutura_nao_suportada")
                apagar_geometria.update(caminho)
            caminho, recorte = [], False
    novas = []
    texto = None
    for i, (a, op) in enumerate(operacoes):
        if i in apagar_geometria:
            continue
        if op == b"BT":
            texto = i
        if texto in remover and op in MOSTRAR_TEXTO:
            # Os parâmetros de texto persistem entre BT/ET. Preserva Tw/Tc da
            # forma abreviada, mas elimina os próprios caracteres do cliente.
            if op == b'"':
                novas.extend([([a[0]], b"Tw"), ([a[1]], b"Tc"), ([], b"T*")])
            elif op == b"'":
                novas.append(([], b"T*"))
            continue
        if i in remover and grupos[i] != b"TEXTO":
            if op in PINTURA_CAMINHO:
                # Consome o caminho sem preservar coordenadas de identificação.
                novas.append(([], b"n"))
            continue
        novas.append((a, op))
        if op == b"ET":
            texto = None
    return novas


def _limpar_recursos(pagina, operacoes):
    # Um logo/formulário removido não pode continuar embutido como recurso
    # sem uso. Mantém os recursos dos elementos técnicos que permanecem.
    recursos = pagina.get("/Resources")
    if recursos is None:
        return
    # Recursos podem ser compartilhados com páginas não editadas. Isola os
    # dicionários antes de retirar entradas desta página.
    recursos = DictionaryObject(recursos.get_object())
    pagina[NameObject("/Resources")] = recursos
    recursos.pop(NameObject("/Properties"), None)
    usados = {str(a[0]) for a, op in operacoes if op == b"Do"}
    xobjects = recursos.get("/XObject")
    if xobjects is not None:
        xobjects = DictionaryObject(xobjects.get_object())
        recursos[NameObject("/XObject")] = xobjects
        for nome in list(xobjects):
            if str(nome) not in usados:
                del xobjects[nome]


def _imagem_comparacao(pagina, escala):
    bitmap = pagina.render(scale=escala)
    try:
        im = bitmap.to_pil()
        try:
            return im.convert("RGB")
        finally:
            im.close()
    finally:
        bitmap.close()


def _conferir_preservacao_visual(original, preparado, areas):
    """Compara todos os pixels fora da legenda; permite 1 pixel de borda."""
    with pdfium.PdfDocument(original) as antes, pdfium.PdfDocument(preparado) as depois:
        for area in areas:
            with closing(antes[area.pagina - 1]) as a, closing(depois[area.pagina - 1]) as b:
                if a.get_size() != b.get_size():
                    raise HTTPException(422, detail="pdf_divergencia_fora_legenda")
                w, h = a.get_size()
                escala = min(2.0, 4000 / max(w, h))
                im_a = _imagem_comparacao(a, escala)
                im_b = _imagem_comparacao(b, escala)
                try:
                    if im_a.size != im_b.size:
                        raise HTTPException(422, detail="pdf_divergencia_fora_legenda")
                    diferenca = ImageChops.difference(im_a, im_b)
                    try:
                        limites = (max(0, math.floor(area.x*w*escala)-1),
                                   max(0, math.floor(area.y*h*escala)-1),
                                   min(im_a.width, math.ceil((area.x+area.largura)*w*escala)+1),
                                   min(im_a.height, math.ceil((area.y+area.altura)*h*escala)+1))
                        diferenca.paste((0, 0, 0), limites)
                        if diferenca.getbbox() is not None:
                            raise HTTPException(422, detail="pdf_divergencia_fora_legenda")
                    finally:
                        diferenca.close()
                finally:
                    im_a.close()
                    im_b.close()


def preparar(conteudo: bytes, areas: list[AreaCarimbo], logo: Path, codigo: str) -> bytes:
    leitor = ler_pdf(conteudo)
    overlays = {}
    for area in areas:
        if area.pagina > len(leitor.pages):
            raise HTTPException(422, detail="pagina_pdf_nao_encontrada")
        p = leitor.pages[area.pagina - 1]
        overlays[area.pagina - 1] = carimbo(float(p.mediabox.width), float(p.mediabox.height), area, logo, codigo)
    with TRAVA_PDFIUM:
        try:
            # Marca uma cópia apenas para medir os objetos. O conteúdo final
            # é construído dos operadores originais, sem PDFium gen_content.
            marcado = PdfWriter()
            operacoes_paginas = {}
            for i, p in enumerate(leitor.pages):
                pagina = marcado.add_page(p)
                if i in overlays:
                    operacoes_paginas[i] = _operacoes_marcadas(pagina, marcado)
            buf = BytesIO()
            marcado.write(buf)
            remover = _classificar_objetos(buf.getvalue(), areas, operacoes_paginas)
            writer = PdfWriter()
            writer.pdf_header = b"%PDF-1.7"
            for i, p in enumerate(leitor.pages):
                pagina = writer.add_page(p, excluded_keys=["/Annots", "/AA", "/Metadata", "/PieceInfo", "/Thumb", "/StructParents"])
                if i in overlays:
                    operacoes, grupos = operacoes_paginas[i]
                    novas = _remover_pintura(operacoes, grupos, remover[i])
                    stream = ContentStream(None, writer)
                    stream.operations = novas
                    pagina.replace_contents(stream)
                    _limpar_recursos(pagina, novas)
                    pagina.merge_page(PdfReader(BytesIO(overlays[i])).pages[0], expand=False)
                    pagina.compress_content_streams()
            writer.add_metadata({"/Title": "MEC-Serviços - Documento técnico para cotação", "/Author": "MEC-Serviços"})
            writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
            saida = BytesIO()
            writer.write(saida)
            resultado = saida.getvalue()
            if len(resultado) > MAX_BYTES:
                raise HTTPException(413, detail="pdf_excede_limite_preparacao")
            _conferir_preservacao_visual(conteudo, resultado, areas)
            return resultado
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, detail="pdf_nao_pode_ser_preparado") from None
