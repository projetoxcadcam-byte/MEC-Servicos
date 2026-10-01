from __future__ import annotations

import ast
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D8_CONTRATACAO.py"
REVISION = "MEC-SERVICOS-V0.1-D8-CONTRATACAO-2026-10-01"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D8_CONTRATACAO_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D8_CONTRATACAO.json"
BACKUP_ROOT = "_mec_backups"
EXPECTED_BASE_COMMIT = "43cb31b"
DB_PATH = Path("data/mec_servicos.db")

FILES = {'backend/app/models/contratacao.py': 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom decimal import Decimal\n\nfrom sqlalchemy import (\n    CheckConstraint,\n    DateTime,\n    ForeignKey,\n    Integer,\n    Numeric,\n    String,\n    Text,\n    UniqueConstraint,\n    func,\n)\nfrom sqlalchemy.orm import Mapped, mapped_column\n\nfrom backend.app.database.base import Base\n\n\nclass ContratacaoServico(Base):\n    __tablename__ = "contratacoes_servico"\n    __table_args__ = (\n        UniqueConstraint("solicitacao_id", name="uq_contratacao_solicitacao"),\n        UniqueConstraint("cotacao_id", name="uq_contratacao_cotacao"),\n        CheckConstraint(\n            "status IN (\'ativa\', \'cancelada\', \'encerrada\')",\n            name="ck_contratacoes_status",\n        ),\n        CheckConstraint("valor_total > 0", name="ck_contratacoes_valor_total"),\n        CheckConstraint("prazo_dias > 0", name="ck_contratacoes_prazo"),\n    )\n\n    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)\n    solicitacao_id: Mapped[int] = mapped_column(\n        ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    cotacao_id: Mapped[int] = mapped_column(\n        ForeignKey("cotacoes_fornecedor.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    empresa_cliente_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    empresa_fornecedora_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)\n    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)\n    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)\n    status: Mapped[str] = mapped_column(\n        String(16),\n        nullable=False,\n        default="ativa",\n        server_default="ativa",\n    )\n    criada_em: Mapped[datetime] = mapped_column(\n        DateTime(timezone=True),\n        server_default=func.now(),\n        nullable=False,\n    )\n    cancelada_em: Mapped[datetime | None] = mapped_column(\n        DateTime(timezone=True),\n        nullable=True,\n    )\n    encerrada_em: Mapped[datetime | None] = mapped_column(\n        DateTime(timezone=True),\n        nullable=True,\n    )\n', 'backend/app/schemas/contratacao.py': 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom decimal import Decimal\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\n\nclass ContratacaoCriacao(BaseModel):\n    cotacao_id: int = Field(gt=0)\n    empresa_cliente_id: int = Field(gt=0)\n    observacoes: str | None = Field(default=None, max_length=5000)\n\n\nclass ContratacaoCancelamento(BaseModel):\n    empresa_cliente_id: int = Field(gt=0)\n\n\nclass ContratacaoLeitura(BaseModel):\n    model_config = ConfigDict(from_attributes=True)\n\n    id: int\n    solicitacao_id: int\n    cotacao_id: int\n    empresa_cliente_id: int\n    empresa_fornecedora_id: int\n    valor_total: Decimal\n    prazo_dias: int\n    observacoes: str | None\n    status: str\n    criada_em: datetime\n    cancelada_em: datetime | None\n    encerrada_em: datetime | None\n', 'backend/app/repositories/contratacao.py': 'from __future__ import annotations\n\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.contratacao import ContratacaoServico\n\n\nclass RepositorioContratacao:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def criar(self, contratacao: ContratacaoServico) -> ContratacaoServico:\n        self.banco.add(contratacao)\n        self.banco.commit()\n        self.banco.refresh(contratacao)\n        return contratacao\n\n    def buscar_por_solicitacao(\n        self,\n        solicitacao_id: int,\n    ) -> ContratacaoServico | None:\n        consulta = select(ContratacaoServico).where(\n            ContratacaoServico.solicitacao_id == solicitacao_id,\n        )\n        return self.banco.scalar(consulta)\n', 'backend/app/services/contratacao.py': 'from __future__ import annotations\n\nfrom datetime import datetime, timezone\n\nfrom sqlalchemy.exc import IntegrityError\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.repositories.contratacao import RepositorioContratacao\nfrom backend.app.schemas.contratacao import ContratacaoCriacao\n\n\nclass ContratacaoSolicitacaoNaoEncontrada(LookupError):\n    pass\n\n\nclass ContratacaoCotacaoNaoEncontrada(LookupError):\n    pass\n\n\nclass ContratacaoCotacaoNaoAceita(ValueError):\n    pass\n\n\nclass ContratacaoSolicitacaoNaoAberta(ValueError):\n    pass\n\n\nclass ContratacaoEmpresaNaoPodeContratar(PermissionError):\n    pass\n\n\nclass ContratacaoJaExiste(ValueError):\n    pass\n\n\nclass ContratacaoNaoEncontrada(LookupError):\n    pass\n\n\nclass ContratacaoNaoAtiva(ValueError):\n    pass\n\n\nclass ServicoContratacao:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.repositorio = RepositorioContratacao(banco)\n\n    @staticmethod\n    def _agora_utc_sem_fuso() -> datetime:\n        return datetime.now(timezone.utc).replace(tzinfo=None)\n\n    def criar(\n        self,\n        solicitacao_id: int,\n        dados: ContratacaoCriacao,\n    ) -> ContratacaoServico:\n        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)\n        if solicitacao is None:\n            raise ContratacaoSolicitacaoNaoEncontrada(solicitacao_id)\n\n        if solicitacao.empresa_cliente_id != dados.empresa_cliente_id:\n            raise ContratacaoEmpresaNaoPodeContratar(dados.empresa_cliente_id)\n\n        if self.repositorio.buscar_por_solicitacao(solicitacao_id) is not None:\n            raise ContratacaoJaExiste(solicitacao_id)\n\n        if solicitacao.status != "aberta":\n            raise ContratacaoSolicitacaoNaoAberta(solicitacao_id)\n\n        cotacao = self.banco.get(CotacaoFornecedor, dados.cotacao_id)\n        if cotacao is None or cotacao.solicitacao_id != solicitacao_id:\n            raise ContratacaoCotacaoNaoEncontrada(dados.cotacao_id)\n\n        if cotacao.status != "aceita":\n            raise ContratacaoCotacaoNaoAceita(dados.cotacao_id)\n\n        if cotacao.decidida_por_empresa_id != dados.empresa_cliente_id:\n            raise ContratacaoEmpresaNaoPodeContratar(dados.empresa_cliente_id)\n\n        contratacao = ContratacaoServico(\n            solicitacao_id=solicitacao_id,\n            cotacao_id=cotacao.id,\n            empresa_cliente_id=solicitacao.empresa_cliente_id,\n            empresa_fornecedora_id=cotacao.empresa_fornecedora_id,\n            valor_total=cotacao.valor_total,\n            prazo_dias=cotacao.prazo_dias,\n            observacoes=dados.observacoes,\n            status="ativa",\n        )\n\n        solicitacao.status = "encerrada"\n\n        try:\n            return self.repositorio.criar(contratacao)\n        except IntegrityError as exc:\n            self.banco.rollback()\n            raise ContratacaoJaExiste(solicitacao_id) from exc\n\n    def obter(self, solicitacao_id: int) -> ContratacaoServico:\n        contratacao = self.repositorio.buscar_por_solicitacao(solicitacao_id)\n        if contratacao is None:\n            raise ContratacaoNaoEncontrada(solicitacao_id)\n        return contratacao\n\n    def cancelar(\n        self,\n        solicitacao_id: int,\n        empresa_cliente_id: int,\n    ) -> ContratacaoServico:\n        contratacao = self.repositorio.buscar_por_solicitacao(solicitacao_id)\n        if contratacao is None:\n            raise ContratacaoNaoEncontrada(solicitacao_id)\n\n        if contratacao.empresa_cliente_id != empresa_cliente_id:\n            raise ContratacaoEmpresaNaoPodeContratar(empresa_cliente_id)\n\n        if contratacao.status != "ativa":\n            raise ContratacaoNaoAtiva(contratacao.id)\n\n        contratacao.status = "cancelada"\n        contratacao.cancelada_em = self._agora_utc_sem_fuso()\n        self.banco.commit()\n        self.banco.refresh(contratacao)\n        return contratacao\n', 'backend/app/api/rotas/contratacoes.py': 'from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, HTTPException, status\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.contratacao import (\n    ContratacaoCancelamento,\n    ContratacaoCriacao,\n    ContratacaoLeitura,\n)\nfrom backend.app.services.contratacao import (\n    ContratacaoCotacaoNaoAceita,\n    ContratacaoCotacaoNaoEncontrada,\n    ContratacaoEmpresaNaoPodeContratar,\n    ContratacaoJaExiste,\n    ContratacaoNaoAtiva,\n    ContratacaoNaoEncontrada,\n    ContratacaoSolicitacaoNaoEncontrada,\n    ContratacaoSolicitacaoNaoAberta,\n    ServicoContratacao,\n)\n\nroteador = APIRouter(\n    prefix="/solicitacoes-servico",\n    tags=["contratações"],\n)\n\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\n\n\n@roteador.post(\n    "/{solicitacao_id}/contratacao",\n    response_model=ContratacaoLeitura,\n    status_code=status.HTTP_201_CREATED,\n)\ndef criar_contratacao(\n    solicitacao_id: int,\n    dados: ContratacaoCriacao,\n    banco: SessaoBanco,\n) -> ContratacaoLeitura:\n    try:\n        contratacao = ServicoContratacao(banco).criar(solicitacao_id, dados)\n    except ContratacaoSolicitacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="solicitacao_nao_encontrada",\n        ) from exc\n    except ContratacaoEmpresaNaoPodeContratar as exc:\n        raise HTTPException(\n            status_code=status.HTTP_403_FORBIDDEN,\n            detail="empresa_nao_e_cliente_da_solicitacao",\n        ) from exc\n    except ContratacaoJaExiste as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="contratacao_ja_cadastrada",\n        ) from exc\n    except ContratacaoSolicitacaoNaoAberta as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="solicitacao_nao_esta_aberta",\n        ) from exc\n    except ContratacaoCotacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="cotacao_nao_encontrada",\n        ) from exc\n    except ContratacaoCotacaoNaoAceita as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="cotacao_nao_esta_aceita",\n        ) from exc\n\n    return ContratacaoLeitura.model_validate(contratacao)\n\n\n@roteador.get(\n    "/{solicitacao_id}/contratacao",\n    response_model=ContratacaoLeitura,\n)\ndef obter_contratacao(\n    solicitacao_id: int,\n    banco: SessaoBanco,\n) -> ContratacaoLeitura:\n    try:\n        contratacao = ServicoContratacao(banco).obter(solicitacao_id)\n    except ContratacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="contratacao_nao_encontrada",\n        ) from exc\n\n    return ContratacaoLeitura.model_validate(contratacao)\n\n\n@roteador.post(\n    "/{solicitacao_id}/contratacao/cancelar",\n    response_model=ContratacaoLeitura,\n)\ndef cancelar_contratacao(\n    solicitacao_id: int,\n    dados: ContratacaoCancelamento,\n    banco: SessaoBanco,\n) -> ContratacaoLeitura:\n    try:\n        contratacao = ServicoContratacao(banco).cancelar(\n            solicitacao_id,\n            dados.empresa_cliente_id,\n        )\n    except ContratacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="contratacao_nao_encontrada",\n        ) from exc\n    except ContratacaoEmpresaNaoPodeContratar as exc:\n        raise HTTPException(\n            status_code=status.HTTP_403_FORBIDDEN,\n            detail="empresa_nao_e_cliente_da_solicitacao",\n        ) from exc\n    except ContratacaoNaoAtiva as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="contratacao_nao_esta_ativa",\n        ) from exc\n\n    return ContratacaoLeitura.model_validate(contratacao)\n', 'tests/test_contratacoes.py': 'from __future__ import annotations\n\nfrom decimal import Decimal\n\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import sessionmaker\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.capacidade import CapacidadeFornecedor\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.principal import app\n\n\ndef _cliente(banco, documento: str) -> Empresa:\n    item = Empresa(\n        razao_social="Cliente Teste D8",\n        documento=documento,\n        tipo_empresa="cliente",\n    )\n    banco.add(item)\n    banco.commit()\n    banco.refresh(item)\n    return item\n\n\ndef _fornecedor(banco, documento: str) -> Empresa:\n    item = Empresa(\n        razao_social="Fornecedor Teste D8",\n        documento=documento,\n        tipo_empresa="fornecedor",\n    )\n    banco.add(item)\n    banco.commit()\n    banco.refresh(item)\n    return item\n\n\ndef _base_cotacao_aceita(banco, sufixo: str):\n    cliente = _cliente(banco, f"1000000000{sufixo}1")\n    fornecedor = _fornecedor(banco, f"2000000000{sufixo}2")\n\n    processo = ProcessoFabricacao(\n        codigo=f"usinagem_cnc_d8_{sufixo}",\n        nome="Usinagem CNC D8",\n        descricao="Processo D8",\n    )\n    material = Material(\n        codigo=f"aluminio_6061_d8_{sufixo}",\n        nome="Aluminio 6061 D8",\n        familia="Aluminio",\n        especificacao="Liga 6061",\n    )\n    banco.add_all([processo, material])\n    banco.commit()\n    banco.refresh(processo)\n    banco.refresh(material)\n\n    capacidade = CapacidadeFornecedor(\n        empresa_id=fornecedor.id,\n        processo_id=processo.id,\n        dimensao_x_maxima_mm=Decimal("800"),\n        dimensao_y_maxima_mm=Decimal("500"),\n        dimensao_z_maxima_mm=Decimal("450"),\n        tolerancia_minima_mm=Decimal("0.0200"),\n        observacoes="Capacidade D8",\n    )\n    banco.add(capacidade)\n    banco.commit()\n\n    solicitacao = SolicitacaoServico(\n        empresa_cliente_id=cliente.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        dimensao_x_maxima_mm=Decimal("600"),\n        dimensao_y_maxima_mm=Decimal("400"),\n        dimensao_z_maxima_mm=Decimal("300"),\n        tolerancia_requerida_mm=Decimal("0.0200"),\n        quantidade=10,\n        observacoes="Solicitação D8",\n    )\n    banco.add(solicitacao)\n    banco.commit()\n    banco.refresh(solicitacao)\n\n    cotacao = CotacaoFornecedor(\n        solicitacao_id=solicitacao.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("12500.00"),\n        prazo_dias=15,\n        validade_dias=10,\n        observacoes="Cotação aceita D8",\n        status="aceita",\n        decidida_por_empresa_id=cliente.id,\n    )\n    banco.add(cotacao)\n    banco.commit()\n    banco.refresh(cotacao)\n\n    return cliente, fornecedor, solicitacao, cotacao\n\n\ndef _client():\n    engine = create_engine(\n        "sqlite:///:memory:",\n        connect_args={"check_same_thread": False},\n    )\n    Base.metadata.create_all(bind=engine)\n    SessionLocal = sessionmaker(bind=engine)\n    banco = SessionLocal()\n\n    def override_obter_banco():\n        yield banco\n\n    app.dependency_overrides[obter_banco] = override_obter_banco\n    return TestClient(app), banco, engine\n\n\ndef test_criar_contratacao_a_partir_de_cotacao_aceita():\n    cliente_http, banco, engine = _client()\n    try:\n        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "31")\n\n        resposta = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": cliente.id,\n                "observacoes": "Contratação D8",\n            },\n        )\n\n        assert resposta.status_code == 201\n        dados = resposta.json()\n        assert dados["status"] == "ativa"\n        assert dados["empresa_fornecedora_id"] == fornecedor.id\n        assert dados["valor_total"] == "12500.00"\n        assert dados["prazo_dias"] == 15\n\n        banco.refresh(solicitacao)\n        assert solicitacao.status == "encerrada"\n    finally:\n        app.dependency_overrides.clear()\n        banco.close()\n        engine.dispose()\n\n\ndef test_nao_cria_contratacao_de_cotacao_nao_aceita():\n    cliente_http, banco, engine = _client()\n    try:\n        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "32")\n        cotacao.status = "enviada"\n        banco.commit()\n\n        resposta = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": cliente.id,\n            },\n        )\n\n        assert resposta.status_code == 409\n        assert resposta.json()["detail"] == "cotacao_nao_esta_aceita"\n    finally:\n        app.dependency_overrides.clear()\n        banco.close()\n        engine.dispose()\n\n\ndef test_cliente_incorreto_nao_pode_contratar():\n    cliente_http, banco, engine = _client()\n    try:\n        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "33")\n        outro_cliente = _cliente(banco, "30000000000134")\n\n        resposta = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": outro_cliente.id,\n            },\n        )\n\n        assert resposta.status_code == 403\n        assert resposta.json()["detail"] == "empresa_nao_e_cliente_da_solicitacao"\n        assert banco.query(ContratacaoServico).count() == 0\n    finally:\n        app.dependency_overrides.clear()\n        banco.close()\n        engine.dispose()\n\n\ndef test_nao_permite_duas_contratacoes_para_mesma_solicitacao():\n    cliente_http, banco, engine = _client()\n    try:\n        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "34")\n\n        primeira = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": cliente.id,\n            },\n        )\n        assert primeira.status_code == 201\n\n        segunda = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": cliente.id,\n            },\n        )\n\n        assert segunda.status_code == 409\n        assert segunda.json()["detail"] == "contratacao_ja_cadastrada"\n    finally:\n        app.dependency_overrides.clear()\n        banco.close()\n        engine.dispose()\n\n\ndef test_obter_contratacao():\n    cliente_http, banco, engine = _client()\n    try:\n        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "35")\n\n        criada = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": cliente.id,\n            },\n        )\n        assert criada.status_code == 201\n\n        resposta = cliente_http.get(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n        )\n\n        assert resposta.status_code == 200\n        assert resposta.json()["cotacao_id"] == cotacao.id\n    finally:\n        app.dependency_overrides.clear()\n        banco.close()\n        engine.dispose()\n\n\ndef test_cancelar_contratacao():\n    cliente_http, banco, engine = _client()\n    try:\n        cliente, fornecedor, solicitacao, cotacao = _base_cotacao_aceita(banco, "36")\n\n        criada = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao",\n            json={\n                "cotacao_id": cotacao.id,\n                "empresa_cliente_id": cliente.id,\n            },\n        )\n        assert criada.status_code == 201\n\n        cancelada = cliente_http.post(\n            f"/api/v1/solicitacoes-servico/{solicitacao.id}/contratacao/cancelar",\n            json={"empresa_cliente_id": cliente.id},\n        )\n\n        assert cancelada.status_code == 200\n        assert cancelada.json()["status"] == "cancelada"\n        assert cancelada.json()["cancelada_em"] is not None\n    finally:\n        app.dependency_overrides.clear()\n        banco.close()\n        engine.dispose()\n'}

README_D8 = """## Estado

**V0.1 D8 — Contratação**

Nesta etapa foram estruturados:

- criação de uma contratação a partir de uma cotação aceita;
- validação de que a empresa é a cliente da solicitação;
- validação de que a cotação pertence à solicitação;
- validação de que a cotação está `aceita`;
- registro do fornecedor, valor e prazo contratados;
- uma única contratação por solicitação;
- encerramento comercial da solicitação após a contratação;
- consulta da contratação;
- cancelamento da contratação pelo cliente proprietário.

A contratação mantém o projeto independente do CGX Platform.

## Contratação

Uma contratação pode estar em:

- `ativa`
- `cancelada`
- `encerrada`

A contratação é criada somente a partir da cotação aceita correspondente à solicitação.

## O que ainda não faz parte do D8

- autenticação de usuários;
- negociação de preço;
- contraproposta;
- ordem de produção;
- pagamento;
- avaliação;
- ranking de fornecedores.
"""

README_ENDPOINTS = """- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/contratacao`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/contratacao/cancelar`
"""

DOCS_D8 = """

## D8 — Contratação

A contratação nasce de uma cotação aceita. O cliente proprietário da solicitação é validado, a cotação precisa pertencer à solicitação e estar no estado `aceita`. A criação registra fornecedor, valor e prazo da contratação e encerra comercialmente a solicitação. O contrato pode ser consultado e cancelado pelo cliente proprietário.
"""

def write_file(path: Path, content: str) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    normalized = content.rstrip() + "\n"
    if current == normalized:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8", newline="\n")
    return True


def backup_file(root: Path, path: Path, backup_dir: Path) -> bool:
    if not path.exists():
        return False
    target = backup_dir / path.relative_to(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return True


def validate_baseline(root: Path) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() != EXPECTED_BASE_COMMIT:
        raise RuntimeError(
            f"Commit-base inesperado: {result.stdout.strip()!r}; "
            f"esperado {EXPECTED_BASE_COMMIT!r}."
        )


def update_models_init(root: Path) -> bool:
    path = root / "backend/app/models/__init__.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from backend.app.models.contratacao import ContratacaoServico"
    if import_line not in text:
        lines = text.splitlines()
        all_index = next(
            (i for i, line in enumerate(lines) if line.startswith("__all__")),
            len(lines),
        )
        lines.insert(all_index, import_line)
        text = "\n".join(lines) + "\n"
    if '"ContratacaoServico"' not in text:
        lines = text.splitlines()
        close = next(
            (i for i, line in enumerate(lines) if line.strip() == "]"),
            None,
        )
        if close is None:
            raise RuntimeError("models/__init__.py não possui __all__.")
        lines.insert(close, '    "ContratacaoServico",')
        text = "\n".join(lines) + "\n"
    return write_file(path, text)


def update_router(root: Path) -> bool:
    path = root / "backend/app/api/roteador.py"
    text = path.read_text(encoding="utf-8")
    import_line = (
        "from backend.app.api.rotas.contratacoes "
        "import roteador as roteador_contratacoes"
    )
    include_line = "roteador_api.include_router(roteador_contratacoes)"
    lines = text.splitlines()
    if import_line not in text:
        lines.append(import_line)
    if include_line not in text:
        lines.append(include_line)
    return write_file(path, "\n".join(lines))


def update_readme(root: Path) -> bool:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    start = text.find("## Estado")
    cycle = text.find("## Ciclo da cotação")
    if start == -1 or cycle == -1:
        raise RuntimeError("README.md não possui a estrutura D7 esperada.")
    text = text[:start] + README_D8.rstrip() + "\n" + text[cycle:]
    text = text.replace("- contratação;\n", "")
    marker = "## Executar"
    if marker in text and README_ENDPOINTS.strip() not in text:
        text = text.replace(
            marker,
            "## Endpoints de contratação\n\n" + README_ENDPOINTS + "\n" + marker,
            1,
        )
    return write_file(path, text)


def update_docs(root: Path) -> bool:
    path = root / "docs/README.md"
    text = path.read_text(encoding="utf-8")
    if "## D8 — Contratação" not in text:
        text = text.rstrip() + DOCS_D8
    return write_file(path, text)


def migrate_database(db_path: Path) -> dict:
    if not db_path.exists():
        return {
            "database_changed": False,
            "database_already_migrated": False,
            "rows_preserved": 0,
        }

    conexao = sqlite3.connect(db_path)
    try:
        tabelas = {
            row[0]
            for row in conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "contratacoes_servico" in tabelas:
            count = conexao.execute(
                "SELECT COUNT(*) FROM contratacoes_servico"
            ).fetchone()[0]
            return {
                "database_changed": False,
                "database_already_migrated": True,
                "rows_preserved": count,
            }

        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.execute(
            """
            CREATE TABLE contratacoes_servico (
                id INTEGER PRIMARY KEY,
                solicitacao_id INTEGER NOT NULL UNIQUE,
                cotacao_id INTEGER NOT NULL UNIQUE,
                empresa_cliente_id INTEGER NOT NULL,
                empresa_fornecedora_id INTEGER NOT NULL,
                valor_total NUMERIC(14, 2) NOT NULL
                    CHECK (valor_total > 0),
                prazo_dias INTEGER NOT NULL
                    CHECK (prazo_dias > 0),
                observacoes TEXT,
                status VARCHAR(16) NOT NULL DEFAULT 'ativa'
                    CHECK (status IN ('ativa', 'cancelada', 'encerrada')),
                criada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                cancelada_em DATETIME,
                encerrada_em DATETIME,
                FOREIGN KEY (solicitacao_id)
                    REFERENCES solicitacoes_servico(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (cotacao_id)
                    REFERENCES cotacoes_fornecedor(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (empresa_cliente_id)
                    REFERENCES empresas(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (empresa_fornecedora_id)
                    REFERENCES empresas(id)
                    ON DELETE RESTRICT
            )
            """
        )
        conexao.execute(
            "CREATE INDEX IF NOT EXISTS ix_contratacoes_solicitacao_id "
            "ON contratacoes_servico (solicitacao_id)"
        )
        conexao.execute(
            "CREATE INDEX IF NOT EXISTS ix_contratacoes_cotacao_id "
            "ON contratacoes_servico (cotacao_id)"
        )
        conexao.execute(
            "CREATE INDEX IF NOT EXISTS ix_contratacoes_empresa_cliente_id "
            "ON contratacoes_servico (empresa_cliente_id)"
        )
        conexao.execute(
            "CREATE INDEX IF NOT EXISTS ix_contratacoes_empresa_fornecedora_id "
            "ON contratacoes_servico (empresa_fornecedora_id)"
        )
        conexao.commit()
        return {
            "database_changed": True,
            "database_already_migrated": False,
            "rows_preserved": 0,
        }
    finally:
        conexao.close()


def main() -> None:
    root = Path(__file__).resolve().parent
    if not (root / "backend").is_dir() or not (root / "tests").is_dir():
        raise RuntimeError("ROOT não parece ser a raiz do MEC-Serviços.")

    validate_baseline(root)

    backup_dir = (
        root / BACKUP_ROOT
        / f"V0_1_D8_CONTRATACAO_{datetime.now():%Y%m%d_%H%M%S}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_targets = [
        root / "backend/app/models/__init__.py",
        root / "backend/app/api/roteador.py",
        root / "README.md",
        root / "docs/README.md",
        root / DB_PATH,
    ]
    backed_up = sum(
        backup_file(root, path, backup_dir)
        for path in backup_targets
    )

    created = 0
    changed = 0

    for rel, content in FILES.items():
        path = root / rel
        existed = path.exists()
        if write_file(path, content):
            changed += 1
            if not existed:
                created += 1

    for changed_flag in (
        update_models_init(root),
        update_router(root),
        update_readme(root),
        update_docs(root),
    ):
        if changed_flag:
            changed += 1

    db = migrate_database(root / DB_PATH)

    ast_targets = list(FILES) + [
        "backend/app/models/__init__.py",
        "backend/app/api/roteador.py",
    ]
    ast_errors = []
    for rel in ast_targets:
        path = root / rel
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:
            ast_errors.append(f"{rel}: {exc}")

    if ast_errors:
        raise RuntimeError("AST inválida:\n" + "\n".join(ast_errors))

    payload = {
        "revision": REVISION,
        "files_ok": True,
        "ast_ok": True,
        "created": created,
        "changed": changed,
        "backed_up": backed_up,
        "backup_dir": str(backup_dir),
        "database": db,
        "contratacao_preparada": True,
        "solicitacao_encerrada_apos_contratacao": True,
    }

    report_lines = [
        PROJECT_LABEL,
        f"REVISION= {REVISION}",
        f"ROOT= {root}",
        "FILES_OK= True",
        "AST_OK= True",
        f"CREATED= {created}",
        f"CHANGED= {changed}",
        f"BACKED_UP= {backed_up}",
        f"DATABASE_CHANGED= {db['database_changed']}",
        f"DATABASE_ALREADY_MIGRATED= {db['database_already_migrated']}",
        f"ROWS_PRESERVED= {db['rows_preserved']}",
        f"BACKUP_DIR= {backup_dir}",
        f"REPORT= {root / REPORT_TXT}",
        f"JSON= {root / REPORT_JSON}",
        "D8_CONTRATACAO_APPLIED= True",
        "CONTRATACAO_PREPARADA= True",
        "CRIACAO_A_PARTIR_DE_COTACAO_ACEITA_PREPARADA= True",
        "ENCERRAMENTO_SOLICITACAO_PREPARADO= True",
        "CANCELAMENTO_PREPARADO= True",
    ]

    (root / REPORT_JSON).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / REPORT_TXT).write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )

    print("\n".join(report_lines))


if __name__ == "__main__":
    main()
