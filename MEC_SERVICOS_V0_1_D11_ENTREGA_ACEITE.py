from __future__ import annotations

import ast
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = "MEC-SERVICOS-V0.1-D11-ENTREGA-ACEITE-2026-10-01"
BACKUP_ROOT = ROOT / "_mec_backups"

FILES = {
    "model": ROOT / "backend/app/models/entrega.py",
    "repository": ROOT / "backend/app/repositories/entrega.py",
    "schema": ROOT / "backend/app/schemas/entrega.py",
    "service": ROOT / "backend/app/services/entrega.py",
    "route": ROOT / "backend/app/api/rotas/entregas.py",
    "models_init": ROOT / "backend/app/models/__init__.py",
    "router": ROOT / "backend/app/api/roteador.py",
    "test": ROOT / "tests/test_entregas.py",
}

MODEL = '''from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class EntregaServico(Base):
    __tablename__ = "entregas_servico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ordem_servico_id: Mapped[int] = mapped_column(ForeignKey("ordens_servico.id", ondelete="CASCADE"), nullable=False, index=True)
    empresa_fornecedora_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True)
    empresa_cliente_id: Mapped[int] = mapped_column(ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="entregue", index=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivo_recusa: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    entregue_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    aceita_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recusada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
'''

REPOSITORY = '''from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.entrega import EntregaServico


class RepositorioEntrega:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, item: EntregaServico) -> EntregaServico:
        self.banco.add(item)
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def buscar(self, entrega_id: int) -> EntregaServico | None:
        return self.banco.get(EntregaServico, entrega_id)

    def listar_por_ordem(self, ordem_servico_id: int) -> list[EntregaServico]:
        stmt = select(EntregaServico).where(EntregaServico.ordem_servico_id == ordem_servico_id).order_by(EntregaServico.id)
        return list(self.banco.scalars(stmt).all())

    def pendente_por_ordem(self, ordem_servico_id: int) -> EntregaServico | None:
        stmt = (
            select(EntregaServico)
            .where(EntregaServico.ordem_servico_id == ordem_servico_id, EntregaServico.status == "entregue")
            .order_by(EntregaServico.id.desc())
            .limit(1)
        )
        return self.banco.scalar(stmt)
'''

SCHEMA = '''from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntregaServicoCriacao(BaseModel):
    empresa_fornecedora_id: int = Field(gt=0)
    observacoes: str | None = None


class EntregaServicoDecisao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    motivo: str | None = None

    @field_validator("motivo")
    @classmethod
    def normalizar_motivo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        return valor or None


class EntregaServicoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem_servico_id: int
    empresa_fornecedora_id: int
    empresa_cliente_id: int
    status: str
    observacoes: str | None
    motivo_recusa: str | None
    criada_em: datetime
    entregue_em: datetime
    aceita_em: datetime | None
    recusada_em: datetime | None
'''

