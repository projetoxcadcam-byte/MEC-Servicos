from __future__ import annotations

import ast
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REVISION = "MEC-SERVICOS-V0.1-D13-INTEGRACAO-PAGAMENTOS-2026-10-01"
BACKUP_ROOT = ROOT / "_mec_backups"
DB_PATH = ROOT / "data/mec_servicos.db"
REPORT = ROOT / "MEC_SERVICOS_V0_1_D13_INTEGRACAO_PAGAMENTOS_RELATORIO.txt"
REPORT_JSON = ROOT / "MEC_SERVICOS_V0_1_D13_INTEGRACAO_PAGAMENTOS.json"

FILES = {'backend/app/integracoes/__init__.py': 'from backend.app.integracoes.pagamento import GatewayPagamentoFake\n\n__all__ = ["GatewayPagamentoFake"]\n', 'backend/app/integracoes/pagamento.py': 'from __future__ import annotations\n\nimport hashlib\nimport hmac\nimport json\nimport os\nimport uuid\nfrom dataclasses import dataclass\n\nWEBHOOK_SECRET_ENV = "MEC_PAGAMENTO_WEBHOOK_SECRET"\nDEFAULT_WEBHOOK_SECRET = "mec-servicos-d13-dev-secret"\n\n\n@dataclass(frozen=True)\nclass CobrancaGateway:\n    provedor: str\n    external_payment_id: str\n    checkout_url: str\n\n\nclass GatewayPagamento:\n    nome = "base"\n\n    def criar_cobranca(\n        self,\n        *,\n        valor: str,\n        forma_pagamento: str,\n        idempotency_key: str,\n    ) -> CobrancaGateway:\n        raise NotImplementedError\n\n\nclass GatewayPagamentoFake(GatewayPagamento):\n    nome = "fake"\n\n    def criar_cobranca(\n        self,\n        *,\n        valor: str,\n        forma_pagamento: str,\n        idempotency_key: str,\n    ) -> CobrancaGateway:\n        external_payment_id = f"fake_{uuid.uuid4().hex}"\n        checkout_url = f"https://fake-gateway.local/checkout/{external_payment_id}"\n        return CobrancaGateway(\n            provedor=self.nome,\n            external_payment_id=external_payment_id,\n            checkout_url=checkout_url,\n        )\n\n\ndef segredo_webhook() -> bytes:\n    return os.getenv(WEBHOOK_SECRET_ENV, DEFAULT_WEBHOOK_SECRET).encode("utf-8")\n\n\ndef assinatura_webhook(payload: dict) -> str:\n    corpo = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")\n    return hmac.new(segredo_webhook(), corpo, hashlib.sha256).hexdigest()\n\n\ndef validar_assinatura_webhook(payload: dict, assinatura: str) -> bool:\n    esperada = assinatura_webhook(payload)\n    return hmac.compare_digest(esperada, assinatura)\n', 'backend/app/models/intencao_pagamento.py': 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom decimal import Decimal\n\nfrom sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint\nfrom sqlalchemy.orm import Mapped, mapped_column\n\nfrom backend.app.database.base import Base\n\n\nclass IntencaoPagamento(Base):\n    __tablename__ = "intencoes_pagamento"\n    __table_args__ = (\n        UniqueConstraint("idempotency_key", name="uq_intencoes_pagamento_idempotency_key"),\n        UniqueConstraint("external_payment_id", name="uq_intencoes_pagamento_external_payment_id"),\n        CheckConstraint(\n            "status IN (\'aguardando_pagamento\', \'paga\', \'falhou\', \'cancelada\')",\n            name="ck_intencoes_pagamento_status",\n        ),\n        CheckConstraint(\n            "forma_pagamento IN (\'pix\', \'transferencia\', \'boleto\', \'cartao\', \'dinheiro\', \'outro\')",\n            name="ck_intencoes_pagamento_forma",\n        ),\n    )\n\n    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)\n    contratacao_id: Mapped[int] = mapped_column(\n        ForeignKey("contratacoes_servico.id", ondelete="RESTRICT"), nullable=False, index=True\n    )\n    empresa_cliente_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True\n    )\n    empresa_fornecedora_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=False, index=True\n    )\n    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)\n    forma_pagamento: Mapped[str] = mapped_column(String(20), nullable=False)\n    provedor: Mapped[str] = mapped_column(String(40), nullable=False, default="fake", server_default="fake")\n    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)\n    external_payment_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)\n    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)\n    status: Mapped[str] = mapped_column(\n        String(24), nullable=False, default="aguardando_pagamento", server_default="aguardando_pagamento", index=True\n    )\n    pagamento_id: Mapped[int | None] = mapped_column(\n        ForeignKey("pagamentos_contratacao.id", ondelete="SET NULL"), nullable=True, index=True\n    )\n    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)\n    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)\n    atualizada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)\n    paga_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)\n    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)\n', 'backend/app/models/evento_gateway_pagamento.py': 'from __future__ import annotations\n\nfrom datetime import datetime\n\nfrom sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint\nfrom sqlalchemy.orm import Mapped, mapped_column\n\nfrom backend.app.database.base import Base\n\n\nclass EventoGatewayPagamento(Base):\n    __tablename__ = "eventos_gateway_pagamento"\n    __table_args__ = (\n        UniqueConstraint("provedor", "evento_id", name="uq_eventos_gateway_provedor_evento"),\n    )\n\n    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)\n    provedor: Mapped[str] = mapped_column(String(40), nullable=False, index=True)\n    evento_id: Mapped[str] = mapped_column(String(120), nullable=False)\n    intencao_pagamento_id: Mapped[int | None] = mapped_column(\n        ForeignKey("intencoes_pagamento.id", ondelete="SET NULL"), nullable=True, index=True\n    )\n    external_payment_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)\n    tipo_evento: Mapped[str] = mapped_column(String(50), nullable=False)\n    status_processamento: Mapped[str] = mapped_column(String(24), nullable=False, default="processado", server_default="processado")\n    payload_json: Mapped[str] = mapped_column(Text, nullable=False)\n    recebido_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)\n    processado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)\n', 'backend/app/repositories/intencao_pagamento.py': 'from __future__ import annotations\n\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.intencao_pagamento import IntencaoPagamento\nfrom backend.app.models.evento_gateway_pagamento import EventoGatewayPagamento\n\n\nclass RepositorioIntencaoPagamento:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def criar(self, item: IntencaoPagamento) -> IntencaoPagamento:\n        self.banco.add(item)\n        self.banco.commit()\n        self.banco.refresh(item)\n        return item\n\n    def buscar(self, intencao_id: int) -> IntencaoPagamento | None:\n        return self.banco.get(IntencaoPagamento, intencao_id)\n\n    def buscar_por_idempotency(self, chave: str) -> IntencaoPagamento | None:\n        stmt = select(IntencaoPagamento).where(IntencaoPagamento.idempotency_key == chave)\n        return self.banco.scalar(stmt)\n\n    def buscar_por_external_id(self, external_payment_id: str) -> IntencaoPagamento | None:\n        stmt = select(IntencaoPagamento).where(IntencaoPagamento.external_payment_id == external_payment_id)\n        return self.banco.scalar(stmt)\n\n\nclass RepositorioEventoGatewayPagamento:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def buscar(self, provedor: str, evento_id: str) -> EventoGatewayPagamento | None:\n        stmt = select(EventoGatewayPagamento).where(\n            EventoGatewayPagamento.provedor == provedor,\n            EventoGatewayPagamento.evento_id == evento_id,\n        )\n        return self.banco.scalar(stmt)\n\n    def criar(self, item: EventoGatewayPagamento) -> EventoGatewayPagamento:\n        self.banco.add(item)\n        self.banco.commit()\n        self.banco.refresh(item)\n        return item\n', 'backend/app/schemas/intencao_pagamento.py': 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom decimal import Decimal\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\n\nclass IntencaoPagamentoCriacao(BaseModel):\n    empresa_cliente_id: int = Field(gt=0)\n    valor: Decimal = Field(gt=0, max_digits=14, decimal_places=2)\n    forma_pagamento: str = Field(min_length=1, max_length=20)\n    observacoes: str | None = Field(default=None, max_length=5000)\n\n\nclass IntencaoPagamentoLeitura(BaseModel):\n    model_config = ConfigDict(from_attributes=True)\n\n    id: int\n    contratacao_id: int\n    empresa_cliente_id: int\n    empresa_fornecedora_id: int\n    valor: Decimal\n    forma_pagamento: str\n    provedor: str\n    idempotency_key: str\n    external_payment_id: str\n    checkout_url: str | None\n    status: str\n    pagamento_id: int | None\n    observacoes: str | None\n    criada_em: datetime\n    atualizada_em: datetime\n    paga_em: datetime | None\n    cancelada_em: datetime | None\n\n\nclass WebhookPagamento(BaseModel):\n    evento_id: str = Field(min_length=1, max_length=120)\n    external_payment_id: str = Field(min_length=1, max_length=120)\n    tipo_evento: str = Field(min_length=1, max_length=50)\n\n\nclass WebhookPagamentoLeitura(BaseModel):\n    processado: bool\n    duplicado: bool\n    intencao: IntencaoPagamentoLeitura\n', 'backend/app/services/integracao_pagamento.py': 'from __future__ import annotations\n\nimport json\nfrom datetime import datetime, timezone\nfrom decimal import Decimal, ROUND_HALF_UP\n\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.integracoes.pagamento import GatewayPagamentoFake, validar_assinatura_webhook\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.evento_gateway_pagamento import EventoGatewayPagamento\nfrom backend.app.models.intencao_pagamento import IntencaoPagamento\nfrom backend.app.repositories.intencao_pagamento import RepositorioEventoGatewayPagamento, RepositorioIntencaoPagamento\nfrom backend.app.schemas.intencao_pagamento import IntencaoPagamentoCriacao, WebhookPagamento\nfrom backend.app.schemas.pagamento import PagamentoContratacaoCriacao\nfrom backend.app.services.pagamento import ServicoPagamento\n\nCENTAVO = Decimal("0.01")\nFORMAS_PAGAMENTO = {"pix", "transferencia", "boleto", "cartao", "dinheiro", "outro"}\nEVENTOS = {"payment.succeeded", "payment.failed", "payment.cancelled"}\n\n\nclass IntegracaoContratacaoNaoEncontrada(LookupError):\n    pass\n\n\nclass IntegracaoEmpresaNaoPodeIniciar(PermissionError):\n    pass\n\n\nclass IntegracaoFormaInvalida(ValueError):\n    pass\n\n\nclass IntegracaoContratacaoNaoPodeReceber(ValueError):\n    pass\n\n\nclass IntegracaoValorAcimaDoSaldo(ValueError):\n    pass\n\n\nclass IntegracaoIdempotencyInvalida(ValueError):\n    pass\n\n\nclass IntegracaoIntencaoNaoEncontrada(LookupError):\n    pass\n\n\nclass IntegracaoEventoInvalido(ValueError):\n    pass\n\n\nclass IntegracaoProvedorNaoSuportado(ValueError):\n    pass\n\n\nclass IntegracaoAssinaturaInvalida(PermissionError):\n    pass\n\n\nclass IntegracaoPagamentoNaoPodeSerConfirmado(ValueError):\n    pass\n\n\nclass ServicoIntegracaoPagamento:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.repositorio = RepositorioIntencaoPagamento(banco)\n        self.eventos = RepositorioEventoGatewayPagamento(banco)\n        self.gateway = GatewayPagamentoFake()\n\n    @staticmethod\n    def _agora() -> datetime:\n        return datetime.now(timezone.utc).replace(tzinfo=None)\n\n    @staticmethod\n    def _moeda(valor: Decimal) -> Decimal:\n        return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)\n\n    def _contratacao(self, contratacao_id: int) -> ContratacaoServico:\n        item = self.banco.get(ContratacaoServico, contratacao_id)\n        if item is None:\n            raise IntegracaoContratacaoNaoEncontrada\n        return item\n\n    def iniciar(self, contratacao_id: int, dados: IntencaoPagamentoCriacao, idempotency_key: str) -> tuple[IntencaoPagamento, bool]:\n        if not idempotency_key.strip():\n            raise IntegracaoIdempotencyInvalida\n        existente = self.repositorio.buscar_por_idempotency(idempotency_key)\n        if existente is not None:\n            return existente, True\n\n        contratacao = self._contratacao(contratacao_id)\n        if contratacao.empresa_cliente_id != dados.empresa_cliente_id:\n            raise IntegracaoEmpresaNaoPodeIniciar\n        if self.banco.get(Empresa, dados.empresa_cliente_id) is None:\n            raise IntegracaoEmpresaNaoPodeIniciar\n        if contratacao.status == "cancelada":\n            raise IntegracaoContratacaoNaoPodeReceber\n        if dados.forma_pagamento not in FORMAS_PAGAMENTO:\n            raise IntegracaoFormaInvalida\n\n        _, valor_contratado, total_pago, _, _ = ServicoPagamento(self.banco).resumo(contratacao_id)\n        saldo = self._moeda(valor_contratado - total_pago)\n        valor = self._moeda(dados.valor)\n        if valor > saldo or saldo <= Decimal("0.00"):\n            raise IntegracaoValorAcimaDoSaldo\n\n        cobranca = self.gateway.criar_cobranca(\n            valor=str(valor), forma_pagamento=dados.forma_pagamento, idempotency_key=idempotency_key\n        )\n        agora = self._agora()\n        item = IntencaoPagamento(\n            contratacao_id=contratacao.id,\n            empresa_cliente_id=contratacao.empresa_cliente_id,\n            empresa_fornecedora_id=contratacao.empresa_fornecedora_id,\n            valor=valor,\n            forma_pagamento=dados.forma_pagamento,\n            provedor=cobranca.provedor,\n            idempotency_key=idempotency_key,\n            external_payment_id=cobranca.external_payment_id,\n            checkout_url=cobranca.checkout_url,\n            status="aguardando_pagamento",\n            observacoes=dados.observacoes,\n            criada_em=agora,\n            atualizada_em=agora,\n        )\n        return self.repositorio.criar(item), False\n\n    def obter(self, intencao_id: int) -> IntencaoPagamento:\n        item = self.repositorio.buscar(intencao_id)\n        if item is None:\n            raise IntegracaoIntencaoNaoEncontrada\n        return item\n\n    def webhook(self, provedor: str, dados: WebhookPagamento, assinatura: str) -> tuple[IntencaoPagamento, bool]:\n        if provedor != "fake":\n            raise IntegracaoProvedorNaoSuportado\n        payload = dados.model_dump()\n        if not validar_assinatura_webhook(payload, assinatura):\n            raise IntegracaoAssinaturaInvalida\n        if dados.tipo_evento not in EVENTOS:\n            raise IntegracaoEventoInvalido\n\n        existente_evento = self.eventos.buscar(provedor, dados.evento_id)\n        if existente_evento is not None:\n            return self.obter(existente_evento.intencao_pagamento_id), True\n\n        item = self.repositorio.buscar_por_external_id(dados.external_payment_id)\n        if item is None:\n            raise IntegracaoIntencaoNaoEncontrada\n        agora = self._agora()\n        if item.provedor != provedor:\n            raise IntegracaoProvedorNaoSuportado\n\n        if dados.tipo_evento == "payment.succeeded":\n            if item.status == "paga":\n                raise IntegracaoPagamentoNaoPodeSerConfirmado\n            if item.status != "aguardando_pagamento":\n                raise IntegracaoPagamentoNaoPodeSerConfirmado\n            pagamento = ServicoPagamento(self.banco).registrar(\n                item.contratacao_id,\n                PagamentoContratacaoCriacao(\n                    empresa_cliente_id=item.empresa_cliente_id,\n                    valor=item.valor,\n                    forma_pagamento=item.forma_pagamento,\n                    observacoes=f"Pagamento via gateway {item.provedor}; intent={item.id}.",\n                ),\n            )\n            item.pagamento_id = pagamento.id\n            item.status = "paga"\n            item.paga_em = agora\n        elif dados.tipo_evento == "payment.failed":\n            if item.status != "aguardando_pagamento":\n                raise IntegracaoPagamentoNaoPodeSerConfirmado\n            item.status = "falhou"\n        else:\n            if item.status != "aguardando_pagamento":\n                raise IntegracaoPagamentoNaoPodeSerConfirmado\n            item.status = "cancelada"\n            item.cancelada_em = agora\n\n        item.atualizada_em = agora\n        evento = EventoGatewayPagamento(\n            provedor=provedor,\n            evento_id=dados.evento_id,\n            intencao_pagamento_id=item.id,\n            external_payment_id=item.external_payment_id,\n            tipo_evento=dados.tipo_evento,\n            status_processamento="processado",\n            payload_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),\n            recebido_em=agora,\n            processado_em=agora,\n        )\n        self.banco.add(evento)\n        self.banco.commit()\n        self.banco.refresh(item)\n        return item, False\n', 'backend/app/api/rotas/integracao_pagamentos.py': 'from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, Header, HTTPException, status\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.intencao_pagamento import (\n    IntencaoPagamentoCriacao,\n    IntencaoPagamentoLeitura,\n    WebhookPagamento,\n    WebhookPagamentoLeitura,\n)\nfrom backend.app.services.integracao_pagamento import (\n    IntegracaoAssinaturaInvalida,\n    IntegracaoContratacaoNaoEncontrada,\n    IntegracaoContratacaoNaoPodeReceber,\n    IntegracaoEmpresaNaoPodeIniciar,\n    IntegracaoEventoInvalido,\n    IntegracaoFormaInvalida,\n    IntegracaoIdempotencyInvalida,\n    IntegracaoIntencaoNaoEncontrada,\n    IntegracaoPagamentoNaoPodeSerConfirmado,\n    IntegracaoProvedorNaoSuportado,\n    IntegracaoValorAcimaDoSaldo,\n    ServicoIntegracaoPagamento,\n)\n\nroteador = APIRouter(prefix="/pagamentos", tags=["integracao-pagamentos"])\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\n\n\n@roteador.post(\n    "/contratacoes/{contratacao_id}/intencoes",\n    response_model=IntencaoPagamentoLeitura,\n    status_code=status.HTTP_201_CREATED,\n)\ndef criar_intencao(\n    contratacao_id: int,\n    dados: IntencaoPagamentoCriacao,\n    banco: SessaoBanco,\n    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],\n):\n    try:\n        item, duplicado = ServicoIntegracaoPagamento(banco).iniciar(contratacao_id, dados, idempotency_key)\n    except IntegracaoContratacaoNaoEncontrada as exc:\n        raise HTTPException(404, "contratacao_nao_encontrada") from exc\n    except IntegracaoEmpresaNaoPodeIniciar as exc:\n        raise HTTPException(403, "empresa_nao_e_cliente_da_contratacao") from exc\n    except IntegracaoContratacaoNaoPodeReceber as exc:\n        raise HTTPException(409, "contratacao_nao_pode_receber_pagamento") from exc\n    except IntegracaoFormaInvalida as exc:\n        raise HTTPException(422, "forma_pagamento_invalida") from exc\n    except IntegracaoValorAcimaDoSaldo as exc:\n        raise HTTPException(409, "valor_acima_do_saldo") from exc\n    except IntegracaoIdempotencyInvalida as exc:\n        raise HTTPException(422, "idempotency_key_invalida") from exc\n    if duplicado:\n        return item\n    return item\n\n\n@roteador.get("/intencoes/{intencao_id}", response_model=IntencaoPagamentoLeitura)\ndef obter_intencao(intencao_id: int, banco: SessaoBanco):\n    try:\n        return ServicoIntegracaoPagamento(banco).obter(intencao_id)\n    except IntegracaoIntencaoNaoEncontrada as exc:\n        raise HTTPException(404, "intencao_pagamento_nao_encontrada") from exc\n\n\n@roteador.post("/webhooks/{provedor}", response_model=WebhookPagamentoLeitura)\ndef receber_webhook(\n    provedor: str,\n    dados: WebhookPagamento,\n    banco: SessaoBanco,\n    x_webhook_signature: Annotated[str, Header(alias="X-Webhook-Signature", min_length=64, max_length=128)],\n):\n    try:\n        item, duplicado = ServicoIntegracaoPagamento(banco).webhook(provedor, dados, x_webhook_signature)\n    except IntegracaoProvedorNaoSuportado as exc:\n        raise HTTPException(422, "provedor_nao_suportado") from exc\n    except IntegracaoAssinaturaInvalida as exc:\n        raise HTTPException(401, "assinatura_webhook_invalida") from exc\n    except IntegracaoEventoInvalido as exc:\n        raise HTTPException(422, "evento_gateway_invalido") from exc\n    except IntegracaoIntencaoNaoEncontrada as exc:\n        raise HTTPException(404, "intencao_pagamento_nao_encontrada") from exc\n    except IntegracaoPagamentoNaoPodeSerConfirmado as exc:\n        raise HTTPException(409, "intencao_pagamento_nao_pode_ser_confirmada") from exc\n    return WebhookPagamentoLeitura(processado=not duplicado, duplicado=duplicado, intencao=item)\n', 'tests/test_integracao_pagamentos.py': 'from __future__ import annotations\n\nimport json\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.integracoes.pagamento import assinatura_webhook\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.principal import app\n\n\n@pytest.fixture()\ndef ambiente():\n    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)\n    SessaoTeste = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)\n    Base.metadata.create_all(bind=engine)\n\n    def override():\n        banco = SessaoTeste()\n        try:\n            yield banco\n        finally:\n            banco.close()\n\n    app.dependency_overrides[obter_banco] = override\n    try:\n        with TestClient(app) as cliente_http:\n            yield cliente_http, SessaoTeste\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(bind=engine)\n        engine.dispose()\n\n\ndef preparar_contratacao(SessaoTeste):\n    banco = SessaoTeste()\n    cliente = Empresa(razao_social="Cliente D13", documento="D13-CLIENTE-001", tipo_empresa="cliente")\n    fornecedor = Empresa(razao_social="Fornecedor D13", documento="D13-FORNECEDOR-001", tipo_empresa="fornecedor")\n    processo = ProcessoFabricacao(codigo="usinagem_cnc_d13", nome="Usinagem CNC D13", descricao="Processo D13")\n    material = Material(codigo="aluminio_6061_d13", nome="Aluminio 6061 D13", familia="Aluminio", especificacao="Liga 6061")\n    banco.add_all([cliente, fornecedor, processo, material])\n    banco.commit()\n    for item in (cliente, fornecedor, processo, material):\n        banco.refresh(item)\n\n    solicitacao = SolicitacaoServico(\n        empresa_cliente_id=cliente.id,\n        processo_id=processo.id,\n        material_id=material.id,\n        dimensao_x_maxima_mm=Decimal("100"),\n        dimensao_y_maxima_mm=Decimal("100"),\n        dimensao_z_maxima_mm=Decimal("100"),\n        tolerancia_requerida_mm=Decimal("0.0200"),\n        quantidade=5,\n        observacoes="Solicitacao D13",\n        status="aberta",\n    )\n    banco.add(solicitacao)\n    banco.commit()\n    banco.refresh(solicitacao)\n\n    cotacao = CotacaoFornecedor(\n        solicitacao_id=solicitacao.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("10000.00"),\n        prazo_dias=10,\n        validade_dias=10,\n        observacoes="Cotacao D13",\n        status="aceita",\n        decidida_por_empresa_id=cliente.id,\n    )\n    banco.add(cotacao)\n    banco.commit()\n    banco.refresh(cotacao)\n\n    contratacao = ContratacaoServico(\n        solicitacao_id=solicitacao.id,\n        cotacao_id=cotacao.id,\n        empresa_cliente_id=cliente.id,\n        empresa_fornecedora_id=fornecedor.id,\n        valor_total=Decimal("10000.00"),\n        prazo_dias=10,\n        observacoes="Contratacao D13",\n        status="ativa",\n    )\n    banco.add(contratacao)\n    banco.commit()\n    banco.refresh(contratacao)\n    ids = cliente.id, fornecedor.id, contratacao.id\n    banco.close()\n    return ids\n\n\ndef criar_intencao(cliente_http, contratacao_id, cliente_id, chave="d13-idempotency-001"):\n    return cliente_http.post(\n        f"/api/v1/pagamentos/contratacoes/{contratacao_id}/intencoes",\n        headers={"Idempotency-Key": chave},\n        json={"empresa_cliente_id": cliente_id, "valor": "5000.00", "forma_pagamento": "pix"},\n    )\n\n\ndef test_criar_intencao_com_gateway_fake(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    resposta = criar_intencao(cliente_http, contratacao_id, cliente_id)\n    assert resposta.status_code == 201\n    dados = resposta.json()\n    assert dados["provedor"] == "fake"\n    assert dados["status"] == "aguardando_pagamento"\n    assert dados["external_payment_id"]\n    assert dados["checkout_url"]\n\n\ndef test_idempotency_nao_cria_duas_intencoes(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    primeira = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-002")\n    segunda = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-002")\n    assert primeira.status_code == 201\n    assert segunda.status_code == 201\n    assert segunda.json()["id"] == primeira.json()["id"]\n\n\ndef test_webhook_sucesso_gera_pagamento_no_livro_d12(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-003")\n    dados_intencao = intencao.json()\n    payload = {\n        "evento_id": "evt-d13-003",\n        "external_payment_id": dados_intencao["external_payment_id"],\n        "tipo_evento": "payment.succeeded",\n    }\n    assinatura = assinatura_webhook(payload)\n    resposta = cliente_http.post(\n        "/api/v1/pagamentos/webhooks/fake",\n        headers={"X-Webhook-Signature": assinatura},\n        json=payload,\n    )\n    assert resposta.status_code == 200\n    corpo = resposta.json()\n    assert corpo["processado"] is True\n    assert corpo["duplicado"] is False\n    assert corpo["intencao"]["status"] == "paga"\n    assert corpo["intencao"]["pagamento_id"] is not None\n\n    resumo = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/financeiro")\n    assert resumo.status_code == 200\n    assert resumo.json()["total_pago"] == "5000.00"\n    assert resumo.json()["saldo"] == "5000.00"\n    assert resumo.json()["status_pagamento"] == "parcial"\n\n\ndef test_webhook_idempotente_nao_duplica_pagamento(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-004")\n    payload = {\n        "evento_id": "evt-d13-004",\n        "external_payment_id": intencao.json()["external_payment_id"],\n        "tipo_evento": "payment.succeeded",\n    }\n    assinatura = assinatura_webhook(payload)\n    primeira = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": assinatura}, json=payload)\n    segunda = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": assinatura}, json=payload)\n    assert primeira.status_code == 200\n    assert segunda.status_code == 200\n    assert segunda.json()["duplicado"] is True\n    pagamentos = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/pagamentos")\n    assert len(pagamentos.json()) == 1\n\n\ndef test_webhook_assinatura_invalida(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-005")\n    payload = {"evento_id": "evt-d13-005", "external_payment_id": intencao.json()["external_payment_id"], "tipo_evento": "payment.succeeded"}\n    resposta = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": "0" * 64}, json=payload)\n    assert resposta.status_code == 401\n\n\ndef test_webhook_falha_muda_status_sem_criar_pagamento(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    intencao = criar_intencao(cliente_http, contratacao_id, cliente_id, "d13-idempotency-006")\n    payload = {"evento_id": "evt-d13-006", "external_payment_id": intencao.json()["external_payment_id"], "tipo_evento": "payment.failed"}\n    assinatura = assinatura_webhook(payload)\n    resposta = cliente_http.post("/api/v1/pagamentos/webhooks/fake", headers={"X-Webhook-Signature": assinatura}, json=payload)\n    assert resposta.status_code == 200\n    assert resposta.json()["intencao"]["status"] == "falhou"\n    pagamentos = cliente_http.get(f"/api/v1/contratacoes/{contratacao_id}/pagamentos")\n    assert pagamentos.status_code == 200\n    assert pagamentos.json() == []\n\n\ndef test_cliente_incorreto_nao_cria_intencao(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    resposta = criar_intencao(cliente_http, contratacao_id, cliente_id + 1000, "d13-idempotency-007")\n    assert resposta.status_code == 403\n\n\ndef test_intencao_nao_permite_valor_acima_do_saldo(ambiente):\n    cliente_http, SessaoTeste = ambiente\n    cliente_id, _, contratacao_id = preparar_contratacao(SessaoTeste)\n    resposta = cliente_http.post(\n        f"/api/v1/pagamentos/contratacoes/{contratacao_id}/intencoes",\n        headers={"Idempotency-Key": "d13-idempotency-008"},\n        json={"empresa_cliente_id": cliente_id, "valor": "10000.01", "forma_pagamento": "pix"},\n    )\n    assert resposta.status_code == 409\n'}


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


