r"""MEC-Serviços D27 — Acompanhamento de Produção nos portais.

Na raiz do MEC-Servicos, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D27_PORTAIS_PRODUCAO.py

Requer D10 e D26. O fornecedor registra etapas com observações; cliente
e fornecedor consultam a etapa atual, as datas e o histórico existente.
Mantém as cinco etapas D10, sem impor uma sequência de fabricação.
Ordens concluídas/canceladas permitem consultar o histórico.
Não cria dados de demonstração nem modifica ordens e históricos existentes.
Faz backup, valida o contrato, executa a suíte MEC e npm run build.
Em caso de falha, restaura os fontes alterados e frontend/dist.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REVISION = "MEC-SERVICOS-V0.1-D27-PORTAIS-PRODUCAO-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D27_PORTAIS_PRODUCAO_RELATORIO"
APP_REL = Path("frontend/src/App.tsx")
ROUTER_REL = Path("backend/app/api/roteador.py")
DIST_REL = Path("frontend/dist")
FONTES = {
  "backend/app/api/rotas/portal_producao.py": "from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, Path, Query, status\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.api.rotas.etapas_producao import registrar_etapa_producao\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.etapa_producao import EtapaProducaoCriacao, EtapaProducaoLeitura\nfrom backend.app.schemas.portal_producao import AcompanhamentoPortalLeitura, EtapaPortalCriacao, ProducaoPortalPagina\nfrom backend.app.services.portal_producao import ServicoPortalProducao\n\nroteador = APIRouter(tags=[\"acompanhamento de produção dos portais\"])\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\nEmpresaId = Annotated[int, Query(gt=0)]\nRecursoId = Annotated[int, Path(gt=0)]\nDeslocamento = Annotated[int, Query(ge=0)]\nLimite = Annotated[int, Query(ge=1, le=100)]\n\n\n@roteador.get(\"/portal-cliente/producao\", response_model=ProducaoPortalPagina)\ndef listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,\n                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> ProducaoPortalPagina:\n    return ServicoPortalProducao(banco).listar(empresa_cliente_id, \"cliente\", deslocamento, limite)\n\n\n@roteador.get(\"/portal-fornecedor/producao\", response_model=ProducaoPortalPagina)\ndef listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,\n                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> ProducaoPortalPagina:\n    return ServicoPortalProducao(banco).listar(empresa_fornecedora_id, \"fornecedor\", deslocamento, limite)\n\n\n@roteador.get(\"/portal-cliente/producao/{ordem_id}\", response_model=AcompanhamentoPortalLeitura)\ndef obter_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> AcompanhamentoPortalLeitura:\n    return ServicoPortalProducao(banco).obter(ordem_id, empresa_cliente_id, \"cliente\")\n\n\n@roteador.get(\"/portal-fornecedor/producao/{ordem_id}\", response_model=AcompanhamentoPortalLeitura)\ndef obter_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> AcompanhamentoPortalLeitura:\n    return ServicoPortalProducao(banco).obter(ordem_id, empresa_fornecedora_id, \"fornecedor\")\n\n\n@roteador.post(\"/portal-fornecedor/producao/{ordem_id}/etapas\",\n               response_model=EtapaProducaoLeitura, status_code=status.HTTP_201_CREATED)\ndef registrar(ordem_id: RecursoId, dados: EtapaPortalCriacao, banco: SessaoBanco) -> EtapaProducaoLeitura:\n    ServicoPortalProducao(banco).preparar_registro(ordem_id, dados.empresa_fornecedora_id, dados.ultima_etapa_id)\n    criacao = EtapaProducaoCriacao(empresa_fornecedora_id=dados.empresa_fornecedora_id,\n                                 etapa=dados.etapa, observacoes=dados.observacoes)\n    return registrar_etapa_producao(ordem_id, criacao, banco)\n",
  "backend/app/schemas/portal_producao.py": "from __future__ import annotations\n\nfrom datetime import datetime\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\nfrom backend.app.schemas.etapa_producao import EtapaProducaoCriacao, EtapaProducaoLeitura\nfrom backend.app.schemas.portal_ordens_servico import OrdemPortalLeitura\n\n\nclass OrdemProducaoLeitura(OrdemPortalLeitura):\n    etapa_atual: str | None\n    ultima_etapa_id: int\n    etapa_atual_em: datetime | None\n    total_atualizacoes: int\n\n\nclass ProducaoPortalPagina(BaseModel):\n    itens: list[OrdemProducaoLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n\n\nclass AcompanhamentoPortalLeitura(BaseModel):\n    ordem: OrdemProducaoLeitura\n    etapa_atual: str | None\n    ultima_etapa_id: int\n    historico: list[EtapaProducaoLeitura]\n\n\nclass EtapaPortalCriacao(EtapaProducaoCriacao):\n    model_config = ConfigDict(extra=\"forbid\")\n    observacoes: str | None = Field(default=None, max_length=5000)\n    ultima_etapa_id: int = Field(ge=0)\n",
  "backend/app/services/portal_producao.py": "from __future__ import annotations\n\nfrom fastapi import HTTPException\nfrom sqlalchemy import func, select, update\nfrom sqlalchemy.orm import Session, aliased\n\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.etapa_producao import EtapaProducao\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.schemas.etapa_producao import EtapaProducaoLeitura\nfrom backend.app.schemas.portal_producao import (\n    AcompanhamentoPortalLeitura, OrdemProducaoLeitura, ProducaoPortalPagina,\n)\nfrom backend.app.services.etapa_producao import ServicoEtapaProducao\nfrom backend.app.services.portal_contratacoes import Perfil\nfrom backend.app.services.portal_ordens_servico import ServicoPortalOrdens\n\n\nclass ServicoPortalProducao:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.ordens = ServicoPortalOrdens(banco)\n\n    def _consulta(self):\n        resumo = select(EtapaProducao.ordem_servico_id.label(\"ordem_id\"),\n                        func.max(EtapaProducao.id).label(\"ultima_id\"),\n                        func.count(EtapaProducao.id).label(\"quantidade\")).group_by(EtapaProducao.ordem_servico_id).subquery()\n        atual = aliased(EtapaProducao)\n        return self.ordens._consulta().add_columns(atual.etapa, atual.id, atual.criada_em, resumo.c.quantidade).outerjoin(\n            resumo, resumo.c.ordem_id == OrdemServico.id).outerjoin(atual, atual.id == resumo.c.ultima_id)\n\n    def _ordem(self, linha) -> OrdemProducaoLeitura:\n        etapa, etapa_id, instante, quantidade = linha[-4:]\n        return OrdemProducaoLeitura(**self.ordens._ordem(linha[:-4]).model_dump(),\n            etapa_atual=etapa, ultima_etapa_id=etapa_id or 0, etapa_atual_em=instante, total_atualizacoes=quantidade or 0)\n\n    def listar(self, empresa: int, perfil: Perfil, deslocamento: int, limite: int) -> ProducaoPortalPagina:\n        self.ordens.contratos.validar_empresa(empresa, perfil)\n        consulta = self._consulta().where(self.ordens._dono(empresa, perfil))\n        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0\n        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()\n        return ProducaoPortalPagina(itens=[self._ordem(linha) for linha in linhas], total=total,\n                                  deslocamento=deslocamento, limite=limite)\n\n    def obter(self, ordem_id: int, empresa: int, perfil: Perfil) -> AcompanhamentoPortalLeitura:\n        self.ordens.contratos.validar_empresa(empresa, perfil)\n        linha = self.banco.execute(self._consulta().where(OrdemServico.id == ordem_id, self.ordens._dono(empresa, perfil))).first()\n        if linha is None:\n            raise HTTPException(404, detail=\"ordem_servico_nao_encontrada\")\n        ordem = self._ordem(linha)\n        historico = [EtapaProducaoLeitura.model_validate(item) for item in ServicoEtapaProducao(self.banco).listar(ordem_id)]\n        ultima = historico[-1] if historico else None\n        ordem = ordem.model_copy(update={\"etapa_atual\": ultima.etapa if ultima else None,\n            \"ultima_etapa_id\": ultima.id if ultima else 0, \"etapa_atual_em\": ultima.criada_em if ultima else None,\n            \"total_atualizacoes\": len(historico)})\n        return AcompanhamentoPortalLeitura(ordem=ordem, etapa_atual=ordem.etapa_atual,\n                                          ultima_etapa_id=ordem.ultima_etapa_id, historico=historico)\n\n    def preparar_registro(self, ordem_id: int, empresa: int, ultima_etapa_id: int) -> None:\n        ordem = self.ordens.obter(ordem_id, empresa, \"fornecedor\")\n        if ordem.contratacao_status != \"ativa\":\n            raise HTTPException(409, detail=\"contratacao_nao_esta_ativa\")\n        if ordem.status not in {\"aberta\", \"em_execucao\"}:\n            raise HTTPException(409, detail=\"ordem_servico_nao_pode_atualizar_producao\")\n        contrato_ativo = select(ContratacaoServico.id).where(\n            ContratacaoServico.id == OrdemServico.contratacao_id, ContratacaoServico.status == \"ativa\",\n            ContratacaoServico.empresa_fornecedora_id == empresa).correlate(OrdemServico).exists()\n        # A atualização sem mudança de estado serializa registros desta ordem\n        # com outras atualizações do portal e as ações de execução do D26.\n        travada = self.banco.execute(update(OrdemServico).where(\n            OrdemServico.id == ordem_id, OrdemServico.empresa_fornecedora_id == empresa,\n            OrdemServico.status.in_((\"aberta\", \"em_execucao\")), contrato_ativo,\n        ).values(status=OrdemServico.status), execution_options={\"synchronize_session\": False})\n        if travada.rowcount != 1:\n            self.banco.rollback()\n            raise HTTPException(409, detail=\"ordem_servico_alterada_atualize\")\n        atual_id = self.banco.scalar(select(func.max(EtapaProducao.id)).where(EtapaProducao.ordem_servico_id == ordem_id)) or 0\n        if atual_id != ultima_etapa_id:\n            self.banco.rollback()\n            raise HTTPException(409, detail=\"producao_alterada_atualize\")\n",
  "frontend/src/pages/producao/PortalProducaoPage.css": ".p27-page { color: #dce7f7; display: flex; flex-direction: column; gap: 22px; width: 100%; }\n.p27-page * { box-sizing: border-box; }\n.p27-page h1, .p27-page h2, .p27-page h3, .p27-page p { margin: 0; }\n.p27-page h1 { color: #edf3fc; font-size: clamp(28px, 3vw, 40px); line-height: 1.25; margin: 10px 0 12px; }\n.p27-page h2 { font-size: 19px; color: #e9f0fc; }\n.p27-page h3 { color: #c6d8ef; font-size: 14px; margin: 22px 0 10px; }\n.p27-page p { color: #91a8c8; line-height: 1.6; }\n.p27-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }\n.p27-page .p27-eyebrow { display: flex; align-items: center; gap: 9px; color: #6ba6ff; font-size: 12px; font-weight: 800; letter-spacing: .09em; }\n.p27-button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 11px 15px; background: #162333; border: 1px solid #31465f; border-radius: 8px; color: #dce9fc; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; text-decoration: none; line-height: 1.4; }\n.p27-button:hover:enabled, a.p27-button:hover { background: #213754; border-color: #6592cc; }\n.p27-button:focus-visible, .p27-form textarea:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.p27-button:disabled { opacity: .45; cursor: default; }\n.p27-primary { background: #2563eb; border-color: #357bf5; color: #fff; }\n.p27-primary:hover:enabled { background: #3475fb; }\n.p27-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }\n.p27-summary article { display: flex; flex-direction: column; gap: 12px; padding: 23px; background: linear-gradient(145deg, #162235, #101b2b); border: 1px solid #2b3c53; border-radius: 13px; }\n.p27-summary span { color: #a6c0e2; font-size: 13px; }\n.p27-summary strong { font-size: 31px; color: #f2f6fe; }\n.p27-summary small { color: #7794ba; line-height: 1.5; }\n.p27-tabs { display: flex; flex-wrap: wrap; gap: 9px; }\n.p27-tab-active { background: #193658; border-color: #4976b0; }\n.p27-panel { background: #111c2a; border: 1px solid #293d56; border-radius: 13px; overflow: hidden; }\n.p27-section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 23px; }\n.p27-section-head p { font-size: 13px; margin-top: 10px; }\n.p27-section-head > svg { color: #79aef5; flex-shrink: 0; }\n.p27-table-wrap { overflow-x: auto; }\n.p27-page table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; }\n.p27-page th { color: #819fc5; background: #0e1825; padding: 17px 20px; font-weight: 700; white-space: nowrap; }\n.p27-page td { padding: 19px 20px; border-top: 1px solid #26384e; color: #d5e4f7; overflow-wrap: anywhere; }\n.p27-page td strong { color: #e8f1ff; font-size: 13px; }\n.p27-page td small { display: block; color: #7899c2; margin-top: 9px; font-size: 11px; line-height: 1.5; }\n.p27-page .p27-selected { background: #192d46; }\n.p27-nowrap { white-space: nowrap; }\n.p27-badge { display: inline-block; padding: 7px 10px; border-radius: 18px; background: #223245; font-size: 11px; font-weight: 800; white-space: nowrap; }\n.p27-status-ativa, .p27-status-concluida { background: #173d31; color: #80deae; }\n.p27-status-cancelada { background: #42303b; color: #e4a1b9; }\n.p27-status-em_execucao { background: #203956; color: #99c6ff; }\n.p27-empty { min-height: 235px; padding: 45px 24px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 15px; text-align: center; }\n.p27-empty svg { color: #669dea; }\n.p27-empty h3 { font-size: 18px; margin: 0; color: #d9e9ff; }\n.p27-empty p { max-width: 680px; font-size: 13px; }\n.p27-pagination { padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; gap: 14px; border-top: 1px solid #293d56; color: #8fa9cb; font-size: 12px; }\n.p27-pagination > div { display: flex; gap: 9px; }\n.p27-columns { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 22px; align-items: start; }\n.p27-detail { padding: 23px; }\n.p27-detail .p27-section-head, .p27-dialog .p27-section-head { padding: 0; margin-bottom: 22px; }\n.p27-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }\n.p27-fields > div { border: 1px solid #2b3e56; background: #0d1724; border-radius: 9px; padding: 15px; min-width: 0; }\n.p27-fields dt { color: #819fc4; font-size: 11px; margin-bottom: 10px; }\n.p27-fields dd { color: #e2ecfa; font-size: 13px; font-weight: 700; margin: 0; line-height: 1.6; overflow-wrap: anywhere; }\n.p27-fields .p27-value { font-size: 19px; }\n.p27-wide { grid-column: 1 / -1; }\n.p27-page .p27-observacoes { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; margin-bottom: 20px; }\n.p27-form { margin-top: 22px; }\n.p27-form fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }\n.p27-form label { display: block; color: #b2c9e7; font-size: 12px; font-weight: 700; margin-bottom: 10px; }\n.p27-form textarea { display: block; width: 100%; border: 1px solid #37506e; border-radius: 9px; background: #0b1523; color: #e6f0ff; padding: 13px; font: inherit; font-size: 13px; resize: vertical; line-height: 1.7; }\n.p27-form p { font-size: 12px; margin: 14px 0; }\n.p27-form button[type=\"submit\"] { width: 100%; margin-top: 8px; }\n.p27-page .p27-alert { display: flex; align-items: flex-start; gap: 11px; padding: 15px 18px; border-radius: 9px; font-size: 13px; }\n.p27-alert svg { flex-shrink: 0; }\n.p27-page .p27-success { color: #a1e8c4; background: #143028; border: 1px solid #276148; }\n.p27-page .p27-error { color: #ffbdc6; background: #37212a; border: 1px solid #703c4c; }\n.p27-files-head { margin-top: 28px; }\n.p27-files-head h3 { margin: 0; }\n.p27-files { padding: 0; margin: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }\n.p27-files li { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 9px; border: 1px solid #30445f; background: #0d1724; }\n.p27-files li > svg { color: #79aef5; flex-shrink: 0; }\n.p27-files li > span { flex: 1; min-width: 0; }\n.p27-files strong { font-size: 12px; overflow-wrap: anywhere; }\n.p27-files small { color: #7695bd; font-size: 11px; display: block; margin-top: 6px; }\n.p27-dialog { color: #e4edfa; background: #111e30; border: 1px solid #466891; border-radius: 14px; padding: 26px; width: min(600px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto; box-shadow: 0 24px 90px #0009; }\n.p27-dialog::backdrop { background: #020814c9; }\n.p27-dialog p { font-size: 13px; margin-bottom: 20px; }\n.p27-dialog h3 { margin-top: 20px; }\n.p27-dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 24px; }\n.p27-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }\n@media (max-width: 1100px) { .p27-columns { grid-template-columns: minmax(0, 1fr); } }\n@media (max-width: 650px) { .p27-header { flex-direction: column; } .p27-summary { grid-template-columns: minmax(0, 1fr); } .p27-tabs { flex-direction: column; } .p27-detail, .p27-section-head { padding: 18px; } .p27-pagination { flex-wrap: wrap; } .p27-fields { grid-template-columns: minmax(0, 1fr); } .p27-files li { flex-wrap: wrap; } .p27-files li .p27-button { width: 100%; } .p27-dialog { padding: 20px; } }\n.p27-status-aberta { background: #4a3c20; color: #f0cd83; }\n.p27-operacao { display: flex; flex-direction: column; gap: 16px; margin-top: 24px; }\n.p27-operacao p { font-size: 13px; }\n.p27-dialog .p27-review-note { margin-top: 20px; }\n.p27-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }\n.p27-summary .p27-summary-stage { font-size: 20px; line-height: 1.5; }\n.p27-detail .p27-section-head h2 { display: flex; align-items: center; gap: 9px; }\n.p27-stage-current { background: #203956; color: #99c6ff; }\n.p27-stage-ready { background: #173d31; color: #80deae; }\n.p27-current { display: flex; align-items: center; gap: 10px; font-weight: 700; }\n.p27-form select { display: block; width: 100%; color: #e6f0ff; background: #0b1523; border: 1px solid #37506e; border-radius: 9px; padding: 13px; font: inherit; font-size: 13px; margin-bottom: 20px; }\n.p27-form select:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.p27-readonly { margin-top: 22px !important; padding: 16px; border: 1px solid #31465f; border-radius: 9px; }\n.p27-history h3 { margin-top: 0; }\n.p27-history-empty { display: flex; align-items: center; gap: 12px; border: 1px dashed #31465f; border-radius: 9px; padding: 24px; }\n.p27-timeline { padding: 0; margin: 0; list-style: none; }\n.p27-timeline li { position: relative; padding: 0 0 22px 25px; margin-left: 5px; border-left: 2px solid #2e4665; }\n.p27-timeline li:last-child { border-left-color: transparent; }\n.p27-timeline-dot { position: absolute; left: -6px; top: 17px; width: 10px; height: 10px; border-radius: 50%; background: #79aef5; }\n.p27-timeline article { border: 1px solid #2d4564; border-radius: 10px; background: #0d1724; padding: 19px; }\n.p27-timeline h4 { margin: 0 0 9px; font-size: 14px; color: #dfeafd; }\n.p27-timeline time { display: block; color: #8ea8ca; font-size: 12px; margin-bottom: 14px; }\n.p27-timeline .p27-observacoes { margin-bottom: 0; }\n@media (max-width: 850px) { .p27-summary { grid-template-columns: minmax(0, 1fr); } }\n",
  "frontend/src/pages/producao/PortalProducaoPage.tsx": "import { useEffect, useRef, useState, type FormEvent } from \"react\";\nimport { Link } from \"react-router-dom\";\nimport { CheckCircle2, ClipboardList, Clock3, Factory, History, RefreshCw, Wrench, X } from \"lucide-react\";\nimport { useAuth } from \"../../auth/AuthContext\";\nimport { api } from \"../../services/api\";\nimport { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from \"../client/cotacoesCliente\";\nimport { formatarMedidaContrato, rotuloContratacao, type PaginaContratacoes } from \"../contratacoes/contratacoesPortal\";\nimport { rotuloOrdem, type PerfilOrdens } from \"../ordens/ordensPortal\";\nimport { ETAPAS_PRODUCAO, etapaValida, mensagemErroProducao, rotuloEtapa, type AcompanhamentoProducao, type EtapaProducao, type EtapaValor, type OrdemProducao } from \"./producaoPortal\";\nimport \"./PortalProducaoPage.css\";\n\ntype Revisao = { chave: string; dono: string; ordem: OrdemProducao; etapa: EtapaValor; observacoes: string | null; ultimaId: number };\n\nfunction dataHoraEtapa(valor: string): string | undefined {\n  const instante = instanteUtc(valor);\n  return instante === null ? undefined : new Date(instante).toISOString();\n}\n\nexport default function PortalProducaoPage({ perfil }: { perfil: PerfilOrdens }) {\n  const { user } = useAuth();\n  const empresaId = user?.role === perfil ? user.id : 0;\n  const dono = `${perfil}:${empresaId}`;\n  const base = `/portal-${perfil}/producao`;\n  const [deslocamento, setDeslocamento] = useState(0);\n  const [atualizacao, setAtualizacao] = useState(0);\n  const [lista, setLista] = useState<{ chave: string; pagina: PaginaContratacoes<OrdemProducao> } | null>(null);\n  const [selecionadoId, setSelecionadoId] = useState(0);\n  const [carregando, setCarregando] = useState(true);\n  const [erroLista, setErroLista] = useState(\"\");\n  const [detalhe, setDetalhe] = useState<{ chave: string; dados: AcompanhamentoProducao } | null>(null);\n  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);\n  const [erroDetalhe, setErroDetalhe] = useState(\"\");\n  const [atualizacaoDetalhe, setAtualizacaoDetalhe] = useState(0);\n  const [rascunho, setRascunho] = useState({ chave: \"\", etapa: \"\", observacoes: \"\" });\n  const [revisao, setRevisao] = useState<Revisao | null>(null);\n  const [enviando, setEnviando] = useState(false);\n  const [aviso, setAviso] = useState<{ dono: string; texto: string } | null>(null);\n  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);\n  const [revalidar, setRevalidar] = useState(\"\");\n  const chaveLista = `${dono}:${deslocamento}:${atualizacao}`;\n  const pagina = lista?.chave === chaveLista ? lista.pagina : null;\n  const selecionada = pagina?.itens.find((o) => o.id === selecionadoId) ?? pagina?.itens[0];\n  const chaveSelecao = `${dono}:${selecionada?.id ?? 0}`;\n  const chaveDetalhe = `${chaveLista}:${chaveSelecao}:${atualizacaoDetalhe}`;\n  const dados = detalhe?.chave === chaveDetalhe ? detalhe.dados : null;\n  const ordem = dados?.ordem ?? selecionada;\n  const rascunhoAtual = rascunho.chave === chaveSelecao ? rascunho : { etapa: \"\", observacoes: \"\" };\n  const podeRegistrar = perfil === \"fornecedor\" && dados?.ordem.contratacao_status === \"ativa\" && [\"aberta\", \"em_execucao\"].includes(dados.ordem.status);\n  const bloquear = enviando || carregando || carregandoDetalhe || !dados || revalidar === chaveDetalhe;\n  const modalAtual = revisao?.chave === chaveDetalhe && revisao.dono === dono && podeRegistrar && !bloquear ? revisao\n    : revisao?.chave === chaveDetalhe && revisao.dono === dono && podeRegistrar && enviando ? revisao : null;\n  const parametrosEmpresa = perfil === \"cliente\" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };\n  const contexto = useRef({ chaveLista, chaveDetalhe, dono });\n  contexto.current = { chaveLista, chaveDetalhe, dono };\n  const montada = useRef(true);\n  const trava = useRef(false);\n  const envio = useRef<AbortController | null>(null);\n  const dialogo = useRef<HTMLDialogElement | null>(null);\n\n  useEffect(() => {\n    montada.current = true;\n    return () => { montada.current = false; envio.current?.abort(); };\n  }, []);\n\n  useEffect(() => { setDeslocamento(0); setSelecionadoId(0); setRevisao(null); envio.current?.abort(); }, [perfil, empresaId]);\n\n  useEffect(() => {\n    const controlador = new AbortController(); let vigente = true;\n    setCarregando(true); setErroLista(\"\"); setRevisao(null);\n    if (!empresaId) {\n      setErroLista(`Entre como ${perfil} para consultar a produção.`); setCarregando(false);\n      return () => { vigente = false; controlador.abort(); };\n    }\n    async function carregar() {\n      try {\n        const { data } = await api.get<PaginaContratacoes<OrdemProducao>>(base, {\n          params: { ...parametrosEmpresa, deslocamento, limite: 20 }, signal: controlador.signal, timeout: 20_000,\n        });\n        if (!vigente || contexto.current.chaveLista !== chaveLista) return;\n        if (data.total > 0 && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }\n        if (data.total === 0 && deslocamento > 0) { setDeslocamento(0); return; }\n        const proprias = data.itens.filter((o) => (perfil === \"cliente\" ? o.empresa_cliente_id : o.empresa_fornecedora_id) === empresaId);\n        setLista({ chave: chaveLista, pagina: { ...data, itens: proprias } });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.chaveLista === chaveLista) setErroLista(mensagemErroProducao(erro));\n      } finally { if (vigente && contexto.current.chaveLista === chaveLista) setCarregando(false); }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, perfil, empresaId, deslocamento, chaveLista]);\n\n  useEffect(() => {\n    const controlador = new AbortController(); let vigente = true;\n    setCarregandoDetalhe(Boolean(selecionada)); setErroDetalhe(\"\"); setRevisao(null);\n    if (!selecionada) return () => { vigente = false; controlador.abort(); };\n    const ordemId = selecionada.id;\n    async function carregar() {\n      try {\n        const { data } = await api.get<AcompanhamentoProducao>(`${base}/${ordemId}`, {\n          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,\n        });\n        if (!vigente || contexto.current.chaveDetalhe !== chaveDetalhe) return;\n        const empresa = perfil === \"cliente\" ? data.ordem.empresa_cliente_id : data.ordem.empresa_fornecedora_id;\n        if (data.ordem.id !== ordemId || empresa !== empresaId || data.historico.some((e) => e.ordem_servico_id !== ordemId)) throw new Error(\"Acompanhamento divergente.\");\n        setDetalhe({ chave: chaveDetalhe, dados: data });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.chaveDetalhe === chaveDetalhe) setErroDetalhe(mensagemErroProducao(erro));\n      } finally { if (vigente && contexto.current.chaveDetalhe === chaveDetalhe) setCarregandoDetalhe(false); }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, perfil, empresaId, selecionada?.id, chaveDetalhe]);\n\n  useEffect(() => {\n    const elemento = dialogo.current;\n    if (!elemento) return;\n    if (modalAtual && !elemento.open) elemento.showModal();\n    if (!modalAtual && elemento.open) elemento.close();\n  }, [modalAtual]);\n\n  function revisar(evento: FormEvent<HTMLFormElement>) {\n    evento.preventDefault();\n    if (!dados || !podeRegistrar || bloquear || trava.current) return;\n    if (!etapaValida(rascunhoAtual.etapa) || rascunhoAtual.observacoes.length > 5000) {\n      setAviso({ dono, texto: \"Selecione uma etapa e limite as observações a 5000 caracteres.\" }); return;\n    }\n    setAviso(null); setSucesso(null);\n    setRevisao({ chave: chaveDetalhe, dono, ordem: dados.ordem, etapa: rascunhoAtual.etapa,\n      observacoes: rascunhoAtual.observacoes.trim() || null, ultimaId: dados.ultima_etapa_id });\n  }\n\n  async function confirmar() {\n    if (!modalAtual || bloquear || trava.current) return;\n    const confirmado = modalAtual; const controlador = new AbortController();\n    envio.current = controlador; trava.current = true; setEnviando(true); setAviso(null);\n    try {\n      const { data } = await api.post<EtapaProducao>(`/portal-fornecedor/producao/${confirmado.ordem.id}/etapas`, {\n        empresa_fornecedora_id: empresaId, etapa: confirmado.etapa, observacoes: confirmado.observacoes, ultima_etapa_id: confirmado.ultimaId,\n      }, { signal: controlador.signal, timeout: 30_000 });\n      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== confirmado.dono || contexto.current.chaveDetalhe !== confirmado.chave) return;\n      if (data.ordem_servico_id !== confirmado.ordem.id || data.empresa_fornecedora_id !== empresaId || data.etapa !== confirmado.etapa) throw new Error(\"Registro de produção divergente.\");\n      setSucesso({ dono, texto: `${rotuloEtapa(data.etapa)} registrada na OS #${data.ordem_servico_id}. O cliente já pode consultar a atualização.` });\n      setRascunho({ chave: \"\", etapa: \"\", observacoes: \"\" }); setRevisao(null); setAtualizacao((v) => v + 1);\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.dono === confirmado.dono && contexto.current.chaveDetalhe === confirmado.chave) {\n        const status = typeof erro === \"object\" && erro !== null && \"response\" in erro ? (erro as { response?: { status?: number } }).response?.status : undefined;\n        const incerta = !status || status >= 500;\n        setAviso({ dono, texto: incerta ? \"O registro não pôde ser confirmado. Atualize o histórico e confira se a etapa já aparece antes de tentar novamente.\" : mensagemErroProducao(erro) });\n        if (incerta || status === 409) setRevalidar(chaveDetalhe);\n        setRevisao(null);\n      }\n    } finally {\n      if (envio.current === controlador) envio.current = null;\n      trava.current = false; if (montada.current) setEnviando(false);\n    }\n  }\n\n  return <main className=\"p27-page\">\n    <header className=\"p27-header\"><div><p className=\"p27-eyebrow\"><Factory size={16} /> PORTAL DO {perfil === \"cliente\" ? \"CLIENTE\" : \"FORNECEDOR\"}</p>\n      <h1>Acompanhamento de Produção</h1><p>{perfil === \"cliente\" ? \"Consulte a etapa atual e o histórico dos seus serviços.\" : \"Registre as etapas e mantenha seus clientes informados sobre a produção.\"}</p></div>\n      <button className=\"p27-button\" disabled={enviando || carregando} onClick={() => { setAviso(null); setAtualizacao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>\n    {sucesso?.dono === dono && <p className=\"p27-alert p27-success\" role=\"status\"><CheckCircle2 size={18} /> {sucesso.texto}</p>}\n    {aviso?.dono === dono && <p className=\"p27-alert p27-error\" role=\"alert\">{aviso.texto}</p>}\n    {erroLista && <p className=\"p27-alert p27-error\" role=\"alert\">{erroLista}</p>}\n    <div className=\"p27-summary\"><article><span>Ordens da sua empresa</span><strong>{pagina ? pagina.total : \"—\"}</strong><small>Inclui ordens abertas, em execução e finalizadas</small></article>\n      <article><span>Etapa da OS selecionada</span><strong className=\"p27-summary-stage\">{ordem ? rotuloEtapa(ordem.etapa_atual) : \"—\"}</strong><small>{ordem ? `OS #${ordem.id} · ${rotuloOrdem(ordem.status)}` : \"Selecione uma ordem de serviço\"}</small></article>\n      <article><span>Atualizações desta OS</span><strong>{ordem?.total_atualizacoes ?? \"—\"}</strong><small>{ordem?.etapa_atual_em ? `Último registro: ${formatarInstanteCotacao(instanteUtc(ordem.etapa_atual_em))}` : \"Ainda sem registro de etapa\"}</small></article></div>\n    <nav className=\"p27-tabs\"><Link className=\"p27-button\" to={`/${perfil}/ordens-servico`}><Wrench size={16} /> Ordens de Serviço e arquivos técnicos</Link></nav>\n    <section className=\"p27-panel\" aria-busy={carregando}><div className=\"p27-section-head\"><div><h2>Produção dos serviços</h2><p>Selecione a ordem para acompanhar as etapas registradas pelo fornecedor.</p></div></div>\n      {carregando ? <div className=\"p27-empty\" role=\"status\">Carregando ordens…</div>\n        : !erroLista && pagina?.itens.length === 0 ? <div className=\"p27-empty\"><Factory size={32} /><h3>Nenhuma ordem disponível</h3><p>{perfil === \"cliente\" ? \"Gere uma ordem de serviço a partir de uma contratação ativa para acompanhar a produção.\" : \"O cliente precisa gerar a ordem de serviço para que ela apareça neste acompanhamento.\"}</p></div>\n        : pagina && <div className=\"p27-table-wrap\"><table><thead><tr><th>Ordem / referência</th><th>{perfil === \"cliente\" ? \"Fornecedor\" : \"Cliente\"}</th><th>Etapa de produção</th><th>Situação da OS</th><th>Última atualização</th><th><span className=\"p27-sr-only\">Ações</span></th></tr></thead><tbody>\n          {pagina.itens.map((linha) => { const selecionada = linha.id === ordem?.id; const atual = selecionada && dados ? dados.ordem : linha;\n            return <tr key={linha.id} className={selecionada ? \"p27-selected\" : \"\"}><td><strong>OS #{linha.id}</strong><small>Solicitação #{linha.solicitacao_id} · Contratação #{linha.contratacao_id}</small></td>\n              <td>{perfil === \"cliente\" ? linha.fornecedor_razao_social : linha.cliente_razao_social}<small>{linha.processo_nome} · {linha.material_nome}</small></td>\n              <td><span className={`p27-badge ${atual.etapa_atual === \"pronto_para_envio\" ? \"p27-stage-ready\" : \"p27-stage-current\"}`}>{rotuloEtapa(atual.etapa_atual)}</span></td>\n              <td>{rotuloOrdem(linha.status)}</td><td>{atual.etapa_atual_em ? formatarInstanteCotacao(instanteUtc(atual.etapa_atual_em)) : \"—\"}</td>\n              <td><button className=\"p27-button\" disabled={enviando} aria-pressed={selecionada} onClick={() => setSelecionadoId(linha.id)}>{selecionada ? \"Selecionada\" : \"Ver histórico\"}</button></td></tr>;\n          })}</tbody></table></div>}\n      {pagina && pagina.total > 0 && <div className=\"p27-pagination\"><span>{deslocamento + 1}–{Math.min(deslocamento + pagina.itens.length, pagina.total)} de {pagina.total}</span><div>\n        <button className=\"p27-button\" disabled={enviando || carregando || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => Math.max(0, v - 20)); }}>Anterior</button>\n        <button className=\"p27-button\" disabled={enviando || carregando || deslocamento + 20 >= pagina.total} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => v + 20); }}>Próxima</button></div></div>}\n    </section>\n    {selecionada && <section className=\"p27-panel p27-detail\" aria-busy={carregandoDetalhe}><div className=\"p27-section-head\"><h2><History size={20} /> Histórico da OS #{selecionada.id}</h2><button className=\"p27-button\" disabled={enviando || carregandoDetalhe} onClick={() => { setAviso(null); setAtualizacaoDetalhe((v) => v + 1); }}>Atualizar histórico</button></div>\n      {carregandoDetalhe ? <p role=\"status\">Carregando histórico…</p> : erroDetalhe ? <p className=\"p27-alert p27-error\" role=\"alert\">{erroDetalhe}</p> : dados && <>\n        <div className=\"p27-columns\"><div><dl className=\"p27-fields\"><div><dt>Cliente</dt><dd>{dados.ordem.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{dados.ordem.fornecedor_razao_social}</dd></div>\n          <div><dt>Valor total</dt><dd>{formatarValorCotacao(dados.ordem.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{dados.ordem.prazo_dias} dias</dd></div>\n          <div><dt>Quantidade da ordem</dt><dd>{dados.ordem.quantidade} unidades</dd></div><div><dt>Contratação</dt><dd>#{dados.ordem.contratacao_id} · {rotuloContratacao(dados.ordem.contratacao_status)}</dd></div>\n          <div><dt>Processo da ordem</dt><dd>{dados.ordem.processo_nome}</dd></div><div><dt>Material da ordem</dt><dd>{dados.ordem.material_nome}</dd></div>\n          <div className=\"p27-wide\"><dt>Dimensões máximas X / Y / Z</dt><dd>{[dados.ordem.solicitacao.dimensao_x_maxima_mm,dados.ordem.solicitacao.dimensao_y_maxima_mm,dados.ordem.solicitacao.dimensao_z_maxima_mm].map((v) => formatarMedidaContrato(v)).join(\" × \")} mm</dd></div></dl>\n          <h3>Etapa atual</h3><p className=\"p27-current\"><Factory size={18} /> {rotuloEtapa(dados.etapa_atual)}</p>\n          {perfil === \"fornecedor\" && (podeRegistrar ? <form className=\"p27-form\" onSubmit={revisar}><fieldset disabled={bloquear}>\n            <label htmlFor=\"p27-etapa\">Etapa de produção</label><select id=\"p27-etapa\" required value={rascunhoAtual.etapa} onChange={(e) => setRascunho({ chave: chaveSelecao, etapa: e.target.value, observacoes: rascunhoAtual.observacoes })}><option value=\"\">Selecione a etapa atual</option>{ETAPAS_PRODUCAO.map((e) => <option key={e.valor} value={e.valor}>{e.rotulo}</option>)}</select>\n            <label htmlFor=\"p27-observacoes\">Observações da atualização (opcional)</label><textarea id=\"p27-observacoes\" maxLength={5000} rows={4} value={rascunhoAtual.observacoes} onChange={(e) => setRascunho({ chave: chaveSelecao, etapa: rascunhoAtual.etapa, observacoes: e.target.value })} placeholder=\"Informe o andamento, uma previsão ou um detalhe relevante para o cliente.\" />\n            <p>Escolha a etapa que representa a situação atual. Cada registro será acrescentado ao histórico.</p><button type=\"submit\" className=\"p27-button p27-primary\" disabled={bloquear || !etapaValida(rascunhoAtual.etapa)}><ClipboardList size={16} /> Revisar atualização</button>\n          </fieldset></form> : <p className=\"p27-readonly\">{dados.ordem.contratacao_status !== \"ativa\" ? \"A contratação está finalizada. O histórico continua disponível para consulta.\" : \"Esta ordem está concluída ou cancelada. O histórico continua disponível para consulta.\"}</p>)}\n          {perfil === \"cliente\" && <p className=\"p27-readonly\">As etapas são registradas pelo fornecedor responsável. Use Atualizar histórico para conferir novos registros.</p>}\n        </div><div className=\"p27-history\"><h3>Atualizações registradas</h3>\n          {dados.historico.length === 0 ? <div className=\"p27-history-empty\"><Clock3 size={25} /><p>Nenhuma etapa de produção registrada para esta ordem.</p></div> : <ol className=\"p27-timeline\">{dados.historico.slice().reverse().map((etapa) => <li key={etapa.id}><span className=\"p27-timeline-dot\" /><article><h4>{rotuloEtapa(etapa.etapa)}</h4><time dateTime={dataHoraEtapa(etapa.criada_em)}>{formatarInstanteCotacao(instanteUtc(etapa.criada_em))}</time><p className=\"p27-observacoes\">{etapa.observacoes || \"Sem observações.\"}</p></article></li>)}</ol>}\n        </div></div>\n      </>}\n    </section>}\n    <dialog ref={dialogo} className=\"p27-dialog\" aria-labelledby=\"p27-dialog-title\" onCancel={(e) => { if (trava.current) e.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>\n      {modalAtual && <><div className=\"p27-section-head\"><h2 id=\"p27-dialog-title\">Confirmar atualização de produção</h2><button className=\"p27-button\" aria-label=\"Fechar revisão\" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>\n        <p>Confira a etapa e as observações que o cliente poderá consultar.</p><dl className=\"p27-fields\"><div><dt>Ordem de serviço</dt><dd>#{modalAtual.ordem.id}</dd></div><div><dt>Solicitação</dt><dd>#{modalAtual.ordem.solicitacao_id}</dd></div><div className=\"p27-wide\"><dt>Nova etapa</dt><dd>{rotuloEtapa(modalAtual.etapa)}</dd></div></dl>\n        <h3>Observações da atualização</h3><p className=\"p27-observacoes\">{modalAtual.observacoes || \"Sem observações.\"}</p><p>Este registro será acrescentado ao histórico da ordem.</p>\n        <div className=\"p27-dialog-actions\"><button className=\"p27-button\" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button><button className=\"p27-button p27-primary\" disabled={enviando} onClick={() => void confirmar()}>{enviando ? \"Registrando…\" : \"Confirmar atualização\"}</button></div>\n      </>}\n    </dialog>\n  </main>;\n}\n",
  "frontend/src/pages/producao/producaoPortal.ts": "import type { OrdemPortal } from \"../ordens/ordensPortal\";\n\nexport const ETAPAS_PRODUCAO = [\n  { valor: \"aguardando_material\", rotulo: \"Aguardando material\" },\n  { valor: \"em_usinagem\", rotulo: \"Em usinagem\" },\n  { valor: \"em_solda_dobra\", rotulo: \"Em solda/dobra\" },\n  { valor: \"em_acabamento\", rotulo: \"Em acabamento\" },\n  { valor: \"pronto_para_envio\", rotulo: \"Pronto para envio\" },\n] as const;\nexport type EtapaValor = typeof ETAPAS_PRODUCAO[number][\"valor\"];\nexport type EtapaProducao = {\n  id: number; ordem_servico_id: number; empresa_fornecedora_id: number;\n  etapa: string; observacoes: string | null; criada_em: string;\n};\nexport type OrdemProducao = OrdemPortal & {\n  etapa_atual: string | null; ultima_etapa_id: number; etapa_atual_em: string | null; total_atualizacoes: number;\n};\nexport type AcompanhamentoProducao = {\n  ordem: OrdemProducao; etapa_atual: string | null; ultima_etapa_id: number; historico: EtapaProducao[];\n};\n\nexport function rotuloEtapa(etapa: string | null): string {\n  return ETAPAS_PRODUCAO.find((item) => item.valor === etapa)?.rotulo ?? (etapa ? \"Etapa indisponível\" : \"Sem etapa registrada\");\n}\n\nexport function etapaValida(valor: string): valor is EtapaValor {\n  return ETAPAS_PRODUCAO.some((item) => item.valor === valor);\n}\n\nexport function mensagemErroProducao(erro: unknown): string {\n  if (typeof erro === \"object\" && erro !== null && \"response\" in erro) {\n    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;\n    const mensagens: Record<string, string> = {\n      empresa_cliente_nao_encontrada: \"A empresa cliente deste acesso não foi encontrada.\",\n      empresa_fornecedor_nao_encontrada: \"A empresa fornecedora deste acesso não foi encontrada.\",\n      empresa_nao_e_cliente: \"Entre como cliente para consultar a produção dos seus serviços.\",\n      empresa_nao_e_fornecedor: \"Entre como fornecedor para consultar e atualizar a produção dos seus serviços.\",\n      ordem_servico_nao_encontrada: \"A ordem não está disponível para esta empresa. Atualize a lista.\",\n      contratacao_nao_esta_ativa: \"A contratação precisa estar ativa para registrar etapas. Atualize a tela.\",\n      ordem_servico_nao_pode_atualizar_producao: \"Ordens concluídas ou canceladas permitem consultar o histórico. Atualize a tela.\",\n      empresa_nao_e_fornecedora_da_ordem_servico: \"Somente o fornecedor responsável pode atualizar esta ordem.\",\n      producao_alterada_atualize: \"A produção já recebeu outra atualização. Atualize o histórico e confira a etapa atual antes de continuar.\",\n      ordem_servico_alterada_atualize: \"A ordem foi alterada durante a operação. Atualize a tela antes de continuar.\",\n    };\n    if (typeof detalhe === \"string\") return mensagens[detalhe] ?? \"Não foi possível concluir a operação. Atualize a tela e tente novamente.\";\n    if (Array.isArray(detalhe)) return \"Selecione uma etapa válida e limite as observações a 5000 caracteres.\";\n  }\n  return \"Não foi possível consultar os dados. Confira a conexão e atualize a tela.\";\n}\n",
  "tests/test_portal_producao.py": "from __future__ import annotations\n\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi import FastAPI\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine, event, select, update\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos\nfrom backend.app.api.rotas.ordens_servico import roteador as original\nfrom backend.app.api.rotas.portal_ordens_servico import roteador as ordens\nfrom backend.app.api.rotas.portal_producao import roteador as portal\nfrom backend.app.api.rotas.etapas_producao import roteador as etapas\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.etapa_producao import EtapaProducao\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\nfrom backend.app.services.portal_ordens_servico import ServicoPortalOrdens\nfrom backend.app.services.portal_producao import ServicoPortalProducao\n\nCLIENTE = \"/api/v1/portal-cliente\"\nFORNECEDOR = \"/api/v1/portal-fornecedor\"\n\n\ndef novo_contrato(banco, numero, cliente=1, fornecedor=2, situacao=\"ativa\"):\n    pedido = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,\n        dimensao_x_maxima_mm=500, dimensao_y_maxima_mm=300, dimensao_z_maxima_mm=250,\n        tolerancia_requerida_mm=Decimal(\"0.0200\"), quantidade=5, status=\"encerrada\", observacoes=\"Pedido D27.\")\n    banco.add(pedido)\n    banco.flush()\n    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=numero, empresa_fornecedora_id=fornecedor,\n        valor_total=Decimal(\"1250.50\"), prazo_dias=15, validade_dias=10, status=\"aceita\",\n        decidida_por_empresa_id=cliente, encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None))\n    banco.add(cotacao)\n    banco.flush()\n    contrato = ContratacaoServico(id=numero, solicitacao_id=numero, cotacao_id=numero,\n        empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, valor_total=Decimal(\"1250.50\"),\n        prazo_dias=15, status=situacao, observacoes=\"Termos da contratação D27.\")\n    banco.add(contrato)\n    banco.flush()\n    return contrato\n\n\n@pytest.fixture()\ndef ambiente(tmp_path, monkeypatch):\n    engine = create_engine(\"sqlite://\", connect_args={\"check_same_thread\": False}, poolclass=StaticPool)\n\n    @event.listens_for(engine, \"connect\")\n    def chaves(conexao, _):\n        conexao.execute(\"PRAGMA foreign_keys=ON\")\n\n    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)\n    Base.metadata.create_all(engine)\n    monkeypatch.setattr(ServicoArquivoTecnico, \"STORAGE_ROOT\", tmp_path)\n    with sessoes() as banco:\n        banco.add_all([\n            Empresa(id=1, razao_social=\"Cliente D27\", documento=\"cliente-d27-1\", tipo_empresa=\"cliente\"),\n            Empresa(id=2, razao_social=\"Fornecedor D27\", documento=\"fornecedor-d27-2\", tipo_empresa=\"fornecedor\"),\n            Empresa(id=3, razao_social=\"Outro Fornecedor\", documento=\"fornecedor-d27-3\", tipo_empresa=\"fornecedor\"),\n            Empresa(id=4, razao_social=\"Empresa Ambos\", documento=\"ambos-d27-4\", tipo_empresa=\"ambos\"),\n            Empresa(id=5, razao_social=\"Outro Cliente\", documento=\"cliente-d27-5\", tipo_empresa=\"cliente\"),\n            ProcessoFabricacao(id=1, codigo=\"cnc-d27\", nome=\"Usinagem CNC\"),\n            Material(id=1, codigo=\"al6061-d27\", nome=\"Alumínio 6061\"),\n        ])\n        banco.commit()\n        novo_contrato(banco, 1)\n        novo_contrato(banco, 2, cliente=5, fornecedor=3)\n        novo_contrato(banco, 3, situacao=\"cancelada\")\n        novo_contrato(banco, 4, situacao=\"encerrada\")\n        novo_contrato(banco, 5)\n        banco.commit()\n\n    def banco_teste():\n        with sessoes() as banco:\n            yield banco\n\n    app = FastAPI()\n    for roteador in (arquivos, original, ordens, etapas, portal):\n        app.include_router(roteador, prefix=\"/api/v1\")\n    app.dependency_overrides[obter_banco] = banco_teste\n    try:\n        with TestClient(app) as http:\n            yield http, sessoes\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(engine)\n        engine.dispose()\n\n\ndef gerar(http, contrato=1, cliente=1, **extra):\n    return http.post(f\"{CLIENTE}/contratacoes/{contrato}/ordem-servico\", json={\"empresa_cliente_id\": cliente, **extra})\n\n\ndef listar(http, perfil=\"cliente\", empresa=1, **extra):\n    return http.get(f\"/api/v1/portal-{perfil}/ordens-servico\", params={\n        \"empresa_cliente_id\" if perfil == \"cliente\" else \"empresa_fornecedora_id\": empresa, **extra,\n    })\n\n\ndef candidatas(http, cliente=1, **extra):\n    return http.get(CLIENTE + \"/contratacoes-para-ordem\", params={\"empresa_cliente_id\": cliente, **extra})\n\n\ndef agir(http, ordem, acao=\"iniciar\", fornecedor=2):\n    return http.post(f\"{FORNECEDOR}/ordens-servico/{ordem}/{acao}\", json={\"empresa_fornecedora_id\": fornecedor})\n\n\ndef producao(http, perfil=\"cliente\", empresa=1, **extra):\n    return http.get(f\"/api/v1/portal-{perfil}/producao\", params={\n        \"empresa_cliente_id\" if perfil == \"cliente\" else \"empresa_fornecedora_id\":empresa, **extra,\n    })\n\n\ndef detalhe(http, ordem, perfil=\"cliente\", empresa=1):\n    return http.get(f\"/api/v1/portal-{perfil}/producao/{ordem}\", params={\n        \"empresa_cliente_id\" if perfil == \"cliente\" else \"empresa_fornecedora_id\":empresa,\n    })\n\n\ndef registrar(http, ordem, etapa=\"aguardando_material\", fornecedor=2, ultima=0, **extra):\n    return http.post(f\"{FORNECEDOR}/producao/{ordem}/etapas\", json={\n        \"empresa_fornecedora_id\":fornecedor, \"etapa\":etapa, \"ultima_etapa_id\":ultima,\n        \"observacoes\":\"Material em compra.\", **extra,\n    })\n\n\ndef test_ordens_sem_etapas_sao_listadas_so_para_os_donos(ambiente):\n    http, _ = ambiente\n    oid = gerar(http).json()[\"id\"]\n    item = producao(http).json()[\"itens\"][0]\n    assert item == producao(http,\"fornecedor\",2).json()[\"itens\"][0]\n    assert item[\"id\"] == oid and item[\"etapa_atual\"] is None and item[\"ultima_etapa_id\"] == 0\n    assert item[\"total_atualizacoes\"] == 0 and item[\"etapa_atual_em\"] is None\n    assert item[\"fornecedor_razao_social\"] == \"Fornecedor D27\"\n    assert producao(http,\"cliente\",5).json()[\"total\"] == 0\n    assert producao(http,\"fornecedor\",3).json()[\"total\"] == 0\n    dados = detalhe(http,oid).json()\n    assert dados[\"historico\"] == [] and dados[\"ordem\"][\"id\"] == oid\n\n\n@pytest.mark.parametrize(\"etapa\", [\"aguardando_material\",\"em_usinagem\",\"em_solda_dobra\",\"em_acabamento\",\"pronto_para_envio\"])\ndef test_etapas_d10_normalizadas_e_preservadas_no_historico(ambiente, etapa):\n    http, sessoes = ambiente\n    oid = gerar(http).json()[\"id\"]\n    resposta = registrar(http,oid,etapa=\"  \" + etapa.upper() + \"  \")\n    assert resposta.status_code == 201 and resposta.json()[\"etapa\"] == etapa\n    novo = resposta.json()\n    for perfil,empresa in ((\"cliente\",1),(\"fornecedor\",2)):\n        dados = detalhe(http,oid,perfil,empresa).json()\n        assert dados[\"etapa_atual\"] == etapa and dados[\"ultima_etapa_id\"] == novo[\"id\"]\n        assert dados[\"historico\"][0] == novo\n        resumo = producao(http,perfil,empresa).json()[\"itens\"][0]\n        assert resumo[\"total_atualizacoes\"] == 1 and resumo[\"ultima_etapa_id\"] == novo[\"id\"]\n        assert resumo[\"etapa_atual_em\"] == novo[\"criada_em\"]\n    with sessoes() as banco:\n        assert banco.get(OrdemServico,oid).status == \"aberta\"\n        assert banco.get(OrdemServico,oid).iniciada_em is None\n        assert banco.get(ContratacaoServico,1).status == \"ativa\"\n\n\ndef test_historico_pode_incluir_observacoes_e_etapas_alternativas(ambiente):\n    http, _ = ambiente\n    oid = gerar(http).json()[\"id\"]\n    ids=[]\n    for etapa,nota in ((\"aguardando_material\",\"Material em compra.\"),(\"em_solda_dobra\",\"Etapa adequada ao serviço.\"),(\"em_acabamento\",\"Acabamento iniciado.\")):\n        resp = registrar(http,oid,etapa,ultima=ids[-1] if ids else 0,observacoes=nota)\n        assert resp.status_code == 201\n        ids.append(resp.json()[\"id\"])\n    dados = detalhe(http,oid).json()\n    assert [item[\"id\"] for item in dados[\"historico\"]] == ids\n    assert dados[\"etapa_atual\"] == \"em_acabamento\"\n    assert dados[\"historico\"][1][\"observacoes\"] == \"Etapa adequada ao serviço.\"\n    assert dados[\"ordem\"][\"total_atualizacoes\"] == 3\n\n\ndef test_repeticao_com_versao_antiga_nao_duplica_etapa(ambiente):\n    http, sessoes = ambiente\n    oid = gerar(http).json()[\"id\"]\n    primeira = registrar(http,oid).json()\n    repetida = registrar(http,oid)\n    assert repetida.status_code == 409 and repetida.json()[\"detail\"] == \"producao_alterada_atualize\"\n    with sessoes() as banco:\n        assert len(banco.scalars(select(EtapaProducao)).all()) == 1\n    atualizada = registrar(http,oid,ultima=primeira[\"id\"],observacoes=\"Compra confirmada.\")\n    assert atualizada.status_code == 201\n    assert len(detalhe(http,oid).json()[\"historico\"]) == 2\n\n\ndef test_repetir_mesma_etapa_com_nova_observacao_e_permitido_apos_atualizar(ambiente):\n    http, _ = ambiente\n    oid = gerar(http).json()[\"id\"]\n    primeiro = registrar(http,oid).json()[\"id\"]\n    assert registrar(http,oid,ultima=primeiro,observacoes=\"Material atrasado pelo distribuidor.\").status_code == 201\n    historico = detalhe(http,oid).json()[\"historico\"]\n    assert len(historico) == 2 and historico[0][\"observacoes\"] != historico[1][\"observacoes\"]\n\n\n@pytest.mark.parametrize(\"fornecedor,codigo\", [(3,404),(1,403),(999,404)])\ndef test_fornecedor_incorreto_nao_pode_registrar(ambiente, fornecedor, codigo):\n    http, sessoes = ambiente\n    oid = gerar(http).json()[\"id\"]\n    assert registrar(http,oid,fornecedor=fornecedor).status_code == codigo\n    with sessoes() as banco:\n        assert banco.scalars(select(EtapaProducao)).all() == []\n\n\n@pytest.mark.parametrize(\"perfil,empresa\", [(\"cliente\",5),(\"fornecedor\",3)])\ndef test_detalhe_de_outra_empresa_nao_expoe_historico(ambiente, perfil, empresa):\n    http, _ = ambiente\n    oid = gerar(http).json()[\"id\"]\n    registrar(http,oid)\n    assert detalhe(http,oid,perfil,empresa).status_code == 404\n\n\n@pytest.mark.parametrize(\"situacao\", [\"concluida\",\"cancelada\"])\ndef test_ordem_finalizada_tem_historico_mas_nao_recebe_novos_registros(ambiente, situacao):\n    http, sessoes = ambiente\n    oid = gerar(http).json()[\"id\"]\n    etapa = registrar(http,oid).json()[\"id\"]\n    with sessoes() as banco:\n        banco.get(OrdemServico,oid).status=situacao\n        banco.commit()\n    resposta = registrar(http,oid,\"em_usinagem\",ultima=etapa)\n    assert resposta.status_code == 409\n    assert resposta.json()[\"detail\"] == \"ordem_servico_nao_pode_atualizar_producao\"\n    dados = detalhe(http,oid).json()\n    assert len(dados[\"historico\"]) == 1 and dados[\"ordem\"][\"status\"] == situacao\n\n\n@pytest.mark.parametrize(\"situacao\", [\"cancelada\",\"encerrada\"])\ndef test_contrato_inativo_bloqueia_registro_sem_apagar_historico(ambiente, situacao):\n    http, sessoes = ambiente\n    oid = gerar(http).json()[\"id\"]\n    registrar(http,oid)\n    with sessoes() as banco:\n        banco.get(ContratacaoServico,1).status=situacao\n        banco.commit()\n    resp = registrar(http,oid,\"em_usinagem\",ultima=1)\n    assert resp.status_code == 409 and resp.json()[\"detail\"] == \"contratacao_nao_esta_ativa\"\n    assert len(detalhe(http,oid).json()[\"historico\"]) == 1\n\n\ndef test_resumo_atual_por_ordem_paginacao_e_contagem_nao_misturam_historicos(ambiente):\n    http, _ = ambiente\n    a=gerar(http).json()[\"id\"]\n    b=gerar(http,5).json()[\"id\"]\n    aid=registrar(http,a).json()[\"id\"]\n    registrar(http,b,\"em_usinagem\")\n    registrar(http,a,\"em_acabamento\",ultima=aid)\n    primeira=producao(http,limite=1).json()\n    segunda=producao(http,deslocamento=1,limite=1).json()\n    assert primeira[\"total\"] == segunda[\"total\"] == 2\n    assert primeira[\"itens\"][0][\"id\"] == b and primeira[\"itens\"][0][\"total_atualizacoes\"] == 1\n    assert primeira[\"itens\"][0][\"etapa_atual\"] == \"em_usinagem\"\n    assert segunda[\"itens\"][0][\"id\"] == a and segunda[\"itens\"][0][\"total_atualizacoes\"] == 2\n    assert segunda[\"itens\"][0][\"etapa_atual\"] == \"em_acabamento\"\n\n\n@pytest.mark.parametrize(\"campos\", [{\"etapa\":\"inexistente\"},{\"observacoes\":\"x\"*5001},{\"ultima_etapa_id\":-1},\n                                   {\"empresa_cliente_id\":1},{\"empresa_fornecedora_id\":0}])\ndef test_corpo_invalido_nao_grava(ambiente, campos):\n    http, sessoes = ambiente\n    oid=gerar(http).json()[\"id\"]\n    assert registrar(http,oid,**campos).status_code == 422\n    with sessoes() as banco:\n        assert banco.scalars(select(EtapaProducao)).all() == []\n\n\ndef test_registro_exige_versao_e_empresa_do_fornecedor(ambiente):\n    http, _ = ambiente\n    oid=gerar(http).json()[\"id\"]\n    url=f\"{FORNECEDOR}/producao/{oid}/etapas\"\n    assert http.post(url,json={\"empresa_fornecedora_id\":2,\"etapa\":\"em_usinagem\"}).status_code == 422\n    assert http.post(url,json={\"empresa_cliente_id\":1,\"etapa\":\"em_usinagem\",\"ultima_etapa_id\":0}).status_code == 422\n    assert http.post(f\"{CLIENTE}/producao/{oid}/etapas\",json={\"etapa\":\"em_usinagem\"}).status_code == 404\n\n\n@pytest.mark.parametrize(\"parametros,codigo\", [({},422),({\"empresa_cliente_id\":0},422),\n    ({\"empresa_cliente_id\":1,\"limite\":101},422),({\"empresa_cliente_id\":1,\"deslocamento\":-1},422),\n    ({\"empresa_cliente_id\":2},403),({\"empresa_cliente_id\":999},404)])\ndef test_consulta_valida_empresa_e_paginacao(ambiente, parametros, codigo):\n    http, _ = ambiente\n    assert http.get(CLIENTE+\"/producao\",params=parametros).status_code == codigo\n\n\ndef test_etapas_do_d10_existente_sao_visiveis_sem_migracao(ambiente):\n    http, _ = ambiente\n    oid=gerar(http).json()[\"id\"]\n    old=http.post(f\"/api/v1/ordens-servico/{oid}/etapas-producao\",json={\n        \"empresa_fornecedora_id\":2,\"etapa\":\"em_usinagem\",\"observacoes\":\"Registro anterior ao D27.\"})\n    assert old.status_code == 201\n    dados=detalhe(http,oid).json()\n    assert dados[\"historico\"][0]==old.json()\n    assert dados[\"ultima_etapa_id\"]==old.json()[\"id\"]\n    assert registrar(http,oid,\"em_acabamento\").status_code == 409\n\n\ndef test_empresa_ambos_utiliza_cada_perfil_sem_expor_outros(ambiente):\n    http,sessoes=ambiente\n    with sessoes() as banco:\n        novo_contrato(banco,6,cliente=4,fornecedor=4)\n        banco.commit()\n    oid=gerar(http,6,4).json()[\"id\"]\n    assert registrar(http,oid,fornecedor=4).status_code == 201\n    assert producao(http,\"cliente\",4).json()[\"total\"] == 1\n    assert producao(http,\"fornecedor\",4).json()[\"total\"] == 1\n\n\ndef test_registrar_etapas_em_execucao_e_concluir_no_d26_mantem_historico(ambiente):\n    http,_=ambiente\n    oid=gerar(http).json()[\"id\"]\n    assert agir(http,oid).status_code == 200\n    eid=registrar(http,oid,\"em_usinagem\").json()[\"id\"]\n    pronta=registrar(http,oid,\"pronto_para_envio\",ultima=eid)\n    assert pronta.status_code == 201\n    assert detalhe(http,oid).json()[\"ordem\"][\"status\"] == \"em_execucao\"\n    assert agir(http,oid,\"concluir\").status_code == 200\n    dados=detalhe(http,oid).json()\n    assert dados[\"ordem\"][\"status\"] == \"concluida\"\n    assert dados[\"etapa_atual\"] == \"pronto_para_envio\" and len(dados[\"historico\"]) == 2\n"
}
ALVOS = (APP_REL, ROUTER_REL, *(Path(nome) for nome in FONTES))
IMPORT_LINE = 'import PortalProducaoPage from "./pages/producao/PortalProducaoPage";'


VALIDACAO_PORTAIS = r'''
from backend.app.principal import app

documento = app.openapi()
paths = documento["paths"]

def schema(valor):
    vistos = set()
    while "$ref" in valor:
        ref = valor["$ref"]
        if ref in vistos or not ref.startswith("#/"):
            raise RuntimeError("Referência OpenAPI inesperada.")
        vistos.add(ref)
        valor = documento
        for parte in ref[2:].split("/"):
            valor = valor[parte.replace("~1", "/").replace("~0", "~")]
    return valor

def campos(valor, nomes):
    ausentes = set(nomes) - set(schema(valor).get("properties", {}))
    if ausentes:
        raise RuntimeError("Campos ausentes no portal de produção: " + ", ".join(sorted(ausentes)))

for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    base = "/api/v1/portal-" + perfil + "/producao"
    for sufixo in ("", "/{ordem_id}"):
        op = paths.get(base + sufixo, {}).get("get")
        if not op:
            raise RuntimeError("Rota de produção do portal ausente: " + base + sufixo)
        params = {p["name"]: p for p in op.get("parameters", [])}
        if not params.get(empresa, {}).get("required"):
            raise RuntimeError("Consulta de produção sem empresa obrigatória.")
        dados = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
        if sufixo:
            campos(dados, ("ordem", "etapa_atual", "ultima_etapa_id", "historico"))
            dados = schema(dados["properties"]["ordem"])
        else:
            campos(dados, ("itens", "total", "limite", "deslocamento"))
            if not {"limite", "deslocamento"}.issubset(params):
                raise RuntimeError("Listagem de produção sem paginação.")
            dados = schema(schema(dados["properties"]["itens"])["items"])
        campos(dados, ("id", "contratacao_id", "empresa_cliente_id", "empresa_fornecedora_id", "status",
                       "cliente_razao_social", "fornecedor_razao_social", "etapa_atual", "ultima_etapa_id",
                       "etapa_atual_em", "total_atualizacoes"))
op = paths.get("/api/v1/portal-fornecedor/producao/{ordem_id}/etapas", {}).get("post")
if not op:
    raise RuntimeError("Registro de etapa do portal do fornecedor ausente.")
corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
campos(corpo, ("empresa_fornecedora_id", "etapa", "observacoes", "ultima_etapa_id"))
if set(corpo.get("required", [])) != {"empresa_fornecedora_id", "etapa", "ultima_etapa_id"}:
    raise RuntimeError("Registro sem empresa e versão obrigatórias.")
campos(op["responses"]["201"]["content"]["application/json"]["schema"], ("id", "ordem_servico_id", "etapa", "criada_em"))
print("PRODUCAO_CLIENTE_FORNECEDOR_PAGINADA_OK=True")
print("ETAPA_ATUAL_HISTORICO_E_REGISTRO_FORNECEDOR_OK=True")
print("CONTROLE_ATUALIZACAO_CONCORRENTE_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/api/roteador.py",
        "backend/app/models/etapa_producao.py", "backend/app/services/etapa_producao.py",
        "backend/app/schemas/etapa_producao.py", "backend/app/api/rotas/etapas_producao.py",
        "backend/app/services/portal_ordens_servico.py", "backend/app/schemas/portal_ordens_servico.py",
        "backend/app/api/rotas/portal_ordens_servico.py",
        "frontend/src/App.tsx", "frontend/package.json", "frontend/src/auth/AuthContext.tsx",
        "frontend/src/services/api.ts", "frontend/src/pages/ordens/PortalOrdensServicoPage.tsx",
        "frontend/src/pages/ordens/ordensPortal.ts", "frontend/src/pages/contratacoes/contratacoesPortal.ts",
        "frontend/src/pages/client/cotacoesCliente.ts", "tests/test_acompanhamento_producao.py",
        "tests/test_portal_ordens_servico.py",
    )
    ausentes = [nome for nome in obrigatorios if not (raiz / nome).is_file()]
    if ausentes:
        raise RuntimeError("Execute na raiz do MEC-Servicos com D10 e D26 instalados. Arquivos ausentes: " + ", ".join(ausentes))
    return raiz


def validar_fontes_existentes(originais: dict[Path, bytes | None]) -> None:
    for nome, fonte in FONTES.items():
        if nome.endswith(".py"):
            ast.parse(fonte, filename=nome)
        anterior = originais[Path(nome)]
        if anterior is not None:
            texto = anterior.decode("utf-8-sig").replace("\r\n", "\n").rstrip()
            if texto != fonte.replace("\r\n", "\n").rstrip():
                raise RuntimeError("Já existe um arquivo diferente no destino D27. Ele foi preservado: " + nome)


def atualizar_roteador(texto: str) -> str:
    arvore = ast.parse(texto)
    modulo = "backend.app.api.rotas.portal_producao"
    alias = "roteador_portal_producao"
    importacoes = [n for n in arvore.body if isinstance(n, ast.ImportFrom) and n.module == modulo]
    for n in importacoes:
        if len(n.names) != 1 or n.names[0].name != "roteador" or n.names[0].asname != alias:
            raise RuntimeError("O import do portal de produção já usa outro formato. O roteador foi preservado.")
    if len(importacoes) > 1:
        raise RuntimeError("Há imports duplicados do portal de produção.")
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "roteador_api" and n.func.attr == "include_router"
                and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == alias]
    if len(chamadas) > 1 or any(n.keywords or len(n.args) != 1 for n in chamadas):
        raise RuntimeError("O registro do portal de produção já usa outro formato.")
    if not any(isinstance(n, ast.Name) and n.id == "roteador_api" and isinstance(n.ctx, ast.Store) for n in ast.walk(arvore)):
        raise RuntimeError("Não encontrei a definição de roteador_api. Nenhum fonte foi alterado.")
    quebra = "\r\n" if "\r\n" in texto else "\n"
    atualizado = texto
    if not importacoes:
        if any(isinstance(n, ast.Name) and n.id == alias for n in ast.walk(arvore)):
            raise RuntimeError("O nome do novo roteador já está em uso. Nenhum fonte foi alterado.")
        linhas = texto.splitlines(keepends=True)
        fim = 0
        for n in arvore.body:
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) and fim == 0:
                fim = n.end_lineno
            elif isinstance(n, ast.ImportFrom) and n.module == "__future__":
                fim = n.end_lineno
            else:
                break
        linhas.insert(fim, f"from {modulo} import roteador as {alias}" + quebra)
        atualizado = "".join(linhas)
    if not chamadas:
        atualizado = atualizado.rstrip("\r\n") + quebra + f"roteador_api.include_router({alias})" + quebra
    ast.parse(atualizado)
    return atualizado


def atualizar_app(texto: str) -> str:
    rotas = localizar_rotas(texto)
    trocas = []
    for perfil in ("cliente", "fornecedor"):
        grupos = [item for item in rotas if item["path"] == "/" + perfil and not item["auto_fecha"]]
        if len(grupos) != 1:
            raise RuntimeError("Não encontrei um único grupo /" + perfil + " em App.tsx. Nenhum fonte foi alterado.")
        grupo = grupos[0]
        candidatas = [item for item in rotas if grupo["fim_abertura"] <= item["inicio"] < item["fim"] <= grupo["fim"] and item["path"] == "producao"]
        if len(candidatas) != 1 or not candidatas[0]["auto_fecha"]:
            raise RuntimeError("Não encontrei uma única rota de produção no portal " + perfil + ".")
        rota = candidatas[0]
        abertura = texto[rota["inicio"]:rota["fim"]]
        componentes = list(re.finditer(r"<(?:ModulePage|PortalProducaoPage)\b", abertura))
        if len(componentes) != 1:
            raise RuntimeError("A rota de produção do " + perfil + " usa outra tela. Ela foi preservada.")
        inicio = rota["inicio"] + componentes[0].start()
        fim = fim_tag(texto, inicio)
        if not texto[inicio:fim].rstrip().endswith("/>"):
            raise RuntimeError("O componente de produção do " + perfil + " possui filhos. Ele foi preservado.")
        novo = f'<PortalProducaoPage perfil="{perfil}" />'
        if texto[inicio:fim] != novo:
            trocas.append((inicio, fim, novo))
    atualizado = texto
    for inicio, fim, novo in sorted(trocas, reverse=True):
        atualizado = atualizado[:inicio] + novo + atualizado[fim:]
    existente = re.search(r'''import\s+PortalProducaoPage\s+from\s*["']\./pages/producao/PortalProducaoPage["']\s*;?''', atualizado)
    if not existente:
        if "./pages/producao/PortalProducaoPage" in atualizado:
            raise RuntimeError("O import de produção usa outro formato. Nenhum fonte foi alterado.")
        quebra = "\r\n" if "\r\n" in atualizado else "\n"
        atualizado = IMPORT_LINE + quebra + atualizado
    return atualizado

VALIDACAO_CONTRATO = r'''
from backend.app.principal import app
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.schemas.etapa_producao import ETAPAS_PRODUCAO

documento = app.openapi()
paths = documento["paths"]

def schema(valor):
    vistos = set()
    while "$ref" in valor:
        ref = valor["$ref"]
        if ref in vistos or not ref.startswith("#/"):
            raise RuntimeError("Referência OpenAPI inesperada.")
        vistos.add(ref)
        valor = documento
        for parte in ref[2:].split("/"):
            valor = valor[parte.replace("~1", "/").replace("~0", "~")]
    return valor

def campos(valor, nomes):
    ausentes = set(nomes) - set(schema(valor).get("properties", {}))
    if ausentes:
        raise RuntimeError("Campos ausentes no contrato de produção: " + ", ".join(sorted(ausentes)))

esperadas = ("aguardando_material", "em_usinagem", "em_solda_dobra", "em_acabamento", "pronto_para_envio")
if tuple(ETAPAS_PRODUCAO) != esperadas:
    raise RuntimeError("As etapas de produção diferem do contrato D10. Nenhum fonte foi alterado.")
for nome in ("id", "ordem_servico_id", "empresa_fornecedora_id", "etapa", "observacoes", "criada_em"):
    if not hasattr(EtapaProducao, nome):
        raise RuntimeError("Modelo de produção sem o campo " + nome)
base = "/api/v1/ordens-servico/{ordem_servico_id}"
for metodo in ("get", "post"):
    op = paths.get(base + "/etapas-producao", {}).get(metodo)
    if not op:
        raise RuntimeError("Rota de etapas de produção D10 ausente: " + metodo)
    if metodo == "post":
        corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
        campos(corpo, ("empresa_fornecedora_id", "etapa", "observacoes"))
        if set(corpo.get("required", [])) != {"empresa_fornecedora_id", "etapa"}:
            raise RuntimeError("O corpo do registro de etapa difere do contrato D10.")
        campos(op["responses"]["201"]["content"]["application/json"]["schema"], ("id", "ordem_servico_id", "etapa", "criada_em"))
op = paths.get(base + "/acompanhamento-producao", {}).get("get")
if not op:
    raise RuntimeError("O acompanhamento de produção D10 não está registrado.")
campos(op["responses"]["200"]["content"]["application/json"]["schema"], ("ordem_servico_id", "etapa_atual", "historico"))
for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    op = paths.get("/api/v1/portal-" + perfil + "/ordens-servico", {}).get("get")
    if not op or not any(p["name"] == empresa and p.get("required") for p in op.get("parameters", [])):
        raise RuntimeError("O portal de ordens D26 não está instalado para " + perfil)
print("CONTRATO_PRODUCAO_D10_OK=True")
print("CINCO_ETAPAS_E_HISTORICO_EXISTENTES_OK=True")
print("PORTAIS_ORDENS_D26_OK=True")
'''

def fim_tag(texto: str, inicio: int) -> int:
    """Encontra o fim da tag Route sem confundir JSX dentro de element={...}."""
    pos = inicio
    nivel = 0
    aspas = ""
    while pos < len(texto):
        caractere = texto[pos]
        if aspas:
            if caractere == "\\":
                pos += 2
                continue
            if caractere == aspas:
                aspas = ""
        elif caractere in "\"'`":
            aspas = caractere
        elif texto.startswith("/*", pos):
            fim = texto.find("*/", pos + 2)
            if fim < 0:
                break
            pos = fim + 2
            continue
        elif texto.startswith("//", pos):
            fim = texto.find("\n", pos + 2)
            if fim < 0:
                break
            pos = fim + 1
            continue
        elif caractere == "{":
            nivel += 1
        elif caractere == "}":
            nivel -= 1
            if nivel < 0:
                break
        elif caractere == ">" and nivel == 0:
            return pos + 1
        pos += 1
    raise RuntimeError("Uma tag Route de App.tsx não pôde ser interpretada com segurança.")


def localizar_rotas(texto: str) -> list[dict]:
    rotas = []
    pilha = []
    pos = 0
    token = re.compile(r"</?Route\b")
    padrao_path = re.compile(r'''\bpath\s*=\s*(?:(["'])(.*?)\1|\{\s*(["'])(.*?)\3\s*\})''', re.S)
    while correspondencia := token.search(texto, pos):
        inicio = correspondencia.start()
        fim = fim_tag(texto, inicio)
        abertura = texto[inicio:fim]
        if abertura.startswith("</"):
            if not pilha:
                raise RuntimeError("Fechamento Route sem abertura correspondente em App.tsx.")
            pilha.pop()["fim"] = fim
        else:
            caminho = padrao_path.search(abertura)
            registro = {
                "inicio": inicio, "fim_abertura": fim, "fim": fim,
                "path": (caminho.group(2) if caminho.group(1) else caminho.group(4)) if caminho else None,
                "auto_fecha": abertura.rstrip().endswith("/>"),
            }
            rotas.append(registro)
            if not registro["auto_fecha"]:
                pilha.append(registro)
        pos = fim
    if pilha:
        raise RuntimeError("Há um grupo Route sem fechamento em App.tsx.")
    return rotas


def codificar(texto: str, original: bytes | None) -> bytes:
    marcador = b"\xef\xbb\xbf" if original and original.startswith(b"\xef\xbb\xbf") else b""
    return marcador + texto.encode("utf-8")


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d27_", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def executar_etapa(nome: str, comando: list[str], pasta: Path, relatorio: dict) -> None:
    print(f"Executando {nome}...", flush=True)
    ambiente = os.environ.copy()
    ambiente["PYTHONIOENCODING"] = "utf-8"
    processo = subprocess.run(
        comando, cwd=pasta, env=ambiente, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=600,
    )
    saida = (processo.stdout or "") + (processo.stderr or "")
    relatorio["etapas"].append({"nome": nome, "returncode": processo.returncode, "saida": saida})
    if saida:
        print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
    print(f"{nome.upper().replace(' ', '_')}_RETURN_CODE={processo.returncode}", flush=True)
    if processo.returncode:
        raise RuntimeError(f"A etapa {nome} falhou. Confira a saída e o relatório.")


def salvar_relatorios(raiz: Path, relatorio: dict) -> None:
    json_path = raiz / (RELATORIO_NOME + ".json")
    txt_path = raiz / (RELATORIO_NOME + ".txt")
    linhas = [
        "MEC-Serviços D27 — Acompanhamento de Produção nos Portais do Cliente e Fornecedor",
        f"REVISION={REVISION}", f"ROOT={raiz}", f"RESULTADO={relatorio['resultado']}",
        f"BACKUP_DIR={relatorio.get('backup_dir', '')}",
    ]
    if relatorio.get("erro"):
        linhas.append("ERRO=" + relatorio["erro"])
    if "restaurado" in relatorio:
        linhas.append(f"RESTAURADO={relatorio['restaurado']}")
    for etapa in relatorio["etapas"]:
        linhas.extend(["", etapa["nome"], f"RETURN_CODE={etapa['returncode']}", etapa["saida"].rstrip()])
    gravar_atomico(json_path, (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    gravar_atomico(txt_path, ("\n".join(linhas).rstrip() + "\n").encode("utf-8"))
    print(f"RELATORIO={txt_path}", flush=True)
    print(f"JSON={json_path}", flush=True)


def main() -> int:
    print("MEC-Serviços D27 — Acompanhamento de Produção nos Portais do Cliente e Fornecedor", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    raiz = None
    backup = None
    originais: dict[Path, bytes | None] = {}
    alterados: list[Path] = []
    dist_alteravel = False
    dist_existia = False
    relatorio_salvo = False
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapas": []}
    try:
        raiz = localizar_raiz()
        print(f"ROOT={raiz}", flush=True)
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm não encontrado no PATH. Nenhum fonte foi alterado.")
        pacote = json.loads(ler_texto(raiz / "frontend/package.json"))
        dependencias = {**pacote.get("dependencies", {}), **pacote.get("devDependencies", {})}
        if not pacote.get("scripts", {}).get("build") or not all(nome in dependencias for nome in ("react", "react-router-dom", "lucide-react", "axios")):
            raise RuntimeError("As dependências e o comando de build do frontend não correspondem ao D22.")
        if not re.search(r'''\bbaseURL\s*:\s*["']/api/v1/?["']''', ler_texto(raiz / "frontend/src/services/api.ts")):
            raise RuntimeError("O endereço base do cliente API difere de /api/v1. Nenhum fonte foi alterado.")
        for alvo in (*ALVOS, DIST_REL):
            caminho = raiz / alvo
            if caminho.is_symlink() or not caminho.resolve().is_relative_to(raiz):
                raise RuntimeError("Um destino da atualização aponta para fora do projeto: " + str(alvo))
            if alvo == DIST_REL and caminho.exists() and not caminho.is_dir():
                raise RuntimeError("frontend/dist existe, mas não é uma pasta. Nenhum fonte foi alterado.")
        originais = {alvo: (raiz / alvo).read_bytes() if (raiz / alvo).exists() else None for alvo in ALVOS}
        app_atualizado = atualizar_app(originais[APP_REL].decode("utf-8-sig"))
        conteudos = {APP_REL: app_atualizado, ROUTER_REL: atualizar_roteador(originais[ROUTER_REL].decode("utf-8-sig")), **{Path(nome): fonte for nome, fonte in FONTES.items()}}
        validar_fontes_existentes(originais)
        planejados = {alvo: codificar(texto, originais[alvo]) for alvo, texto in conteudos.items()}
        executar_etapa("validacao contrato", [sys.executable, "-c", VALIDACAO_CONTRATO], raiz, relatorio)
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = raiz / "_mec_backups" / ("D27_PORTAIS_PRODUCAO_" + carimbo)
        backup.mkdir(parents=True, exist_ok=False)
        relatorio["backup_dir"] = str(backup)
        for alvo, original in originais.items():
            if original is not None:
                destino = backup / alvo
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(original)
        dist = raiz / DIST_REL
        dist_existia = dist.is_dir()
        if dist_existia:
            shutil.copytree(dist, backup / DIST_REL)
        print(f"BACKUP_DIR={backup}", flush=True)
        for alvo, dados in planejados.items():
            if dados != originais[alvo]:
                alterados.append(alvo)
                gravar_atomico(raiz / alvo, dados)
        relatorio["arquivos_atualizados"] = [str(alvo) for alvo in alterados]
        executar_etapa("contrato portais", [sys.executable, "-c", VALIDACAO_PORTAIS], raiz, relatorio)
        print("PRODUCAO_TELAS_ROTAS_E_BACKEND_OK=True", flush=True)
        print("PYTEST_COMANDO=python -m pytest tests -q --ignore=tests/mold", flush=True)
        executar_etapa("pytest", [sys.executable, "-m", "pytest", "tests", "-q", "--ignore=tests/mold"], raiz, relatorio)
        dist_alteravel = True
        executar_etapa("npm build", [npm, "run", "build"], raiz / "frontend", relatorio)
        relatorio["resultado"] = "OK"
        salvar_relatorios(raiz, relatorio)
        relatorio_salvo = True
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["resultado"] = "ERRO"
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ERRO=" + relatorio["erro"], flush=True)
        falhas = []
        if raiz is not None and backup is not None:
            for alvo in reversed(alterados):
                try:
                    original = originais[alvo]
                    if original is None:
                        (raiz / alvo).unlink(missing_ok=True)
                    else:
                        gravar_atomico(raiz / alvo, original)
                except Exception as falha:
                    falhas.append(str(alvo) + ": " + str(falha))
            if dist_alteravel:
                try:
                    dist = raiz / DIST_REL
                    if dist.exists():
                        shutil.rmtree(dist)
                    if dist_existia:
                        shutil.copytree(backup / DIST_REL, dist)
                except Exception as falha:
                    falhas.append("frontend/dist: " + str(falha))
            if alterados or dist_alteravel:
                relatorio["restaurado"] = not falhas
                print(f"RESTAURADO={not falhas}", flush=True)
            if falhas:
                relatorio["falhas_restauracao"] = falhas
                for falha in falhas:
                    print("ERRO_RESTAURACAO=" + falha, flush=True)
    if raiz is not None and not relatorio_salvo:
        try:
            salvar_relatorios(raiz, relatorio)
        except Exception as erro:
            print(f"ERRO_RELATORIO={erro}", flush=True)
            relatorio["resultado"] = "ERRO"
    print("RESULTADO=" + relatorio["resultado"], flush=True)
    if relatorio["resultado"] != "OK":
        return 1
    print("Reinicie o backend e atualize /cliente/producao e /fornecedor/producao com Ctrl+F5.", flush=True)
    print("Como fornecedor, selecione uma ordem aberta ou em execução em /fornecedor/producao.", flush=True)
    print("Escolha a etapa, informe as observações, revise e confirme a atualização.", flush=True)
    print("Como cliente, atualize /cliente/producao e confira a etapa atual e o histórico da mesma ordem.", flush=True)
    print("Ordens concluídas continuam disponíveis para consulta do histórico.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
