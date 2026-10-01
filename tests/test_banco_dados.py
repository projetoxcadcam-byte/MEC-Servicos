from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.models.empresa import Empresa


def test_persistencia_empresa_em_memoria() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as banco:
        empresa = Empresa(
            razao_social="Oficina Teste Ltda",
            documento="TEST-DOC-0001",
            tipo_empresa="fornecedor",
        )
        banco.add(empresa)
        banco.commit()
        empresa_id = empresa.id

    with Session(engine) as banco:
        carregada = banco.scalar(
            select(Empresa).where(Empresa.id == empresa_id)
        )

        assert carregada is not None
        assert carregada.razao_social == "Oficina Teste Ltda"
        assert carregada.documento == "TEST-DOC-0001"
        assert carregada.tipo_empresa == "fornecedor"
        assert carregada.avaliacao is None