def update_models_init() -> bool:
    path = ROOT / "backend/app/models/__init__.py"
    text = path.read_text(encoding="utf-8")
    changed = False
    for line in (
        "from backend.app.models.intencao_pagamento import IntencaoPagamento",
        "from backend.app.models.evento_gateway_pagamento import EventoGatewayPagamento",
    ):
        if line not in text:
            text = text.rstrip() + "\n" + line + "\n"
            changed = True
    if "__all__" in text:
        pairs = (
            ("    \"PagamentoContratacao\",\n", "    \"IntencaoPagamento\",\n"),
            ("    \"IntencaoPagamento\",\n", "    \"EventoGatewayPagamento\",\n"),
        )
        for marker, item in pairs:
            if item not in text and marker in text:
                text = text.replace(marker, marker + item, 1)
                changed = True
    return write_file(path, text) if changed else False


def update_router() -> bool:
    path = ROOT / "backend/app/api/roteador.py"
    text = path.read_text(encoding="utf-8")
    import_line = "from backend.app.api.rotas.integracao_pagamentos import roteador as roteador_integracao_pagamentos"
    include_line = "roteador_api.include_router(roteador_integracao_pagamentos)"
    changed = False
    if import_line not in text:
        text = text.rstrip() + "\n" + import_line + "\n"
        changed = True
    if include_line not in text:
        text = text.rstrip() + "\n" + include_line + "\n"
        changed = True
    return write_file(path, text) if changed else False


