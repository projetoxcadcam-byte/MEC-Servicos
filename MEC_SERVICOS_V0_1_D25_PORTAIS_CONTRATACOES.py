r"""MEC-Serviços D25 — Contratações nos portais do cliente e fornecedor.

Na raiz do MEC-Servicos, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D25_PORTAIS_CONTRATACOES.py

Requer D8, D22, D23 e D24. Cria páginas de consulta e contratação de uma
cotação aceita usando o serviço D8. Não cria registros de demonstração
nem instala dependências. Preserva as telas anteriores e o login atual.
Faz backup, valida os contratos, executa a suíte MEC e npm run build.
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

REVISION = "MEC-SERVICOS-V0.1-D25-PORTAIS-CONTRATACOES-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D25_PORTAIS_CONTRATACOES_RELATORIO"
APP_REL = Path("frontend/src/App.tsx")
ROUTER_REL = Path("backend/app/api/roteador.py")
DIST_REL = Path("frontend/dist")
FONTES = {'backend/app/schemas/portal_contratacoes.py': 'from __future__ import annotations\n\nfrom pydantic import BaseModel\n\nfrom backend.app.schemas.contratacao import ContratacaoLeitura\nfrom backend.app.schemas.cotacao import CotacaoLeitura\nfrom backend.app.schemas.solicitacao import SolicitacaoServicoLeitura\n\n\nclass SolicitacaoContratacaoLeitura(SolicitacaoServicoLeitura):\n    cliente_razao_social: str\n    processo_nome: str\n    material_nome: str\n\n\nclass CotacaoParaContratarLeitura(CotacaoLeitura):\n    fornecedor_razao_social: str\n    solicitacao: SolicitacaoContratacaoLeitura\n\n\nclass ContratacaoPortalLeitura(ContratacaoLeitura):\n    cliente_razao_social: str\n    fornecedor_razao_social: str\n    solicitacao: SolicitacaoContratacaoLeitura\n\n\nclass CotacoesParaContratarPagina(BaseModel):\n    itens: list[CotacaoParaContratarLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n\n\nclass ContratacoesPortalPagina(BaseModel):\n    itens: list[ContratacaoPortalLeitura]\n    total: int\n    deslocamento: int\n    limite: int\n', 'backend/app/services/portal_contratacoes.py': 'from __future__ import annotations\n\nfrom typing import Literal\n\nfrom fastapi import HTTPException\nfrom sqlalchemy import func, select\nfrom sqlalchemy.orm import Session, aliased\n\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.schemas.contratacao import ContratacaoLeitura\nfrom backend.app.schemas.cotacao import CotacaoLeitura\nfrom backend.app.schemas.portal_contratacoes import (\n    ContratacaoPortalLeitura, ContratacoesPortalPagina,\n    CotacaoParaContratarLeitura, CotacoesParaContratarPagina,\n    SolicitacaoContratacaoLeitura,\n)\nfrom backend.app.schemas.solicitacao import SolicitacaoServicoLeitura\n\nPerfil = Literal["cliente", "fornecedor"]\n\n\nclass ServicoPortalContratacoes:\n    def __init__(self, banco: Session) -> None:\n        self.banco = banco\n\n    def validar_empresa(self, empresa_id: int, perfil: Perfil) -> Empresa:\n        empresa = self.banco.get(Empresa, empresa_id)\n        if empresa is None:\n            raise HTTPException(404, detail=f"empresa_{perfil}_nao_encontrada")\n        if empresa.tipo_empresa not in {perfil, "ambos"}:\n            raise HTTPException(403, detail=f"empresa_nao_e_{perfil}")\n        return empresa\n\n    @staticmethod\n    def _solicitacao(item, cliente: str, processo: str, material: str) -> SolicitacaoContratacaoLeitura:\n        return SolicitacaoContratacaoLeitura(\n            **SolicitacaoServicoLeitura.model_validate(item).model_dump(),\n            cliente_razao_social=cliente, processo_nome=processo, material_nome=material,\n        )\n\n    @staticmethod\n    def _consulta_contratacoes():\n        cliente, fornecedor = aliased(Empresa), aliased(Empresa)\n        return (\n            select(ContratacaoServico, SolicitacaoServico, cliente.razao_social,\n                   fornecedor.razao_social, ProcessoFabricacao.nome, Material.nome)\n            .join(SolicitacaoServico, SolicitacaoServico.id == ContratacaoServico.solicitacao_id)\n            .join(cliente, cliente.id == ContratacaoServico.empresa_cliente_id)\n            .join(fornecedor, fornecedor.id == ContratacaoServico.empresa_fornecedora_id)\n            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)\n            .join(Material, Material.id == SolicitacaoServico.material_id)\n        )\n\n    @classmethod\n    def _contratacao(cls, linha) -> ContratacaoPortalLeitura:\n        contrato, solicitacao, cliente, fornecedor, processo, material = linha\n        return ContratacaoPortalLeitura(\n            **ContratacaoLeitura.model_validate(contrato).model_dump(),\n            cliente_razao_social=cliente, fornecedor_razao_social=fornecedor,\n            solicitacao=cls._solicitacao(solicitacao, cliente, processo, material),\n        )\n\n    @staticmethod\n    def _dono(empresa_id: int, perfil: Perfil):\n        coluna = (ContratacaoServico.empresa_cliente_id if perfil == "cliente"\n                  else ContratacaoServico.empresa_fornecedora_id)\n        return coluna == empresa_id\n\n    def listar_contratacoes(self, empresa_id: int, perfil: Perfil, deslocamento: int, limite: int) -> ContratacoesPortalPagina:\n        self.validar_empresa(empresa_id, perfil)\n        consulta = self._consulta_contratacoes().where(self._dono(empresa_id, perfil))\n        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0\n        linhas = self.banco.execute(consulta.order_by(ContratacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()\n        return ContratacoesPortalPagina(\n            itens=[self._contratacao(linha) for linha in linhas], total=total,\n            deslocamento=deslocamento, limite=limite,\n        )\n\n    def obter_contratacao(self, contratacao_id: int, empresa_id: int, perfil: Perfil) -> ContratacaoPortalLeitura:\n        self.validar_empresa(empresa_id, perfil)\n        consulta = self._consulta_contratacoes().where(\n            ContratacaoServico.id == contratacao_id, self._dono(empresa_id, perfil),\n        )\n        linha = self.banco.execute(consulta).first()\n        if linha is None:\n            raise HTTPException(404, detail="contratacao_nao_encontrada")\n        return self._contratacao(linha)\n\n    def listar_cotacoes_para_contratar(self, empresa_id: int, deslocamento: int, limite: int) -> CotacoesParaContratarPagina:\n        self.validar_empresa(empresa_id, "cliente")\n        cliente, fornecedor = aliased(Empresa), aliased(Empresa)\n        existe = select(ContratacaoServico.id).where(\n            ContratacaoServico.solicitacao_id == SolicitacaoServico.id,\n        ).correlate(SolicitacaoServico).exists()\n        consulta = (\n            select(CotacaoFornecedor, SolicitacaoServico, cliente.razao_social,\n                   fornecedor.razao_social, ProcessoFabricacao.nome, Material.nome)\n            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)\n            .join(cliente, cliente.id == SolicitacaoServico.empresa_cliente_id)\n            .join(fornecedor, fornecedor.id == CotacaoFornecedor.empresa_fornecedora_id)\n            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)\n            .join(Material, Material.id == SolicitacaoServico.material_id)\n            .where(SolicitacaoServico.empresa_cliente_id == empresa_id,\n                   SolicitacaoServico.status == "aberta", CotacaoFornecedor.status == "aceita",\n                   CotacaoFornecedor.decidida_por_empresa_id == empresa_id, ~existe)\n        )\n        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0\n        linhas = self.banco.execute(consulta.order_by(CotacaoFornecedor.id.desc()).offset(deslocamento).limit(limite)).all()\n        itens = [CotacaoParaContratarLeitura(\n            **CotacaoLeitura.model_validate(cotacao).model_dump(), fornecedor_razao_social=fornecedor_nome,\n            solicitacao=self._solicitacao(solicitacao, cliente_nome, processo, material),\n        ) for cotacao, solicitacao, cliente_nome, fornecedor_nome, processo, material in linhas]\n        return CotacoesParaContratarPagina(itens=itens, total=total, deslocamento=deslocamento, limite=limite)\n', 'backend/app/api/rotas/portal_contratacoes.py': 'from __future__ import annotations\n\nfrom typing import Annotated\n\nfrom fastapi import APIRouter, Depends, HTTPException, Path, Query, status\nfrom fastapi.responses import FileResponse\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.api.rotas.contratacoes import criar_contratacao\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.schemas.arquivo_tecnico import ArquivoTecnicoResposta\nfrom backend.app.schemas.contratacao import ContratacaoCriacao, ContratacaoLeitura\nfrom backend.app.schemas.portal_contratacoes import (\n    ContratacaoPortalLeitura, ContratacoesPortalPagina, CotacoesParaContratarPagina,\n)\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\nfrom backend.app.services.portal_contratacoes import Perfil, ServicoPortalContratacoes\n\nroteador = APIRouter(tags=["contratações dos portais"])\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\nEmpresaId = Annotated[int, Query(gt=0)]\nRecursoId = Annotated[int, Path(gt=0)]\nDeslocamento = Annotated[int, Query(ge=0)]\nLimite = Annotated[int, Query(ge=1, le=100)]\n\n\n@roteador.get("/portal-cliente/cotacoes-aceitas", response_model=CotacoesParaContratarPagina)\ndef listar_cotacoes_aceitas(banco: SessaoBanco, empresa_cliente_id: EmpresaId,\n                          deslocamento: Deslocamento = 0, limite: Limite = 20) -> CotacoesParaContratarPagina:\n    return ServicoPortalContratacoes(banco).listar_cotacoes_para_contratar(empresa_cliente_id, deslocamento, limite)\n\n\n@roteador.post("/portal-cliente/solicitacoes/{solicitacao_id}/contratacao",\n               response_model=ContratacaoLeitura, status_code=status.HTTP_201_CREATED)\ndef contratar_cotacao(solicitacao_id: RecursoId, dados: ContratacaoCriacao, banco: SessaoBanco) -> ContratacaoLeitura:\n    ServicoPortalContratacoes(banco).validar_empresa(dados.empresa_cliente_id, "cliente")\n    return criar_contratacao(solicitacao_id, dados, banco)\n\n\n@roteador.get("/portal-cliente/contratacoes", response_model=ContratacoesPortalPagina)\ndef listar_cliente(banco: SessaoBanco, empresa_cliente_id: EmpresaId,\n                   deslocamento: Deslocamento = 0, limite: Limite = 20) -> ContratacoesPortalPagina:\n    return ServicoPortalContratacoes(banco).listar_contratacoes(empresa_cliente_id, "cliente", deslocamento, limite)\n\n\n@roteador.get("/portal-fornecedor/contratacoes", response_model=ContratacoesPortalPagina)\ndef listar_fornecedor(banco: SessaoBanco, empresa_fornecedora_id: EmpresaId,\n                      deslocamento: Deslocamento = 0, limite: Limite = 20) -> ContratacoesPortalPagina:\n    return ServicoPortalContratacoes(banco).listar_contratacoes(empresa_fornecedora_id, "fornecedor", deslocamento, limite)\n\n\n@roteador.get("/portal-cliente/contratacoes/{contratacao_id}", response_model=ContratacaoPortalLeitura)\ndef obter_cliente(contratacao_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> ContratacaoPortalLeitura:\n    return ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_cliente_id, "cliente")\n\n\n@roteador.get("/portal-fornecedor/contratacoes/{contratacao_id}", response_model=ContratacaoPortalLeitura)\ndef obter_fornecedor(contratacao_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> ContratacaoPortalLeitura:\n    return ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_fornecedora_id, "fornecedor")\n\n\ndef _listar_arquivos(contratacao_id: int, banco: Session, empresa_id: int, perfil: Perfil) -> list[ArquivoTecnicoResposta]:\n    item = ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_id, perfil)\n    return [ArquivoTecnicoResposta.model_validate(arquivo)\n            for arquivo in ServicoArquivoTecnico(banco).listar(item.solicitacao_id)]\n\n\ndef _baixar_arquivo(contratacao_id: int, arquivo_id: int, banco: Session, empresa_id: int, perfil: Perfil) -> FileResponse:\n    contrato = ServicoPortalContratacoes(banco).obter_contratacao(contratacao_id, empresa_id, perfil)\n    arquivos = ServicoArquivoTecnico(banco)\n    arquivo = arquivos.obter(arquivo_id)\n    if arquivo.solicitacao_id != contrato.solicitacao_id:\n        raise HTTPException(404, detail="arquivo_tecnico_nao_encontrado")\n    return FileResponse(arquivos.caminho_seguro(arquivo),\n                        media_type=arquivo.content_type or "application/octet-stream", filename=arquivo.nome_original)\n\n\n@roteador.get("/portal-cliente/contratacoes/{contratacao_id}/arquivos", response_model=list[ArquivoTecnicoResposta])\ndef arquivos_cliente(contratacao_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> list[ArquivoTecnicoResposta]:\n    return _listar_arquivos(contratacao_id, banco, empresa_cliente_id, "cliente")\n\n\n@roteador.get("/portal-fornecedor/contratacoes/{contratacao_id}/arquivos", response_model=list[ArquivoTecnicoResposta])\ndef arquivos_fornecedor(contratacao_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> list[ArquivoTecnicoResposta]:\n    return _listar_arquivos(contratacao_id, banco, empresa_fornecedora_id, "fornecedor")\n\n\n@roteador.get("/portal-cliente/contratacoes/{contratacao_id}/arquivos/{arquivo_id}/download", response_class=FileResponse)\ndef download_cliente(contratacao_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_cliente_id: EmpresaId) -> FileResponse:\n    return _baixar_arquivo(contratacao_id, arquivo_id, banco, empresa_cliente_id, "cliente")\n\n\n@roteador.get("/portal-fornecedor/contratacoes/{contratacao_id}/arquivos/{arquivo_id}/download", response_class=FileResponse)\ndef download_fornecedor(contratacao_id: RecursoId, arquivo_id: RecursoId, banco: SessaoBanco, empresa_fornecedora_id: EmpresaId) -> FileResponse:\n    return _baixar_arquivo(contratacao_id, arquivo_id, banco, empresa_fornecedora_id, "fornecedor")\n', 'frontend/src/pages/contratacoes/PortalContratacoesPage.tsx': 'import { useEffect, useRef, useState, type FormEvent } from "react";\nimport { Link } from "react-router-dom";\nimport { CheckCircle2, ClipboardList, Download, FileText, Handshake, RefreshCw, X } from "lucide-react";\nimport { useAuth } from "../../auth/AuthContext";\nimport { api } from "../../services/api";\nimport { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from "../client/cotacoesCliente";\nimport { formatarTamanhoArquivo, type ArquivoFornecedor } from "../supplier/cotacoesFornecedor";\nimport {\n  formatarMedidaContrato, mensagemErroContratacao, rotuloContratacao,\n  type ContratacaoPortal, type ContratacaoResposta, type CotacaoParaContratar, type PaginaContratacoes, type PerfilContratacoes,\n} from "./contratacoesPortal";\nimport "./PortalContratacoesPage.css";\n\ntype Visao = "contratacoes" | "aceitas";\ntype Grupo = { chave: string; contratos: PaginaContratacoes<ContratacaoPortal>; aceitas: PaginaContratacoes<CotacaoParaContratar> };\ntype Revisao = { chave: string; empresaId: number; cotacao: CotacaoParaContratar; observacoes: string | null };\nconst LIMITE = 20;\nconst PAGINA_VAZIA = { itens: [], total: 0, deslocamento: 0, limite: LIMITE };\n\nexport default function PortalContratacoesPage({ perfil }: { perfil: PerfilContratacoes }) {\n  const { user } = useAuth();\n  const empresaId = user?.role === perfil ? user.id : 0;\n  const base = `/portal-${perfil}`;\n  const [visao, setVisao] = useState<Visao>("contratacoes");\n  const visaoAtual = perfil === "cliente" ? visao : "contratacoes";\n  const [deslocamento, setDeslocamento] = useState(0);\n  const [atualizacao, setAtualizacao] = useState(0);\n  const [grupo, setGrupo] = useState<Grupo | null>(null);\n  const [selecionadoId, setSelecionadoId] = useState(0);\n  const [carregando, setCarregando] = useState(true);\n  const [erroLista, setErroLista] = useState("");\n  const [rascunho, setRascunho] = useState({ chave: "", texto: "" });\n  const [revisao, setRevisao] = useState<Revisao | null>(null);\n  const [enviando, setEnviando] = useState(false);\n  const [erroEnvio, setErroEnvio] = useState("");\n  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);\n  const [arquivos, setArquivos] = useState<{ chave: string; itens: ArquivoFornecedor[] } | null>(null);\n  const [erroArquivos, setErroArquivos] = useState("");\n  const [carregandoArquivos, setCarregandoArquivos] = useState(false);\n  const [atualizacaoArquivos, setAtualizacaoArquivos] = useState(0);\n  const [baixando, setBaixando] = useState<number | null>(null);\n  const paginaChave = `${perfil}:${empresaId}:${visaoAtual}:${deslocamento}:${atualizacao}`;\n  const grupoAtual = grupo?.chave === paginaChave ? grupo : null;\n  const pagina = visaoAtual === "aceitas" ? grupoAtual?.aceitas : grupoAtual?.contratos;\n  const contratos = grupoAtual?.contratos.itens ?? [];\n  const aceitas = grupoAtual?.aceitas.itens ?? [];\n  const contrato = visaoAtual === "contratacoes" ? contratos.find((item) => item.id === selecionadoId) ?? contratos[0] : undefined;\n  const cotacao = visaoAtual === "aceitas" ? aceitas.find((item) => item.id === selecionadoId) ?? aceitas[0] : undefined;\n  const solicitacao = contrato?.solicitacao ?? cotacao?.solicitacao;\n  const selecaoChave = `${perfil}:${empresaId}:${visaoAtual}:${contrato?.id ?? cotacao?.id ?? 0}`;\n  const textoObservacoes = rascunho.chave === selecaoChave ? rascunho.texto : "";\n  const modalAtual = revisao?.chave === selecaoChave && revisao.empresaId === empresaId && perfil === "cliente" && grupoAtual ? revisao : null;\n  const arquivosAtuais = arquivos?.chave === selecaoChave ? arquivos.itens : [];\n  const bloquear = carregando || enviando || !grupoAtual;\n  const parametrosEmpresa = perfil === "cliente" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };\n  const contexto = useRef({ paginaChave, selecaoChave, dono: `${perfil}:${empresaId}` });\n  contexto.current = { paginaChave, selecaoChave, dono: `${perfil}:${empresaId}` };\n  const montada = useRef(true);\n  const dialogo = useRef<HTMLDialogElement | null>(null);\n  const trava = useRef(false);\n  const envio = useRef<AbortController | null>(null);\n  const download = useRef<AbortController | null>(null);\n\n  useEffect(() => {\n    montada.current = true;\n    return () => { montada.current = false; envio.current?.abort(); download.current?.abort(); };\n  }, []);\n\n  useEffect(() => {\n    setVisao("contratacoes"); setDeslocamento(0); setSelecionadoId(0);\n    setRevisao(null); setErroEnvio(""); envio.current?.abort();\n  }, [empresaId, perfil]);\n\n  useEffect(() => {\n    const controlador = new AbortController();\n    let vigente = true;\n    setCarregando(true); setErroLista(""); setRevisao(null);\n    if (!empresaId) {\n      setErroLista(`Entre com um acesso de ${perfil} para consultar suas contratações.`);\n      setCarregando(false);\n      return () => { vigente = false; controlador.abort(); };\n    }\n    async function carregar() {\n      try {\n        const config = { params: { ...parametrosEmpresa, deslocamento: visaoAtual === "contratacoes" ? deslocamento : 0, limite: LIMITE }, signal: controlador.signal, timeout: 20_000 };\n        const [resposta, candidatas] = await Promise.all([\n          api.get<PaginaContratacoes<ContratacaoPortal>>(`${base}/contratacoes`, config),\n          perfil === "cliente" ? api.get<PaginaContratacoes<CotacaoParaContratar>>("/portal-cliente/cotacoes-aceitas", {\n            ...config, params: { empresa_cliente_id: empresaId, deslocamento: visaoAtual === "aceitas" ? deslocamento : 0, limite: LIMITE },\n          }) : Promise.resolve({ data: PAGINA_VAZIA as PaginaContratacoes<CotacaoParaContratar> }),\n        ]);\n        if (!vigente || contexto.current.paginaChave !== paginaChave) return;\n        const quantidade = visaoAtual === "aceitas" ? candidatas.data.total : resposta.data.total;\n        if (quantidade > 0 && deslocamento >= quantidade) {\n          setDeslocamento(Math.floor((quantidade - 1) / LIMITE) * LIMITE); return;\n        }\n        if (quantidade === 0 && deslocamento > 0) { setDeslocamento(0); return; }\n        const proprios = resposta.data.itens.filter((item) => (perfil === "cliente" ? item.empresa_cliente_id : item.empresa_fornecedora_id) === empresaId);\n        const aptas = candidatas.data.itens.filter((item) => item.solicitacao.empresa_cliente_id === empresaId && item.status === "aceita" && item.decidida_por_empresa_id === empresaId);\n        setGrupo({ chave: paginaChave, contratos: { ...resposta.data, itens: proprios }, aceitas: { ...candidatas.data, itens: aptas } });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.paginaChave === paginaChave) setErroLista(mensagemErroContratacao(erro));\n      } finally {\n        if (vigente && contexto.current.paginaChave === paginaChave) setCarregando(false);\n      }\n    }\n    void carregar();\n    return () => { vigente = false; controlador.abort(); };\n    // Os parâmetros da empresa são derivados do perfil e da empresaId.\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, empresaId, perfil, visaoAtual, deslocamento, paginaChave]);\n\n  useEffect(() => {\n    setRevisao(null); setErroEnvio(""); setErroArquivos(""); setBaixando(null);\n    download.current?.abort();\n  }, [selecaoChave]);\n\n  useEffect(() => {\n    const controlador = new AbortController();\n    let vigente = true;\n    setErroArquivos(""); setCarregandoArquivos(Boolean(contrato));\n    if (!contrato) return () => { vigente = false; controlador.abort(); };\n    async function carregarArquivos() {\n      try {\n        const { data } = await api.get<ArquivoFornecedor[]>(`${base}/contratacoes/${contrato!.id}/arquivos`, {\n          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,\n        });\n        if (vigente && contexto.current.selecaoChave === selecaoChave) setArquivos({ chave: selecaoChave, itens: data.filter((item) => item.ativo && item.solicitacao_id === contrato!.solicitacao_id) });\n      } catch (erro) {\n        if (vigente && !controlador.signal.aborted && contexto.current.selecaoChave === selecaoChave) setErroArquivos(mensagemErroContratacao(erro));\n      } finally {\n        if (vigente && contexto.current.selecaoChave === selecaoChave) setCarregandoArquivos(false);\n      }\n    }\n    void carregarArquivos();\n    return () => { vigente = false; controlador.abort(); };\n    // eslint-disable-next-line react-hooks/exhaustive-deps\n  }, [base, perfil, empresaId, contrato?.id, selecaoChave, atualizacaoArquivos]);\n\n  useEffect(() => {\n    const elemento = dialogo.current;\n    if (!elemento) return;\n    if (modalAtual && !elemento.open) elemento.showModal();\n    if (!modalAtual && elemento.open) elemento.close();\n  }, [modalAtual]);\n\n  function mudarVisao(nova: Visao) {\n    if (trava.current) return;\n    setVisao(nova); setDeslocamento(0); setSelecionadoId(0); setRevisao(null); setErroEnvio("");\n  }\n\n  function revisar(evento: FormEvent<HTMLFormElement>) {\n    evento.preventDefault();\n    if (!cotacao || perfil !== "cliente" || bloquear || trava.current) return;\n    if (textoObservacoes.length > 5000) { setErroEnvio("As observações podem ter até 5000 caracteres."); return; }\n    setErroEnvio("");\n    setRevisao({ chave: selecaoChave, empresaId, cotacao, observacoes: textoObservacoes.trim() || null });\n  }\n\n  async function confirmar() {\n    if (!modalAtual || bloquear || trava.current) return;\n    const confirmado = modalAtual;\n    const dono = `${perfil}:${empresaId}`;\n    const controlador = new AbortController();\n    envio.current = controlador; trava.current = true; setEnviando(true); setErroEnvio("");\n    try {\n      const { data } = await api.post<ContratacaoResposta>(`/portal-cliente/solicitacoes/${confirmado.cotacao.solicitacao_id}/contratacao`, {\n        empresa_cliente_id: confirmado.empresaId, cotacao_id: confirmado.cotacao.id, observacoes: confirmado.observacoes,\n      }, { signal: controlador.signal, timeout: 30_000 });\n      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== dono || contexto.current.selecaoChave !== confirmado.chave) return;\n      if (data.solicitacao_id !== confirmado.cotacao.solicitacao_id || data.cotacao_id !== confirmado.cotacao.id || data.empresa_cliente_id !== confirmado.empresaId) throw new Error("Resposta da contratação divergente.");\n      setSucesso({ dono, texto: `Contratação #${data.id} criada para a solicitação #${data.solicitacao_id}. O fornecedor já pode consultá-la.` });\n      setRascunho({ chave: "", texto: "" }); setRevisao(null);\n      setVisao("contratacoes"); setDeslocamento(0); setSelecionadoId(data.id); setAtualizacao((valor) => valor + 1);\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.dono === dono && contexto.current.selecaoChave === confirmado.chave) {\n        const respondeu = typeof erro === "object" && erro !== null && "response" in erro && Boolean((erro as { response?: unknown }).response);\n        setErroEnvio(respondeu ? mensagemErroContratacao(erro) : "A criação não pôde ser confirmada. Atualize a aba Contratações antes de tentar contratar novamente.");\n        setRevisao(null);\n      }\n    } finally {\n      if (envio.current === controlador) envio.current = null;\n      trava.current = false;\n      if (montada.current) setEnviando(false);\n    }\n  }\n\n  async function baixar(arquivo: ArquivoFornecedor) {\n    if (!contrato || baixando !== null || download.current) return;\n    const controlador = new AbortController();\n    const chave = selecaoChave;\n    download.current = controlador; setBaixando(arquivo.id); setErroArquivos("");\n    try {\n      const { data } = await api.get<Blob>(`${base}/contratacoes/${contrato.id}/arquivos/${arquivo.id}/download`, {\n        params: parametrosEmpresa, signal: controlador.signal, responseType: "blob", timeout: 60_000,\n      });\n      if (!montada.current || controlador.signal.aborted || contexto.current.selecaoChave !== chave) return;\n      const url = URL.createObjectURL(data);\n      const link = document.createElement("a");\n      try {\n        link.href = url; link.download = arquivo.nome_original.replace(/[\\\\/]/g, "_");\n        document.body.appendChild(link); link.click();\n      } finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }\n    } catch (erro) {\n      if (montada.current && !controlador.signal.aborted && contexto.current.selecaoChave === chave) setErroArquivos(mensagemErroContratacao(erro));\n    } finally {\n      if (download.current === controlador) download.current = null;\n      if (montada.current && contexto.current.selecaoChave === chave) setBaixando(null);\n    }\n  }\n\n  const total = pagina?.total ?? 0;\n  const linhas = visaoAtual === "aceitas" ? aceitas : contratos;\n  return <main className="k25-page">\n    <header className="k25-header">\n      <div><p className="k25-eyebrow"><Handshake size={16} /> PORTAL DO {perfil === "cliente" ? "CLIENTE" : "FORNECEDOR"}</p>\n        <h1>{perfil === "cliente" ? "Minhas Contratações" : "Contratações"}</h1>\n        <p>{perfil === "cliente" ? "Contrate uma proposta aceita e acompanhe os serviços da sua empresa." : "Consulte os serviços contratados pelos seus clientes."}</p></div>\n      <button className="k25-button" disabled={enviando || carregando} onClick={() => setAtualizacao((valor) => valor + 1)}><RefreshCw size={16} /> Atualizar</button>\n    </header>\n    {sucesso?.dono === `${perfil}:${empresaId}` && <p className="k25-alert k25-success" role="status"><CheckCircle2 size={18} /> {sucesso.texto}</p>}\n    {erroLista && <p className="k25-alert k25-error" role="alert">{erroLista}</p>}\n    <div className="k25-summary">\n      <article><span>Contratações da sua empresa</span><strong>{grupoAtual ? grupoAtual.contratos.total : "—"}</strong><small>Inclui ativas, canceladas e encerradas</small></article>\n      {perfil === "cliente" && <article><span>Cotações prontas para contratar</span><strong>{grupoAtual ? grupoAtual.aceitas.total : "—"}</strong><small>Aceitas e ainda sem contratação</small></article>}\n    </div>\n    <nav className="k25-tabs" aria-label="Consultas de contratação">\n      <button className={`k25-button ${visaoAtual === "contratacoes" ? "k25-tab-active" : ""}`} aria-pressed={visaoAtual === "contratacoes"} disabled={enviando} onClick={() => mudarVisao("contratacoes")}><Handshake size={16} /> Contratações</button>\n      {perfil === "cliente" && <button className={`k25-button ${visaoAtual === "aceitas" ? "k25-tab-active" : ""}`} aria-pressed={visaoAtual === "aceitas"} disabled={enviando} onClick={() => mudarVisao("aceitas")}><CheckCircle2 size={16} /> Cotações para contratar</button>}\n      <Link className="k25-button" to={`/${perfil}/cotacoes`}><FileText size={16} /> {perfil === "cliente" ? "Cotações Recebidas" : "Minhas Cotações"}</Link>\n    </nav>\n    <section className="k25-panel" aria-busy={carregando}>\n      <div className="k25-section-head"><div><h2>{visaoAtual === "aceitas" ? "Propostas aceitas pelo cliente" : "Serviços contratados"}</h2><p>{visaoAtual === "aceitas" ? "Confira a proposta e revise os dados antes de criar a contratação." : "Selecione uma contratação para consultar os detalhes e os arquivos técnicos."}</p></div></div>\n      {carregando ? <div className="k25-empty" role="status">Carregando {visaoAtual === "aceitas" ? "cotações" : "contratações"}…</div>\n        : !erroLista && linhas.length === 0 ? <div className="k25-empty"><Handshake size={32} /><h3>{visaoAtual === "aceitas" ? "Nenhuma cotação pronta para contratar" : "Nenhuma contratação cadastrada"}</h3><p>{visaoAtual === "aceitas" ? "Aceite uma proposta em Cotações Recebidas. Solicitações já contratadas não aparecem nesta lista." : perfil === "cliente" ? "Abra Cotações para contratar para criar uma contratação a partir de uma proposta aceita." : "As contratações aparecerão aqui quando o cliente contratar uma proposta da sua empresa."}</p></div>\n        : grupoAtual && <div className="k25-table-wrap"><table><thead><tr><th>Solicitação / referência</th><th>{perfil === "cliente" ? "Fornecedor" : "Cliente"}</th><th>Valor total</th><th>Prazo</th><th>Situação</th><th><span className="k25-sr-only">Ações</span></th></tr></thead><tbody>\n          {linhas.map((item) => { const criado = "cotacao_id" in item; const ativo = item.id === (contrato?.id ?? cotacao?.id);\n            return <tr key={item.id} className={ativo ? "k25-selected" : ""}><td><strong>Solicitação #{item.solicitacao_id}</strong><small>{criado ? `Contratação #${item.id} · Cotação #${item.cotacao_id}` : `Cotação #${item.id}`}</small></td>\n              <td>{perfil === "cliente" ? item.fornecedor_razao_social : criado ? item.cliente_razao_social : ""}<small>{item.solicitacao.processo_nome} · {item.solicitacao.material_nome}</small></td>\n              <td className="k25-nowrap"><strong>{formatarValorCotacao(item.valor_total)}</strong></td><td className="k25-nowrap">{item.prazo_dias} dias</td>\n              <td><span className={`k25-badge k25-status-${criado && ["ativa", "cancelada", "encerrada"].includes(item.status) ? item.status : "aceita"}`}>{criado ? rotuloContratacao(item.status) : "Pronta para contratar"}</span></td>\n              <td><button className="k25-button" disabled={enviando} onClick={() => setSelecionadoId(item.id)} aria-pressed={ativo}>{ativo ? "Selecionada" : "Ver detalhes"}</button></td></tr>;\n          })}\n        </tbody></table></div>}\n      {grupoAtual && total > 0 && <div className="k25-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + linhas.length, total)} de {total}</span><div>\n        <button className="k25-button" disabled={bloquear || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((valor) => Math.max(0, valor - LIMITE)); }}>Anterior</button>\n        <button className="k25-button" disabled={bloquear || deslocamento + LIMITE >= total} onClick={() => { setSelecionadoId(0); setDeslocamento((valor) => valor + LIMITE); }}>Próxima</button></div></div>}\n    </section>\n    {solicitacao && <div className="k25-columns">\n      <section className="k25-panel k25-detail"><div className="k25-section-head"><h2>Solicitação #{solicitacao.id}</h2><ClipboardList size={21} /></div>\n        <dl className="k25-fields"><div><dt>Cliente</dt><dd>{solicitacao.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{contrato?.fornecedor_razao_social ?? cotacao?.fornecedor_razao_social}</dd></div>\n          <div><dt>Processo</dt><dd>{solicitacao.processo_nome}</dd></div><div><dt>Material</dt><dd>{solicitacao.material_nome}</dd></div>\n          <div><dt>Quantidade</dt><dd>{solicitacao.quantidade} unidades</dd></div><div><dt>Tolerância requerida</dt><dd>{formatarMedidaContrato(solicitacao.tolerancia_requerida_mm, 4)} mm</dd></div>\n          <div className="k25-wide"><dt>Dimensões máximas X / Y / Z</dt><dd>{[solicitacao.dimensao_x_maxima_mm, solicitacao.dimensao_y_maxima_mm, solicitacao.dimensao_z_maxima_mm].map((valor) => formatarMedidaContrato(valor)).join(" × ")} mm</dd></div></dl>\n        <h3>Observações da solicitação</h3><p className="k25-observacoes">{solicitacao.observacoes || "Sem observações."}</p>\n        {perfil === "cliente" && <Link className="k25-button" to={`/cliente/cotacoes?solicitacao=${solicitacao.id}`}>Consultar cotações desta solicitação</Link>}\n        {contrato && <><div className="k25-section-head k25-files-head"><h3>Arquivos técnicos</h3><button className="k25-button" disabled={carregandoArquivos || baixando !== null} onClick={() => setAtualizacaoArquivos((valor) => valor + 1)}>Atualizar arquivos</button></div>\n          {erroArquivos && <p className="k25-alert k25-error" role="alert">{erroArquivos}</p>}\n          {carregandoArquivos ? <p role="status">Carregando arquivos…</p> : !erroArquivos && arquivosAtuais.length === 0 ? <p>Nenhum arquivo ativo vinculado a esta solicitação.</p> : <ul className="k25-files">{arquivosAtuais.map((arquivo) => <li key={arquivo.id}><FileText size={19} /><span><strong>{arquivo.nome_original}</strong><small>{arquivo.extensao.toUpperCase()} · {formatarTamanhoArquivo(arquivo.tamanho_bytes)}</small></span><button className="k25-button" disabled={baixando !== null} onClick={() => void baixar(arquivo)}><Download size={15} /> {baixando === arquivo.id ? "Baixando…" : "Baixar"}</button></li>)}</ul>}\n        </>}\n      </section>\n      <section className="k25-panel k25-detail"><div className="k25-section-head"><h2>{contrato ? `Contratação #${contrato.id}` : `Contratar cotação #${cotacao!.id}`}</h2><Handshake size={21} /></div>\n        <dl className="k25-fields"><div><dt>Valor total</dt><dd className="k25-value">{formatarValorCotacao((contrato ?? cotacao)!.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{(contrato ?? cotacao)!.prazo_dias} dias</dd></div>\n          {contrato && <><div><dt>Situação</dt><dd>{rotuloContratacao(contrato.status)}</dd></div><div><dt>Criada em</dt><dd>{formatarInstanteCotacao(instanteUtc(contrato.criada_em))}</dd></div>\n            {contrato.cancelada_em && <div><dt>Cancelada em</dt><dd>{formatarInstanteCotacao(instanteUtc(contrato.cancelada_em))}</dd></div>}\n            {contrato.encerrada_em && <div><dt>Encerrada em</dt><dd>{formatarInstanteCotacao(instanteUtc(contrato.encerrada_em))}</dd></div>}</>}\n          {cotacao && <div className="k25-wide"><dt>Proposta aceita em</dt><dd>{formatarInstanteCotacao(instanteUtc(cotacao.encerrada_em))}</dd></div>}\n        </dl>\n        <h3>{contrato ? "Observações da contratação" : "Observações da proposta aceita"}</h3><p className="k25-observacoes">{(contrato ?? cotacao)!.observacoes || "Sem observações."}</p>\n        {cotacao && perfil === "cliente" && <form className="k25-form" onSubmit={revisar}><fieldset disabled={bloquear}><label htmlFor="k25-observacoes">Observações da contratação (opcional)</label>\n          <textarea id="k25-observacoes" maxLength={5000} rows={4} value={textoObservacoes} onChange={(evento) => { setRascunho({ chave: selecaoChave, texto: evento.target.value }); setErroEnvio(""); }} placeholder="Registre os termos adicionais já acordados com o fornecedor." />\n          <p>O valor e o prazo serão os da cotação aceita. Ao contratar, a solicitação será encerrada para novas propostas.</p>\n          {erroEnvio && <p className="k25-alert k25-error" role="alert">{erroEnvio}</p>}\n          <button type="submit" className="k25-button k25-primary"><Handshake size={16} /> Revisar contratação</button>\n        </fieldset></form>}\n      </section>\n    </div>}\n    <dialog ref={dialogo} className="k25-dialog" aria-labelledby="k25-dialog-title" onCancel={(evento) => { if (trava.current) evento.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>\n      {modalAtual && <><div className="k25-section-head"><h2 id="k25-dialog-title">Confirmar contratação</h2><button className="k25-button" aria-label="Fechar revisão" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>\n        <p>Confira os dados antes de contratar esta proposta.</p>\n        <dl className="k25-fields"><div><dt>Solicitação</dt><dd>#{modalAtual.cotacao.solicitacao_id}</dd></div><div><dt>Cotação aceita</dt><dd>#{modalAtual.cotacao.id}</dd></div>\n          <div className="k25-wide"><dt>Fornecedor</dt><dd>{modalAtual.cotacao.fornecedor_razao_social}</dd></div><div><dt>Valor total</dt><dd>{formatarValorCotacao(modalAtual.cotacao.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{modalAtual.cotacao.prazo_dias} dias</dd></div></dl>\n        <h3>Observações da contratação</h3><p className="k25-observacoes">{modalAtual.observacoes || "Sem observações."}</p>\n        <p>A contratação ficará ativa e a solicitação será encerrada para novas propostas.</p>\n        <div className="k25-dialog-actions"><button className="k25-button" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button><button className="k25-button k25-primary" disabled={enviando} onClick={() => void confirmar()}>{enviando ? "Criando contratação…" : "Confirmar contratação"}</button></div>\n      </>}\n    </dialog>\n  </main>;\n}\n', 'frontend/src/pages/contratacoes/contratacoesPortal.ts': 'import type { CotacaoCliente } from "../client/cotacoesCliente";\nimport type { SolicitacaoFornecedor } from "../supplier/cotacoesFornecedor";\n\nexport type PerfilContratacoes = "cliente" | "fornecedor";\nexport type CotacaoParaContratar = CotacaoCliente & {\n  fornecedor_razao_social: string;\n  solicitacao: SolicitacaoFornecedor;\n};\nexport type ContratacaoPortal = {\n  id: number; solicitacao_id: number; cotacao_id: number;\n  empresa_cliente_id: number; empresa_fornecedora_id: number;\n  cliente_razao_social: string; fornecedor_razao_social: string;\n  valor_total: string | number; prazo_dias: number; observacoes: string | null;\n  status: string; criada_em: string; cancelada_em: string | null; encerrada_em: string | null;\n  solicitacao: SolicitacaoFornecedor;\n};\nexport type ContratacaoResposta = Omit<ContratacaoPortal, "cliente_razao_social" | "fornecedor_razao_social" | "solicitacao">;\nexport type PaginaContratacoes<T> = { itens: T[]; total: number; deslocamento: number; limite: number };\n\nexport function rotuloContratacao(status: string): string {\n  return ({ ativa: "Ativa", cancelada: "Cancelada", encerrada: "Encerrada" } as Record<string, string>)[status] ?? "Situação indisponível";\n}\n\nexport function formatarMedidaContrato(valor: string | number, casas = 3): string {\n  const numero = Number(valor);\n  return Number.isFinite(numero) ? numero.toLocaleString("pt-BR", { maximumFractionDigits: casas }) : "—";\n}\n\nexport function mensagemErroContratacao(erro: unknown): string {\n  if (typeof erro === "object" && erro !== null && "response" in erro) {\n    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;\n    const mensagens: Record<string, string> = {\n      empresa_cliente_nao_encontrada: "A empresa cliente deste acesso não foi encontrada.",\n      empresa_fornecedor_nao_encontrada: "A empresa fornecedora deste acesso não foi encontrada.",\n      empresa_nao_e_cliente: "Entre com um acesso de cliente para consultar ou criar suas contratações.",\n      empresa_nao_e_fornecedor: "Entre com um acesso de fornecedor para consultar suas contratações.",\n      empresa_nao_e_cliente_da_solicitacao: "Esta solicitação pertence a outro cliente.",\n      solicitacao_nao_encontrada: "A solicitação não foi encontrada. Atualize a lista.",\n      solicitacao_nao_esta_aberta: "A solicitação já foi encerrada. Atualize as listas antes de continuar.",\n      cotacao_nao_encontrada: "A cotação não foi encontrada nessa solicitação. Atualize a lista.",\n      cotacao_nao_esta_aceita: "A cotação precisa estar aceita pelo cliente para ser contratada.",\n      contratacao_ja_cadastrada: "Esta solicitação já possui uma contratação. Consulte a aba Contratações.",\n      contratacao_nao_encontrada: "A contratação não está disponível para esta empresa. Atualize a lista.",\n      arquivo_tecnico_nao_encontrado: "O arquivo não está mais disponível. Atualize os arquivos.",\n    };\n    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";\n    if (Array.isArray(detalhe)) return "Confira os dados da contratação e limite as observações a 5000 caracteres.";\n  }\n  return "Não foi possível consultar os dados. Confira a conexão e atualize a tela.";\n}\n', 'frontend/src/pages/contratacoes/PortalContratacoesPage.css': '.k25-page { color: #dce7f7; display: flex; flex-direction: column; gap: 22px; width: 100%; }\n.k25-page * { box-sizing: border-box; }\n.k25-page h1, .k25-page h2, .k25-page h3, .k25-page p { margin: 0; }\n.k25-page h1 { color: #edf3fc; font-size: clamp(28px, 3vw, 40px); line-height: 1.25; margin: 10px 0 12px; }\n.k25-page h2 { font-size: 19px; color: #e9f0fc; }\n.k25-page h3 { color: #c6d8ef; font-size: 14px; margin: 22px 0 10px; }\n.k25-page p { color: #91a8c8; line-height: 1.6; }\n.k25-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }\n.k25-page .k25-eyebrow { display: flex; align-items: center; gap: 9px; color: #6ba6ff; font-size: 12px; font-weight: 800; letter-spacing: .09em; }\n.k25-button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 11px 15px; background: #162333; border: 1px solid #31465f; border-radius: 8px; color: #dce9fc; font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; text-decoration: none; line-height: 1.4; }\n.k25-button:hover:enabled, a.k25-button:hover { background: #213754; border-color: #6592cc; }\n.k25-button:focus-visible, .k25-form textarea:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }\n.k25-button:disabled { opacity: .45; cursor: default; }\n.k25-primary { background: #2563eb; border-color: #357bf5; color: #fff; }\n.k25-primary:hover:enabled { background: #3475fb; }\n.k25-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }\n.k25-summary article { display: flex; flex-direction: column; gap: 12px; padding: 23px; background: linear-gradient(145deg, #162235, #101b2b); border: 1px solid #2b3c53; border-radius: 13px; }\n.k25-summary span { color: #a6c0e2; font-size: 13px; }\n.k25-summary strong { font-size: 31px; color: #f2f6fe; }\n.k25-summary small { color: #7794ba; line-height: 1.5; }\n.k25-tabs { display: flex; flex-wrap: wrap; gap: 9px; }\n.k25-tab-active { background: #193658; border-color: #4976b0; }\n.k25-panel { background: #111c2a; border: 1px solid #293d56; border-radius: 13px; overflow: hidden; }\n.k25-section-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 23px; }\n.k25-section-head p { font-size: 13px; margin-top: 10px; }\n.k25-section-head > svg { color: #79aef5; flex-shrink: 0; }\n.k25-table-wrap { overflow-x: auto; }\n.k25-page table { width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; }\n.k25-page th { color: #819fc5; background: #0e1825; padding: 17px 20px; font-weight: 700; white-space: nowrap; }\n.k25-page td { padding: 19px 20px; border-top: 1px solid #26384e; color: #d5e4f7; overflow-wrap: anywhere; }\n.k25-page td strong { color: #e8f1ff; font-size: 13px; }\n.k25-page td small { display: block; color: #7899c2; margin-top: 9px; font-size: 11px; line-height: 1.5; }\n.k25-page .k25-selected { background: #192d46; }\n.k25-nowrap { white-space: nowrap; }\n.k25-badge { display: inline-block; padding: 7px 10px; border-radius: 18px; background: #223245; font-size: 11px; font-weight: 800; white-space: nowrap; }\n.k25-status-ativa, .k25-status-aceita { background: #173d31; color: #80deae; }\n.k25-status-cancelada { background: #42303b; color: #e4a1b9; }\n.k25-status-encerrada { background: #203956; color: #99c6ff; }\n.k25-empty { min-height: 235px; padding: 45px 24px; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 15px; text-align: center; }\n.k25-empty svg { color: #669dea; }\n.k25-empty h3 { font-size: 18px; margin: 0; color: #d9e9ff; }\n.k25-empty p { max-width: 680px; font-size: 13px; }\n.k25-pagination { padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; gap: 14px; border-top: 1px solid #293d56; color: #8fa9cb; font-size: 12px; }\n.k25-pagination > div { display: flex; gap: 9px; }\n.k25-columns { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); gap: 22px; align-items: start; }\n.k25-detail { padding: 23px; }\n.k25-detail .k25-section-head, .k25-dialog .k25-section-head { padding: 0; margin-bottom: 22px; }\n.k25-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }\n.k25-fields > div { border: 1px solid #2b3e56; background: #0d1724; border-radius: 9px; padding: 15px; min-width: 0; }\n.k25-fields dt { color: #819fc4; font-size: 11px; margin-bottom: 10px; }\n.k25-fields dd { color: #e2ecfa; font-size: 13px; font-weight: 700; margin: 0; line-height: 1.6; overflow-wrap: anywhere; }\n.k25-fields .k25-value { font-size: 19px; }\n.k25-wide { grid-column: 1 / -1; }\n.k25-page .k25-observacoes { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; margin-bottom: 20px; }\n.k25-form { margin-top: 22px; }\n.k25-form fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }\n.k25-form label { display: block; color: #b2c9e7; font-size: 12px; font-weight: 700; margin-bottom: 10px; }\n.k25-form textarea { display: block; width: 100%; border: 1px solid #37506e; border-radius: 9px; background: #0b1523; color: #e6f0ff; padding: 13px; font: inherit; font-size: 13px; resize: vertical; line-height: 1.7; }\n.k25-form p { font-size: 12px; margin: 14px 0; }\n.k25-form button[type="submit"] { width: 100%; margin-top: 8px; }\n.k25-page .k25-alert { display: flex; align-items: flex-start; gap: 11px; padding: 15px 18px; border-radius: 9px; font-size: 13px; }\n.k25-alert svg { flex-shrink: 0; }\n.k25-page .k25-success { color: #a1e8c4; background: #143028; border: 1px solid #276148; }\n.k25-page .k25-error { color: #ffbdc6; background: #37212a; border: 1px solid #703c4c; }\n.k25-files-head { margin-top: 28px; }\n.k25-files-head h3 { margin: 0; }\n.k25-files { padding: 0; margin: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }\n.k25-files li { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 9px; border: 1px solid #30445f; background: #0d1724; }\n.k25-files li > svg { color: #79aef5; flex-shrink: 0; }\n.k25-files li > span { flex: 1; min-width: 0; }\n.k25-files strong { font-size: 12px; overflow-wrap: anywhere; }\n.k25-files small { color: #7695bd; font-size: 11px; display: block; margin-top: 6px; }\n.k25-dialog { color: #e4edfa; background: #111e30; border: 1px solid #466891; border-radius: 14px; padding: 26px; width: min(600px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto; box-shadow: 0 24px 90px #0009; }\n.k25-dialog::backdrop { background: #020814c9; }\n.k25-dialog p { font-size: 13px; margin-bottom: 20px; }\n.k25-dialog h3 { margin-top: 20px; }\n.k25-dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; margin-top: 24px; }\n.k25-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }\n@media (max-width: 1100px) { .k25-columns { grid-template-columns: minmax(0, 1fr); } }\n@media (max-width: 650px) { .k25-header { flex-direction: column; } .k25-summary { grid-template-columns: minmax(0, 1fr); } .k25-tabs { flex-direction: column; } .k25-detail, .k25-section-head { padding: 18px; } .k25-pagination { flex-wrap: wrap; } .k25-fields { grid-template-columns: minmax(0, 1fr); } .k25-files li { flex-wrap: wrap; } .k25-files li .k25-button { width: 100%; } .k25-dialog { padding: 20px; } }\n', 'tests/test_portal_contratacoes.py': 'from __future__ import annotations\n\nfrom datetime import datetime, timedelta, timezone\nfrom decimal import Decimal\n\nimport pytest\nfrom fastapi import FastAPI\nfrom fastapi.testclient import TestClient\nfrom sqlalchemy import create_engine, event, select\nfrom sqlalchemy.orm import Session, sessionmaker\nfrom sqlalchemy.pool import StaticPool\n\nfrom backend.app.api.rotas.arquivos_tecnicos import roteador as arquivos\nfrom backend.app.api.rotas.contratacoes import roteador as contratacoes\nfrom backend.app.api.rotas.portal_contratacoes import roteador as portal\nfrom backend.app.database.base import Base\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.contratacao import ContratacaoServico\nfrom backend.app.models.cotacao import CotacaoFornecedor\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.material import Material\nfrom backend.app.models.processo import ProcessoFabricacao\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.services.arquivo_tecnico import ServicoArquivoTecnico\n\nCLIENTE = "/api/v1/portal-cliente"\nFORNECEDOR = "/api/v1/portal-fornecedor"\n\n\ndef nova_solicitacao(banco, numero, cliente=1):\n    solicitacao = SolicitacaoServico(id=numero, empresa_cliente_id=cliente, processo_id=1, material_id=1,\n        dimensao_x_maxima_mm=Decimal("500"), dimensao_y_maxima_mm=Decimal("300"),\n        dimensao_z_maxima_mm=Decimal("250"), tolerancia_requerida_mm=Decimal("0.0200"),\n        quantidade=5, observacoes="Solicitação de teste.")\n    banco.add(solicitacao)\n    banco.flush()\n    return solicitacao\n\n\ndef nova_cotacao(banco, numero, solicitacao, fornecedor=2, decisor=1, status="aceita"):\n    cotacao = CotacaoFornecedor(id=numero, solicitacao_id=solicitacao, empresa_fornecedora_id=fornecedor,\n        valor_total=Decimal("1250.50"), prazo_dias=15, validade_dias=10, status=status,\n        observacoes="Observações da proposta.", decidida_por_empresa_id=decisor if status == "aceita" else None,\n        encerrada_em=datetime.now(timezone.utc).replace(tzinfo=None) if status == "aceita" else None)\n    banco.add(cotacao)\n    banco.flush()\n    return cotacao\n\n\n@pytest.fixture()\ndef ambiente(tmp_path, monkeypatch):\n    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)\n\n    @event.listens_for(engine, "connect")\n    def ativar_chaves_estrangeiras(conexao, _):\n        conexao.execute("PRAGMA foreign_keys=ON")\n\n    sessoes = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)\n    Base.metadata.create_all(engine)\n    monkeypatch.setattr(ServicoArquivoTecnico, "STORAGE_ROOT", tmp_path)\n    with sessoes() as banco:\n        banco.add_all([\n            Empresa(id=1, razao_social="Cliente Teste", documento="cliente-1", tipo_empresa="cliente"),\n            Empresa(id=2, razao_social="Fornecedor Teste", documento="fornecedor-2", tipo_empresa="fornecedor"),\n            Empresa(id=3, razao_social="Outro Fornecedor", documento="fornecedor-3", tipo_empresa="fornecedor"),\n            Empresa(id=4, razao_social="Empresa Ambos", documento="ambos-4", tipo_empresa="ambos"),\n            Empresa(id=5, razao_social="Outro Cliente", documento="cliente-5", tipo_empresa="cliente"),\n            ProcessoFabricacao(id=1, codigo="cnc-d25", nome="Usinagem CNC"),\n            Material(id=1, codigo="al6061-d25", nome="Alumínio 6061"),\n        ])\n        banco.commit()\n        for numero, cliente in ((1, 1), (2, 5), (3, 1), (4, 1)):\n            nova_solicitacao(banco, numero, cliente)\n        nova_cotacao(banco, 1, 1)\n        nova_cotacao(banco, 2, 2, fornecedor=3, decisor=5)\n        nova_cotacao(banco, 3, 3, fornecedor=3, status="enviada")\n        nova_cotacao(banco, 4, 4, decisor=5)\n        banco.commit()\n\n    def banco_teste():\n        with sessoes() as banco:\n            yield banco\n\n    app = FastAPI()\n    for roteador in (arquivos, contratacoes, portal):\n        app.include_router(roteador, prefix="/api/v1")\n    app.dependency_overrides[obter_banco] = banco_teste\n    try:\n        with TestClient(app) as cliente:\n            yield cliente, sessoes\n    finally:\n        app.dependency_overrides.clear()\n        Base.metadata.drop_all(engine)\n        engine.dispose()\n\n\ndef candidatas(http, cliente=1, **pagina):\n    return http.get(CLIENTE + "/cotacoes-aceitas", params={"empresa_cliente_id": cliente, **pagina})\n\n\ndef contratar(http, solicitacao=1, cotacao=1, cliente=1, **campos):\n    return http.post(f"{CLIENTE}/solicitacoes/{solicitacao}/contratacao", json={\n        "empresa_cliente_id": cliente, "cotacao_id": cotacao, "observacoes": "Termos da contratação.", **campos,\n    })\n\n\ndef listar(http, perfil="cliente", empresa=1, **pagina):\n    return http.get(f"/api/v1/portal-{perfil}/contratacoes", params={\n        "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id": empresa, **pagina,\n    })\n\n\ndef test_candidatas_so_aceitas_pelo_dono_e_com_nomes(ambiente):\n    http, _ = ambiente\n    pagina = candidatas(http).json()\n    assert pagina["total"] == 1\n    item = pagina["itens"][0]\n    assert item["id"] == 1 and item["fornecedor_razao_social"] == "Fornecedor Teste"\n    assert item["solicitacao"]["cliente_razao_social"] == "Cliente Teste"\n    assert item["solicitacao"]["processo_nome"] == "Usinagem CNC"\n    assert item["solicitacao"]["material_nome"] == "Alumínio 6061"\n    assert [item["id"] for item in candidatas(http, 5).json()["itens"]] == [2]\n\n\ndef test_criacao_reutiliza_d8_copia_valores_e_chega_aos_dois_portais(ambiente):\n    http, sessoes = ambiente\n    resposta = contratar(http, valor_total="0.01", prazo_dias=1)\n    assert resposta.status_code == 201\n    contrato = resposta.json()\n    assert contrato["valor_total"] == "1250.50" and contrato["prazo_dias"] == 15\n    assert contrato["status"] == "ativa" and contrato["observacoes"] == "Termos da contratação."\n    assert candidatas(http).json()["total"] == 0\n    cliente = listar(http).json()["itens"][0]\n    fornecedor = listar(http, "fornecedor", 2).json()["itens"][0]\n    assert cliente == fornecedor\n    assert cliente["cliente_razao_social"] == "Cliente Teste"\n    assert cliente["fornecedor_razao_social"] == "Fornecedor Teste"\n    assert cliente["solicitacao"]["status"] == "encerrada"\n    with sessoes() as banco:\n        assert banco.get(SolicitacaoServico, 1).status == "encerrada"\n        assert banco.get(CotacaoFornecedor, 1).status == "aceita"\n        assert banco.scalar(select(ContratacaoServico)).valor_total == Decimal("1250.50")\n\n\ndef test_criacao_repetida_nao_duplica_nem_altera_contrato(ambiente):\n    http, sessoes = ambiente\n    assert contratar(http).status_code == 201\n    repetida = contratar(http, observacoes="Tentativa repetida.")\n    assert repetida.status_code == 409 and repetida.json()["detail"] == "contratacao_ja_cadastrada"\n    with sessoes() as banco:\n        itens = banco.scalars(select(ContratacaoServico)).all()\n        assert len(itens) == 1 and itens[0].observacoes == "Termos da contratação."\n\n\n@pytest.mark.parametrize("campos,codigo", [\n    ({"cliente": 5}, 403), ({"cotacao": 2}, 404),\n    ({"solicitacao": 999}, 404), ({"solicitacao": 3, "cotacao": 3}, 409),\n    ({"solicitacao": 4, "cotacao": 4}, 403), ({"cliente": 2}, 403),\n])\ndef test_propostas_invalidas_e_empresa_errada_nao_criam_contratacao(ambiente, campos, codigo):\n    http, sessoes = ambiente\n    assert contratar(http, **campos).status_code == codigo\n    with sessoes() as banco:\n        assert banco.scalars(select(ContratacaoServico)).all() == []\n        assert banco.get(SolicitacaoServico, 1).status == "aberta"\n\n\n@pytest.mark.parametrize("situacao", ["encerrada", "cancelada"])\ndef test_solicitacao_fechada_nao_e_candidata_nem_pode_ser_contratada(ambiente, situacao):\n    http, sessoes = ambiente\n    with sessoes() as banco:\n        banco.get(SolicitacaoServico, 1).status = situacao\n        banco.commit()\n    assert candidatas(http).json()["total"] == 0\n    assert contratar(http).status_code == 409\n\n\ndef test_proposta_ja_aceita_permanece_contratavel_apos_validade_original(ambiente):\n    http, sessoes = ambiente\n    with sessoes() as banco:\n        banco.get(CotacaoFornecedor, 1).criada_em = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)\n        banco.commit()\n    assert candidatas(http).json()["total"] == 1\n    assert contratar(http).status_code == 201\n\n\ndef test_consultas_e_detalhes_limitados_as_empresas_participantes(ambiente):\n    http, _ = ambiente\n    contrato = contratar(http).json()["id"]\n    assert contratar(http, solicitacao=2, cotacao=2, cliente=5).status_code == 201\n    assert listar(http).json()["total"] == 1\n    assert listar(http, "fornecedor", 2).json()["total"] == 1\n    for perfil, parametro, dono, estranho in (("cliente", "empresa_cliente_id", 1, 5), ("fornecedor", "empresa_fornecedora_id", 2, 3)):\n        url = f"/api/v1/portal-{perfil}/contratacoes/{contrato}"\n        assert http.get(url, params={parametro: dono}).status_code == 200\n        assert http.get(url, params={parametro: estranho}).status_code == 404\n\n\ndef test_paginacao_contratos_e_candidatas_sem_perder_contagem(ambiente):\n    http, sessoes = ambiente\n    with sessoes() as banco:\n        for numero in (6, 7):\n            nova_solicitacao(banco, numero)\n            nova_cotacao(banco, numero, numero)\n        banco.commit()\n    pagina = candidatas(http, deslocamento=1, limite=1).json()\n    assert pagina["total"] == 3 and [i["id"] for i in pagina["itens"]] == [6]\n    for numero in (1, 6, 7):\n        assert contratar(http, solicitacao=numero, cotacao=numero).status_code == 201\n    pagina = listar(http, "fornecedor", 2, deslocamento=1, limite=1).json()\n    assert pagina["total"] == 3 and len(pagina["itens"]) == 1\n    assert pagina["itens"][0]["solicitacao_id"] == 6\n    assert candidatas(http).json()["total"] == 0\n\n\n@pytest.mark.parametrize("status", ["cancelada", "encerrada"])\ndef test_historico_conserva_status_e_nao_libera_nova_contratacao(ambiente, status):\n    http, sessoes = ambiente\n    identificador = contratar(http).json()["id"]\n    with sessoes() as banco:\n        item = banco.get(ContratacaoServico, identificador)\n        item.status = status\n        setattr(item, "cancelada_em" if status == "cancelada" else "encerrada_em", datetime.now(timezone.utc).replace(tzinfo=None))\n        banco.commit()\n    for perfil, empresa in (("cliente", 1), ("fornecedor", 2)):\n        assert listar(http, perfil, empresa).json()["itens"][0]["status"] == status\n    assert candidatas(http).json()["total"] == 0\n    assert contratar(http).status_code == 409\n\n\n@pytest.mark.parametrize("url,parametros,codigo", [\n    (CLIENTE + "/contratacoes", {}, 422),\n    (CLIENTE + "/cotacoes-aceitas", {"empresa_cliente_id": 0}, 422),\n    (CLIENTE + "/contratacoes", {"empresa_cliente_id": 2}, 403),\n    (FORNECEDOR + "/contratacoes", {"empresa_fornecedora_id": 1}, 403),\n    (FORNECEDOR + "/contratacoes", {"empresa_fornecedora_id": 999}, 404),\n    (CLIENTE + "/contratacoes", {"empresa_cliente_id": 1, "limite": 101}, 422),\n    (CLIENTE + "/contratacoes", {"empresa_cliente_id": 1, "deslocamento": -1}, 422),\n])\ndef test_consultas_exigem_empresa_valida_e_paginacao_limitada(ambiente, url, parametros, codigo):\n    http, _ = ambiente\n    assert http.get(url, params=parametros).status_code == codigo\n\n\ndef test_empresa_ambos_pode_consultar_nos_dois_perfis(ambiente):\n    http, _ = ambiente\n    assert listar(http, "cliente", 4).status_code == 200\n    assert listar(http, "fornecedor", 4).status_code == 200\n    assert candidatas(http, 4).status_code == 200\n\n\n@pytest.mark.parametrize("extensao,conteudo", [("ZIP", b"PK\\x03\\x04conteudo-zip"), ("rar", b"Rar!\\x1a\\x07conteudo-rar")])\ndef test_arquivos_zip_rar_acessiveis_so_aos_participantes_e_desvinculo_respeitado(ambiente, extensao, conteudo):\n    http, _ = ambiente\n    contrato = contratar(http).json()["id"]\n    enviada = http.post("/api/v1/solicitacoes-servico/1/arquivos-tecnicos", files={"file": (f"pecas.{extensao}", conteudo, "application/octet-stream")})\n    assert enviada.status_code == 201\n    arquivo = enviada.json()["id"]\n    for perfil, parametro, dono, estranho in (("cliente", "empresa_cliente_id", 1, 5), ("fornecedor", "empresa_fornecedora_id", 2, 3)):\n        url = f"/api/v1/portal-{perfil}/contratacoes/{contrato}/arquivos"\n        assert [i["id"] for i in http.get(url, params={parametro: dono}).json()] == [arquivo]\n        assert http.get(url, params={parametro: estranho}).status_code == 404\n        download = f"{url}/{arquivo}/download"\n        assert http.get(download, params={parametro: dono}).content == conteudo\n        assert http.get(download, params={parametro: estranho}).status_code == 404\n    assert http.delete(f"/api/v1/arquivos-tecnicos/{arquivo}").status_code == 204\n    url = f"{FORNECEDOR}/contratacoes/{contrato}/arquivos"\n    assert http.get(url, params={"empresa_fornecedora_id": 2}).json() == []\n    assert http.get(f"{url}/{arquivo}/download", params={"empresa_fornecedora_id": 2}).status_code == 404\n\n\ndef test_arquivo_de_outra_solicitacao_nao_pode_ser_baixado_por_contrato_proprio(ambiente):\n    http, _ = ambiente\n    contrato = contratar(http).json()["id"]\n    arquivo = http.post("/api/v1/solicitacoes-servico/2/arquivos-tecnicos", files={"file": ("outra.pdf", b"pdf-outro-cliente", "application/pdf")}).json()["id"]\n    url = f"{FORNECEDOR}/contratacoes/{contrato}/arquivos/{arquivo}/download"\n    resposta = http.get(url, params={"empresa_fornecedora_id": 2})\n    assert resposta.status_code == 404 and resposta.json()["detail"] == "arquivo_tecnico_nao_encontrado"\n\n\ndef test_observacoes_excessivas_nao_gravam_contrato(ambiente):\n    http, _ = ambiente\n    assert contratar(http, observacoes="x" * 5001).status_code == 422\n    assert listar(http).json()["total"] == 0\n'}
ALVOS = (APP_REL, ROUTER_REL, *(Path(nome) for nome in FONTES))
IMPORT_LINE = 'import PortalContratacoesPage from "./pages/contratacoes/PortalContratacoesPage";'


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
        raise RuntimeError("Campos ausentes no portal de contratações: " + ", ".join(sorted(ausentes)))

for perfil, empresa in (("cliente", "empresa_cliente_id"), ("fornecedor", "empresa_fornecedora_id")):
    base = "/api/v1/portal-" + perfil + "/contratacoes"
    for sufixo in ("", "/{contratacao_id}", "/{contratacao_id}/arquivos", "/{contratacao_id}/arquivos/{arquivo_id}/download"):
        op = paths.get(base + sufixo, {}).get("get")
        if not op:
            raise RuntimeError("Rota de contratação ausente: " + base + sufixo)
        params = {p["name"]: p for p in op.get("parameters", [])}
        dono = params.get(empresa, {})
        if dono.get("in") != "query" or not dono.get("required"):
            raise RuntimeError("Consulta de contratação sem empresa obrigatória.")
        if sufixo in ("", "/{contratacao_id}"):
            dados = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
            if not sufixo:
                if not {"limite", "deslocamento"}.issubset(params):
                    raise RuntimeError("Consulta de contratação sem paginação.")
                campos(dados, ("itens", "total", "limite", "deslocamento"))
                dados = schema(schema(dados["properties"]["itens"])["items"])
            campos(dados, ("id", "cotacao_id", "empresa_cliente_id", "empresa_fornecedora_id", "cliente_razao_social", "fornecedor_razao_social", "solicitacao", "status"))
            campos(schema(dados["properties"]["solicitacao"]), ("id", "processo_nome", "material_nome", "quantidade", "tolerancia_requerida_mm"))
op = paths.get("/api/v1/portal-cliente/cotacoes-aceitas", {}).get("get")
if not op:
    raise RuntimeError("Consulta de propostas prontas para contratar ausente.")
dados = schema(op["responses"]["200"]["content"]["application/json"]["schema"])
campos(dados, ("itens", "total", "deslocamento", "limite"))
campos(schema(schema(dados["properties"]["itens"])["items"]), ("id", "status", "decidida_por_empresa_id", "fornecedor_razao_social", "solicitacao"))
op = paths.get("/api/v1/portal-cliente/solicitacoes/{solicitacao_id}/contratacao", {}).get("post")
if not op:
    raise RuntimeError("Criação de contratação do portal não registrada.")
campos(op["requestBody"]["content"]["application/json"]["schema"], ("cotacao_id", "empresa_cliente_id", "observacoes"))
campos(op["responses"]["201"]["content"]["application/json"]["schema"], ("id", "cotacao_id", "empresa_cliente_id", "empresa_fornecedora_id", "valor_total", "prazo_dias", "status"))
print("CONTRATACOES_CLIENTE_FORNECEDOR_PAGINADAS_OK=True")
print("COTACOES_ACEITAS_E_CRIACAO_D8_OK=True")
print("DETALHES_E_ARQUIVOS_DAS_CONTRATACOES_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/api/roteador.py",
        "backend/app/models/contratacao.py", "backend/app/services/contratacao.py",
        "backend/app/schemas/contratacao.py", "backend/app/api/rotas/contratacoes.py",
        "backend/app/services/arquivo_tecnico.py", "backend/app/api/rotas/portal_fornecedor.py",
        "frontend/src/App.tsx", "frontend/package.json", "frontend/src/auth/AuthContext.tsx",
        "frontend/src/services/api.ts", "frontend/src/pages/client/ClientCotacoesPage.tsx",
        "frontend/src/pages/client/cotacoesCliente.ts", "frontend/src/pages/supplier/SupplierCotacoesPage.tsx",
        "frontend/src/pages/supplier/cotacoesFornecedor.ts", "tests/test_contratacoes.py",
    )
    if not all((raiz / nome).is_file() for nome in obrigatorios):
        raise RuntimeError("Execute este script na raiz do MEC-Servicos com contratação D8 e os portais D23/D24 instalados.")
    return raiz


def validar_fontes_existentes(originais: dict[Path, bytes | None]) -> None:
    for nome, fonte in FONTES.items():
        if nome.endswith(".py"):
            ast.parse(fonte, filename=nome)
        anterior = originais[Path(nome)]
        if anterior is not None:
            texto = anterior.decode("utf-8-sig").replace("\r\n", "\n").rstrip()
            if texto != fonte.replace("\r\n", "\n").rstrip():
                raise RuntimeError("Já existe um arquivo diferente no destino D25. Ele foi preservado: " + nome)


def atualizar_roteador(texto: str) -> str:
    arvore = ast.parse(texto)
    modulo = "backend.app.api.rotas.portal_contratacoes"
    alias = "roteador_portal_contratacoes"
    importacoes = [n for n in arvore.body if isinstance(n, ast.ImportFrom) and n.module == modulo]
    for n in importacoes:
        if len(n.names) != 1 or n.names[0].name != "roteador" or n.names[0].asname != alias:
            raise RuntimeError("O import do portal de contratações já usa outro formato. O roteador foi preservado.")
    if len(importacoes) > 1:
        raise RuntimeError("Há imports duplicados do portal de contratações.")
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "roteador_api" and n.func.attr == "include_router"
                and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id == alias]
    if len(chamadas) > 1 or any(n.keywords or len(n.args) != 1 for n in chamadas):
        raise RuntimeError("O registro do portal de contratações já usa outro formato.")
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
        candidatas = [item for item in rotas if grupo["fim_abertura"] <= item["inicio"] < item["fim"] <= grupo["fim"] and item["path"] == "contratacoes"]
        if len(candidatas) != 1 or not candidatas[0]["auto_fecha"]:
            raise RuntimeError("Não encontrei uma única rota de contratações no portal " + perfil + ".")
        rota = candidatas[0]
        abertura = texto[rota["inicio"]:rota["fim"]]
        componentes = list(re.finditer(r"<(?:ModulePage|PortalContratacoesPage)\b", abertura))
        if len(componentes) != 1:
            raise RuntimeError("A rota de contratações do " + perfil + " usa outra tela. Ela foi preservada.")
        inicio = rota["inicio"] + componentes[0].start()
        fim = fim_tag(texto, inicio)
        if not texto[inicio:fim].rstrip().endswith("/>"):
            raise RuntimeError("O componente de contratações do " + perfil + " possui filhos. Ele foi preservado.")
        novo = f'<PortalContratacoesPage perfil="{perfil}" />'
        if texto[inicio:fim] != novo:
            trocas.append((inicio, fim, novo))
    atualizado = texto
    for inicio, fim, novo in sorted(trocas, reverse=True):
        atualizado = atualizado[:inicio] + novo + atualizado[fim:]
    existente = re.search(r'''import\s+PortalContratacoesPage\s+from\s*["']\./pages/contratacoes/PortalContratacoesPage["']\s*;?''', atualizado)
    if not existente:
        if "./pages/contratacoes/PortalContratacoesPage" in atualizado:
            raise RuntimeError("O import de contratações usa outro formato. Nenhum fonte foi alterado.")
        quebra = "\r\n" if "\r\n" in atualizado else "\n"
        atualizado = IMPORT_LINE + quebra + atualizado
    return atualizado

VALIDACAO_CONTRATO = r'''
from sqlalchemy import UniqueConstraint
from backend.app.principal import app
from backend.app.models.contratacao import ContratacaoServico
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
        raise RuntimeError("Campos ausentes no contrato D8: " + ", ".join(sorted(ausentes)))

esperados = ("id", "solicitacao_id", "cotacao_id", "empresa_cliente_id", "empresa_fornecedora_id", "valor_total", "prazo_dias", "observacoes", "status", "criada_em", "cancelada_em", "encerrada_em")
for metodo, codigo in (("get", "200"), ("post", "201")):
    op = paths.get("/api/v1/solicitacoes-servico/{solicitacao_id}/contratacao", {}).get(metodo)
    if not op:
        raise RuntimeError("Rota D8 ausente: " + metodo)
    campos(op["responses"][codigo]["content"]["application/json"]["schema"], esperados)
    if metodo == "post":
        corpo = schema(op["requestBody"]["content"]["application/json"]["schema"])
        campos(corpo, ("cotacao_id", "empresa_cliente_id", "observacoes"))
        if set(corpo.get("required", [])) != {"cotacao_id", "empresa_cliente_id"}:
            raise RuntimeError("O corpo de criação difere do contrato D8.")
for nome in esperados:
    if not hasattr(ContratacaoServico, nome):
        raise RuntimeError("Modelo de contratação sem o campo " + nome)
unicas = [set(c.columns.keys()) for c in ContratacaoServico.__table__.constraints if isinstance(c, UniqueConstraint)]
if {"solicitacao_id"} not in unicas or {"cotacao_id"} not in unicas:
    raise RuntimeError("As restrições de contratação única do D8 estão ausentes.")
if not {".zip", ".rar"}.issubset(ServicoArquivoTecnico.ALLOWED_EXTENSIONS):
    raise RuntimeError("O suporte a ZIP/RAR do D22 ainda não está instalado.")
for recurso in ("/oportunidades", "/cotacoes"):
    if "get" not in paths.get("/api/v1/portal-fornecedor" + recurso, {}):
        raise RuntimeError("O portal do fornecedor D24 ainda não está instalado.")
print("CONTRATO_CONTRATACAO_D8_OK=True")
print("RESTRICOES_CONTRATACAO_UNICA_OK=True")
print("PORTAIS_D23_D24_E_ARQUIVOS_ZIP_RAR_OK=True")
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
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d25_", delete=False) as arquivo:
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
        "MEC-Serviços D25 — Contratações nos Portais do Cliente e Fornecedor",
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
    print("MEC-Serviços D25 — Contratações nos Portais do Cliente e Fornecedor", flush=True)
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
        backup = raiz / "_mec_backups" / ("D25_PORTAIS_CONTRATACOES_" + carimbo)
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
        print("CONTRATACOES_TELAS_ROTAS_E_BACKEND_OK=True", flush=True)
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
    print("Reinicie o backend e atualize /cliente/contratacoes com Ctrl+F5.", flush=True)
    print("Como cliente, abra Cotações para contratar, revise uma proposta aceita e confirme a contratação de teste.", flush=True)
    print("Confira a contratação em /cliente/contratacoes e /fornecedor/contratacoes, incluindo os arquivos técnicos.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
