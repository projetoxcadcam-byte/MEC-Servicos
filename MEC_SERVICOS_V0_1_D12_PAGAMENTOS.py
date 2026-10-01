from __future__ import annotations

import ast
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = "MEC-SERVICOS-V0.1-D12-PAGAMENTOS-2026-10-01"
EXPECTED_BASE_COMMIT = "c0367b3"
BACKUP_ROOT = ROOT / "_mec_backups"
DB_PATH = ROOT / "data/mec_servicos.db"
REPORT = ROOT / "MEC_SERVICOS_V0_1_D12_PAGAMENTOS_RELATORIO.txt"
REPORT_JSON = ROOT / "MEC_SERVICOS_V0_1_D12_PAGAMENTOS.json"

FILES = {
    "backend/app/models/pagamento.py": '''from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base


class PagamentoContratacao(Base):
    __tablename__ = "pagamentos_contratacao"
    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_pagamentos_valor"),
        CheckConstraint(
            "forma_pagamento IN ('pix', 'transferencia', 'boleto', 'cartao', 'dinheiro', 'outro')",
            name="ck_pagamentos_forma",
        ),
        CheckConstraint(
            "status IN ('confirmado', 'cancelado')",
            name="ck_pagamentos_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contratacao_id: Mapped[int] = mapped_column(
        ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    empresa_cliente_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    empresa_fornecedora_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="confirmado", server_default="confirmado", index=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    paga_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
''',
    "backend/app/repositories/pagamento.py": '''from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.pagamento import PagamentoContratacao


class RepositorioPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco

    def criar(self, pagamento: PagamentoContratacao) -> PagamentoContratacao:
        self.banco.add(pagamento)
        self.banco.commit()
        self.banco.refresh(pagamento)
        return pagamento

    def buscar(self, pagamento_id: int) -> PagamentoContratacao | None:
        return self.banco.get(PagamentoContratacao, pagamento_id)

    def listar_por_contratacao(self, contratacao_id: int) -> list[PagamentoContratacao]:
        stmt = (
            select(PagamentoContratacao)
            .where(PagamentoContratacao.contratacao_id == contratacao_id)
            .order_by(PagamentoContratacao.id)
        )
        return list(self.banco.scalars(stmt).all())
''',
    "backend/app/schemas/pagamento.py": '''from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PagamentoContratacaoCriacao(BaseModel):
    empresa_cliente_id: int = Field(gt=0)
    valor: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    forma_pagamento: str = Field(min_length=1, max_length=20)
    observacoes: str | None = Field(default=None, max_length=5000)


class PagamentoContratacaoCancelamento(BaseModel):
    empresa_cliente_id: int = Field(gt=0)


class PagamentoContratacaoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contratacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    valor: Decimal
    forma_pagamento: str
    status: str
    observacoes: str | None
    criada_em: datetime
    paga_em: datetime
    cancelada_em: datetime | None


class ResumoFinanceiroLeitura(BaseModel):
    contratacao_id: int
    valor_contratado: Decimal
    total_pago: Decimal
    saldo: Decimal
    status_pagamento: str
    pagamentos: list[PagamentoContratacaoLeitura]
''',
    "backend/app/services/pagamento.py": '''from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.pagamento import PagamentoContratacao
from backend.app.models.empresa import Empresa
from backend.app.repositories.pagamento import RepositorioPagamento
from backend.app.schemas.pagamento import PagamentoContratacaoCriacao

CENTAVO = Decimal("0.01")
FORMAS_PAGAMENTO = {"pix", "transferencia", "boleto", "cartao", "dinheiro", "outro"}


class PagamentoContratacaoNaoEncontrada(LookupError):
    pass


class PagamentoContratacaoEmpresaNaoEncontrada(LookupError):
    pass


class PagamentoEmpresaNaoPodePagar(PermissionError):
    pass


class PagamentoContratacaoNaoPodeReceber(ValueError):
    pass


class PagamentoFormaInvalida(ValueError):
    pass


class PagamentoAcimaDoSaldo(ValueError):
    pass


class PagamentoJaCancelado(ValueError):
    pass


class PagamentoNaoEncontrado(LookupError):
    pass


class PagamentoEmpresaNaoPodeCancelar(PermissionError):
    pass


class PagamentoNaoPodeSerCancelado(ValueError):
    pass


class ServicoPagamento:
    def __init__(self, banco: Session) -> None:
        self.banco = banco
        self.repositorio = RepositorioPagamento(banco)

    @staticmethod
    def _agora_utc_sem_fuso() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _moeda(valor: Decimal) -> Decimal:
        return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    def _contratacao(self, contratacao_id: int) -> ContratacaoServico:
        item = self.banco.get(ContratacaoServico, contratacao_id)
        if item is None:
            raise PagamentoContratacaoNaoEncontrada
        return item

    def _validar_empresa_cliente(self, contratacao: ContratacaoServico, empresa_cliente_id: int) -> None:
        if contratacao.empresa_cliente_id != empresa_cliente_id:
            raise PagamentoEmpresaNaoPodePagar
        if self.banco.get(Empresa, empresa_cliente_id) is None:
            raise PagamentoContratacaoEmpresaNaoEncontrada

    def _total_pago(self, contratacao_id: int) -> Decimal:
        pagamentos = self.repositorio.listar_por_contratacao(contratacao_id)
        total = sum(
            (self._moeda(item.valor) for item in pagamentos if item.status == "confirmado"),
            Decimal("0.00"),
        )
        return self._moeda(total)

    def resumo(self, contratacao_id: int) -> tuple[ContratacaoServico, Decimal, Decimal, str, list[PagamentoContratacao]]:
        contratacao = self._contratacao(contratacao_id)
        total_pago = self._total_pago(contratacao_id)
        valor_contratado = self._moeda(contratacao.valor_total)
        saldo = self._moeda(valor_contratado - total_pago)
        if contratacao.status == "cancelada":
            status = "cancelado"
        elif total_pago == Decimal("0.00"):
            status = "pendente"
        elif total_pago < valor_contratado:
            status = "parcial"
        else:
            status = "pago"
        return contratacao, valor_contratado, total_pago, status, self.repositorio.listar_por_contratacao(contratacao_id)

    def registrar(self, contratacao_id: int, dados: PagamentoContratacaoCriacao) -> PagamentoContratacao:
        contratacao = self._contratacao(contratacao_id)
        self._validar_empresa_cliente(contratacao, dados.empresa_cliente_id)

        if contratacao.status == "cancelada":
            raise PagamentoContratacaoNaoPodeReceber
        if dados.forma_pagamento not in FORMAS_PAGAMENTO:
            raise PagamentoFormaInvalida

        valor = self._moeda(dados.valor)
        total_pago = self._total_pago(contratacao_id)
        saldo = self._moeda(contratacao.valor_total - total_pago)
        if valor > saldo:
            raise PagamentoAcimaDoSaldo
        if saldo <= Decimal("0.00"):
            raise PagamentoContratacaoNaoPodeReceber

        agora = self._agora_utc_sem_fuso()
        pagamento = PagamentoContratacao(
            contratacao_id=contratacao.id,
            empresa_cliente_id=contratacao.empresa_cliente_id,
            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,
            valor=valor,
            forma_pagamento=dados.forma_pagamento,
            status="confirmado",
            observacoes=dados.observacoes,
            criada_em=agora,
            paga_em=agora,
        )
        return self.repositorio.criar(pagamento)

    def obter(self, pagamento_id: int) -> PagamentoContratacao:
        item = self.repositorio.buscar(pagamento_id)
        if item is None:
            raise PagamentoNaoEncontrado
        return item

    def listar(self, contratacao_id: int) -> list[PagamentoContratacao]:
        self._contratacao(contratacao_id)
        return self.repositorio.listar_por_contratacao(contratacao_id)

    def cancelar(self, pagamento_id: int, empresa_cliente_id: int) -> PagamentoContratacao:
        item = self.obter(pagamento_id)
        contratacao = self._contratacao(item.contratacao_id)
        self._validar_empresa_cliente(contratacao, empresa_cliente_id)
        if item.status == "cancelado":
            raise PagamentoJaCancelado
        if contratacao.status == "cancelada":
            raise PagamentoNaoPodeSerCancelado
        item.status = "cancelado"
        item.cancelada_em = self._agora_utc_sem_fuso()
        self.banco.commit()
        self.banco.refresh(item)
        return item
''',
    "backend/app/api/rotas/pagamentos.py": '''from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.schemas.pagamento import (
    PagamentoContratacaoCancelamento,
    PagamentoContratacaoCriacao,
    PagamentoContratacaoLeitura,
    ResumoFinanceiroLeitura,
)
from backend.app.services.pagamento import (
    PagamentoAcimaDoSaldo,
    PagamentoContratacaoEmpresaNaoEncontrada,
    PagamentoContratacaoNaoEncontrada,
    PagamentoContratacaoNaoPodeReceber,
    PagamentoEmpresaNaoPodeCancelar,
    PagamentoEmpresaNaoPodePagar,
    PagamentoFormaInvalida,
    PagamentoJaCancelado,
    PagamentoNaoEncontrado,
    PagamentoNaoPodeSerCancelado,
    ServicoPagamento,
)

roteador = APIRouter(prefix="/contratacoes", tags=["pagamentos"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]


def _erro(exc: Exception) -> None:
    raise exc


@roteador.post("/{contratacao_id}/pagamentos", response_model=PagamentoContratacaoLeitura, status_code=status.HTTP_201_CREATED)
def registrar_pagamento(contratacao_id: int, dados: PagamentoContratacaoCriacao, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).registrar(contratacao_id, dados)
    except PagamentoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc
    except PagamentoEmpresaNaoPodePagar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except PagamentoContratacaoEmpresaNaoEncontrada as exc:
        raise HTTPException(404, "empresa_cliente_nao_encontrada") from exc
    except PagamentoContratacaoNaoPodeReceber as exc:
        raise HTTPException(409, "contratacao_nao_pode_receber_pagamento") from exc
    except PagamentoFormaInvalida as exc:
        raise HTTPException(422, "forma_pagamento_invalida") from exc
    except PagamentoAcimaDoSaldo as exc:
        raise HTTPException(409, "pagamento_acima_do_saldo") from exc


@roteador.get("/{contratacao_id}/pagamentos", response_model=list[PagamentoContratacaoLeitura])
def listar_pagamentos(contratacao_id: int, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).listar(contratacao_id)
    except PagamentoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc


@roteador.get("/{contratacao_id}/financeiro", response_model=ResumoFinanceiroLeitura)
def resumo_financeiro(contratacao_id: int, banco: SessaoBanco):
    try:
        contratacao, valor_contratado, total_pago, status_pagamento, pagamentos = ServicoPagamento(banco).resumo(contratacao_id)
    except PagamentoContratacaoNaoEncontrada as exc:
        raise HTTPException(404, "contratacao_nao_encontrada") from exc
    return ResumoFinanceiroLeitura(
        contratacao_id=contratacao.id,
        valor_contratado=valor_contratado,
        total_pago=total_pago,
        saldo=valor_contratado - total_pago,
        status_pagamento=status_pagamento,
        pagamentos=pagamentos,
    )


@roteador.get("/pagamentos/{pagamento_id}", response_model=PagamentoContratacaoLeitura)
def obter_pagamento(pagamento_id: int, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).obter(pagamento_id)
    except PagamentoNaoEncontrado as exc:
        raise HTTPException(404, "pagamento_nao_encontrado") from exc


@roteador.post("/pagamentos/{pagamento_id}/cancelar", response_model=PagamentoContratacaoLeitura)
def cancelar_pagamento(pagamento_id: int, dados: PagamentoContratacaoCancelamento, banco: SessaoBanco):
    try:
        return ServicoPagamento(banco).cancelar(pagamento_id, dados.empresa_cliente_id)
    except PagamentoNaoEncontrado as exc:
        raise HTTPException(404, "pagamento_nao_encontrado") from exc
    except PagamentoEmpresaNaoPodeCancelar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except PagamentoEmpresaNaoPodePagar as exc:
        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc
    except PagamentoJaCancelado as exc:
        raise HTTPException(409, "pagamento_ja_cancelado") from exc
    except PagamentoNaoPodeSerCancelado as exc:
        raise HTTPException(409, "pagamento_nao_pode_ser_cancelado") from exc
''',
    "tests/test_pagamentos.py": '''from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.ordem_servico import OrdemServico
from backend.app.principal import app


@pytest.fixture()
def ambiente():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessaoTeste = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    def override():
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = override
    try:
        with TestClient(app) as cliente_http:
            yield cliente_http, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_contratacao(SessaoTeste):
    banco = SessaoTeste()
    cliente = Empresa(razao_social="Cliente D12", documento="D12-CLIENTE-001", tipo_empresa="cliente")
    fornecedor = Empresa(razao_social="Fornecedor D12", documento="D12-FORNECEDOR-001", tipo_empresa="fornecedor")
    processo = ProcessoFabricacao(codigo="usinagem_cnc_d12", nome="Usinagem CNC D12", descricao="Processo D12")
    material = Material(codigo="aluminio_6061_d12", nome="Aluminio 6061 D12", familia="Aluminio", especificacao="Liga 6061")
    banco.add_all([cliente, fornecedor, processo, material])
    banco.commit()
    for item in (cliente, fornecedor, processo, material):
        banco.refresh(item)

    solicitacao = SolicitacaoServico(
        empresa_cliente_id=cliente.id,
        processo_id=processo.id,
        material_id=material.id,
        dimensao_x_maxima_mm=Decimal("100"),
        dimensao_y_maxima_mm=Decimal("100"),
        dimensao_z_maxima_mm=Decimal("100"),
        tolerancia_requerida_mm=Decimal("0.0200"),
        quantidade=5,
        observacoes="Solicitacao D12",
        status="aberta",
    )
    banco.add(solicitacao)
    banco.commit()
    banco.refresh(solicitacao)

    cotacao = CotacaoFornecedor(
        solicitacao_id=solicitacao.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("10000.00"),
        prazo_dias=10,
        validade_dias=10,
        observacoes="Cotacao D12",
        status="aceita",
        decidida_por_empresa_id=cliente.id,
    )
    banco.add(cotacao)
    banco.commit()
    banco.refresh(cotacao)

    contratacao = ContratacaoServico(
        solicitacao_id=solicitacao.id,
        cotacao_id=cotacao.id,
        empresa_cliente_id=cliente.id,
        empresa_fornecedora_id=fornecedor.id,
        valor_total=Decimal("10000.00"),
        prazo_dias=10,
        observacoes="Contratacao D12",
        status="ativa",
    )
    banco.add(contratacao)
    banco.commit()
    banco.refresh(contratacao)
    ids = cliente.id, fornecedor.id, contratacao.id
    banco.close()
    return ids


def test_pagamento_integral(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "10000.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 201
    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.status_code == 200
    dados = resumo.json()
    assert dados["total_pago"] == "10000.00"
    assert dados["saldo"] == "0.00"
    assert dados["status_pagamento"] == "pago"


def test_pagamentos_parciais_calculam_saldo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    for valor in ("2500.00", "1500.00"):
        resposta = cliente_http.post(
            f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
            json={"empresa_cliente_id": cliente_id, "valor": valor, "forma_pagamento": "transferencia"},
        )
        assert resposta.status_code == 201
    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.json()["total_pago"] == "4000.00"
    assert resumo.json()["saldo"] == "6000.00"
    assert resumo.json()["status_pagamento"] == "parcial"


def test_nao_permite_pagamento_acima_do_saldo(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "10000.01", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "pagamento_acima_do_saldo"


def test_cliente_incorreto_nao_pode_pagar(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id + 1000, "valor": "100.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 403


def test_forma_pagamento_invalida(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "100.00", "forma_pagamento": "cheque"},
    )
    assert resposta.status_code == 422


def test_listar_pagamentos(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "100.00", "forma_pagamento": "pix"},
    )
    resposta = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/pagamentos")
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_cancelamento_reabre_saldo_financeiro(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    criada = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "1000.00", "forma_pagamento": "pix"},
    )
    assert criada.status_code == 201
    pagamento_id = criada.json()["id"]
    cancelada = cliente_http.post(
        f"/api/v1/contratacoes/pagamentos/{pagamento_id}/cancelar",
        json={"empresa_cliente_id": cliente_id},
    )
    assert cancelada.status_code == 200
    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")
    assert resumo.json()["total_pago"] == "0.00"
    assert resumo.json()["saldo"] == "10000.00"
    assert resumo.json()["status_pagamento"] == "pendente"


def test_contratacao_cancelada_nao_recebe_pagamento(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    banco = SessaoTeste()
    contratacao = banco.get(ContratacaoServico, contratacao_id)
    contratacao.status = "cancelada"
    banco.commit()
    banco.close()
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "100.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 409


def test_pagamento_negativo_rejeitado(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)
    resposta = cliente_http.post(
        f"/api/v1/contratacoes/{contratacao_id}/pagamentos",
        json={"empresa_cliente_id": cliente_id, "valor": "-1.00", "forma_pagamento": "pix"},
    )
    assert resposta.status_code == 422


def test_pagamento_inexistente(ambiente):
    cliente_http, _ = ambiente
    resposta = cliente_http.get("/api/v1/contratacoes/pagamentos/999999")
    assert resposta.status_code == 404
''',
}


