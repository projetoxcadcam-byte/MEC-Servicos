from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.empresa import Empresa
from backend.app.schemas.empresa import EmpresaCriacao


class RepositorioEmpresa:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def obter_por_id(self, empresa_id: int) -> Empresa | None:
        return self.banco.get(Empresa, empresa_id)

    def obter_por_documento(self, documento: str) -> Empresa | None:
        consulta = select(Empresa).where(Empresa.documento == documento)
        return self.banco.scalar(consulta)

    def listar(self, *, deslocamento: int = 0, limite: int = 100) -> list[Empresa]:
        consulta = (
            select(Empresa)
            .order_by(Empresa.id)
            .offset(deslocamento)
            .limit(limite)
        )
        return list(self.banco.scalars(consulta).all())

    def criar(self, dados: EmpresaCriacao) -> Empresa:
        empresa = Empresa(
            razao_social=dados.razao_social,
            documento=dados.documento,
            tipo_empresa=dados.tipo_empresa.value,
        )
        self.banco.add(empresa)
        self.banco.commit()
        self.banco.refresh(empresa)
        return empresa
