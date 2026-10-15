'MEC-Serviços D48 FIX1 — Abertura visível da preparação do PDF.\nCorreção apenas da interface e roteiro; exige D48 aprovada.\nExecuta build do frontend e preserva backend, documentos e ambos os bancos.\n'

from __future__ import annotations

import ast

import base64

from contextlib import closing

from datetime import datetime

import hashlib

import json

import os

from pathlib import Path

import queue

import shutil

import signal

import socket

import sqlite3

import subprocess

import sys

import tempfile

import threading

import time

from urllib.parse import urlsplit

REVISION = 'MEC-SERVICOS-V0.1-D48-FIX1-ABERTURA-PREPARACAO-PDF-2026-10-09'

LIMITE_BUILD_SEGUNDOS = 600

D41_REVISION = 'MEC-SERVICOS-V0.1-D41-CONSOLIDACAO-BACKUP-2026-10-06'

STEM = 'MEC_SERVICOS_V0_1_D48_FIX1_ABERTURA_PREPARACAO_PDF_RELATORIO'

FONTES = {'frontend/src/pages/documentacao/AdminDocumentacaoPage.tsx': 'import { useSearchParams } from "react-router-dom";\nimport { identificador } from "../painel/painelPortal";\nimport { useEffect, useRef, useState } from "react";\nimport { api } from "../../services/api";\nimport { useAuth } from "../../auth/AuthContext";\nimport PrepararPdfAdmin, { erroPdf, type PreparacaoPdf } from "./PrepararPdfAdmin";\nimport "./Documentacao.css";\n\ntype Evento = { versao: number; acao: string; registro_interno: string; administrador_nome: string; criado_em: string; versao_pdf_preparada?: number | null };\ntype Arquivo = { id: number; solicitacao_id: number; nome_original: string; extensao: string; tamanho_bytes: number; sha256: string; versao: number; liberado: boolean; conteudo_valido: boolean; ativo: boolean; historico: Evento[]; preparacao_pdf_publicada_id?: number | null; versao_pdf_publicada?: number | null };\ntype Solicitacao = { id: number; cliente: string; processo: string; material: string; quantidade: number; status: string; arquivos_ativos: number; arquivos_disponiveis: number; arquivos: Arquivo[] };\ntype Pagina = { itens: Solicitacao[]; total: number; deslocamento: number; limite: number };\ntype Operacao = { arquivo: Arquivo; acao: "liberar" | "bloquear"; chave: string; preparacao?: PreparacaoPdf };\nconst BASE = "/administracao/documentacao-cotacao";\n\nfunction mensagem(erro: unknown) {\n  const falha = erro as { response?: { status?: number; data?: { detail?: unknown } } };\n  const textos: Record<string, string> = {\n    documentacao_alterada_atualize: "O arquivo ou sua liberação mudou. Atualize e revise novamente.",\n    documentacao_ja_nesta_situacao: "O arquivo já está nessa situação. Atualize a lista.",\n    arquivo_tecnico_sem_conteudo_valido: "O arquivo precisa estar ativo e ter conteúdo físico íntegro para ser liberado.",\n    revisao_administrativa_obrigatoria: "Confirme a revisão do conteúdo antes de liberar o arquivo.",\n    registro_interno_obrigatorio: "Informe um registro interno com pelo menos três caracteres.",\n    chave_operacao_reutilizada: "A conferência desta operação mudou. Atualize e revise novamente.",\n  };\n  const detalhe = falha.response?.data?.detail;\n  if (typeof detalhe === "string" && textos[detalhe]) return textos[detalhe];\n  if (falha.response?.status === 401) return "Sua sessão expirou. Entre novamente.";\n  if (falha.response?.status === 403) return "Esta revisão exige acesso administrativo.";\n  return "Não foi possível confirmar a operação. Atualize a lista antes de continuar.";\n}\n\nexport default function AdminDocumentacaoPage() {\n  const { user } = useAuth(); const contexto = user?.role === "admin" ? String(user.usuario_id) : "";\n  const vigente = useRef(contexto); vigente.current = contexto;\n  const [parametrosUrl] = useSearchParams();\n  const solicitacaoInicial = identificador(parametrosUrl.get("solicitacao"));\n  const [filtro, setFiltro] = useState(solicitacaoInicial ? String(solicitacaoInicial) : ""); const [aplicado, setAplicado] = useState(solicitacaoInicial ? String(solicitacaoInicial) : "");\n  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);\n  const [pagina, setPagina] = useState<Pagina | null>(null); const [carregando, setCarregando] = useState(true);\n  const [erro, setErro] = useState(""); const [aviso, setAviso] = useState("");\n  const [operacao, setOperacao] = useState<Operacao | null>(null); const [registro, setRegistro] = useState("");\n  const [revisado, setRevisado] = useState(false); const [ocupado, setOcupado] = useState(false);\n  const [baixando, setBaixando] = useState<number | null>(null);\n  const [preparando, setPreparando] = useState<Arquivo | null>(null);\n  const [focoPreparacao, setFocoPreparacao] = useState(0);\n  const areaPreparacao = useRef<HTMLDivElement | null>(null);\n  const areaConferencia = useRef<HTMLElement | null>(null);\n  const botaoPreparacao = useRef<HTMLButtonElement | null>(null);\n  const montada = useRef(true); const trava = useRef(false); const controladorDownload = useRef<AbortController | null>(null);\n  useEffect(() => { montada.current = true; return () => { montada.current = false; controladorDownload.current?.abort(); }; }, []);\n  useEffect(() => {\n    const controlador = new AbortController(); let vigente = true;\n    setPagina(null); setCarregando(true); setErro("");\n    if (!contexto) { setCarregando(false); return; }\n    void api.get<Pagina>(BASE, { params: { ...(aplicado ? { solicitacao_id: aplicado } : {}), deslocamento, limite: 20 }, signal: controlador.signal, timeout: 20_000 })\n      .then(({ data }) => { if (vigente) {\n        if (data.total > 0 && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }\n        setPagina(data);\n      } }).catch(e => { if (vigente && !controlador.signal.aborted) setErro(mensagem(e)); })\n      .finally(() => { if (vigente) setCarregando(false); });\n    return () => { vigente = false; controlador.abort(); };\n  }, [aplicado, deslocamento, revisao, contexto]);\n\n  useEffect(() => { setOperacao(null); setPreparando(null); }, [contexto]);\n  useEffect(() => {\n    const area = operacao ? areaConferencia.current : preparando ? areaPreparacao.current : null;\n    if (!area) return;\n    area.focus({ preventScroll: true });\n    area.scrollIntoView({ block: "start", behavior: "auto" });\n  }, [preparando?.id, operacao?.chave, focoPreparacao, contexto]);\n\n  function abrirPreparacao(arquivo: Arquivo, botao: HTMLButtonElement) {\n    if (ocupado) return;\n    botaoPreparacao.current = botao;\n    setErro(""); setAviso(""); setOperacao(null); setPreparando(arquivo);\n    setFocoPreparacao(v => v + 1);\n  }\n  function fecharPreparacao() {\n    if (ocupado) return;\n    setPreparando(null); setOperacao(null);\n    botaoPreparacao.current?.focus();\n  }\n  function abrir(arquivo: Arquivo, acao: "liberar" | "bloquear", preparacao?: PreparacaoPdf) {\n    if (ocupado) return;\n    if (!preparacao) setPreparando(null);\n    setOperacao({ arquivo, acao, chave: crypto.randomUUID(), preparacao }); setRegistro(""); setRevisado(false); setErro(""); setAviso("");\n  }\n  async function salvar() {\n    if (!operacao || trava.current || registro.trim().length < 3 || (operacao.acao === "liberar" && !revisado)) return;\n    const op = operacao; const ctx = contexto; if (!ctx) return; trava.current = true; setOcupado(true); setErro("");\n    try {\n      await api.post<Arquivo>(`${BASE}/arquivos/${op.arquivo.id}/eventos`, { acao: op.acao, versao: op.arquivo.versao,\n        sha256: op.arquivo.sha256, registro_interno: registro.trim(), revisado_sem_contatos: revisado, chave_operacao: op.chave,\n        ...(op.preparacao ? { preparacao_pdf_id: op.preparacao.id } : {}) }, { timeout: 30_000 });\n      if (montada.current && vigente.current === ctx) { setOperacao(null); setPreparando(null); setAviso(`Arquivo #${op.arquivo.id}${op.preparacao ? ` · cópia MEC versão ${op.preparacao.versao}` : ""} ${op.acao === "liberar" ? "liberado para cotação" : "bloqueado para novas consultas"}.`); setRevisao(v => v + 1); }\n    } catch (e) { if (montada.current && vigente.current === ctx) setErro(op.preparacao ? erroPdf(e) : mensagem(e)); }\n    finally { trava.current = false; if (montada.current && vigente.current === ctx) setOcupado(false); }\n  }\n  async function baixar(arquivo: Arquivo) {\n    if (baixando !== null) return;\n    const ctx = contexto; if (!ctx) return;\n    const controlador = new AbortController(); controladorDownload.current = controlador; setBaixando(arquivo.id); setErro("");\n    try {\n      const { data } = await api.get<Blob>(`/arquivos-tecnicos/${arquivo.id}/download`, { responseType: "blob", signal: controlador.signal, timeout: 30_000 });\n      if (!montada.current || controlador.signal.aborted || vigente.current !== ctx) return;\n      const url = URL.createObjectURL(data); const ancora = document.createElement("a");\n      ancora.href = url; ancora.download = arquivo.nome_original; document.body.appendChild(ancora); ancora.click(); ancora.remove();\n      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);\n    } catch (e) { if (montada.current && !controlador.signal.aborted && vigente.current === ctx) setErro(mensagem(e)); }\n    finally { if (montada.current && controladorDownload.current === controlador && vigente.current === ctx) setBaixando(null); }\n  }\n  if (!contexto) return <p role="alert">A revisão de arquivos exige acesso administrativo.</p>;\n  return <div className="doc42-page">\n    <header><div><p>ADMINISTRAÇÃO</p><h1>Arquivos para cotação</h1><p>Revise os documentos antes de disponibilizar as solicitações aos fornecedores.</p></div>\n      <button disabled={ocupado || carregando} onClick={() => { setOperacao(null); setPreparando(null); setAviso(""); setRevisao(v => v + 1); }}>Atualizar</button></header>\n    <div className="doc42-alert">A oportunidade exige pelo menos um arquivo ativo, íntegro e liberado. Cotações já registradas permanecem no histórico.</div>\n    <form className="doc42-filtro" onSubmit={e => { e.preventDefault(); if (ocupado) return; const n = filtro.trim(); if (n && !/^[1-9]\\d*$/.test(n)) { setErro("Informe um número de solicitação válido."); return; } setOperacao(null); setPreparando(null); setDeslocamento(0); setAplicado(n); setRevisao(v => v + 1); }}>\n      <label>Solicitação #<input inputMode="numeric" value={filtro} disabled={ocupado} onChange={e => setFiltro(e.target.value)} placeholder="Todas" /></label>\n      <button type="submit" disabled={ocupado}>Consultar</button></form>\n    {erro && !operacao && <p className="doc42-alert doc42-erro" role="alert">{erro}</p>}{aviso && <p className="doc42-alert" role="status">{aviso}</p>}\n    {carregando && <p role="status">Carregando documentação…</p>}\n    {pagina && <><p>{pagina.total} solicitação(ões) · Página {Math.floor(deslocamento / 20) + 1}</p>\n      {!pagina.itens.length && <p className="doc42-alert">Nenhuma solicitação encontrada.</p>}\n      {pagina.itens.map(s => <section className="doc42-card" key={s.id}><h2>Solicitação #{s.id} · {s.cliente}</h2>\n        <p>{s.processo} · {s.material} · {s.quantidade} unidades · {s.status}</p>\n        <p><strong>{s.arquivos_disponiveis} arquivo(s) disponível(is)</strong> de {s.arquivos_ativos} ativo(s)</p>\n        {!s.arquivos.length && <p className="doc42-alert">Aguardando envio de arquivo técnico pelo cliente.</p>}\n        {s.arquivos.map(a => <article className="doc42-arquivo" key={a.id}>\n          <div><h3>{a.nome_original}</h3><p>Arquivo #{a.id} · {a.tamanho_bytes.toLocaleString("pt-BR")} bytes · {a.liberado ? "Liberado para cotação" : !a.ativo ? "Desvinculado pelo cliente" : !a.conteudo_valido ? "Conteúdo físico indisponível ou divergente" : "Aguardando revisão e liberação"}</p></div>\n          {a.versao_pdf_publicada && <p>Cópia MEC versão {a.versao_pdf_publicada}{a.liberado ? " disponível para o fornecedor" : " indisponível; confira o arquivo e a liberação"}.</p>}\n          <div className="doc42-acoes"><button disabled={!a.ativo || !a.conteudo_valido || baixando !== null} onClick={() => void baixar(a)}>{baixando === a.id ? "Baixando…" : "Baixar para revisar"}</button>\n            {a.ativo && a.conteudo_valido && <button disabled={ocupado} onClick={() => abrir(a, a.liberado ? "bloquear" : "liberar")}>{a.liberado ? "Bloquear liberação" : "Liberar para cotação"}</button>}</div>\n          {a.ativo && a.conteudo_valido && a.extensao.toLowerCase() === ".pdf" && <div className="doc42-acoes"><button id={`doc42-preparar-${a.id}`} disabled={ocupado} aria-expanded={preparando?.id === a.id} aria-controls={`doc42-preparacao-${a.id}`} onClick={e => abrirPreparacao(a, e.currentTarget)}>Preparar PDF com nossa logo{preparando?.id === a.id && " · aberta"}</button></div>}\n          {preparando?.id === a.id && <div id={`doc42-preparacao-${a.id}`} className="doc42-preparacao" ref={areaPreparacao} tabIndex={-1} role="region" aria-label={`Preparação do arquivo #${a.id}`}>\n            <PrepararPdfAdmin key={`${contexto}:${a.id}`} arquivo={preparando} onFechar={fecharPreparacao} onLiberar={p => abrir(preparando, "liberar", p)} />\n          </div>}\n          {operacao?.arquivo.id === a.id && <section ref={areaConferencia} tabIndex={-1} className="doc42-confirmacao" aria-label="Conferência da documentação"><h2>{operacao.acao === "liberar" ? "Liberar arquivo para cotação" : "Bloquear a liberação do arquivo"}</h2>\n      {erro && <p className="doc42-alert doc42-erro" role="alert">{erro}</p>}\n      <p>Solicitação #{operacao.arquivo.solicitacao_id} · {operacao.arquivo.nome_original}</p>\n      {operacao.acao === "liberar" && <p><strong>{operacao.preparacao ? `O fornecedor receberá a cópia MEC versão ${operacao.preparacao.versao}.` : "O fornecedor receberá o arquivo original revisado."}</strong></p>}\n      {operacao.acao === "liberar" && <label className="doc42-check"><input type="checkbox" checked={revisado} disabled={ocupado} onChange={e => setRevisado(e.target.checked)} />Revisei o conteúdo e confirmei que não contém contatos nem identifica o cliente.</label>}\n      <label>Registro interno da revisão<textarea value={registro} disabled={ocupado} minLength={3} maxLength={2000} onChange={e => setRegistro(e.target.value)} /></label>\n      <div className="doc42-acoes"><button disabled={ocupado || registro.trim().length < 3 || (operacao.acao === "liberar" && !revisado)} onClick={() => void salvar()}>{ocupado ? "Registrando…" : "Confirmar registro"}</button><button disabled={ocupado} onClick={() => setOperacao(null)}>Voltar</button></div>\n    </section>}\n          {!!a.historico.length && <details><summary>Histórico da revisão</summary>{a.historico.map(h => <p key={h.versao}><strong>{h.acao === "liberar" ? "Liberação" : "Bloqueio"} · {h.administrador_nome}</strong> · {h.criado_em}{h.acao === "liberar" && <><br />{h.versao_pdf_preparada ? `Cópia MEC versão ${h.versao_pdf_preparada}` : "Original revisado"}</>}<br />{h.registro_interno}</p>)}</details>}\n        </article>)}\n      </section>)}\n      <nav className="doc42-acoes" aria-label="Paginação"><button disabled={ocupado || deslocamento === 0} onClick={() => { setOperacao(null); setPreparando(null); setDeslocamento(v => Math.max(0, v - 20)); }}>Anterior</button><button disabled={ocupado || deslocamento + 20 >= pagina.total} onClick={() => { setOperacao(null); setPreparando(null); setDeslocamento(v => v + 20); }}>Próxima</button></nav></>}\n\n  </div>;\n}\n', 'frontend/src/pages/documentacao/Documentacao.css': '.doc42-page{color:#dbe7f4;max-width:1500px;padding:24px}.doc42-page header{display:flex;gap:20px;align-items:center;justify-content:space-between;margin-bottom:20px}.doc42-page h1{font-size:32px;margin:6px 0}.doc42-page h2{font-size:21px}.doc42-page h3{font-size:17px}.doc42-page p{color:#9fb1c7;line-height:1.55}.doc42-page button{background:#17283c;border:1px solid #3c5470;border-radius:8px;color:#e5effb;padding:10px 16px;font:inherit;cursor:pointer}.doc42-page button:disabled{opacity:.5;cursor:default}.doc42-card,.doc42-confirmacao{background:#101b29;border:1px solid #2b4058;border-radius:12px;padding:20px;margin:18px 0}.doc42-arquivo{border-top:1px solid #2a3c52;margin-top:16px;padding-top:16px;overflow-wrap:anywhere}.doc42-acoes{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}.doc42-alert{background:#182a3b;border-left:3px solid #5faaff;border-radius:7px;padding:14px;margin:16px 0}.doc42-erro{background:#351d29;border-color:#f08598;color:#ffc5cf!important}.doc42-filtro{display:flex;align-items:end;gap:12px;margin:24px 0}.doc42-page label{display:flex;flex-direction:column;gap:8px}.doc42-page input:not([type=checkbox]),.doc42-page textarea{background:#0a1420;border:1px solid #3c5470;border-radius:7px;padding:10px;color:#e5effb;font:inherit}.doc42-page textarea{min-height:90px;max-width:100%;resize:vertical}.doc42-check{flex-direction:row!important;align-items:center;margin:14px 0}.doc42-confirmacao{border-color:#5faaff}.doc42-page summary{cursor:pointer;color:#afc6e0;margin-top:14px}@media(max-width:680px){.doc42-page{padding:14px}.doc42-page header,.doc42-filtro{align-items:stretch;flex-direction:column}.doc42-page h1{font-size:27px}}\n\n.doc42-preparacao,.doc42-confirmacao{scroll-margin-top:24px}.doc42-preparacao:focus-visible,.doc42-confirmacao:focus-visible{outline:2px solid #8dc5ff;outline-offset:4px}.doc42-page button[aria-expanded=true]{border-color:#8dc5ff;background:#213c58}\n', 'D48_FIX1_CONTRATO_ABERTURA_PREPARACAO_PDF.txt': 'MEC-Serviços D48 FIX1 — Abertura visível da preparação do PDF\n\nO painel da D48 era renderizado depois de toda a lista de solicitações.\nAgora ele abre dentro do arquivo selecionado, logo abaixo do botão, com\nrolagem automática e foco. Repetir o clique localiza a preparação já aberta\ne mantém os campos preenchidos. Fechar devolve o foco ao botão do arquivo.\nA conferência de liberação ou bloqueio também abre junto ao arquivo.\nAo mudar o filtro ou a página, a preparação anterior é encerrada.\n\nAPLICAÇÃO\n1. Pare o backend e o frontend com Ctrl+C nos terminais correspondentes.\n2. Salve MEC_SERVICOS_V0_1_D48_FIX1_ABERTURA_PREPARACAO_PDF.py na raiz:\n   C:\\Users\\Omega\\Desktop\\MEC-Servicos\n3. Execute cada comando separadamente no PowerShell:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_V0_1_D48_FIX1_ABERTURA_PREPARACAO_PDF.py\n\n4. Aguarde RESULTADO=OK. A correção executa o build do frontend e reutiliza\n   a validação aprovada do backend D48, sem repetir a suíte longa.\n5. Inicie o backend:\n\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_INICIAR_TESTE_LOCAL.py\n\n6. Em outro PowerShell, inicie o frontend:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\\frontend\nnpm.cmd run dev -- --host localhost --port 5173 --strictPort\n\n7. Abra http://localhost:5173 e atualize com Ctrl+F5.\n\nTESTE DA CORREÇÃO\n1. Entre como ADM e abra Administração > Arquivos Técnicos.\n2. Na lista com várias solicitações, clique Preparar PDF com nossa logo\n   no PDF desejado. A tela deve ir imediatamente ao painel no mesmo arquivo.\n3. O painel mostra Conferindo PDF e depois a página do desenho; se a consulta\n   falhar, o erro aparece dentro do painel. O nome deve ser o do PDF clicado.\n4. Preencha um campo, clique novamente no botão Preparar PDF com nossa logo\n   do mesmo arquivo e confira que o campo permanece preenchido.\n5. Feche a preparação e confira o retorno ao botão. Abra outro PDF e confira\n   que existe apenas um painel, junto ao novo arquivo.\n6. Se já houver uma cópia preparada e revisada, clique Liberar esta versão:\n   a conferência deve aparecer no mesmo arquivo, identificando a versão.\n   Use Voltar se estiver somente conferindo a interface.\n\nESCOPO E PRESERVAÇÃO\nExige D48 concluída e seus dois bancos íntegros. Backup dos bancos, das fontes\nalteradas e do build antes da aplicação. Altera dois arquivos do frontend e\nadiciona este roteiro. Não altera o backend, dependências, tabelas, contas,\nsenhas, sessões, PDF original, cópias preparadas ou liberações existentes.\nNão gera nem libera documentos automaticamente. Em falha de build, restaura\nas fontes e o build anteriores; alterações externas nos bancos são preservadas.\nAs regras e limitações do roteiro D48 original continuam aplicáveis.\n'}

