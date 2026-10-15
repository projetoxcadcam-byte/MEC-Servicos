from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.documentacao_cotacao import EventoArquivoCotacao, LiberacaoArquivoCotacao
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.documentacao_cotacao import ArquivoDocumentacao, EventoDocumentacao, PaginaDocumentacao, RegistroDocumentacao, SolicitacaoDocumentacao
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico


def travar_documentacao(banco: Session) -> None:
    # Serializa liberação, desvínculo e envio da cotação no SQLite local.
    conexao = banco.connection()
    if conexao.dialect.name == "sqlite" and not conexao.connection.driver_connection.in_transaction:
        banco.execute(text("BEGIN IMMEDIATE"))


class ServicoDocumentacaoCotacao:
    def __init__(self, banco: Session):
        self.banco = banco
        self.arquivos = ServicoArquivoTecnico(banco)

    def conteudo_valido(self, item: ArquivoTecnico) -> bool:
        if not item.ativo or item.tamanho_bytes <= 0:
            return False
        try:
            caminho = self.arquivos.caminho_seguro(item)
            if caminho.stat().st_size != item.tamanho_bytes: return False
            digest = hashlib.sha256()
            with caminho.open("rb") as arquivo:
                for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                    digest.update(bloco)
            return digest.hexdigest() == item.sha256
        except (HTTPException, OSError, ValueError):
            return False

    @staticmethod
    def _liberados():
        return select(ArquivoTecnico).join(LiberacaoArquivoCotacao, LiberacaoArquivoCotacao.arquivo_id == ArquivoTecnico.id).where(
            ArquivoTecnico.ativo.is_(True), LiberacaoArquivoCotacao.disponivel.is_(True),
            LiberacaoArquivoCotacao.sha256 == ArquivoTecnico.sha256,
        ).order_by(ArquivoTecnico.id)

    def listar_liberados(self, solicitacao_id: int) -> list[ArquivoTecnico]:
        from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
        pdfs = ServicoPreparacaoPdf(self.banco)
        return [a for a in self.banco.scalars(self._liberados().where(ArquivoTecnico.solicitacao_id == solicitacao_id)) if self.conteudo_valido(a) and pdfs.publicado_valido(a)]

    def solicitacoes_disponiveis(self) -> set[int]:
        from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
        pdfs = ServicoPreparacaoPdf(self.banco)
        return {a.solicitacao_id for a in self.banco.scalars(self._liberados()) if self.conteudo_valido(a) and pdfs.publicado_valido(a)}

    def exigir_para_cotacao(self, solicitacao_id: int) -> None:
        travar_documentacao(self.banco)
        if not self.listar_liberados(solicitacao_id):
            raise HTTPException(409, detail="solicitacao_sem_arquivo_liberado_para_cotacao")

    def exigir_acesso(self, solicitacao_id: int, arquivo_id: int | None = None) -> None:
        itens = self.listar_liberados(solicitacao_id)
        if not itens or (arquivo_id is not None and all(a.id != arquivo_id for a in itens)):
            raise HTTPException(403, detail="arquivo_aguarda_liberacao_administrativa")

    def detalhe(self, item: ArquivoTecnico) -> ArquivoDocumentacao:
        from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
        from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao, PublicacaoPdfCotacao
        pdfs = ServicoPreparacaoPdf(self.banco)
        publicado = pdfs.publicado(item.id)
        estado = self.banco.get(LiberacaoArquivoCotacao, item.id)
        valido = self.conteudo_valido(item)
        eventos = self.banco.scalars(select(EventoArquivoCotacao).where(EventoArquivoCotacao.arquivo_id == item.id).order_by(EventoArquivoCotacao.versao.desc())).all()
        copias = dict(self.banco.execute(select(PublicacaoPdfCotacao.evento_id, PreparacaoPdfCotacao.versao)
            .join(PreparacaoPdfCotacao, PreparacaoPdfCotacao.id == PublicacaoPdfCotacao.preparacao_id)
            .where(PublicacaoPdfCotacao.arquivo_id == item.id)).all())
        return ArquivoDocumentacao(id=item.id, solicitacao_id=item.solicitacao_id,nome_original=item.nome_original,
            extensao=item.extensao,tamanho_bytes=item.tamanho_bytes,sha256=item.sha256,ativo=item.ativo,
            versao=estado.versao if estado else 0, conteudo_valido=valido,
            liberado=bool(valido and estado and estado.disponivel and estado.sha256 == item.sha256 and pdfs.publicado_valido(item)),
            preparacao_pdf_publicada_id=publicado.id if publicado else None,
            versao_pdf_publicada=publicado.versao if publicado else None,
            historico=[EventoDocumentacao.model_validate(e).model_copy(update={"versao_pdf_preparada": copias.get(e.id)}) for e in eventos])

    def listar(self, solicitacao_id: int | None, deslocamento: int, limite: int) -> PaginaDocumentacao:
        filtros = [SolicitacaoServico.id == solicitacao_id] if solicitacao_id else []
        total = self.banco.scalar(select(func.count()).select_from(SolicitacaoServico).where(*filtros)) or 0
        linhas = self.banco.execute(select(SolicitacaoServico,Empresa.razao_social,ProcessoFabricacao.nome,Material.nome)
            .join(Empresa,Empresa.id == SolicitacaoServico.empresa_cliente_id).join(ProcessoFabricacao,ProcessoFabricacao.id == SolicitacaoServico.processo_id)
            .join(Material,Material.id == SolicitacaoServico.material_id).where(*filtros).order_by(SolicitacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()
        itens = []
        for s, cliente, processo, material in linhas:
            arquivos = [self.detalhe(a) for a in self.banco.scalars(select(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id == s.id).order_by(ArquivoTecnico.id))]
            itens.append(SolicitacaoDocumentacao(id=s.id,cliente=cliente,processo=processo,material=material,quantidade=s.quantidade,
                status=s.status,arquivos_ativos=sum(a.ativo for a in arquivos),arquivos_disponiveis=sum(a.liberado for a in arquivos),arquivos=arquivos))
        return PaginaDocumentacao(itens=itens,total=total,deslocamento=deslocamento,limite=limite)

    def registrar(self, arquivo_id: int, dados: RegistroDocumentacao, usuario: UsuarioAcesso) -> ArquivoDocumentacao:
        from backend.app.services.preparacao_pdf import ServicoPreparacaoPdf
        from backend.app.models.preparacao_pdf import PublicacaoPdfCotacao
        pdfs = ServicoPreparacaoPdf(self.banco)
        if usuario.perfil != "admin": raise HTTPException(403, detail="acao_exclusiva_da_administracao")
        travar_documentacao(self.banco)
        item = self.banco.get(ArquivoTecnico, arquivo_id)
        if item is None: raise HTTPException(404, detail="arquivo_tecnico_nao_encontrado")
        registro = dados.registro_interno.strip()
        if len(registro) < 3: raise HTTPException(422, detail="registro_interno_obrigatorio")
        repetido = self.banco.scalar(select(EventoArquivoCotacao).where(EventoArquivoCotacao.chave_operacao == str(dados.chave_operacao)))
        if repetido:
            publicacao = self.banco.scalar(select(PublicacaoPdfCotacao).where(PublicacaoPdfCotacao.evento_id == repetido.id))
            if (publicacao.preparacao_id if publicacao else None) != dados.preparacao_pdf_id:
                raise HTTPException(409,detail="chave_operacao_reutilizada")
            if (repetido.arquivo_id,repetido.acao,repetido.sha256,repetido.registro_interno,repetido.usuario_admin_id,repetido.versao - 1) != (
                    arquivo_id,dados.acao,dados.sha256,registro,usuario.usuario_id,dados.versao):
                raise HTTPException(409,detail="chave_operacao_reutilizada")
            if dados.acao == "liberar" and not dados.revisado_sem_contatos: raise HTTPException(422,detail="revisao_administrativa_obrigatoria")
            return self.detalhe(item)
        estado = self.banco.get(LiberacaoArquivoCotacao, arquivo_id)
        if dados.versao != (estado.versao if estado else 0) or dados.sha256 != item.sha256:
            raise HTTPException(409,detail="documentacao_alterada_atualize")
        if dados.acao == "liberar" and not dados.revisado_sem_contatos:
            raise HTTPException(422,detail="revisao_administrativa_obrigatoria")
        if dados.acao == "liberar" and not self.conteudo_valido(item):
            raise HTTPException(409,detail="arquivo_tecnico_sem_conteudo_valido")
        if dados.acao == "bloquear" and dados.preparacao_pdf_id is not None:
            raise HTTPException(422,detail="bloqueio_nao_seleciona_preparacao_pdf")
        if dados.preparacao_pdf_id is not None:
            pdfs.validar_para_liberacao(item, dados.preparacao_pdf_id)
        publicado = pdfs.publicado(item.id)
        if estado and estado.disponivel == (dados.acao == "liberar"):
            if dados.acao != "liberar" or (publicado.id if publicado else None) == dados.preparacao_pdf_id:
                raise HTTPException(409,detail="documentacao_ja_nesta_situacao")
        agora = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")
        versao = dados.versao + 1
        if estado is None:
            estado = LiberacaoArquivoCotacao(arquivo_id=arquivo_id,sha256=item.sha256,disponivel=dados.acao == "liberar",versao=versao,atualizado_em=agora)
            self.banco.add(estado)
        else:
            estado.sha256=item.sha256;estado.disponivel=dados.acao == "liberar";estado.versao=versao;estado.atualizado_em=agora
        evento = EventoArquivoCotacao(arquivo_id=arquivo_id,versao=versao,acao=dados.acao,sha256=item.sha256,
            registro_interno=registro,usuario_admin_id=usuario.usuario_id,administrador_nome=usuario.nome,
            chave_operacao=str(dados.chave_operacao),criado_em=agora)
        self.banco.add(evento)
        try:
            self.banco.flush()
            if dados.preparacao_pdf_id is not None:
                self.banco.add(PublicacaoPdfCotacao(arquivo_id=arquivo_id,preparacao_id=dados.preparacao_pdf_id,
                    evento_id=evento.id,versao_liberacao=versao))
            self.banco.commit()
        except IntegrityError:
            self.banco.rollback();raise HTTPException(409,detail="documentacao_alterada_atualize") from None
        return self.detalhe(item)
