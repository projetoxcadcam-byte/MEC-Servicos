r"""MEC-Serviços D24 — Portal do Fornecedor / Envio de Cotações.

Na raiz do projeto, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D24_PORTAL_FORNECEDOR_COTACOES.py

Requer os módulos D22 e D23 instalados. Acrescenta consultas de oportunidades,
histórico do fornecedor e acesso aos arquivos técnicos. O envio usa o serviço
de cotações existente. Não cria registros de demonstração nem instala pacotes.
Faz backup dos fontes e do frontend/dist; executa os testes MEC e npm run build.
Se qualquer etapa falhar, restaura os arquivos alterados e o dist anterior.
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

REVISION = "MEC-SERVICOS-V0.1-D24-PORTAL-FORNECEDOR-COTACOES-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D24_PORTAL_FORNECEDOR_COTACOES_RELATORIO"
APP_REL = Path("frontend/src/App.tsx")
ROUTER_REL = Path("backend/app/api/roteador.py")
DIST_REL = Path("frontend/dist")
FONTES = {'backend/app/api/rotas/portal_fornecedor.py': 'from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, Query, status\nfrom fastapi.responses import FileResponse\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.api.rotas.cotacoes import criar_cotacao\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta\nfrom backend.app.schemas.cotacao import CotacaoCriacao, CotacaoLeitura\nfrom backend.app.schemas.portal_fornecedor import CotacoesFornecedorLeitura, OportunidadesFornecedorLeitura\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\nfrom backend.app.services.portal_fornecedor import ServicoPortalFornecedor\n\nroteador = APIRouter(prefix="/portal-fornecedor", tags=["portal do fornecedor"])\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\nEmpresaFornecedor = Annotated[int, Query(gt=0)]\n\n\n@roteador.get("/oportunidades", response_model=OportunidadesFornecedorLeitura)\ndef listar_oportunidades(\n    banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor,\n    deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100),\n) -> OportunidadesFornecedorLeitura:\n    return ServicoPortalFornecedor(banco).listar_oportunidades(empresa_fornecedora_id, deslocamento, limite)\n\n\n@roteador.get("/cotacoes", response_model=CotacoesFornecedorLeitura)\ndef listar_minhas_cotacoes(\n    banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor,\n    deslocamento: int = Query(default=0, ge=0), limite: int = Query(default=20, ge=1, le=100),\n) -> CotacoesFornecedorLeitura:\n    return ServicoPortalFornecedor(banco).listar_cotacoes(empresa_fornecedora_id, deslocamento, limite)\n\n\n@roteador.post("/solicitacoes/{solicitacao_id}/cotacoes", response_model=CotacaoLeitura, status_code=status.HTTP_201_CREATED)\ndef enviar_cotacao(solicitacao_id: int, dados: CotacaoCriacao, banco: SessaoBanco) -> CotacaoLeitura:\n    ServicoPortalFornecedor(banco).validar_envio(solicitacao_id, dados.empresa_fornecedora_id)\n    return criar_cotacao(solicitacao_id, dados, banco)\n\n\n@roteador.get("/solicitacoes/{solicitacao_id}/arquivos", response_model=list[ArquivoTecnicoResposta])\ndef listar_arquivos(solicitacao_id: int, banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor) -> list[ArquivoTecnicoResposta]:\n    ServicoPortalFornecedor(banco).validar_acesso_arquivos(solicitacao_id, empresa_fornecedora_id)\n    return [ArquivoTecnicoResposta.model_validate(item) for item in ServicoArquivoTecnico(banco).listar(solicitacao_id)]\n\n\n@roteador.get("/arquivos/{arquivo_id}/download", response_class=FileResponse)\ndef baixar_arquivo(arquivo_id: int, banco: SessaoBanco, empresa_fornecedora_id: EmpresaFornecedor) -> FileResponse:\n    arquivos = ServicoArquivoTecnico(banco)\n    item = arquivos.obter(arquivo_id)\n    ServicoPortalFornecedor(banco).validar_acesso_arquivos(item.solicitacao_id, empresa_fornecedora_id)\n    return FileResponse(arquivos.caminho_seguro(item), media_type=item.content_type or "application/octet-stream", filename=item.nome_original)\n', 'backend/app/schemas/portal_fornecedor.py': 'from __future__ import annotations\n\nfrom pydantic import BaseModel\n\nfrom backend.app.schemas.cotacao import CotacaoLeitura\nfrom backend.app.schemas.solicitacao import SolicitacaoServicoLeitura\n\n\nclass SolicitacaoFornecedorLeitura(SolicitacaoServicoLeitura):\n    cliente_razao_social: str\n    processo_nome: str\n    material_nome: str\n\n\nclass CotacaoFornecedorLeitura(CotacaoLeitura):\n    solicitacao: SolicitacaoFornecedorLeitura\n\n\nclass OportunidadesFornecedorLeitura(BaseModel):\n    itens: list[SolicitacaoFornecedorLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n\n\nclass CotacoesFornecedorLeitura(BaseModel):\n    itens: list[CotacaoFornecedorLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n', 'backend/app/services/portal_fornecedor.py': 'from __future__ import annotations\n\nfrom datetime import timedelta\n\nfrom fastapi import HTTPException\nfrom sqlalchemy import func, select\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.models.capacidade import CapacidadeFornecedor\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.material_fornecedor import MaterialFornecedor\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.schemas.cotacao import CotacaoLeitura\nfrom backend.app.schemas.portal_fornecedor import (\n    CotacaoFornecedorLeitura,\n    CotacoesFornecedorLeitura,\n    OportunidadesFornecedorLeitura,\n    SolicitacaoFornecedorLeitura,\n)\nfrom backend.app.schemas.solicitacao import SolicitacaoServicoLeitura\nfrom backend.app.services.cotacao import ServicoCotacao\n\n\nclass ServicoPortalFornecedor:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def validar_fornecedor(self, empresa_id: int) -> Empresa:\n        empresa = self.banco.get(Empresa, empresa_id)\n        if empresa is None:\n            raise HTTPException(404, detail="empresa_fornecedora_nao_encontrada")\n        if empresa.tipo_empresa not in {"fornecedor", "ambos"}:\n            raise HTTPException(409, detail="empresa_nao_e_fornecedora")\n        return empresa\n\n    @staticmethod\n    def _compativel(empresa_id: int):\n        # Mesmas comparações do RepositorioCompatibilidade, com os eixos na\n        # ordem cadastrada. EXISTS impede que vínculos multipliquem resultados.\n        return (\n            select(CapacidadeFornecedor.id)\n            .join(MaterialFornecedor, MaterialFornecedor.empresa_id == CapacidadeFornecedor.empresa_id)\n            .where(\n                CapacidadeFornecedor.empresa_id == empresa_id,\n                CapacidadeFornecedor.processo_id == SolicitacaoServico.processo_id,\n                MaterialFornecedor.material_id == SolicitacaoServico.material_id,\n                CapacidadeFornecedor.dimensao_x_maxima_mm >= SolicitacaoServico.dimensao_x_maxima_mm,\n                CapacidadeFornecedor.dimensao_y_maxima_mm >= SolicitacaoServico.dimensao_y_maxima_mm,\n                CapacidadeFornecedor.dimensao_z_maxima_mm >= SolicitacaoServico.dimensao_z_maxima_mm,\n                CapacidadeFornecedor.tolerancia_minima_mm <= SolicitacaoServico.tolerancia_requerida_mm,\n            )\n            .correlate(SolicitacaoServico)\n            .exists()\n        )\n\n    @staticmethod\n    def _nomes(consulta):\n        return (\n            consulta\n            .join(Empresa, Empresa.id == SolicitacaoServico.empresa_cliente_id)\n            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)\n            .join(Material, Material.id == SolicitacaoServico.material_id)\n        )\n\n    @staticmethod\n    def _solicitacao(item, cliente: str, processo: str, material: str) -> SolicitacaoFornecedorLeitura:\n        return SolicitacaoFornecedorLeitura(\n            **SolicitacaoServicoLeitura.model_validate(item).model_dump(),\n            cliente_razao_social=cliente,\n            processo_nome=processo,\n            material_nome=material,\n        )\n\n    def listar_oportunidades(self, empresa_id: int, deslocamento: int, limite: int) -> OportunidadesFornecedorLeitura:\n        self.validar_fornecedor(empresa_id)\n        ja_enviou = select(CotacaoFornecedor.id).where(\n            CotacaoFornecedor.solicitacao_id == SolicitacaoServico.id,\n            CotacaoFornecedor.empresa_fornecedora_id == empresa_id,\n        ).correlate(SolicitacaoServico).exists()\n        possui_aceita = select(CotacaoFornecedor.id).where(\n            CotacaoFornecedor.solicitacao_id == SolicitacaoServico.id,\n            CotacaoFornecedor.status == "aceita",\n        ).correlate(SolicitacaoServico).exists()\n        filtros = (\n            SolicitacaoServico.status == "aberta", self._compativel(empresa_id),\n            ~ja_enviou, ~possui_aceita,\n        )\n        contagem = self._nomes(select(func.count()).select_from(SolicitacaoServico)).where(*filtros)\n        total = self.banco.scalar(contagem) or 0\n        consulta = self._nomes(select(\n            SolicitacaoServico, Empresa.razao_social, ProcessoFabricacao.nome, Material.nome,\n        )).where(*filtros).order_by(SolicitacaoServico.id.desc()).offset(deslocamento).limit(limite)\n        itens = [self._solicitacao(*linha) for linha in self.banco.execute(consulta).all()]\n        return OportunidadesFornecedorLeitura(itens=itens, total=total, deslocamento=deslocamento, limite=limite)\n\n    def listar_cotacoes(self, empresa_id: int, deslocamento: int, limite: int) -> CotacoesFornecedorLeitura:\n        self.validar_fornecedor(empresa_id)\n        filtros = CotacaoFornecedor.empresa_fornecedora_id == empresa_id\n        contagem = self._nomes(\n            select(func.count()).select_from(CotacaoFornecedor)\n            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)\n        ).where(filtros)\n        total = self.banco.scalar(contagem) or 0\n        consulta = self._nomes(\n            select(CotacaoFornecedor, SolicitacaoServico, Empresa.razao_social, ProcessoFabricacao.nome, Material.nome)\n            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)\n        ).where(filtros).order_by(CotacaoFornecedor.id.desc()).offset(deslocamento).limit(limite)\n        linhas = self.banco.execute(consulta).all()\n        agora = ServicoCotacao._agora_utc_sem_fuso()\n        alterou = False\n        for cotacao, *_ in linhas:\n            if cotacao.status == "enviada" and agora >= ServicoCotacao._normalizar_data(cotacao.criada_em) + timedelta(days=cotacao.validade_dias):\n                cotacao.status = "expirada"\n                cotacao.encerrada_em = agora\n                cotacao.decidida_por_empresa_id = None\n                alterou = True\n        if alterou:\n            self.banco.commit()\n        itens = [CotacaoFornecedorLeitura(\n            **CotacaoLeitura.model_validate(cotacao).model_dump(),\n            solicitacao=self._solicitacao(item, cliente, processo, material),\n        ) for cotacao, item, cliente, processo, material in linhas]\n        return CotacoesFornecedorLeitura(itens=itens, total=total, deslocamento=deslocamento, limite=limite)\n\n    def validar_envio(self, solicitacao_id: int, empresa_id: int) -> None:\n        self.validar_fornecedor(empresa_id)\n        item = self.banco.get(SolicitacaoServico, solicitacao_id)\n        if item is None:\n            raise HTTPException(404, detail="solicitacao_nao_encontrada")\n        if item.status != "aberta":\n            raise HTTPException(409, detail="solicitacao_nao_esta_aberta")\n        # Compatibilidade, aceite prévio e duplicidade são conferidos pelo\n        # serviço de cotações existente no momento de gravar a proposta.\n\n    def validar_acesso_arquivos(self, solicitacao_id: int, empresa_id: int) -> None:\n        self.validar_fornecedor(empresa_id)\n        if self.banco.get(SolicitacaoServico, solicitacao_id) is None:\n            raise HTTPException(404, detail="solicitacao_nao_encontrada")\n        possui_cotacao = self.banco.scalar(select(CotacaoFornecedor.id).where(\n            CotacaoFornecedor.solicitacao_id == solicitacao_id,\n            CotacaoFornecedor.empresa_fornecedora_id == empresa_id,\n        ).limit(1))\n        compativel = self.banco.scalar(select(SolicitacaoServico.id).where(\n            SolicitacaoServico.id == solicitacao_id, self._compativel(empresa_id),\n        ))\n        if possui_cotacao is None and compativel is None:\n            raise HTTPException(403, detail="fornecedor_sem_acesso_a_solicitacao")\n', 'frontend/src/pages/supplier/SupplierCotacoesPage.css': '.f24-page .c23-alert a { color: inherit; font-weight: 700; }\n.f24-tabs { display: flex; flex-wrap: wrap; gap: 8px; }\n.f24-tab { display: inline-flex; align-items: center; gap: 8px; padding: 12px 16px; border-radius: 8px; border: 1px solid #2d405a; color: #a3b9d5; text-decoration: none; font-size: 13px; font-weight: 700; background: #101b2a; }\n.f24-tab-active, .f24-tab:hover { color: #cbe0ff; border-color: #4772ab; background: #183455; }\n.f24-page .f24-selected { background: #172c45; }\n.f24-pagination { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; border-top: 1px solid #28384d; color: #8aa1bf; font-size: 12px; }\n.f24-pagination > div { display: flex; gap: 8px; }\n.f24-columns { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(300px, 1fr); gap: 20px; align-items: start; }\n.f24-detail, .f24-form-panel { padding: 22px; }\n.f24-section-head { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-bottom: 18px; }\n.f24-section-head h2, .f24-section-head h3 { font-size: 18px; margin: 0; color: #e7eef9; }\n.f24-section-head > svg { color: #6ea5f5; }\n.f24-section-head > span { max-width: 55%; text-align: right; overflow-wrap: anywhere; }\n.f24-files-head { margin-top: 26px; margin-bottom: 12px; }\n.f24-files { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 9px; }\n.f24-files li { display: flex; align-items: center; gap: 11px; padding: 12px; border: 1px solid #2b3d54; border-radius: 8px; background: #0e1826; }\n.f24-files li > svg { color: #71a6f0; flex-shrink: 0; }\n.f24-files li > span { flex: 1; min-width: 0; }\n.f24-files strong { display: block; color: #c2d3ea; font-size: 12px; overflow-wrap: anywhere; }\n.f24-files small { display: block; color: #7991b1; font-size: 11px; margin-top: 5px; }\n.f24-form { margin-top: 20px; }\n.f24-form fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }\n.f24-form label { display: block; font-size: 12px; font-weight: 700; color: #a8bfdb; margin: 0 0 8px; }\n.f24-form input, .f24-form textarea { width: 100%; margin-bottom: 16px; }\n.f24-form textarea { border: 1px solid #33465e; border-radius: 8px; padding: 11px; background: #0c1521; color: #e7eef9; font: inherit; font-size: 13px; line-height: 1.6; resize: vertical; }\n.f24-form textarea:focus-visible, .f24-tab:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.f24-form fieldset:disabled { opacity: .7; }\n.f24-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }\n.f24-form .f24-submit { margin-top: 12px; width: 100%; }\n.f24-review { margin-top: 20px; }\n@media (max-width: 1120px) { .f24-columns { grid-template-columns: minmax(0, 1fr); } }\n@media (max-width: 600px) { .f24-detail, .f24-form-panel { padding: 17px; } .f24-form-grid { grid-template-columns: 1fr; gap: 0; } .f24-tabs { flex-direction: column; } .f24-pagination { flex-wrap: wrap; gap: 14px; } .f24-files li { flex-wrap: wrap; } .f24-files li .c23-button { width: 100%; } .f24-section-head { align-items: flex-start; flex-direction: column; } .f24-section-head > span { max-width: 100%; text-align: left; } }\n', 'frontend/src/pages/supplier/SupplierCotacoesPage.tsx': 'import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";\nimport { Link } from "react-router-dom";\nimport { CheckCircle2, ClipboardList, Download, FileText, RefreshCw, Send, X, XCircle } from "lucide-react";\nimport { useAuth } from "../../auth/AuthContext";\nimport { api } from "../../services/api";\nimport {\n  formatarInstanteCotacao, formatarValorCotacao, instanteUtc,\n  rotuloStatusCotacao, statusCotacao, vencimentoCotacao, type CotacaoCliente,\n} from "../client/cotacoesCliente";\nimport {\n  formatarTamanhoArquivo, mensagemErroFornecedor, validarProposta,\n  type ArquivoFornecedor, type CamposProposta, type CotacaoFornecedor,\n  type DadosProposta, type PaginaFornecedor, type SolicitacaoFornecedor,\n} from "./cotacoesFornecedor";\nimport "../client/ClientCotacoesPage.css";\nimport "./SupplierCotacoesPage.css";\n\ntype Modo = "oportunidades" | "cotacoes";\ntype Linha = { solicitacao: SolicitacaoFornecedor; cotacao?: CotacaoFornecedor };\ntype Grupo = { chave: string; total: number; itens: Linha[] };\ntype Rascunho = CamposProposta & { chave: string };\ntype Revisao = { chave: string; empresaId: number; solicitacao: SolicitacaoFornecedor; dados: DadosProposta };\nconst CAMPOS_VAZIOS: CamposProposta = { valor: "", prazo: "", validade: "10", observacoes: "" };\nconst LIMITE = 20;\n\nexport default function SupplierCotacoesPage({ modo = "oportunidades" }: { modo?: Modo }) {\n  const { user } = useAuth();\n  const empresaId = user?.role === "fornecedor" ? user.id : 0;\n  const [deslocamento, setDeslocamento] = useState(0);\n  const [atualizacao, setAtualizacao] = useState(0);\n  const [grupo, setGrupo] = useState<Grupo | null>(null);\n  const [selecionadoId, setSelecionadoId] = useState(0);\n  const [carregando, setCarregando] = useState(true);\n  const [erroLista, setErroLista] = useState("");\n  const [rascunho, setRascunho] = useState<Rascunho>({ chave: "", ...CAMPOS_VAZIOS });\n  const [erroEnvio, setErroEnvio] = useState("");\n  const [sucesso, setSucesso] = useState<{ empresaId: number; texto: string } | null>(null);\n  const [revisao, setRevisao] = useState<Revisao | null>(null);\n  const [enviando, setEnviando] = useState(false);\n  const [arquivos, setArquivos] = useState<{ chave: string; itens: ArquivoFornecedor[] } | null>(null);\n  const [erroArquivos, setErroArquivos] = useState("");\n  const [carregandoArquivos, setCarregandoArquivos] = useState(false);\n  const [atualizacaoArquivos, setAtualizacaoArquivos] = useState(0);\n  const [baixando, setBaixando] = useState<number | null>(null);\n  const [agora, setAgora] = useState(Date.now);\n  const dialogo = useRef<HTMLDialogElement | null>(null);\n  const travaEnvio = useRef(false);\n  const envio = useRef<AbortController | null>(null);\n  const download = useRef<AbortController | null>(null);\n  const montada = useRef(true);\n  const urls = useRef(new Set<string>());\n  const paginaChave = `${empresaId}:${modo}:${deslocamento}:${atualizacao}`;\n  const grupoAtual = grupo?.chave === paginaChave ? grupo : null;\n  const linhas = useMemo(() => grupoAtual?.itens ?? [], [grupoAtual]);\n  const linha = linhas.find((item) => (item.cotacao?.id ?? item.solicitacao.id) === selecionadoId) ?? linhas[0];\n  const solicitacao = linha?.solicitacao;\n  const cotacao = linha?.cotacao;\n  const selecaoChave = `${empresaId}:${modo}:${solicitacao?.id ?? 0}:${cotacao?.id ?? 0}`;\n  const contexto = useRef({ empresaId, paginaChave, selecaoChave });\n  contexto.current = { empresaId, paginaChave, selecaoChave };\n  const campos = rascunho.chave === selecaoChave ? rascunho : CAMPOS_VAZIOS;\n  const modalAtual = revisao?.chave === selecaoChave && revisao.empresaId === empresaId && grupoAtual ? revisao : null;\n  const arquivosAtuais = arquivos?.chave === selecaoChave ? arquivos.itens : [];\n  const total = grupoAtual?.total ?? 0;\n  const bloquear = carregando || enviando || !grupoAtual;\n\n  useEffect(() => {\n    montada.current = true;\n    const intervalo = window.setInterval(() => setAgora(Date.now()), 30_000);\n    return () => {\n      montada.current = false;\n      window.clearInterval(intervalo);\n      envio.current?.abort();\n      download.current?.abort();\n      for (const url of urls.current) URL.revokeObjectURL(url);\n      urls.current.clear();\n    };\n  }, []);\n\n  useEffect(() => {\n    setDeslocamento(0);\n    setSelecionadoId(0);\n    setErroEnvio("");\n    setRevisao(null);\n    envio.current?.abort();\n  }, [empresaId, modo]);\n\n  useEffect(() => {\n    const controlador = new AbortController();\n    let vigente = true;\n    setCarregando(true);\n    setErroLista("");\n    if (!empresaId) {\n      setErroLista("Entre com um acesso de fornecedor para consultar suas solicitações e propostas.");\n      setCarregando(false);\n      return () => { vigente = false; controlador.abort(); };\n    }\n    async function carregar() {\n      try {\n        const config = { params: { empresa_fornecedora_id: empresaId, deslocamento, limite: LIMITE }, signal: controlador.signal, timeout: 20_000 };\n        let itens: Linha[];\n        let quantidade: number;\n        if (modo === "oportunidades") {\n          const { data } = await api.get<PaginaFornecedor<SolicitacaoFornecedor>>("/portal-fornecedor/oportunidades", config);\n          itens = data.itens.map((item) => ({ solicitacao: item }));\n          quantidade = data.total;\n        } else {\n          const { data } = await api.get<PaginaFornecedor<CotacaoFornecedor>>("/portal-fornecedor/cotacoes", config);\n          itens = data.itens.filter((item) => item.empresa_fornecedora_id === empresaId).map((item) => ({ solicitacao: item.solicitacao, cotacao: item }));\n          quantidade = data.total;\n        }\n        if (!vigente || contexto.current.paginaChave !== paginaChave) return;\n        if (quantidade > 0 && deslocamento >= quantidade) {\n          setDeslocamento(Math.floor((quantidade - 1) / LIMITE) * LIMITE);\n          return;\n        }\n        setGrupo({ chave: paginaChave, total: quantidade, itens });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.paginaChave === paginaChave) setErroLista(mensagemErroFornecedor(erro));\n      } finally {\n        if (vigente && contexto.current.paginaChave === paginaChave) setCarregando(false);\n      }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n  }, [empresaId, modo, deslocamento, paginaChave]);\n\n  useEffect(() => {\n    setErroEnvio("");\n    setRevisao(null);\n    setErroArquivos("");\n    setBaixando(null);\n    download.current?.abort();\n  }, [selecaoChave]);\n\n  useEffect(() => {\n    const controlador = new AbortController();\n    let vigente = true;\n    setCarregandoArquivos(Boolean(solicitacao));\n    setErroArquivos("");\n    if (!solicitacao) return () => { vigente = false; controlador.abort(); };\n    async function carregarArquivos() {\n      try {\n        const { data } = await api.get<ArquivoFornecedor[]>(`/portal-fornecedor/solicitacoes/${solicitacao!.id}/arquivos`, {\n          params: { empresa_fornecedora_id: empresaId }, signal: controlador.signal, timeout: 20_000,\n        });\n        if (vigente && contexto.current.selecaoChave === selecaoChave) setArquivos({ chave: selecaoChave, itens: data.filter((item) => item.ativo && item.solicitacao_id === solicitacao!.id) });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.selecaoChave === selecaoChave) setErroArquivos(mensagemErroFornecedor(erro));\n      } finally {\n        if (vigente && contexto.current.selecaoChave === selecaoChave) setCarregandoArquivos(false);\n      }\n    }\n    void carregarArquivos();\n    return () => { vigente = false; controlador.abort(); };\n  }, [empresaId, selecaoChave, solicitacao?.id, atualizacaoArquivos]);\n\n  useEffect(() => {\n    const elemento = dialogo.current;\n    if (!elemento) return;\n    if (modalAtual && !elemento.open) elemento.showModal();\n    if (!modalAtual && elemento.open) elemento.close();\n  }, [modalAtual]);\n\n  function alterarCampo(nome: keyof CamposProposta, valor: string) {\n    setRascunho({ chave: selecaoChave, ...campos, [nome]: valor });\n    setErroEnvio("");\n  }\n\n  function revisar(evento: FormEvent<HTMLFormElement>) {\n    evento.preventDefault();\n    if (!solicitacao || bloquear || modo !== "oportunidades" || travaEnvio.current) return;\n    const resultado = validarProposta(campos);\n    setErroEnvio(resultado.erro);\n    if (resultado.dados) setRevisao({ chave: selecaoChave, empresaId, solicitacao, dados: resultado.dados });\n  }\n\n  async function confirmarEnvio() {\n    if (!modalAtual || travaEnvio.current || bloquear) return;\n    const confirmado = modalAtual;\n    const chavePaginaEnvio = paginaChave;\n    const controlador = new AbortController();\n    envio.current = controlador;\n    travaEnvio.current = true;\n    setEnviando(true);\n    setErroEnvio("");\n    try {\n      const { data } = await api.post<CotacaoCliente>(`/portal-fornecedor/solicitacoes/${confirmado.solicitacao.id}/cotacoes`, {\n        empresa_fornecedora_id: confirmado.empresaId, ...confirmado.dados,\n      }, { signal: controlador.signal, timeout: 30_000 });\n      if (!montada.current || controlador.signal.aborted || contexto.current.empresaId !== confirmado.empresaId || contexto.current.selecaoChave !== confirmado.chave) return;\n      if (data.solicitacao_id !== confirmado.solicitacao.id || data.empresa_fornecedora_id !== confirmado.empresaId) throw new Error("Resposta divergente da proposta enviada.");\n      setRevisao(null);\n      setRascunho({ chave: "", ...CAMPOS_VAZIOS });\n      setSucesso({ empresaId: confirmado.empresaId, texto: `Cotação #${data.id} enviada para a solicitação #${data.solicitacao_id}. O cliente já pode consultá-la.` });\n      setAtualizacao((valor) => valor + 1);\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.paginaChave === chavePaginaEnvio) {\n        const possuiResposta = typeof erro === "object" && erro !== null && "response" in erro && Boolean((erro as { response?: unknown }).response);\n        setErroEnvio(possuiResposta ? mensagemErroFornecedor(erro) : "O envio não pôde ser confirmado. Consulte Minhas Cotações antes de tentar enviar novamente.");\n        setRevisao(null);\n      }\n    } finally {\n      if (envio.current === controlador) envio.current = null;\n      travaEnvio.current = false;\n      if (montada.current) setEnviando(false);\n    }\n  }\n\n  async function baixarArquivo(arquivo: ArquivoFornecedor) {\n    if (baixando !== null || download.current || arquivo.solicitacao_id !== solicitacao?.id) return;\n    const chave = selecaoChave;\n    const controlador = new AbortController();\n    download.current = controlador;\n    setBaixando(arquivo.id);\n    setErroArquivos("");\n    try {\n      const { data } = await api.get<Blob>(`/portal-fornecedor/arquivos/${arquivo.id}/download`, {\n        params: { empresa_fornecedora_id: empresaId }, responseType: "blob", signal: controlador.signal, timeout: 60_000,\n      });\n      if (!montada.current || controlador.signal.aborted || contexto.current.selecaoChave !== chave) return;\n      const url = URL.createObjectURL(data);\n      urls.current.add(url);\n      const ancora = document.createElement("a");\n      ancora.href = url;\n      ancora.download = arquivo.nome_original;\n      document.body.appendChild(ancora);\n      ancora.click();\n      ancora.remove();\n      window.setTimeout(() => { URL.revokeObjectURL(url); urls.current.delete(url); }, 30_000);\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.selecaoChave === chave) setErroArquivos(mensagemErroFornecedor(erro));\n    } finally {\n      if (download.current === controlador) download.current = null;\n      if (montada.current && contexto.current.selecaoChave === chave) setBaixando(null);\n    }\n  }\n\n  return (\n    <div className="c23-page f24-page">\n      <header className="c23-header">\n        <div><span className="c23-eyebrow"><ClipboardList size={15} /> PORTAL DO FORNECEDOR</span>\n          <h1>{modo === "oportunidades" ? "Solicitações Compatíveis" : "Minhas Cotações"}</h1>\n          <p>{modo === "oportunidades" ? "Consulte os requisitos e envie sua proposta ao cliente." : "Acompanhe suas propostas, prazos e decisões do cliente."}</p></div>\n        <button className="c23-button" disabled={carregando || enviando} onClick={() => setAtualizacao((valor) => valor + 1)}><RefreshCw size={15} className={carregando ? "c23-spin" : ""} /> Atualizar</button>\n      </header>\n      <nav className="f24-tabs" aria-label="Cotações do fornecedor">\n        <Link className={modo === "oportunidades" ? "f24-tab f24-tab-active" : "f24-tab"} to="/fornecedor/solicitacoes"><ClipboardList size={16} /> Solicitações Compatíveis</Link>\n        <Link className={modo === "cotacoes" ? "f24-tab f24-tab-active" : "f24-tab"} to="/fornecedor/cotacoes"><FileText size={16} /> Minhas Cotações</Link>\n      </nav>\n      {sucesso?.empresaId === empresaId && <div className="c23-alert c23-alert-success" role="status"><CheckCircle2 size={18} /><span>{sucesso.texto} <Link to="/fornecedor/cotacoes">Ver minhas cotações</Link></span></div>}\n      {erroEnvio && <div className="c23-alert c23-alert-error" role="alert"><XCircle size={18} /><span>{erroEnvio} <Link to="/fornecedor/cotacoes">Minhas Cotações</Link></span></div>}\n      {erroLista && <div className="c23-alert c23-alert-error" role="alert"><XCircle size={18} />{erroLista}</div>}\n      <section className="c23-panel">\n        <div className="c23-toolbar"><div><h2>{modo === "oportunidades" ? "Oportunidades para sua empresa" : "Propostas enviadas"}</h2><p>{grupoAtual ? `${total} ${modo === "oportunidades" ? "solicitações disponíveis" : "cotações da sua empresa"}` : "Consultando suas informações"}</p></div>\n          <span className="c23-footnote">{modo === "oportunidades" ? "Processo · material · dimensões · tolerância" : "As decisões são atualizadas ao consultar a lista."}</span></div>\n        {carregando ? <div className="c23-empty" role="status"><RefreshCw className="c23-spin" size={26} /><strong>Carregando...</strong></div>\n          : !erroLista && linhas.length === 0 ? <div className="c23-empty"><ClipboardList size={34} /><strong>{modo === "oportunidades" ? "Nenhuma solicitação disponível" : "Sua empresa ainda não enviou cotações"}</strong><p>{modo === "oportunidades" ? "As oportunidades precisam estar abertas e atender aos processos, materiais, dimensões e tolerância cadastrados para sua empresa. Solicitações já cotadas ficam em Minhas Cotações." : "Escolha uma solicitação compatível e envie sua primeira proposta."}</p>{modo === "cotacoes" && <Link className="c23-link" to="/fornecedor/solicitacoes">Consultar solicitações</Link>}</div>\n            : linhas.length > 0 && <>\n              <div className="c23-table-scroll"><table><thead><tr><th>Solicitação / cliente</th><th>Processo / material</th><th>{modo === "oportunidades" ? "Quantidade" : "Valor total"}</th><th>{modo === "oportunidades" ? "Dimensões X × Y × Z" : "Situação"}</th><th><span className="c23-sr">Ações</span></th></tr></thead>\n                <tbody>{linhas.map((item) => {\n                  const s = item.solicitacao;\n                  const c = item.cotacao;\n                  const id = c?.id ?? s.id;\n                  const selecionada = id === (linha?.cotacao?.id ?? linha?.solicitacao.id);\n                  const status = c ? statusCotacao(c, agora) : "";\n                  return <tr key={id} className={selecionada ? "f24-selected" : ""}>\n                    <td><strong>Solicitação #{s.id}{c ? ` · Cotação #${c.id}` : ""}</strong><small>{s.cliente_razao_social}</small></td>\n                    <td><strong>{s.processo_nome}</strong><small>{s.material_nome}</small></td>\n                    <td>{c ? <strong className="c23-price">{formatarValorCotacao(c.valor_total)}</strong> : `${s.quantidade} un.`}</td>\n                    <td>{c ? <span className={`c23-badge ${status === "aceita" ? "c23-status-success" : status === "enviada" ? "c23-status-pending" : "c23-status-closed"}`}>{rotuloStatusCotacao(status)}</span> : <span>{s.dimensao_x_maxima_mm} × {s.dimensao_y_maxima_mm} × {s.dimensao_z_maxima_mm} mm</span>}</td>\n                    <td><button className="c23-button c23-small" aria-pressed={selecionada} disabled={enviando} onClick={() => setSelecionadoId(id)}>{selecionada ? "Selecionada" : "Ver detalhes"}</button></td>\n                  </tr>;\n                })}</tbody></table></div>\n              <div className="f24-pagination"><span>{deslocamento + 1}–{deslocamento + linhas.length} de {total}</span><div><button className="c23-button c23-small" disabled={bloquear || deslocamento === 0} onClick={() => setDeslocamento((valor) => Math.max(0, valor - LIMITE))}>Anterior</button><button className="c23-button c23-small" disabled={bloquear || deslocamento + LIMITE >= total} onClick={() => setDeslocamento((valor) => valor + LIMITE)}>Próxima</button></div></div>\n            </>}\n      </section>\n      {solicitacao && !carregando && !erroLista && <div className="f24-columns">\n        <section className="c23-panel f24-detail"><div className="f24-section-head"><h2>Solicitação #{solicitacao.id}</h2><span className="c23-footnote">{solicitacao.cliente_razao_social}</span></div>\n          <div className="c23-detail-grid"><div><span>Processo</span><strong>{solicitacao.processo_nome}</strong></div><div><span>Material</span><strong>{solicitacao.material_nome}</strong></div>\n            <div><span>Dimensões X × Y × Z (mm)</span><strong>{solicitacao.dimensao_x_maxima_mm} × {solicitacao.dimensao_y_maxima_mm} × {solicitacao.dimensao_z_maxima_mm}</strong></div><div><span>Tolerância requerida (mm)</span><strong>{solicitacao.tolerancia_requerida_mm}</strong></div>\n            <div><span>Quantidade</span><strong>{solicitacao.quantidade} unidades</strong></div><div><span>Solicitada em</span><strong>{formatarInstanteCotacao(instanteUtc(solicitacao.criada_em))}</strong></div></div>\n          <div className="c23-observacoes"><span>Observações do cliente</span><p>{solicitacao.observacoes || "Sem observações."}</p></div>\n          <div className="f24-section-head f24-files-head"><h3>Arquivos técnicos</h3><button className="c23-button c23-small" disabled={carregandoArquivos || baixando !== null} onClick={() => setAtualizacaoArquivos((valor) => valor + 1)} aria-label="Atualizar arquivos técnicos"><RefreshCw size={14} /></button></div>\n          {erroArquivos && <p className="c23-alert c23-alert-error" role="alert">{erroArquivos}</p>}\n          {carregandoArquivos ? <p className="c23-footnote" role="status">Carregando arquivos...</p> : !erroArquivos && (arquivosAtuais.length ? <ul className="f24-files">{arquivosAtuais.map((arquivo) => <li key={arquivo.id}><FileText size={19} /><span><strong>{arquivo.nome_original}</strong><small>{arquivo.extensao.replace(".", "").toUpperCase()} · {formatarTamanhoArquivo(arquivo.tamanho_bytes)}</small></span><button className="c23-button c23-small" disabled={baixando !== null} onClick={() => void baixarArquivo(arquivo)} aria-label={`Baixar ${arquivo.nome_original}`}><Download size={15} />{baixando === arquivo.id ? "Baixando..." : "Baixar"}</button></li>)}</ul> : <p className="c23-footnote">O cliente ainda não vinculou arquivos a esta solicitação.</p>)}\n        </section>\n        {modo === "oportunidades" ? <section className="c23-panel f24-form-panel"><div className="f24-section-head"><h2>Sua proposta</h2><Send size={20} /></div><p className="c23-footnote">Informe o valor total para as {solicitacao.quantidade} unidades solicitadas.</p>\n          <form onSubmit={revisar} className="f24-form"><fieldset disabled={bloquear}>\n            <label htmlFor="f24-valor">Valor total (R$)</label><input id="f24-valor" inputMode="decimal" autoComplete="off" maxLength={24} placeholder="Ex.: 1.250,50" value={campos.valor} onChange={(evento) => alterarCampo("valor", evento.target.value)} required />\n            <div className="f24-form-grid"><div><label htmlFor="f24-prazo">Prazo de execução (dias)</label><input id="f24-prazo" type="number" min={1} max={3650} step={1} value={campos.prazo} onChange={(evento) => alterarCampo("prazo", evento.target.value)} required /></div><div><label htmlFor="f24-validade">Validade da proposta (dias)</label><input id="f24-validade" type="number" min={1} max={3650} step={1} value={campos.validade} onChange={(evento) => alterarCampo("validade", evento.target.value)} required /></div></div>\n            <label htmlFor="f24-observacoes">Observações da proposta</label><textarea id="f24-observacoes" maxLength={5000} rows={5} placeholder="Condições, itens inclusos e informações para o cliente." value={campos.observacoes} onChange={(evento) => alterarCampo("observacoes", evento.target.value)} /><small className="c23-footnote">{campos.observacoes.length}/5000 caracteres</small>\n            <p className="c23-footnote">Após o envio, a proposta fica registrada para esta solicitação. A validade começa no envio.</p>\n            <button className="c23-button c23-primary f24-submit" type="submit"><Send size={16} />{enviando ? "Enviando..." : "Revisar e enviar proposta"}</button>\n          </fieldset></form></section>\n          : cotacao && <section className="c23-panel f24-detail"><div className="f24-section-head"><h2>Cotação #{cotacao.id}</h2><FileText size={20} /></div><div className="c23-detail-grid"><div><span>Valor total</span><strong>{formatarValorCotacao(cotacao.valor_total)}</strong></div><div><span>Situação</span><strong>{rotuloStatusCotacao(statusCotacao(cotacao, agora))}</strong></div><div><span>Prazo de execução</span><strong>{cotacao.prazo_dias} dias</strong></div><div><span>Validade</span><strong>{cotacao.validade_dias} dias</strong></div></div>\n            <div className="c23-observacoes"><span>Observações da proposta</span><p>{cotacao.observacoes || "Sem observações."}</p></div><p className="c23-dates">Enviada em {formatarInstanteCotacao(instanteUtc(cotacao.criada_em))}<br />Validade até {formatarInstanteCotacao(vencimentoCotacao(cotacao))}{cotacao.encerrada_em && <><br />Encerrada em {formatarInstanteCotacao(instanteUtc(cotacao.encerrada_em))}</>}</p></section>}\n      </div>}\n      <dialog ref={dialogo} className="c23-dialog" aria-labelledby="f24-confirmacao" onCancel={(evento) => { evento.preventDefault(); if (!travaEnvio.current) setRevisao(null); }}>\n        {modalAtual && <><div className="c23-dialog-head"><div><span className="c23-eyebrow">REVISÃO DA PROPOSTA</span><h2 id="f24-confirmacao">Enviar cotação ao cliente?</h2></div><button className="c23-icon-button" disabled={enviando} aria-label="Fechar revisão" onClick={() => setRevisao(null)}><X size={22} /></button></div>\n          <p className="c23-footnote">Solicitação #{modalAtual.solicitacao.id} · {modalAtual.solicitacao.cliente_razao_social} · {modalAtual.solicitacao.quantidade} unidades</p><div className="c23-detail-grid f24-review"><div><span>Valor total</span><strong>{formatarValorCotacao(modalAtual.dados.valor_total)}</strong></div><div><span>Prazo de execução</span><strong>{modalAtual.dados.prazo_dias} dias</strong></div><div><span>Validade após o envio</span><strong>{modalAtual.dados.validade_dias} dias</strong></div><div><span>Processo / material</span><strong>{modalAtual.solicitacao.processo_nome} · {modalAtual.solicitacao.material_nome}</strong></div></div>\n          <div className="c23-observacoes"><span>Observações que o cliente receberá</span><p>{modalAtual.dados.observacoes || "Sem observações."}</p></div><p className="c23-footnote f24-review">Ao confirmar, sua proposta será registrada e o cliente poderá aceitá-la ou recusá-la.</p><div className="c23-dialog-actions"><button className="c23-button" disabled={enviando} autoFocus onClick={() => setRevisao(null)}>Voltar ao formulário</button><button className="c23-button c23-primary" disabled={enviando || bloquear} onClick={() => void confirmarEnvio()}><Send size={16} />{enviando ? "Enviando..." : "Confirmar envio"}</button></div></>}\n      </dialog>\n    </div>\n  );\n}\n', 'frontend/src/pages/supplier/cotacoesFornecedor.ts': 'import type { CotacaoCliente } from "../client/cotacoesCliente";\n\nexport type SolicitacaoFornecedor = {\n  id: number;\n  empresa_cliente_id: number;\n  cliente_razao_social: string;\n  processo_id: number;\n  processo_nome: string;\n  material_id: number;\n  material_nome: string;\n  dimensao_x_maxima_mm: string | number;\n  dimensao_y_maxima_mm: string | number;\n  dimensao_z_maxima_mm: string | number;\n  tolerancia_requerida_mm: string | number;\n  quantidade: number;\n  observacoes: string | null;\n  status: string;\n  criada_em: string;\n};\nexport type CotacaoFornecedor = CotacaoCliente & { solicitacao: SolicitacaoFornecedor };\nexport type PaginaFornecedor<T> = { itens: T[]; total: number; deslocamento: number; limite: number };\nexport type ArquivoFornecedor = {\n  id: number; solicitacao_id: number; nome_original: string; extensao: string;\n  tamanho_bytes: number; ativo: boolean;\n};\nexport type CamposProposta = { valor: string; prazo: string; validade: string; observacoes: string };\nexport type DadosProposta = { valor_total: string; prazo_dias: number; validade_dias: number; observacoes: string | null };\n\nexport function normalizarValorProposta(entrada: string): string | null {\n  // Normalização textual: centavos nunca passam por arredondamento em ponto flutuante.\n  const texto = entrada.trim().replace(/^R\\$\\s*/, "");\n  let inteiro: string;\n  let fracao: string;\n  if (/^\\d+(?:,\\d{1,2})?$/.test(texto)) {\n    [inteiro, fracao = ""] = texto.split(",");\n  } else if (/^\\d{1,3}(?:\\.\\d{3})+(?:,\\d{1,2})?$/.test(texto)) {\n    const partes = texto.split(",");\n    inteiro = partes[0].replaceAll(".", "");\n    fracao = partes[1] ?? "";\n  } else if (/^\\d+\\.\\d{1,2}$/.test(texto)) {\n    [inteiro, fracao] = texto.split(".");\n  } else {\n    return null;\n  }\n  inteiro = inteiro.replace(/^0+(?=\\d)/, "");\n  if (inteiro.length > 12) return null;\n  const centavos = fracao.padEnd(2, "0");\n  return inteiro === "0" && centavos === "00" ? null : `${inteiro}.${centavos}`;\n}\n\nexport function validarProposta(campos: CamposProposta): { dados: DadosProposta | null; erro: string } {\n  const valor = normalizarValorProposta(campos.valor);\n  if (valor === null) return { dados: null, erro: "Informe um valor maior que zero, com até 12 dígitos inteiros e 2 casas decimais. Exemplo: 1.250,50." };\n  const prazo = /^\\d+$/.test(campos.prazo.trim()) ? Number(campos.prazo) : NaN;\n  const validade = /^\\d+$/.test(campos.validade.trim()) ? Number(campos.validade) : NaN;\n  if (!Number.isInteger(prazo) || prazo < 1 || prazo > 3650) return { dados: null, erro: "Informe o prazo de execução entre 1 e 3650 dias." };\n  if (!Number.isInteger(validade) || validade < 1 || validade > 3650) return { dados: null, erro: "Informe a validade da proposta entre 1 e 3650 dias." };\n  if (campos.observacoes.length > 5000) return { dados: null, erro: "As observações podem ter até 5000 caracteres." };\n  return { dados: { valor_total: valor, prazo_dias: prazo, validade_dias: validade, observacoes: campos.observacoes.trim() || null }, erro: "" };\n}\n\nexport function mensagemErroFornecedor(erro: unknown): string {\n  if (typeof erro === "object" && erro !== null && "response" in erro) {\n    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;\n    const mensagens: Record<string, string> = {\n      empresa_fornecedora_nao_encontrada: "A empresa do fornecedor não foi encontrada. Confira o cadastro da empresa.",\n      empresa_nao_e_fornecedora: "A empresa deste acesso precisa estar cadastrada como fornecedor ou ambos.",\n      solicitacao_nao_encontrada: "A solicitação não foi encontrada. Atualize a lista.",\n      solicitacao_nao_esta_aberta: "Esta solicitação já foi encerrada. Atualize as oportunidades.",\n      fornecedor_nao_compativel_com_a_solicitacao: "A capacidade da sua empresa não atende a esta solicitação. Confira processo, material, dimensões e tolerância.",\n      cotacao_ja_cadastrada_para_este_fornecedor: "Sua empresa já enviou uma cotação para esta solicitação. Consulte Minhas Cotações.",\n      solicitacao_ja_possui_cotacao_aceita: "O cliente já aceitou uma cotação para esta solicitação.",\n      fornecedor_sem_acesso_a_solicitacao: "Sua empresa não possui acesso aos arquivos desta solicitação.",\n      arquivo_tecnico_nao_encontrado: "O arquivo não está mais disponível. Atualize os arquivos.",\n    };\n    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";\n    if (Array.isArray(detalhe)) return "Os dados não foram aceitos. Confira valor, prazo, validade e observações.";\n  }\n  return "Não foi possível confirmar a operação. Confira a conexão e atualize a tela.";\n}\n\nexport function formatarTamanhoArquivo(bytes: number): string {\n  if (!Number.isFinite(bytes) || bytes < 0) return "Tamanho indisponível";\n  if (bytes < 1024) return `${bytes} B`;\n  const unidade = bytes >= 1024 * 1024 ? "MB" : "KB";\n  const valor = bytes / (unidade === "MB" ? 1024 * 1024 : 1024);\n  return `${valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${unidade}`;\n}\n', 'tests/test_portal_fornecedor_cotacoes.py': 'from __future__ import annotations\n\nfrom datetime import datetime, timedelta, timezone\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi import FastAPI\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine, event, select\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos\nfrom backend.app.api.rotas.cotacoes import roteador as cotacoes\nfrom backend.app.api.rotas.portal_fornecedor import roteador as portal\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.capacidade import CapacidadeFornecedor\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.material_fornecedor import MaterialFornecedor\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.repositories.compatibilidade import RepositorioCompatibilidade\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\n\nBASE = "/api/v1/portal-fornecedor"\n\n\n@pytest.fixture()\ndef ambiente(tmp_path, monkeypatch):\n    # Aplicação sem lifespan: os testes usam somente SQLite e arquivos temporários.\n    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)\n\n    @event.listens_for(engine, "connect")\n    def ativar_chaves_estrangeiras(conexao, _):\n        conexao.execute("PRAGMA foreign_keys=ON")\n\n    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)\n    Base.metadata.create_all(engine)\n    monkeypatch.setattr(ServicoArquivoTecnico, "STORAGE_ROOT", tmp_path)\n    with sessoes() as banco:\n        banco.add_all([\n            Empresa(id=1, razao_social="Cliente Teste", documento="cliente-1", tipo_empresa="cliente"),\n            Empresa(id=2, razao_social="Fornecedor Teste", documento="fornecedor-2", tipo_empresa="fornecedor"),\n            Empresa(id=3, razao_social="Concorrente Teste", documento="fornecedor-3", tipo_empresa="ambos"),\n            Empresa(id=4, razao_social="Fornecedor sem capacidade", documento="fornecedor-4", tipo_empresa="fornecedor"),\n            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-5", tipo_empresa="cliente"),\n            ProcessoFabricacao(id=1, codigo="cnc", nome="Usinagem CNC"),\n            ProcessoFabricacao(id=2, codigo="torno", nome="Torneamento"),\n            Material(id=1, codigo="al6061", nome="Alumínio 6061"),\n            Material(id=2, codigo="aco1045", nome="Aço 1045"),\n        ])\n        banco.commit()\n        for empresa in (2, 3):\n            banco.add(CapacidadeFornecedor(empresa_id=empresa, processo_id=1,\n                dimensao_x_maxima_mm=Decimal("800"), dimensao_y_maxima_mm=Decimal("500"),\n                dimensao_z_maxima_mm=Decimal("450"), tolerancia_minima_mm=Decimal("0.0200")))\n            banco.add(MaterialFornecedor(empresa_id=empresa, material_id=1))\n        banco.add(SolicitacaoServico(id=1, empresa_cliente_id=1, processo_id=1, material_id=1,\n            dimensao_x_maxima_mm=Decimal("800"), dimensao_y_maxima_mm=Decimal("500"),\n            dimensao_z_maxima_mm=Decimal("450"), tolerancia_requerida_mm=Decimal("0.0200"),\n            quantidade=10, observacoes="Peça de teste."))\n        banco.commit()\n\n    def banco_teste():\n        with sessoes() as banco:\n            yield banco\n\n    app = FastAPI()\n    for roteador in (arquivos, cotacoes, portal):\n        app.include_router(roteador, prefix="/api/v1")\n    app.dependency_overrides[obter_banco] = banco_teste\n    try:\n        with TestClient(app) as cliente:\n            yield cliente, sessoes\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(engine)\n        engine.dispose()\n\n\ndef listar(cliente, recurso="oportunidades", empresa=2, **pagina):\n    return cliente.get(BASE + "/" + recurso, params={"empresa_fornecedora_id": empresa, **pagina})\n\n\ndef enviar(cliente, empresa=2, solicitacao=1, **campos):\n    return cliente.post(f"{BASE}/solicitacoes/{solicitacao}/cotacoes", json={\n        "empresa_fornecedora_id": empresa, "valor_total": "1250.50", "prazo_dias": 15,\n        "validade_dias": 10, "observacoes": "Proposta de teste.", **campos,\n    })\n\n\ndef test_oportunidade_com_limites_iguais_traz_cliente_e_catalogos(ambiente):\n    cliente, _ = ambiente\n    resposta = listar(cliente)\n    assert resposta.status_code == 200\n    pagina = resposta.json()\n    assert pagina["total"] == 1\n    item = pagina["itens"][0]\n    assert item["id"] == 1 and item["quantidade"] == 10\n    assert item["cliente_razao_social"] == "Cliente Teste"\n    assert item["processo_nome"] == "Usinagem CNC"\n    assert item["material_nome"] == "Alumínio 6061"\n\n\n@pytest.mark.parametrize("campo,valor", [\n    ("dimensao_x_maxima_mm", "800.001"), ("dimensao_y_maxima_mm", "500.001"),\n    ("dimensao_z_maxima_mm", "450.001"), ("tolerancia_requerida_mm", "0.0199"),\n    ("processo_id", 2), ("material_id", 2),\n])\ndef test_oportunidades_seguem_compatibilidade_e_envio_rejeita_incompativel(ambiente, campo, valor):\n    cliente, sessoes = ambiente\n    with sessoes() as banco:\n        solicitacao = banco.get(SolicitacaoServico, 1)\n        setattr(solicitacao, campo, valor if campo.endswith("_id") else Decimal(valor))\n        banco.commit()\n        assert all(empresa.id != 2 for empresa, _ in RepositorioCompatibilidade(banco).listar_fornecedores_compativeis(solicitacao))\n    assert listar(cliente).json()["total"] == 0\n    resposta = enviar(cliente)\n    assert resposta.status_code == 409\n    assert resposta.json()["detail"] == "fornecedor_nao_compativel_com_a_solicitacao"\n\n\n@pytest.mark.parametrize("status", ["encerrada", "cancelada"])\ndef test_solicitacao_encerrada_sai_das_oportunidades_e_nao_recebe_proposta(ambiente, status):\n    cliente, sessoes = ambiente\n    with sessoes() as banco:\n        banco.get(SolicitacaoServico, 1).status = status\n        banco.commit()\n    assert listar(cliente).json()["total"] == 0\n    resposta = enviar(cliente)\n    assert resposta.status_code == 409 and resposta.json()["detail"] == "solicitacao_nao_esta_aberta"\n\n\ndef test_envio_aparece_no_cliente_impede_duplicidade_e_preserva_dados(ambiente):\n    cliente, sessoes = ambiente\n    criada = enviar(cliente)\n    assert criada.status_code == 201\n    item = criada.json()\n    assert item["valor_total"] == "1250.50" and item["status"] == "enviada"\n    assert item["observacoes"] == "Proposta de teste."\n    assert listar(cliente).json()["total"] == 0\n    repetida = enviar(cliente)\n    assert repetida.status_code == 409\n    assert repetida.json()["detail"] == "cotacao_ja_cadastrada_para_este_fornecedor"\n    recebidas = cliente.get("/api/v1/solicitacoes-servico/1/cotacoes").json()\n    assert [cotacao["id"] for cotacao in recebidas] == [item["id"]]\n    minhas = listar(cliente, "cotacoes").json()\n    assert minhas["total"] == 1\n    assert minhas["itens"][0]["solicitacao"]["cliente_razao_social"] == "Cliente Teste"\n    with sessoes() as banco:\n        assert len(banco.scalars(select(CotacaoFornecedor)).all()) == 1\n\n\ndef test_fornecedor_recebe_so_proprias_propostas_e_cliente_decide(ambiente):\n    cliente, _ = ambiente\n    a = enviar(cliente).json()\n    b = enviar(cliente, empresa=3).json()\n    assert [item["id"] for item in listar(cliente, "cotacoes").json()["itens"]] == [a["id"]]\n    assert [item["id"] for item in listar(cliente, "cotacoes", empresa=3).json()["itens"]] == [b["id"]]\n    caminho = f\'/api/v1/solicitacoes-servico/1/cotacoes/{a["id"]}/aceitar\'\n    assert cliente.post(caminho, json={"empresa_cliente_id": 5}).status_code == 403\n    aceita = cliente.post(caminho, json={"empresa_cliente_id": 1})\n    assert aceita.status_code == 200 and aceita.json()["status"] == "aceita"\n    assert listar(cliente, "cotacoes", empresa=3).json()["itens"][0]["status"] == "recusada"\n    assert listar(cliente, empresa=3).json()["total"] == 0\n\n\ndef test_aceite_por_outro_fornecedor_bloqueia_oportunidade_e_novo_envio(ambiente):\n    cliente, _ = ambiente\n    cotacao = enviar(cliente, empresa=3).json()\n    assert cliente.post(f\'/api/v1/solicitacoes-servico/1/cotacoes/{cotacao["id"]}/aceitar\', json={"empresa_cliente_id": 1}).status_code == 200\n    assert listar(cliente).json()["total"] == 0\n    resposta = enviar(cliente)\n    assert resposta.status_code == 409 and resposta.json()["detail"] == "solicitacao_ja_possui_cotacao_aceita"\n\n\ndef test_validade_utc_e_historico_sem_reenvio(ambiente):\n    cliente, sessoes = ambiente\n    cotacao = enviar(cliente, validade_dias=1).json()\n    with sessoes() as banco:\n        banco.get(CotacaoFornecedor, cotacao["id"]).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)\n        banco.commit()\n    item = listar(cliente, "cotacoes").json()["itens"][0]\n    assert item["status"] == "expirada" and item["encerrada_em"] is not None\n    assert item["decidida_por_empresa_id"] is None\n    assert listar(cliente).json()["total"] == 0\n    assert enviar(cliente).status_code == 409\n\n\n@pytest.mark.parametrize("empresa,codigo", [(1, 409), (999, 404)])\ndef test_empresa_cliente_ou_inexistente_nao_opera_portal(ambiente, empresa, codigo):\n    cliente, _ = ambiente\n    assert listar(cliente, empresa=empresa).status_code == codigo\n    assert listar(cliente, "cotacoes", empresa=empresa).status_code == codigo\n    assert enviar(cliente, empresa=empresa).status_code == codigo\n\n\ndef test_paginacao_nao_repete_itens_e_valida_limites(ambiente):\n    cliente, sessoes = ambiente\n    with sessoes() as banco:\n        original = banco.get(SolicitacaoServico, 1)\n        dados = {campo: getattr(original, campo) for campo in (\n            "empresa_cliente_id", "processo_id", "material_id", "dimensao_x_maxima_mm",\n            "dimensao_y_maxima_mm", "dimensao_z_maxima_mm", "tolerancia_requerida_mm", "quantidade",\n        )}\n        banco.add_all([SolicitacaoServico(**dados), SolicitacaoServico(**dados)])\n        banco.commit()\n    paginas = [listar(cliente, deslocamento=n, limite=1).json() for n in range(3)]\n    assert all(pagina["total"] == 3 for pagina in paginas)\n    assert [p["itens"][0]["id"] for p in paginas] == [3, 2, 1]\n    assert listar(cliente, deslocamento=-1).status_code == 422\n    assert listar(cliente, limite=101).status_code == 422\n    assert listar(cliente, empresa=0).status_code == 422\n\n\n@pytest.mark.parametrize("extensao,conteudo", [("ZIP", b"PK\\x03\\x04arquivo zip"), ("rar", b"Rar!\\x1a\\x07\\x00arquivo rar")])\ndef test_arquivos_zip_rar_acesso_download_e_desvinculo(ambiente, extensao, conteudo):\n    cliente, sessoes = ambiente\n    upload = cliente.post("/api/v1/solicitacoes-servico/1/arquivos-tecnicos", files={"file": ("pecas." + extensao, conteudo, "application/octet-stream")})\n    assert upload.status_code == 201\n    arquivo = upload.json()\n    caminho = BASE + "/solicitacoes/1/arquivos"\n    assert cliente.get(caminho, params={"empresa_fornecedora_id": 4}).status_code == 403\n    itens = cliente.get(caminho, params={"empresa_fornecedora_id": 2}).json()\n    assert itens[0]["id"] == arquivo["id"]\n    download = BASE + f\'/arquivos/{arquivo["id"]}/download\'\n    assert cliente.get(download, params={"empresa_fornecedora_id": 4}).status_code == 403\n    baixado = cliente.get(download, params={"empresa_fornecedora_id": 2})\n    assert baixado.status_code == 200 and baixado.content == conteudo\n    assert "attachment" in baixado.headers["content-disposition"]\n    assert enviar(cliente).status_code == 201\n    with sessoes() as banco:\n        banco.get(CapacidadeFornecedor, 1).dimensao_x_maxima_mm = Decimal("1")\n        banco.commit()\n    # Histórico da própria proposta continua acessível após mudança de capacidade.\n    assert cliente.get(download, params={"empresa_fornecedora_id": 2}).status_code == 200\n    assert cliente.delete(f\'/api/v1/arquivos-tecnicos/{arquivo["id"]}\').status_code == 204\n    assert cliente.get(caminho, params={"empresa_fornecedora_id": 2}).json() == []\n    assert cliente.get(download, params={"empresa_fornecedora_id": 2}).status_code == 404\n\n\n@pytest.mark.parametrize("campos", [\n    {"valor_total": "0"}, {"valor_total": "10.123"}, {"prazo_dias": 0},\n    {"validade_dias": 3651}, {"observacoes": "x" * 5001},\n])\ndef test_proposta_invalida_nao_grava(ambiente, campos):\n    cliente, _ = ambiente\n    assert enviar(cliente, **campos).status_code == 422\n    assert listar(cliente, "cotacoes").json()["total"] == 0\n'}
ALVOS = (APP_REL, ROUTER_REL, *(Path(nome) for nome in FONTES))
IMPORT_LINE = 'import SupplierCotacoesPage from "./pages/supplier/SupplierCotacoesPage";'


VALIDACAO_FORNECEDOR = r'''
from collections import Counter
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

def campos(valor, esperados):
    ausentes = set(esperados) - set(schema(valor).get("properties", {}))
    if ausentes:
        raise RuntimeError("Campos ausentes no portal do fornecedor: " + ", ".join(sorted(ausentes)))

base = "/api/v1/portal-fornecedor"
for recurso in ("/oportunidades", "/cotacoes", "/solicitacoes/{solicitacao_id}/arquivos", "/arquivos/{arquivo_id}/download"):
    op = paths.get(base + recurso, {}).get("get")
    if not op:
        raise RuntimeError("Rota do fornecedor ausente: " + recurso)
    params = {item["name"]: item for item in op.get("parameters", [])}
    empresa = params.get("empresa_fornecedora_id", {})
    if empresa.get("in") != "query" or not empresa.get("required"):
        raise RuntimeError("Consulta do fornecedor sem empresa obrigatória.")
    if recurso in ("/oportunidades", "/cotacoes"):
        if not {"deslocamento", "limite"}.issubset(params):
            raise RuntimeError("A paginação do fornecedor está incompleta.")
        pagina = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
        campos(pagina, ("itens", "total", "deslocamento", "limite"))
        lista = schema(pagina["properties"]["itens"])
        item = schema(lista["items"])
        if recurso == "/cotacoes":
            campos(item, ("id", "empresa_fornecedora_id", "valor_total", "status", "solicitacao"))
            item = schema(item["properties"]["solicitacao"])
        campos(item, ("id", "cliente_razao_social", "processo_nome", "material_nome", "quantidade", "tolerancia_requerida_mm"))
op = paths.get(base + "/solicitacoes/{solicitacao_id}/cotacoes", {}).get("post")
if not op:
    raise RuntimeError("A rota de envio do fornecedor não está registrada.")
dados = schema(op["requestBody"]["content"]["application/json"]["schema"])
campos(dados, ("empresa_fornecedora_id", "valor_total", "prazo_dias", "validade_dias", "observacoes"))
campos(schema(op["responses"]["201"]["content"]["application/json"]["schema"]), ("id", "solicitacao_id", "empresa_fornecedora_id", "status"))
print("CONSULTAS_FORNECEDOR_PAGINADAS_OK=True")
print("ENVIO_FORNECEDOR_CONTRATO_D7_OK=True")
print("ACESSO_ARQUIVOS_FORNECEDOR_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/api/roteador.py",
        "backend/app/api/rotas/cotacoes.py", "backend/app/api/rotas/arquivos_tecnicos.py",
        "backend/app/services/cotacao.py", "backend/app/services/arquivo_tecnico.py",
        "backend/app/models/capacidade.py", "backend/app/models/material_fornecedor.py",
        "frontend/src/App.tsx", "frontend/package.json", "frontend/src/auth/AuthContext.tsx",
        "frontend/src/services/api.ts", "frontend/src/pages/client/ClientArquivosTecnicosPage.tsx",
        "frontend/src/pages/client/ClientCotacoesPage.tsx", "frontend/src/pages/client/ClientCotacoesPage.css",
        "frontend/src/pages/client/cotacoesCliente.ts", "tests/test_cotacoes.py",
    )
    if not all((raiz / nome).is_file() for nome in obrigatorios):
        raise RuntimeError("Execute este script na raiz do MEC-Servicos com os módulos D22 e D23 instalados.")
    return raiz


def validar_fontes_existentes(originais: dict[Path, bytes | None]) -> None:
    for nome, fonte in FONTES.items():
        if nome.endswith(".py"):
            ast.parse(fonte, filename=nome)
        anterior = originais[Path(nome)]
        if anterior is not None:
            texto = anterior.decode("utf-8-sig").replace("\r\n", "\n").rstrip()
            if texto != fonte.replace("\r\n", "\n").rstrip():
                raise RuntimeError("Já existe um arquivo diferente no destino D24. Ele foi preservado: " + nome)


def atualizar_roteador(texto: str) -> str:
    arvore = ast.parse(texto)
    modulo = "backend.app.api.rotas.portal_fornecedor"
    alias = "roteador_portal_fornecedor"
    importacoes = [n for n in arvore.body if isinstance(n, ast.ImportFrom) and n.module == modulo]
    for n in importacoes:
        if len(n.names) != 1 or n.names[0].name != "roteador" or n.names[0].asname != alias:
            raise RuntimeError("O import do portal do fornecedor já usa outro formato. O roteador foi preservado.")
    if len(importacoes) > 1:
        raise RuntimeError("Há imports duplicados do portal do fornecedor.")
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "roteador_api" and n.func.attr == "include_router"
                and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == alias]
    if len(chamadas) > 1 or any(n.keywords or len(n.args) != 1 for n in chamadas):
        raise RuntimeError("O registro do portal do fornecedor já usa outro formato.")
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
    grupos = [item for item in rotas if item["path"] == "/fornecedor" and not item["auto_fecha"]]
    if len(grupos) != 1:
        raise RuntimeError("Não encontrei um único grupo /fornecedor em App.tsx. Nenhum fonte foi alterado.")
    grupo = grupos[0]
    trocas = []
    for caminho, modo in (("solicitacoes", "oportunidades"), ("cotacoes", "cotacoes")):
        candidatas = [item for item in rotas if grupo["fim_abertura"] <= item["inicio"] < item["fim"] <= grupo["fim"] and item["path"] == caminho]
        if len(candidatas) != 1 or not candidatas[0]["auto_fecha"]:
            raise RuntimeError("Não encontrei uma única rota fornecedor " + caminho + " sem subrotas.")
        rota = candidatas[0]
        abertura = texto[rota["inicio"]:rota["fim"]]
        novo = f'<SupplierCotacoesPage modo="{modo}" />'
        componentes = list(re.finditer(r"<(?:ModulePage|SupplierCotacoesPage)\b", abertura))
        if len(componentes) != 1:
            raise RuntimeError("A rota fornecedor " + caminho + " já usa uma tela diferente. Ela foi preservada.")
        inicio = rota["inicio"] + componentes[0].start()
        fim = fim_tag(texto, inicio)
        if not texto[inicio:fim].rstrip().endswith("/>"):
            raise RuntimeError("O componente da rota " + caminho + " possui filhos. Ele foi preservado.")
        if texto[inicio:fim] != novo:
            trocas.append((inicio, fim, novo))
    atualizado = texto
    for inicio, fim, novo in sorted(trocas, reverse=True):
        atualizado = atualizado[:inicio] + novo + atualizado[fim:]
    existente = re.search(r'''import\s+SupplierCotacoesPage\s+from\s*["']\./pages/supplier/SupplierCotacoesPage["']\s*;?''', atualizado)
    if not existente:
        if "./pages/supplier/SupplierCotacoesPage" in atualizado:
            raise RuntimeError("O import da tela do fornecedor usa outro formato. Nenhum fonte foi alterado.")
        quebra = "\r\n" if "\r\n" in atualizado else "\n"
        atualizado = IMPORT_LINE + quebra + atualizado
    return atualizado

VALIDACAO_CONTRATO = '\nfrom backend.app.principal import app\n\ndocumento = app.openapi()\npaths = documento.get("paths", {})\n\ndef schema(valor):\n    vistos = set()\n    while "$ref" in valor:\n        referencia = valor["$ref"]\n        if referencia in vistos or not referencia.startswith("#/"):\n            raise RuntimeError("Referência OpenAPI inesperada.")\n        vistos.add(referencia)\n        valor = documento\n        for parte in referencia[2:].split("/"):\n            valor = valor[parte.replace("~1", "/").replace("~0", "~")]\n    return valor\n\ndef operacao(caminho, metodo):\n    valor = paths.get(caminho, {}).get(metodo)\n    if not isinstance(valor, dict):\n        raise RuntimeError(f"Contrato ausente: {metodo.upper()} {caminho}")\n    return valor\n\ndef resposta(op):\n    return schema(op["responses"]["200"]["content"]["application/json"]["schema"])\n\ndef campos(valor, esperados, nome):\n    propriedades = schema(valor).get("properties", {})\n    ausentes = set(esperados) - set(propriedades)\n    if ausentes:\n        raise RuntimeError(nome + ": faltam " + ", ".join(sorted(ausentes)))\n\nbase = "/api/v1/solicitacoes-servico"\nsolicitacoes = operacao(base, "get")\nparametros = {p.get("name"): p for p in solicitacoes.get("parameters", [])}\nif parametros.get("empresa_cliente_id", {}).get("in") != "query":\n    raise RuntimeError("Listagem de solicitações sem filtro por empresa cliente.")\nlista = resposta(solicitacoes)\nif lista.get("type") != "array":\n    raise RuntimeError("A listagem de solicitações não retorna uma lista.")\ncampos(lista["items"], ("id", "empresa_cliente_id", "quantidade", "dimensao_x_maxima_mm", "dimensao_y_maxima_mm", "dimensao_z_maxima_mm", "status"), "Solicitação")\n\ncotacoes = operacao(base + "/{solicitacao_id}/cotacoes", "get")\nlista = resposta(cotacoes)\nif lista.get("type") != "array":\n    raise RuntimeError("A listagem de cotações não retorna uma lista.")\nesperados = ("id", "solicitacao_id", "empresa_fornecedora_id", "valor_total", "prazo_dias", "validade_dias", "observacoes", "status", "criada_em", "encerrada_em", "decidida_por_empresa_id")\ncampos(lista["items"], esperados, "Cotação")\nfor acao in ("aceitar", "recusar"):\n    op = operacao(base + "/{solicitacao_id}/cotacoes/{cotacao_id}/" + acao, "post")\n    dados = schema(op["requestBody"]["content"]["application/json"]["schema"])\n    if set(dados.get("required", [])) != {"empresa_cliente_id"}:\n        raise RuntimeError("O corpo da decisão difere do contrato D7.")\n    campos(dados, ("empresa_cliente_id",), "Decisão")\n    campos(resposta(op), esperados, "Resposta da decisão")\nfornecedor = operacao("/api/v1/empresas/{empresa_id}", "get")\ncampos(resposta(fornecedor), ("id", "razao_social"), "Fornecedor")\nprint("LISTAGEM_SOLICITACOES_CLIENTE_OK=True")\nprint("LISTAGEM_COTACOES_POR_SOLICITACAO_OK=True")\nprint("ACEITE_RECUSA_EMPRESA_CLIENTE_OK=True")\nprint("NOMES_FORNECEDORES_OK=True")\nprint("CONTRATO_COTACOES_OK=True")\n\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\nfrom backend.app.models.capacidade import CapacidadeFornecedor\nfrom backend.app.models.material_fornecedor import MaterialFornecedor\nop = operacao(base + "/{solicitacao_id}/cotacoes", "post")\ndados = schema(op["requestBody"]["content"]["application/json"]["schema"])\ncampos(dados, ("empresa_fornecedora_id", "valor_total", "prazo_dias", "validade_dias", "observacoes"), "Envio de cotação")\nif set(dados.get("required", [])) != {"empresa_fornecedora_id", "valor_total", "prazo_dias", "validade_dias"}:\n    raise RuntimeError("O corpo da proposta difere do contrato D7.")\ncampos(schema(op["responses"]["201"]["content"]["application/json"]["schema"]), esperados, "Resposta do envio")\nfor recurso in ("/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos", "/arquivos-tecnicos/{arquivo_id}/download"):\n    operacao("/api/v1" + recurso, "get")\nif not {".zip", ".rar"}.issubset(ServicoArquivoTecnico.ALLOWED_EXTENSIONS):\n    raise RuntimeError("O suporte a ZIP/RAR do D22 ainda não está instalado.")\nfor atributo in ("empresa_id", "processo_id", "dimensao_x_maxima_mm", "dimensao_y_maxima_mm", "dimensao_z_maxima_mm", "tolerancia_minima_mm"):\n    if not hasattr(CapacidadeFornecedor, atributo):\n        raise RuntimeError("Capacidade técnica sem o campo " + atributo)\nif not hasattr(MaterialFornecedor, "material_id") or not hasattr(MaterialFornecedor, "empresa_id"):\n    raise RuntimeError("Vínculo de materiais do fornecedor incompatível.")\nprint("ENVIO_COTACAO_E_ARQUIVOS_ZIP_RAR_OK=True")\n'

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
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d24_", delete=False) as arquivo:
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
        "MEC-Serviços D24 — Portal do Fornecedor / Envio de Cotações",
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
    print("MEC-Serviços D24 — Portal do Fornecedor / Envio de Cotações", flush=True)
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
        backup = raiz / "_mec_backups" / ("D24_COTACOES_FORNECEDOR_" + carimbo)
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
        executar_etapa("contrato fornecedor", [sys.executable, "-c", VALIDACAO_FORNECEDOR], raiz, relatorio)
        print("FORNECEDOR_TELA_ROTAS_E_BACKEND_OK=True", flush=True)
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
    print("Reinicie o backend e atualize /fornecedor/solicitacoes com Ctrl+F5.", flush=True)
    print("Entre como fornecedor, selecione uma solicitação compatível e envie uma cotação de teste.", flush=True)
    print("Confira /fornecedor/cotacoes e /cliente/cotacoes para a mesma solicitação.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