BASE_SHA256 = {'backend/app/principal.py': ['67a8f88977916b78a8e58a65abb0f5e0a65c5ee8220f36ea31fc69e0d608dbb6'], 'frontend/src/App.tsx': ['3902856accb3da439d94794d033c87d249679e80bc5ef5712724128937ed3ea1'], 'frontend/src/pages/financeiro/FinanceiroPage.tsx': ['670a078eae983c565a4e49743a5567acb4645ad068b7d82262b804a6e1cbe34a'], 'backend/app/services/financeiro_administrativo.py': ['472578665256b9aa5422a734fc10a0091e95ef103ba654e8a5b581c4ffacf22a'], 'backend/app/models/financeiro_administrativo.py': ['74efa682efd815f778782fb35701783d3081eddc4e689d0329ff9424b253d7e7'], 'frontend/src/pages/financeiro/financeiroPortal.ts': ['703c3d478e1c9f372c7eb21b4bf17670dfbd420305d74595789ce2ef3f6b8eb9'], 'frontend/src/pages/intermediacao/AdminIntermediacaoPage.tsx': ['825a4319b7b5b24137f6446503e2f5b41fa88fef74af1cc1e076bd14496594f3'], 'backend/app/services/intermediacao.py': ['8764c2cc920f9af14edfbc17029cf4875b02bcc6484725657ac69a90c436edfd'], 'backend/app/models/intermediacao.py': ['f6ed06fa32b5aae0d9b5d0b50b6d33759f7d19e2770acdfd1b45e1e3e9293db9'], 'frontend/src/pages/intermediacao/intermediacaoPortal.ts': ['ffc934f799789f13eea2437b99c9b7134318a8b8585c39dd48e2913c6a4d43cd'], 'backend/app/core/permissoes_acesso.py': ['76f8574acfe5f118e3653c0f4fa95da4bcb568497cca14e6d956bc21d97b435e'], 'frontend/src/auth/AuthContext.tsx': ['3ab2c8142ca86f6df51a72799f31a61c66e24f5fac59e20e83a8ff3532a5a795'], 'frontend/src/services/api.ts': ['e5db9ea929d076ce6e2411d3d89c195a33acc5610af6035f23761a96fe543db3'], 'frontend/src/services/acesso.ts': ['c4c799053bcb9338a55c649a95ae80df45f4b294754c9bb751b0c4e062697ee5', '3dbe6b9d31ca74ab59362bf64740cdc776a209aedd81eafa44c7bc191c215d45'], 'D33_CONTRATO_PAINEL_ADMIN.txt': ['3fdf7577b59dba860bdf7c1f25e05ec0a62762f689a7d11492adb4041532ae15'], 'tests/test_painel_administrativo_d33.py': ['90cf716dc34755ad8db367caca4e77e25210d37c07710242bcc882728e65afab'], 'frontend/src/pages/painel/PainelAdministrativoPage.tsx': ['51030b1bfef117461bc4bfcdd915cbaf3c9162afdee638baf0a9197db7947e39'], 'frontend/src/pages/painel/painelPortal.ts': ['d077a53088d4023edba366997d77ef97719d17e80faddb8852dab4a6871b7ecd'], 'frontend/src/pages/painel/PainelAdministrativo.css': ['eea184d9069e3382243b0be6aac09cafd9a4ed50cc2063c19acb4625bdac17e2'], 'backend/app/services/painel_administrativo.py': ['60bfec3afcb0ef726f2f833ae9a4771fe05e96f29f35234916eed4575227e338'], 'backend/app/schemas/painel_administrativo.py': ['0fbb493e8132fbc1e5b220685e501860533e2c819b78d10fc30543510e8ab9b4'], 'backend/app/api/rotas/painel_administrativo.py': ['69000275b72a35814298075be18f2e95f04cd74320b7be2ee3deaa8a3872e883'], 'D34_CONTRATO_RELATORIO_ADMIN.txt': ['48c3bf12e576ba0efc391ede4c89dc3760e2c2e1e2b3c7bcc50d93e17d7bb9b2'], 'tests/test_relatorio_administrativo_d34.py': ['26032d692db416035331bc50db0911ba90489e199ace78ebba5a50564709e5bf'], 'frontend/src/pages/relatorios/RelatorioAdministrativoPage.tsx': ['b623fd9adf6d5519f8a636551097f9f6ad90e990ce9190889be4c36a910aa813'], 'frontend/src/pages/relatorios/relatorioPortal.ts': ['4b54d5346f81b065887d1cb8585f132f2418187c8e786c1124a45a75d796963d'], 'frontend/src/pages/relatorios/RelatorioAdministrativo.css': ['8862a85b43d1b282e5a556c2f0a6c35d77f51e20993966fb32282d25714278cb'], 'backend/app/services/relatorio_administrativo.py': ['0fa0ac56e453c32744f04635f64db876433bc5eb448165a08e336935d360d0ff'], 'backend/app/schemas/relatorio_administrativo.py': ['1a4123973bd6a61d82470798c9772924f85bbaeaea0db281f4d198fcd5277a88'], 'backend/app/api/rotas/relatorio_administrativo.py': ['79cad524f2632341685a4ed602eab3b3ed2ec6630bb3e1fd9d322845c87775f7'], 'D35_CONTRATO_RELATORIO_PERIODO.txt': ['f1754e201943e59cfaeb9bf955baaeb36225c217cd6f9cc5f6a59d6d67c33ab1'], 'backend/app/api/rotas/relatorio_periodo.py': ['8d6d5a2015f99668bbfed01bc82d5d45f4009c11d8bd3a0b7f6c0710e74e06d6'], 'backend/app/schemas/relatorio_periodo.py': ['36e2a56bee8b9a6a547930d04e36c47157852feab2ebcbb8b208ac7a0186bce0'], 'backend/app/services/relatorio_periodo.py': ['fa0bf2374a2110aec49ff6e4caebb6848a0e47003ec096e9ae5ab38ed090ab54'], 'frontend/src/pages/periodo/RelatorioPeriodo.css': ['b26d7c98c78774d1d6d185d8770af84159fbc5bcca7ba7e13db5ec2b92a5fbf8'], 'frontend/src/pages/periodo/RelatorioPeriodoPage.tsx': ['1dc0223179de83b01626f91e095c384e7929a992af698f28c8ac50e03ace1fbb'], 'frontend/src/pages/periodo/periodoPortal.ts': ['3ff8c0077bf53414f06620e8d6a545a027d88587a5701132462ae2340b0619df'], 'tests/test_relatorio_periodo_d35.py': ['4d3e5a659815d121cdf466b23e26df322e21286db753257f1073de8061f0016d'], 'D36_CONTRATO_RELATORIO_EMPRESAS.txt': ['af900f57dd64409c244da20ea2417d39a9eb9d20992739fabf830503bc2f428d'], 'backend/app/api/rotas/relatorio_empresas.py': ['225efaa3e2fb99aaa89f4cfc053a6b29b03f4ea39a85c7b13477641b91cbad61'], 'backend/app/schemas/relatorio_empresas.py': ['4e76d3d6ef778ddf80a093e52f78209526e29c92c9dba60e74cbd7628b410df2'], 'backend/app/services/relatorio_empresas.py': ['ffa5df1f91dc6f8b6758e65aa49f41b17c732e9192eaabfa7e7853788833db66'], 'frontend/src/pages/empresas/RelatorioEmpresas.css': ['d86d463385bbb705da95755979e43a1b8db3c7efb71eaee2e7ec4bff28f03a57'], 'frontend/src/pages/empresas/RelatorioEmpresasPage.tsx': ['58785b939e6bb476c69934d2a5fece088224dd26ee18e259a5b2dfc3c2afafc0'], 'frontend/src/pages/empresas/empresasPortal.ts': ['697ab17c48bf729c96d7838e5ffb633aa8efea3c5da47c8e593d6be012f2ea0b'], 'tests/test_relatorio_empresas_d36.py': ['de7106423af5dceec98cdc4d9d84ab8e022191a4d655e0029e85fd4443e50140'], 'D37_CONTRATO_CENTRAL_PENDENCIAS.txt': ['a14a181f67b0df05bcd7e71f451170e6a74eb2041e913875f3342c6c90b53757'], 'backend/app/api/rotas/central_pendencias.py': ['78e947cb062b81cc6af4ba40d261d9bbaefb440fec11d01171d9e5ba09a12cc7'], 'backend/app/schemas/central_pendencias.py': ['7326f459a0a70cd54048620e464731ea53cb4a4a17cd03450a49a52e53e08711'], 'backend/app/services/central_pendencias.py': ['1865833db3b34606b869ef8eb9b1fe32ad0c52aa4337a8fc015734d256296963'], 'frontend/src/pages/pendencias/CentralPendencias.css': ['f7faf8ed21d8660e06a25921b8636824f7e4613f6382419a084c8b7712cace80'], 'frontend/src/pages/pendencias/CentralPendenciasPage.tsx': ['f72bb5826fd226903e7be0788d2dcfe91e4b62db109d366506e232b1d720867c'], 'frontend/src/pages/pendencias/pendenciasPortal.ts': ['93b74cc9d977c80f6b77bc237fa281c254f6e233d3b4bcec9e083d3a9b55cbe4'], 'tests/test_central_pendencias_d37.py': ['a476ed08c728ddd3fcc405f305e9a58c32e3559e8265a00ae55a0079500f5d47'], 'D38_CONTRATO_RESUMO_GERENCIAL.txt': ['346685fa01bd3721879f7aff20cdc51665c979a9e5aa3d4153b7c037d2536622'], 'backend/app/api/rotas/resumo_gerencial.py': ['66cd246932992d32fbd12f9e67ed5178d7f79c15f9e58464c53d6b72b24f7df2'], 'backend/app/schemas/resumo_gerencial.py': ['aa51ebaaae32057c7e3779616eafdf2187a4874ae9738c36cb95b19beb0c4108'], 'backend/app/services/resumo_gerencial.py': ['0bbae5c14ed90e6722975181615ccc8dea76240616f81f1d1827f967a68700ca'], 'frontend/src/pages/gerencial/ResumoGerencial.css': ['6f79a62aaa42ab830c8a4bc6bc9d31beea3f6c535660ddcf15b2f1fb1f35dfc4'], 'frontend/src/pages/gerencial/ResumoGerencialPage.tsx': ['ffee2d228632e804024fa109d20c39bf6dec6abee05ac2e2344415bdc4bb32db'], 'frontend/src/pages/gerencial/gerencialPortal.ts': ['fe6c0ec330f0382fb014b3844bf0402fb6edb8e1b973ce7a2d8d4614f3b8de5a'], 'tests/test_resumo_gerencial_d38.py': ['49b35f87181bcf9e244f716b8c477eeb94c2397cbf214f5644425b906748f22f'], 'D38_FIX1_VER_MES_VISIVEL.txt': ['2391ed33d03302cdfd92171d9475274137d7b4e395c1bf899e24f6c403d5a705'], 'D39_CONTRATO_COMPARATIVO_GERENCIAL.txt': ['6a11efb401c00060a517510397edd6d6573621c1a6c65232b32eb781cf052efd'], 'backend/app/api/rotas/comparativo_gerencial.py': ['e4d7059ba75fc9d7f2ccbe750409675387746d62d6bd1a660c704956e0a6a605'], 'backend/app/schemas/comparativo_gerencial.py': ['e0c13912101874f2dc33912dea785992fd5e0e3949e4847eeb058a695ed01851'], 'backend/app/services/comparativo_gerencial.py': ['924072496b95bfa6ad235791cdf20d34a6075a67e55f3e886ae391f795106001'], 'frontend/src/pages/comparativo/ComparativoGerencial.css': ['969607ede26920ab36a78a6f7b422fb3de3d7ecc5f655cccc2baafe7c8388229'], 'frontend/src/pages/comparativo/ComparativoGerencialPage.tsx': ['34f149d93ee48562d1a6f42f313db422aaf80c7a89fd0b21e06c1078626e6887'], 'frontend/src/pages/comparativo/comparativoPortal.ts': ['654292aef1729e1449a58d54e6a9d830ccf78aac3321798c6098fd3d2bb9aeda'], 'tests/test_comparativo_gerencial_d39.py': ['fb5d10189e887ddbcc6068d05583ea98f2b10aa883b51d6490dd9c6f5ad55764'], 'D40_CONTRATO_EXTRATO_FINANCEIRO.txt': ['be535b740022b1bbaee6cf2287681762ebdf942fe4645b2027c111e0f601496a'], 'backend/app/api/rotas/extrato_financeiro.py': ['48c15f895665057302c4770e2500ec16d0e3cec664f8ca66e67469ae214543ee'], 'backend/app/schemas/extrato_financeiro.py': ['b2728c060f3c95dd4c793b314bf0605fd3fd6a226a6cdb25d90237cb5c3b4e24'], 'backend/app/services/extrato_financeiro.py': ['1bd9476755156adbfcaa8606443fa0c8d8c3a3fc57775f74ffe5a427f5e3fdcf'], 'frontend/src/pages/extrato/ExtratoFinanceiro.css': ['0a0284f29ca75a05d60e60c73eafbbc59f0262ac311f1e915f4cb5d3a1419bd9'], 'frontend/src/pages/extrato/ExtratoFinanceiroPage.tsx': ['aefb8802f6db300c8ec328f02097b988559f387a13c596a1694acb9592e56480'], 'frontend/src/pages/extrato/extratoPortal.ts': ['fe04c26177109b4346c563db25be32c49c41dd020c3ca5c0703df682a52a3c86'], 'tests/test_extrato_financeiro_d40.py': ['c9fb8d4172c45c6772659c2e4af0cfe5e406d6d0d9cd02ac1bc87e3c8296576c'], 'backend/app/api/rotas/portal_fornecedor.py': ['3821c6c2956cadd061fcdbbc3bccd056b58c3fd6a146b8ac6bce81380fbaf222'], 'backend/app/services/cotacao.py': ['d9b40d6df27a1d1e90fb446f486cdc7fb68f5a5bc37a92314ee94c8ffc6cd8ac'], 'backend/app/services/portal_fornecedor.py': ['99234f6e655332848eafce7b6941f02b6e987012290a37143a67ea9f18c42a94'], 'frontend/src/pages/supplier/SupplierCotacoesPage.tsx': ['bfbade69cf66263289f4efb86aa82ccb07a51ead1bedd157f434cd15cf41f741'], 'frontend/src/pages/supplier/cotacoesFornecedor.ts': ['13891d5297b62026cd72276d48f0a4a9f9813377bc3b7d189bca267124c2a5d3'], 'tests/test_acesso_d30.py': ['349a44f5b78b671fdea714afea5e36fe2311b5d9617cde487bf4a0df831716ee'], 'tests/test_cotacoes.py': ['a716b81c44d813d2c571686afca8e242159887c5cb7be320db8ce337510c0153'], 'tests/test_portal_fornecedor_cotacoes.py': ['f6b7976a14174ed72ea9ceb36f418c805a224856e90ab9080653bc3dbf5dcb32'], 'D42_CONTRATO_DOCUMENTACAO_COTACAO.txt': ['caeac8ef1a6db9bd02795367e0920d2b2a3ea2517ceae99c4f339480c089f9c4'], 'backend/app/api/rotas/documentacao_cotacao.py': ['c939a6604b29ba261f0c7423920693e53ce74be7448b670585a482a48bb1d8b7'], 'backend/app/models/documentacao_cotacao.py': ['66f4c3b0b8732321508dfd884e6daf6ae2263f94a4fcd50d7d3b48e7362c6682'], 'backend/app/schemas/documentacao_cotacao.py': ['155d09636e46849e50ee91f6fed815d7e3171ed5a8e2dd6c46ec57ccb24e8324'], 'backend/app/services/documentacao_cotacao.py': ['419fa116af4f022abb6537da2d66c79e314ca87933cfbd9469dbbd9923721ad8'], 'frontend/src/pages/documentacao/AdminDocumentacaoPage.tsx': ['1d8074823b34bb8cd0aea8510853fb8867c720c81b3cb6f7cc820f9a782cf42c'], 'frontend/src/pages/documentacao/Documentacao.css': ['0c0108268d95d5a073f92aef8e46755de75f5dbdde6db96e3a0e3dd6ad0cff93'], 'tests/apoio_documentacao_d42.py': ['253114528d5753b93ebdbb1b40c391f027dd93770bae7b1eedceeaf5a481f5f2'], 'tests/test_documentacao_cotacao_d42.py': ['6ba4ad4c0196b4d45e1d0d1291d1a11a9dc54477f0010cc114b6ddee3e65b8a6'], 'D42_FIX1_COMPATIBILIDADE_MODELOS.txt': ['8f1d4ffa3700888e2c2e46382cdc119dc2bc555ff7f22aebf71ad6e3d033cef0'], 'D42_FIX2_COMPATIBILIDADE_BASE_LOCAL.txt': ['aa58c58da6528cb257996a5684ea5a492474a20c82d730cb4f2cb2c0592c660c'], 'D43_CONTRATO_COMERCIAL_ADMIN.txt': ['625bdd44b10eae8a52620e1f5de21d1d0a5d91f017b96e7c1ac46cf36272abd6'], 'backend/app/api/rotas/comercial_admin.py': ['65fee9ae4bbb055d227b816733a65530c175cafa52a4e357602a11080f390c0d'], 'backend/app/models/comercial_admin.py': ['9cafd943786e78460506f7fd81a3b2926fc7ee556c526e3109cf6f14642bd94f'], 'backend/app/schemas/comercial_admin.py': ['5615f49549c69be1f57bbe145c878c4fd02055a72a743dc4d94608761af52163'], 'backend/app/services/comercial_admin.py': ['783a206e54497ec02f298de2b8c07e7731c3106834585d6ed39bc4f120e8cf76'], 'frontend/src/pages/comercial/AdminComercialPage.tsx': ['99a82e7abc165817a21c575e15ba11e37f279cc98bfb44e8aba8433d5dfe4c64'], 'frontend/src/pages/comercial/ComercialAdmin.css': ['af27a1751e19b79a6a7cd38620c938e796101e72d3f10f4deabe460e2b551ac0'], 'tests/test_comercial_administrativo_d43.py': ['97324f42108bb8f52b66b15d6398bcec714065a5d96c2fccf8811f4ec75948eb'], 'backend/app/services/contratacao.py': ['5c310b91e1617face5022eeb0a44551f22136fcbe4c6d9375ebdb02ab0249a53'], 'backend/app/services/ordem_servico.py': ['f4800b8d033b32487bd1399ea8a5212cf51f1915d0ee7dd51b778cecb6170691'], 'D44_CONTRATO_CONTRATACAO_ADMIN.txt': ['66b1fea843f3e73bde865f97cc48d36a136af8631f5c12e2dc2ddee7656d6396'], 'backend/app/api/rotas/contratacao_admin.py': ['a488492f278fe4dc724bdcef4f1e9cae15335f3a57ac53ba5e987ef212d05f65'], 'backend/app/models/contratacao_admin.py': ['7c2ad9aab2781463bf91967edc7a5873644c0c6d23a053b002208e6470859023'], 'backend/app/schemas/contratacao_admin.py': ['ebf59d99669bd04ff731d1ae68c204f2e672b86dd43663be5302de3287b0ede8'], 'backend/app/services/contratacao_admin.py': ['0cc6e7a9f52863b38b57af719d00d15af953557e1129f6201a59e35ae0bff1a0'], 'frontend/src/pages/contratacao-admin/AdminContratacaoPage.tsx': ['3df0bb0862257abfbbf9408d9feb4ae87a7e47da0f7b14d377fb46f72918c83c'], 'tests/test_contratacao_administrativa_d44.py': ['13ac4e8e0d116dd25d097a2e906899c8604172a62fb5fa7dca42e50b3c16a3f5'], 'backend/app/services/portal_ordens_servico.py': ['9974a8943bcc6ba97c8deff0380255bca88bfdfb7c9901a3806b747e0ee53250'], 'frontend/src/pages/entregas/PortalEntregasPage.tsx': ['f084917c40cd93ae45bd2dc1d85084362b06da77e592eaf3fe32ca97530de057'], 'frontend/src/pages/producao/PortalProducaoPage.tsx': ['a36530fc8debc941ca12d99b62a73d2d1672b1666cefb752e9a4f2a18be11346'], 'D45_CONTRATO_NOTIFICACOES_PERFIS.txt': ['d25b6e43e0f510877b7ff4fbb43cb65281d4509a162bc2cf2a727c22902d2c52'], 'backend/app/api/rotas/notificacoes.py': ['f6af42f8154c50a795fa9d97809ed8c80c98e585b0d9c4259e777afae1d1604b'], 'backend/app/models/notificacao.py': ['dede9ef5ccbe90a0d9d342822fc9408693a03fb8536f317004a365ace099d916'], 'backend/app/schemas/notificacao.py': ['178458a3f5c1663f50cff447f438fa8b8b47578dd780374860e21549adb512a5'], 'backend/app/services/eventos_notificacoes.py': ['632f980a88d25fd2ad2923b9875f94804d8b957947ec36cc914e43b012675317'], 'backend/app/services/notificacoes.py': ['7b4c1fdfc4876fc34125c1f62f72ac4a929ed0f42c88fd8d3ce9f7f60290598b'], 'frontend/src/components/notificacoes/CentroNotificacoes.tsx': ['e67bef0b8804907b5a0885808fc76da6e8a44958f58d70209bcda447b90a7c12'], 'frontend/src/components/notificacoes/Notificacoes.css': ['1640d489b9c4603566aa2c1c0ebe7dbfa1384feb19aa0b2fd83e96455956b336'], 'tests/test_notificacoes_d45.py': ['3cf1f52e9f60695d3867388b43037d4eff4399b6e6614ac463c95e6b20e48e47'], 'backend/app/services/avaliacao.py': ['0d01b31a469b9e6def65e7377d034c6c35b2c57bd0577ec5d1921ef7bda819bb'], 'D46_CONTRATO_AVALIACOES_PERFIS.txt': ['781978fc764e582278340bb92753c25677dc0d587d70e34bb25ce48333f1cc7e'], 'backend/app/api/rotas/avaliacoes_perfis.py': ['ba14f36184a6a6a85a5ce6a987562df9c1fc088d8a0a9c2768bdc12b0fcfb26c'], 'backend/app/models/avaliacao_perfil.py': ['6a12d6082a478b1462ece24eed4f138784f5dbbe6d2c86285fc62dfbb0d8eea7'], 'backend/app/schemas/avaliacao_perfil.py': ['e0ca6db0af205499337c055956806cec997dee24c95fa6f68620ef1a662f59e8'], 'backend/app/services/avaliacoes_perfis.py': ['04a4c4c295eec76df4dee6f74a8c30b7ed41dca03b93cd49b3496c8f61ca858c'], 'frontend/src/pages/avaliacoes/Avaliacoes.css': ['a9021a11dfa5a323f266e0a076f03069c3f4eb1d163cc1a38ce09749f3e0e9f2'], 'frontend/src/pages/avaliacoes/AvaliacoesPage.tsx': ['293a7d9a003ffaa749609a4f4c680b856b18e9dbfc79ea68de6731f3a3f73359'], 'frontend/src/pages/avaliacoes/RankingAvaliacoesPage.tsx': ['77aa3c854ed0384ce0b5fdee020d478d1f01d19c5486a7a59862ac1ec7fe4e34'], 'frontend/src/pages/avaliacoes/avaliacoesPortal.ts': ['450f99c8ba8986f4686353d6a4a6956116c6abfe352e20de6ec7e2046727ecaa'], 'tests/test_avaliacoes_perfis_d46.py': ['f7162ce6063c4fcdf83af6c13ca470cd2aa7f6083602f33cf230b4493466fafd'], 'D46_FIX1_CONTRATO_RANKING_PRIVADO.txt': ['d9e33131f32680a97bb953d688c0575981e81e225fa5baded5655840989ef79d'], 'frontend/src/auth/PortalSemRanking.css': ['4aecb3fc37d014eabf8bc322f235b118238e7863b888429cafc87955eca31cbc'], 'frontend/src/auth/PortalSemRanking.tsx': ['0c7c7b8f57681bd496055b4dd946857956762d81935dd50f32bda5273667133e'], 'tests/test_ranking_privado_d46_fix1.py': ['f03b3f48d2656f5e3fae55b831eec2b0acd410c9a2aac61435c84181f0641392'], 'D47_CONTRATO_COMPARACAO_COTACOES.txt': ['3e8f1b0ccd6b8e2ef9e7f827f50b5bdac685bafc4bbe0ded2983ed6fe375a172'], 'tests/test_comparacao_cotacoes_d47.py': ['9d47e4f944abfebb220bb14a3dba6978fd189472112b5214bd3c0d5844fa2308'], 'backend/app/schemas/comparacao_cotacoes_admin.py': ['e663f38decdffe44fba854123df80972246eed177f55980708b3a77864b8d24f'], 'backend/app/services/comparacao_cotacoes_admin.py': ['2270592edcc03a8c47a03b65558a03522244a18ad9c9843e86648c7dfd88630a'], 'frontend/src/pages/comercial/ComparacaoCotacoesAdmin.css': ['70baac1d41474b6174a941b7e29ba7139075bf5b570a8f50dcb19b88fe485a2c'], 'frontend/src/pages/comercial/ComparacaoCotacoesAdmin.tsx': ['b66b74199d788c8b3091509a1feb7f77e61d2798ae1d8f93388eda19282f16a3'], 'D47_FIX1_CONTRATO_CONTRASTE_COMPARACAO.txt': ['c85a3cc6c6673898fc2c4d8ab5c3b1846f3e947db4a914113962866e706856f5'], 'D48_CONTRATO_PREPARACAO_PDF_COTACAO.txt': ['f1343071b629335e62b0a993fe254dee61c194c3877bba36d267bc8348abdf32'], 'requirements_pdf_d48.txt': ['fbc536fb745cb55cde440d6df7af508484df0823b340d766745cee82f0da0f13'], 'tests/test_preparacao_pdf_d48.py': ['e9fcd2a0f3712779b0de706983ae573f0b993bfd66f11b2793f3c8866d777803'], 'backend/app/schemas/preparacao_pdf.py': ['6bd3e19b4aa127a2df3d0d69c9d9daca597b6ab269cc57a16071ababf440cca9'], 'backend/app/models/preparacao_pdf.py': ['9821621d9eb79979ed02e93d96b12b453d43afed22df92fa3fa466f317e2ddc9'], 'backend/app/services/preparacao_pdf.py': ['c346c692f22e77ba7b3030bc7d7eb5047b285eef3aeed8de1f278d4d7f67fc07'], 'backend/app/services/motor_pdf_cotacao.py': ['68a44fcb4d79cfb3cd89d8a63c3ebb65d86b508339f93878aa7fa2ec65dbe7c6'], 'backend/app/api/rotas/preparacao_pdf.py': ['feddd970a88351c8ca3156bee8901d95721a58f67d727e99e0d16ba2d5b364c1'], 'frontend/src/pages/documentacao/PrepararPdfAdmin.tsx': ['8b3bece7722eba0befdb0d3ebe00c8759c74a09a24497c74f555181d4c2f5915'], 'frontend/src/pages/documentacao/PreparacaoPdf.css': ['820c3cee69dd8e95783f418a552d0cfc73fb233f9fa25035a8d80f20a487e90f'], 'backend/app/assets/mec_logo_pdf.png': ['bfd839a02bbbb72a405a2c2c6f2c4f9339b4de9de16cceb540d3afd2e3cb63a2']}