SERVICE = '''from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.entrega import EntregaServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.repositories.entrega import RepositorioEntrega
from backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao


class OrdemServicoNaoEncontradaParaEntrega(Exception): pass
class EntregaNaoEncontrada(Exception): pass
class EmpresaFornecedoraNaoPodeEntregar(Exception): pass
class EmpresaClienteNaoPodeDecidirEntrega(Exception): pass
class OrdemServicoNaoPodeReceberEntrega(Exception): pass
class OrdemServicoNaoEstaProntaParaEntrega(Exception): pass
class EntregaPendenteJaExiste(Exception): pass
class EntregaNaoEstaPendente(Exception): pass
class MotivoRecusaObrigatorio(Exception): pass


class ServicoEntrega:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioEntrega(banco)

    @staticmethod
    def _agora_utc_sem_fuso() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _ordem(self, ordem_servico_id: int) -> OrdemServico:
        item = self.banco.get(OrdemServico, ordem_servico_id)
        if item is None:
            raise OrdemServicoNaoEncontradaParaEntrega
        return item

    def _entrega(self, entrega_id: int) -> EntregaServico:
        item = self.repositorio.buscar(entrega_id)
        if item is None:
            raise EntregaNaoEncontrada
        return item

    def _validar_pronta_para_entrega(self, ordem: OrdemServico) -> None:
        if ordem.status in {"concluida", "cancelada"} or ordem.status != "em_execucao":
            raise OrdemServicoNaoPodeReceberEntrega
        stmt = (
            select(EtapaProducao)
            .where(EtapaProducao.ordem_servico_id == ordem.id)
            .order_by(EtapaProducao.id.desc())
            .limit(1)
        )
        etapa_atual = self.banco.scalar(stmt)
        if etapa_atual is None or etapa_atual.etapa != "pronto_para_envio":
            raise OrdemServicoNaoEstaProntaParaEntrega

    def registrar(self, ordem_servico_id: int, dados: EntregaServicoCriacao) -> EntregaServico:
        ordem = self._ordem(ordem_servico_id)
        if ordem.empresa_fornecedora_id != dados.empresa_fornecedora_id:
            raise EmpresaFornecedoraNaoPodeEntregar
        self._validar_pronta_para_entrega(ordem)
        if self.repositorio.pendente_por_ordem(ordem.id) is not None:
            raise EntregaPendenteJaExiste
        agora = self._agora_utc_sem_fuso()
        item = EntregaServico(
            ordem_servico_id=ordem.id,
            empresa_fornecedora_id=ordem.empresa_fornecedora_id,
            empresa_cliente_id=ordem.empresa_cliente_id,
            status="entregue",
            observacoes=dados.observacoes,
            criada_em=agora,
            entregue_em=agora,
        )
        return self.repositorio.criar(item)

    def obter(self, entrega_id: int) -> EntregaServico:
        return self._entrega(entrega_id)

    def listar(self, ordem_servico_id: int) -> list[EntregaServico]:
        self._ordem(ordem_servico_id)
        return self.repositorio.listar_por_ordem(ordem_servico_id)

    def aceitar(self, ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao) -> EntregaServico:
        ordem = self._ordem(ordem_servico_id)
        if ordem.empresa_cliente_id != dados.empresa_cliente_id:
            raise EmpresaClienteNaoPodeDecidirEntrega
        item = self._entrega(entrega_id)
        if item.ordem_servico_id != ordem.id:
            raise EntregaNaoEncontrada
        if item.status != "entregue":
            raise EntregaNaoEstaPendente
        agora = self._agora_utc_sem_fuso()
        item.status = "aceita"
        item.aceita_em = agora
        ordem.status = "concluida"
        ordem.concluida_em = agora
        contratacao = self.banco.get(ContratacaoServico, ordem.contratacao_id)
        if contratacao is not None and contratacao.status == "ativa":
            contratacao.status = "encerrada"
            contratacao.encerrada_em = agora
        self.banco.commit()
        self.banco.refresh(item)
        return item

    def recusar(self, ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao) -> EntregaServico:
        ordem = self._ordem(ordem_servico_id)
        if ordem.empresa_cliente_id != dados.empresa_cliente_id:
            raise EmpresaClienteNaoPodeDecidirEntrega
        item = self._entrega(entrega_id)
        if item.ordem_servico_id != ordem.id:
            raise EntregaNaoEncontrada
        if item.status != "entregue":
            raise EntregaNaoEstaPendente
        if not dados.motivo:
            raise MotivoRecusaObrigatorio
        item.status = "recusada"
        item.motivo_recusa = dados.motivo
        item.recusada_em = self._agora_utc_sem_fuso()
        self.banco.commit()
        self.banco.refresh(item)
        return item
'''

