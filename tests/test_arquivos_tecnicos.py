from __future__ import annotations

import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.principal import app
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico


@pytest.fixture()
def ambiente(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr(
        ServicoArquivoTecnico,
        "STORAGE_ROOT",
        tmp_path / "arquivos_tecnicos",
    )

    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = substituir_banco
    try:
        with TestClient(app) as test_client:
            yield test_client, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_solicitacao(SessaoTeste: sessionmaker) -> int:
    banco = SessaoTeste()

    cliente = Empresa(
        razao_social="Cliente D16",
        documento="D16-CLIENTE-001",
        tipo_empresa="cliente",
    )
    processo = ProcessoFabricacao(
        codigo="usinagem_cnc_d16",
        nome="Usinagem CNC D16",
        descricao="Processo D16.",
    )
    material = Material(
        codigo="aluminio_6061_d16",
        nome="Aluminio 6061 D16",
        familia="Aluminio",
        especificacao="Liga D16.",
    )

    banco.add_all([cliente, processo, material])
    banco.commit()

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=100,
        dimensao_y_maxima_mm=100,
        dimensao_z_maxima_mm=100,
        tolerancia_requerida_mm=0.02,
        quantidade=1,
        observacoes="Solicitacao D16.",
        status="aberta",
    )
    banco.add(solicitacao)
    banco.commit()

    solicitacao_id = solicitacao.id
    banco.close()
    return solicitacao_id


def test_upload_arquivo_permitido_registra_sha256_e_metadados(ambiente):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)
    conteudo = b"STEP-D16-CONTENT"

    resposta = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={
            "file": (
                "peca.step",
                conteudo,
                "application/step",
            )
        },
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["solicitacao_id"] == solicitacao_id
    assert corpo["nome_original"] == "peca.step"
    assert corpo["extensao"] == ".step"
    assert corpo["tamanho_bytes"] == len(conteudo)
    assert corpo["sha256"] == hashlib.sha256(conteudo).hexdigest()
    assert corpo["ativo"] is True

    banco = SessaoTeste()
    item = banco.scalar(
        select(ArquivoTecnico).where(ArquivoTecnico.id == corpo["id"])
    )
    assert item is not None
    assert Path(item.caminho_arquivo).is_file()
    assert Path(item.caminho_arquivo).read_bytes() == conteudo
    banco.close()


@pytest.mark.parametrize(
    "extensao",
    [".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf"],
)
def test_demais_extensoes_permitidas(ambiente, extensao):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={
            "file": (
                f"arquivo{extensao}",
                b"D16",
                "application/octet-stream",
            )
        },
    )

    assert resposta.status_code == 201
    assert resposta.json()["extensao"] == extensao


def test_extensao_nao_permitida_e_bloqueada(ambiente):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)

    resposta = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={"file": ("peca.stl", b"STL", "model/stl")},
    )

    assert resposta.status_code == 415
    assert resposta.json()["detail"] == "extensao_arquivo_nao_permitida"


def test_limite_de_tamanho_e_aplicado(
    ambiente,
    monkeypatch: pytest.MonkeyPatch,
):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)

    monkeypatch.setattr(
        ServicoArquivoTecnico,
        "MAX_FILE_SIZE_BYTES",
        8,
    )

    resposta = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={"file": ("grande.pdf", b"123456789", "application/pdf")},
    )

    assert resposta.status_code == 413
    assert resposta.json()["detail"] == "arquivo_excede_limite_de_tamanho"


def test_listar_e_baixar_arquivo(ambiente):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)
    conteudo = b"PDF-D16"

    upload = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={
            "file": (
                "desenho.pdf",
                conteudo,
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201
    arquivo_id = upload.json()["id"]

    lista = cliente_http.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos"
    )
    assert lista.status_code == 200
    assert len(lista.json()) == 1
    assert lista.json()[0]["id"] == arquivo_id

    metadata = cliente_http.get(f"/api/v1/arquivos-tecnicos/{arquivo_id}")
    assert metadata.status_code == 200
    assert metadata.json()["nome_original"] == "desenho.pdf"

    download = cliente_http.get(
        f"/api/v1/arquivos-tecnicos/{arquivo_id}/download"
    )
    assert download.status_code == 200
    assert download.content == conteudo
    assert "desenho.pdf" in download.headers.get("content-disposition", "")


def test_solicitacao_inexistente_e_bloqueada(ambiente):
    cliente_http, _ = ambiente

    resposta = cliente_http.post(
        "/api/v1/solicitacoes-servico/999999/arquivos-tecnicos",
        files={
            "file": (
                "peca.pdf",
                b"D16",
                "application/pdf",
            )
        },
    )

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "solicitacao_nao_encontrada"


def test_desvincular_preserva_historico_e_arquivo_fisico(ambiente):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)
    conteudo = b"HISTORICO-D16"

    upload = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={
            "file": (
                "historico.pdf",
                conteudo,
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201
    arquivo_id = upload.json()["id"]

    banco = SessaoTeste()
    item = banco.get(ArquivoTecnico, arquivo_id)
    assert item is not None
    caminho = Path(item.caminho_arquivo)
    banco.close()

    resposta = cliente_http.delete(
        f"/api/v1/arquivos-tecnicos/{arquivo_id}"
    )
    assert resposta.status_code == 204
    assert caminho.is_file()
    assert caminho.read_bytes() == conteudo

    banco = SessaoTeste()
    item = banco.get(ArquivoTecnico, arquivo_id)
    assert item is not None
    assert item.ativo is False
    banco.close()

    assert (
        cliente_http.get(
            f"/api/v1/arquivos-tecnicos/{arquivo_id}"
        ).status_code
        == 404
    )
    assert (
        cliente_http.get(
            f"/api/v1/arquivos-tecnicos/{arquivo_id}/download"
        ).status_code
        == 404
    )


def test_arquivo_desvinculado_nao_aparece_na_listagem(ambiente):
    cliente_http, SessaoTeste = ambiente
    solicitacao_id = preparar_solicitacao(SessaoTeste)

    upload = cliente_http.post(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos",
        files={
            "file": (
                "peca.pdf",
                b"D16",
                "application/pdf",
            )
        },
    )
    assert upload.status_code == 201

    arquivo_id = upload.json()["id"]
    assert (
        cliente_http.delete(
            f"/api/v1/arquivos-tecnicos/{arquivo_id}"
        ).status_code
        == 204
    )

    resposta = cliente_http.get(
        f"/api/v1/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos"
    )
    assert resposta.status_code == 200
    assert resposta.json() == []