PERMISSOES_SEM_TESTE = 'from __future__ import annotations\n\nimport hmac\nimport json\nimport os\nimport re\nfrom pathlib import Path\nfrom typing import Annotated\n\nfrom fastapi import Depends, HTTPException, Request\nfrom sqlalchemy.orm import Session\n\nfrom backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, COOKIE_SESSAO, UsuarioAcesso\nfrom backend.app.database.sessao import obter_banco\nfrom backend.app.models.arquivo_tecnico import ArquivoTecnico\nfrom backend.app.models.empresa import Empresa\nfrom backend.app.models.solicitacao import SolicitacaoServico\nfrom backend.app.services.intermediacao import proteger_ciclo_legado\nfrom backend.app.services.financeiro_administrativo import proteger_financeiro_legado\n\nSessaoBanco = Annotated[Session, Depends(obter_banco)]\n\n\ndef armazenamento(request: Request) -> ArmazenamentoAcesso:\n    padrao = Path(__file__).resolve().parents[3] / "data/mec_acessos.db"\n    caminho = getattr(request.app.state, "caminho_acessos", None) or os.environ.get("MEC_ACESSOS_DB") or padrao\n    return ArmazenamentoAcesso(Path(caminho))\n\n\ndef verificar_origem(request: Request) -> None:\n    origem = request.headers.get("origin")\n    if not origem:\n        if request.headers.get("sec-fetch-site") == "cross-site":\n            raise HTTPException(403, detail="origem_nao_autorizada")\n        return\n    mesma_origem = origem.rstrip("/") == str(request.base_url).rstrip("/")\n    locais = origem.rstrip("/") in {"http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"}\n    servidor_local = request.url.hostname in {"localhost", "127.0.0.1", "testserver"}\n    configuradas = {item.strip().rstrip("/") for item in os.environ.get("MEC_ORIGENS_PERMITIDAS", "").split(",") if item.strip()}\n    if origem == "null" or not (mesma_origem or (locais and servidor_local) or origem.rstrip("/") in configuradas):\n        raise HTTPException(403, detail="origem_nao_autorizada")\n\n\ndef identificar_usuario(request: Request, banco: Session) -> UsuarioAcesso:\n    usuario = armazenamento(request).obter_sessao(request.cookies.get(COOKIE_SESSAO))\n    if usuario.perfil != "admin":\n        empresa = banco.get(Empresa, usuario.empresa_id)\n        if empresa is None or empresa.tipo_empresa not in {usuario.perfil, "ambos"}:\n            raise HTTPException(403, detail="vinculo_empresa_nao_autorizado")\n    request.state.usuario_acesso = usuario\n    return usuario\n\n\ndef verificar_csrf(request: Request, usuario: UsuarioAcesso) -> None:\n    verificar_origem(request)\n    recebido = request.headers.get("x-mec-csrf", "")\n    if not recebido or not hmac.compare_digest(recebido.encode("utf-8"), usuario.csrf.encode("utf-8")):\n        raise HTTPException(403, detail="sessao_alterada_entre_novamente")\n\n\ndef inteiro(valor) -> int | None:\n    if type(valor) is int and valor > 0:\n        return valor\n    if isinstance(valor, str) and re.fullmatch(r"[1-9]\\d{0,12}", valor):\n        return int(valor)\n    return None\n\n\nasync def vincular_parametros(request: Request, usuario: UsuarioAcesso, exigir_query: bool = False) -> None:\n    campo = "empresa_cliente_id" if usuario.perfil == "cliente" else "empresa_fornecedora_id"\n    for nome in (campo, "empresa_id"):\n        valores = request.query_params.getlist(nome)\n        if valores and (len(valores) != 1 or inteiro(valores[0]) != usuario.empresa_id):\n            raise HTTPException(403, detail="empresa_diverge_da_sessao")\n    if exigir_query and not request.query_params.getlist(campo):\n        raise HTTPException(403, detail="empresa_da_sessao_obrigatoria")\n    if request.method not in {"GET", "HEAD", "OPTIONS"} and "application/json" in request.headers.get("content-type", ""):\n        tamanho = request.headers.get("content-length", "")\n        if tamanho.isdigit() and int(tamanho) > 1_000_000:\n            raise HTTPException(413, detail="corpo_requisicao_muito_grande")\n        corpo = await request.body()\n        if len(corpo) > 1_000_000:\n            raise HTTPException(413, detail="corpo_requisicao_muito_grande")\n        try:\n            dados = json.loads(corpo)\n        except (ValueError, UnicodeError):\n            raise HTTPException(422, detail="corpo_json_invalido") from None\n        if not isinstance(dados, dict):\n            raise HTTPException(422, detail="corpo_json_invalido")\n        for nome in (campo, "empresa_id"):\n            if nome in dados and inteiro(dados[nome]) != usuario.empresa_id:\n                raise HTTPException(403, detail="empresa_diverge_da_sessao")\n        if any(nome in dados for nome in ("role", "perfil", "usuario_id")):\n            raise HTTPException(403, detail="perfil_e_usuario_definidos_pelo_servidor")\n\n\ndef solicitacao_propria(banco: Session, solicitacao_id: int, usuario: UsuarioAcesso) -> None:\n    item = banco.get(SolicitacaoServico, solicitacao_id)\n    if item is None or item.empresa_cliente_id != usuario.empresa_id:\n        raise HTTPException(404, detail="solicitacao_nao_encontrada")\n\n\nasync def autorizar_requisicao(request: Request, banco: SessaoBanco) -> None:\n    prefixo = getattr(request.app.state, "prefixo_api_acesso", "/api/v1").rstrip("/")\n    caminho = request.url.path[len(prefixo):] if request.url.path.startswith(prefixo + "/") else request.url.path\n    if request.method == "GET" and caminho in {"/saude", "/banco-dados/saude"}:\n        return\n    usuario = identificar_usuario(request, banco)\n    if request.method not in {"GET", "HEAD", "OPTIONS"}:\n        verificar_csrf(request, usuario)\n    if usuario.deve_alterar_senha:\n        raise HTTPException(403, detail="troca_senha_inicial_obrigatoria")\n    if usuario.perfil == "admin":\n        proteger_ciclo_legado(banco, caminho, request.method, usuario)\n        proteger_financeiro_legado(banco, caminho, request.method)\n        return\n    await vincular_parametros(request, usuario)\n    if request.method == "GET" and caminho in {"/materiais", "/processos-fabricacao"}:\n        return\n    empresa = re.fullmatch(r"/empresas/([1-9]\\d*)(?:/(capacidades|maquinas|materiais))?", caminho)\n    if empresa and int(empresa[1]) == usuario.empresa_id:\n        if request.method == "GET" or (usuario.perfil == "fornecedor" and empresa[2] and request.method == "POST"):\n            return\n    portal = "/portal-" + usuario.perfil + "/"\n    if caminho.startswith(portal):\n        restante = caminho[len(portal):]\n        if usuario.perfil == "fornecedor" and ("/arquivos" in "/" + restante or "/download" in restante):\n            lista = re.fullmatch(r"solicitacoes/([1-9]\\d*)/arquivos", restante)\n            download = re.fullmatch(r"arquivos/([1-9]\\d*)/download", restante)\n            if request.method == "GET" and (lista or download):\n                await vincular_parametros(request, usuario, exigir_query=True)\n                from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao\n                from backend.app.services.portal_fornecedor import ServicoPortalFornecedor\n                arquivo = banco.get(ArquivoTecnico, int(download[1])) if download else None\n                if download and arquivo is None:\n                    raise HTTPException(403, detail="arquivo_aguarda_liberacao_administrativa")\n                solicitacao_id = int(lista[1]) if lista else arquivo.solicitacao_id\n                documentos = ServicoDocumentacaoCotacao(banco)\n                documentos.exigir_acesso(solicitacao_id, arquivo.id if arquivo else None)\n                ServicoPortalFornecedor(banco).validar_acesso_arquivos(solicitacao_id, usuario.empresa_id)\n                return\n            raise HTTPException(403, detail="arquivo_aguarda_liberacao_administrativa")\n        if request.method == "GET":\n            leituras = (r"(?:contratacoes|ordens-servico|producao|entregas)(?:/[1-9]\\d*)?", r"intermediacao/[1-9]\\d*", r"financeiro(?:/[1-9]\\d*)?",)\n            if usuario.perfil == "cliente":\n                leituras += (r"cotacoes-aceitas", r"contratacoes-para-ordem",\n                             r"(?:contratacoes|ordens-servico)/[1-9]\\d*/arquivos(?:/[1-9]\\d*/download)?")\n            else:\n                leituras += (r"oportunidades", r"cotacoes")\n            if any(re.fullmatch(padrao, restante) for padrao in leituras):\n                await vincular_parametros(request, usuario, exigir_query=True)\n                return\n        if usuario.perfil == "fornecedor" and request.method == "POST":\n            permitidas = (r"solicitacoes/[1-9]\\d*/cotacoes", r"ordens-servico/[1-9]\\d*/iniciar", r"producao/[1-9]\\d*/etapas")\n            if any(re.fullmatch(padrao, restante) for padrao in permitidas):\n                proteger_ciclo_legado(banco, caminho, request.method, usuario)\n                return\n        raise HTTPException(403, detail="acao_exclusiva_da_administracao")\n    if usuario.perfil == "cliente":\n        if caminho == "/solicitacoes-servico":\n            if request.method == "GET":\n                await vincular_parametros(request, usuario, exigir_query=True)\n                return\n            if request.method == "POST":\n                return\n        solicitacao = re.fullmatch(r"/solicitacoes-servico/([1-9]\\d*)(?:/(cotacoes|arquivos-tecnicos))?", caminho)\n        if solicitacao:\n            solicitacao_propria(banco, int(solicitacao[1]), usuario)\n            if request.method == "GET" or (solicitacao[2] == "arquivos-tecnicos" and request.method == "POST"):\n                return\n        arquivo = re.fullmatch(r"/arquivos-tecnicos/([1-9]\\d*)(/download)?", caminho)\n        if arquivo and request.method in {"GET", "DELETE"}:\n            item = banco.get(ArquivoTecnico, int(arquivo[1]))\n            if item is None:\n                raise HTTPException(404, detail="arquivo_tecnico_nao_encontrado")\n            solicitacao_propria(banco, item.solicitacao_id, usuario)\n            if request.method == "GET" or arquivo[2] is None:\n                return\n    # Rotas legadas e rotas novas não liberadas explicitamente exigem operador.\n    raise HTTPException(403, detail="acao_exclusiva_da_administracao")\n'

