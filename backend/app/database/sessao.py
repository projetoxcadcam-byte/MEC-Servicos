from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.configuracao import configuracoes


def _argumentos_engine(url_banco: str) -> dict:
    if url_banco.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(
    configuracoes.url_banco_dados,
    pool_pre_ping=True,
    **_argumentos_engine(configuracoes.url_banco_dados),
)

SessaoLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def obter_banco() -> Generator[Session, None, None]:
    banco = SessaoLocal()
    try:
        yield banco
    finally:
        banco.close()
