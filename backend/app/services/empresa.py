from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.empresa import Empresa
from backend.app.repositories.empresa import RepositorioEmpresa
from backend.app.schemas.empresa import EmpresaCriacao


class EmpresaNaoEncontrada(LookupError):
    pass


class DocumentoEmpresaDuplicado(ValueError):
    pass


class ServicoEmpresa:
    def __init__(self, banco: Session) -> None:
        self.repositorio = RepositorioEmpresa(banco)

    def criar(self, dados: EmpresaCriacao) -> Empresa:
        if self.repositorio.obter_por_documento(dados.documento) is not None:
            raise DocumentoEmpresaDuplicado(dados.documento)

        try:
            return self.repositorio.criar(dados)
        except IntegrityError as exc:
            self.repositorio.banco.rollback()
            raise DocumentoEmpresaDuplicado(dados.documento) from exc

    def obter(self, empresa_id: int) -> Empresa:
        empresa = self.repositorio.obter_por_id(empresa_id)
        if empresa is None:
            raise EmpresaNaoEncontrada(empresa_id)
        return empresa

    def listar(self, *, deslocamento: int = 0, limite: int = 100) -> list[Empresa]:
        return self.repositorio.listar(
            deslocamento=deslocamento,
            limite=limite,
        )