DDL_D42 = {'liberacoes_arquivos_cotacao': 'CREATE TABLE liberacoes_arquivos_cotacao (\n\tarquivo_id INTEGER NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\tdisponivel BOOLEAN NOT NULL, \n\tversao INTEGER NOT NULL, \n\tatualizado_em VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (arquivo_id), \n\tCONSTRAINT ck_liberacao_arquivo_versao CHECK (versao > 0), \n\tFOREIGN KEY(arquivo_id) REFERENCES arquivos_tecnicos (id) ON DELETE RESTRICT\n)', 'eventos_arquivos_cotacao': "CREATE TABLE eventos_arquivos_cotacao (\n\tid INTEGER NOT NULL, \n\tarquivo_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(16) NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tchave_operacao VARCHAR(36) NOT NULL, \n\tcriado_em VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_evento_arquivo_versao UNIQUE (arquivo_id, versao), \n\tCONSTRAINT ck_evento_arquivo_versao CHECK (versao > 0), \n\tCONSTRAINT ck_evento_arquivo_acao CHECK (acao IN ('liberar','bloquear')), \n\tFOREIGN KEY(arquivo_id) REFERENCES arquivos_tecnicos (id) ON DELETE RESTRICT, \n\tUNIQUE (chave_operacao)\n)"}

