from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.documentacao_cotacao import LiberacaoArquivoCotacao
from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao, PublicacaoPdfCotacao
from backend.app.schemas.preparacao_pdf import AreaCarimbo, PrepararPdf, PreparacaoPdfResposta
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico


class ServicoPreparacaoPdf:
    def __init__(self, banco: Session):
        self.banco = banco
        self.arquivos = ServicoArquivoTecnico(banco)
        self.pasta = (self.arquivos.storage_root.parent / "pdfs_preparados_cotacao").resolve()
        self.logo = Path(__file__).resolve().parents[1] / "assets/mec_logo_pdf.png"

    @staticmethod
    def exigir_admin(usuario: UsuarioAcesso):
        if usuario.perfil != "admin":
            raise HTTPException(403, detail="acao_exclusiva_da_administracao")

    def original(self, arquivo_id: int, sha: str | None = None) -> ArquivoTecnico:
        from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao
        item = self.arquivos.obter(arquivo_id)
        if item.extensao.lower() != ".pdf":
            raise HTTPException(422, detail="arquivo_nao_e_pdf")
        if sha is not None and item.sha256 != sha:
            raise HTTPException(409, detail="documentacao_alterada_atualize")
        if not ServicoDocumentacaoCotacao(self.banco).conteudo_valido(item):
            raise HTTPException(409, detail="arquivo_tecnico_sem_conteudo_valido")
        return item

    def conteudo_original(self, arquivo_id: int, sha: str | None = None) -> bytes:
        item = self.original(arquivo_id, sha)
        caminho = self.arquivos.caminho_seguro(item)
        from backend.app.services.motor_pdf_cotacao import MAX_BYTES
        if item.tamanho_bytes > MAX_BYTES:
            raise HTTPException(413, detail="pdf_excede_limite_preparacao")
        conteudo = caminho.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != item.sha256:
            raise HTTPException(409, detail="documentacao_alterada_atualize")
        return conteudo

    @staticmethod
    def resposta(p: PreparacaoPdfCotacao):
        return PreparacaoPdfResposta(id=p.id, arquivo_id=p.arquivo_id, versao=p.versao,
            sha256_original=p.sha256_original, sha256=p.sha256, tamanho_bytes=p.tamanho_bytes,
            criado_em=p.criado_em, administrador_nome=p.administrador_nome,
            registro_interno=p.registro_interno,
            paginas=[AreaCarimbo.model_validate(v) for v in json.loads(p.configuracao_json)])

    def listar(self, arquivo_id: int):
        self.original(arquivo_id)
        return [self.resposta(p) for p in self.banco.scalars(select(PreparacaoPdfCotacao)
            .where(PreparacaoPdfCotacao.arquivo_id == arquivo_id).order_by(PreparacaoPdfCotacao.versao.desc()))]

    def obter(self, preparacao_id: int) -> PreparacaoPdfCotacao:
        p = self.banco.get(PreparacaoPdfCotacao, preparacao_id)
        if p is None:
            raise HTTPException(404, detail="preparacao_pdf_nao_encontrada")
        return p

    def caminho(self, p: PreparacaoPdfCotacao) -> Path:
        caminho = Path(p.caminho_arquivo).resolve()
        if not caminho.is_relative_to(self.pasta) or not caminho.is_file():
            raise HTTPException(409, detail="pdf_preparado_indisponivel")
        if caminho.stat().st_size != p.tamanho_bytes or hashlib.sha256(caminho.read_bytes()).hexdigest() != p.sha256:
            raise HTTPException(409, detail="pdf_preparado_indisponivel")
        return caminho

    def validar_para_liberacao(self, arquivo: ArquivoTecnico, preparacao_id: int):
        p = self.obter(preparacao_id)
        if p.arquivo_id != arquivo.id or p.sha256_original != arquivo.sha256 or arquivo.extensao.lower() != ".pdf":
            raise HTTPException(409, detail="preparacao_pdf_diverge_do_original")
        self.caminho(p)
        return p

    def publicado(self, arquivo_id: int):
        estado = self.banco.get(LiberacaoArquivoCotacao, arquivo_id)
        if estado is None or not estado.disponivel:
            return None
        publicacao = self.banco.scalar(select(PublicacaoPdfCotacao).where(
            PublicacaoPdfCotacao.arquivo_id == arquivo_id,
            PublicacaoPdfCotacao.versao_liberacao == estado.versao))
        return self.obter(publicacao.preparacao_id) if publicacao else None

    def publicado_valido(self, item: ArquivoTecnico) -> bool:
        try:
            p = self.publicado(item.id)
            if p is not None:
                self.validar_para_liberacao(item, p.id)
            return True
        except (HTTPException, OSError, ValueError):
            return False

    def criar(self, arquivo_id: int, dados: PrepararPdf, usuario: UsuarioAcesso):
        self.exigir_admin(usuario)
        from backend.app.services.documentacao_cotacao import travar_documentacao
        from backend.app.services.motor_pdf_cotacao import preparar
        paginas = [{**a.model_dump(mode="json"), "campos": a.campos.dados_persistentes()}
                   for a in dados.paginas]
        pedido_dados = {**dados.model_dump(mode="json"), "paginas": paginas}
        pedido = json.dumps(pedido_dados, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(pedido.encode()).hexdigest()
        existente = self.banco.scalar(select(PreparacaoPdfCotacao).where(PreparacaoPdfCotacao.chave_operacao == str(dados.chave_operacao)))
        if existente:
            if existente.usuario_admin_id != usuario.usuario_id or existente.arquivo_id != arquivo_id or existente.pedido_sha256 != digest:
                raise HTTPException(409, detail="chave_operacao_reutilizada")
            return self.resposta(existente)
        item = self.original(arquivo_id, dados.sha256)
        estado = self.banco.get(LiberacaoArquivoCotacao, arquivo_id)
        if dados.versao_liberacao != (estado.versao if estado else 0):
            raise HTTPException(409, detail="documentacao_alterada_atualize")
        conteudo = self.conteudo_original(arquivo_id, dados.sha256)
        saida = preparar(conteudo, dados.paginas, self.logo, f"ARQUIVO-{item.id}")
        # Renderização e processamento não seguram a escrita do banco.
        travar_documentacao(self.banco)
        self.banco.expire_all()
        item = self.original(arquivo_id, dados.sha256)
        estado = self.banco.get(LiberacaoArquivoCotacao, arquivo_id)
        if dados.versao_liberacao != (estado.versao if estado else 0):
            raise HTTPException(409, detail="documentacao_alterada_atualize")
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.pasta / (uuid4().hex + ".pdf")
        versao = (self.banco.scalar(select(func.max(PreparacaoPdfCotacao.versao)).where(PreparacaoPdfCotacao.arquivo_id == arquivo_id)) or 0) + 1
        p = PreparacaoPdfCotacao(arquivo_id=arquivo_id, versao=versao, sha256_original=item.sha256,
            sha256=hashlib.sha256(saida).hexdigest(), tamanho_bytes=len(saida), caminho_arquivo=str(destino),
            configuracao_json=json.dumps(paginas, ensure_ascii=False),
            registro_interno=dados.registro_interno, usuario_admin_id=usuario.usuario_id, administrador_nome=usuario.nome,
            criado_em=datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            chave_operacao=str(dados.chave_operacao), pedido_sha256=digest)
        try:
            with destino.open("xb") as f:
                f.write(saida)
            self.banco.add(p)
            self.banco.commit()
        except IntegrityError:
            self.banco.rollback()
            destino.unlink(missing_ok=True)
            repetido = self.banco.scalar(select(PreparacaoPdfCotacao).where(PreparacaoPdfCotacao.chave_operacao == str(dados.chave_operacao)))
            if repetido and repetido.usuario_admin_id == usuario.usuario_id and repetido.arquivo_id == arquivo_id and repetido.pedido_sha256 == digest:
                return self.resposta(repetido)
            raise HTTPException(409, detail="documentacao_alterada_atualize") from None
        except Exception:
            self.banco.rollback()
            destino.unlink(missing_ok=True)
            raise
        return self.resposta(p)
