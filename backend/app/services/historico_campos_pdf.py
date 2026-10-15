from datetime import datetime, timezone
import hashlib
import json
from sqlalchemy import select
from backend.app.models.historico_campos_pdf import HistoricoCampoPdf
from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao
from backend.app.schemas.historico_campos_pdf import GuardarHistoricoPdf, ValorHistoricoPdf, LIMITES
from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
from backend.app.services.documentacao_cotacao import travar_documentacao


def chave_valor(valor: str) -> str:
    return hashlib.sha256(" ".join(valor.split()).casefold().encode()).hexdigest()


class ServicoHistoricoCamposPdf:
    def __init__(self, banco):
        self.banco = banco

    def listar(self, usuario):
        ServicoPreparacaoPdf.exigir_admin(usuario)
        valores = {campo: [] for campo in LIMITES}
        vistos = {campo: set() for campo in LIMITES}

        def incluir(campo, valor):
            try:
                item = ValorHistoricoPdf(campo=campo, valor=str(valor))
            except (ValueError, TypeError):
                return
            chave = chave_valor(item.valor)
            if chave not in vistos[campo]:
                vistos[campo].add(chave)
                valores[campo].append(item.valor)

        registros = self.banco.scalars(select(HistoricoCampoPdf).where(
            HistoricoCampoPdf.usuario_admin_id == usuario.usuario_id).order_by(
            HistoricoCampoPdf.atualizado_em.desc(), HistoricoCampoPdf.id.desc()))
        for item in registros:
            incluir(item.campo, item.valor)
        # Leitura das configurações antigas: não modifica PDFs ou o histórico.
        anteriores = self.banco.scalars(select(PreparacaoPdfCotacao.configuracao_json).where(
            PreparacaoPdfCotacao.usuario_admin_id == usuario.usuario_id).order_by(
            PreparacaoPdfCotacao.criado_em.desc(), PreparacaoPdfCotacao.id.desc()))
        for configuracao in anteriores:
            try:
                paginas = json.loads(configuracao)
            except (ValueError, TypeError):
                continue
            if not isinstance(paginas, list):
                continue
            for pagina in paginas:
                campos = pagina.get("campos") if isinstance(pagina, dict) else None
                if isinstance(campos, dict):
                    for campo, valor in campos.items():
                        if campo in LIMITES and isinstance(valor, (str, int)) and not isinstance(valor, bool):
                            incluir(campo, valor)
        return {"campos": valores}

    def guardar(self, dados: GuardarHistoricoPdf, usuario):
        ServicoPreparacaoPdf.exigir_admin(usuario)
        itens = {(item.campo, chave_valor(item.valor)): item.valor for item in dados.itens}
        # A transação curta impede duplicação em duas abas do mesmo ADM.
        travar_documentacao(self.banco)
        agora = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        try:
            for (campo, chave), valor in itens.items():
                item = self.banco.scalar(select(HistoricoCampoPdf).where(
                    HistoricoCampoPdf.usuario_admin_id == usuario.usuario_id,
                    HistoricoCampoPdf.campo == campo, HistoricoCampoPdf.chave_valor == chave))
                if item is None:
                    item = HistoricoCampoPdf(usuario_admin_id=usuario.usuario_id, campo=campo,
                        chave_valor=chave, valor=valor, atualizado_em=agora)
                    self.banco.add(item)
                else:
                    item.valor = valor
                    item.atualizado_em = agora
            self.banco.commit()
        except Exception:
            self.banco.rollback()
            raise
        return {"guardados": len(itens)}