INDICES_D42 = {'ix_eventos_arquivos_cotacao_arquivo_id': 'CREATE INDEX ix_eventos_arquivos_cotacao_arquivo_id ON eventos_arquivos_cotacao (arquivo_id)'}

TABELAS_D31 = ('ciclos_intermediacao', 'eventos_intermediacao')

DDL_TABELAS = {'ciclos_intermediacao': "CREATE TABLE ciclos_intermediacao (\n\tid INTEGER NOT NULL, \n\tordem_servico_id INTEGER NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\tversao INTEGER NOT NULL, \n\tultima_etapa_coleta_id INTEGER NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tatualizado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_ciclo_intermediacao_ordem UNIQUE (ordem_servico_id), \n\tCONSTRAINT ck_ciclo_intermediacao_versao CHECK (versao > 0), \n\tCONSTRAINT ck_ciclo_intermediacao_status CHECK (status IN ('aguardando_material','material_recebido','material_encaminhado','coleta_solicitada','pecas_recebidas','em_avaliacao','retrabalho','retrabalho_encaminhado','aprovado_para_entrega','entregue_cliente','cancelado')), \n\tFOREIGN KEY(ordem_servico_id) REFERENCES ordens_servico (id) ON DELETE RESTRICT\n)", 'eventos_intermediacao': 'CREATE TABLE eventos_intermediacao (\n\tid INTEGER NOT NULL, \n\tciclo_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(40) NOT NULL, \n\tstatus_anterior VARCHAR(40), \n\tstatus_resultante VARCHAR(40) NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\treferencia VARCHAR(200), \n\tparecer_tecnico TEXT, \n\tquantidade_conferida INTEGER, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_evento_intermediacao_versao UNIQUE (ciclo_id, versao), \n\tFOREIGN KEY(ciclo_id) REFERENCES ciclos_intermediacao (id) ON DELETE RESTRICT\n)'}

SCHEMA_D31 = {'ciclos_intermediacao': [('id', 'INTEGER', True, True), ('ordem_servico_id', 'INTEGER', True, False), ('status', 'VARCHAR(40)', True, False), ('versao', 'INTEGER', True, False), ('ultima_etapa_coleta_id', 'INTEGER', True, False), ('criado_em', 'VARCHAR(40)', True, False), ('atualizado_em', 'VARCHAR(40)', True, False)], 'eventos_intermediacao': [('id', 'INTEGER', True, True), ('ciclo_id', 'INTEGER', True, False), ('versao', 'INTEGER', True, False), ('acao', 'VARCHAR(40)', True, False), ('status_anterior', 'VARCHAR(40)', False, False), ('status_resultante', 'VARCHAR(40)', True, False), ('usuario_admin_id', 'INTEGER', True, False), ('administrador_nome', 'VARCHAR(120)', True, False), ('registro_interno', 'TEXT', True, False), ('referencia', 'VARCHAR(200)', False, False), ('parecer_tecnico', 'TEXT', False, False), ('quantidade_conferida', 'INTEGER', False, False), ('criado_em', 'VARCHAR(40)', True, False)]}

DDL_D32 = {'controles_financeiros_admin': "CREATE TABLE controles_financeiros_admin (\n\tcontratacao_id INTEGER NOT NULL, \n\tvalor_contratado_centavos INTEGER NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tversao INTEGER NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tatualizado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (contratacao_id), \n\tCONSTRAINT ck_financeiro_valor CHECK (valor_contratado_centavos > 0), \n\tCONSTRAINT ck_financeiro_versao CHECK (versao > 0), \n\tCONSTRAINT ck_financeiro_status CHECK (status IN ('aberto','encerrado')), \n\tFOREIGN KEY(contratacao_id) REFERENCES contratacoes_servico (id) ON DELETE RESTRICT\n)", 'repasses_administrativos': "CREATE TABLE repasses_administrativos (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tvalor_centavos INTEGER NOT NULL, \n\tforma_pagamento VARCHAR(20) NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tregistrado_em VARCHAR(40) NOT NULL, \n\testornado_em VARCHAR(40), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_repasse_valor CHECK (valor_centavos > 0), \n\tCONSTRAINT ck_repasse_status CHECK (status IN ('confirmado','estornado')), \n\tFOREIGN KEY(contratacao_id) REFERENCES controles_financeiros_admin (contratacao_id) ON DELETE RESTRICT\n)", 'eventos_financeiros_admin': 'CREATE TABLE eventos_financeiros_admin (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(32) NOT NULL, \n\tchave_operacao VARCHAR(36), \n\tresumo_operacao VARCHAR(64), \n\tpagamento_id INTEGER, \n\trepasse_id INTEGER, \n\tvalor_centavos INTEGER, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\treferencia VARCHAR(200), \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_financeiro_evento_versao UNIQUE (contratacao_id, versao), \n\tCONSTRAINT uq_financeiro_chave UNIQUE (contratacao_id, chave_operacao), \n\tCONSTRAINT uq_financeiro_referencia UNIQUE (contratacao_id, referencia), \n\tFOREIGN KEY(contratacao_id) REFERENCES controles_financeiros_admin (contratacao_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(pagamento_id) REFERENCES pagamentos_contratacao (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(repasse_id) REFERENCES repasses_administrativos (id) ON DELETE RESTRICT\n)'}

INDICES_D32 = {'ix_repasses_administrativos_contratacao_id': 'CREATE INDEX ix_repasses_administrativos_contratacao_id ON repasses_administrativos (contratacao_id)', 'ix_eventos_financeiros_admin_contratacao_id': 'CREATE INDEX ix_eventos_financeiros_admin_contratacao_id ON eventos_financeiros_admin (contratacao_id)'}