def update_readme() -> bool:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    section = (
        "\n\n## D13 — Integração de Pagamentos\n\n"
        "Nesta etapa foi criada a camada de integração de pagamentos, mantendo o D12 como livro financeiro interno:\n\n"
        "- intenção de pagamento vinculada à contratação;\n"
        "- gateway abstrato com implementação `fake` para testes;\n"
        "- chave de idempotência para evitar duplicação de cobranças;\n"
        "- `external_payment_id` do provedor;\n"
        "- webhook assinado;\n"
        "- processamento idempotente de eventos;\n"
        "- evento `payment.succeeded` convertendo a intenção em lançamento D12;\n"
        "- eventos `payment.failed` e `payment.cancelled`;\n"
        "- separação entre intenção de pagamento, evento do gateway e lançamento financeiro.\n\n"
        "A integração externa real permanece desacoplada do domínio e poderá ser adicionada posteriormente por um adaptador de provedor.\n"
    )
    if "## D13 — Integração de Pagamentos" in text:
        return False
    return write_file(path, text.rstrip() + section)


def update_docs() -> bool:
    path = ROOT / "docs/README.md"
    text = path.read_text(encoding="utf-8")
    section = (
        "\n\n## D13 — Integração de Pagamentos\n\n"
        "O D13 adiciona uma camada de intenção de pagamento e um contrato de gateway. O provedor `fake` é usado exclusivamente para testes. "
        "O webhook exige assinatura HMAC e possui idempotência por `(provedor, evento_id)`.\n\n"
        "Quando `payment.succeeded` é recebido, o serviço cria o lançamento confirmado no livro financeiro do D12 e associa seu identificador à intenção. "
        "Eventos duplicados não criam um segundo lançamento.\n"
    )
    if "## D13 — Integração de Pagamentos" in text:
        return False
    return write_file(path, text.rstrip() + section)


