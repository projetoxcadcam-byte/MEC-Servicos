from __future__ import annotations

from pathlib import Path
from sqlalchemy import inspect, text
from backend.app.core.configuracao import configuracoes
from backend.app.database.base import Base
from backend.app.database.sessao import engine
from backend.app.models import (
    CapacidadeFornecedor, Empresa, Maquina, Material,
    MaterialFornecedor, ProcessoFabricacao,
)


def _garantir_pasta_sqlite() -> None:
    prefixo = "sqlite:///"
    if not configuracoes.url_banco_dados.startswith(prefixo):
        return
    caminho_bruto = configuracoes.url_banco_dados[len(prefixo):]
    if not caminho_bruto or caminho_bruto == ":memory:":
        return
    caminho = Path(caminho_bruto)
    if not caminho.is_absolute():
        caminho = Path.cwd() / caminho
    caminho.parent.mkdir(parents=True, exist_ok=True)


def _migrar_companies_para_empresas() -> None:
    if not configuracoes.url_banco_dados.startswith("sqlite"):
        return
    inspetor = inspect(engine)
    tabelas = set(inspetor.get_table_names())
    if "empresas" in tabelas and "companies" in tabelas:
        raise RuntimeError("Banco em estado ambíguo: as tabelas 'companies' e 'empresas' existem simultaneamente.")
    if "companies" not in tabelas:
        return
    colunas = {coluna["name"] for coluna in inspetor.get_columns("companies")}
    esperadas = {"id", "legal_name", "document", "company_type", "rating", "created_at", "updated_at"}
    ausentes = esperadas - colunas
    if ausentes:
        raise RuntimeError("A tabela legada 'companies' não possui as colunas esperadas: " + ", ".join(sorted(ausentes)))
    with engine.begin() as conexao:
        tipos_invalidos = conexao.execute(text("""
            SELECT DISTINCT company_type FROM companies
            WHERE company_type NOT IN ('client', 'supplier', 'both')
        """)).scalars().all()
        if tipos_invalidos:
            raise RuntimeError("A tabela legada 'companies' possui tipos de empresa desconhecidos: " + ", ".join(str(valor) for valor in tipos_invalidos))
        conexao.execute(text("""
            CREATE TABLE empresas (
                id INTEGER PRIMARY KEY,
                razao_social VARCHAR(200) NOT NULL,
                documento VARCHAR(32) NOT NULL UNIQUE,
                tipo_empresa VARCHAR(16) NOT NULL CHECK (tipo_empresa IN ('cliente', 'fornecedor', 'ambos')),
                avaliacao FLOAT,
                criado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                atualizado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ck_empresas_avaliacao CHECK (avaliacao IS NULL OR (avaliacao >= 0 AND avaliacao <= 5))
            )
        """))
        conexao.execute(text("""
            INSERT INTO empresas (id, razao_social, documento, tipo_empresa, avaliacao, criado_em, atualizado_em)
            SELECT id, legal_name, document,
                CASE company_type WHEN 'client' THEN 'cliente' WHEN 'supplier' THEN 'fornecedor' WHEN 'both' THEN 'ambos' END,
                rating, created_at, updated_at
            FROM companies
        """))
        conexao.execute(text("CREATE INDEX IF NOT EXISTS ix_empresas_razao_social ON empresas (razao_social)"))
        conexao.execute(text("DROP TABLE companies"))


def inicializar_banco() -> None:
    _garantir_pasta_sqlite()
    _migrar_companies_para_empresas()
    Base.metadata.create_all(bind=engine)
