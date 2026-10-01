from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D7_DECISAO_COTACOES.py"
REVISION = "MEC-SERVICOS-V0.1-D7-DECISAO-COTACOES-2026-10-01"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D7_DECISAO_COTACOES_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D7_DECISAO_COTACOES.json"
BACKUP_ROOT = "_mec_backups"

EXPECTED_D6_HASHES = {'.env.example': '87eee5ce36ba1ae7bc1a51a07094e24b3bf8b4ee5d41b66f8cd1200bdad6981d', '.gitignore': 'a1144fdc91958b636c070731d3a43dffb86b3eff72c962ec04c235568d5f9d08', 'README.md': '1f24435cce61d629b2dee64095074b718d31682e373c258d7cc35fa8babea5a6', 'backend/__init__.py': '690ba32252f50de29c041a17bd248e084cfaec2aad44ed8e2feca911fb71f0f7', 'backend/app/__init__.py': '2ddf04ce230d37abf359b2abd8d1677209e06b54dcfaf256148aecb551b7d46c', 'backend/app/api/__init__.py': 'f2bb21446686add00526d449012aea5f0b2c313166124fa756965721d7655500', 'backend/app/api/rotas/__init__.py': 'adcf1b9f47338f24a6bc9471aa5382e447dafa5e37bbe8e837bc3c22d2150f27', 'backend/app/api/rotas/banco_dados.py': '4ede4c00d97ffeb6a6a07773b5cc965112420ec50151f71f1a741c5a1d1948a7', 'backend/app/api/rotas/capacidades.py': 'f6618b2615afe1f982243add5c746f6e203688a97cf824d310f6a30adbf7cebd', 'backend/app/api/rotas/empresas.py': '8b053288b7c0db67afa6947feb21e4f8029a2daafed91ef7f62a0a87fbe9fb09', 'backend/app/api/rotas/materiais.py': 'f30f27e3f85685efdf554f6e9bc6d9438cce2df70090bad21989d7e0a8b2d80d', 'backend/app/api/rotas/processos.py': '09b41103270590f34cae7c04accfe5f035cfc3fe6bb948dc84d8ce5d00bd009e', 'backend/app/api/rotas/saude.py': '71762976f56f1286a4caf30edbc699573fb2f859a6e89e78cc85791973a4ea39', 'backend/app/api/roteador.py': '63bac31caf7d9dcf6e9a5f835591d498e1657d5771db0bfaca7abb727064db83', 'backend/app/auth/__init__.py': '3201b3408ec5bc94f9f1921146643b6aba1195cf93fcb44891c6535640b86d29', 'backend/app/core/__init__.py': 'e6d29562bddb2c0bd00adee7a6dbe81028949a848e4d767de324b6bcd43c773a', 'backend/app/core/configuracao.py': '3c09980767ca8fdec98d3e6d83847ddefe93fe62636f59f478f2123360360823', 'backend/app/database/__init__.py': 'db6d80c314e9b104c7ce5fa3a8cbc688620f948263b55f89bdb799655931e5ca', 'backend/app/database/base.py': '169ee7e047f140ec73aa6df8f83fab632bbad0ff3c7995087b008134ffc8b9ce', 'backend/app/database/inicializacao.py': 'ae713833fc5ffc79e2f79642d972cda0e4c640ac33d58efd69294429c9a1abf7', 'backend/app/database/sessao.py': '0eb809448955331d1ce4b65e06153882bd5f523e839f6736f66ca323c54c658a', 'backend/app/models/__init__.py': '1f2a2d51f42b754dcb159fafd470aecc77d7c03dbde0e70fadf454be9412b17d', 'backend/app/models/capacidade.py': '3e52b82bf88d8636acb5b93de24f6c12fd78c08fd465b5cc37c58348aa8934b7', 'backend/app/models/empresa.py': '56f2bdbc9930627574ee50b1a19624a903e43ddb330a75dc1c5355b8f5e78730', 'backend/app/models/maquina.py': '87e05f3563524822d31bff9cfa2bc24aeba2667baecb3f43b87fa5972d37a617', 'backend/app/models/material.py': 'bc424157fc9141d35c4275d54655d331fa6b2e5d51eca4d35a23fb4e0e1eb313', 'backend/app/models/material_fornecedor.py': '30372d3a583069625bb54120793351b5da16b037b79fd1bb34f0424d002213ae', 'backend/app/models/processo.py': '84ddea465d90af57c729973e1b80697d70ebaf8cf328453f6c4436d73e50b51b', 'backend/app/principal.py': '7a4a04cbaae7e0b99e2acae3a4c7c031d494e108184c699e35ab431c4898db48', 'backend/app/repositories/__init__.py': '1c34878befe52911e8dd3c67b64ed745d826a017bc92c6abc140fddd4a6a2892', 'backend/app/repositories/capacidade.py': 'ebeabad5e367cbf6fd56c30cdcc8ada786cef963c80172f1b192e437ebe0be38', 'backend/app/repositories/empresa.py': 'be9cc6fd0caef93e475f585cf349642d86744f2efee9bd2d4df894857070080a', 'backend/app/schemas/__init__.py': '508499fde601fcbc35d55153522d82e2f37471781e48ff6eaf2ef92fde7a65c0', 'backend/app/schemas/capacidade.py': '39e765fc34fcaf55a1b3775cef4b5a10e53fedac123586f95fcd73e59f210609', 'backend/app/schemas/empresa.py': 'c45daf2aa640d50576d113b5917466e4feff44015ef1cd07715297e145f561ba', 'backend/app/schemas/material.py': '51a7360a94223cda59ead93d285fb898fcc3441161a4a2752cc579ea57b91f9e', 'backend/app/schemas/processo.py': '43ee83979a70faae06e2f33977ebff5db9c1b0684645b5558cf54dd0a0f0bc2b', 'backend/app/services/__init__.py': '0a1ee226f5b792028404f5726d3c8560c7451a4a9d8e483ca53d7d176bc6da95', 'backend/app/services/capacidade.py': 'f052d3448f05be622df4eb65e9f16f9a5e26c7cf1f9b0f6e304432f9dda1505d', 'backend/app/services/empresa.py': '239e4f78f66a583493cb1c45b0ca818270910deb992e93673e68bef5416a563e', 'docs/README.md': 'd57eafc62261a9b07b2c6083391725678cb14331d3b6c4ef318ac4ea7c477cfb', 'pyproject.toml': '804119239108047d4248590388e74779e241f3c0050d3e8c81c92dd4f249ce33', 'tests/test_banco_dados.py': 'a3c73d8f22483993efaba3a3e1803e5c28ef5f6d94e484368a5082fad33199d2', 'tests/test_capacidade_tecnica.py': '096492868933fa0b9899c265bbe31937de6f82fe8edc581cc3d92f85e5de470b', 'tests/test_empresas_api.py': 'ead6248db13f010d8a528aec745c614779d77786261fb3a1529cd8fb4cf70365', 'tests/test_saude.py': 'b301583b26b6d3d5ebec124594e02dcc9ca6a9ea675e78563f32bddd5a02afa5', 'backend/app/api/rotas/solicitacoes.py': '10765d225ffa1204ec535eaa9ce9100c8a2a66f693cc19d3fd40fbd845a43ef5', 'backend/app/models/solicitacao.py': '5e975e2300c7474b8d0dcf03f08594b1b9ec57a1c8c3c1f82120870c5ef8fadd', 'backend/app/repositories/compatibilidade.py': '49fc99c0af6d702a574eb9d7a55367db2f8cd6c717169b89f90bf8836433377e', 'backend/app/schemas/solicitacao.py': '460c40a287e1d32e10d29545b8fbd53af040f22b4201fb5a3f1403ca0e9f3a5e', 'backend/app/services/compatibilidade.py': 'cc00cb2d08c1d910250b8b4da12058e7500d9b69eedb864f35b0421e63eced6b', 'tests/test_compatibilidade_fornecedores.py': '521f5543d8114e04e71742d777d9d5e9d85811d855ebe003ee07c30a0e6df688', 'backend/app/models/cotacao.py': 'dfdd6c74fb2cd217100387497b33e15a602dda46144b62394011f7b9b69cdae6', 'backend/app/schemas/cotacao.py': '0e21f59f4c60ce9ff071a0810b54ca9be90b72694632f94de1406690bda2227e', 'backend/app/repositories/cotacao.py': '8ba4c03d108c556a263a3eb0e093b98bc57c362697601bb5b8aa0dbe0b438b81', 'backend/app/services/cotacao.py': 'ae67abd1dfc4fb3af79d2d432bc423a47a00b00f361d554fc2a54e8cae38dfcf', 'backend/app/api/rotas/cotacoes.py': '62bd78b43b98f8e58d45715137f769a132d641c3a9e484c4fec01ba384d3836d', 'tests/test_cotacoes.py': '67f6180efcbc00d12cf8c79c29364c5c3a4711294dd435a881ce75ea2123939b'}
UPDATED_FILES = {'README.md': '# Plataforma de Serviços Mecânicos\n\nProjeto independente para conectar clientes e fornecedores de serviços mecânicos.\n\n## Regra de idioma\n\nA aplicação é desenvolvida em português: interface, documentação, mensagens,\nvalidações, nomes do domínio e módulos específicos da aplicação.\n\nNomes de tecnologias externas, como Python, FastAPI, SQLAlchemy, SQLite e Uvicorn,\npermanecem com seus nomes oficiais.\n\n## Estado\n\n**V0.1 D7 — Decisão Comercial das Cotações**\n\nNesta etapa foram estruturados:\n\n- ciclo de vida da cotação;\n- aceite de uma cotação pelo cliente da solicitação;\n- recusa de uma cotação pelo cliente da solicitação;\n- registro da data de encerramento;\n- registro da empresa que tomou a decisão;\n- rejeição automática das demais cotações pendentes quando uma é aceita;\n- bloqueio de novas cotações depois que uma solicitação já possui cotação aceita;\n- expiração automática das cotações vencidas durante consultas ou decisões;\n- preservação do histórico das cotações.\n\nO projeto continua independente do CGX Platform.\n\n## Ciclo da cotação\n\nUma cotação pode estar em:\n\n- `enviada`\n- `aceita`\n- `recusada`\n- `expirada`\n- `cancelada`\n\nSomente uma cotação por solicitação pode ficar `aceita`.\n\nQuando uma cotação é aceita, as demais que ainda estiverem `enviada`\nsão marcadas como `recusada`.\n\n## Autorização comercial\n\nComo ainda não existe autenticação de usuários, as rotas de decisão recebem\nexplicitamente `empresa_cliente_id`.\n\nO sistema verifica se essa empresa é a empresa cliente da solicitação.\n\nIsso é uma validação de domínio e **não substitui autenticação**.\n\n## Regra técnica\n\nA criação da cotação continua dependente da compatibilidade técnica do D5.\n\nO D7 não altera o motor de compatibilidade.\n\n## O que ainda não faz parte do D7\n\n- autenticação de usuários;\n- negociação de preço;\n- contraproposta;\n- contratação;\n- ordem de produção;\n- pagamento;\n- avaliação;\n- ranking de fornecedores.\n\n## Executar\n\n```powershell\npython -m pytest\npython -m uvicorn backend.app.principal:app --reload\n```\n\n## Endpoints principais\n\n- `http://127.0.0.1:8000/`\n- `http://127.0.0.1:8000/api/v1/saude`\n- `http://127.0.0.1:8000/api/v1/banco-dados/saude`\n- `http://127.0.0.1:8000/api/v1/empresas`\n- `http://127.0.0.1:8000/api/v1/processos-fabricacao`\n- `http://127.0.0.1:8000/api/v1/materiais`\n- `http://127.0.0.1:8000/api/v1/solicitacoes-servico`\n- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis`\n- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes`\n- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/aceitar`\n- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/recusar`\n- `http://127.0.0.1:8000/docs`\n', 'backend/app/models/cotacao.py': 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom decimal import Decimal\n\nfrom sqlalchemy import (\n    CheckConstraint,\n    DateTime,\n    ForeignKey,\n    Integer,\n    Numeric,\n    String,\n    Text,\n    UniqueConstraint,\n    func,\n)\nfrom sqlalchemy.orm import Mapped, mapped_column\n\nfrom backend.app.database.base import Base\n\n\nclass CotacaoFornecedor(Base):\n    __tablename__ = "cotacoes_fornecedor"\n    __table_args__ = (\n        UniqueConstraint(\n            "solicitacao_id",\n            "empresa_fornecedora_id",\n            name="uq_cotacao_solicitacao_fornecedor",\n        ),\n        CheckConstraint("valor_total > 0", name="ck_cotacoes_valor_total"),\n        CheckConstraint("prazo_dias > 0", name="ck_cotacoes_prazo"),\n        CheckConstraint("validade_dias > 0", name="ck_cotacoes_validade"),\n        CheckConstraint(\n            "status IN (\'enviada\', \'aceita\', \'recusada\', \'expirada\', \'cancelada\')",\n            name="ck_cotacoes_status",\n        ),\n    )\n\n    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)\n    solicitacao_id: Mapped[int] = mapped_column(\n        ForeignKey("solicitacoes_servico.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    empresa_fornecedora_id: Mapped[int] = mapped_column(\n        ForeignKey("empresas.id", ondelete="RESTRICT"),\n        nullable=False,\n        index=True,\n    )\n    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)\n    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)\n    validade_dias: Mapped[int] = mapped_column(Integer, nullable=False)\n    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)\n    status: Mapped[str] = mapped_column(\n        String(16),\n        nullable=False,\n        default="enviada",\n        server_default="enviada",\n    )\n    criada_em: Mapped[datetime] = mapped_column(\n        DateTime(timezone=True),\n        server_default=func.now(),\n        nullable=False,\n    )\n    encerrada_em: Mapped[datetime | None] = mapped_column(\n        DateTime(timezone=True),\n        nullable=True,\n    )\n    decidida_por_empresa_id: Mapped[int | None] = mapped_column(\n        ForeignKey("empresas.id", ondelete="RESTRICT"),\n        nullable=True,\n        index=True,\n    )\n', 'backend/app/schemas/cotacao.py': 'from __future__ import annotations\n\nfrom datetime import datetime\nfrom decimal import Decimal\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\n\nclass CotacaoCriacao(BaseModel):\n    empresa_fornecedora_id: int = Field(gt=0)\n    valor_total: Decimal = Field(gt=0, max_digits=14, decimal_places=2)\n    prazo_dias: int = Field(gt=0, le=3650)\n    validade_dias: int = Field(gt=0, le=3650)\n    observacoes: str | None = Field(default=None, max_length=5000)\n\n\nclass CotacaoDecisao(BaseModel):\n    empresa_cliente_id: int = Field(gt=0)\n\n\nclass CotacaoLeitura(BaseModel):\n    model_config = ConfigDict(from_attributes=True)\n\n    id: int\n    solicitacao_id: int\n    empresa_fornecedora_id: int\n    valor_total: Decimal\n    prazo_dias: int\n    validade_dias: int\n    observacoes: str | None\n    status: str\n    criada_em: datetime\n    encerrada_em: datetime | None\n    decidida_por_empresa_id: int | None\n', 'backend/app/repositories/cotacao.py': 'from __future__ import annotations\n\nfrom sqlalchemy import select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.cotacao import CotacaoFornecedor\n\n\nclass RepositorioCotacao:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def criar(self, cotacao: CotacaoFornecedor) -> CotacaoFornecedor:\n        self.banco.add(cotacao)\n        self.banco.commit()\n        self.banco.refresh(cotacao)\n        return cotacao\n\n    def buscar(\n        self,\n        solicitacao_id: int,\n        cotacao_id: int,\n    ) -> CotacaoFornecedor | None:\n        consulta = select(CotacaoFornecedor).where(\n            CotacaoFornecedor.id == cotacao_id,\n            CotacaoFornecedor.solicitacao_id == solicitacao_id,\n        )\n        return self.banco.scalar(consulta)\n\n    def listar_por_solicitacao(\n        self,\n        solicitacao_id: int,\n    ) -> list[CotacaoFornecedor]:\n        consulta = (\n            select(CotacaoFornecedor)\n            .where(CotacaoFornecedor.solicitacao_id == solicitacao_id)\n            .order_by(CotacaoFornecedor.id)\n        )\n        return list(self.banco.scalars(consulta).all())\n\n    def listar_pendentes(\n        self,\n        solicitacao_id: int,\n    ) -> list[CotacaoFornecedor]:\n        consulta = (\n            select(CotacaoFornecedor)\n            .where(\n                CotacaoFornecedor.solicitacao_id == solicitacao_id,\n                CotacaoFornecedor.status == "enviada",\n            )\n            .order_by(CotacaoFornecedor.id)\n        )\n        return list(self.banco.scalars(consulta).all())\n\n    def listar_aceitas(\n        self,\n        solicitacao_id: int,\n    ) -> list[CotacaoFornecedor]:\n        consulta = (\n            select(CotacaoFornecedor)\n            .where(\n                CotacaoFornecedor.solicitacao_id == solicitacao_id,\n                CotacaoFornecedor.status == "aceita",\n            )\n            .order_by(CotacaoFornecedor.id)\n        )\n        return list(self.banco.scalars(consulta).all())\n', 'backend/app/services/cotacao.py': 'from __future__ import annotations\n\nfrom datetime import datetime, timedelta, timezone\n\nfrom sqlalchemy.exc import IntegrityError\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.repositories.cotacao import RepositorioCotacao\nfrom backend.app.schemas.cotacao import CotacaoCriacao\nfrom backend.app.services.compatibilidade import ServicoCompatibilidade\n\n\nclass CotacaoSolicitacaoNaoEncontrada(LookupError):\n    pass\n\n\nclass CotacaoEmpresaNaoEncontrada(LookupError):\n    pass\n\n\nclass CotacaoEmpresaNaoFornecedor(ValueError):\n    pass\n\n\nclass CotacaoFornecedorIncompativel(ValueError):\n    pass\n\n\nclass CotacaoDuplicada(ValueError):\n    pass\n\n\nclass CotacaoNaoEncontrada(LookupError):\n    pass\n\n\nclass CotacaoNaoPendente(ValueError):\n    pass\n\n\nclass CotacaoExpirada(ValueError):\n    pass\n\n\nclass EmpresaNaoPodeDecidir(PermissionError):\n    pass\n\n\nclass SolicitacaoJaPossuiCotacaoAceita(ValueError):\n    pass\n\n\nclass ServicoCotacao:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.repositorio = RepositorioCotacao(banco)\n\n    @staticmethod\n    def _agora_utc_sem_fuso() -> datetime:\n        return datetime.now(timezone.utc).replace(tzinfo=None)\n\n    @staticmethod\n    def _normalizar_data(data: datetime) -> datetime:\n        if data.tzinfo is None:\n            return data\n        return data.astimezone(timezone.utc).replace(tzinfo=None)\n\n    def _atualizar_expiradas(self, solicitacao_id: int) -> None:\n        agora = self._agora_utc_sem_fuso()\n        alterou = False\n\n        for cotacao in self.repositorio.listar_pendentes(solicitacao_id):\n            criada = self._normalizar_data(cotacao.criada_em)\n            vencimento = criada + timedelta(days=cotacao.validade_dias)\n            if agora >= vencimento:\n                cotacao.status = "expirada"\n                cotacao.encerrada_em = agora\n                cotacao.decidida_por_empresa_id = None\n                alterou = True\n\n        if alterou:\n            self.banco.commit()\n\n    def criar(\n        self,\n        solicitacao_id: int,\n        dados: CotacaoCriacao,\n    ) -> CotacaoFornecedor:\n        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)\n        if solicitacao is None:\n            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)\n\n        self._atualizar_expiradas(solicitacao_id)\n\n        if self.repositorio.listar_aceitas(solicitacao_id):\n            raise SolicitacaoJaPossuiCotacaoAceita(solicitacao_id)\n\n        empresa = self.banco.get(Empresa, dados.empresa_fornecedora_id)\n        if empresa is None:\n            raise CotacaoEmpresaNaoEncontrada(\n                dados.empresa_fornecedora_id\n            )\n\n        if empresa.tipo_empresa not in {"fornecedor", "ambos"}:\n            raise CotacaoEmpresaNaoFornecedor(\n                dados.empresa_fornecedora_id\n            )\n\n        fornecedores_compativeis = (\n            ServicoCompatibilidade(self.banco)\n            .listar_fornecedores_compativeis(solicitacao_id)\n        )\n        ids_compativeis = {\n            fornecedor.id\n            for fornecedor, _capacidade in fornecedores_compativeis\n        }\n\n        if empresa.id not in ids_compativeis:\n            raise CotacaoFornecedorIncompativel(\n                dados.empresa_fornecedora_id\n            )\n\n        cotacao = CotacaoFornecedor(\n            solicitacao_id=solicitacao_id,\n            empresa_fornecedora_id=dados.empresa_fornecedora_id,\n            valor_total=dados.valor_total,\n            prazo_dias=dados.prazo_dias,\n            validade_dias=dados.validade_dias,\n            observacoes=dados.observacoes,\n        )\n\n        try:\n            return self.repositorio.criar(cotacao)\n        except IntegrityError as exc:\n            self.banco.rollback()\n            raise CotacaoDuplicada from exc\n\n    def listar(\n        self,\n        solicitacao_id: int,\n    ) -> list[CotacaoFornecedor]:\n        if self.banco.get(SolicitacaoServico, solicitacao_id) is None:\n            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)\n\n        self._atualizar_expiradas(solicitacao_id)\n        return self.repositorio.listar_por_solicitacao(solicitacao_id)\n\n    def _validar_decisor(\n        self,\n        solicitacao: SolicitacaoServico,\n        empresa_cliente_id: int,\n    ) -> None:\n        if solicitacao.empresa_cliente_id != empresa_cliente_id:\n            raise EmpresaNaoPodeDecidir(empresa_cliente_id)\n\n        empresa = self.banco.get(Empresa, empresa_cliente_id)\n        if empresa is None:\n            raise EmpresaNaoPodeDecidir(empresa_cliente_id)\n\n    def aceitar(\n        self,\n        solicitacao_id: int,\n        cotacao_id: int,\n        empresa_cliente_id: int,\n    ) -> CotacaoFornecedor:\n        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)\n        if solicitacao is None:\n            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)\n\n        self._validar_decisor(solicitacao, empresa_cliente_id)\n        self._atualizar_expiradas(solicitacao_id)\n\n        cotacao = self.repositorio.buscar(solicitacao_id, cotacao_id)\n        if cotacao is None:\n            raise CotacaoNaoEncontrada(cotacao_id)\n\n        if cotacao.status == "expirada":\n            raise CotacaoExpirada(cotacao_id)\n        if cotacao.status != "enviada":\n            raise CotacaoNaoPendente(cotacao_id)\n\n        outras_aceitas = [\n            item\n            for item in self.repositorio.listar_aceitas(solicitacao_id)\n            if item.id != cotacao_id\n        ]\n        if outras_aceitas:\n            raise SolicitacaoJaPossuiCotacaoAceita(solicitacao_id)\n\n        agora = self._agora_utc_sem_fuso()\n        cotacao.status = "aceita"\n        cotacao.encerrada_em = agora\n        cotacao.decidida_por_empresa_id = empresa_cliente_id\n\n        for outra in self.repositorio.listar_pendentes(solicitacao_id):\n            if outra.id == cotacao.id:\n                continue\n            outra.status = "recusada"\n            outra.encerrada_em = agora\n            outra.decidida_por_empresa_id = empresa_cliente_id\n\n        self.banco.commit()\n        self.banco.refresh(cotacao)\n        return cotacao\n\n    def recusar(\n        self,\n        solicitacao_id: int,\n        cotacao_id: int,\n        empresa_cliente_id: int,\n    ) -> CotacaoFornecedor:\n        solicitacao = self.banco.get(SolicitacaoServico, solicitacao_id)\n        if solicitacao is None:\n            raise CotacaoSolicitacaoNaoEncontrada(solicitacao_id)\n\n        self._validar_decisor(solicitacao, empresa_cliente_id)\n        self._atualizar_expiradas(solicitacao_id)\n\n        cotacao = self.repositorio.buscar(solicitacao_id, cotacao_id)\n        if cotacao is None:\n            raise CotacaoNaoEncontrada(cotacao_id)\n\n        if cotacao.status == "expirada":\n            raise CotacaoExpirada(cotacao_id)\n        if cotacao.status != "enviada":\n            raise CotacaoNaoPendente(cotacao_id)\n\n        agora = self._agora_utc_sem_fuso()\n        cotacao.status = "recusada"\n        cotacao.encerrada_em = agora\n        cotacao.decidida_por_empresa_id = empresa_cliente_id\n\n        self.banco.commit()\n        self.banco.refresh(cotacao)\n        return cotacao\n', 'backend/app/api/rotas/cotacoes.py': 'from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, HTTPException, status\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.cotacao import (\n    CotacaoCriacao,\n    CotacaoDecisao,\n    CotacaoLeitura,\n)\nfrom backend.app.services.cotacao import (\n    CotacaoDuplicada,\n    CotacaoEmpresaNaoFornecedor,\n    CotacaoEmpresaNaoEncontrada,\n    CotacaoExpirada,\n    CotacaoFornecedorIncompativel,\n    CotacaoNaoEncontrada,\n    CotacaoNaoPendente,\n    CotacaoSolicitacaoNaoEncontrada,\n    EmpresaNaoPodeDecidir,\n    SolicitacaoJaPossuiCotacaoAceita,\n    ServicoCotacao,\n)\n\nroteador = APIRouter(\n    prefix="/solicitacoes-servico",\n    tags=["cotações"],\n)\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\n\n\n@roteador.post(\n    "/{solicitacao_id}/cotacoes",\n    response_model=CotacaoLeitura,\n    status_code=status.HTTP_201_CREATED,\n)\ndef criar_cotacao(\n    solicitacao_id: int,\n    dados: CotacaoCriacao,\n    banco: SessaoBanco,\n) -> CotacaoLeitura:\n    try:\n        cotacao = ServicoCotacao(banco).criar(solicitacao_id, dados)\n    except CotacaoSolicitacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="solicitacao_nao_encontrada",\n        ) from exc\n    except CotacaoEmpresaNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="empresa_fornecedora_nao_encontrada",\n        ) from exc\n    except CotacaoEmpresaNaoFornecedor as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="empresa_nao_e_fornecedora",\n        ) from exc\n    except CotacaoFornecedorIncompativel as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="fornecedor_nao_compativel_com_a_solicitacao",\n        ) from exc\n    except CotacaoDuplicada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="cotacao_ja_cadastrada_para_este_fornecedor",\n        ) from exc\n    except SolicitacaoJaPossuiCotacaoAceita as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="solicitacao_ja_possui_cotacao_aceita",\n        ) from exc\n\n    return CotacaoLeitura.model_validate(cotacao)\n\n\n@roteador.get(\n    "/{solicitacao_id}/cotacoes",\n    response_model=list[CotacaoLeitura],\n)\ndef listar_cotacoes(\n    solicitacao_id: int,\n    banco: SessaoBanco,\n) -> list[CotacaoLeitura]:\n    try:\n        cotacoes = ServicoCotacao(banco).listar(solicitacao_id)\n    except CotacaoSolicitacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="solicitacao_nao_encontrada",\n        ) from exc\n\n    return [CotacaoLeitura.model_validate(cotacao) for cotacao in cotacoes]\n\n\ndef _processar_decisao(\n    acao: str,\n    solicitacao_id: int,\n    cotacao_id: int,\n    dados: CotacaoDecisao,\n    banco: Session,\n) -> CotacaoLeitura:\n    servico = ServicoCotacao(banco)\n\n    try:\n        if acao == "aceitar":\n            cotacao = servico.aceitar(\n                solicitacao_id,\n                cotacao_id,\n                dados.empresa_cliente_id,\n            )\n        else:\n            cotacao = servico.recusar(\n                solicitacao_id,\n                cotacao_id,\n                dados.empresa_cliente_id,\n            )\n    except CotacaoSolicitacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="solicitacao_nao_encontrada",\n        ) from exc\n    except CotacaoNaoEncontrada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_404_NOT_FOUND,\n            detail="cotacao_nao_encontrada",\n        ) from exc\n    except EmpresaNaoPodeDecidir as exc:\n        raise HTTPException(\n            status_code=status.HTTP_403_FORBIDDEN,\n            detail="empresa_nao_e_cliente_da_solicitacao",\n        ) from exc\n    except CotacaoExpirada as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="cotacao_expirada",\n        ) from exc\n    except CotacaoNaoPendente as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="cotacao_nao_esta_pendente",\n        ) from exc\n    except SolicitacaoJaPossuiCotacaoAceita as exc:\n        raise HTTPException(\n            status_code=status.HTTP_409_CONFLICT,\n            detail="solicitacao_ja_possui_cotacao_aceita",\n        ) from exc\n\n    return CotacaoLeitura.model_validate(cotacao)\n\n\n@roteador.post(\n    "/{solicitacao_id}/cotacoes/{cotacao_id}/aceitar",\n    response_model=CotacaoLeitura,\n)\ndef aceitar_cotacao(\n    solicitacao_id: int,\n    cotacao_id: int,\n    dados: CotacaoDecisao,\n    banco: SessaoBanco,\n) -> CotacaoLeitura:\n    return _processar_decisao(\n        "aceitar",\n        solicitacao_id,\n        cotacao_id,\n        dados,\n        banco,\n    )\n\n\n@roteador.post(\n    "/{solicitacao_id}/cotacoes/{cotacao_id}/recusar",\n    response_model=CotacaoLeitura,\n)\ndef recusar_cotacao(\n    solicitacao_id: int,\n    cotacao_id: int,\n    dados: CotacaoDecisao,\n    banco: SessaoBanco,\n) -> CotacaoLeitura:\n    return _processar_decisao(\n        "recusar",\n        solicitacao_id,\n        cotacao_id,\n        dados,\n        banco,\n    )\n', 'tests/test_cotacoes.py': 'from collections.abc import Generator\n\nimport pytest\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.principal import app\n\n\n@pytest.fixture()\ndef cliente() -> Generator[TestClient, None, None]:\n    engine = create_engine(\n        "sqlite://",\n        connect_args={"check_same_thread": False},\n        poolclass=StaticPool,\n    )\n    SessaoTeste = sessionmaker(\n        bind=engine,\n        autoflush=False,\n        expire_on_commit=False,\n        class_=Session,\n    )\n    Base.metadata.create_all(bind=engine)\n\n    def substituir_banco() -> Generator[Session, None, None]:\n        banco = SessaoTeste()\n        try:\n            yield banco\n        finally:\n            banco.close()\n\n    app.dependency_overrides[obter_banco] = substituir_banco\n\n    with TestClient(app) as test_client:\n        yield test_client\n\n    app.dependency_overrides.clear()\n    Base.metadata.drop_all(bind=engine)\n    engine.dispose()\n\n\ndef cadastrar_empresa(\n    cliente: TestClient,\n    documento: str,\n    tipo: str,\n    nome: str,\n) -> int:\n    resposta = cliente.post(\n        "/api/v1/empresas",\n        json={\n            "razao_social": nome,\n            "documento": documento,\n            "tipo_empresa": tipo,\n        },\n    )\n    assert resposta.status_code == 201\n    return resposta.json()["id"]\n\n\ndef adicionar_fornecedor_compativel(\n    cliente: TestClient,\n    processo_id: int,\n    material_id: int,\n    documento: str,\n    nome: str,\n) -> int:\n    fornecedor_id = cadastrar_empresa(\n        cliente,\n        documento,\n        "fornecedor",\n        nome,\n    )\n    capacidade = cliente.post(\n        f"/api/v1/empresas/{fornecedor_id}/capacidades",\n        json={\n            "processo_id": processo_id,\n            "dimensao_x_maxima_mm": "800.000",\n            "dimensao_y_maxima_mm": "500.000",\n            "dimensao_z_maxima_mm": "450.000",\n            "tolerancia_minima_mm": "0.0200",\n        },\n    )\n    vinculo = cliente.post(\n        f"/api/v1/empresas/{fornecedor_id}/materiais",\n        json={"material_id": material_id},\n    )\n    assert capacidade.status_code == 201\n    assert vinculo.status_code == 201\n    return fornecedor_id\n\n\ndef criar_cotacao(\n    cliente: TestClient,\n    solicitacao_id: int,\n    fornecedor_id: int,\n    valor: str = "12500.00",\n) -> dict:\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",\n        json={\n            "empresa_fornecedora_id": fornecedor_id,\n            "valor_total": valor,\n            "prazo_dias": 15,\n            "validade_dias": 10,\n        },\n    )\n    assert resposta.status_code == 201\n    return resposta.json()\n\n\ndef preparar_cenario(cliente: TestClient) -> tuple[int, int, int, int, int]:\n    cliente_id = cadastrar_empresa(\n        cliente,\n        "98765432000110",\n        "cliente",\n        "Cliente Cotação Ltda",\n    )\n    fornecedor_id = cadastrar_empresa(\n        cliente,\n        "12345678000190",\n        "fornecedor",\n        "Fornecedor Cotação Ltda",\n    )\n\n    processo = cliente.post(\n        "/api/v1/processos-fabricacao",\n        json={"codigo": "usinagem_cnc", "nome": "Usinagem CNC"},\n    )\n    material = cliente.post(\n        "/api/v1/materiais",\n        json={\n            "codigo": "aluminio_6061",\n            "nome": "Alumínio 6061",\n            "familia": "Alumínio",\n        },\n    )\n    assert processo.status_code == 201\n    assert material.status_code == 201\n\n    processo_id = processo.json()["id"]\n    material_id = material.json()["id"]\n\n    capacidade = cliente.post(\n        f"/api/v1/empresas/{fornecedor_id}/capacidades",\n        json={\n            "processo_id": processo_id,\n            "dimensao_x_maxima_mm": "800.000",\n            "dimensao_y_maxima_mm": "500.000",\n            "dimensao_z_maxima_mm": "450.000",\n            "tolerancia_minima_mm": "0.0200",\n        },\n    )\n    vinculo = cliente.post(\n        f"/api/v1/empresas/{fornecedor_id}/materiais",\n        json={"material_id": material_id},\n    )\n    assert capacidade.status_code == 201\n    assert vinculo.status_code == 201\n\n    solicitacao = cliente.post(\n        "/api/v1/solicitacoes-servico",\n        json={\n            "empresa_cliente_id": cliente_id,\n            "processo_id": processo_id,\n            "material_id": material_id,\n            "dimensao_x_maxima_mm": "600.000",\n            "dimensao_y_maxima_mm": "400.000",\n            "dimensao_z_maxima_mm": "300.000",\n            "tolerancia_requerida_mm": "0.0200",\n            "quantidade": 10,\n            "observacoes": "Solicitação de teste D7.",\n        },\n    )\n    assert solicitacao.status_code == 201\n\n    return (\n        solicitacao.json()["id"],\n        cliente_id,\n        fornecedor_id,\n        processo_id,\n        material_id,\n    )\n\n\ndef test_cria_cotacao_de_fornecedor_compativel(cliente: TestClient) -> None:\n    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    dados = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n    assert dados["status"] == "enviada"\n    assert dados["encerrada_em"] is None\n    assert dados["decidida_por_empresa_id"] is None\n\n\ndef test_lista_cotacoes_da_solicitacao(cliente: TestClient) -> None:\n    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    resposta = cliente.get(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes"\n    )\n\n    assert resposta.status_code == 200\n    assert len(resposta.json()) == 1\n\n\ndef test_fornecedor_incompativel_nao_pode_cotar(cliente: TestClient) -> None:\n    solicitacao_id, _cliente_id, _fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    outro_fornecedor = cadastrar_empresa(\n        cliente,\n        "11222333000144",\n        "fornecedor",\n        "Fornecedor Incompatível Ltda",\n    )\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",\n        json={\n            "empresa_fornecedora_id": outro_fornecedor,\n            "valor_total": "10000.00",\n            "prazo_dias": 10,\n            "validade_dias": 10,\n        },\n    )\n\n    assert resposta.status_code == 409\n    assert resposta.json()["detail"] == (\n        "fornecedor_nao_compativel_com_a_solicitacao"\n    )\n\n\ndef test_empresa_cliente_nao_pode_enviar_cotacao(cliente: TestClient) -> None:\n    solicitacao_id, _cliente_id, _fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    cliente_extra = cadastrar_empresa(\n        cliente,\n        "55666777000188",\n        "cliente",\n        "Cliente Extra Ltda",\n    )\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",\n        json={\n            "empresa_fornecedora_id": cliente_extra,\n            "valor_total": "10000.00",\n            "prazo_dias": 10,\n            "validade_dias": 10,\n        },\n    )\n    assert resposta.status_code == 409\n    assert resposta.json()["detail"] == "empresa_nao_e_fornecedora"\n\n\ndef test_nao_permite_duas_cotacoes_do_mesmo_fornecedor(\n    cliente: TestClient,\n) -> None:\n    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    primeira = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    segunda = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",\n        json={\n            "empresa_fornecedora_id": fornecedor_id,\n            "valor_total": "11000.00",\n            "prazo_dias": 12,\n            "validade_dias": 10,\n        },\n    )\n\n    assert primeira["status"] == "enviada"\n    assert segunda.status_code == 409\n    assert segunda.json()["detail"] == (\n        "cotacao_ja_cadastrada_para_este_fornecedor"\n    )\n\n\n@pytest.mark.parametrize(\n    "campo,valor",\n    [\n        ("valor_total", "0"),\n        ("prazo_dias", 0),\n        ("validade_dias", 0),\n    ],\n)\ndef test_dados_comerciais_invalidos_sao_rejeitados(\n    cliente: TestClient,\n    campo: str,\n    valor: object,\n) -> None:\n    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    dados = {\n        "empresa_fornecedora_id": fornecedor_id,\n        "valor_total": "10000.00",\n        "prazo_dias": 10,\n        "validade_dias": 10,\n    }\n    dados[campo] = valor\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",\n        json=dados,\n    )\n    assert resposta.status_code == 422\n\n\ndef test_solicitacao_inexistente_nao_aceita_cotacao(cliente: TestClient) -> None:\n    fornecedor_id = cadastrar_empresa(\n        cliente,\n        "12345678000190",\n        "fornecedor",\n        "Fornecedor Cotação Ltda",\n    )\n    resposta = cliente.post(\n        "/api/v1/solicitacoes-servico/999/cotacoes",\n        json={\n            "empresa_fornecedora_id": fornecedor_id,\n            "valor_total": "10000.00",\n            "prazo_dias": 10,\n            "validade_dias": 10,\n        },\n    )\n    assert resposta.status_code == 404\n    assert resposta.json()["detail"] == "solicitacao_nao_encontrada"\n\n\ndef test_cliente_pode_aceitar_cotacao(cliente: TestClient) -> None:\n    solicitacao_id, cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao[\'id\']}/aceitar",\n        json={"empresa_cliente_id": cliente_id},\n    )\n\n    assert resposta.status_code == 200\n    dados = resposta.json()\n    assert dados["status"] == "aceita"\n    assert dados["decidida_por_empresa_id"] == cliente_id\n    assert dados["encerrada_em"] is not None\n\n\ndef test_aceite_recusa_automaticamente_as_demais_cotacoes(\n    cliente: TestClient,\n) -> None:\n    solicitacao_id, cliente_id, fornecedor_id, processo_id, material_id = (\n        preparar_cenario(cliente)\n    )\n    outro_fornecedor = adicionar_fornecedor_compativel(\n        cliente,\n        processo_id,\n        material_id,\n        "22333444000155",\n        "Segundo Fornecedor Ltda",\n    )\n\n    primeira = criar_cotacao(\n        cliente,\n        solicitacao_id,\n        fornecedor_id,\n        "12000.00",\n    )\n    segunda = criar_cotacao(\n        cliente,\n        solicitacao_id,\n        outro_fornecedor,\n        "13000.00",\n    )\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{primeira[\'id\']}/aceitar",\n        json={"empresa_cliente_id": cliente_id},\n    )\n    assert resposta.status_code == 200\n\n    consulta = cliente.get(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes"\n    )\n    assert consulta.status_code == 200\n\n    por_id = {item["id"]: item for item in consulta.json()}\n    assert por_id[primeira["id"]]["status"] == "aceita"\n    assert por_id[segunda["id"]]["status"] == "recusada"\n    assert por_id[segunda["id"]]["decidida_por_empresa_id"] == cliente_id\n\n\ndef test_cliente_pode_recusar_cotacao(cliente: TestClient) -> None:\n    solicitacao_id, cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao[\'id\']}/recusar",\n        json={"empresa_cliente_id": cliente_id},\n    )\n\n    assert resposta.status_code == 200\n    assert resposta.json()["status"] == "recusada"\n    assert resposta.json()["decidida_por_empresa_id"] == cliente_id\n\n\ndef test_empresa_que_nao_e_cliente_nao_pode_decidir(\n    cliente: TestClient,\n) -> None:\n    solicitacao_id, _cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    outra_empresa = cadastrar_empresa(\n        cliente,\n        "66777888000199",\n        "cliente",\n        "Outro Cliente Ltda",\n    )\n\n    resposta = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao[\'id\']}/aceitar",\n        json={"empresa_cliente_id": outra_empresa},\n    )\n\n    assert resposta.status_code == 403\n    assert resposta.json()["detail"] == (\n        "empresa_nao_e_cliente_da_solicitacao"\n    )\n\n\ndef test_nao_pode_criar_nova_cotacao_depois_de_aceite(\n    cliente: TestClient,\n) -> None:\n    solicitacao_id, cliente_id, fornecedor_id, processo_id, material_id = (\n        preparar_cenario(cliente)\n    )\n    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    outro_fornecedor = adicionar_fornecedor_compativel(\n        cliente,\n        processo_id,\n        material_id,\n        "77888999000100",\n        "Terceiro Fornecedor Ltda",\n    )\n\n    aceite = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao[\'id\']}/aceitar",\n        json={"empresa_cliente_id": cliente_id},\n    )\n    assert aceite.status_code == 200\n\n    nova = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes",\n        json={\n            "empresa_fornecedora_id": outro_fornecedor,\n            "valor_total": "14000.00",\n            "prazo_dias": 15,\n            "validade_dias": 10,\n        },\n    )\n    assert nova.status_code == 409\n    assert nova.json()["detail"] == "solicitacao_ja_possui_cotacao_aceita"\n\n\ndef test_cotacao_decidida_nao_pode_ser_aceita_novamente(\n    cliente: TestClient,\n) -> None:\n    solicitacao_id, cliente_id, fornecedor_id, _processo_id, _material_id = (\n        preparar_cenario(cliente)\n    )\n    cotacao = criar_cotacao(cliente, solicitacao_id, fornecedor_id)\n\n    primeira = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao[\'id\']}/recusar",\n        json={"empresa_cliente_id": cliente_id},\n    )\n    segunda = cliente.post(\n        f"/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao[\'id\']}/aceitar",\n        json={"empresa_cliente_id": cliente_id},\n    )\n\n    assert primeira.status_code == 200\n    assert segunda.status_code == 409\n    assert segunda.json()["detail"] == "cotacao_nao_esta_pendente"\n'}


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(normalize(content), encoding="utf-8", newline="\n")
    os.replace(temp, path)


def is_cgx_root(root: Path) -> bool:
    return (root / "src" / "cgx").exists() or (root / "src" / "cgx_platform").exists()


def validar_ast(root: Path, rels: list[str]) -> list[str]:
    erros: list[str] = []
    for rel in rels:
        if not rel.endswith(".py"):
            continue
        path = root / rel
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            erros.append(f"{rel}: {type(exc).__name__}: {exc}")
    return erros


def migrar_banco_d7(db_path: Path) -> dict:
    resultado = {
        "database_exists": db_path.exists(),
        "database_migrated": False,
        "already_migrated": False,
        "rows_preserved": 0,
        "cotacao_1_preserved": False,
        "error": None,
    }

    if not db_path.exists():
        return resultado

    conexao = sqlite3.connect(str(db_path), timeout=10)
    try:
        conexao.execute("PRAGMA foreign_keys = OFF")
        tabela = conexao.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='cotacoes_fornecedor'"
        ).fetchone()

        if tabela is None:
            return resultado

        sql_atual = tabela[0] or ""
        colunas = {
            row[1]
            for row in conexao.execute(
                "PRAGMA table_info(cotacoes_fornecedor)"
            ).fetchall()
        }

        ja_migrado = (
            "encerrada_em" in colunas
            and "decidida_por_empresa_id" in colunas
            and "status IN ('enviada', 'aceita'" in sql_atual
        )
        if ja_migrado:
            resultado["already_migrated"] = True
            resultado["rows_preserved"] = conexao.execute(
                "SELECT COUNT(*) FROM cotacoes_fornecedor"
            ).fetchone()[0]
            resultado["cotacao_1_preserved"] = (
                conexao.execute(
                    "SELECT 1 FROM cotacoes_fornecedor WHERE id=1"
                ).fetchone()
                is not None
            )
            return resultado

        quantidade = conexao.execute(
            "SELECT COUNT(*) FROM cotacoes_fornecedor"
        ).fetchone()[0]

        # Uma única transação protege renomeação, reconstrução e cópia.
        conexao.execute("BEGIN IMMEDIATE")

        # Índices gerados pelo SQLAlchemy na tabela D6.
        conexao.execute(
            "DROP INDEX IF EXISTS ix_cotacoes_fornecedor_solicitacao_id"
        )
        conexao.execute(
            "DROP INDEX IF EXISTS ix_cotacoes_fornecedor_empresa_fornecedora_id"
        )
        conexao.execute(
            "ALTER TABLE cotacoes_fornecedor "
            "RENAME TO cotacoes_fornecedor_d6"
        )

        conexao.execute(
            """
            CREATE TABLE cotacoes_fornecedor (
                id INTEGER NOT NULL PRIMARY KEY,
                solicitacao_id INTEGER NOT NULL,
                empresa_fornecedora_id INTEGER NOT NULL,
                valor_total NUMERIC(14, 2) NOT NULL,
                prazo_dias INTEGER NOT NULL,
                validade_dias INTEGER NOT NULL,
                observacoes TEXT,
                status VARCHAR(16) NOT NULL DEFAULT 'enviada',
                criada_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                encerrada_em DATETIME,
                decidida_por_empresa_id INTEGER,
                CONSTRAINT uq_cotacao_solicitacao_fornecedor
                    UNIQUE (solicitacao_id, empresa_fornecedora_id),
                CONSTRAINT ck_cotacoes_valor_total
                    CHECK (valor_total > 0),
                CONSTRAINT ck_cotacoes_prazo
                    CHECK (prazo_dias > 0),
                CONSTRAINT ck_cotacoes_validade
                    CHECK (validade_dias > 0),
                CONSTRAINT ck_cotacoes_status
                    CHECK (
                        status IN (
                            'enviada',
                            'aceita',
                            'recusada',
                            'expirada',
                            'cancelada'
                        )
                    ),
                FOREIGN KEY (solicitacao_id)
                    REFERENCES solicitacoes_servico(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (empresa_fornecedora_id)
                    REFERENCES empresas(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY (decidida_por_empresa_id)
                    REFERENCES empresas(id)
                    ON DELETE RESTRICT
            )
            """
        )

        conexao.execute(
            """
            INSERT INTO cotacoes_fornecedor (
                id,
                solicitacao_id,
                empresa_fornecedora_id,
                valor_total,
                prazo_dias,
                validade_dias,
                observacoes,
                status,
                criada_em,
                encerrada_em,
                decidida_por_empresa_id
            )
            SELECT
                id,
                solicitacao_id,
                empresa_fornecedora_id,
                valor_total,
                prazo_dias,
                validade_dias,
                observacoes,
                status,
                criada_em,
                NULL,
                NULL
            FROM cotacoes_fornecedor_d6
            """
        )

        conexao.execute("DROP TABLE cotacoes_fornecedor_d6")
        conexao.execute(
            "CREATE INDEX ix_cotacoes_fornecedor_solicitacao_id "
            "ON cotacoes_fornecedor (solicitacao_id)"
        )
        conexao.execute(
            "CREATE INDEX ix_cotacoes_fornecedor_empresa_fornecedora_id "
            "ON cotacoes_fornecedor (empresa_fornecedora_id)"
        )
        conexao.execute(
            "CREATE INDEX ix_cotacoes_fornecedor_decidida_por_empresa_id "
            "ON cotacoes_fornecedor (decidida_por_empresa_id)"
        )

        conexao.commit()

        resultado["database_migrated"] = True
        resultado["rows_preserved"] = quantidade
        resultado["cotacao_1_preserved"] = (
            conexao.execute(
                "SELECT 1 FROM cotacoes_fornecedor WHERE id=1"
            ).fetchone()
            is not None
        )
        return resultado

    except Exception as exc:
        try:
            conexao.rollback()
        except Exception:
            pass
        resultado["error"] = f"{type(exc).__name__}: {exc}"
        return resultado
    finally:
        try:
            conexao.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        conexao.close()


def main() -> int:
    root = Path.cwd().resolve()
    print(f"{PROJECT_LABEL} — V0.1 D7 Decisão das Cotações")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    if is_cgx_root(root):
        print("ERRO: esta pasta parece ser a raiz do CGX Platform.")
        print("Execute este arquivo somente na raiz do projeto MEC-Servicos.")
        return 20

    conflicts: list[str] = []

    for rel, esperado_hash in EXPECTED_D6_HASHES.items():
        path = root / rel
        if not path.exists():
            conflicts.append(rel)
            continue

        try:
            atual_hash = sha256_text(path.read_text(encoding="utf-8"))
        except Exception:
            conflicts.append(rel)
            continue

        if atual_hash != esperado_hash:
            alvo = UPDATED_FILES.get(rel)
            if alvo is not None and atual_hash == sha256_text(alvo):
                continue
            conflicts.append(rel)

    if conflicts:
        conflitos = sorted(set(conflicts))
        print("ERRO: foram encontrados arquivos divergentes da baseline D6.")
        print("Nenhum arquivo foi alterado.")
        for rel in conflitos:
            print(f"  CONFLICT: {rel}")

        atomic_write(
            root / REPORT_TXT,
            "\n".join(
                [
                    f"{PROJECT_LABEL} — V0.1 D7",
                    f"REVISION={REVISION}",
                    f"ROOT={root}",
                    "STATUS=CONFLICT",
                    "NO_FILES_CHANGED=True",
                    "",
                    "CONFLICTS:",
                    *[f"  {item}" for item in conflitos],
                    "",
                ]
            ),
        )
        atomic_write(
            root / REPORT_JSON,
            json.dumps(
                {
                    "project": PROJECT_LABEL,
                    "revision": REVISION,
                    "status": "CONFLICT",
                    "root": str(root),
                    "conflicts": conflitos,
                    "no_files_changed": True,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )
        return 30

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / BACKUP_ROOT / f"V0_1_D7_DECISAO_COTACOES_{stamp}"
    backed_up: list[str] = []

    db_path = root / "data" / "mec_servicos.db"

    if db_path.exists():
        destino = backup_dir / "data" / db_path.name
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, destino)
        backed_up.append(str(db_path.relative_to(root)))

    for rel in UPDATED_FILES:
        path = root / rel
        destino = backup_dir / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destino)
        backed_up.append(rel)

    migration = migrar_banco_d7(db_path)

    if migration["error"]:
        print("ERRO: a migração do banco D7 falhou.")
        print(f"  {migration['error']}")
        print("Nenhum arquivo do projeto foi alterado.")
        print("O banco foi protegido por backup antes da tentativa.")

        atomic_write(
            root / REPORT_TXT,
            "\n".join(
                [
                    f"{PROJECT_LABEL} — V0.1 D7",
                    f"REVISION={REVISION}",
                    f"ROOT={root}",
                    "STATUS=DATABASE_MIGRATION_FAILED",
                    "PROJECT_FILES_CHANGED=False",
                    f"DATABASE_ERROR={migration['error']}",
                    f"BACKUP_DIR={backup_dir}",
                    "",
                ]
            ),
        )
        atomic_write(
            root / REPORT_JSON,
            json.dumps(
                {
                    "project": PROJECT_LABEL,
                    "revision": REVISION,
                    "status": "DATABASE_MIGRATION_FAILED",
                    "project_files_changed": False,
                    "database_migration": migration,
                    "backup_dir": str(backup_dir),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )
        return 40

    changed: list[str] = []
    for rel, content in UPDATED_FILES.items():
        atomic_write(root / rel, content)
        changed.append(rel)

    todos_alvos = list(UPDATED_FILES)
    faltantes = [rel for rel in todos_alvos if not (root / rel).exists()]
    divergentes: list[str] = []

    for rel, esperado in UPDATED_FILES.items():
        path = root / rel
        if path.exists() and normalize(path.read_text(encoding="utf-8")) != normalize(esperado):
            divergentes.append(rel)

    ast_erros = validar_ast(root, todos_alvos)
    files_ok = not faltantes and not divergentes
    ast_ok = not ast_erros
    status = "OK" if files_ok and ast_ok else "FAILED"

    relatorio = {
        "project": PROJECT_LABEL,
        "revision": REVISION,
        "script": SCRIPT_NAME,
        "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "status": status,
        "d6_baseline_verified": True,
        "files_ok": files_ok,
        "ast_ok": ast_ok,
        "changed": changed,
        "backed_up": backed_up,
        "backup_dir": str(backup_dir),
        "missing": faltantes,
        "content_mismatch": divergentes,
        "ast_errors": ast_erros,
        "database_migration": migration,
        "database_changed_by_script": bool(
            migration["database_migrated"]
        ),
        "lifecycle_statuses": [
            "enviada",
            "aceita",
            "recusada",
            "expirada",
            "cancelada",
        ],
        "new_endpoints": [
            "POST /api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/aceitar",
            "POST /api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/recusar",
        ],
    }

    atomic_write(
        root / REPORT_JSON,
        json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n",
    )

    linhas = [
        f"{PROJECT_LABEL} — V0.1 D7",
        f"REVISION={REVISION}",
        f"ROOT={root}",
        "",
        f"STATUS={status}",
        "D6_BASELINE_VERIFIED=True",
        f"FILES_OK={files_ok}",
        f"AST_OK={ast_ok}",
        f"CHANGED={len(changed)}",
        f"BACKED_UP={len(backed_up)}",
        f"DATABASE_MIGRATED={migration['database_migrated']}",
        f"DATABASE_ALREADY_MIGRATED={migration['already_migrated']}",
        f"ROWS_PRESERVED={migration['rows_preserved']}",
        f"COTACAO_1_PRESERVED={migration['cotacao_1_preserved']}",
        "",
        "CICLO_COTACAO:",
        "  enviada",
        "  aceita",
        "  recusada",
        "  expirada",
        "  cancelada",
        "",
        "REGRAS_D7:",
        "  somente a empresa cliente da solicitação pode decidir",
        "  uma solicitação pode ter no máximo uma cotação aceita",
        "  ao aceitar uma cotação, as demais pendentes são recusadas",
        "  cotação decidida não pode ser decidida novamente",
        "  cotação vencida passa para expirada",
        "  solicitação com cotação aceita não recebe novas cotações",
        "",
        "NOVOS_ENDPOINTS:",
        "  POST /api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/aceitar",
        "  POST /api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/recusar",
        "",
        "NAO_IMPLEMENTADO:",
        "  autenticação, negociação, contratação, pagamento e avaliação",
        "",
        "PROXIMO:",
        "  1. python -m pytest",
        "  2. python -m uvicorn backend.app.principal:app --reload",
        "  3. testar aceite e recusa no banco real",
        "",
    ]
    atomic_write(root / REPORT_TXT, "\n".join(linhas))

    print(f"FILES_OK= {files_ok}")
    print(f"AST_OK= {ast_ok}")
    print(f"CHANGED= {len(changed)}")
    print(f"BACKED_UP= {len(backed_up)}")
    print(f"DATABASE_MIGRATED= {migration['database_migrated']}")
    print(f"DATABASE_ALREADY_MIGRATED= {migration['already_migrated']}")
    print(f"ROWS_PRESERVED= {migration['rows_preserved']}")
    print(f"COTACAO_1_PRESERVED= {migration['cotacao_1_preserved']}")
    print(f"BACKUP_DIR= {backup_dir}")
    print(f"REPORT= {root / REPORT_TXT}")
    print(f"JSON= {root / REPORT_JSON}")

    if not files_ok or not ast_ok:
        print("ERRO: a validação estática do D7 falhou.")
        return 50

    print("D7_DECISAO_COTACOES_APPLIED= True")
    print("CICLO_VIDA_COTACAO_PREPARADO= True")
    print("ACEITE_RECUSA_PREPARADOS= True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