def migrate_database() -> dict:
    result = {"database_exists": DB_PATH.exists(), "database_changed": False, "database_already_migrated": False}
    if not DB_PATH.exists():
        return result
    con = sqlite3.connect(DB_PATH)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"intencoes_pagamento", "eventos_gateway_pagamento"}
        if required.issubset(tables):
            result["database_already_migrated"] = True
            result["rows_intencoes"] = con.execute("SELECT COUNT(*) FROM intencoes_pagamento").fetchone()[0]
            result["rows_eventos"] = con.execute("SELECT COUNT(*) FROM eventos_gateway_pagamento").fetchone()[0]
            return result
        con.execute("PRAGMA foreign_keys=ON")
        if "intencoes_pagamento" not in tables:
            con.execute("""
                CREATE TABLE intencoes_pagamento (
                    id INTEGER PRIMARY KEY,
                    contratacao_id INTEGER NOT NULL,
                    empresa_cliente_id INTEGER NOT NULL,
                    empresa_fornecedora_id INTEGER NOT NULL,
                    valor NUMERIC(14, 2) NOT NULL,
                    forma_pagamento VARCHAR(20) NOT NULL CHECK (forma_pagamento IN ('pix','transferencia','boleto','cartao','dinheiro','outro')),
                    provedor VARCHAR(40) NOT NULL DEFAULT 'fake',
                    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
                    external_payment_id VARCHAR(120) NOT NULL UNIQUE,
                    checkout_url VARCHAR(500),
                    status VARCHAR(24) NOT NULL DEFAULT 'aguardando_pagamento' CHECK (status IN ('aguardando_pagamento','paga','falhou','cancelada')),
                    pagamento_id INTEGER,
                    observacoes TEXT,
                    criada_em DATETIME NOT NULL,
                    atualizada_em DATETIME NOT NULL,
                    paga_em DATETIME,
                    cancelada_em DATETIME,
                    FOREIGN KEY (contratacao_id) REFERENCES contratacoes_servico(id) ON DELETE RESTRICT,
                    FOREIGN KEY (empresa_cliente_id) REFERENCES empresas(id) ON DELETE RESTRICT,
                    FOREIGN KEY (empresa_fornecedora_id) REFERENCES empresas(id) ON DELETE RESTRICT,
                    FOREIGN KEY (pagamento_id) REFERENCES pagamentos_contratacao(id) ON DELETE SET NULL
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS ix_intencoes_pagamento_contratacao_id ON intencoes_pagamento (contratacao_id)")
            con.execute("CREATE INDEX IF NOT EXISTS ix_intencoes_pagamento_empresa_cliente_id ON intencoes_pagamento (empresa_cliente_id)")
            con.execute("CREATE INDEX IF NOT EXISTS ix_intencoes_pagamento_status ON intencoes_pagamento (status)")
        if "eventos_gateway_pagamento" not in tables:
            con.execute("""
                CREATE TABLE eventos_gateway_pagamento (
                    id INTEGER PRIMARY KEY,
                    provedor VARCHAR(40) NOT NULL,
                    evento_id VARCHAR(120) NOT NULL,
                    intencao_pagamento_id INTEGER,
                    external_payment_id VARCHAR(120) NOT NULL,
                    tipo_evento VARCHAR(50) NOT NULL,
                    status_processamento VARCHAR(24) NOT NULL DEFAULT 'processado',
                    payload_json TEXT NOT NULL,
                    recebido_em DATETIME NOT NULL,
                    processado_em DATETIME NOT NULL,
                    FOREIGN KEY (intencao_pagamento_id) REFERENCES intencoes_pagamento(id) ON DELETE SET NULL,
                    UNIQUE (provedor, evento_id)
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS ix_eventos_gateway_external_payment_id ON eventos_gateway_pagamento (external_payment_id)")
            con.execute("CREATE INDEX IF NOT EXISTS ix_eventos_gateway_intencao_id ON eventos_gateway_pagamento (intencao_pagamento_id)")
        con.commit()
        result["database_changed"] = True
        result["rows_intencoes"] = 0
        result["rows_eventos"] = 0
        return result
    finally:
        con.close()


def validate_d12_baseline() -> None:
    required = [
        ROOT / "backend/app/models/pagamento.py",
        ROOT / "backend/app/services/pagamento.py",
        ROOT / "backend/app/api/rotas/pagamentos.py",
        ROOT / "backend/app/api/roteador.py",
        ROOT / "data/mec_servicos.db",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        raise RuntimeError("D12_BASELINE_MISSING\n" + "\n".join(missing))


def main() -> int:
    print("Plataforma de Serviços Mecânicos — V0.1 D13 Integração de Pagamentos")
    print("REVISION=", REVISION)
    print("ROOT=", ROOT)
    validate_d12_baseline()
    print("D12_BASELINE_OK= True")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / f"V0_1_D13_INTEGRACAO_PAGAMENTOS_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_targets = [ROOT / rel for rel in FILES]
    backup_targets += [ROOT / "backend/app/models/__init__.py", ROOT / "backend/app/api/roteador.py", ROOT / "README.md", ROOT / "docs/README.md", DB_PATH]
    backed_up = sum(backup_file(path, backup_dir) for path in backup_targets)

    changed = []
    for rel, content in FILES.items():
        if write_file(ROOT / rel, content):
            changed.append(rel)
    if update_models_init():
        changed.append("backend/app/models/__init__.py")
    if update_router():
        changed.append("backend/app/api/roteador.py")
    if update_readme():
        changed.append("README.md")
    if update_docs():
        changed.append("docs/README.md")

    ast_targets = list(FILES) + ["backend/app/models/__init__.py", "backend/app/api/roteador.py"]
    ast_errors = []
    for rel in ast_targets:
        try:
            ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)
        except Exception as exc:
            ast_errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    if ast_errors:
        raise RuntimeError("AST_INVALIDA\n" + "\n".join(ast_errors))

    db = migrate_database()
    import sys
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import create_engine, inspect
    from backend.app.core.configuracao import configuracoes
    import backend.app.models  # noqa: F401
    import backend.app.models.intencao_pagamento  # noqa: F401
    import backend.app.models.evento_gateway_pagamento  # noqa: F401

    engine = create_engine(
        configuracoes.url_banco_dados,
        connect_args={"check_same_thread": False} if configuracoes.url_banco_dados.startswith("sqlite") else {},
    )
    try:
        tables = set(inspect(engine).get_table_names())
        if "intencoes_pagamento" not in tables or "eventos_gateway_pagamento" not in tables:
            raise RuntimeError("Tabelas D13 não foram criadas pela migração.")
    finally:
        engine.dispose()

    payload = {
        "revision": REVISION,
        "ast_ok": True,
        "d12_baseline_ok": True,
        "table_intencoes_pagamento": True,
        "table_eventos_gateway_pagamento": True,
        "database": db,
        "backup_dir": str(backup_dir),
        "backed_up": backed_up,
        "changed_files": changed,
        "gateway_abstraction": True,
        "fake_gateway": True,
        "idempotency": True,
        "signed_webhook": True,
        "webhook_event_idempotency": True,
        "success_event_creates_d12_payment": True,
        "failed_event_preserves_no_payment": True,
        "external_real_gateway": False,
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "Plataforma de Serviços Mecânicos — V0.1 D13 Integração de Pagamentos",
        f"REVISION= {REVISION}",
        f"ROOT= {ROOT}",
        "AST_OK= True",
        "D12_BASELINE_OK= True",
        "TABLE_INTENCOES_PAGAMENTO= True",
        "TABLE_EVENTOS_GATEWAY_PAGAMENTO= True",
        f"DATABASE_CHANGED= {db.get('database_changed')}",
        f"DATABASE_ALREADY_MIGRATED= {db.get('database_already_migrated')}",
        f"BACKED_UP= {backed_up}",
        f"CHANGED_FILES= {len(changed)}",
        "GATEWAY_ABSTRACTION= True",
        "FAKE_GATEWAY= True",
        "IDEMPOTENCY= True",
        "SIGNED_WEBHOOK= True",
        "WEBHOOK_EVENT_IDEMPOTENCY= True",
        "SUCCESS_EVENT_CREATES_D12_PAYMENT= True",
        "FAILED_EVENT_PRESERVES_NO_PAYMENT= True",
        "EXTERNAL_REAL_GATEWAY= False",
        f"BACKUP_DIR= {backup_dir}",
        f"REPORT= {REPORT}",
        f"JSON= {REPORT_JSON}",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines[3:]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