def write_file(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == normalized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8", newline="\n")
    return True


def backup_file(path: Path, backup_dir: Path) -> bool:
    if not path.exists():
        return False
    target = backup_dir / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return True


def validate_baseline() -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    if head != EXPECTED_BASE_COMMIT:
        raise RuntimeError(f"Commit-base inesperado: {head!r}; esperado {EXPECTED_BASE_COMMIT!r}.")


def update_models_init() -> bool:
    path = ROOT / "backend/app/models/__init__.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from backend.app.models.pagamento import PagamentoContratacao"
    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
    if '"PagamentoContratacao"' not in text and "__all__" in text:
        marker = '    "EntregaServico",\n'
        if marker in text:
            text = text.replace(marker, marker + '    "PagamentoContratacao",\n', 1)
        else:
            close = next((i for i, line in enumerate(text.splitlines()) if line.strip() == "]"), None)
            if close is not None:
                lines = text.splitlines()
                lines.insert(close, '    "PagamentoContratacao",')
                text = "\n".join(lines) + "\n"
    return write_file(path, text)


def update_router() -> bool:
    path = ROOT / "backend/app/api/roteador.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from backend.app.api.rotas.pagamentos import roteador as roteador_pagamentos"
    include_line = "roteador_api.include_router(roteador_pagamentos)"
    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
    if include_line not in text:
        text = text.rstrip() + "\n" + include_line + "\n"
    return write_file(path, text)


def update_readme() -> bool:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    section = '''

## D12 — Pagamentos

Nesta etapa foi criado o núcleo financeiro da contratação:

- registro de pagamentos parciais ou integrais;
- cálculo de total pago e saldo;
- status financeiro `pendente`, `parcial`, `pago` e `cancelado`;
- formas de pagamento controladas;
- bloqueio de pagamento acima do saldo;
- bloqueio de pagamento para contratação cancelada;
- cancelamento de lançamento preservando o histórico;
- consulta do histórico de pagamentos;
- resumo financeiro por contratação.

O D12 registra o **livro financeiro interno da contratação**. Não integra gateway, banco ou adquirente externo nesta etapa.
'''
    if "## D12 — Pagamentos" not in text:
        text = text.rstrip() + section
    return write_file(path, text)


def update_docs() -> bool:
    path = ROOT / "docs/README.md"
    text = path.read_text(encoding="utf-8")
    section = '''

## D12 — Pagamentos

O módulo financeiro trabalha sobre a contratação existente e registra lançamentos confirmados ou cancelados. O saldo é derivado do valor contratado menos a soma dos pagamentos confirmados. O sistema impede valor acima do saldo e não permite novos pagamentos para contratação cancelada.

Nesta etapa não existe integração com PSP/gateway externo; o objetivo é estabelecer o domínio financeiro interno antes da integração de meios de pagamento reais.
'''
    if "## D12 — Pagamentos" not in text:
        text = text.rstrip() + section
    return write_file(path, text)


def migrate_database() -> dict:
    result = {"database_exists": DB_PATH.exists(), "database_changed": False, "database_already_migrated": False}
    if not DB_PATH.exists():
        return result
    con = sqlite3.connect(DB_PATH)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "pagamentos_contratacao" in tables:
            result["database_already_migrated"] = True
            result["rows_existing"] = con.execute("SELECT COUNT(*) FROM pagamentos_contratacao").fetchone()[0]
            return result
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("""
            CREATE TABLE pagamentos_contratacao (
                id INTEGER PRIMARY KEY,
                contratacao_id INTEGER NOT NULL,
                empresa_cliente_id INTEGER NOT NULL,
                empresa_fornecedora_id INTEGER NOT NULL,
                valor NUMERIC(14, 2) NOT NULL CHECK (valor > 0),
                forma_pagamento VARCHAR(20) NOT NULL CHECK (forma_pagamento IN ('pix','transferencia','boleto','cartao','dinheiro','outro')),
                status VARCHAR(16) NOT NULL DEFAULT 'confirmado' CHECK (status IN ('confirmado','cancelado')),
                observacoes TEXT,
                criada_em DATETIME NOT NULL,
                paga_em DATETIME NOT NULL,
                cancelada_em DATETIME,
                FOREIGN KEY (contratacao_id) REFERENCES contratacoes_servico(id) ON DELETE RESTRICT,
                FOREIGN KEY (empresa_cliente_id) REFERENCES empresas(id) ON DELETE RESTRICT,
                FOREIGN KEY (empresa_fornecedora_id) REFERENCES empresas(id) ON DELETE RESTRICT
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS ix_pagamentos_contratacao_contratacao_id ON pagamentos_contratacao (contratacao_id)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_pagamentos_contratacao_empresa_cliente_id ON pagamentos_contratacao (empresa_cliente_id)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_pagamentos_contratacao_empresa_fornecedora_id ON pagamentos_contratacao (empresa_fornecedora_id)")
        con.execute("CREATE INDEX IF NOT EXISTS ix_pagamentos_contratacao_status ON pagamentos_contratacao (status)")
        con.commit()
        result["database_changed"] = True
        result["rows_existing"] = 0
        return result
    finally:
        con.close()


def main() -> int:
    print("Plataforma de Serviços Mecânicos — V0.1 D12 Pagamentos")
    print("REVISION=", REVISION)
    print("ROOT=", ROOT)

    required = [
        ROOT / "backend/app/models/contratacao.py",
        ROOT / "backend/app/models/entrega.py",
        ROOT / "backend/app/api/roteador.py",
        ROOT / "backend/app/database/base.py",
        ROOT / "data/mec_servicos.db",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        print("BASELINE_MISSING=")
        for item in missing:
            print("MISSING=", item)
        return 1

    validate_baseline()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D12_PAGAMENTOS_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_targets = [ROOT / rel for rel in FILES]
    backup_targets += [
        ROOT / "backend/app/models/__init__.py",
        ROOT / "backend/app/api/roteador.py",
        ROOT / "README.md",
        ROOT / "docs/README.md",
        DB_PATH,
    ]
    backed_up = sum(backup_file(path, backup_dir) for path in backup_targets)

    changed = []
    for rel, content in FILES.items():
        path = ROOT / rel
        if write_file(path, content):
            changed.append(rel)

    if update_models_init():
        changed.append("backend/app/models/__init__.py")
    if update_router():
        changed.append("backend/app/api/roteador.py")
    if update_readme():
        changed.append("README.md")
    if update_docs():
        changed.append("docs/README.md")

    ast_errors = []
    for rel in list(FILES) + ["backend/app/models/__init__.py", "backend/app/api/roteador.py"]:
        try:
            ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)
        except Exception as exc:
            ast_errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    if ast_errors:
        raise RuntimeError("AST_INVALIDA\n" + "\n".join(ast_errors))

    # Migra primeiro a base existente; depois apenas verifica pelo ORM que a tabela
    # está compatível com o modelo. Isso evita declarar uma migração como "já feita"
    # depois de create_all() tê-la criado durante o próprio diagnóstico.
    db = migrate_database()

    import sys
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import create_engine, inspect
    from backend.app.core.configuracao import configuracoes
    import backend.app.models  # noqa: F401
    import backend.app.models.pagamento  # noqa: F401

    engine = create_engine(
        configuracoes.url_banco_dados,
        connect_args={"check_same_thread": False} if configuracoes.url_banco_dados.startswith("sqlite") else {},
    )
    try:
        tables = set(inspect(engine).get_table_names())
        if "pagamentos_contratacao" not in tables:
            raise RuntimeError("Tabela pagamentos_contratacao não foi criada pela migração.")
        orm_table_created = bool(db.get("database_changed"))
    finally:
        engine.dispose()

    payload = {
        "revision": REVISION,
        "head_expected": EXPECTED_BASE_COMMIT,
        "ast_ok": True,
        "table_pagamentos_contratacao": True,
        "orm_table_created": orm_table_created,
        "database": db,
        "backup_dir": str(backup_dir),
        "backed_up": backed_up,
        "changed_files": changed,
        "internal_financial_ledger_only": True,
        "partial_payments": True,
        "balance_calculation": True,
        "overpayment_blocked": True,
        "cancelled_contract_payment_blocked": True,
        "payment_cancellation_preserves_history": True,
        "external_gateway_integration": False,
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("\n".join([
        "Plataforma de Serviços Mecânicos — V0.1 D12 Pagamentos",
        f"REVISION= {REVISION}",
        f"ROOT= {ROOT}",
        f"HEAD_EXPECTED= {EXPECTED_BASE_COMMIT}",
        "AST_OK= True",
        "TABLE_PAGAMENTOS_CONTRATACAO= True",
        f"ORM_TABLE_CREATED= {orm_table_created}",
        f"DATABASE_CHANGED= {db.get('database_changed')}",
        f"DATABASE_ALREADY_MIGRATED= {db.get('database_already_migrated')}",
        f"BACKED_UP= {backed_up}",
        f"CHANGED_FILES= {len(changed)}",
        "INTERNAL_FINANCIAL_LEDGER_ONLY= True",
        "PARTIAL_PAYMENTS= True",
        "BALANCE_CALCULATION= True",
        "OVERPAYMENT_BLOCKED= True",
        "CANCELLED_CONTRACT_PAYMENT_BLOCKED= True",
        "PAYMENT_CANCELLATION_PRESERVES_HISTORY= True",
        "EXTERNAL_GATEWAY_INTEGRATION= False",
        f"BACKUP_DIR= {backup_dir}",
        f"REPORT= {REPORT}",
        f"JSON= {REPORT_JSON}",
    ]) + "\n", encoding="utf-8")

    print("AST_OK= True")
    print("TABLE_PAGAMENTOS_CONTRATACAO= True")
    print("ORM_TABLE_CREATED=", orm_table_created)
    print("DATABASE_CHANGED=", db.get("database_changed"))
    print("DATABASE_ALREADY_MIGRATED=", db.get("database_already_migrated"))
    print("BACKED_UP=", backed_up)
    print("CHANGED_FILES=", len(changed))
    print("INTERNAL_FINANCIAL_LEDGER_ONLY= True")
    print("PARTIAL_PAYMENTS= True")
    print("BALANCE_CALCULATION= True")
    print("OVERPAYMENT_BLOCKED= True")
    print("CANCELLED_CONTRACT_PAYMENT_BLOCKED= True")
    print("PAYMENT_CANCELLATION_PRESERVES_HISTORY= True")
    print("EXTERNAL_GATEWAY_INTEGRATION= False")
    print("BACKUP_DIR=", backup_dir)
    print("REPORT=", REPORT)
    print("JSON=", REPORT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