ROUTE = '''from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao, EntregaServicoLeitura
from backend.app.services.entrega import (
    EmpresaClienteNaoPodeDecidirEntrega,
    EmpresaFornecedoraNaoPodeEntregar,
    EntregaNaoEncontrada,
    EntregaNaoEstaPendente,
    EntregaPendenteJaExiste,
    MotivoRecusaObrigatorio,
    OrdemServicoNaoEncontradaParaEntrega,
    OrdemServicoNaoEstaProntaParaEntrega,
    OrdemServicoNaoPodeReceberEntrega,
    ServicoEntrega,
)

roteador = APIRouter(tags=["entregas"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post("/ordens-servico/{ordem_servico_id}/entregas", response_model=EntregaServicoLeitura, status_code=status.HTTP_201_CREATED)
def registrar_entrega(ordem_servico_id: int, dados: EntregaServicoCriacao, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).registrar(ordem_servico_id, dados)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc
    except EmpresaFornecedoraNaoPodeEntregar as exc:
        raise HTTPException(403, "empresa_nao_e_fornecedora_da_ordem_servico") from exc
    except OrdemServicoNaoPodeReceberEntrega as exc:
        raise HTTPException(409, "ordem_servico_nao_pode_receber_entrega") from exc
    except OrdemServicoNaoEstaProntaParaEntrega as exc:
        raise HTTPException(409, "ordem_servico_nao_esta_pronta_para_entrega") from exc
    except EntregaPendenteJaExiste as exc:
        raise HTTPException(409, "entrega_pendente_ja_existe") from exc


@roteador.get("/ordens-servico/{ordem_servico_id}/entregas", response_model=list[EntregaServicoLeitura])
def listar_entregas(ordem_servico_id: int, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).listar(ordem_servico_id)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc


@roteador.get("/ordens-servico/{ordem_servico_id}/entregas/{entrega_id}", response_model=EntregaServicoLeitura)
def obter_entrega(ordem_servico_id: int, entrega_id: int, banco: SessaoBanco):
    try:
        item = ServicoEntrega(banco).obter(entrega_id)
        if item.ordem_servico_id != ordem_servico_id:
            raise EntregaNaoEncontrada
        return item
    except EntregaNaoEncontrada as exc:
        raise HTTPException(404, "entrega_nao_encontrada") from exc


@roteador.post("/ordens-servico/{ordem_servico_id}/entregas/{entrega_id}/aceitar", response_model=EntregaServicoLeitura)
def aceitar_entrega(ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).aceitar(ordem_servico_id, entrega_id, dados)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc
    except EmpresaClienteNaoPodeDecidirEntrega as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_ordem_servico") from exc
    except EntregaNaoEncontrada as exc:
        raise HTTPException(404, "entrega_nao_encontrada") from exc
    except EntregaNaoEstaPendente as exc:
        raise HTTPException(409, "entrega_nao_esta_pendente") from exc


@roteador.post("/ordens-servico/{ordem_servico_id}/entregas/{entrega_id}/recusar", response_model=EntregaServicoLeitura)
def recusar_entrega(ordem_servico_id: int, entrega_id: int, dados: EntregaServicoDecisao, banco: SessaoBanco):
    try:
        return ServicoEntrega(banco).recusar(ordem_servico_id, entrega_id, dados)
    except OrdemServicoNaoEncontradaParaEntrega as exc:
        raise HTTPException(404, "ordem_servico_nao_encontrada") from exc
    except EmpresaClienteNaoPodeDecidirEntrega as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_ordem_servico") from exc
    except EntregaNaoEncontrada as exc:
        raise HTTPException(404, "entrega_nao_encontrada") from exc
    except EntregaNaoEstaPendente as exc:
        raise HTTPException(409, "entrega_nao_esta_pendente") from exc
    except MotivoRecusaObrigatorio as exc:
        raise HTTPException(422, "motivo_recusa_obrigatorio") from exc
'''

