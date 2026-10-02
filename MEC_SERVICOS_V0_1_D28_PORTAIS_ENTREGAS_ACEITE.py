r"""MEC-Serviços D28 — Entregas e Aceite nos portais.

Na raiz do MEC-Servicos, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D28_PORTAIS_ENTREGAS_ACEITE.py

Requer D11 e D27. O fornecedor registra entregas para uma OS em execução
com última etapa Pronto para envio. O cliente aceita ou recusa com motivo.
O aceite D11 conclui a OS e encerra a contratação. A recusa permite outra
entrega após a correção. Mantém os registros e as operações D11 existentes.
Não cria dados de demonstração nem altera ordens, contratos e entregas
durante a instalação. Faz backup, valida o contrato, executa a suíte MEC
e npm run build. Se alguma etapa falhar, restaura os fontes e frontend/dist.
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

REVISION = "MEC-SERVICOS-V0.1-D28-PORTAIS-ENTREGAS-ACEITE-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D28_PORTAIS_ENTREGAS_ACEITE_RELATORIO"
APP_REL = Path("frontend/src/App.tsx")
ROUTER_REL = Path("backend/app/api/roteador.py")
DIST_REL = Path("frontend/dist")
FONTES = {
  "backend/app/api/rotas/portal_entregas.py": "from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, HTTPException, Path, Query, status\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.api.rotas.entregas import aceitar_entrega, recusar_entrega, registrar_entrega\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao, EntregaServicoLeitura\nfrom backend.app.schemas.portal_entregas import (\n    EntregaPortalCriacao, EntregaPortalDecisao, EntregasPortalLeitura, EntregasPortalPagina,\n)\nfrom backend.app.services.portal_entregas import ServicoPortalEntregas\n\nroteador = APIRouter(tags=[\"entregas e aceite dos portais\"])\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\nEmpresaId = Annotated[int, Query(gt=0)]\nRecursoId = Annotated[int, Path(gt=0)]\nDeslocamento = Annotated[int, Query(ge=0)]\nLimite = Annotated[int, Query(ge=1, le=100)]\n\n\n@roteador.get(\"/portal-cliente/entregas\", response_model=EntregasPortalPagina)\ndef listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,\n                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> EntregasPortalPagina:\n    return ServicoPortalEntregas(banco).listar(empresa_cliente_id, \"cliente\", deslocamento, limite)\n\n\n@roteador.get(\"/portal-fornecedor/entregas\", response_model=EntregasPortalPagina)\ndef listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,\n                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> EntregasPortalPagina:\n    return ServicoPortalEntregas(banco).listar(empresa_fornecedora_id, \"fornecedor\", deslocamento, limite)\n\n\n@roteador.get(\"/portal-cliente/entregas/{ordem_id}\", response_model=EntregasPortalLeitura)\ndef obter_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> EntregasPortalLeitura:\n    return ServicoPortalEntregas(banco).obter(ordem_id, empresa_cliente_id, \"cliente\")\n\n\n@roteador.get(\"/portal-fornecedor/entregas/{ordem_id}\", response_model=EntregasPortalLeitura)\ndef obter_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> EntregasPortalLeitura:\n    return ServicoPortalEntregas(banco).obter(ordem_id, empresa_fornecedora_id, \"fornecedor\")\n\n\n@roteador.post(\"/portal-fornecedor/entregas/{ordem_id}/registrar\",\n               response_model=EntregaServicoLeitura, status_code=status.HTTP_201_CREATED)\ndef registrar(ordem_id: RecursoId, dados: EntregaPortalCriacao, banco: SessaoBanco):\n    try:\n        ServicoPortalEntregas(banco).preparar_registro(ordem_id, dados.empresa_fornecedora_id,\n                                                    dados.ultima_entrega_id, dados.ultima_etapa_id)\n        return registrar_entrega(ordem_id, EntregaServicoCriacao(\n            empresa_fornecedora_id=dados.empresa_fornecedora_id, observacoes=dados.observacoes), banco)\n    except HTTPException:\n        banco.rollback()\n        raise\n\n\n@roteador.post(\"/portal-cliente/entregas/{ordem_id}/{entrega_id}/aceitar\", response_model=EntregaServicoLeitura)\ndef aceitar(ordem_id: RecursoId, entrega_id: RecursoId, dados: EntregaPortalDecisao, banco: SessaoBanco):\n    try:\n        ServicoPortalEntregas(banco).preparar_decisao(ordem_id, entrega_id, dados.empresa_cliente_id)\n        return aceitar_entrega(ordem_id, entrega_id, EntregaServicoDecisao(\n            empresa_cliente_id=dados.empresa_cliente_id), banco)\n    except HTTPException:\n        banco.rollback()\n        raise\n\n\n@roteador.post(\"/portal-cliente/entregas/{ordem_id}/{entrega_id}/recusar\", response_model=EntregaServicoLeitura)\ndef recusar(ordem_id: RecursoId, entrega_id: RecursoId, dados: EntregaPortalDecisao, banco: SessaoBanco):\n    try:\n        if not dados.motivo:\n            raise HTTPException(422, detail=\"motivo_recusa_obrigatorio\")\n        ServicoPortalEntregas(banco).preparar_decisao(ordem_id, entrega_id, dados.empresa_cliente_id)\n        return recusar_entrega(ordem_id, entrega_id, EntregaServicoDecisao(\n            empresa_cliente_id=dados.empresa_cliente_id, motivo=dados.motivo), banco)\n    except HTTPException:\n        banco.rollback()\n        raise\n",
  "backend/app/schemas/portal_entregas.py": "from __future__ import annotations\n\nfrom datetime import datetime\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\nfrom backend.app.schemas.entrega import EntregaServicoCriacao, EntregaServicoDecisao, EntregaServicoLeitura\nfrom backend.app.schemas.portal_producao import OrdemProducaoLeitura\n\n\nclass OrdemEntregaLeitura(OrdemProducaoLeitura):\n    ultima_entrega_id: int\n    ultima_entrega_status: str | None\n    ultima_entrega_em: datetime | None\n    total_entregas: int\n    entrega_pendente_id: int | None\n\n\nclass EntregasPortalPagina(BaseModel):\n    itens: list[OrdemEntregaLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n\n\nclass EntregasPortalLeitura(BaseModel):\n    ordem: OrdemEntregaLeitura\n    historico: list[EntregaServicoLeitura]\n\n\nclass EntregaPortalCriacao(EntregaServicoCriacao):\n    model_config = ConfigDict(extra=\"forbid\")\n    observacoes: str | None = Field(default=None, max_length=5000)\n    ultima_entrega_id: int = Field(ge=0)\n    ultima_etapa_id: int = Field(ge=0)\n\n\nclass EntregaPortalDecisao(EntregaServicoDecisao):\n    model_config = ConfigDict(extra=\"forbid\")\n    motivo: str | None = Field(default=None, max_length=5000)\n",
  "backend/app/services/portal_entregas.py": "from __future__ import annotations\n\nfrom fastapi import HTTPException\nfrom sqlalchemy import case, func, select, update\nfrom sqlalchemy.orm import Session, aliased\n\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.entrega import EntregaServico\nfrom backend.app.models.etapa_producao import EtapaProducao\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.schemas.entrega import EntregaServicoLeitura\nfrom backend.app.schemas.portal_entregas import EntregasPortalLeitura, EntregasPortalPagina, OrdemEntregaLeitura\nfrom backend.app.services.portal_contratacoes import Perfil\nfrom backend.app.services.portal_producao import ServicoPortalProducao\n\n\nclass ServicoPortalEntregas:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.producao = ServicoPortalProducao(banco)\n        self.ordens = self.producao.ordens\n\n    def _consulta(self):\n        resumo = select(\n            EntregaServico.ordem_servico_id.label(\"ordem_id\"),\n            func.max(EntregaServico.id).label(\"ultima_id\"),\n            func.count(EntregaServico.id).label(\"quantidade\"),\n            func.max(case((EntregaServico.status == \"entregue\", EntregaServico.id), else_=None)).label(\"pendente_id\"),\n        ).group_by(EntregaServico.ordem_servico_id).subquery()\n        ultima = aliased(EntregaServico)\n        return self.producao._consulta().add_columns(\n            ultima.id, ultima.status, ultima.entregue_em, resumo.c.quantidade, resumo.c.pendente_id,\n        ).outerjoin(resumo, resumo.c.ordem_id == OrdemServico.id).outerjoin(ultima, ultima.id == resumo.c.ultima_id)\n\n    def _ordem(self, linha) -> OrdemEntregaLeitura:\n        entrega_id, situacao, instante, quantidade, pendente_id = linha[-5:]\n        return OrdemEntregaLeitura(**self.producao._ordem(linha[:-5]).model_dump(),\n            ultima_entrega_id=entrega_id or 0, ultima_entrega_status=situacao,\n            ultima_entrega_em=instante, total_entregas=quantidade or 0, entrega_pendente_id=pendente_id)\n\n    def listar(self, empresa: int, perfil: Perfil, deslocamento: int, limite: int) -> EntregasPortalPagina:\n        self.ordens.contratos.validar_empresa(empresa, perfil)\n        consulta = self._consulta().where(self.ordens._dono(empresa, perfil))\n        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0\n        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()\n        return EntregasPortalPagina(itens=[self._ordem(linha) for linha in linhas], total=total,\n                                   deslocamento=deslocamento, limite=limite)\n\n    def obter(self, ordem_id: int, empresa: int, perfil: Perfil) -> EntregasPortalLeitura:\n        self.ordens.contratos.validar_empresa(empresa, perfil)\n        linha = self.banco.execute(self._consulta().where(\n            OrdemServico.id == ordem_id, self.ordens._dono(empresa, perfil),\n        )).first()\n        if linha is None:\n            raise HTTPException(404, detail=\"ordem_servico_nao_encontrada\")\n        ordem = self._ordem(linha)\n        itens = self.banco.scalars(select(EntregaServico).where(\n            EntregaServico.ordem_servico_id == ordem_id,\n            EntregaServico.empresa_cliente_id == ordem.empresa_cliente_id,\n            EntregaServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id,\n        ).order_by(EntregaServico.id)).all()\n        historico = [EntregaServicoLeitura.model_validate(item) for item in itens]\n        ultima = historico[-1] if historico else None\n        pendente = next((e.id for e in reversed(historico) if e.status == \"entregue\"), None)\n        ordem = ordem.model_copy(update={\"ultima_entrega_id\": ultima.id if ultima else 0,\n            \"ultima_entrega_status\": ultima.status if ultima else None,\n            \"ultima_entrega_em\": ultima.entregue_em if ultima else None,\n            \"total_entregas\": len(historico), \"entrega_pendente_id\": pendente})\n        return EntregasPortalLeitura(ordem=ordem, historico=historico)\n\n    def _travar_ordem(self, ordem_id: int, empresa: int, perfil: Perfil):\n        ordem = self.ordens.obter(ordem_id, empresa, perfil)\n        if ordem.contratacao_status != \"ativa\":\n            raise HTTPException(409, detail=\"contratacao_nao_esta_ativa\")\n        if ordem.status != \"em_execucao\":\n            raise HTTPException(409, detail=\"ordem_servico_nao_pode_receber_entrega\")\n        contrato_ativo = select(ContratacaoServico.id).where(\n            ContratacaoServico.id == OrdemServico.contratacao_id,\n            ContratacaoServico.status == \"ativa\",\n            ContratacaoServico.empresa_cliente_id == ordem.empresa_cliente_id,\n            ContratacaoServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id,\n        ).correlate(OrdemServico).exists()\n        # Serializa registro/decisão com a produção e a execução da mesma OS.\n        travada = self.banco.execute(update(OrdemServico).where(\n            OrdemServico.id == ordem_id, self.ordens._dono(empresa, perfil),\n            OrdemServico.status == \"em_execucao\", contrato_ativo,\n        ).values(status=OrdemServico.status), execution_options={\"synchronize_session\": False})\n        if travada.rowcount != 1:\n            self.banco.rollback()\n            raise HTTPException(409, detail=\"ordem_servico_alterada_atualize\")\n        contrato = self.banco.execute(update(ContratacaoServico).where(\n            ContratacaoServico.id == ordem.contratacao_id, ContratacaoServico.status == \"ativa\",\n            ContratacaoServico.empresa_cliente_id == ordem.empresa_cliente_id,\n            ContratacaoServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id,\n        ).values(status=ContratacaoServico.status), execution_options={\"synchronize_session\": False})\n        if contrato.rowcount != 1:\n            self.banco.rollback()\n            raise HTTPException(409, detail=\"contratacao_nao_esta_ativa\")\n        return ordem\n\n    def preparar_registro(self, ordem_id: int, empresa: int, ultima_entrega_id: int, ultima_etapa_id: int) -> None:\n        self._travar_ordem(ordem_id, empresa, \"fornecedor\")\n        ultima = self.banco.scalar(select(func.max(EntregaServico.id)).where(EntregaServico.ordem_servico_id == ordem_id)) or 0\n        etapa = self.banco.scalar(select(EtapaProducao).where(\n            EtapaProducao.ordem_servico_id == ordem_id).order_by(EtapaProducao.id.desc()).limit(1))\n        if ultima != ultima_entrega_id:\n            raise HTTPException(409, detail=\"entregas_alteradas_atualize\")\n        if (etapa.id if etapa else 0) != ultima_etapa_id:\n            raise HTTPException(409, detail=\"producao_alterada_atualize\")\n        if etapa is None or etapa.etapa != \"pronto_para_envio\":\n            raise HTTPException(409, detail=\"ordem_servico_nao_esta_pronta_para_entrega\")\n        pendente = self.banco.scalar(select(EntregaServico.id).where(\n            EntregaServico.ordem_servico_id == ordem_id, EntregaServico.status == \"entregue\").limit(1))\n        if pendente is not None:\n            raise HTTPException(409, detail=\"entrega_pendente_ja_existe\")\n        self.banco.expire_all()\n\n    def preparar_decisao(self, ordem_id: int, entrega_id: int, empresa: int) -> None:\n        ordem = self.ordens.obter(ordem_id, empresa, \"cliente\")\n        item = self.banco.scalar(select(EntregaServico).where(\n            EntregaServico.id == entrega_id, EntregaServico.ordem_servico_id == ordem_id,\n            EntregaServico.empresa_cliente_id == empresa,\n            EntregaServico.empresa_fornecedora_id == ordem.empresa_fornecedora_id))\n        if item is None:\n            raise HTTPException(404, detail=\"entrega_nao_encontrada\")\n        if item.status != \"entregue\":\n            raise HTTPException(409, detail=\"entrega_nao_esta_pendente\")\n        self._travar_ordem(ordem_id, empresa, \"cliente\")\n        travada = self.banco.execute(update(EntregaServico).where(\n            EntregaServico.id == entrega_id, EntregaServico.ordem_servico_id == ordem_id,\n            EntregaServico.empresa_cliente_id == empresa, EntregaServico.status == \"entregue\",\n        ).values(status=EntregaServico.status), execution_options={\"synchronize_session\": False})\n        if travada.rowcount != 1:\n            raise HTTPException(409, detail=\"entrega_nao_esta_pendente\")\n        self.banco.expire_all()\n",
  "frontend/src/pages/entregas/PortalEntregasPage.css": ".p28-page { color: #dce7f7; display: flex; flex-direction: column; gap: 22px; width: 100%; }\n.p28-page * { box-sizing: border-box; }\n.p28-page h1, .p28-page h2, .p28-page h3, .p28-page p { margin: 0; }\n.p28-page h1 { color: #edf3fc; font-size: clamp(28px, 3vw, 40px); line-height: 1.25; margin: 10px 0 12px; }\n.p28-page h2 { font-size: 19px; color: #e9f0fc; }\n.p28-page h3 { color: #c6d8ef; font-size: 14px; margin: 22px 0 10px; }\n.p28-page p { color: #91a8c8; line-height: 1.6; }\n.p28-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }\n.p28-page .p28-eyebrow { display: flex; align-items: center; gap: 9px; color: #6ba6ff; font-size: 12px; font-weight: 800; letter-spacing: .09em; }\n.p28-button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 11px 15px; background: #162333; border: 1px solid #31465f; border-radius: 8px; color: #dce9fc; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; text-decoration: none; line-height: 1.4; }\n.p28-button:hover:enabled, a.p28-button:hover { background: #213754; border-color: #6592cc; }\n.p28-button:focus-visible, .p28-form textarea:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.p28-button:disabled { opacity: .45; cursor: default; }\n.p28-primary { background: #2563eb; border-color: #357bf5; color: #fff; }\n.p28-primary:hover:enabled { background: #3475fb; }\n.p28-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }\n.p28-summary article { display: flex; flex-direction: column; gap: 12px; padding: 23px; background: linear-gradient(145deg, #162235, #101b2b); border: 1px solid #2b3c53; border-radius: 13px; }\n.p28-summary span { color: #a6c0e2; font-size: 13px; }\n.p28-summary strong { font-size: 31px; color: #f2f6fe; }\n.p28-summary small { color: #7794ba; line-height: 1.5; }\n.p28-tabs { display: flex; flex-wrap: wrap; gap: 9px; }\n.p28-tab-active { background: #193658; border-color: #4976b0; }\n.p28-panel { background: #111c2a; border: 1px solid #293d56; border-radius: 13px; overflow: hidden; }\n.p28-section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 23px; }\n.p28-section-head p { font-size: 13px; margin-top: 10px; }\n.p28-section-head > svg { color: #79aef5; flex-shrink: 0; }\n.p28-table-wrap { overflow-x: auto; }\n.p28-page table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; }\n.p28-page th { color: #819fc5; background: #0e1825; padding: 17px 20px; font-weight: 700; white-space: nowrap; }\n.p28-page td { padding: 19px 20px; border-top: 1px solid #26384e; color: #d5e4f7; overflow-wrap: anywhere; }\n.p28-page td strong { color: #e8f1ff; font-size: 13px; }\n.p28-page td small { display: block; color: #7899c2; margin-top: 9px; font-size: 11px; line-height: 1.5; }\n.p28-page .p28-selected { background: #192d46; }\n.p28-nowrap { white-space: nowrap; }\n.p28-badge { display: inline-block; padding: 7px 10px; border-radius: 18px; background: #223245; font-size: 11px; font-weight: 800; white-space: nowrap; }\n.p28-status-ativa, .p28-status-concluida { background: #173d31; color: #80deae; }\n.p28-status-cancelada { background: #42303b; color: #e4a1b9; }\n.p28-status-em_execucao { background: #203956; color: #99c6ff; }\n.p28-empty { min-height: 235px; padding: 45px 24px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 15px; text-align: center; }\n.p28-empty svg { color: #669dea; }\n.p28-empty h3 { font-size: 18px; margin: 0; color: #d9e9ff; }\n.p28-empty p { max-width: 680px; font-size: 13px; }\n.p28-pagination { padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; gap: 14px; border-top: 1px solid #293d56; color: #8fa9cb; font-size: 12px; }\n.p28-pagination > div { display: flex; gap: 9px; }\n.p28-columns { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 22px; align-items: start; }\n.p28-detail { padding: 23px; }\n.p28-detail .p28-section-head, .p28-dialog .p28-section-head { padding: 0; margin-bottom: 22px; }\n.p28-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }\n.p28-fields > div { border: 1px solid #2b3e56; background: #0d1724; border-radius: 9px; padding: 15px; min-width: 0; }\n.p28-fields dt { color: #819fc4; font-size: 11px; margin-bottom: 10px; }\n.p28-fields dd { color: #e2ecfa; font-size: 13px; font-weight: 700; margin: 0; line-height: 1.6; overflow-wrap: anywhere; }\n.p28-fields .p28-value { font-size: 19px; }\n.p28-wide { grid-column: 1 / -1; }\n.p28-page .p28-observacoes { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; margin-bottom: 20px; }\n.p28-form { margin-top: 22px; }\n.p28-form fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }\n.p28-form label { display: block; color: #b2c9e7; font-size: 12px; font-weight: 700; margin-bottom: 10px; }\n.p28-form textarea { display: block; width: 100%; border: 1px solid #37506e; border-radius: 9px; background: #0b1523; color: #e6f0ff; padding: 13px; font: inherit; font-size: 13px; resize: vertical; line-height: 1.7; }\n.p28-form p { font-size: 12px; margin: 14px 0; }\n.p28-form button[type=\"submit\"] { width: 100%; margin-top: 8px; }\n.p28-page .p28-alert { display: flex; align-items: flex-start; gap: 11px; padding: 15px 18px; border-radius: 9px; font-size: 13px; }\n.p28-alert svg { flex-shrink: 0; }\n.p28-page .p28-success { color: #a1e8c4; background: #143028; border: 1px solid #276148; }\n.p28-page .p28-error { color: #ffbdc6; background: #37212a; border: 1px solid #703c4c; }\n.p28-files-head { margin-top: 28px; }\n.p28-files-head h3 { margin: 0; }\n.p28-files { padding: 0; margin: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }\n.p28-files li { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 9px; border: 1px solid #30445f; background: #0d1724; }\n.p28-files li > svg { color: #79aef5; flex-shrink: 0; }\n.p28-files li > span { flex: 1; min-width: 0; }\n.p28-files strong { font-size: 12px; overflow-wrap: anywhere; }\n.p28-files small { color: #7695bd; font-size: 11px; display: block; margin-top: 6px; }\n.p28-dialog { color: #e4edfa; background: #111e30; border: 1px solid #466891; border-radius: 14px; padding: 26px; width: min(600px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto; box-shadow: 0 24px 90px #0009; }\n.p28-dialog::backdrop { background: #020814c9; }\n.p28-dialog p { font-size: 13px; margin-bottom: 20px; }\n.p28-dialog h3 { margin-top: 20px; }\n.p28-dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 24px; }\n.p28-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }\n@media (max-width: 1100px) { .p28-columns { grid-template-columns: minmax(0, 1fr); } }\n@media (max-width: 650px) { .p28-header { flex-direction: column; } .p28-summary { grid-template-columns: minmax(0, 1fr); } .p28-tabs { flex-direction: column; } .p28-detail, .p28-section-head { padding: 18px; } .p28-pagination { flex-wrap: wrap; } .p28-fields { grid-template-columns: minmax(0, 1fr); } .p28-files li { flex-wrap: wrap; } .p28-files li .p28-button { width: 100%; } .p28-dialog { padding: 20px; } }\n.p28-status-aberta { background: #4a3c20; color: #f0cd83; }\n.p28-operacao { display: flex; flex-direction: column; gap: 16px; margin-top: 24px; }\n.p28-operacao p { font-size: 13px; }\n.p28-dialog .p28-review-note { margin-top: 20px; }\n.p28-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }\n.p28-summary .p28-summary-stage { font-size: 20px; line-height: 1.5; }\n.p28-detail .p28-section-head h2 { display: flex; align-items: center; gap: 9px; }\n.p28-stage-current { background: #203956; color: #99c6ff; }\n.p28-stage-ready { background: #173d31; color: #80deae; }\n.p28-current { display: flex; align-items: center; gap: 10px; font-weight: 700; }\n.p28-form select { display: block; width: 100%; color: #e6f0ff; background: #0b1523; border: 1px solid #37506e; border-radius: 9px; padding: 13px; font: inherit; font-size: 13px; margin-bottom: 20px; }\n.p28-form select:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.p28-readonly { margin-top: 22px !important; padding: 16px; border: 1px solid #31465f; border-radius: 9px; }\n.p28-history h3 { margin-top: 0; }\n.p28-history-empty { display: flex; align-items: center; gap: 12px; border: 1px dashed #31465f; border-radius: 9px; padding: 24px; }\n.p28-timeline { padding: 0; margin: 0; list-style: none; }\n.p28-timeline li { position: relative; padding: 0 0 22px 25px; margin-left: 5px; border-left: 2px solid #2e4665; }\n.p28-timeline li:last-child { border-left-color: transparent; }\n.p28-timeline-dot { position: absolute; left: -6px; top: 17px; width: 10px; height: 10px; border-radius: 50%; background: #79aef5; }\n.p28-timeline article { border: 1px solid #2d4564; border-radius: 10px; background: #0d1724; padding: 19px; }\n.p28-timeline h4 { margin: 0 0 9px; font-size: 14px; color: #dfeafd; }\n.p28-timeline time { display: block; color: #8ea8ca; font-size: 12px; margin-bottom: 14px; }\n.p28-timeline .p28-observacoes { margin-bottom: 0; }\n@media (max-width: 850px) { .p28-summary { grid-template-columns: minmax(0, 1fr); } }\n\n.p28-decision-actions { display:flex;flex-wrap:wrap;gap:12px;margin-top:16px; }\n.p28-button.p28-danger { background:#7f1d1d;border-color:#b91c1c;color:#fff; }\n.p28-button.p28-danger:hover:not(:disabled) { background:#991b1b; }\n.p28-entrega-entregue,.p28-entrega-vazia { color:#93c5fd;background:#1e3a5f; }\n.p28-entrega-aceita { color:#86efac;background:#14532d; }\n.p28-entrega-recusada { color:#fca5a5;background:#7f1d1d; }\n.p28-history h4 { display:flex;flex-wrap:wrap;align-items:center;gap:10px; }\n.p28-history-date { color:#94a3b8;font-size:14px; }\n.p28-history h5 { margin:16px 0 8px;color:#fca5a5;font-size:14px; }\n.p28-refusal-reason { color:#fecaca; }\n.p28-review-effect { padding:16px;border-radius:10px;background:#1e293b;line-height:1.7; }\n",
  "frontend/src/pages/entregas/PortalEntregasPage.tsx": "import { useEffect, useRef, useState, type FormEvent } from \"react\";\nimport { Link } from \"react-router-dom\";\nimport { CheckCircle2, ClipboardList, Factory, History, PackageCheck, RefreshCw, Wrench, X } from \"lucide-react\";\nimport { useAuth } from \"../../auth/AuthContext\";\nimport { api } from \"../../services/api\";\nimport { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from \"../client/cotacoesCliente\";\nimport { formatarMedidaContrato, rotuloContratacao, type PaginaContratacoes } from \"../contratacoes/contratacoesPortal\";\nimport { rotuloOrdem, type PerfilOrdens } from \"../ordens/ordensPortal\";\nimport { rotuloEtapa } from \"../producao/producaoPortal\";\nimport { mensagemErroEntrega, rotuloEntrega, type AcaoEntrega, type EntregaServico, type EntregasDetalhe, type OrdemEntrega } from \"./entregasPortal\";\nimport \"./PortalEntregasPage.css\";\n\ntype Revisao = { chave: string; dono: string; ordem: OrdemEntrega; acao: AcaoEntrega; entregaId: number | null; texto: string | null };\n\nfunction dataHora(valor: string): string | undefined {\n  const instante = instanteUtc(valor);\n  return instante === null ? undefined : new Date(instante).toISOString();\n}\nfunction dataVisivel(valor: string | null): string {\n  return valor ? formatarInstanteCotacao(instanteUtc(valor)) : \"—\";\n}\n\nexport default function PortalEntregasPage({ perfil }: { perfil: PerfilOrdens }) {\n  const { user } = useAuth();\n  const empresaId = user?.role === perfil ? user.id : 0;\n  const dono = `${perfil}:${empresaId}`;\n  const base = `/portal-${perfil}/entregas`;\n  const [deslocamento, setDeslocamento] = useState(0);\n  const [atualizacao, setAtualizacao] = useState(0);\n  const [lista, setLista] = useState<{ chave: string; pagina: PaginaContratacoes<OrdemEntrega> } | null>(null);\n  const [selecionadoId, setSelecionadoId] = useState(0);\n  const [carregando, setCarregando] = useState(true);\n  const [erroLista, setErroLista] = useState(\"\");\n  const [detalhe, setDetalhe] = useState<{ chave: string; dados: EntregasDetalhe } | null>(null);\n  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);\n  const [erroDetalhe, setErroDetalhe] = useState(\"\");\n  const [atualizacaoDetalhe, setAtualizacaoDetalhe] = useState(0);\n  const [rascunho, setRascunho] = useState({ chave: \"\", observacoes: \"\", motivo: \"\" });\n  const [revisao, setRevisao] = useState<Revisao | null>(null);\n  const [enviando, setEnviando] = useState(false);\n  const [aviso, setAviso] = useState<{ dono: string; texto: string } | null>(null);\n  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);\n  const [revalidar, setRevalidar] = useState(\"\");\n  const chaveLista = `${dono}:${deslocamento}:${atualizacao}`;\n  const pagina = lista?.chave === chaveLista ? lista.pagina : null;\n  const selecionada = pagina?.itens.find((o) => o.id === selecionadoId) ?? pagina?.itens[0];\n  const chaveSelecao = `${dono}:${selecionada?.id ?? 0}`;\n  const chaveDetalhe = `${chaveLista}:${chaveSelecao}:${atualizacaoDetalhe}`;\n  const dados = detalhe?.chave === chaveDetalhe ? detalhe.dados : null;\n  const ordem = dados?.ordem ?? selecionada;\n  const rascunhoAtual = rascunho.chave === chaveSelecao ? rascunho : { observacoes: \"\", motivo: \"\" };\n  const pendente = dados?.historico.find((e) => e.id === dados.ordem.entrega_pendente_id && e.status === \"entregue\");\n  const ativa = dados?.ordem.contratacao_status === \"ativa\" && dados.ordem.status === \"em_execucao\";\n  const podeRegistrar = perfil === \"fornecedor\" && ativa && !pendente && dados?.ordem.etapa_atual === \"pronto_para_envio\";\n  const podeDecidir = perfil === \"cliente\" && ativa && Boolean(pendente);\n  const bloquear = enviando || carregando || carregandoDetalhe || !dados || revalidar === chaveDetalhe;\n  const revisaoPermitida = revisao?.acao === \"registrar\" ? podeRegistrar : podeDecidir && revisao?.entregaId === pendente?.id;\n  const modalAtual = revisao?.chave === chaveDetalhe && revisao.dono === dono && revisaoPermitida && (!bloquear || enviando) ? revisao : null;\n  const parametrosEmpresa = perfil === \"cliente\" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };\n  const contexto = useRef({ chaveLista, chaveDetalhe, dono });\n  contexto.current = { chaveLista, chaveDetalhe, dono };\n  const montada = useRef(true);\n  const trava = useRef(false);\n  const envio = useRef<AbortController | null>(null);\n  const dialogo = useRef<HTMLDialogElement | null>(null);\n\n  useEffect(() => {\n    montada.current = true;\n    return () => { montada.current = false; envio.current?.abort(); };\n  }, []);\n  useEffect(() => { setDeslocamento(0); setSelecionadoId(0); setRevisao(null); envio.current?.abort(); }, [perfil, empresaId]);\n\n  useEffect(() => {\n    const controlador = new AbortController(); let vigente = true;\n    setCarregando(true); setErroLista(\"\"); setRevisao(null);\n    if (!empresaId) {\n      setErroLista(`Entre como ${perfil} para consultar as entregas.`); setCarregando(false);\n      return () => { vigente = false; controlador.abort(); };\n    }\n    async function carregar() {\n      try {\n        const { data } = await api.get<PaginaContratacoes<OrdemEntrega>>(base, {\n          params: { ...parametrosEmpresa, deslocamento, limite: 20 }, signal: controlador.signal, timeout: 20_000,\n        });\n        if (!vigente || contexto.current.chaveLista !== chaveLista) return;\n        if (data.total > 0 && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }\n        if (data.total === 0 && deslocamento > 0) { setDeslocamento(0); return; }\n        const proprias = data.itens.filter((o) => (perfil === \"cliente\" ? o.empresa_cliente_id : o.empresa_fornecedora_id) === empresaId);\n        setLista({ chave: chaveLista, pagina: { ...data, itens: proprias } });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.chaveLista === chaveLista) setErroLista(mensagemErroEntrega(erro));\n      } finally { if (vigente && contexto.current.chaveLista === chaveLista) setCarregando(false); }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, perfil, empresaId, deslocamento, chaveLista]);\n\n  useEffect(() => {\n    const controlador = new AbortController(); let vigente = true;\n    setCarregandoDetalhe(Boolean(selecionada)); setErroDetalhe(\"\"); setRevisao(null);\n    if (!selecionada) return () => { vigente = false; controlador.abort(); };\n    const ordemId = selecionada.id;\n    async function carregar() {\n      try {\n        const { data } = await api.get<EntregasDetalhe>(`${base}/${ordemId}`, {\n          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,\n        });\n        if (!vigente || contexto.current.chaveDetalhe !== chaveDetalhe) return;\n        const empresa = perfil === \"cliente\" ? data.ordem.empresa_cliente_id : data.ordem.empresa_fornecedora_id;\n        if (data.ordem.id !== ordemId || empresa !== empresaId || data.historico.some((e) => e.ordem_servico_id !== ordemId\n          || e.empresa_cliente_id !== data.ordem.empresa_cliente_id || e.empresa_fornecedora_id !== data.ordem.empresa_fornecedora_id)) throw new Error(\"Histórico divergente.\");\n        setDetalhe({ chave: chaveDetalhe, dados: data });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.chaveDetalhe === chaveDetalhe) setErroDetalhe(mensagemErroEntrega(erro));\n      } finally { if (vigente && contexto.current.chaveDetalhe === chaveDetalhe) setCarregandoDetalhe(false); }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, perfil, empresaId, selecionada?.id, chaveDetalhe]);\n\n  useEffect(() => {\n    const elemento = dialogo.current;\n    if (!elemento) return;\n    if (modalAtual && !elemento.open) elemento.showModal();\n    if (!modalAtual && elemento.open) elemento.close();\n  }, [modalAtual]);\n\n  function revisar(acao: AcaoEntrega) {\n    if (!dados || bloquear || trava.current || !(acao === \"registrar\" ? podeRegistrar : podeDecidir)) return;\n    const texto = acao === \"registrar\" ? rascunhoAtual.observacoes : acao === \"recusar\" ? rascunhoAtual.motivo : \"\";\n    if (texto.length > 5000 || (acao === \"recusar\" && !texto.trim())) {\n      setAviso({ dono, texto: acao === \"recusar\" && !texto.trim() ? \"Informe o motivo da recusa para que o fornecedor possa corrigir a entrega.\" : \"Limite o texto a 5000 caracteres.\" }); return;\n    }\n    setAviso(null); setSucesso(null);\n    setRevisao({ chave: chaveDetalhe, dono, ordem: dados.ordem, acao,\n      entregaId: acao === \"registrar\" ? null : pendente!.id, texto: texto.trim() || null });\n  }\n\n  async function confirmar() {\n    if (!modalAtual || bloquear || trava.current) return;\n    const confirmado = modalAtual; const controlador = new AbortController();\n    envio.current = controlador; trava.current = true; setEnviando(true); setAviso(null);\n    const url = confirmado.acao === \"registrar\" ? `/portal-fornecedor/entregas/${confirmado.ordem.id}/registrar`\n      : `/portal-cliente/entregas/${confirmado.ordem.id}/${confirmado.entregaId}/${confirmado.acao}`;\n    const corpo = confirmado.acao === \"registrar\" ? { empresa_fornecedora_id: empresaId, observacoes: confirmado.texto,\n      ultima_entrega_id: confirmado.ordem.ultima_entrega_id, ultima_etapa_id: confirmado.ordem.ultima_etapa_id }\n      : confirmado.acao === \"recusar\" ? { empresa_cliente_id: empresaId, motivo: confirmado.texto } : { empresa_cliente_id: empresaId };\n    try {\n      const { data } = await api.post<EntregaServico>(url, corpo, { signal: controlador.signal, timeout: 30_000 });\n      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== confirmado.dono || contexto.current.chaveDetalhe !== confirmado.chave) return;\n      const situacao = { registrar: \"entregue\", aceitar: \"aceita\", recusar: \"recusada\" }[confirmado.acao];\n      if (data.ordem_servico_id !== confirmado.ordem.id || data.empresa_cliente_id !== confirmado.ordem.empresa_cliente_id\n        || data.empresa_fornecedora_id !== confirmado.ordem.empresa_fornecedora_id || data.status !== situacao\n        || (confirmado.entregaId !== null && data.id !== confirmado.entregaId)) throw new Error(\"Resultado de entrega divergente.\");\n      const texto = confirmado.acao === \"registrar\" ? `Entrega #${data.id} registrada na OS #${data.ordem_servico_id}. Aguardando aceite do cliente.`\n        : confirmado.acao === \"aceitar\" ? `Entrega #${data.id} aceita. A OS #${data.ordem_servico_id} foi concluída e a contratação #${confirmado.ordem.contratacao_id} encerrada.`\n        : `Entrega #${data.id} recusada. O fornecedor já pode consultar o motivo e registrar uma nova entrega após a correção.`;\n      setSucesso({ dono, texto }); setRascunho({ chave: \"\", observacoes: \"\", motivo: \"\" }); setRevisao(null); setAtualizacao((v) => v + 1);\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.dono === confirmado.dono && contexto.current.chaveDetalhe === confirmado.chave) {\n        const status = typeof erro === \"object\" && erro !== null && \"response\" in erro ? (erro as { response?: { status?: number } }).response?.status : undefined;\n        const incerta = !status || status >= 500;\n        setAviso({ dono, texto: incerta ? \"A operação não pôde ser confirmada. Atualize o histórico e confira a entrega antes de tentar novamente.\" : mensagemErroEntrega(erro) });\n        if (incerta || status === 409) setRevalidar(chaveDetalhe);\n        setRevisao(null);\n      }\n    } finally {\n      if (envio.current === controlador) envio.current = null;\n      trava.current = false; if (montada.current) setEnviando(false);\n    }\n  }\n\n  function enviarFormulario(evento: FormEvent<HTMLFormElement>) { evento.preventDefault(); revisar(\"registrar\"); }\n\n  return <main className=\"p28-page\">\n    <header className=\"p28-header\"><div><p className=\"p28-eyebrow\"><PackageCheck size={16} /> PORTAL DO {perfil === \"cliente\" ? \"CLIENTE\" : \"FORNECEDOR\"}</p>\n      <h1>{perfil === \"cliente\" ? \"Entregas e Aceite\" : \"Entregas\"}</h1><p>{perfil === \"cliente\" ? \"Confira as entregas, aceite o serviço ou informe o motivo da recusa.\" : \"Registre as entregas e acompanhe a decisão dos seus clientes.\"}</p></div>\n      <button className=\"p28-button\" disabled={enviando || carregando} onClick={() => { setAviso(null); setAtualizacao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>\n    {sucesso?.dono === dono && <p className=\"p28-alert p28-success\" role=\"status\"><CheckCircle2 size={18} /> {sucesso.texto}</p>}\n    {aviso?.dono === dono && <p className=\"p28-alert p28-error\" role=\"alert\">{aviso.texto}</p>}\n    {erroLista && <p className=\"p28-alert p28-error\" role=\"alert\">{erroLista}</p>}\n    <div className=\"p28-summary\"><article><span>Ordens da sua empresa</span><strong>{pagina ? pagina.total : \"—\"}</strong><small>Inclui ordens abertas, em execução e finalizadas</small></article>\n      <article><span>Entrega da OS selecionada</span><strong className=\"p28-summary-stage\">{ordem ? rotuloEntrega(ordem.ultima_entrega_status) : \"—\"}</strong><small>{ordem ? `OS #${ordem.id} · ${rotuloOrdem(ordem.status)}` : \"Selecione uma ordem de serviço\"}</small></article>\n      <article><span>Entregas desta OS</span><strong>{ordem?.total_entregas ?? \"—\"}</strong><small>{ordem?.ultima_entrega_em ? `Última entrega: ${dataVisivel(ordem.ultima_entrega_em)}` : \"Ainda sem registro de entrega\"}</small></article></div>\n    <nav className=\"p28-tabs\"><Link className=\"p28-button\" to={`/${perfil}/producao`}><Factory size={16} /> {perfil === \"cliente\" ? \"Acompanhamento de Produção\" : \"Produção\"}</Link>\n      <Link className=\"p28-button\" to={`/${perfil}/ordens-servico`}><Wrench size={16} /> Ordens de Serviço e arquivos técnicos</Link></nav>\n    <section className=\"p28-panel\" aria-busy={carregando}><div className=\"p28-section-head\"><div><h2>Entregas dos serviços</h2><p>Selecione a ordem para consultar as entregas e as decisões do cliente.</p></div></div>\n      {carregando ? <div className=\"p28-empty\" role=\"status\">Carregando ordens…</div>\n        : !erroLista && pagina?.itens.length === 0 ? <div className=\"p28-empty\"><PackageCheck size={32} /><h3>Nenhuma ordem disponível</h3><p>{perfil === \"cliente\" ? \"Gere uma ordem de serviço a partir de uma contratação ativa.\" : \"O cliente precisa gerar a ordem de serviço para que ela apareça aqui.\"}</p></div>\n        : pagina && <div className=\"p28-table-wrap\"><table><thead><tr><th>Ordem / referência</th><th>{perfil === \"cliente\" ? \"Fornecedor\" : \"Cliente\"}</th><th>Última entrega</th><th>Situação da OS</th><th>Data da entrega</th><th><span className=\"p28-sr-only\">Ações</span></th></tr></thead><tbody>\n          {pagina.itens.map((linha) => { const selecionada = linha.id === ordem?.id; const atual = selecionada && dados ? dados.ordem : linha;\n            return <tr key={linha.id} className={selecionada ? \"p28-selected\" : \"\"}><td><strong>OS #{linha.id}</strong><small>Solicitação #{linha.solicitacao_id} · Contratação #{linha.contratacao_id}</small></td>\n              <td>{perfil === \"cliente\" ? linha.fornecedor_razao_social : linha.cliente_razao_social}<small>{linha.processo_nome} · {linha.material_nome}</small></td>\n              <td><span className={`p28-badge p28-entrega-${atual.ultima_entrega_status ?? \"vazia\"}`}>{rotuloEntrega(atual.ultima_entrega_status)}</span></td>\n              <td>{rotuloOrdem(atual.status)}</td><td>{dataVisivel(atual.ultima_entrega_em)}</td>\n              <td><button className=\"p28-button\" disabled={enviando} aria-pressed={selecionada} onClick={() => setSelecionadoId(linha.id)}>{selecionada ? \"Selecionada\" : \"Ver entregas\"}</button></td></tr>;\n          })}</tbody></table></div>}\n      {pagina && pagina.total > 0 && <div className=\"p28-pagination\"><span>{deslocamento + 1}–{Math.min(deslocamento + pagina.itens.length, pagina.total)} de {pagina.total}</span><div>\n        <button className=\"p28-button\" disabled={enviando || carregando || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => Math.max(0, v - 20)); }}>Anterior</button>\n        <button className=\"p28-button\" disabled={enviando || carregando || deslocamento + 20 >= pagina.total} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => v + 20); }}>Próxima</button></div></div>}\n    </section>\n    {selecionada && <section className=\"p28-panel p28-detail\" aria-busy={carregandoDetalhe}><div className=\"p28-section-head\"><h2><History size={20} /> Entregas da OS #{selecionada.id}</h2><button className=\"p28-button\" disabled={enviando || carregandoDetalhe} onClick={() => { setAviso(null); setAtualizacaoDetalhe((v) => v + 1); }}>Atualizar histórico</button></div>\n      {carregandoDetalhe ? <p role=\"status\">Carregando entregas…</p> : erroDetalhe ? <p className=\"p28-alert p28-error\" role=\"alert\">{erroDetalhe}</p> : dados && <div className=\"p28-columns\"><div><dl className=\"p28-fields\">\n        <div><dt>Cliente</dt><dd>{dados.ordem.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{dados.ordem.fornecedor_razao_social}</dd></div>\n        <div><dt>Valor total</dt><dd>{formatarValorCotacao(dados.ordem.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{dados.ordem.prazo_dias} dias</dd></div>\n        <div><dt>Quantidade da ordem</dt><dd>{dados.ordem.quantidade} unidades</dd></div><div><dt>Contratação</dt><dd>#{dados.ordem.contratacao_id} · {rotuloContratacao(dados.ordem.contratacao_status)}</dd></div>\n        <div><dt>Processo da ordem</dt><dd>{dados.ordem.processo_nome}</dd></div><div><dt>Material da ordem</dt><dd>{dados.ordem.material_nome}</dd></div>\n        <div className=\"p28-wide\"><dt>Dimensões máximas X / Y / Z</dt><dd>{[dados.ordem.solicitacao.dimensao_x_maxima_mm,dados.ordem.solicitacao.dimensao_y_maxima_mm,dados.ordem.solicitacao.dimensao_z_maxima_mm].map((v) => formatarMedidaContrato(v)).join(\" × \")} mm</dd></div>\n        <div><dt>Situação da OS</dt><dd>{rotuloOrdem(dados.ordem.status)}</dd></div><div><dt>Etapa de produção</dt><dd>{rotuloEtapa(dados.ordem.etapa_atual)}</dd></div></dl>\n        {perfil === \"fornecedor\" && (podeRegistrar ? <form className=\"p28-form\" onSubmit={enviarFormulario}><fieldset disabled={bloquear}>\n          <h3>Registrar entrega</h3><label htmlFor=\"p28-observacoes\">Observações da entrega (opcional)</label><textarea id=\"p28-observacoes\" maxLength={5000} rows={4} value={rascunhoAtual.observacoes}\n            onChange={(e) => setRascunho({ chave: chaveSelecao, observacoes: e.target.value, motivo: rascunhoAtual.motivo })} placeholder=\"Descreva a entrega e as informações necessárias para o recebimento.\" />\n          <p>O cliente poderá aceitar a entrega ou recusá-la com um motivo.</p><button type=\"submit\" className=\"p28-button p28-primary\" disabled={bloquear}><ClipboardList size={16} /> Revisar entrega</button>\n        </fieldset></form> : <p className=\"p28-readonly\">{dados.ordem.contratacao_status !== \"ativa\" ? \"A contratação está finalizada. As entregas continuam disponíveis para consulta.\"\n          : [\"concluida\", \"cancelada\"].includes(dados.ordem.status) ? \"Esta OS está concluída ou cancelada. As entregas continuam disponíveis para consulta.\"\n          : pendente ? `A entrega #${pendente.id} aguarda a decisão do cliente. Consulte o histórico para acompanhar o aceite ou a recusa.`\n          : dados.ordem.status !== \"em_execucao\" ? \"Inicie esta OS em Ordens de Serviço antes de registrar a entrega.\"\n          : \"Registre Pronto para envio como etapa atual na página Produção antes de entregar.\"}</p>)}\n        {perfil === \"cliente\" && (podeDecidir ? <div className=\"p28-form\"><fieldset disabled={bloquear}><h3>Decidir entrega #{pendente!.id}</h3>\n          <p>Confira os dados e as observações da entrega no histórico antes de decidir.</p><label htmlFor=\"p28-motivo\">Motivo da recusa (obrigatório para recusar)</label><textarea id=\"p28-motivo\" maxLength={5000} rows={4} value={rascunhoAtual.motivo}\n            onChange={(e) => setRascunho({ chave: chaveSelecao, motivo: e.target.value, observacoes: rascunhoAtual.observacoes })} placeholder=\"Explique o que precisa ser corrigido, caso recuse a entrega.\" />\n          <div className=\"p28-decision-actions\"><button className=\"p28-button p28-primary\" disabled={bloquear} onClick={() => revisar(\"aceitar\")}>Aceitar entrega</button>\n            <button className=\"p28-button p28-danger\" disabled={bloquear} onClick={() => revisar(\"recusar\")}>Recusar entrega</button></div></fieldset></div>\n          : <p className=\"p28-readonly\">{pendente ? \"A ordem ou a contratação está finalizada. A entrega permanece disponível para consulta.\" : \"Nenhuma entrega aguardando sua decisão. Use Atualizar histórico para conferir novos registros.\"}</p>)}\n      </div><div className=\"p28-history\"><h3>Histórico de entregas</h3>{dados.historico.length === 0 ? <div className=\"p28-history-empty\"><PackageCheck size={25} /><p>Nenhuma entrega registrada para esta ordem.</p></div>\n        : <ol className=\"p28-timeline\">{dados.historico.slice().reverse().map((entrega) => <li key={entrega.id}><span className=\"p28-timeline-dot\" /><article><h4>Entrega #{entrega.id} <span className={`p28-badge p28-entrega-${entrega.status}`}>{rotuloEntrega(entrega.status)}</span></h4>\n          <p className=\"p28-history-date\">Entregue em <time dateTime={dataHora(entrega.entregue_em)}>{dataVisivel(entrega.entregue_em)}</time></p><p className=\"p28-observacoes\">{entrega.observacoes || \"Sem observações da entrega.\"}</p>\n          {entrega.aceita_em && <p className=\"p28-history-date\">Aceita em <time dateTime={dataHora(entrega.aceita_em)}>{dataVisivel(entrega.aceita_em)}</time></p>}\n          {entrega.recusada_em && <><p className=\"p28-history-date\">Recusada em <time dateTime={dataHora(entrega.recusada_em)}>{dataVisivel(entrega.recusada_em)}</time></p><h5>Motivo da recusa</h5><p className=\"p28-observacoes p28-refusal-reason\">{entrega.motivo_recusa || \"Motivo não informado no registro anterior.\"}</p></>}\n        </article></li>)}</ol>}</div></div>}\n    </section>}\n    <dialog ref={dialogo} className=\"p28-dialog\" aria-labelledby=\"p28-dialog-title\" onCancel={(e) => { if (trava.current) e.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>\n      {modalAtual && <><div className=\"p28-section-head\"><h2 id=\"p28-dialog-title\">{modalAtual.acao === \"registrar\" ? \"Confirmar registro de entrega\" : modalAtual.acao === \"aceitar\" ? \"Confirmar aceite da entrega\" : \"Confirmar recusa da entrega\"}</h2>\n        <button className=\"p28-button\" aria-label=\"Fechar revisão\" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>\n        <dl className=\"p28-fields\"><div><dt>Ordem de serviço</dt><dd>#{modalAtual.ordem.id}</dd></div><div><dt>Contratação</dt><dd>#{modalAtual.ordem.contratacao_id}</dd></div>\n          <div><dt>Cliente</dt><dd>{modalAtual.ordem.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{modalAtual.ordem.fornecedor_razao_social}</dd></div>\n          {modalAtual.entregaId && <div><dt>Entrega</dt><dd>#{modalAtual.entregaId}</dd></div>}</dl>\n        {modalAtual.acao === \"aceitar\" ? <p className=\"p28-review-effect\">Ao confirmar o aceite, esta entrega será aceita, a OS será concluída e a contratação encerrada.</p>\n          : <><h3>{modalAtual.acao === \"registrar\" ? \"Observações da entrega\" : \"Motivo da recusa\"}</h3><p className=\"p28-observacoes\">{modalAtual.texto || \"Sem observações da entrega.\"}</p>\n            <p className=\"p28-review-effect\">{modalAtual.acao === \"registrar\" ? \"A entrega ficará aguardando o aceite do cliente. A OS continuará em execução e a contratação ativa.\"\n              : \"A entrega será recusada com este motivo. A OS continuará em execução e a contratação ativa, permitindo outra entrega após a correção.\"}</p></>}\n        <div className=\"p28-dialog-actions\"><button className=\"p28-button\" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button>\n          <button className={`p28-button ${modalAtual.acao === \"recusar\" ? \"p28-danger\" : \"p28-primary\"}`} disabled={enviando} onClick={() => void confirmar()}>{enviando ? \"Confirmando…\" : modalAtual.acao === \"registrar\" ? \"Confirmar entrega\" : modalAtual.acao === \"aceitar\" ? \"Confirmar aceite\" : \"Confirmar recusa\"}</button></div>\n      </>}\n    </dialog>\n  </main>;\n}\n",
  "frontend/src/pages/entregas/entregasPortal.ts": "import type { OrdemProducao } from \"../producao/producaoPortal\";\n\nexport type EntregaServico = {\n  id: number; ordem_servico_id: number; empresa_fornecedora_id: number; empresa_cliente_id: number;\n  status: string; observacoes: string | null; motivo_recusa: string | null;\n  criada_em: string; entregue_em: string; aceita_em: string | null; recusada_em: string | null;\n};\nexport type OrdemEntrega = OrdemProducao & {\n  ultima_entrega_id: number; ultima_entrega_status: string | null; ultima_entrega_em: string | null;\n  total_entregas: number; entrega_pendente_id: number | null;\n};\nexport type EntregasDetalhe = { ordem: OrdemEntrega; historico: EntregaServico[] };\nexport type AcaoEntrega = \"registrar\" | \"aceitar\" | \"recusar\";\n\nexport function rotuloEntrega(situacao: string | null): string {\n  return ({ entregue: \"Aguardando aceite\", aceita: \"Aceita\", recusada: \"Recusada\" } as Record<string, string>)[situacao ?? \"\"]\n    ?? (situacao ? \"Situação indisponível\" : \"Sem entrega registrada\");\n}\n\nexport function mensagemErroEntrega(erro: unknown): string {\n  if (typeof erro === \"object\" && erro !== null && \"response\" in erro) {\n    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;\n    const mensagens: Record<string, string> = {\n      empresa_cliente_nao_encontrada: \"A empresa cliente deste acesso não foi encontrada.\",\n      empresa_fornecedor_nao_encontrada: \"A empresa fornecedora deste acesso não foi encontrada.\",\n      empresa_nao_e_cliente: \"Entre como cliente para consultar e decidir suas entregas.\",\n      empresa_nao_e_fornecedor: \"Entre como fornecedor para consultar e registrar suas entregas.\",\n      ordem_servico_nao_encontrada: \"A ordem não está disponível para esta empresa. Atualize a lista.\",\n      entrega_nao_encontrada: \"A entrega não está disponível nesta ordem. Atualize o histórico.\",\n      contratacao_nao_esta_ativa: \"A contratação precisa estar ativa. Atualize a tela.\",\n      ordem_servico_nao_pode_receber_entrega: \"A ordem precisa estar em execução para registrar ou decidir a entrega. Atualize a tela.\",\n      ordem_servico_nao_esta_pronta_para_entrega: \"Registre Pronto para envio como etapa atual na página Produção antes de entregar.\",\n      empresa_nao_e_fornecedora_da_ordem_servico: \"Somente o fornecedor responsável pode registrar esta entrega.\",\n      empresa_nao_e_cliente_da_ordem_servico: \"Somente o cliente responsável pode decidir esta entrega.\",\n      entrega_pendente_ja_existe: \"Já existe uma entrega aguardando aceite nesta ordem. Atualize o histórico.\",\n      entrega_nao_esta_pendente: \"Esta entrega já recebeu uma decisão. Atualize o histórico antes de continuar.\",\n      motivo_recusa_obrigatorio: \"Informe o motivo da recusa para que o fornecedor possa corrigir a entrega.\",\n      entregas_alteradas_atualize: \"As entregas desta ordem foram alteradas. Atualize o histórico antes de continuar.\",\n      producao_alterada_atualize: \"A produção recebeu outra atualização. Atualize a tela e confira a etapa atual.\",\n      ordem_servico_alterada_atualize: \"A ordem foi alterada durante a operação. Atualize a tela antes de continuar.\",\n    };\n    if (typeof detalhe === \"string\") return mensagens[detalhe] ?? \"Não foi possível concluir a operação. Atualize a tela e tente novamente.\";\n    if (Array.isArray(detalhe)) return \"Confira os campos e limite as observações e o motivo da recusa a 5000 caracteres.\";\n  }\n  return \"Não foi possível consultar os dados. Confira a conexão e atualize a tela.\";\n}\n",
  "tests/test_portal_entregas.py": "from __future__ import annotations\n\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi import FastAPI\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine, event, select, update\nfrom sqlalchemy.orm import Session, sessionmaker\n\nfrom backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos\nfrom backend.app.api.rotas.ordens_servico import roteador as original\nfrom backend.app.api.rotas.portal_ordens_servico import roteador as ordens\nfrom backend.app.api.rotas.portal_producao import roteador as producao\nfrom backend.app.api.rotas.portal_entregas import roteador as portal\nfrom backend.app.api.rotas.entregas import roteador as entregas_original\nfrom backend.app.api.rotas.etapas_producao import roteador as etapas\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.etapa_producao import EtapaProducao\nfrom backend.app.models.entrega import EntregaServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\n\nCLIENTE = \"/api/v1/portal-cliente\"\nFORNECEDOR = \"/api/v1/portal-fornecedor\"\n\n\ndef novo_contrato(banco, numero, cliente=1, fornecedor=2, situacao=\"ativa\"):\n    pedido = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,\n        dimensao_x_maxima_mm=500, dimensao_y_maxima_mm=300, dimensao_z_maxima_mm=250,\n        tolerancia_requerida_mm=Decimal(\"0.0200\"), quantidade=5, status=\"encerrada\", observacoes=\"Pedido D28.\")\n    banco.add(pedido)\n    banco.flush()\n    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=numero, empresa_fornecedora_id=fornecedor,\n        valor_total=Decimal(\"1250.50\"), prazo_dias=15, validade_dias=10, status=\"aceita\",\n        decidida_por_empresa_id=cliente, encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None))\n    banco.add(cotacao)\n    banco.flush()\n    contrato = ContratacaoServico(id=numero, solicitacao_id=numero, cotacao_id=numero,\n        empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, valor_total=Decimal(\"1250.50\"),\n        prazo_dias=15, status=situacao, observacoes=\"Termos da contratação D28.\")\n    banco.add(contrato)\n    banco.flush()\n    return contrato\n\n\n@pytest.fixture()\ndef ambiente(tmp_path, monkeypatch):\n    engine = create_engine(f\"sqlite:///{tmp_path / 'portal_entregas_teste.db'}\", connect_args={\"check_same_thread\": False})\n\n    @event.listens_for(engine, \"connect\")\n    def chaves(conexao, _):\n        conexao.execute(\"PRAGMA foreign_keys=ON\")\n\n    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)\n    Base.metadata.create_all(engine)\n    monkeypatch.setattr(ServicoArquivoTecnico, \"STORAGE_ROOT\", tmp_path)\n    with sessoes() as banco:\n        banco.add_all([\n            Empresa(id=1, razao_social=\"Cliente D28\", documento=\"cliente-d28-1\", tipo_empresa=\"cliente\"),\n            Empresa(id=2, razao_social=\"Fornecedor D28\", documento=\"fornecedor-d28-2\", tipo_empresa=\"fornecedor\"),\n            Empresa(id=3, razao_social=\"Outro Fornecedor\", documento=\"fornecedor-d28-3\", tipo_empresa=\"fornecedor\"),\n            Empresa(id=4, razao_social=\"Empresa Ambos\", documento=\"ambos-d28-4\", tipo_empresa=\"ambos\"),\n            Empresa(id=5, razao_social=\"Outro Cliente\", documento=\"cliente-d28-5\", tipo_empresa=\"cliente\"),\n            ProcessoFabricacao(id=1, codigo=\"cnc-d28\", nome=\"Usinagem CNC\"),\n            Material(id=1, codigo=\"al6061-d28\", nome=\"Alumínio 6061\"),\n        ])\n        banco.commit()\n        novo_contrato(banco, 1)\n        novo_contrato(banco, 2, cliente=5, fornecedor=3)\n        novo_contrato(banco, 3, situacao=\"cancelada\")\n        novo_contrato(banco, 4, situacao=\"encerrada\")\n        novo_contrato(banco, 5)\n        banco.commit()\n\n    def banco_teste():\n        with sessoes() as banco:\n            yield banco\n\n    app = FastAPI()\n    for roteador in (arquivos, original, ordens, etapas, producao, entregas_original, portal):\n        app.include_router(roteador, prefix=\"/api/v1\")\n    app.dependency_overrides[obter_banco] = banco_teste\n    try:\n        with TestClient(app) as http:\n            yield http, sessoes\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(engine)\n        engine.dispose()\n\n\n\ndef gerar(http, contrato=1, cliente=1):\n    return http.post(f\"{CLIENTE}/contratacoes/{contrato}/ordem-servico\", json={\"empresa_cliente_id\":cliente})\n\n\ndef iniciar(http, oid, fornecedor=2):\n    return http.post(f\"{FORNECEDOR}/ordens-servico/{oid}/iniciar\", json={\"empresa_fornecedora_id\":fornecedor})\n\n\ndef etapa(http, oid, valor=\"pronto_para_envio\", fornecedor=2, ultima=0):\n    return http.post(f\"{FORNECEDOR}/producao/{oid}/etapas\",json={\"empresa_fornecedora_id\":fornecedor,\n        \"etapa\":valor,\"ultima_etapa_id\":ultima,\"observacoes\":\"Etapa para entrega D28.\"})\n\n\ndef preparar(http, contrato=1, cliente=1, fornecedor=2):\n    oid=gerar(http,contrato,cliente).json()[\"id\"]\n    assert iniciar(http,oid,fornecedor).status_code == 200\n    eid=etapa(http,oid,fornecedor=fornecedor).json()[\"id\"]\n    return oid,eid\n\n\ndef detalhe(http, oid, perfil=\"cliente\", empresa=1):\n    return http.get(f\"/api/v1/portal-{perfil}/entregas/{oid}\",params={\n        \"empresa_cliente_id\" if perfil==\"cliente\" else \"empresa_fornecedora_id\":empresa})\n\n\ndef listar(http, perfil=\"cliente\", empresa=1, **extra):\n    return http.get(f\"/api/v1/portal-{perfil}/entregas\",params={\n        \"empresa_cliente_id\" if perfil==\"cliente\" else \"empresa_fornecedora_id\":empresa,**extra})\n\n\ndef registrar(http,oid,eid,fornecedor=2,ultima=0,**extra):\n    return http.post(f\"{FORNECEDOR}/entregas/{oid}/registrar\",json={\"empresa_fornecedora_id\":fornecedor,\n        \"ultima_etapa_id\":eid,\"ultima_entrega_id\":ultima,\"observacoes\":\"Peças entregues com identificação.\",**extra})\n\n\ndef decidir(http,oid,entrega,acao=\"aceitar\",cliente=1,**extra):\n    return http.post(f\"{CLIENTE}/entregas/{oid}/{entrega}/{acao}\",json={\"empresa_cliente_id\":cliente,**extra})\n\n\ndef test_lista_ordens_sem_entrega_e_consulta_apenas_donos(ambiente):\n    http,_=ambiente\n    oid=gerar(http).json()[\"id\"]\n    item=listar(http).json()[\"itens\"][0]\n    assert item == listar(http,\"fornecedor\",2).json()[\"itens\"][0]\n    assert item[\"id\"] == oid and item[\"ultima_entrega_id\"]==item[\"total_entregas\"]==0\n    assert item[\"ultima_entrega_status\"] is None and item[\"entrega_pendente_id\"] is None\n    assert listar(http,\"cliente\",5).json()[\"total\"]==0\n    assert listar(http,\"fornecedor\",3).json()[\"total\"]==0\n    assert detalhe(http,oid,\"cliente\",5).status_code == 404\n    assert detalhe(http,oid,\"fornecedor\",3).status_code == 404\n\n\ndef test_fluxo_entrega_aceite_conclui_ordem_e_encerra_contratacao(ambiente):\n    http,sessoes=ambiente\n    oid,eid=preparar(http)\n    resposta=registrar(http,oid,eid)\n    assert resposta.status_code==201\n    entrega=resposta.json();did=entrega[\"id\"]\n    assert entrega[\"status\"]==\"entregue\" and entrega[\"entregue_em\"] and entrega[\"aceita_em\"] is None\n    antes=detalhe(http,oid).json()\n    assert antes==detalhe(http,oid,\"fornecedor\",2).json()\n    assert antes[\"ordem\"][\"status\"]==\"em_execucao\" and antes[\"ordem\"][\"contratacao_status\"]==\"ativa\"\n    assert antes[\"ordem\"][\"entrega_pendente_id\"]==did and antes[\"historico\"]==[entrega]\n    aceita=decidir(http,oid,did)\n    assert aceita.status_code==200 and aceita.json()[\"status\"]==\"aceita\"\n    assert aceita.json()[\"aceita_em\"] and aceita.json()[\"recusada_em\"] is None\n    dados=detalhe(http,oid).json()\n    assert dados[\"ordem\"][\"status\"]==\"concluida\" and dados[\"ordem\"][\"contratacao_status\"]==\"encerrada\"\n    assert dados[\"ordem\"][\"total_entregas\"]==1 and dados[\"ordem\"][\"entrega_pendente_id\"] is None\n    assert listar(http,\"fornecedor\",2).json()[\"itens\"][0][\"ultima_entrega_status\"]==\"aceita\"\n    with sessoes() as banco:\n        ordem=banco.get(OrdemServico,oid);contrato=banco.get(ContratacaoServico,1)\n        assert ordem.concluida_em==contrato.encerrada_em==banco.get(EntregaServico,did).aceita_em\n        assert str(ordem.valor_total)==\"1250.50\" and ordem.quantidade==5 and ordem.prazo_dias==15\n        assert banco.scalars(select(EtapaProducao)).one().id==eid\n\n\n@pytest.mark.parametrize(\"motivo\",[None,\"\",\"   \"])\ndef test_recusa_sem_motivo_nao_muda_entrega_ordem_ou_contrato(ambiente,motivo):\n    http,_=ambiente\n    oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    assert decidir(http,oid,did,\"recusar\",motivo=motivo).status_code==422\n    dados=detalhe(http,oid).json()\n    assert dados[\"historico\"][0][\"status\"]==\"entregue\" and dados[\"historico\"][0][\"recusada_em\"] is None\n    assert dados[\"ordem\"][\"status\"]==\"em_execucao\" and dados[\"ordem\"][\"contratacao_status\"]==\"ativa\"\n\n\ndef test_recusa_correcao_nova_entrega_e_aceite_preservam_os_registros(ambiente):\n    http,_=ambiente\n    oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    recusada=decidir(http,oid,did,\"recusar\",motivo=\"  Corrigir identificação das peças.  \")\n    assert recusada.status_code==200 and recusada.json()[\"motivo_recusa\"]==\"Corrigir identificação das peças.\"\n    dados=detalhe(http,oid).json()\n    assert dados[\"ordem\"][\"status\"]==\"em_execucao\" and dados[\"ordem\"][\"contratacao_status\"]==\"ativa\"\n    assert dados[\"ordem\"][\"entrega_pendente_id\"] is None\n    assert registrar(http,oid,eid).status_code==409\n    nova=registrar(http,oid,eid,ultima=did,observacoes=\"Identificação corrigida.\")\n    assert nova.status_code==201\n    assert decidir(http,oid,nova.json()[\"id\"]).status_code==200\n    historico=detalhe(http,oid).json()[\"historico\"]\n    assert [e[\"status\"] for e in historico]==[\"recusada\",\"aceita\"]\n    assert historico[0][\"observacoes\"]==\"Peças entregues com identificação.\"\n    assert historico[0][\"motivo_recusa\"]==\"Corrigir identificação das peças.\" and historico[0][\"recusada_em\"]\n    assert historico[1][\"observacoes\"]==\"Identificação corrigida.\"\n\n\n@pytest.mark.parametrize(\"situacao\",[\"aberta\",\"concluida\",\"cancelada\"])\ndef test_ordem_fora_de_execucao_nao_recebe_entrega(ambiente,situacao):\n    http,sessoes=ambiente;oid=gerar(http).json()[\"id\"]\n    with sessoes() as banco:\n        banco.get(OrdemServico,oid).status=situacao;banco.commit()\n    assert registrar(http,oid,0).status_code==409\n    assert detalhe(http,oid).json()[\"historico\"]==[]\n\n\ndef test_exige_ultima_etapa_pronto_para_envio(ambiente):\n    http,_=ambiente;oid=gerar(http).json()[\"id\"];iniciar(http,oid)\n    assert registrar(http,oid,0).status_code==409\n    eid=etapa(http,oid).json()[\"id\"]\n    outra=etapa(http,oid,\"em_acabamento\",ultima=eid).json()[\"id\"]\n    assert registrar(http,oid,eid).json()[\"detail\"]==\"producao_alterada_atualize\"\n    assert registrar(http,oid,outra).json()[\"detail\"]==\"ordem_servico_nao_esta_pronta_para_entrega\"\n    assert detalhe(http,oid).json()[\"historico\"]==[]\n\n\ndef test_nao_aceita_revisao_de_producao_antiga_mesmo_que_esteja_pronta(ambiente):\n    http,_=ambiente;oid,eid=preparar(http)\n    outra=etapa(http,oid,ultima=eid).json()[\"id\"]\n    assert registrar(http,oid,eid).status_code==409\n    assert registrar(http,oid,outra).status_code==201\n\n\ndef test_entrega_pendente_impede_novo_registro_e_repeticao_do_envio(ambiente):\n    http,_=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    assert registrar(http,oid,eid).json()[\"detail\"]==\"entregas_alteradas_atualize\"\n    assert registrar(http,oid,eid,ultima=did).json()[\"detail\"]==\"entrega_pendente_ja_existe\"\n    assert detalhe(http,oid).json()[\"ordem\"][\"total_entregas\"]==1\n\n\n@pytest.mark.parametrize(\"empresa,codigo\",[(3,404),(1,403),(999,404)])\ndef test_outro_fornecedor_ou_perfil_nao_pode_entregar(ambiente,empresa,codigo):\n    http,_=ambiente;oid,eid=preparar(http)\n    assert registrar(http,oid,eid,fornecedor=empresa).status_code==codigo\n    assert detalhe(http,oid).json()[\"historico\"]==[]\n\n\n@pytest.mark.parametrize(\"empresa,codigo\",[(5,404),(2,403),(999,404)])\ndef test_outro_cliente_ou_perfil_nao_pode_decidir(ambiente,empresa,codigo):\n    http,_=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    assert decidir(http,oid,did,cliente=empresa).status_code==codigo\n    assert decidir(http,oid,did,\"recusar\",cliente=empresa,motivo=\"Teste.\").status_code==codigo\n    assert detalhe(http,oid).json()[\"historico\"][0][\"status\"]==\"entregue\"\n\n\n@pytest.mark.parametrize(\"campos\",[{\"ultima_etapa_id\":-1},{\"ultima_entrega_id\":-1},{\"empresa_fornecedora_id\":0},\n    {\"observacoes\":\"x\"*5001},{\"empresa_cliente_id\":1},{\"status\":\"aceita\"}])\ndef test_campos_invalidos_do_registro_nao_gravam(ambiente,campos):\n    http,_=ambiente;oid,eid=preparar(http)\n    assert registrar(http,oid,eid,**campos).status_code==422\n    assert detalhe(http,oid).json()[\"historico\"]==[]\n\n\ndef test_decisao_valida_campos_e_papel_e_exige_versoes_no_registro(ambiente):\n    http,_=ambiente;oid,eid=preparar(http)\n    assert http.post(f\"{FORNECEDOR}/entregas/{oid}/registrar\",json={\"empresa_fornecedora_id\":2}).status_code==422\n    did=registrar(http,oid,eid).json()[\"id\"]\n    for campos in ({\"motivo\":\"x\"*5001},{\"empresa_fornecedora_id\":2},{\"status\":\"aceita\"}):\n        assert decidir(http,oid,did,\"recusar\",**campos).status_code==422\n    assert http.post(f\"{FORNECEDOR}/entregas/{oid}/{did}/aceitar\",json={\"empresa_cliente_id\":1}).status_code==404\n    assert http.post(f\"{CLIENTE}/entregas/{oid}/registrar\",json={\"empresa_fornecedora_id\":2}).status_code==404\n\n\n@pytest.mark.parametrize(\"parametros,codigo\",[({},422),({\"empresa_cliente_id\":0},422),\n    ({\"empresa_cliente_id\":1,\"limite\":101},422),({\"empresa_cliente_id\":1,\"deslocamento\":-1},422),\n    ({\"empresa_cliente_id\":2},403),({\"empresa_cliente_id\":999},404)])\ndef test_consulta_valida_empresa_e_paginacao(ambiente,parametros,codigo):\n    http,_=ambiente\n    assert http.get(CLIENTE+\"/entregas\",params=parametros).status_code==codigo\n\n\n@pytest.mark.parametrize(\"situacao\",[\"cancelada\",\"encerrada\"])\ndef test_contrato_finalizado_bloqueia_registro_e_decisoes_preservando_historico(ambiente,situacao):\n    http,sessoes=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    with sessoes() as banco:\n        banco.get(ContratacaoServico,1).status=situacao;banco.commit()\n    assert registrar(http,oid,eid,ultima=did).status_code==409\n    assert decidir(http,oid,did).status_code==409\n    assert decidir(http,oid,did,\"recusar\",motivo=\"Correção.\").status_code==409\n    assert detalhe(http,oid).json()[\"historico\"][0][\"status\"]==\"entregue\"\n\n\ndef test_nao_mistura_entregas_de_outra_ordem_e_resumos_paginados(ambiente):\n    http,_=ambiente;a,ea=preparar(http);b,eb=preparar(http,5)\n    da=registrar(http,a,ea).json()[\"id\"];db=registrar(http,b,eb).json()[\"id\"]\n    assert decidir(http,a,db).status_code==404\n    assert decidir(http,b,da,\"recusar\",motivo=\"Correção.\").status_code==404\n    assert detalhe(http,a).json()[\"ordem\"][\"entrega_pendente_id\"]==da\n    assert detalhe(http,b).json()[\"ordem\"][\"entrega_pendente_id\"]==db\n    p1=listar(http,limite=1).json();p2=listar(http,deslocamento=1,limite=1).json()\n    assert p1[\"total\"]==p2[\"total\"]==2\n    assert p1[\"itens\"][0][\"id\"]==b and p2[\"itens\"][0][\"id\"]==a\n\n\n@pytest.mark.parametrize(\"acao\",[\"aceitar\",\"recusar\"])\ndef test_entrega_decidida_nao_recebe_nova_decisao(ambiente,acao):\n    http,_=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    assert decidir(http,oid,did,acao,motivo=\"Correção.\").status_code==200\n    assert decidir(http,oid,did,\"aceitar\").status_code==409\n    assert decidir(http,oid,did,\"recusar\",motivo=\"Outra decisão.\").status_code==409\n\n\ndef test_entregas_antigas_do_d11_aparecem_sem_migracao(ambiente):\n    http,_=ambiente;oid,eid=preparar(http)\n    antiga=http.post(f\"/api/v1/ordens-servico/{oid}/entregas\",json={\"empresa_fornecedora_id\":2,\"observacoes\":\"Anterior ao D28.\"})\n    assert antiga.status_code==201\n    assert detalhe(http,oid).json()[\"historico\"]==[antiga.json()]\n    assert decidir(http,oid,antiga.json()[\"id\"],\"recusar\",motivo=\"Corrigir.\").status_code==200\n    assert registrar(http,oid,eid,ultima=antiga.json()[\"id\"]).status_code==201\n\n\ndef test_empresa_ambos_utiliza_cada_perfil(ambiente):\n    http,sessoes=ambiente\n    with sessoes() as banco:\n        novo_contrato(banco,6,cliente=4,fornecedor=4);banco.commit()\n    oid,eid=preparar(http,6,4,4);did=registrar(http,oid,eid,fornecedor=4).json()[\"id\"]\n    assert listar(http,\"cliente\",4).json()[\"total\"]==listar(http,\"fornecedor\",4).json()[\"total\"]==1\n    assert decidir(http,oid,did,cliente=4).status_code==200\n\n\ndef test_duas_sessoes_com_mesma_revisao_criam_so_uma_entrega(ambiente):\n    from concurrent.futures import ThreadPoolExecutor\n    http,_=ambiente;oid,eid=preparar(http)\n    with ThreadPoolExecutor(max_workers=2) as executor:\n        respostas=list(executor.map(lambda _:registrar(http,oid,eid),range(2)))\n    assert sorted(r.status_code for r in respostas)==[201,409]\n    assert detalhe(http,oid).json()[\"ordem\"][\"total_entregas\"]==1\n\n\ndef test_aceite_e_recusa_concorrentes_resultam_em_uma_so_decisao(ambiente):\n    from concurrent.futures import ThreadPoolExecutor\n    http,sessoes=ambiente;oid,eid=preparar(http);did=registrar(http,oid,eid).json()[\"id\"]\n    with ThreadPoolExecutor(max_workers=2) as executor:\n        respostas=list(executor.map(lambda acao:decidir(http,oid,did,acao,motivo=\"Corrigir.\"),(\"aceitar\",\"recusar\")))\n    assert sorted(r.status_code for r in respostas)==[200,409]\n    with sessoes() as banco:\n        entrega=banco.get(EntregaServico,did);ordem=banco.get(OrdemServico,oid);contrato=banco.get(ContratacaoServico,1)\n        if entrega.status==\"aceita\":\n            assert entrega.aceita_em and entrega.recusada_em is None\n            assert ordem.status==\"concluida\" and contrato.status==\"encerrada\"\n        else:\n            assert entrega.status==\"recusada\" and entrega.recusada_em and entrega.aceita_em is None\n            assert ordem.status==\"em_execucao\" and contrato.status==\"ativa\"\n"
}
ALVOS = (APP_REL, ROUTER_REL, *(Path(nome) for nome in FONTES))
IMPORT_LINE = 'import PortalEntregasPage from "./pages/entregas/PortalEntregasPage";'


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
        raise RuntimeError("Campos ausentes no portal de entregas: " + ", ".join(sorted(ausentes)))

for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    base = "/api/v1/portal-" + perfil + "/entregas"
    for sufixo in ("", "/{ordem_id}"):
        op = paths.get(base + sufixo, {}).get("get")
        if not op:
            raise RuntimeError("Rota de entregas do portal ausente: " + base + sufixo)
        params = {p["name"]: p for p in op.get("parameters", [])}
        if not params.get(empresa, {}).get("required"):
            raise RuntimeError("Consulta de entregas sem empresa obrigatória.")
        dados = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
        if sufixo:
            campos(dados, ("ordem", "historico"))
            dados = schema(dados["properties"]["ordem"])
        else:
            campos(dados, ("itens", "total", "limite", "deslocamento"))
            if not {"limite", "deslocamento"}.issubset(params):
                raise RuntimeError("Listagem de entregas sem paginação.")
            dados = schema(schema(dados["properties"]["itens"])["items"])
        campos(dados, ("id", "contratacao_id", "empresa_cliente_id", "empresa_fornecedora_id", "status",
                       "cliente_razao_social", "fornecedor_razao_social", "etapa_atual", "ultima_etapa_id",
                       "ultima_entrega_id", "ultima_entrega_status", "total_entregas", "entrega_pendente_id"))
op = paths.get("/api/v1/portal-fornecedor/entregas/{ordem_id}/registrar", {}).get("post")
if not op:
    raise RuntimeError("Registro de entrega do portal do fornecedor ausente.")
corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
campos(corpo, ("empresa_fornecedora_id", "observacoes", "ultima_entrega_id", "ultima_etapa_id"))
if set(corpo.get("required", [])) != {"empresa_fornecedora_id", "ultima_etapa_id", "ultima_entrega_id"}:
    raise RuntimeError("Registro de entrega sem empresa e versões obrigatórias.")
for acao in ("aceitar", "recusar"):
    op = paths.get("/api/v1/portal-cliente/entregas/{ordem_id}/{entrega_id}/" + acao, {}).get("post")
    if not op:
        raise RuntimeError("Decisão de entrega do portal do cliente ausente: " + acao)
    corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
    campos(corpo, ("empresa_cliente_id", "motivo"))
    if set(corpo.get("required", [])) != {"empresa_cliente_id"}:
        raise RuntimeError("Decisão de entrega sem empresa cliente obrigatória.")
print("ENTREGAS_CLIENTE_FORNECEDOR_PAGINADAS_OK=True")
print("REGISTRO_ACEITE_RECUSA_E_HISTORICO_OK=True")
print("CONTROLE_REVISAO_E_DECISAO_CONCORRENTE_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/api/roteador.py",
        "backend/app/models/entrega.py", "backend/app/services/entrega.py",
        "backend/app/schemas/entrega.py", "backend/app/api/rotas/entregas.py",
        "backend/app/models/etapa_producao.py", "backend/app/services/portal_producao.py",
        "backend/app/schemas/portal_producao.py", "backend/app/api/rotas/portal_producao.py",
        "backend/app/services/portal_ordens_servico.py", "backend/app/services/portal_contratacoes.py",
        "frontend/src/App.tsx", "frontend/package.json", "frontend/src/auth/AuthContext.tsx",
        "frontend/src/services/api.ts", "frontend/src/pages/producao/PortalProducaoPage.tsx",
        "frontend/src/pages/producao/producaoPortal.ts", "frontend/src/pages/ordens/ordensPortal.ts",
        "frontend/src/pages/contratacoes/contratacoesPortal.ts", "frontend/src/pages/client/cotacoesCliente.ts",
        "tests/test_entregas.py", "tests/test_portal_producao.py",
    )
    ausentes = [nome for nome in obrigatorios if not (raiz / nome).is_file()]
    if ausentes:
        raise RuntimeError("Execute na raiz do MEC-Servicos com D11 e D27 instalados. Arquivos ausentes: " + ", ".join(ausentes))
    return raiz


def validar_fontes_existentes(originais: dict[Path, bytes | None]) -> None:
    for nome, fonte in FONTES.items():
        if nome.endswith(".py"):
            ast.parse(fonte, filename=nome)
        anterior = originais[Path(nome)]
        if anterior is not None:
            texto = anterior.decode("utf-8-sig").replace("\r\n", "\n").rstrip()
            if texto != fonte.replace("\r\n", "\n").rstrip():
                raise RuntimeError("Já existe um arquivo diferente no destino D28. Ele foi preservado: " + nome)


def atualizar_roteador(texto: str) -> str:
    arvore = ast.parse(texto)
    modulo = "backend.app.api.rotas.portal_entregas"
    alias = "roteador_portal_entregas"
    importacoes = [n for n in arvore.body if isinstance(n, ast.ImportFrom) and n.module == modulo]
    for n in importacoes:
        if len(n.names) != 1 or n.names[0].name != "roteador" or n.names[0].asname != alias:
            raise RuntimeError("O import do portal de entregas já usa outro formato. O roteador foi preservado.")
    if len(importacoes) > 1:
        raise RuntimeError("Há imports duplicados do portal de entregas.")
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "roteador_api" and n.func.attr == "include_router"
                and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == alias]
    if len(chamadas) > 1 or any(n.keywords or len(n.args) != 1 for n in chamadas):
        raise RuntimeError("O registro do portal de entregas já usa outro formato.")
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
        candidatas = [item for item in rotas if grupo["fim_abertura"] <= item["inicio"] < item["fim"] <= grupo["fim"] and item["path"] == "entregas"]
        if len(candidatas) != 1 or not candidatas[0]["auto_fecha"]:
            raise RuntimeError("Não encontrei uma única rota de entregas no portal " + perfil + ".")
        rota = candidatas[0]
        abertura = texto[rota["inicio"]:rota["fim"]]
        componentes = list(re.finditer(r"<(?:ModulePage|PortalEntregasPage)\b", abertura))
        if len(componentes) != 1:
            raise RuntimeError("A rota de entregas do " + perfil + " usa outra tela. Ela foi preservada.")
        inicio = rota["inicio"] + componentes[0].start()
        fim = fim_tag(texto, inicio)
        if not texto[inicio:fim].rstrip().endswith("/>"):
            raise RuntimeError("O componente de entregas do " + perfil + " possui filhos. Ele foi preservado.")
        novo = f'<PortalEntregasPage perfil="{perfil}" />'
        if texto[inicio:fim] != novo:
            trocas.append((inicio, fim, novo))
    atualizado = texto
    for inicio, fim, novo in sorted(trocas, reverse=True):
        atualizado = atualizado[:inicio] + novo + atualizado[fim:]
    existente = re.search(r'''import\s+PortalEntregasPage\s+from\s*["']\./pages/entregas/PortalEntregasPage["']\s*;?''', atualizado)
    if not existente:
        if "./pages/entregas/PortalEntregasPage" in atualizado:
            raise RuntimeError("O import de entregas usa outro formato. Nenhum fonte foi alterado.")
        quebra = "\r\n" if "\r\n" in atualizado else "\n"
        atualizado = IMPORT_LINE + quebra + atualizado
    return atualizado

VALIDACAO_CONTRATO = r'''
from backend.app.principal import app
from backend.app.models.entrega import EntregaServico
from backend.app.services.entrega import ServicoEntrega
from backend.app.api.rotas.entregas import registrar_entrega, aceitar_entrega, recusar_entrega
from backend.app.schemas.etapa_producao import ETAPAS_PRODUCAO
from backend.app.services.portal_producao import ServicoPortalProducao

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
        raise RuntimeError("Campos ausentes no contrato de entrega: " + ", ".join(sorted(ausentes)))

nomes = ("id", "ordem_servico_id", "empresa_cliente_id", "empresa_fornecedora_id", "status", "observacoes",
         "motivo_recusa", "criada_em", "entregue_em", "aceita_em", "recusada_em")
for nome in nomes:
    if not hasattr(EntregaServico, nome):
        raise RuntimeError("Modelo de entrega sem o campo " + nome)
for nome in ("registrar", "aceitar", "recusar", "listar"):
    if not callable(getattr(ServicoEntrega, nome, None)):
        raise RuntimeError("Serviço de entrega sem a operação " + nome)
if "pronto_para_envio" not in ETAPAS_PRODUCAO:
    raise RuntimeError("A etapa Pronto para envio está ausente do contrato de produção.")
base = "/api/v1/ordens-servico/{ordem_servico_id}/entregas"
for metodo, sufixo, codigo in (("get", "", "200"), ("post", "", "201"),
                              ("post", "/{entrega_id}/aceitar", "200"), ("post", "/{entrega_id}/recusar", "200")):
    op = paths.get(base + sufixo, {}).get(metodo)
    if not op:
        raise RuntimeError("Rota de entrega D11 ausente: " + metodo + " " + base + sufixo)
    retorno = schema(op["responses"][codigo]["content"]["application/json"]["schema"])
    campos(schema(retorno["items"]) if metodo == "get" else retorno, nomes)
    if metodo == "post":
        corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
        empresa = "empresa_cliente_id" if sufixo else "empresa_fornecedora_id"
        campos(corpo, (empresa, "motivo" if sufixo else "observacoes"))
        if set(corpo.get("required", [])) != {empresa}:
            raise RuntimeError("Corpo da operação de entrega difere do contrato D11.")
for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    op = paths.get("/api/v1/portal-" + perfil + "/producao/{ordem_id}", {}).get("get")
    if not op or not any(p["name"] == empresa and p.get("required") for p in op.get("parameters", [])):
        raise RuntimeError("O portal de produção D27 não está instalado para " + perfil)
    campos(op["responses"]["200"]["content"]["application/json"]["schema"], ("ordem", "ultima_etapa_id", "historico"))
for nome in ("_consulta", "_ordem"):
    if not callable(getattr(ServicoPortalProducao, nome, None)):
        raise RuntimeError("O resumo de produção D27 não contém " + nome)
print("CONTRATO_ENTREGA_ACEITE_D11_OK=True")
print("PRONTO_PARA_ENVIO_E_PORTAIS_D27_OK=True")
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
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d28_", delete=False) as arquivo:
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
        "MEC-Serviços D28 — Entregas e Aceite nos Portais do Cliente e Fornecedor",
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
    print("MEC-Serviços D28 — Entregas e Aceite nos Portais do Cliente e Fornecedor", flush=True)
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
        backup = raiz / "_mec_backups" / ("D28_PORTAIS_ENTREGAS_ACEITE_" + carimbo)
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
        print("ENTREGAS_TELAS_ROTAS_E_BACKEND_OK=True", flush=True)
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
    print("Reinicie o backend e atualize /cliente/entregas e /fornecedor/entregas com Ctrl+F5.", flush=True)
    print("Use uma OS em execução do mesmo fornecedor; registre Pronto para envio na página Produção.", flush=True)
    print("Como fornecedor, revise e confirme o registro da entrega em /fornecedor/entregas.", flush=True)
    print("Como cliente, confira a entrega e revise o aceite ou a recusa com motivo em /cliente/entregas.", flush=True)
    print("O aceite conclui a OS e encerra a contratação. A recusa permite outra entrega após a correção.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