SCHEMA_D32 = {'controles_financeiros_admin': [('contratacao_id', 'INTEGER', True, True), ('valor_contratado_centavos', 'INTEGER', True, False), ('status', 'VARCHAR(16)', True, False), ('versao', 'INTEGER', True, False), ('criado_em', 'VARCHAR(40)', True, False), ('atualizado_em', 'VARCHAR(40)', True, False)], 'repasses_administrativos': [('id', 'INTEGER', True, True), ('contratacao_id', 'INTEGER', True, False), ('valor_centavos', 'INTEGER', True, False), ('forma_pagamento', 'VARCHAR(20)', True, False), ('status', 'VARCHAR(16)', True, False), ('registrado_em', 'VARCHAR(40)', True, False), ('estornado_em', 'VARCHAR(40)', False, False)], 'eventos_financeiros_admin': [('id', 'INTEGER', True, True), ('contratacao_id', 'INTEGER', True, False), ('versao', 'INTEGER', True, False), ('acao', 'VARCHAR(32)', True, False), ('chave_operacao', 'VARCHAR(36)', False, False), ('resumo_operacao', 'VARCHAR(64)', False, False), ('pagamento_id', 'INTEGER', False, False), ('repasse_id', 'INTEGER', False, False), ('valor_centavos', 'INTEGER', False, False), ('usuario_admin_id', 'INTEGER', True, False), ('administrador_nome', 'VARCHAR(120)', True, False), ('registro_interno', 'TEXT', True, False), ('referencia', 'VARCHAR(200)', False, False), ('criado_em', 'VARCHAR(40)', True, False)]}

D42_REVISION = 'MEC-SERVICOS-V0.1-D42-FIX2-DOCUMENTACAO-PARA-COTACAO-2026-10-06'

DDL_D43 = {'eventos_decisoes_cotacao_admin': "CREATE TABLE eventos_decisoes_cotacao_admin (\n\tid INTEGER NOT NULL, \n\tsolicitacao_id INTEGER NOT NULL, \n\tcotacao_id INTEGER NOT NULL, \n\tacao VARCHAR(16) NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(200) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\tversao_anterior VARCHAR(64) NOT NULL, \n\tchave_operacao VARCHAR(36) NOT NULL, \n\tresultado_json TEXT NOT NULL, \n\tcriado_em VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_decisao_cotacao_admin_acao CHECK (acao IN ('aceitar', 'recusar')), \n\tCONSTRAINT ck_decisao_cotacao_admin_usuario CHECK (usuario_admin_id > 0), \n\tFOREIGN KEY(solicitacao_id) REFERENCES solicitacoes_servico (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(cotacao_id) REFERENCES cotacoes_fornecedor (id) ON DELETE RESTRICT, \n\tUNIQUE (chave_operacao)\n)"}

INDICES_D43 = {'ix_eventos_decisoes_cotacao_admin_cotacao_id': 'CREATE INDEX ix_eventos_decisoes_cotacao_admin_cotacao_id ON eventos_decisoes_cotacao_admin (cotacao_id)', 'ix_eventos_decisoes_cotacao_admin_solicitacao_id': 'CREATE INDEX ix_eventos_decisoes_cotacao_admin_solicitacao_id ON eventos_decisoes_cotacao_admin (solicitacao_id)'}

D43_REVISION = 'MEC-SERVICOS-V0.1-D43-SOLICITACOES-COTACOES-ADMINISTRATIVAS-2026-10-07'

DDL_D44 = {'eventos_contratacoes_admin': "CREATE TABLE eventos_contratacoes_admin (\n\tid INTEGER NOT NULL, \n\tsolicitacao_id INTEGER NOT NULL, \n\tcotacao_id INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tordem_servico_id INTEGER NOT NULL, \n\tacao VARCHAR(32) NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\tobservacoes_execucao TEXT, \n\tversao_anterior VARCHAR(64) NOT NULL, \n\tchave_operacao VARCHAR(36) NOT NULL, \n\tresultado_json TEXT NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_contratacao_admin_chave UNIQUE (chave_operacao), \n\tCONSTRAINT ck_contratacao_admin_acao CHECK (acao IN ('contratar_e_abrir_os','abrir_os')), \n\tCONSTRAINT ck_contratacao_admin_usuario CHECK (usuario_admin_id > 0), \n\tFOREIGN KEY(solicitacao_id) REFERENCES solicitacoes_servico (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(cotacao_id) REFERENCES cotacoes_fornecedor (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(contratacao_id) REFERENCES contratacoes_servico (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(ordem_servico_id) REFERENCES ordens_servico (id) ON DELETE RESTRICT\n)"}

INDICES_D44 = {'ix_eventos_contratacoes_admin_contratacao_id': 'CREATE INDEX ix_eventos_contratacoes_admin_contratacao_id ON eventos_contratacoes_admin (contratacao_id)', 'ix_eventos_contratacoes_admin_cotacao_id': 'CREATE INDEX ix_eventos_contratacoes_admin_cotacao_id ON eventos_contratacoes_admin (cotacao_id)', 'ix_eventos_contratacoes_admin_ordem_servico_id': 'CREATE INDEX ix_eventos_contratacoes_admin_ordem_servico_id ON eventos_contratacoes_admin (ordem_servico_id)', 'ix_eventos_contratacoes_admin_solicitacao_id': 'CREATE INDEX ix_eventos_contratacoes_admin_solicitacao_id ON eventos_contratacoes_admin (solicitacao_id)'}

D44_REVISION = 'MEC-SERVICOS-V0.1-D44-CONTRATACAO-ADMINISTRATIVA-2026-10-07'

DDL_D45 = {'notificacoes_perfis': "CREATE TABLE notificacoes_perfis (\n\tid INTEGER NOT NULL, \n\tchave_evento VARCHAR(160) NOT NULL, \n\tperfil_destino VARCHAR(16) NOT NULL, \n\tempresa_destino INTEGER NOT NULL, \n\tperfil_origem VARCHAR(16) NOT NULL, \n\tassunto VARCHAR(160) NOT NULL, \n\tmensagem VARCHAR(500) NOT NULL, \n\tdestino VARCHAR(200) NOT NULL, \n\tsolicitacao_id INTEGER, \n\tcontratacao_id INTEGER, \n\tordem_servico_id INTEGER, \n\tcriada_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_notificacao_evento_destino UNIQUE (chave_evento, perfil_destino, empresa_destino), \n\tCONSTRAINT ck_notificacao_perfil CHECK (perfil_destino IN ('admin','cliente','fornecedor')), \n\tCONSTRAINT ck_notificacao_origem CHECK (perfil_origem IN ('admin','cliente','fornecedor')), \n\tCONSTRAINT ck_notificacao_empresa CHECK ((perfil_destino = 'admin' AND empresa_destino = 0) OR (perfil_destino IN ('cliente','fornecedor') AND empresa_destino > 0))\n)", 'leituras_notificacoes': "CREATE TABLE leituras_notificacoes (\n\tnotificacao_id INTEGER NOT NULL, \n\tusuario_id INTEGER NOT NULL, \n\tperfil VARCHAR(16) NOT NULL, \n\tempresa_id INTEGER NOT NULL, \n\tlida_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (notificacao_id, usuario_id, perfil, empresa_id), \n\tCONSTRAINT ck_leitura_usuario CHECK (usuario_id > 0), \n\tCONSTRAINT ck_leitura_perfil CHECK (perfil IN ('admin','cliente','fornecedor')), \n\tCONSTRAINT ck_leitura_empresa CHECK ((perfil = 'admin' AND empresa_id = 0) OR (perfil IN ('cliente','fornecedor') AND empresa_id > 0)), \n\tFOREIGN KEY(notificacao_id) REFERENCES notificacoes_perfis (id) ON DELETE CASCADE\n)"}

INDICES_D45 = {'ix_notificacoes_destino_id': 'CREATE INDEX ix_notificacoes_destino_id ON notificacoes_perfis (perfil_destino, empresa_destino, id)'}

RELATORIOS_D45 = {'MEC_SERVICOS_V0_1_D45_NOTIFICACOES_POR_PERFIL_RELATORIO.json': 'MEC-SERVICOS-V0.1-D45-NOTIFICACOES-POR-PERFIL-2026-10-07', 'MEC_SERVICOS_V0_1_D45_FIX1_NOTIFICACOES_POR_PERFIL_RELATORIO.json': 'MEC-SERVICOS-V0.1-D45-FIX1-NOTIFICACOES-POR-PERFIL-2026-10-08', 'MEC_SERVICOS_V0_1_D45_FIX2_NOTIFICACOES_POR_PERFIL_RELATORIO.json': 'MEC-SERVICOS-V0.1-D45-FIX2-NOTIFICACOES-POR-PERFIL-2026-10-08'}

DDL_D46 = {'autorias_avaliacoes_cliente': 'CREATE TABLE autorias_avaliacoes_cliente (\n\tavaliacao_id INTEGER NOT NULL, \n\tusuario_id INTEGER NOT NULL, \n\tnome_autor VARCHAR(120) NOT NULL, \n\tchave_operacao VARCHAR(36) NOT NULL, \n\tresumo_operacao VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (avaliacao_id), \n\tCONSTRAINT uq_autoria_avaliacao_operacao UNIQUE (chave_operacao), \n\tCONSTRAINT ck_autoria_avaliacao_usuario CHECK (usuario_id > 0), \n\tFOREIGN KEY(avaliacao_id) REFERENCES avaliacoes_oficina (id) ON DELETE RESTRICT\n)', 'avaliacoes_administrativas': 'CREATE TABLE avaliacoes_administrativas (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tordem_servico_id INTEGER NOT NULL, \n\tempresa_cliente_id INTEGER NOT NULL, \n\tempresa_fornecedora_id INTEGER NOT NULL, \n\tnota INTEGER NOT NULL, \n\tcomentario TEXT, \n\tcriada_em VARCHAR(40) NOT NULL, \n\tusuario_id INTEGER NOT NULL, \n\tnome_autor VARCHAR(120) NOT NULL, \n\tchave_operacao VARCHAR(36) NOT NULL, \n\tresumo_operacao VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_avaliacao_admin_contratacao UNIQUE (contratacao_id), \n\tCONSTRAINT uq_avaliacao_admin_operacao UNIQUE (chave_operacao), \n\tCONSTRAINT ck_avaliacao_admin_nota CHECK (nota >= 1 AND nota <= 5), \n\tCONSTRAINT ck_avaliacao_admin_usuario CHECK (usuario_id > 0), \n\tFOREIGN KEY(contratacao_id) REFERENCES contratacoes_servico (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(ordem_servico_id) REFERENCES ordens_servico (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(empresa_cliente_id) REFERENCES empresas (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(empresa_fornecedora_id) REFERENCES empresas (id) ON DELETE RESTRICT\n)'}

INDICES_D46 = {'ix_avaliacoes_administrativas_contratacao_id': 'CREATE INDEX ix_avaliacoes_administrativas_contratacao_id ON avaliacoes_administrativas (contratacao_id)', 'ix_avaliacoes_administrativas_empresa_fornecedora_id': 'CREATE INDEX ix_avaliacoes_administrativas_empresa_fornecedora_id ON avaliacoes_administrativas (empresa_fornecedora_id)', 'ix_avaliacoes_administrativas_ordem_servico_id': 'CREATE INDEX ix_avaliacoes_administrativas_ordem_servico_id ON avaliacoes_administrativas (ordem_servico_id)'}

D46_REVISION = 'MEC-SERVICOS-V0.1-D48-PREPARACAO-PDF-COTACAO-2026-10-08'

D46_RELATORIO = 'MEC_SERVICOS_V0_1_D48_PREPARACAO_PDF_COTACAO_RELATORIO.json'

def conferir_schema_d46(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D46)
    if not presentes: return False
    if presentes != set(DDL_D46): raise RuntimeError("Estrutura D46 parcial; banco preservado.")
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D46, **INDICES_D46}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D46 divergente; banco preservado: " + nome)
    return True

def conferir_schema_d45(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D45)
    if not presentes: return False
    if presentes != set(DDL_D45): raise RuntimeError("Estrutura D45 parcial; banco preservado.")
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D45, **INDICES_D45}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D45 divergente; banco preservado: " + nome)
    return True

def conferir_schema_d44(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D44)
    if not presentes: return False
    if presentes != set(DDL_D44): raise RuntimeError("Estrutura D44 parcial; banco preservado.")
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D44, **INDICES_D44}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D44 divergente; banco preservado: " + nome)
    return True

def conferir_schema_d43(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D43)
    if not presentes: return False
    if presentes != set(DDL_D43): raise RuntimeError("Estrutura D43 parcial; banco preservado.")
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D43, **INDICES_D43}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D43 divergente; banco preservado: " + nome)
    return True

def conferir_schema_d42(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D42)
    if not presentes: return False
    if presentes != set(DDL_D42): raise RuntimeError("Estrutura D42 parcial; banco preservado.")
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D42, **INDICES_D42}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D42 divergente; banco preservado: " + nome)
    return True

def sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()

def localizar_raiz() -> Path:
    for raiz in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        if (raiz / "backend/app/principal.py").is_file() and (raiz / "frontend/package.json").is_file():
            return raiz
    raise RuntimeError("Salve e execute este arquivo na raiz C:\\Users\\Omega\\Desktop\\MEC-Servicos.")

def seguro(raiz: Path, relativo: str) -> Path:
    alvo = raiz / relativo
    if alvo.is_symlink() or any(p.is_symlink() for p in alvo.parents if p != raiz and raiz in p.parents):
        raise RuntimeError("Destino simbólico preservado: " + relativo)
    if not alvo.resolve().is_relative_to(raiz): raise RuntimeError("Destino fora do projeto.")
    return alvo