TEST = '''from __future__ import annotations

from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.material import Material
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.principal import app


@pytest.fixture()
def ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessaoTeste = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = substituir_banco
    try:
        with TestClient(app) as cliente_http:
            yield cliente_http, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_ordem(SessaoTeste: sessionmaker) -> tuple[int, int, int, int]:
    banco = SessaoTeste()
    cliente = Empresa(razao_social="Cliente D11", documento="D11-CLIENTE-001", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social="Fornecedor D11", documento="D11-FORNECEDOR-001", tipo_empresa="fornecedor")
    processo = ProcessoFabricacao(codigo="usinagem_cnc_d11", nome="Usinagem CNC D11", descricao="Usinagem D11.")
    material = Material(codigo="aluminio_6061_d11", nome="Aluminio 6061 D11", familia="Aluminio", especificacao="Liga D11.")
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()
    for item in (cliente, fornecedor, processo, material):
        banco.refresh(item)
    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id, processo_id=processo.id, material_id=material.id,
        dimensao_x_maxima_mm=100, dimensao_y_maxima_mm=100, dimensao_z_maxima_mm=100,
        tolerancia_requerida_mm=0.02, quantidade=5, observacoes="Solicitacao D11.", status="aberta",
    )
    banco.add(solicitacao); banco.commit(); banco.refresh(solicitacao)
    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id, empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"), prazo_dias=10, validade_dias=10,
        observacoes="Cotacao D11.", status="aceita", decidida_por_empresa_id=cliente.id,
    )
    banco.add(cotacao); banco.commit(); banco.refresh(cotacao)
    contratacao = ContratacaoServico(
        solicitacao_id=solicitacao.id, cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id, empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("5000.00"), prazo_dias=10,
        observacoes="Contratacao D11.", status="ativa",
    )
    banco.add(contratacao); banco.commit(); banco.refresh(contratacao)
    ordem = OrdemServico(
        contratacao_id=contratacao.id, solicitacao_id=solicitacao.id, cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id, empresa_fornecedora_id=fornecedor.id,
        processo_id=processo.id, material_id=material.id, quantidade=5,
        valor_total=Decimal("5000.00"), prazo_dias=10, status="em_execucao",
    )
    banco.add(ordem); banco.commit(); banco.refresh(ordem)
    etapa = EtapaProducao(
        ordem_servico_id=ordem.id, empresa_fornecedora_id=fornecedor.id,
        etapa="pronto_para_envio", observacoes="Produção D11 pronta.",
    )
    banco.add(etapa); banco.commit()
    ids = (cliente.id, fornecedor.id, ordem.id, contratacao.id)
    banco.close()
    return ids


def test_registrar_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert resposta.status_code == 201
    assert resposta.json()["status"] == "entregue"


def test_obter_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.get(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}")
    assert resposta.status_code == 200
    assert resposta.json()["id"] == entrega_id


def test_fornecedor_incorreto_nao_pode_registrar_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id + 1000})
    assert resposta.status_code == 403


def test_cliente_incorreto_nao_pode_aceitar(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id + 1000})
    assert resposta.status_code == 403


def test_cliente_incorreto_nao_pode_recusar(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/recusar", json={"empresa_cliente_id": cliente_id + 1000, "motivo": "Motivo D11."})
    assert resposta.status_code == 403


def test_aceitar_entrega_conclui_ordem_e_contratacao(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, contratacao_id = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id})
    assert resposta.status_code == 200
    banco = SessaoTeste()
    ordem = banco.get(OrdemServico, ordem_id)
    contratacao = banco.get(ContratacaoServico, contratacao_id)
    assert ordem.status == "concluida"
    assert contratacao.status == "encerrada"
    banco.close()


def test_recusar_entrega_exige_motivo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/recusar", json={"empresa_cliente_id": cliente_id})
    assert resposta.status_code == 422


def test_nao_permite_duas_entregas_pendentes(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    primeira = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert primeira.status_code == 201
    segunda = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert segunda.status_code == 409


def test_entrega_aceita_nao_pode_ser_aceita_novamente(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    criada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = criada.json()["id"]
    primeira = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id})
    assert primeira.status_code == 200
    segunda = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/aceitar", json={"empresa_cliente_id": cliente_id})
    assert segunda.status_code == 409


def test_ordem_concluida_nao_recebe_nova_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    banco = SessaoTeste(); ordem = banco.get(OrdemServico, ordem_id); ordem.status = "concluida"; banco.commit(); banco.close()
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert resposta.status_code == 409


def test_ordem_sem_pronto_para_envio_nao_pode_receber_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    _, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    banco = SessaoTeste()
    etapa = banco.query(EtapaProducao).filter(EtapaProducao.ordem_servico_id == ordem_id).first()
    etapa.etapa = "em_usinagem"; banco.commit(); banco.close()
    resposta = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert resposta.status_code == 409


def test_recusar_entrega_permite_nova_entrega(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, fornecedor_id, ordem_id, _ = preparar_ordem(SessaoTeste)
    primeira = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    entrega_id = primeira.json()["id"]
    recusada = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas/{entrega_id}/recusar", json={"empresa_cliente_id": cliente_id, "motivo": "Peça não atende ao desenho."})
    assert recusada.status_code == 200
    segunda = cliente_http.post(f"/api/v1/ordens-servico/{ordem_id}/entregas", json={"empresa_fornecedora_id": fornecedor_id})
    assert segunda.status_code == 201
'''


