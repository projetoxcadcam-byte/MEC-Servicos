r"""MEC-Serviços D26 — Ordens de Serviço nos portais.

Na raiz do MEC-Servicos, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D26_PORTAIS_ORDENS_SERVICO.py

Requer D9 e D25. O cliente gera uma ordem da contratação ativa;
o fornecedor responsável inicia e conclui a execução. Inclui consulta
com paginação, datas e download dos arquivos técnicos nos dois portais.
Não altera o cadastro, os serviços D9/D25 nem cria dados de demonstração.
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

REVISION = "MEC-SERVICOS-V0.1-D26-PORTAIS-ORDENS-SERVICO-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D26_PORTAIS_ORDENS_SERVICO_RELATORIO"
APP_REL = Path("frontend/src/App.tsx")
ROUTER_REL = Path("backend/app/api/roteador.py")
DIST_REL = Path("frontend/dist")
FONTES = {
  "backend/app/api/rotas/portal_ordens_servico.py": "from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, HTTPException, Path, Query, status\nfrom fastapi.responses import FileResponse\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.api.rotas.ordens_servico import criar_ordem_servico\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta\nfrom backend.app.schemas.ordem_servico import OrdemServicoCriacao, OrdemServicoLeitura\nfrom backend.app.schemas.portal_ordens_servico import (\n    ContratacoesParaOrdemPagina, OrdemFornecedorAcao, OrdemPortalLeitura, OrdensPortalPagina,\n)\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\nfrom backend.app.services.portal_contratacoes import Perfil, ServicoPortalContratacoes\nfrom backend.app.services.portal_ordens_servico import ServicoPortalOrdens\n\nroteador = APIRouter(tags=[\"ordens de serviço dos portais\"])\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\nEmpresaId = Annotated[int, Query(gt=0)]\nRecursoId = Annotated[int, Path(gt=0)]\nDeslocamento = Annotated[int, Query(ge=0)]\nLimite = Annotated[int, Query(ge=1, le=100)]\n\n\n@roteador.get(\"/portal-cliente/contratacoes-para-ordem\", response_model=ContratacoesParaOrdemPagina)\ndef contratacoes_para_ordem(banco: SessaoBanco, empresa_cliente_id: EmpresaId,\n                           deslocamento: Deslocamento = 0, limite: Limite = 20) -> ContratacoesParaOrdemPagina:\n    return ServicoPortalOrdens(banco).contratacoes_para_gerar(empresa_cliente_id, deslocamento, limite)\n\n\n@roteador.post(\"/portal-cliente/contratacoes/{contratacao_id}/ordem-servico\",\n               response_model=OrdemServicoLeitura, status_code=status.HTTP_201_CREATED)\ndef gerar_ordem(contratacao_id: RecursoId, dados: OrdemServicoCriacao, banco: SessaoBanco) -> OrdemServicoLeitura:\n    ServicoPortalContratacoes(banco).validar_empresa(dados.empresa_cliente_id, \"cliente\")\n    return criar_ordem_servico(contratacao_id, dados, banco)\n\n\n@roteador.get(\"/portal-cliente/ordens-servico\", response_model=OrdensPortalPagina)\ndef listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,\n                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> OrdensPortalPagina:\n    return ServicoPortalOrdens(banco).listar(empresa_cliente_id, \"cliente\", deslocamento, limite)\n\n\n@roteador.get(\"/portal-fornecedor/ordens-servico\", response_model=OrdensPortalPagina)\ndef listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,\n                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> OrdensPortalPagina:\n    return ServicoPortalOrdens(banco).listar(empresa_fornecedora_id, \"fornecedor\", deslocamento, limite)\n\n\n@roteador.get(\"/portal-cliente/ordens-servico/{ordem_id}\", response_model=OrdemPortalLeitura)\ndef obter_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> OrdemPortalLeitura:\n    return ServicoPortalOrdens(banco).obter(ordem_id, empresa_cliente_id, \"cliente\")\n\n\n@roteador.get(\"/portal-fornecedor/ordens-servico/{ordem_id}\", response_model=OrdemPortalLeitura)\ndef obter_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> OrdemPortalLeitura:\n    return ServicoPortalOrdens(banco).obter(ordem_id, empresa_fornecedora_id, \"fornecedor\")\n\n\n@roteador.post(\"/portal-fornecedor/ordens-servico/{ordem_id}/iniciar\", response_model=OrdemPortalLeitura)\ndef iniciar(ordem_id: RecursoId, dados: OrdemFornecedorAcao, banco: SessaoBanco) -> OrdemPortalLeitura:\n    return ServicoPortalOrdens(banco).executar(ordem_id, dados.empresa_fornecedora_id, \"iniciar\")\n\n\n@roteador.post(\"/portal-fornecedor/ordens-servico/{ordem_id}/concluir\", response_model=OrdemPortalLeitura)\ndef concluir(ordem_id: RecursoId, dados: OrdemFornecedorAcao, banco: SessaoBanco) -> OrdemPortalLeitura:\n    return ServicoPortalOrdens(banco).executar(ordem_id, dados.empresa_fornecedora_id, \"concluir\")\n\n\ndef _arquivos(ordem_id: int, banco: Session, empresa: int, perfil: Perfil) -> list[ArquivoTecnicoResposta]:\n    ordem = ServicoPortalOrdens(banco).obter(ordem_id, empresa, perfil)\n    return [ArquivoTecnicoResposta.model_validate(item) for item in ServicoArquivoTecnico(banco).listar(ordem.solicitacao_id)]\n\n\ndef _download(ordem_id: int, arquivo_id: int, banco: Session, empresa: int, perfil: Perfil) -> FileResponse:\n    ordem = ServicoPortalOrdens(banco).obter(ordem_id, empresa, perfil)\n    servico = ServicoArquivoTecnico(banco)\n    arquivo = servico.obter(arquivo_id)\n    if arquivo.solicitacao_id != ordem.solicitacao_id:\n        raise HTTPException(404, detail=\"arquivo_tecnico_nao_encontrado\")\n    return FileResponse(servico.caminho_seguro(arquivo), media_type=arquivo.content_type or \"application/octet-stream\",\n                        filename=arquivo.nome_original)\n\n\n@roteador.get(\"/portal-cliente/ordens-servico/{ordem_id}/arquivos\", response_model=list[ArquivoTecnicoResposta])\ndef arquivos_cliente(ordem_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> list[ArquivoTecnicoResposta]:\n    return _arquivos(ordem_id, banco, empresa_cliente_id, \"cliente\")\n\n\n@roteador.get(\"/portal-fornecedor/ordens-servico/{ordem_id}/arquivos\", response_model=list[ArquivoTecnicoResposta])\ndef arquivos_fornecedor(ordem_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> list[ArquivoTecnicoResposta]:\n    return _arquivos(ordem_id, banco, empresa_fornecedora_id, \"fornecedor\")\n\n\n@roteador.get(\"/portal-cliente/ordens-servico/{ordem_id}/arquivos/{arquivo_id}/download\")\ndef baixar_cliente(ordem_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> FileResponse:\n    return _download(ordem_id, arquivo_id, banco, empresa_cliente_id, \"cliente\")\n\n\n@roteador.get(\"/portal-fornecedor/ordens-servico/{ordem_id}/arquivos/{arquivo_id}/download\")\ndef baixar_fornecedor(ordem_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> FileResponse:\n    return _download(ordem_id, arquivo_id, banco, empresa_fornecedora_id, \"fornecedor\")\n",
  "backend/app/schemas/portal_ordens_servico.py": "from __future__ import annotations\n\nfrom pydantic import BaseModel, ConfigDict, Field\n\nfrom backend.app.schemas.ordem_servico import OrdemServicoLeitura\nfrom backend.app.schemas.portal_contratacoes import ContratacaoPortalLeitura, SolicitacaoContratacaoLeitura\n\n\nclass OrdemPortalLeitura(OrdemServicoLeitura):\n    cliente_razao_social: str\n    fornecedor_razao_social: str\n    processo_nome: str\n    material_nome: str\n    contratacao_status: str\n    solicitacao: SolicitacaoContratacaoLeitura\n\n\nclass OrdensPortalPagina(BaseModel):\n    itens: list[OrdemPortalLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n\n\nclass ContratacoesParaOrdemPagina(BaseModel):\n    itens: list[ContratacaoPortalLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n\n\nclass OrdemFornecedorAcao(BaseModel):\n    model_config = ConfigDict(extra=\"forbid\")\n    empresa_fornecedora_id: int = Field(gt=0)\n",
  "backend/app/services/portal_ordens_servico.py": "from __future__ import annotations\n\nfrom datetime import datetime, timezone\nfrom typing import Literal\n\nfrom fastapi import HTTPException\nfrom sqlalchemy import func, select, update\nfrom sqlalchemy.orm import Session, aliased\n\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.schemas.ordem_servico import OrdemServicoLeitura\nfrom backend.app.schemas.portal_ordens_servico import (\n    ContratacoesParaOrdemPagina, OrdemPortalLeitura, OrdensPortalPagina,\n)\nfrom backend.app.services.portal_contratacoes import Perfil, ServicoPortalContratacoes\n\n\nclass ServicoPortalOrdens:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n        self.contratos = ServicoPortalContratacoes(banco)\n\n    @staticmethod\n    def _dono(empresa_id: int, perfil: Perfil):\n        coluna = OrdemServico.empresa_cliente_id if perfil == \"cliente\" else OrdemServico.empresa_fornecedora_id\n        return coluna == empresa_id\n\n    @staticmethod\n    def _consulta():\n        cliente, fornecedor = aliased(Empresa), aliased(Empresa)\n        processo_pedido, material_pedido = aliased(ProcessoFabricacao), aliased(Material)\n        return (\n            select(OrdemServico, ContratacaoServico.status, SolicitacaoServico,\n                   cliente.razao_social, fornecedor.razao_social, ProcessoFabricacao.nome, Material.nome,\n                   processo_pedido.nome, material_pedido.nome)\n            .join(ContratacaoServico, ContratacaoServico.id == OrdemServico.contratacao_id)\n            .join(SolicitacaoServico, SolicitacaoServico.id == OrdemServico.solicitacao_id)\n            .join(cliente, cliente.id == OrdemServico.empresa_cliente_id)\n            .join(fornecedor, fornecedor.id == OrdemServico.empresa_fornecedora_id)\n            .join(ProcessoFabricacao, ProcessoFabricacao.id == OrdemServico.processo_id)\n            .join(Material, Material.id == OrdemServico.material_id)\n            .join(processo_pedido, processo_pedido.id == SolicitacaoServico.processo_id)\n            .join(material_pedido, material_pedido.id == SolicitacaoServico.material_id)\n        )\n\n    @staticmethod\n    def _ordem(linha) -> OrdemPortalLeitura:\n        ordem, contrato_status, solicitacao, cliente, fornecedor, processo, material, processo_pedido, material_pedido = linha\n        return OrdemPortalLeitura(\n            **OrdemServicoLeitura.model_validate(ordem).model_dump(),\n            cliente_razao_social=cliente, fornecedor_razao_social=fornecedor,\n            processo_nome=processo, material_nome=material, contratacao_status=contrato_status,\n            solicitacao=ServicoPortalContratacoes._solicitacao(solicitacao, cliente, processo_pedido, material_pedido),\n        )\n\n    def listar(self, empresa_id: int, perfil: Perfil, deslocamento: int, limite: int) -> OrdensPortalPagina:\n        self.contratos.validar_empresa(empresa_id, perfil)\n        consulta = self._consulta().where(self._dono(empresa_id, perfil))\n        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0\n        linhas = self.banco.execute(consulta.order_by(OrdemServico.id.desc()).offset(deslocamento).limit(limite)).all()\n        return OrdensPortalPagina(itens=[self._ordem(linha) for linha in linhas], total=total,\n                                 deslocamento=deslocamento, limite=limite)\n\n    def obter(self, ordem_id: int, empresa_id: int, perfil: Perfil) -> OrdemPortalLeitura:\n        self.contratos.validar_empresa(empresa_id, perfil)\n        linha = self.banco.execute(self._consulta().where(\n            OrdemServico.id == ordem_id, self._dono(empresa_id, perfil),\n        )).first()\n        if linha is None:\n            raise HTTPException(404, detail=\"ordem_servico_nao_encontrada\")\n        return self._ordem(linha)\n\n    def contratacoes_para_gerar(self, empresa_id: int, deslocamento: int, limite: int) -> ContratacoesParaOrdemPagina:\n        self.contratos.validar_empresa(empresa_id, \"cliente\")\n        existe = select(OrdemServico.id).where(\n            OrdemServico.contratacao_id == ContratacaoServico.id,\n        ).correlate(ContratacaoServico).exists()\n        consulta = self.contratos._consulta_contratacoes().where(\n            ContratacaoServico.empresa_cliente_id == empresa_id, ContratacaoServico.status == \"ativa\", ~existe,\n        )\n        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0\n        linhas = self.banco.execute(consulta.order_by(ContratacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()\n        return ContratacoesParaOrdemPagina(itens=[self.contratos._contratacao(linha) for linha in linhas],\n                                          total=total, deslocamento=deslocamento, limite=limite)\n\n    def executar(self, ordem_id: int, empresa_id: int, acao: Literal[\"iniciar\", \"concluir\"]) -> OrdemPortalLeitura:\n        ordem = self.obter(ordem_id, empresa_id, \"fornecedor\")\n        if ordem.contratacao_status != \"ativa\":\n            raise HTTPException(409, detail=\"contratacao_nao_esta_ativa\")\n        antes, depois, campo, erro = (\n            (\"aberta\", \"em_execucao\", \"iniciada_em\", \"ordem_servico_nao_pode_ser_iniciada\") if acao == \"iniciar\"\n            else (\"em_execucao\", \"concluida\", \"concluida_em\", \"ordem_servico_nao_pode_ser_concluida\")\n        )\n        if ordem.status != antes:\n            raise HTTPException(409, detail=erro)\n        contrato_ativo = select(ContratacaoServico.id).where(\n            ContratacaoServico.id == OrdemServico.contratacao_id,\n            ContratacaoServico.status == \"ativa\",\n            ContratacaoServico.empresa_fornecedora_id == empresa_id,\n        ).correlate(OrdemServico).exists()\n        resultado = self.banco.execute(update(OrdemServico).where(\n            OrdemServico.id == ordem_id, OrdemServico.empresa_fornecedora_id == empresa_id,\n            OrdemServico.status == antes, contrato_ativo,\n        ).values(**{ \"status\": depois, campo: datetime.now(timezone.utc).replace(tzinfo=None) }),\n            execution_options={\"synchronize_session\": False})\n        if resultado.rowcount != 1:\n            self.banco.rollback()\n            raise HTTPException(409, detail=\"ordem_servico_alterada_atualize\")\n        self.banco.commit()\n        self.banco.expire_all()\n        return self.obter(ordem_id, empresa_id, \"fornecedor\")\n",
  "frontend/src/pages/ordens/PortalOrdensServicoPage.css": ".o26-page { color: #dce7f7; display: flex; flex-direction: column; gap: 22px; width: 100%; }\n.o26-page * { box-sizing: border-box; }\n.o26-page h1, .o26-page h2, .o26-page h3, .o26-page p { margin: 0; }\n.o26-page h1 { color: #edf3fc; font-size: clamp(28px, 3vw, 40px); line-height: 1.25; margin: 10px 0 12px; }\n.o26-page h2 { font-size: 19px; color: #e9f0fc; }\n.o26-page h3 { color: #c6d8ef; font-size: 14px; margin: 22px 0 10px; }\n.o26-page p { color: #91a8c8; line-height: 1.6; }\n.o26-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }\n.o26-page .o26-eyebrow { display: flex; align-items: center; gap: 9px; color: #6ba6ff; font-size: 12px; font-weight: 800; letter-spacing: .09em; }\n.o26-button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 11px 15px; background: #162333; border: 1px solid #31465f; border-radius: 8px; color: #dce9fc; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; text-decoration: none; line-height: 1.4; }\n.o26-button:hover:enabled, a.o26-button:hover { background: #213754; border-color: #6592cc; }\n.o26-button:focus-visible, .o26-form textarea:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.o26-button:disabled { opacity: .45; cursor: default; }\n.o26-primary { background: #2563eb; border-color: #357bf5; color: #fff; }\n.o26-primary:hover:enabled { background: #3475fb; }\n.o26-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }\n.o26-summary article { display: flex; flex-direction: column; gap: 12px; padding: 23px; background: linear-gradient(145deg, #162235, #101b2b); border: 1px solid #2b3c53; border-radius: 13px; }\n.o26-summary span { color: #a6c0e2; font-size: 13px; }\n.o26-summary strong { font-size: 31px; color: #f2f6fe; }\n.o26-summary small { color: #7794ba; line-height: 1.5; }\n.o26-tabs { display: flex; flex-wrap: wrap; gap: 9px; }\n.o26-tab-active { background: #193658; border-color: #4976b0; }\n.o26-panel { background: #111c2a; border: 1px solid #293d56; border-radius: 13px; overflow: hidden; }\n.o26-section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 23px; }\n.o26-section-head p { font-size: 13px; margin-top: 10px; }\n.o26-section-head > svg { color: #79aef5; flex-shrink: 0; }\n.o26-table-wrap { overflow-x: auto; }\n.o26-page table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; }\n.o26-page th { color: #819fc5; background: #0e1825; padding: 17px 20px; font-weight: 700; white-space: nowrap; }\n.o26-page td { padding: 19px 20px; border-top: 1px solid #26384e; color: #d5e4f7; overflow-wrap: anywhere; }\n.o26-page td strong { color: #e8f1ff; font-size: 13px; }\n.o26-page td small { display: block; color: #7899c2; margin-top: 9px; font-size: 11px; line-height: 1.5; }\n.o26-page .o26-selected { background: #192d46; }\n.o26-nowrap { white-space: nowrap; }\n.o26-badge { display: inline-block; padding: 7px 10px; border-radius: 18px; background: #223245; font-size: 11px; font-weight: 800; white-space: nowrap; }\n.o26-status-ativa, .o26-status-concluida { background: #173d31; color: #80deae; }\n.o26-status-cancelada { background: #42303b; color: #e4a1b9; }\n.o26-status-em_execucao { background: #203956; color: #99c6ff; }\n.o26-empty { min-height: 235px; padding: 45px 24px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 15px; text-align: center; }\n.o26-empty svg { color: #669dea; }\n.o26-empty h3 { font-size: 18px; margin: 0; color: #d9e9ff; }\n.o26-empty p { max-width: 680px; font-size: 13px; }\n.o26-pagination { padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; gap: 14px; border-top: 1px solid #293d56; color: #8fa9cb; font-size: 12px; }\n.o26-pagination > div { display: flex; gap: 9px; }\n.o26-columns { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 22px; align-items: start; }\n.o26-detail { padding: 23px; }\n.o26-detail .o26-section-head, .o26-dialog .o26-section-head { padding: 0; margin-bottom: 22px; }\n.o26-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }\n.o26-fields > div { border: 1px solid #2b3e56; background: #0d1724; border-radius: 9px; padding: 15px; min-width: 0; }\n.o26-fields dt { color: #819fc4; font-size: 11px; margin-bottom: 10px; }\n.o26-fields dd { color: #e2ecfa; font-size: 13px; font-weight: 700; margin: 0; line-height: 1.6; overflow-wrap: anywhere; }\n.o26-fields .o26-value { font-size: 19px; }\n.o26-wide { grid-column: 1 / -1; }\n.o26-page .o26-observacoes { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; margin-bottom: 20px; }\n.o26-form { margin-top: 22px; }\n.o26-form fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }\n.o26-form label { display: block; color: #b2c9e7; font-size: 12px; font-weight: 700; margin-bottom: 10px; }\n.o26-form textarea { display: block; width: 100%; border: 1px solid #37506e; border-radius: 9px; background: #0b1523; color: #e6f0ff; padding: 13px; font: inherit; font-size: 13px; resize: vertical; line-height: 1.7; }\n.o26-form p { font-size: 12px; margin: 14px 0; }\n.o26-form button[type=\"submit\"] { width: 100%; margin-top: 8px; }\n.o26-page .o26-alert { display: flex; align-items: flex-start; gap: 11px; padding: 15px 18px; border-radius: 9px; font-size: 13px; }\n.o26-alert svg { flex-shrink: 0; }\n.o26-page .o26-success { color: #a1e8c4; background: #143028; border: 1px solid #276148; }\n.o26-page .o26-error { color: #ffbdc6; background: #37212a; border: 1px solid #703c4c; }\n.o26-files-head { margin-top: 28px; }\n.o26-files-head h3 { margin: 0; }\n.o26-files { padding: 0; margin: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }\n.o26-files li { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 9px; border: 1px solid #30445f; background: #0d1724; }\n.o26-files li > svg { color: #79aef5; flex-shrink: 0; }\n.o26-files li > span { flex: 1; min-width: 0; }\n.o26-files strong { font-size: 12px; overflow-wrap: anywhere; }\n.o26-files small { color: #7695bd; font-size: 11px; display: block; margin-top: 6px; }\n.o26-dialog { color: #e4edfa; background: #111e30; border: 1px solid #466891; border-radius: 14px; padding: 26px; width: min(600px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto; box-shadow: 0 24px 90px #0009; }\n.o26-dialog::backdrop { background: #020814c9; }\n.o26-dialog p { font-size: 13px; margin-bottom: 20px; }\n.o26-dialog h3 { margin-top: 20px; }\n.o26-dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 24px; }\n.o26-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }\n@media (max-width: 1100px) { .o26-columns { grid-template-columns: minmax(0, 1fr); } }\n@media (max-width: 650px) { .o26-header { flex-direction: column; } .o26-summary { grid-template-columns: minmax(0, 1fr); } .o26-tabs { flex-direction: column; } .o26-detail, .o26-section-head { padding: 18px; } .o26-pagination { flex-wrap: wrap; } .o26-fields { grid-template-columns: minmax(0, 1fr); } .o26-files li { flex-wrap: wrap; } .o26-files li .o26-button { width: 100%; } .o26-dialog { padding: 20px; } }\n.o26-status-aberta { background: #4a3c20; color: #f0cd83; }\n.o26-operacao { display: flex; flex-direction: column; gap: 16px; margin-top: 24px; }\n.o26-operacao p { font-size: 13px; }\n.o26-dialog .o26-review-note { margin-top: 20px; }\n",
  "frontend/src/pages/ordens/PortalOrdensServicoPage.tsx": "import { useEffect, useRef, useState } from \"react\";\nimport { Link } from \"react-router-dom\";\nimport { CheckCircle2, ClipboardList, Download, FileText, Handshake, Play, RefreshCw, Wrench, X } from \"lucide-react\";\nimport { useAuth } from \"../../auth/AuthContext\";\nimport { api } from \"../../services/api\";\nimport { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from \"../client/cotacoesCliente\";\nimport { formatarMedidaContrato, rotuloContratacao, type ContratacaoPortal, type PaginaContratacoes } from \"../contratacoes/contratacoesPortal\";\nimport { formatarTamanhoArquivo, type ArquivoFornecedor } from \"../supplier/cotacoesFornecedor\";\nimport { mensagemErroOrdem, rotuloOrdem, type AcaoOrdem, type OrdemPortal, type OrdemResposta, type PerfilOrdens } from \"./ordensPortal\";\nimport \"./PortalOrdensServicoPage.css\";\n\ntype Visao = \"ordens\" | \"contratos\";\ntype Grupo = { chave: string; ordens: PaginaContratacoes<OrdemPortal>; contratos: PaginaContratacoes<ContratacaoPortal> };\ntype Revisao = { chave: string; dono: string } & (\n  { acao: \"gerar\"; contrato: ContratacaoPortal } | { acao: \"iniciar\" | \"concluir\"; ordem: OrdemPortal }\n);\nconst LIMITE = 20;\nconst PAGINA_VAZIA = { itens: [], total: 0, deslocamento: 0, limite: LIMITE };\nconst TITULOS: Record<AcaoOrdem, string> = { gerar: \"Gerar ordem de serviço\", iniciar: \"Confirmar início\", concluir: \"Confirmar conclusão\" };\n\nexport default function PortalOrdensServicoPage({ perfil }: { perfil: PerfilOrdens }) {\n  const { user } = useAuth();\n  const empresaId = user?.role === perfil ? user.id : 0;\n  const base = `/portal-${perfil}`;\n  const dono = `${perfil}:${empresaId}`;\n  const [visao, setVisao] = useState<Visao>(\"ordens\");\n  const visaoAtual = perfil === \"cliente\" ? visao : \"ordens\";\n  const [deslocamento, setDeslocamento] = useState(0);\n  const [atualizacao, setAtualizacao] = useState(0);\n  const [grupo, setGrupo] = useState<Grupo | null>(null);\n  const [selecionadoId, setSelecionadoId] = useState(0);\n  const [carregando, setCarregando] = useState(true);\n  const [erroLista, setErroLista] = useState(\"\");\n  const [revisao, setRevisao] = useState<Revisao | null>(null);\n  const [enviando, setEnviando] = useState(false);\n  const [avisoAcao, setAvisoAcao] = useState<{ dono: string; texto: string } | null>(null);\n  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);\n  const [revalidar, setRevalidar] = useState<{ dono: string; atualizacao: number } | null>(null);\n  const [arquivos, setArquivos] = useState<{ chave: string; itens: ArquivoFornecedor[] } | null>(null);\n  const [erroArquivos, setErroArquivos] = useState(\"\");\n  const [carregandoArquivos, setCarregandoArquivos] = useState(false);\n  const [atualizacaoArquivos, setAtualizacaoArquivos] = useState(0);\n  const [baixando, setBaixando] = useState<number | null>(null);\n  const paginaChave = `${dono}:${visaoAtual}:${deslocamento}:${atualizacao}`;\n  const grupoAtual = grupo?.chave === paginaChave ? grupo : null;\n  const ordens = grupoAtual?.ordens.itens ?? [];\n  const contratos = grupoAtual?.contratos.itens ?? [];\n  const ordem = visaoAtual === \"ordens\" ? ordens.find((item) => item.id === selecionadoId) ?? ordens[0] : undefined;\n  const contrato = visaoAtual === \"contratos\" ? contratos.find((item) => item.id === selecionadoId) ?? contratos[0] : undefined;\n  const item = ordem ?? contrato;\n  const selecaoChave = `${dono}:${visaoAtual}:${item?.id ?? 0}`;\n  const arquivosChave = `${paginaChave}:${selecaoChave}:${atualizacaoArquivos}`;\n  const precisaAtualizar = revalidar?.dono === dono && revalidar.atualizacao === atualizacao;\n  const bloquear = carregando || enviando || !grupoAtual || precisaAtualizar;\n  const modalAtual = revisao?.chave === selecaoChave && revisao.dono === dono && grupoAtual && !precisaAtualizar ? revisao : null;\n  const arquivosAtuais = arquivos?.chave === arquivosChave ? arquivos.itens : [];\n  const parametrosEmpresa = perfil === \"cliente\" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };\n  const contexto = useRef({ paginaChave, selecaoChave, arquivosChave, dono });\n  contexto.current = { paginaChave, selecaoChave, arquivosChave, dono };\n  const montada = useRef(true);\n  const dialogo = useRef<HTMLDialogElement | null>(null);\n  const trava = useRef(false);\n  const envio = useRef<AbortController | null>(null);\n  const download = useRef<AbortController | null>(null);\n\n  useEffect(() => {\n    montada.current = true;\n    return () => { montada.current = false; envio.current?.abort(); download.current?.abort(); };\n  }, []);\n\n  useEffect(() => {\n    setVisao(\"ordens\"); setDeslocamento(0); setSelecionadoId(0); setRevisao(null);\n    envio.current?.abort(); download.current?.abort();\n  }, [empresaId, perfil]);\n\n  useEffect(() => {\n    const controlador = new AbortController();\n    let vigente = true;\n    setCarregando(true); setErroLista(\"\"); setRevisao(null);\n    if (!empresaId) {\n      setErroLista(`Entre como ${perfil} para consultar suas ordens de serviço.`); setCarregando(false);\n      return () => { vigente = false; controlador.abort(); };\n    }\n    async function carregar() {\n      try {\n        const config = { params: { ...parametrosEmpresa, deslocamento: visaoAtual === \"ordens\" ? deslocamento : 0, limite: LIMITE }, signal: controlador.signal, timeout: 20_000 };\n        const [resposta, candidatas] = await Promise.all([\n          api.get<PaginaContratacoes<OrdemPortal>>(`${base}/ordens-servico`, config),\n          perfil === \"cliente\" ? api.get<PaginaContratacoes<ContratacaoPortal>>(\"/portal-cliente/contratacoes-para-ordem\", {\n            ...config, params: { empresa_cliente_id: empresaId, deslocamento: visaoAtual === \"contratos\" ? deslocamento : 0, limite: LIMITE },\n          }) : Promise.resolve({ data: PAGINA_VAZIA as PaginaContratacoes<ContratacaoPortal> }),\n        ]);\n        if (!vigente || contexto.current.paginaChave !== paginaChave) return;\n        const total = visaoAtual === \"contratos\" ? candidatas.data.total : resposta.data.total;\n        if (total > 0 && deslocamento >= total) { setDeslocamento(Math.floor((total - 1) / LIMITE) * LIMITE); return; }\n        if (total === 0 && deslocamento > 0) { setDeslocamento(0); return; }\n        const proprias = resposta.data.itens.filter((os) => (perfil === \"cliente\" ? os.empresa_cliente_id : os.empresa_fornecedora_id) === empresaId);\n        const aptas = candidatas.data.itens.filter((c) => c.empresa_cliente_id === empresaId && c.status === \"ativa\");\n        setGrupo({ chave: paginaChave, ordens: { ...resposta.data, itens: proprias }, contratos: { ...candidatas.data, itens: aptas } });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.paginaChave === paginaChave) setErroLista(mensagemErroOrdem(erro));\n      } finally {\n        if (vigente && contexto.current.paginaChave === paginaChave) setCarregando(false);\n      }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, empresaId, perfil, visaoAtual, deslocamento, paginaChave]);\n\n  useEffect(() => {\n    setRevisao(null); setErroArquivos(\"\"); setBaixando(null); download.current?.abort();\n  }, [selecaoChave]);\n\n  useEffect(() => {\n    const controlador = new AbortController();\n    let vigente = true;\n    setErroArquivos(\"\"); setCarregandoArquivos(Boolean(ordem));\n    if (!ordem) return () => { vigente = false; controlador.abort(); };\n    async function carregarArquivos() {\n      try {\n        const { data } = await api.get<ArquivoFornecedor[]>(`${base}/ordens-servico/${ordem!.id}/arquivos`, {\n          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,\n        });\n        if (vigente && contexto.current.arquivosChave === arquivosChave) setArquivos({ chave: arquivosChave, itens: data.filter((a) => a.ativo && a.solicitacao_id === ordem!.solicitacao_id) });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.arquivosChave === arquivosChave) setErroArquivos(mensagemErroOrdem(erro));\n      } finally {\n        if (vigente && contexto.current.arquivosChave === arquivosChave) setCarregandoArquivos(false);\n      }\n    }\n    void carregarArquivos();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, perfil, empresaId, ordem?.id, arquivosChave]);\n\n  useEffect(() => {\n    const elemento = dialogo.current;\n    if (!elemento) return;\n    if (modalAtual && !elemento.open) elemento.showModal();\n    if (!modalAtual && elemento.open) elemento.close();\n  }, [modalAtual]);\n\n  function mudarVisao(nova: Visao) {\n    if (trava.current) return;\n    setVisao(nova); setDeslocamento(0); setSelecionadoId(0); setRevisao(null);\n  }\n\n  function revisar(acao: AcaoOrdem) {\n    if (bloquear || trava.current) return;\n    setAvisoAcao(null); setSucesso(null);\n    if (acao === \"gerar\" && contrato && perfil === \"cliente\") setRevisao({ chave: selecaoChave, dono, acao, contrato });\n    if (acao !== \"gerar\" && ordem && perfil === \"fornecedor\" && ordem.contratacao_status === \"ativa\"\n        && ordem.status === (acao === \"iniciar\" ? \"aberta\" : \"em_execucao\")) setRevisao({ chave: selecaoChave, dono, acao, ordem });\n  }\n\n  async function confirmar() {\n    if (!modalAtual || bloquear || trava.current) return;\n    const confirmado = modalAtual;\n    const controlador = new AbortController();\n    envio.current = controlador; trava.current = true; setEnviando(true); setAvisoAcao(null);\n    try {\n      const url = confirmado.acao === \"gerar\" ? `/portal-cliente/contratacoes/${confirmado.contrato.id}/ordem-servico`\n        : `/portal-fornecedor/ordens-servico/${confirmado.ordem.id}/${confirmado.acao}`;\n      const dados = confirmado.acao === \"gerar\" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };\n      const { data } = await api.post<OrdemResposta>(url, dados, { signal: controlador.signal, timeout: 30_000 });\n      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== confirmado.dono || contexto.current.selecaoChave !== confirmado.chave) return;\n      const origem = confirmado.acao === \"gerar\" ? confirmado.contrato : confirmado.ordem;\n      const statusEsperado = confirmado.acao === \"gerar\" ? \"aberta\" : confirmado.acao === \"iniciar\" ? \"em_execucao\" : \"concluida\";\n      if (data.solicitacao_id !== origem.solicitacao_id || data.empresa_cliente_id !== origem.empresa_cliente_id\n          || data.empresa_fornecedora_id !== origem.empresa_fornecedora_id || data.status !== statusEsperado\n          || (confirmado.acao === \"gerar\" ? data.contratacao_id !== confirmado.contrato.id : data.id !== confirmado.ordem.id)) throw new Error(\"Resposta da ordem divergente.\");\n      setSucesso({ dono, texto: confirmado.acao === \"gerar\" ? `Ordem de serviço #${data.id} gerada para a contratação #${data.contratacao_id}. O fornecedor já pode iniciar o serviço.`\n        : confirmado.acao === \"iniciar\" ? `Ordem de serviço #${data.id} iniciada. O cliente já pode acompanhar a execução.` : `Ordem de serviço #${data.id} concluída. O cliente já pode consultar a conclusão.` });\n      setRevisao(null); setVisao(\"ordens\"); setSelecionadoId(data.id);\n      if (confirmado.acao === \"gerar\") setDeslocamento(0);\n      setAtualizacao((valor) => valor + 1);\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.dono === confirmado.dono && contexto.current.selecaoChave === confirmado.chave) {\n        const status = typeof erro === \"object\" && erro !== null && \"response\" in erro ? (erro as { response?: { status?: number } }).response?.status : undefined;\n        const incerta = !status || status >= 500;\n        setAvisoAcao({ dono, texto: incerta ? \"A operação não pôde ser confirmada. Clique em Atualizar e confira a situação da ordem antes de tentar novamente.\" : mensagemErroOrdem(erro) });\n        if (incerta) setRevalidar({ dono, atualizacao });\n        setRevisao(null);\n      }\n    } finally {\n      if (envio.current === controlador) envio.current = null;\n      trava.current = false;\n      if (montada.current) setEnviando(false);\n    }\n  }\n\n  async function baixar(arquivo: ArquivoFornecedor) {\n    if (!ordem || baixando !== null || download.current) return;\n    const controlador = new AbortController();\n    const chave = arquivosChave;\n    download.current = controlador; setBaixando(arquivo.id); setErroArquivos(\"\");\n    try {\n      const { data } = await api.get<Blob>(`${base}/ordens-servico/${ordem.id}/arquivos/${arquivo.id}/download`, {\n        params: parametrosEmpresa, signal: controlador.signal, responseType: \"blob\", timeout: 60_000,\n      });\n      if (!montada.current || controlador.signal.aborted || contexto.current.arquivosChave !== chave) return;\n      const url = URL.createObjectURL(data); const link = document.createElement(\"a\");\n      try { link.href = url; link.download = arquivo.nome_original.replace(/[\\\\/]/g, \"_\"); document.body.appendChild(link); link.click(); }\n      finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.arquivosChave === chave) setErroArquivos(mensagemErroOrdem(erro));\n    } finally {\n      if (download.current === controlador) download.current = null;\n      if (montada.current && contexto.current.arquivosChave === chave) setBaixando(null);\n    }\n  }\n\n  const pagina = visaoAtual === \"contratos\" ? grupoAtual?.contratos : grupoAtual?.ordens;\n  const linhas = visaoAtual === \"contratos\" ? contratos : ordens;\n  const total = pagina?.total ?? 0;\n  const pedido = item?.solicitacao;\n  const revisado = modalAtual ? modalAtual.acao === \"gerar\" ? modalAtual.contrato : modalAtual.ordem : null;\n  return <main className=\"o26-page\">\n    <header className=\"o26-header\"><div><p className=\"o26-eyebrow\"><Wrench size={16} /> PORTAL DO {perfil === \"cliente\" ? \"CLIENTE\" : \"FORNECEDOR\"}</p>\n      <h1>Ordens de Serviço</h1><p>{perfil === \"cliente\" ? \"Gere a ordem da contratação e acompanhe a execução do serviço.\" : \"Consulte suas ordens e registre o início e a conclusão do serviço.\"}</p></div>\n      <button className=\"o26-button\" disabled={enviando || carregando} onClick={() => { setAvisoAcao(null); setAtualizacao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>\n    {sucesso?.dono === dono && <p className=\"o26-alert o26-success\" role=\"status\"><CheckCircle2 size={18} /> {sucesso.texto}</p>}\n    {avisoAcao?.dono === dono && <p className=\"o26-alert o26-error\" role=\"alert\">{avisoAcao.texto}</p>}\n    {erroLista && <p className=\"o26-alert o26-error\" role=\"alert\">{erroLista}</p>}\n    <div className=\"o26-summary\"><article><span>Ordens da sua empresa</span><strong>{grupoAtual ? grupoAtual.ordens.total : \"—\"}</strong><small>Inclui abertas, em execução, concluídas e canceladas</small></article>\n      {perfil === \"cliente\" && <article><span>Contratações prontas para gerar ordem</span><strong>{grupoAtual ? grupoAtual.contratos.total : \"—\"}</strong><small>Ativas e ainda sem ordem de serviço</small></article>}</div>\n    <nav className=\"o26-tabs\" aria-label=\"Consultas de ordens de serviço\">\n      <button className={`o26-button ${visaoAtual === \"ordens\" ? \"o26-tab-active\" : \"\"}`} aria-pressed={visaoAtual === \"ordens\"} disabled={enviando} onClick={() => mudarVisao(\"ordens\")}><Wrench size={16} /> Ordens de Serviço</button>\n      {perfil === \"cliente\" && <button className={`o26-button ${visaoAtual === \"contratos\" ? \"o26-tab-active\" : \"\"}`} aria-pressed={visaoAtual === \"contratos\"} disabled={enviando} onClick={() => mudarVisao(\"contratos\")}><ClipboardList size={16} /> Contratações para gerar ordem</button>}\n      <Link className=\"o26-button\" to={`/${perfil}/contratacoes`}><Handshake size={16} /> Contratações</Link>\n    </nav>\n    <section className=\"o26-panel\" aria-busy={carregando}><div className=\"o26-section-head\"><div><h2>{visaoAtual === \"contratos\" ? \"Contratações disponíveis\" : \"Ordens da sua empresa\"}</h2><p>{visaoAtual === \"contratos\" ? \"Selecione a contratação e revise os dados antes de gerar a ordem.\" : \"Selecione a ordem para consultar os dados, as datas e os arquivos técnicos.\"}</p></div></div>\n      {carregando ? <div className=\"o26-empty\" role=\"status\">Carregando {visaoAtual === \"contratos\" ? \"contratações\" : \"ordens\"}…</div>\n        : !erroLista && linhas.length === 0 ? <div className=\"o26-empty\"><Wrench size={32} /><h3>{visaoAtual === \"contratos\" ? \"Nenhuma contratação pronta para gerar ordem\" : \"Nenhuma ordem de serviço cadastrada\"}</h3><p>{visaoAtual === \"contratos\" ? \"Crie uma contratação ativa. Cada contratação pode ter uma única ordem de serviço.\" : perfil === \"cliente\" ? \"Abra Contratações para gerar ordem e selecione uma contratação ativa.\" : \"A ordem aparecerá aqui quando o cliente gerá-la a partir da contratação.\"}</p></div>\n        : grupoAtual && <div className=\"o26-table-wrap\"><table><thead><tr><th>Ordem / referência</th><th>{perfil === \"cliente\" ? \"Fornecedor\" : \"Cliente\"}</th><th>Valor total</th><th>Prazo</th><th>Situação</th><th><span className=\"o26-sr-only\">Ações</span></th></tr></thead><tbody>\n          {linhas.map((linha) => { const os = \"contratacao_id\" in linha; const ativa = linha.id === item?.id;\n            return <tr key={linha.id} className={ativa ? \"o26-selected\" : \"\"}><td><strong>{os ? `OS #${linha.id}` : `Contratação #${linha.id}`}</strong><small>{`Solicitação #${linha.solicitacao_id} · ${os ? `Contratação #${linha.contratacao_id}` : `Cotação #${linha.cotacao_id}`}`}</small></td>\n              <td>{perfil === \"cliente\" ? linha.fornecedor_razao_social : linha.cliente_razao_social}<small>{os ? linha.processo_nome : linha.solicitacao.processo_nome} · {os ? linha.material_nome : linha.solicitacao.material_nome}</small></td>\n              <td className=\"o26-nowrap\"><strong>{formatarValorCotacao(linha.valor_total)}</strong></td><td className=\"o26-nowrap\">{linha.prazo_dias} dias</td>\n              <td><span className={`o26-badge o26-status-${os && [\"aberta\", \"em_execucao\", \"concluida\", \"cancelada\"].includes(linha.status) ? linha.status : \"ativa\"}`}>{os ? rotuloOrdem(linha.status) : \"Pronta para gerar\"}</span></td>\n              <td><button className=\"o26-button\" disabled={enviando} onClick={() => setSelecionadoId(linha.id)} aria-pressed={ativa}>{ativa ? \"Selecionada\" : \"Ver detalhes\"}</button></td></tr>;\n          })}</tbody></table></div>}\n      {grupoAtual && total > 0 && <div className=\"o26-pagination\"><span>{deslocamento + 1}–{Math.min(deslocamento + linhas.length, total)} de {total}</span><div>\n        <button className=\"o26-button\" disabled={enviando || carregando || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => Math.max(0, v - LIMITE)); }}>Anterior</button>\n        <button className=\"o26-button\" disabled={enviando || carregando || deslocamento + LIMITE >= total} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => v + LIMITE); }}>Próxima</button></div></div>}\n    </section>\n    {pedido && item && <div className=\"o26-columns\">\n      <section className=\"o26-panel o26-detail\"><div className=\"o26-section-head\"><h2>Solicitação #{pedido.id}</h2><ClipboardList size={21} /></div>\n        <dl className=\"o26-fields\"><div><dt>Cliente</dt><dd>{item.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{item.fornecedor_razao_social}</dd></div>\n          <div><dt>Processo {ordem ? \"da ordem\" : \"\"}</dt><dd>{ordem?.processo_nome ?? pedido.processo_nome}</dd></div><div><dt>Material {ordem ? \"da ordem\" : \"\"}</dt><dd>{ordem?.material_nome ?? pedido.material_nome}</dd></div>\n          <div><dt>Quantidade {ordem ? \"da ordem\" : \"\"}</dt><dd>{ordem?.quantidade ?? pedido.quantidade} unidades</dd></div><div><dt>Tolerância requerida</dt><dd>{formatarMedidaContrato(pedido.tolerancia_requerida_mm, 4)} mm</dd></div>\n          <div className=\"o26-wide\"><dt>Dimensões máximas X / Y / Z</dt><dd>{[pedido.dimensao_x_maxima_mm, pedido.dimensao_y_maxima_mm, pedido.dimensao_z_maxima_mm].map((v) => formatarMedidaContrato(v)).join(\" × \")} mm</dd></div></dl>\n        <h3>Observações da solicitação</h3><p className=\"o26-observacoes\">{pedido.observacoes || \"Sem observações.\"}</p>\n        {ordem && <><div className=\"o26-section-head o26-files-head\"><h3>Arquivos técnicos</h3><button className=\"o26-button\" disabled={carregandoArquivos || baixando !== null} onClick={() => setAtualizacaoArquivos((v) => v + 1)}>Atualizar arquivos</button></div>\n          {erroArquivos && <p className=\"o26-alert o26-error\" role=\"alert\">{erroArquivos}</p>}\n          {carregandoArquivos ? <p role=\"status\">Carregando arquivos…</p> : !erroArquivos && arquivosAtuais.length === 0 ? <p>Nenhum arquivo ativo vinculado a esta solicitação.</p> : <ul className=\"o26-files\">{arquivosAtuais.map((a) => <li key={a.id}><FileText size={19} /><span><strong>{a.nome_original}</strong><small>{a.extensao.toUpperCase()} · {formatarTamanhoArquivo(a.tamanho_bytes)}</small></span><button className=\"o26-button\" disabled={baixando !== null} onClick={() => void baixar(a)}><Download size={15} /> {baixando === a.id ? \"Baixando…\" : \"Baixar\"}</button></li>)}</ul>}\n        </>}\n      </section>\n      <section className=\"o26-panel o26-detail\"><div className=\"o26-section-head\"><h2>{ordem ? `Ordem de serviço #${ordem.id}` : `Gerar ordem da contratação #${contrato!.id}`}</h2><Wrench size={21} /></div>\n        <dl className=\"o26-fields\"><div><dt>Valor total</dt><dd className=\"o26-value\">{formatarValorCotacao(item.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{item.prazo_dias} dias</dd></div>\n          <div><dt>Contratação</dt><dd>#{ordem?.contratacao_id ?? contrato!.id} · {rotuloContratacao(ordem?.contratacao_status ?? contrato!.status)}</dd></div><div><dt>Cotação</dt><dd>#{item.cotacao_id}</dd></div>\n          {ordem && <><div><dt>Situação da ordem</dt><dd>{rotuloOrdem(ordem.status)}</dd></div><div><dt>Criada em</dt><dd>{formatarInstanteCotacao(instanteUtc(ordem.criada_em))}</dd></div>\n            <div><dt>Iniciada em</dt><dd>{ordem.iniciada_em ? formatarInstanteCotacao(instanteUtc(ordem.iniciada_em)) : \"Ainda não iniciada\"}</dd></div><div><dt>Concluída em</dt><dd>{ordem.concluida_em ? formatarInstanteCotacao(instanteUtc(ordem.concluida_em)) : \"Ainda não concluída\"}</dd></div>\n            {ordem.cancelada_em && <div><dt>Cancelada em</dt><dd>{formatarInstanteCotacao(instanteUtc(ordem.cancelada_em))}</dd></div>}</>}\n        </dl><h3>{ordem ? \"Observações da ordem\" : \"Observações da contratação\"}</h3><p className=\"o26-observacoes\">{item.observacoes || \"Sem observações.\"}</p>\n        {contrato && perfil === \"cliente\" && <div className=\"o26-operacao\"><p>A ordem será aberta com o valor e o prazo contratados e a quantidade da solicitação.</p><button className=\"o26-button o26-primary\" disabled={bloquear} onClick={() => revisar(\"gerar\")}><ClipboardList size={16} /> Revisar ordem de serviço</button></div>}\n        {ordem && perfil === \"fornecedor\" && <div className=\"o26-operacao\">\n          {ordem.contratacao_status !== \"ativa\" ? <p>A contratação está {rotuloContratacao(ordem.contratacao_status).toLowerCase()}. A execução da ordem está indisponível.</p>\n            : ordem.status === \"aberta\" ? <><p>Registre o início quando começar a executar o serviço.</p><button className=\"o26-button o26-primary\" disabled={bloquear} onClick={() => revisar(\"iniciar\")}><Play size={16} /> Iniciar serviço</button></>\n            : ordem.status === \"em_execucao\" ? <><p>Registre a conclusão após finalizar a execução do serviço.</p><button className=\"o26-button o26-primary\" disabled={bloquear} onClick={() => revisar(\"concluir\")}><CheckCircle2 size={16} /> Concluir serviço</button></>\n            : <p>{ordem.status === \"concluida\" ? \"O serviço foi concluído.\" : \"Esta ordem não permite novas ações de execução.\"}</p>}\n        </div>}\n        {ordem && perfil === \"cliente\" && <p>A execução é atualizada pelo fornecedor responsável. Use Atualizar para conferir a situação mais recente.</p>}\n      </section>\n    </div>}\n    <dialog ref={dialogo} className=\"o26-dialog\" aria-labelledby=\"o26-dialog-title\" onCancel={(e) => { if (trava.current) e.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>\n      {modalAtual && revisado && <><div className=\"o26-section-head\"><h2 id=\"o26-dialog-title\">{TITULOS[modalAtual.acao]}</h2><button className=\"o26-button\" aria-label=\"Fechar revisão\" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>\n        <p>{modalAtual.acao === \"gerar\" ? \"Confira os dados antes de gerar a ordem.\" : modalAtual.acao === \"iniciar\" ? \"Confirme que o serviço será iniciado agora.\" : \"Confirme que a execução deste serviço foi finalizada.\"}</p>\n        <dl className=\"o26-fields\"><div><dt>Solicitação</dt><dd>#{revisado.solicitacao_id}</dd></div><div><dt>{modalAtual.acao === \"gerar\" ? \"Contratação\" : \"Ordem de serviço\"}</dt><dd>#{revisado.id}</dd></div>\n          <div className=\"o26-wide\"><dt>Fornecedor</dt><dd>{revisado.fornecedor_razao_social}</dd></div><div><dt>Valor total</dt><dd>{formatarValorCotacao(revisado.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{revisado.prazo_dias} dias</dd></div></dl>\n        <p className=\"o26-review-note\">{modalAtual.acao === \"gerar\" ? \"A ordem ficará aberta para o fornecedor iniciar o serviço.\" : modalAtual.acao === \"iniciar\" ? \"A ordem ficará Em execução e terá a data de início registrada.\" : \"A ordem ficará Concluída e terá a data de conclusão registrada.\"}</p>\n        <div className=\"o26-dialog-actions\"><button className=\"o26-button\" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button><button className=\"o26-button o26-primary\" disabled={enviando} onClick={() => void confirmar()}>{enviando ? \"Registrando…\" : TITULOS[modalAtual.acao]}</button></div>\n      </>}\n    </dialog>\n  </main>;\n}\n",
  "frontend/src/pages/ordens/ordensPortal.ts": "import type { SolicitacaoFornecedor } from \"../supplier/cotacoesFornecedor\";\n\nexport type PerfilOrdens = \"cliente\" | \"fornecedor\";\nexport type AcaoOrdem = \"gerar\" | \"iniciar\" | \"concluir\";\nexport type OrdemResposta = {\n  id: number; contratacao_id: number; solicitacao_id: number; cotacao_id: number;\n  empresa_cliente_id: number; empresa_fornecedora_id: number;\n  processo_id: number; material_id: number; quantidade: number;\n  valor_total: string | number; prazo_dias: number; status: string; observacoes: string | null;\n  criada_em: string; iniciada_em: string | null; concluida_em: string | null; cancelada_em: string | null;\n};\nexport type OrdemPortal = OrdemResposta & {\n  cliente_razao_social: string; fornecedor_razao_social: string;\n  processo_nome: string; material_nome: string; contratacao_status: string;\n  solicitacao: SolicitacaoFornecedor;\n};\n\nexport function rotuloOrdem(status: string): string {\n  return ({ aberta: \"Aberta\", em_execucao: \"Em execução\", concluida: \"Concluída\", cancelada: \"Cancelada\" } as Record<string, string>)[status] ?? \"Situação indisponível\";\n}\n\nexport function mensagemErroOrdem(erro: unknown): string {\n  if (typeof erro === \"object\" && erro !== null && \"response\" in erro) {\n    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;\n    const mensagens: Record<string, string> = {\n      empresa_cliente_nao_encontrada: \"A empresa cliente deste acesso não foi encontrada.\",\n      empresa_fornecedor_nao_encontrada: \"A empresa fornecedora deste acesso não foi encontrada.\",\n      empresa_nao_e_cliente: \"Entre como cliente para consultar ou gerar suas ordens de serviço.\",\n      empresa_nao_e_fornecedor: \"Entre como fornecedor para consultar e executar suas ordens de serviço.\",\n      empresa_nao_e_cliente_da_contratacao: \"Esta contratação pertence a outro cliente.\",\n      contratacao_nao_encontrada: \"A contratação não está disponível. Atualize a lista.\",\n      contratacao_nao_esta_ativa: \"A contratação precisa estar ativa para gerar ou executar uma ordem. Atualize a tela.\",\n      ordem_servico_ja_cadastrada_para_esta_contratacao: \"Esta contratação já possui uma ordem de serviço. Consulte a aba Ordens de Serviço.\",\n      ordem_servico_nao_encontrada: \"A ordem não está disponível para esta empresa. Atualize a lista.\",\n      ordem_servico_nao_pode_ser_iniciada: \"Somente uma ordem aberta pode ser iniciada. Atualize a tela.\",\n      ordem_servico_nao_pode_ser_concluida: \"Somente uma ordem em execução pode ser concluída. Atualize a tela.\",\n      ordem_servico_alterada_atualize: \"A ordem foi alterada durante a operação. Atualize a tela antes de continuar.\",\n      arquivo_tecnico_nao_encontrado: \"O arquivo não está mais disponível. Atualize os arquivos.\",\n    };\n    if (typeof detalhe === \"string\") return mensagens[detalhe] ?? \"Não foi possível concluir a operação. Atualize a tela e tente novamente.\";\n    if (Array.isArray(detalhe)) return \"Confira a empresa deste acesso e atualize a tela.\";\n  }\n  return \"Não foi possível consultar os dados. Confira a conexão e atualize a tela.\";\n}\n",
  "tests/test_portal_ordens_servico.py": "from __future__ import annotations\n\nfrom datetime import datetime, timezone\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi import FastAPI\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine, event, select, update\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos\nfrom backend.app.api.rotas.ordens_servico import roteador as original\nfrom backend.app.api.rotas.portal_ordens_servico import roteador as portal\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.ordem_servico import OrdemServico\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\nfrom backend.app.services.portal_ordens_servico import ServicoPortalOrdens\n\nCLIENTE = \"/api/v1/portal-cliente\"\nFORNECEDOR = \"/api/v1/portal-fornecedor\"\n\n\ndef novo_contrato(banco, numero, cliente=1, fornecedor=2, situacao=\"ativa\"):\n    pedido = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,\n        dimensao_x_maxima_mm=500, dimensao_y_maxima_mm=300, dimensao_z_maxima_mm=250,\n        tolerancia_requerida_mm=Decimal(\"0.0200\"), quantidade=5, status=\"encerrada\", observacoes=\"Pedido D26.\")\n    banco.add(pedido)\n    banco.flush()\n    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=numero, empresa_fornecedora_id=fornecedor,\n        valor_total=Decimal(\"1250.50\"), prazo_dias=15, validade_dias=10, status=\"aceita\",\n        decidida_por_empresa_id=cliente, encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None))\n    banco.add(cotacao)\n    banco.flush()\n    contrato = ContratacaoServico(id=numero, solicitacao_id=numero, cotacao_id=numero,\n        empresa_cliente_id=cliente, empresa_fornecedora_id=fornecedor, valor_total=Decimal(\"1250.50\"),\n        prazo_dias=15, status=situacao, observacoes=\"Termos da contratação D26.\")\n    banco.add(contrato)\n    banco.flush()\n    return contrato\n\n\n@pytest.fixture()\ndef ambiente(tmp_path, monkeypatch):\n    engine = create_engine(\"sqlite://\", connect_args={\"check_same_thread\": False}, poolclass=StaticPool)\n\n    @event.listens_for(engine, \"connect\")\n    def chaves(conexao, _):\n        conexao.execute(\"PRAGMA foreign_keys=ON\")\n\n    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)\n    Base.metadata.create_all(engine)\n    monkeypatch.setattr(ServicoArquivoTecnico, \"STORAGE_ROOT\", tmp_path)\n    with sessoes() as banco:\n        banco.add_all([\n            Empresa(id=1, razao_social=\"Cliente D26\", documento=\"cliente-d26-1\", tipo_empresa=\"cliente\"),\n            Empresa(id=2, razao_social=\"Fornecedor D26\", documento=\"fornecedor-d26-2\", tipo_empresa=\"fornecedor\"),\n            Empresa(id=3, razao_social=\"Outro Fornecedor\", documento=\"fornecedor-d26-3\", tipo_empresa=\"fornecedor\"),\n            Empresa(id=4, razao_social=\"Empresa Ambos\", documento=\"ambos-d26-4\", tipo_empresa=\"ambos\"),\n            Empresa(id=5, razao_social=\"Outro Cliente\", documento=\"cliente-d26-5\", tipo_empresa=\"cliente\"),\n            ProcessoFabricacao(id=1, codigo=\"cnc-d26\", nome=\"Usinagem CNC\"),\n            Material(id=1, codigo=\"al6061-d26\", nome=\"Alumínio 6061\"),\n        ])\n        banco.commit()\n        novo_contrato(banco, 1)\n        novo_contrato(banco, 2, cliente=5, fornecedor=3)\n        novo_contrato(banco, 3, situacao=\"cancelada\")\n        novo_contrato(banco, 4, situacao=\"encerrada\")\n        novo_contrato(banco, 5)\n        banco.commit()\n\n    def banco_teste():\n        with sessoes() as banco:\n            yield banco\n\n    app = FastAPI()\n    for roteador in (arquivos, original, portal):\n        app.include_router(roteador, prefix=\"/api/v1\")\n    app.dependency_overrides[obter_banco] = banco_teste\n    try:\n        with TestClient(app) as http:\n            yield http, sessoes\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(engine)\n        engine.dispose()\n\n\ndef gerar(http, contrato=1, cliente=1, **extra):\n    return http.post(f\"{CLIENTE}/contratacoes/{contrato}/ordem-servico\", json={\"empresa_cliente_id\": cliente, **extra})\n\n\ndef listar(http, perfil=\"cliente\", empresa=1, **extra):\n    return http.get(f\"/api/v1/portal-{perfil}/ordens-servico\", params={\n        \"empresa_cliente_id\" if perfil == \"cliente\" else \"empresa_fornecedora_id\": empresa, **extra,\n    })\n\n\ndef candidatas(http, cliente=1, **extra):\n    return http.get(CLIENTE + \"/contratacoes-para-ordem\", params={\"empresa_cliente_id\": cliente, **extra})\n\n\ndef agir(http, ordem, acao=\"iniciar\", fornecedor=2):\n    return http.post(f\"{FORNECEDOR}/ordens-servico/{ordem}/{acao}\", json={\"empresa_fornecedora_id\": fornecedor})\n\n\ndef test_candidatas_ativas_da_empresa_com_nomes_e_paginacao(ambiente):\n    http, _ = ambiente\n    pagina = candidatas(http, limite=1).json()\n    assert pagina[\"total\"] == 2 and pagina[\"itens\"][0][\"id\"] == 5\n    item = candidatas(http, deslocamento=1, limite=1).json()[\"itens\"][0]\n    assert item[\"id\"] == 1 and item[\"fornecedor_razao_social\"] == \"Fornecedor D26\"\n    assert item[\"solicitacao\"][\"processo_nome\"] == \"Usinagem CNC\"\n    assert [item[\"id\"] for item in candidatas(http, 5).json()[\"itens\"]] == [2]\n\n\ndef test_gerar_copia_d9_e_e_visivel_so_aos_donos(ambiente):\n    http, sessoes = ambiente\n    resposta = gerar(http, valor_total=\"0.01\", prazo_dias=1, quantidade=99, empresa_fornecedora_id=3)\n    assert resposta.status_code == 201\n    ordem = resposta.json()\n    assert ordem[\"status\"] == \"aberta\" and ordem[\"valor_total\"] == \"1250.50\"\n    assert ordem[\"prazo_dias\"] == 15 and ordem[\"quantidade\"] == 5 and ordem[\"empresa_fornecedora_id\"] == 2\n    assert ordem[\"observacoes\"] == \"Termos da contratação D26.\"\n    cliente = listar(http).json()[\"itens\"][0]\n    fornecedor = listar(http, \"fornecedor\", 2).json()[\"itens\"][0]\n    assert cliente == fornecedor and cliente[\"cliente_razao_social\"] == \"Cliente D26\"\n    assert cliente[\"fornecedor_razao_social\"] == \"Fornecedor D26\"\n    assert cliente[\"contratacao_status\"] == \"ativa\" and cliente[\"processo_nome\"] == \"Usinagem CNC\"\n    assert listar(http, \"cliente\", 5).json()[\"total\"] == 0\n    assert listar(http, \"fornecedor\", 3).json()[\"total\"] == 0\n    assert [item[\"id\"] for item in candidatas(http).json()[\"itens\"]] == [5]\n    with sessoes() as banco:\n        assert banco.get(ContratacaoServico, 1).status == \"ativa\"\n        assert banco.get(SolicitacaoServico, 1).status == \"encerrada\"\n\n\n@pytest.mark.parametrize(\"situacao\", [\"aberta\", \"em_execucao\", \"concluida\", \"cancelada\"])\ndef test_ordem_existente_em_qualquer_status_impede_nova_ordem(ambiente, situacao):\n    http, sessoes = ambiente\n    ordem = gerar(http).json()\n    with sessoes() as banco:\n        banco.get(OrdemServico, ordem[\"id\"]).status = situacao\n        banco.commit()\n    assert [item[\"id\"] for item in candidatas(http).json()[\"itens\"]] == [5]\n    repetida = gerar(http)\n    assert repetida.status_code == 409\n    assert repetida.json()[\"detail\"] == \"ordem_servico_ja_cadastrada_para_esta_contratacao\"\n    with sessoes() as banco:\n        assert len(banco.scalars(select(OrdemServico)).all()) == 1\n\n\n@pytest.mark.parametrize(\"contrato,cliente,codigo\", [(2,1,403),(1,2,403),(999,1,404),(3,1,409),(4,1,409)])\ndef test_criacao_com_empresa_ou_contrato_invalido_nao_altera_banco(ambiente, contrato, cliente, codigo):\n    http, sessoes = ambiente\n    assert gerar(http, contrato, cliente).status_code == codigo\n    with sessoes() as banco:\n        assert banco.scalars(select(OrdemServico)).all() == []\n\n\n@pytest.mark.parametrize(\"perfil,empresa,codigo\", [(\"cliente\",999,404),(\"fornecedor\",999,404),(\"cliente\",2,403),(\"fornecedor\",1,403)])\ndef test_consulta_exige_empresa_existente_do_perfil(ambiente, perfil, empresa, codigo):\n    http, _ = ambiente\n    assert listar(http, perfil, empresa).status_code == codigo\n\n\n@pytest.mark.parametrize(\"parametros\", [{}, {\"empresa_cliente_id\":0}, {\"empresa_cliente_id\":1,\"limite\":101},\n                                      {\"empresa_cliente_id\":1,\"deslocamento\":-1}])\ndef test_consulta_valida_parametros(ambiente, parametros):\n    http, _ = ambiente\n    assert http.get(CLIENTE + \"/ordens-servico\", params=parametros).status_code == 422\n\n\ndef test_detalhe_e_paginacao_nao_expoem_ordem_de_outra_empresa(ambiente):\n    http, _ = ambiente\n    primeira = gerar(http).json()[\"id\"]\n    segunda = gerar(http, 5).json()[\"id\"]\n    assert listar(http, limite=1).json()[\"itens\"][0][\"id\"] == segunda\n    assert listar(http, deslocamento=1, limite=1).json()[\"itens\"][0][\"id\"] == primeira\n    for perfil, empresa in ((\"cliente\",5),(\"fornecedor\",3)):\n        param = \"empresa_cliente_id\" if perfil == \"cliente\" else \"empresa_fornecedora_id\"\n        assert http.get(f\"/api/v1/portal-{perfil}/ordens-servico/{primeira}\", params={param:empresa}).status_code == 404\n\n\ndef test_fornecedor_inicia_conclui_e_cliente_acompanha_datas_sem_alterar_termos(ambiente):\n    http, sessoes = ambiente\n    ordem = gerar(http).json()\n    iniciada = agir(http, ordem[\"id\"])\n    assert iniciada.status_code == 200 and iniciada.json()[\"status\"] == \"em_execucao\"\n    inicio = iniciada.json()[\"iniciada_em\"]\n    concluida = agir(http, ordem[\"id\"], \"concluir\")\n    assert concluida.status_code == 200 and concluida.json()[\"status\"] == \"concluida\"\n    assert concluida.json()[\"iniciada_em\"] == inicio and concluida.json()[\"concluida_em\"] is not None\n    assert concluida.json()[\"observacoes\"] == ordem[\"observacoes\"]\n    assert listar(http).json()[\"itens\"][0][\"status\"] == \"concluida\"\n    with sessoes() as banco:\n        assert banco.get(ContratacaoServico, 1).status == \"ativa\"\n        assert banco.get(CotacaoFornecedor, 1).status == \"aceita\"\n\n\n@pytest.mark.parametrize(\"fornecedor,codigo\", [(3,404),(1,403),(999,404)])\ndef test_acao_rejeita_fornecedor_errado(ambiente, fornecedor, codigo):\n    http, sessoes = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    assert agir(http, ordem, fornecedor=fornecedor).status_code == codigo\n    with sessoes() as banco:\n        item = banco.get(OrdemServico, ordem)\n        assert item.status == \"aberta\" and item.iniciada_em is None\n\n\ndef test_acao_fornecedor_nao_aceita_identidade_de_cliente_no_corpo(ambiente):\n    http, _ = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    url = f\"{FORNECEDOR}/ordens-servico/{ordem}/iniciar\"\n    assert http.post(url, json={\"empresa_cliente_id\":1}).status_code == 422\n    assert http.post(url, json={\"empresa_fornecedora_id\":2,\"empresa_cliente_id\":1}).status_code == 422\n\n\n@pytest.mark.parametrize(\"situacao,acao\", [(\"aberta\",\"concluir\"),(\"em_execucao\",\"iniciar\"),\n                                         (\"concluida\",\"iniciar\"),(\"concluida\",\"concluir\"),(\"cancelada\",\"iniciar\")])\ndef test_transicao_invalida_nao_muda_estado_ou_datas(ambiente, situacao, acao):\n    http, sessoes = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    with sessoes() as banco:\n        banco.get(OrdemServico, ordem).status = situacao\n        banco.commit()\n    assert agir(http, ordem, acao).status_code == 409\n    with sessoes() as banco:\n        item = banco.get(OrdemServico, ordem)\n        assert item.status == situacao and item.iniciada_em is None and item.concluida_em is None\n\n\ndef test_repetir_acoes_nao_sobrescreve_datas(ambiente):\n    http, _ = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    inicio = agir(http, ordem).json()[\"iniciada_em\"]\n    assert agir(http, ordem).status_code == 409\n    fim = agir(http, ordem, \"concluir\").json()[\"concluida_em\"]\n    assert agir(http, ordem, \"concluir\").status_code == 409\n    atual = listar(http).json()[\"itens\"][0]\n    assert atual[\"iniciada_em\"] == inicio and atual[\"concluida_em\"] == fim\n\n\n@pytest.mark.parametrize(\"situacao\", [\"cancelada\",\"encerrada\"])\ndef test_contrato_inativo_mantem_historico_mas_bloqueia_execucao(ambiente, situacao):\n    http, sessoes = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    with sessoes() as banco:\n        banco.get(ContratacaoServico, 1).status = situacao\n        banco.commit()\n    assert agir(http, ordem).status_code == 409\n    assert listar(http, \"fornecedor\", 2).json()[\"itens\"][0][\"contratacao_status\"] == situacao\n\n\ndef test_alteracao_concorrente_entre_leitura_e_update_nao_e_sobrescrita(ambiente, monkeypatch):\n    http, sessoes = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    obter = ServicoPortalOrdens.obter\n    executou = False\n\n    def obter_e_alterar(self, *args):\n        nonlocal executou\n        leitura = obter(self, *args)\n        if not executou:\n            executou = True\n            with sessoes() as banco:\n                banco.execute(update(OrdemServico).where(OrdemServico.id == ordem).values(status=\"cancelada\"))\n                banco.commit()\n        return leitura\n\n    monkeypatch.setattr(ServicoPortalOrdens, \"obter\", obter_e_alterar)\n    resposta = agir(http, ordem)\n    assert resposta.status_code == 409 and resposta.json()[\"detail\"] == \"ordem_servico_alterada_atualize\"\n    with sessoes() as banco:\n        assert banco.get(OrdemServico, ordem).status == \"cancelada\"\n\n\ndef test_empresa_ambos_pode_gerar_e_operar_nos_papeis_corretos(ambiente):\n    http, sessoes = ambiente\n    with sessoes() as banco:\n        novo_contrato(banco, 6, cliente=4, fornecedor=4)\n        banco.commit()\n    ordem = gerar(http, 6, 4).json()[\"id\"]\n    assert listar(http, \"cliente\", 4).json()[\"total\"] == 1\n    assert listar(http, \"fornecedor\", 4).json()[\"total\"] == 1\n    assert agir(http, ordem, fornecedor=4).status_code == 200\n\n\ndef test_snapshot_da_ordem_preserva_processo_material_e_quantidade(ambiente):\n    http, sessoes = ambiente\n    gerar(http)\n    with sessoes() as banco:\n        banco.add_all([ProcessoFabricacao(id=2,codigo=\"outro-d26\",nome=\"Outro Processo\"),\n                       Material(id=2,codigo=\"outro-mat-d26\",nome=\"Outro Material\")])\n        banco.flush()\n        pedido = banco.get(SolicitacaoServico,1)\n        pedido.processo_id = 2; pedido.material_id = 2; pedido.quantidade = 99\n        banco.commit()\n    ordem = listar(http).json()[\"itens\"][0]\n    assert ordem[\"processo_nome\"] == \"Usinagem CNC\" and ordem[\"material_nome\"] == \"Alumínio 6061\"\n    assert ordem[\"quantidade\"] == 5\n    assert ordem[\"solicitacao\"][\"processo_nome\"] == \"Outro Processo\"\n\n\n@pytest.mark.parametrize(\"extensao\", [\"zip\",\"rar\"])\ndef test_arquivos_ativos_somente_da_ordem_e_dos_donos(ambiente, extensao):\n    http, _ = ambiente\n    ordem = gerar(http).json()[\"id\"]\n    arquivo = http.post(\"/api/v1/solicitacoes-servico/1/arquivos-tecnicos\",\n        files={\"file\":(f\"peca.{extensao}\",b\"arquivo D26\",\"application/octet-stream\")})\n    assert arquivo.status_code == 201\n    aid = arquivo.json()[\"id\"]\n    outro = http.post(\"/api/v1/solicitacoes-servico/2/arquivos-tecnicos\",\n        files={\"file\":(\"outro.zip\",b\"outro\",\"application/zip\")}).json()[\"id\"]\n    for perfil, empresa in ((\"cliente\",1),(\"fornecedor\",2)):\n        base = f\"/api/v1/portal-{perfil}/ordens-servico/{ordem}/arquivos\"\n        params = {\"empresa_cliente_id\" if perfil == \"cliente\" else \"empresa_fornecedora_id\":empresa}\n        assert [item[\"id\"] for item in http.get(base, params=params).json()] == [aid]\n        assert http.get(f\"{base}/{aid}/download\",params=params).content == b\"arquivo D26\"\n        assert http.get(f\"{base}/{outro}/download\",params=params).status_code == 404\n        params[next(iter(params))] = 5 if perfil == \"cliente\" else 3\n        assert http.get(base,params=params).status_code == 404\n        assert http.get(f\"{base}/{aid}/download\",params=params).status_code == 404\n    assert http.delete(f\"/api/v1/arquivos-tecnicos/{aid}\").status_code == 204\n    base = f\"{FORNECEDOR}/ordens-servico/{ordem}/arquivos\"\n    assert http.get(base,params={\"empresa_fornecedora_id\":2}).json() == []\n    assert http.get(f\"{base}/{aid}/download\",params={\"empresa_fornecedora_id\":2}).status_code == 404\n\n\ndef test_rotas_d9_existentes_continuam_funcionando(ambiente):\n    http, _ = ambiente\n    criada = http.post(\"/api/v1/contratacoes/1/ordem-servico\",json={\"empresa_cliente_id\":1})\n    assert criada.status_code == 201\n    oid = criada.json()[\"id\"]\n    assert http.post(f\"/api/v1/ordens-servico/{oid}/iniciar\",json={\"empresa_cliente_id\":1}).status_code == 200\n    assert listar(http,\"fornecedor\",2).json()[\"itens\"][0][\"status\"] == \"em_execucao\"\n"
}
ALVOS = (APP_REL, ROUTER_REL, *(Path(nome) for nome in FONTES))
IMPORT_LINE = 'import PortalOrdensServicoPage from "./pages/ordens/PortalOrdensServicoPage";'


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
        raise RuntimeError("Campos ausentes no portal de ordens: " + ", ".join(sorted(ausentes)))

for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    base = "/api/v1/portal-" + perfil + "/ordens-servico"
    for sufixo in ("", "/{ordem_id}", "/{ordem_id}/arquivos", "/{ordem_id}/arquivos/{arquivo_id}/download"):
        op = paths.get(base + sufixo, {}).get("get")
        if not op:
            raise RuntimeError("Rota de ordens do portal ausente: " + base + sufixo)
        params = {p["name"]: p for p in op.get("parameters", [])}
        dono = params.get(empresa, {})
        if dono.get("in") != "query" or not dono.get("required"):
            raise RuntimeError("Consulta de ordem sem empresa obrigatória.")
        if sufixo in ("", "/{ordem_id}"):
            dados = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
            if not sufixo:
                campos(dados, ("itens", "total", "limite", "deslocamento"))
                if not {"limite", "deslocamento"}.issubset(params):
                    raise RuntimeError("Listagem de ordens sem paginação.")
                dados = schema(schema(dados["properties"]["itens"])["items"])
            campos(dados, ("id", "contratacao_id", "empresa_cliente_id", "empresa_fornecedora_id", "status",
                           "cliente_razao_social", "fornecedor_razao_social", "processo_nome", "material_nome",
                           "contratacao_status", "solicitacao", "iniciada_em", "concluida_em"))
op = paths.get("/api/v1/portal-cliente/contratacoes-para-ordem", {}).get("get")
if not op:
    raise RuntimeError("Consulta de contratações para gerar ordem ausente.")
dados = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
campos(dados, ("itens", "total", "limite", "deslocamento"))
op = paths.get("/api/v1/portal-cliente/contratacoes/{contratacao_id}/ordem-servico", {}).get("post")
if not op:
    raise RuntimeError("Geração de ordem do portal do cliente ausente.")
campos(op["requestBody"]["content"]["application/json"]["schema"], ("empresa_cliente_id",))
campos(op["responses"]["201"]["content"]["application/json"]["schema"], ("id", "contratacao_id", "status"))
for acao in ("iniciar", "concluir"):
    op = paths.get("/api/v1/portal-fornecedor/ordens-servico/{ordem_id}/" + acao, {}).get("post")
    if not op:
        raise RuntimeError("Ação de execução da ordem ausente: " + acao)
    corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
    if set(corpo.get("properties", {})) != {"empresa_fornecedora_id"} or set(corpo.get("required", [])) != {"empresa_fornecedora_id"}:
        raise RuntimeError("Ação de execução sem identidade obrigatória do fornecedor.")
print("ORDENS_CLIENTE_FORNECEDOR_PAGINADAS_OK=True")
print("GERACAO_CLIENTE_E_EXECUCAO_FORNECEDOR_OK=True")
print("DETALHES_DATAS_E_ARQUIVOS_DAS_ORDENS_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/api/roteador.py",
        "backend/app/models/ordem_servico.py", "backend/app/services/ordem_servico.py",
        "backend/app/schemas/ordem_servico.py", "backend/app/api/rotas/ordens_servico.py",
        "backend/app/models/contratacao.py", "backend/app/services/arquivo_tecnico.py",
        "backend/app/services/portal_contratacoes.py", "backend/app/schemas/portal_contratacoes.py",
        "backend/app/api/rotas/portal_contratacoes.py",
        "frontend/src/App.tsx", "frontend/package.json", "frontend/src/auth/AuthContext.tsx",
        "frontend/src/services/api.ts", "frontend/src/pages/contratacoes/PortalContratacoesPage.tsx",
        "frontend/src/pages/contratacoes/contratacoesPortal.ts",
        "frontend/src/pages/client/cotacoesCliente.ts", "frontend/src/pages/supplier/cotacoesFornecedor.ts",
        "tests/test_ordens_servico.py", "tests/test_portal_contratacoes.py",
    )
    ausentes = [nome for nome in obrigatorios if not (raiz / nome).is_file()]
    if ausentes:
        raise RuntimeError("Execute na raiz do MEC-Servicos com D9 e D25 instalados. Arquivos ausentes: " + ", ".join(ausentes))
    return raiz


def validar_fontes_existentes(originais: dict[Path, bytes | None]) -> None:
    for nome, fonte in FONTES.items():
        if nome.endswith(".py"):
            ast.parse(fonte, filename=nome)
        anterior = originais[Path(nome)]
        if anterior is not None:
            texto = anterior.decode("utf-8-sig").replace("\r\n", "\n").rstrip()
            if texto != fonte.replace("\r\n", "\n").rstrip():
                raise RuntimeError("Já existe um arquivo diferente no destino D26. Ele foi preservado: " + nome)


def atualizar_roteador(texto: str) -> str:
    arvore = ast.parse(texto)
    modulo = "backend.app.api.rotas.portal_ordens_servico"
    alias = "roteador_portal_ordens_servico"
    importacoes = [n for n in arvore.body if isinstance(n, ast.ImportFrom) and n.module == modulo]
    for n in importacoes:
        if len(n.names) != 1 or n.names[0].name != "roteador" or n.names[0].asname != alias:
            raise RuntimeError("O import do portal de ordens de serviço já usa outro formato. O roteador foi preservado.")
    if len(importacoes) > 1:
        raise RuntimeError("Há imports duplicados do portal de ordens de serviço.")
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "roteador_api" and n.func.attr == "include_router"
                and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == alias]
    if len(chamadas) > 1 or any(n.keywords or len(n.args) != 1 for n in chamadas):
        raise RuntimeError("O registro do portal de ordens de serviço já usa outro formato.")
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
        candidatas = [item for item in rotas if grupo["fim_abertura"] <= item["inicio"] < item["fim"] <= grupo["fim"] and item["path"] == "ordens-servico"]
        if len(candidatas) != 1 or not candidatas[0]["auto_fecha"]:
            raise RuntimeError("Não encontrei uma única rota de ordens de serviço no portal " + perfil + ".")
        rota = candidatas[0]
        abertura = texto[rota["inicio"]:rota["fim"]]
        componentes = list(re.finditer(r"<(?:ModulePage|PortalOrdensServicoPage)\b", abertura))
        if len(componentes) != 1:
            raise RuntimeError("A rota de ordens de serviço do " + perfil + " usa outra tela. Ela foi preservada.")
        inicio = rota["inicio"] + componentes[0].start()
        fim = fim_tag(texto, inicio)
        if not texto[inicio:fim].rstrip().endswith("/>"):
            raise RuntimeError("O componente de ordens de serviço do " + perfil + " possui filhos. Ele foi preservado.")
        novo = f'<PortalOrdensServicoPage perfil="{perfil}" />'
        if texto[inicio:fim] != novo:
            trocas.append((inicio, fim, novo))
    atualizado = texto
    for inicio, fim, novo in sorted(trocas, reverse=True):
        atualizado = atualizado[:inicio] + novo + atualizado[fim:]
    existente = re.search(r'''import\s+PortalOrdensServicoPage\s+from\s*["']\./pages/ordens/PortalOrdensServicoPage["']\s*;?''', atualizado)
    if not existente:
        if "./pages/ordens/PortalOrdensServicoPage" in atualizado:
            raise RuntimeError("O import de ordens de serviço usa outro formato. Nenhum fonte foi alterado.")
        quebra = "\r\n" if "\r\n" in atualizado else "\n"
        atualizado = IMPORT_LINE + quebra + atualizado
    return atualizado

VALIDACAO_CONTRATO = r'''
from sqlalchemy import UniqueConstraint
from backend.app.principal import app
from backend.app.models.ordem_servico import OrdemServico
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico

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
        raise RuntimeError("Campos ausentes no contrato de ordens: " + ", ".join(sorted(ausentes)))

esperados = ("id", "contratacao_id", "solicitacao_id", "cotacao_id", "empresa_cliente_id", "empresa_fornecedora_id",
             "processo_id", "material_id", "quantidade", "valor_total", "prazo_dias", "observacoes", "status",
             "criada_em", "iniciada_em", "concluida_em", "cancelada_em")
op = paths.get("/api/v1/contratacoes/{contratacao_id}/ordem-servico", {}).get("post")
if not op:
    raise RuntimeError("A criação de ordens D9 não está registrada.")
corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
campos(corpo, ("empresa_cliente_id",))
if set(corpo.get("required", [])) != {"empresa_cliente_id"}:
    raise RuntimeError("O corpo de criação difere do contrato D9.")
campos(op["responses"]["201"]["content"]["application/json"]["schema"], esperados)
for sufixo, metodo in (("", "get"), ("/{ordem_id}", "get"), ("/{ordem_id}/iniciar", "post"), ("/{ordem_id}/concluir", "post")):
    if metodo not in paths.get("/api/v1/ordens-servico" + sufixo, {}):
        raise RuntimeError("Rota de ordens D9 ausente: " + sufixo)
for nome in esperados:
    if not hasattr(OrdemServico, nome):
        raise RuntimeError("Modelo de ordem sem o campo " + nome)
unicas = [set(c.columns.keys()) for c in OrdemServico.__table__.constraints if isinstance(c, UniqueConstraint)]
if {"contratacao_id"} not in unicas:
    raise RuntimeError("A restrição de uma ordem por contratação está ausente.")
for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    op = paths.get("/api/v1/portal-" + perfil + "/contratacoes", {}).get("get")
    if not op or not any(p["name"] == empresa and p.get("required") for p in op.get("parameters", [])):
        raise RuntimeError("O portal de contratações D25 não está instalado para " + perfil)
if not {".zip", ".rar"}.issubset(ServicoArquivoTecnico.ALLOWED_EXTENSIONS):
    raise RuntimeError("O suporte a ZIP/RAR do D22 não está instalado.")
print("CONTRATO_ORDENS_D9_OK=True")
print("UMA_ORDEM_POR_CONTRATACAO_OK=True")
print("PORTAIS_D25_E_ARQUIVOS_ZIP_RAR_OK=True")
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
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d26_", delete=False) as arquivo:
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
        "MEC-Serviços D26 — Ordens de Serviço nos Portais do Cliente e Fornecedor",
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
    print("MEC-Serviços D26 — Ordens de Serviço nos Portais do Cliente e Fornecedor", flush=True)
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
        backup = raiz / "_mec_backups" / ("D26_PORTAIS_ORDENS_SERVICO_" + carimbo)
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
        print("ORDENS_TELAS_ROTAS_E_BACKEND_OK=True", flush=True)
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
    print("Reinicie o backend e atualize /cliente/ordens-servico com Ctrl+F5.", flush=True)
    print("Como cliente, abra Contratações para gerar ordem, selecione uma contratação ativa, revise e confirme a geração.", flush=True)
    print("Como fornecedor, abra /fornecedor/ordens-servico; confirme Iniciar serviço e depois Concluir serviço em uma ordem de teste.", flush=True)
    print("Confira as situações Aberta, Em execução e Concluída no portal do cliente, além das datas e dos arquivos técnicos.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