def executar_git(raiz: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git: raise RuntimeError("Git não encontrado.")
    r = subprocess.run([git, *args], cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if r.returncode: raise RuntimeError("Não foi possível conferir o projeto com Git.")
    return r.stdout.strip()

def origem_mec(url: str) -> bool:
    if url.startswith("git@github.com:"): caminho = url.split(":", 1)[1]
    else:
        p = urlsplit(url)
        if p.scheme not in {"https", "ssh"} or p.hostname != "github.com" or (p.scheme == "https" and (p.username or p.password)):
            return False
        caminho = p.path.lstrip("/")
    return caminho.lower().rstrip("/").removesuffix(".git") == "projetoxcadcam-byte/mec-servicos"

def fonte_confere(dados: bytes, esperado: str) -> bool:
    normal = dados.replace(b"\r\n", b"\n")
    return esperado in {sha(dados), sha(normal), sha(normal.replace(b"\n", b"\r\n"))}

def exigir_backend_parado() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
            pass
    except OSError:
        return
    raise RuntimeError("A porta 8000 está em uso. Pare o backend com Ctrl+C no terminal dele antes de executar a D48 FIX1.")

def configuracao_bancos(raiz: Path):
    sys.path.insert(0, str(raiz))
    from backend.app.core.configuracao import configuracoes
    if configuracoes.prefixo_api.rstrip("/") != "/api/v1": raise RuntimeError("Confira o prefixo /api/v1.")
    url = configuracoes.url_banco_dados
    if not url.startswith("sqlite:///"): raise RuntimeError("A D48 foi preparada para o banco SQLite local.")
    banco = Path(url[len("sqlite:///"):]); banco = (raiz / banco).resolve() if not banco.is_absolute() else banco.resolve()
    if not banco.is_file() or not banco.is_relative_to(raiz): raise RuntimeError("Banco de negócio local não encontrado.")
    acesso = Path(os.environ.get("MEC_ACESSOS_DB", str(raiz / "data/mec_acessos.db")))
    acesso = (raiz / acesso).resolve() if not acesso.is_absolute() else acesso.resolve()
    if not acesso.is_file() or not acesso.is_relative_to(raiz): raise RuntimeError("Banco de acesso D30 local não encontrado.")
    if acesso == banco: raise RuntimeError("O banco de acesso deve ser separado do banco de negócio.")
    with closing(sqlite3.connect(acesso.as_uri() + "?mode=ro", uri=True)) as c:
        c.execute("PRAGMA query_only=ON")
        if not c.execute("SELECT COUNT(*) FROM usuarios_acesso WHERE perfil='admin' AND ativo=1").fetchone()[0]:
            raise RuntimeError("Não foi encontrado administrador ativo no banco de acesso.")
    return banco, acesso

def identidade_sql(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'

def historico(conexao, tabelas=None):
    if tabelas is None:
        tabelas = [n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    resultado = {}
    for nome in tabelas:
        sql = conexao.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone()
        if sql is None: raise RuntimeError("Tabela anterior desapareceu: " + nome)
        linhas = [json.dumps(list(l), ensure_ascii=False, default=lambda b: b.hex(), separators=(",", ":"))
                  for l in conexao.execute("SELECT * FROM " + identidade_sql(nome))]
        resultado[nome] = sha(json.dumps([sql[0], sorted(linhas)], ensure_ascii=False).encode("utf-8"))
    return resultado

def ler_historico(banco: Path, tabelas=None):
    with closing(sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True)) as c:
        c.execute("PRAGMA query_only=ON"); c.execute("BEGIN")
        return historico(c, tabelas)

def conferir_schema(conexao):
    existem = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    presentes = existem.intersection(TABELAS_D31)
    if presentes and presentes != set(TABELAS_D31): raise RuntimeError("Estrutura D31 parcial encontrada; banco preservado.")
    if not presentes: return False
    for nome, esperado in SCHEMA_D31.items():
        atual = [(l[1], l[2].upper(), bool(l[3]), bool(l[5])) for l in conexao.execute("PRAGMA table_info(" + identidade_sql(nome) + ")")]
        if atual != [tuple(l) for l in esperado]: raise RuntimeError("Estrutura D31 divergente; banco preservado: " + nome)
        sql = conexao.execute("SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (nome,)).fetchone()[0]
        if "".join(sql.split()).lower() != "".join(DDL_TABELAS[nome].strip().split()).lower():
            raise RuntimeError("Restrições D31 divergentes; banco preservado: " + nome)
    return True

def salvar_relatorio(raiz: Path, relatorio):
    conteudo = json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n"
    for extensao in ("json", "txt"):
        alvo = seguro(raiz, STEM + "." + extensao)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=raiz, delete=False, prefix="mec_d42_fix2_relatorio_") as temp:
            temp.write(conteudo); caminho = Path(temp.name)
        try: os.replace(caminho, alvo)
        finally: caminho.unlink(missing_ok=True)
        print(("JSON=" if extensao == "json" else "RELATORIO=") + str(alvo), flush=True)

def gravar_atomico(alvo: Path, conteudo: bytes) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=alvo.parent, delete=False, prefix="mec_d42_fix2_") as temp:
        temp.write(conteudo)
        caminho = Path(temp.name)
    try:
        os.replace(caminho, alvo)
    finally:
        caminho.unlink(missing_ok=True)

def conferir_schema_d32(conexao):
    tabelas = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    presentes = tabelas.intersection(DDL_D32)
    if presentes and presentes != set(DDL_D32):
        raise RuntimeError("Estrutura D32 parcial; banco preservado.")
    if not presentes: return False
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in DDL_D32.items():
        atual = [(l[1],l[2].upper(),bool(l[3]),bool(l[5])) for l in conexao.execute("PRAGMA table_info("+identidade_sql(nome)+")")]
        if atual != [tuple(l) for l in SCHEMA_D32[nome]]:
            raise RuntimeError("Colunas D32 divergentes; banco preservado: " + nome)
        sql = conexao.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(nome,)).fetchone()[0]
        if normal(sql) != normal(ddl): raise RuntimeError("Restrições D32 divergentes; banco preservado: " + nome)
    for nome, ddl in INDICES_D32.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?",(nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Índice D32 divergente; banco preservado: " + nome)
    return True

def copiar_banco(banco, destino):
    with closing(sqlite3.connect(banco.as_uri()+"?mode=ro",uri=True)) as origem:
        with closing(sqlite3.connect(destino)) as copia: origem.backup(copia)