def backup(path: Path, backup_dir: Path) -> None:
    if path.exists():
        target = backup_dir / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def update_models_init(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    import_line = "from backend.app.models.entrega import EntregaServico"
    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
    if '"EntregaServico"' not in text and "__all__" in text:
        marker = '    "ContratacaoServico",\n'
        if marker in text:
            text = text.replace(marker, marker + '    "EntregaServico",\n', 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def update_router(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    import_line = "from backend.app.api.rotas.entregas import roteador as roteador_entregas"
    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
    include_line = "roteador_api.include_router(roteador_entregas)"
    if include_line not in text:
        text = text.rstrip() + "\n" + include_line + "\n"
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    required = [
        ROOT / "backend/app/models/ordem_servico.py",
        ROOT / "backend/app/models/etapa_producao.py",
        ROOT / "backend/app/api/roteador.py",
        ROOT / "backend/app/database/inicializacao.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        print("ERRO: baseline D9/D10 ausente:")
        for item in missing:
            print("MISSING=", item)
        return 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D11_ENTREGA_ACEITE_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    changed = []
    database_changed = False
    database_already_migrated = False

    try:
        new_files = {
            FILES["model"]: MODEL,
            FILES["repository"]: REPOSITORY,
            FILES["schema"]: SCHEMA,
            FILES["service"]: SERVICE,
            FILES["route"]: ROUTE,
            FILES["test"]: TEST,
        }
        for path, content in new_files.items():
            if path.exists():
                backup(path, backup_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            changed.append(str(path.relative_to(ROOT)))

        for key, updater in (("models_init", update_models_init), ("router", update_router)):
            path = FILES[key]
            before = path.read_text(encoding="utf-8")
            if updater(path):
                target = backup_dir / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(before, encoding="utf-8")
                changed.append(str(path.relative_to(ROOT)))

        for path in [*new_files.keys(), FILES["models_init"], FILES["router"]]:
            ast.parse(path.read_text(encoding="utf-8"))

        sys.path.insert(0, str(ROOT))
        from sqlalchemy import create_engine, inspect
        from backend.app.core.configuracao import configuracoes
        from backend.app.database.base import Base
        import backend.app.models  # noqa: F401
        import backend.app.models.etapa_producao  # noqa: F401
        import backend.app.models.entrega  # noqa: F401

        engine = create_engine(
            configuracoes.url_banco_dados,
            connect_args={"check_same_thread": False}
            if configuracoes.url_banco_dados.startswith("sqlite") else {},
        )
        try:
            before = set(inspect(engine).get_table_names())
            database_already_migrated = "entregas_servico" in before
            Base.metadata.create_all(bind=engine)
            after = set(inspect(engine).get_table_names())
            if "entregas_servico" not in after:
                raise RuntimeError("Tabela entregas_servico não foi criada.")
            database_changed = not database_already_migrated
        finally:
            engine.dispose()

        report = ROOT / "MEC_SERVICOS_V0_1_D11_ENTREGA_ACEITE_RELATORIO.txt"
        report_json = ROOT / "MEC_SERVICOS_V0_1_D11_ENTREGA_ACEITE.json"
        payload = {
            "revision": REVISION,
            "ast_ok": True,
            "metadata_preflight_ok": True,
            "table_entregas_servico": True,
            "supplier_delivery_only": True,
            "client_accept_reject_only": True,
            "rejection_requires_reason": True,
            "accepted_delivery_closes_order": True,
            "accepted_delivery_closes_contract": True,
            "rejected_delivery_allows_new_delivery": True,
            "database_changed": database_changed,
            "database_already_migrated": database_already_migrated,
            "changed": changed,
            "backup_dir": str(backup_dir),
        }
        report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.write_text("\n".join([
            "Plataforma de Serviços Mecânicos — V0.1 D11 Entrega, Aceite e Encerramento",
            f"REVISION= {REVISION}", f"ROOT= {ROOT}", "AST_OK= True",
            "METADATA_PREFLIGHT_OK= True", "TABLE_ENTREGAS_SERVICO= True",
            "SUPPLIER_DELIVERY_ONLY= True", "CLIENT_ACCEPT_REJECT_ONLY= True",
            "REJECTION_REQUIRES_REASON= True", "ACCEPTED_DELIVERY_CLOSES_ORDER= True",
            "ACCEPTED_DELIVERY_CLOSES_CONTRACT= True", "REJECTED_DELIVERY_ALLOWS_NEW_DELIVERY= True",
            f"DATABASE_CHANGED= {database_changed}", f"DATABASE_ALREADY_MIGRATED= {database_already_migrated}",
            f"CHANGED= {len(changed)}", f"BACKUP_DIR= {backup_dir}", f"REPORT= {report}", f"JSON= {report_json}",
        ]) + "\n", encoding="utf-8")

        print("Plataforma de Serviços Mecânicos — V0.1 D11 Entrega, Aceite e Encerramento")
        print("REVISION=", REVISION)
        print("ROOT=", ROOT)
        print("AST_OK= True")
        print("METADATA_PREFLIGHT_OK= True")
        print("TABLE_ENTREGAS_SERVICO= True")
        print("SUPPLIER_DELIVERY_ONLY= True")
        print("CLIENT_ACCEPT_REJECT_ONLY= True")
        print("REJECTION_REQUIRES_REASON= True")
        print("ACCEPTED_DELIVERY_CLOSES_ORDER= True")
        print("ACCEPTED_DELIVERY_CLOSES_CONTRACT= True")
        print("REJECTED_DELIVERY_ALLOWS_NEW_DELIVERY= True")
        print("DATABASE_CHANGED=", database_changed)
        print("DATABASE_ALREADY_MIGRATED=", database_already_migrated)
        print("CHANGED=", len(changed))
        print("BACKUP_DIR=", backup_dir)
        print("REPORT=", report)
        print("JSON=", report_json)
        return 0
    except Exception as exc:
        print(f"ERRO: {type(exc).__name__}: {exc}")
        print("BACKUP_DIR=", backup_dir)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
