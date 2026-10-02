from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.repositories.arquivo_tecnico import RepositorioArquivoTecnico


class ServicoArquivoTecnico:
    ALLOWED_EXTENSIONS = frozenset(
        {".step", ".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf", ".zip", ".rar"}
    )
    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    STORAGE_ROOT = Path("storage") / "arquivos_tecnicos"

    def __init__(self, banco: Session, *, storage_root: Path | None = None) -> None:
        self.banco = banco
        self.repositorio = RepositorioArquivoTecnico(banco)
        self.storage_root = (
            storage_root.resolve()
            if storage_root is not None
            else (Path(__file__).resolve().parents[3] / self.STORAGE_ROOT).resolve()
        )

    def _solicitacao_existe(self, solicitacao_id: int) -> None:
        if self.banco.get(SolicitacaoServico, solicitacao_id) is None:
            raise HTTPException(
                status_code=404,
                detail="solicitacao_nao_encontrada",
            )

    def _validar_extensao(self, filename: str | None) -> tuple[str, str]:
        nome = Path(filename or "").name
        if not nome or nome in {".", ".."}:
            raise HTTPException(
                status_code=400,
                detail="nome_arquivo_obrigatorio",
            )
        if len(nome) > 255:
            raise HTTPException(
                status_code=400,
                detail="nome_arquivo_muito_longo",
            )

        extensao = Path(nome).suffix.lower()
        if extensao not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="extensao_arquivo_nao_permitida",
            )
        return nome, extensao

    async def criar(
        self,
        solicitacao_id: int,
        arquivo: UploadFile,
    ) -> ArquivoTecnico:
        self._solicitacao_existe(solicitacao_id)
        nome_original, extensao = self._validar_extensao(arquivo.filename)

        self.storage_root.mkdir(parents=True, exist_ok=True)
        nome_fisico = f"{uuid.uuid4().hex}{extensao}"
        destino = self.storage_root / nome_fisico
        temporario = self.storage_root / f".{nome_fisico}.part"

        total = 0
        digest = hashlib.sha256()

        try:
            with temporario.open("wb") as saida:
                while True:
                    bloco = await arquivo.read(self.CHUNK_SIZE)
                    if not bloco:
                        break

                    total += len(bloco)
                    if total > self.MAX_FILE_SIZE_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="arquivo_excede_limite_de_tamanho",
                        )

                    digest.update(bloco)
                    saida.write(bloco)

            os.replace(temporario, destino)

            item = ArquivoTecnico(
                solicitacao_id=solicitacao_id,
                nome_original=nome_original,
                extensao=extensao,
                content_type=arquivo.content_type,
                tamanho_bytes=total,
                sha256=digest.hexdigest(),
                caminho_arquivo=str(destino),
                ativo=True,
            )

            try:
                return self.repositorio.criar(item)
            except Exception:
                self.banco.rollback()
                destino.unlink(missing_ok=True)
                raise

        except HTTPException:
            temporario.unlink(missing_ok=True)
            destino.unlink(missing_ok=True)
            raise
        except Exception:
            temporario.unlink(missing_ok=True)
            destino.unlink(missing_ok=True)
            raise
        finally:
            await arquivo.close()

    def listar(self, solicitacao_id: int) -> list[ArquivoTecnico]:
        self._solicitacao_existe(solicitacao_id)
        return self.repositorio.listar_ativos_por_solicitacao(solicitacao_id)

    def obter(self, arquivo_id: int) -> ArquivoTecnico:
        item = self.repositorio.obter_ativo_por_id(arquivo_id)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="arquivo_tecnico_nao_encontrado",
            )
        return item

    def caminho_seguro(self, item: ArquivoTecnico) -> Path:
        caminho = Path(item.caminho_arquivo).resolve()
        if not caminho.is_relative_to(self.storage_root):
            raise HTTPException(
                status_code=500,
                detail="caminho_arquivo_invalido",
            )
        if not caminho.is_file():
            raise HTTPException(
                status_code=404,
                detail="arquivo_fisico_nao_encontrado",
            )
        return caminho

    def desvincular(self, arquivo_id: int) -> None:
        item = self.repositorio.obter_ativo_por_id(arquivo_id)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail="arquivo_tecnico_nao_encontrado",
            )

        item.ativo = False
        self.repositorio.salvar(item)