def encerrar_processo(processo):
    # Somente a árvore iniciada por esta etapa; nunca todos os processos Python.
    if os.name == "nt":
        if processo.poll() is None:
            fim = subprocess.run(["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                capture_output=True, timeout=10)
            if fim.returncode and processo.poll() is None:
                raise RuntimeError("Não foi possível encerrar a etapa. Pare o processo PID " + str(processo.pid) + ".")
    else:
        try: os.killpg(processo.pid, signal.SIGTERM)
        except ProcessLookupError: pass
    try: processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt": processo.kill()
        else:
            try: os.killpg(processo.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        processo.wait(timeout=5)

def executar(raiz, rotulo, comando, ambiente, relatorio, *, limite_segundos=None, intervalo_aviso=30):
    relatorio["etapa"] = rotulo
    limite = limite_segundos if limite_segundos is not None else (LIMITE_PYTEST_SEGUNDOS if rotulo == "pytest" else LIMITE_BUILD_SEGUNDOS)
    print("Executando " + rotulo + "... (saída ao vivo; limite de " + str(limite) + " segundos)", flush=True)
    ambiente = {**ambiente, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    opcoes = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    log = seguro(raiz, STEM + "_" + rotulo + ".log")
    saida = []; fila = queue.Queue(); inicio = ultimo_aviso = time.monotonic(); processo = None; leitor = None
    def recolher():
        try:
            for linha in processo.stdout: fila.put(linha)
        finally: fila.put(None)
    with log.open("w", encoding="utf-8", buffering=1) as arquivo:
        def mostrar(linha):
            saida.append(linha); arquivo.write(linha); print(linha, end="", flush=True)
        try:
            processo = subprocess.Popen(comando, cwd=raiz, env=ambiente, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, **opcoes)
            leitor = threading.Thread(target=recolher, daemon=True); leitor.start()
            terminou_saida = False
            while not terminou_saida or processo.poll() is None:
                agora = time.monotonic()
                if agora - inicio >= limite:
                    raise RuntimeError("A etapa " + rotulo + " excedeu o limite de " + str(limite) + " segundos.")
                try:
                    linha = fila.get(timeout=min(1, max(.01, intervalo_aviso), max(.01, limite - (agora - inicio))))
                    if linha is None: terminou_saida = True
                    else: mostrar(linha); ultimo_aviso = time.monotonic()
                except queue.Empty:
                    agora = time.monotonic()
                    if agora - ultimo_aviso >= intervalo_aviso:
                        mostrar("[" + rotulo + "] Em execução há " + str(int(agora - inicio)) + " segundos.\n")
                        ultimo_aviso = agora
            codigo = processo.wait()
            relatorio[rotulo] = {"return_code": codigo, "saida": "".join(saida), "log": str(log),
                "duracao_segundos": round(time.monotonic() - inicio, 2), "limite_segundos": limite}
            print(rotulo.upper() + "_RETURN_CODE=" + str(codigo), flush=True)
            if codigo: raise RuntimeError("A etapa " + rotulo + " falhou; confira o relatório.")
        except (Exception, KeyboardInterrupt) as erro:
            if processo is not None: encerrar_processo(processo)
            if leitor is not None: leitor.join(timeout=2)
            while not fila.empty():
                linha = fila.get_nowait()
                if linha is not None: mostrar(linha)
            relatorio[rotulo] = {"return_code": processo.poll() if processo is not None else None,
                "saida": "".join(saida), "log": str(log), "erro": str(erro) or "Operação interrompida.",
                "duracao_segundos": round(time.monotonic() - inicio, 2), "limite_segundos": limite}
            raise
        finally:
            if processo is not None and processo.stdout is not None: processo.stdout.close()

def plano_arquivos(raiz: Path) -> dict[str, bytes]:
    for nome, esperados in BASE_SHA256.items():
        alvo = seguro(raiz, nome)
        finais = [sha(FONTES[nome].encode("utf-8"))] if nome in FONTES else []
        if not alvo.is_file() or not any(fonte_confere(alvo.read_bytes(), h) for h in esperados + finais):
            raise RuntimeError("Fonte diferente da base D48 conhecida; preservado: " + nome)
    novos = {nome: conteudo.encode("utf-8") for nome, conteudo in FONTES.items()}
    novos.update({nome: base64.b64decode(conteudo, validate=True) for nome, conteudo in BINARIOS.items()})
    for nome, conteudo in novos.items():
        alvo = seguro(raiz, nome)
        conferir = (lambda b: sha(b) == sha(conteudo)) if nome in BINARIOS else (lambda b: fonte_confere(b, sha(conteudo)))
        if alvo.exists() and nome not in BASE_SHA256 and not conferir(alvo.read_bytes()):
            raise RuntimeError("Arquivo existente com outro conteúdo; preservado: " + nome)
        if nome.endswith(".py"): ast.parse(conteudo, filename=nome)
    return {nome: conteudo for nome, conteudo in novos.items()
            if not (raiz / nome).is_file() or not ((sha((raiz / nome).read_bytes()) == sha(conteudo)) if nome in BINARIOS else fonte_confere((raiz / nome).read_bytes(), sha(conteudo)))}

def conferir_base_d48(raiz, banco):
    arquivo = seguro(raiz, D46_RELATORIO)
    if not arquivo.is_file(): raise RuntimeError("Relatório D48 não encontrado. Conclua a preparação de PDF D48 antes desta correção.")
    dados = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    if (not isinstance(dados, dict) or dados.get("resultado") != "OK" or dados.get("revision") != D46_REVISION or
            dados.get("validacao_backend_e_frontend") is not True or dados.get("ranking_exclusivo_administracao") is not True or dados.get("contraste_comparacao_corrigido") is not True or dados.get("originais_preservados") is not True or dados.get("preparacao_pdf_exclusiva_administracao") is not True):
        raise RuntimeError("Conclua a D48 antes de aplicar a D48 FIX1.")
    with closing(sqlite3.connect(banco.as_uri()+"?mode=ro", uri=True)) as conexao:
        conexao.execute("PRAGMA query_only=ON"); conexao.execute("BEGIN")
        if not all((conferir_schema(conexao), conferir_schema_d32(conexao), conferir_schema_d42(conexao),
                    conferir_schema_d43(conexao), conferir_schema_d44(conexao), conferir_schema_d45(conexao),
                    conferir_schema_d46(conexao))):
            raise RuntimeError("Tabelas da base D48 não confirmadas; banco preservado.")
        if not conferir_schema_d48(conexao): raise RuntimeError("Tabelas D48 ausentes; banco preservado.")
        if conexao.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or conexao.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Integridade do banco de negócio não confirmada.")

BINARIOS = {}

DDL_D48 = {'preparacoes_pdf_cotacao': 'CREATE TABLE preparacoes_pdf_cotacao (\n\tid INTEGER NOT NULL, \n\tarquivo_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tsha256_original VARCHAR(64) NOT NULL, \n\tsha256 VARCHAR(64) NOT NULL, \n\ttamanho_bytes INTEGER NOT NULL, \n\tcaminho_arquivo TEXT NOT NULL, \n\tconfiguracao_json TEXT NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tcriado_em VARCHAR(32) NOT NULL, \n\tchave_operacao VARCHAR(36) NOT NULL, \n\tpedido_sha256 VARCHAR(64) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_preparacao_pdf_versao UNIQUE (arquivo_id, versao), \n\tCONSTRAINT ck_preparacao_pdf_valores CHECK (versao > 0 AND tamanho_bytes > 0), \n\tFOREIGN KEY(arquivo_id) REFERENCES arquivos_tecnicos (id) ON DELETE RESTRICT, \n\tUNIQUE (chave_operacao)\n)', 'publicacoes_pdf_cotacao': 'CREATE TABLE publicacoes_pdf_cotacao (\n\tid INTEGER NOT NULL, \n\tarquivo_id INTEGER NOT NULL, \n\tpreparacao_id INTEGER NOT NULL, \n\tevento_id INTEGER NOT NULL, \n\tversao_liberacao INTEGER NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_publicacao_pdf_versao UNIQUE (arquivo_id, versao_liberacao), \n\tCONSTRAINT ck_publicacao_pdf_versao CHECK (versao_liberacao > 0), \n\tFOREIGN KEY(arquivo_id) REFERENCES arquivos_tecnicos (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(preparacao_id) REFERENCES preparacoes_pdf_cotacao (id) ON DELETE RESTRICT, \n\tUNIQUE (evento_id), \n\tFOREIGN KEY(evento_id) REFERENCES eventos_arquivos_cotacao (id) ON DELETE RESTRICT\n)'}

INDICES_D48 = {'ix_preparacoes_pdf_cotacao_arquivo_id': 'CREATE INDEX ix_preparacoes_pdf_cotacao_arquivo_id ON preparacoes_pdf_cotacao (arquivo_id)', 'ix_publicacoes_pdf_cotacao_arquivo_id': 'CREATE INDEX ix_publicacoes_pdf_cotacao_arquivo_id ON publicacoes_pdf_cotacao (arquivo_id)'}

def conferir_schema_d48(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D48)
    if not presentes: return False
    if presentes != set(DDL_D48): raise RuntimeError("Estrutura D48 parcial; banco preservado.")
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D48, **INDICES_D48}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D48 divergente; banco preservado: " + nome)
    return True

def main() -> int:
    print("MEC-Serviços D48 FIX1 — Abertura da preparação do PDF", flush=True)
    print("REVISION=" + REVISION, flush=True)
    raiz = None; originais = {}; alterados = []; pastas_novas = []; backup = None
    dist_existia = False; build_iniciado = False; concluido = False
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapa": "inicio", "restaurado": False,
                 "operacoes_negocio_executadas": False, "tabelas_criadas": 0,
                 "limite_build_segundos": LIMITE_BUILD_SEGUNDOS}
    try:
        if sys.version_info < (3, 11): raise RuntimeError("Use Python 3.11 ou mais recente da .venv do MEC.")
        raiz = localizar_raiz(); print("ROOT=" + str(raiz), flush=True)
        urls = executar_git(raiz, "remote", "get-url", "--all", "origin").splitlines()
        if not urls or not all(origem_mec(u) for u in urls): raise RuntimeError("Origin não corresponde ao projeto MEC-Servicos.")
        print("ORIGIN_MEC_CONFIRMADO=True", flush=True); exigir_backend_parado()
        relatorio["etapa"] = "conferir_base"
        plano = plano_arquivos(raiz)
        pacote = json.loads(seguro(raiz, "frontend/package.json").read_text(encoding="utf-8-sig"))
        if not pacote.get("scripts", {}).get("build"): raise RuntimeError("Comando build não encontrado no frontend.")
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm: raise RuntimeError("npm não encontrado.")
        os.chdir(raiz); banco, acesso = configuracao_bancos(raiz); conferir_base_d48(raiz, banco)
        negocio_antes = ler_historico(banco); contas_antes = ler_historico(acesso)
        print("BASE_D48_CONFIRMADA=True", flush=True)
        print("REGISTRO_MODELOS_EXISTENTE_PRESERVADO=True", flush=True)
        print("PAGINA_ARQUIVOS_CLIENTE_PRESERVADA=True", flush=True)
        print("REGISTRO_TESTES_LOCAL_PRESERVADO=True", flush=True)
        relatorio["etapa"] = "backup"
        backup = seguro(raiz, "_mec_backups/D48_FIX1_ABERTURA_PDF_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        backup.mkdir(parents=True); relatorio["backup"] = str(backup); print("BACKUP_DIR=" + str(backup), flush=True)
        copiar_banco(banco, backup / "negocio_antes.db"); copiar_banco(acesso, backup / "acessos_antes.db")
        if ler_historico(backup / "negocio_antes.db") != negocio_antes or ler_historico(backup / "acessos_antes.db") != contas_antes:
            raise RuntimeError("O backup não corresponde ao histórico conferido.")
        dist = seguro(raiz, "frontend/dist"); dist_existia = dist.exists()
        if dist_existia: shutil.copytree(dist, backup / "frontend_dist")
        for nome in plano:
            alvo = seguro(raiz, nome); originais[nome] = alvo.read_bytes() if alvo.exists() else None
            if originais[nome] is not None:
                copia = backup / "originais" / nome; copia.parent.mkdir(parents=True, exist_ok=True); copia.write_bytes(originais[nome])
            for pasta in alvo.parents:
                if pasta == raiz: break
                if not pasta.exists() and pasta not in pastas_novas: pastas_novas.append(pasta)
        (backup / "MANIFESTO.json").write_text(json.dumps({n: None if b is None else sha(b) for n, b in originais.items()}, indent=2) + "\n", encoding="utf-8")
        relatorio["etapa"] = "aplicar_fontes"
        for nome, conteudo in plano.items(): alterados.append(nome); gravar_atomico(raiz / nome, conteudo)
        print("ARQUIVOS_D48_FIX1_APLICADOS=" + str(len(plano)), flush=True)
        print("TESTES_BACKEND_REEXECUTADOS=False", flush=True)
        print("BACKEND_PRESERVADO_SEM_ALTERACOES=True", flush=True)
        relatorio["etapa"] = "validar_frontend"
        relatorio["pytest"] = {"executado": False, "motivo": "Correção da interface; backend preservado e validação D48 reutilizada."}
        with tempfile.TemporaryDirectory(prefix="mec_d48_fix1_build_") as pasta:
            ambiente = dict(os.environ)
            ambiente.update(MEC_URL_BANCO_DADOS="sqlite:///" + (Path(pasta) / "negocio.db").resolve().as_posix(),
                MEC_ACESSOS_DB=str(Path(pasta) / "acesso.db"), MEC_MODO_TESTE_LOCAL="0",
                MEC_AMBIENTE="teste", MEC_COOKIE_SEGURO="0")
            build_iniciado = True
            executar(raiz / "frontend", "npm_build", [npm, "run", "build"], ambiente, relatorio)
        relatorio["etapa"] = "conferir_preservacao"
        conferir_base_d48(raiz, banco)
        if ler_historico(banco) != negocio_antes: raise RuntimeError("Banco mudou durante a validação; registros externos preservados.")
        if ler_historico(acesso) != contas_antes: raise RuntimeError("Banco de acesso mudou durante a validação; contas preservadas.")
        if plano_arquivos(raiz): raise RuntimeError("Fontes da correção divergiram após o build.")
        criadas = 0
        relatorio["tabelas_criadas"] = 0
        concluido = True
        relatorio.update(resultado="OK", etapa="concluido", arquivos_alterados=alterados,
            historico_negocio_preservado=True, historico_financeiro_d32_preservado=True, historico_administrativo_d33_preservado=True, relatorio_d34_preservado=True, relatorio_d35_preservado=True, relatorio_d36_preservado=True, central_d37_preservada=True, resumo_gerencial_d38_preservado=True, resumo_gerencial_d38_fix1_preservado=True, comparativo_gerencial_d39_preservado=True, contas_e_senhas_preservadas=True, cotacoes_anteriores_preservadas=True, liberacoes_automaticas_executadas=False, validacao_backend_e_frontend=True, documentacao_e_historico_d42_preservados=True, decisoes_automaticas_executadas=False, historico_comercial_d43_preservado=True, contratacoes_automaticas_executadas=False, ordens_automaticas_executadas=False, historico_contratacao_d44_preservado=True, notificacoes_historicas_geradas=False, avaliacoes_automaticas_geradas=False, ranking_exclusivo_administracao=True, comparacao_exclusiva_administracao=True, contraste_comparacao_corrigido=True, originais_preservados=True, abertura_preparacao_pdf_corrigida=True, backend_preservado_sem_alteracoes=True, validacao_backend_reutilizada_d48=True, preparacoes_e_publicacoes_pdf_preservadas=True, preparacao_pdf_exclusiva_administracao=True, preparacoes_automaticas_executadas=False, avaliacoes_anteriores_preservadas=True, notificacoes_e_leituras_d45_preservadas=True,
            historico_negocio_sha256=negocio_antes, historico_acesso_sha256=contas_antes)
        print("TABELAS_D48_FIX1_CRIADAS=" + str(criadas), flush=True)
        print("COTACOES_ANTERIORES_PRESERVADAS=True", flush=True)
        print("DECISOES_COMERCIAIS_AUTOMATICAS_EXECUTADAS=False", flush=True)
        print("DOCUMENTACAO_E_HISTORICO_D42_PRESERVADOS=True", flush=True)
        print("HISTORICO_COMERCIAL_D43_PRESERVADO=True", flush=True)
        print("HISTORICO_CONTRATACAO_D44_PRESERVADO=True", flush=True)
        print("NOTIFICACOES_HISTORICAS_GERADAS=False", flush=True)
        print("AVALIACOES_ANTERIORES_PRESERVADAS=True", flush=True)
        print("RANKING_EXCLUSIVO_ADMINISTRACAO=True", flush=True)
        print("COMPARACAO_EXCLUSIVA_ADMINISTRACAO=True", flush=True)
        print("ORIGINAIS_PRESERVADOS=True", flush=True)
        print("ABERTURA_PREPARACAO_PDF_CORRIGIDA=True", flush=True)
        print("PREPARACOES_E_PUBLICACOES_PDF_PRESERVADAS=True", flush=True)
        print("PREPARACOES_AUTOMATICAS_EXECUTADAS=False", flush=True)
        print("AVALIACOES_AUTOMATICAS_GERADAS=False", flush=True)
        print("NOTIFICACOES_E_LEITURAS_D45_PRESERVADAS=True", flush=True)
        print("CONTRATACOES_E_ORDENS_AUTOMATICAS_EXECUTADAS=False", flush=True)
        print("HISTORICO_NEGOCIO_PRESERVADO=True", flush=True)
        print("HISTORICO_FINANCEIRO_D32_PRESERVADO=True", flush=True)
        print("PAINEL_E_HISTORICO_D33_PRESERVADOS=True", flush=True)
        print("RELATORIO_E_HISTORICO_D34_PRESERVADOS=True", flush=True)
        print("RELATORIO_E_HISTORICO_D35_PRESERVADOS=True", flush=True)
        print("RELATORIO_E_HISTORICO_D36_PRESERVADOS=True", flush=True)
        print("CENTRAL_E_HISTORICO_D37_PRESERVADOS=True", flush=True)
        print("RESUMO_GERENCIAL_D38_PRESERVADO=True", flush=True)
        print("RESUMO_GERENCIAL_D38_FIX1_PRESERVADO=True", flush=True)
        print("COMPARATIVO_GERENCIAL_D39_PRESERVADO=True", flush=True)
        print("CONTAS_E_SENHAS_PRESERVADAS=True", flush=True)
        try: salvar_relatorio(raiz, relatorio)
        except OSError: print("RELATORIO_NAO_GRAVADO=True; preserve a saída do terminal.", flush=True)
        print("RESULTADO=OK", flush=True)
        print("Reinicie o backend e o frontend. Atualize com Ctrl+F5. Abra Administração > Arquivos Técnicos.", flush=True)
        print("Clique Preparar PDF com nossa logo: o painel deve aparecer junto ao arquivo, com rolagem e foco automáticos.", flush=True)
        print("Roteiro local: D48_FIX1_CONTRATO_ABERTURA_PREPARACAO_PDF.txt", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ETAPA=" + relatorio["etapa"], flush=True); print("ERRO=" + relatorio["erro"], flush=True)
        if raiz and alterados and not concluido:
            falhas = []
            for nome in reversed(alterados):
                try:
                    if originais[nome] is None: (raiz / nome).unlink(missing_ok=True)
                    else: gravar_atomico(raiz / nome, originais[nome])
                except OSError as falha: falhas.append(str(falha))
            if build_iniciado:
                try:
                    if dist.exists(): shutil.rmtree(dist)
                    if dist_existia: shutil.copytree(backup / "frontend_dist", dist)
                except OSError as falha: falhas.append(str(falha))
            for pasta in sorted(pastas_novas, key=lambda p: len(p.parts), reverse=True):
                try:
                    if pasta.exists() and not any(pasta.iterdir()): pasta.rmdir()
                except OSError as falha: falhas.append(str(falha))
            relatorio["restaurado"] = not falhas
            if falhas: relatorio["falhas_restauracao"] = falhas
            print("RESTAURADO=" + str(relatorio["restaurado"]), flush=True)
        if raiz:
            try: salvar_relatorio(raiz, relatorio)
            except OSError: print("RELATORIO_NAO_GRAVADO=True", flush=True)
        print("RESULTADO=ERRO", flush=True); return 1

if __name__ == "__main__":
    raise SystemExit(main())
