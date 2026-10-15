"""MEC-Serviços D66 FIX1 — Caminhos do instalador no Windows, instalado apenas no frontend."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit

REVISION = "MEC-SERVICOS-V0.1-D66-FIX1-CAMINHOS-WINDOWS-2026-10-15"
REVISION_D65 = "MEC-SERVICOS-V0.1-D65-PDF-METAS-2026-10-14"
STEM = "MEC_SERVICOS_V0_1_D66_FIX1_CAMINHOS_WINDOWS_RELATORIO"
FONTES = {'frontend/src/pages/tutorial/Tutorial.css': '.t66 { color: #eaf2fc; max-width: 1400px; margin: 0 auto; line-height: 1.6; }\n.t66 * { box-sizing: border-box; }\n.t66 h1, .t66 h2, .t66 h3, .t66 p { margin-top: 0; }\n.t66 h1 { font-size: clamp(26px, 3vw, 36px); line-height: 1.2; margin-bottom: 12px; }\n.t66 h2 { font-size: 24px; line-height: 1.35; margin-bottom: 12px; overflow-wrap: anywhere; }\n.t66 h3 { font-size: 16px; margin-bottom: 10px; }\n.t66-cabecalho { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 28px; }\n.t66-perfil { display: flex; gap: 9px; align-items: center; color: #96c9ff; font-size: 11px; font-weight: 750; letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 12px; }\n.t66-introducao { color: #b5c4d6; max-width: 730px; margin-bottom: 0; }\n.t66 .t66-botao { display: inline-flex; align-items: center; justify-content: center; gap: 9px; background: #245ebc; color: #fff; border: 1px solid #5996ed; border-radius: 9px; min-height: 44px; padding: 11px 16px; font: inherit; font-size: 13px; font-weight: 650; line-height: 1.4; cursor: pointer; text-decoration: none; text-align: center; }\n.t66 .t66-botao:hover { background: #2b6bcc; border-color: #9bc6ff; }\n.t66 .t66-secundario { background: #142337; border-color: #3b526b; color: #d6e6f8; }\n.t66 .t66-secundario:hover { background: #1c314b; }\n.t66 .t66-botao:disabled { opacity: .45; cursor: default; }\n.t66 :is(button,a,input,summary):focus-visible { outline: 3px solid #a9d4ff; outline-offset: 4px; }\n.t66 h2:focus { outline: 2px solid #70b2ff; outline-offset: 7px; border-radius: 3px; }\n.t66-progresso { display: flex; align-items: center; flex-wrap: wrap; gap: 20px; border: 1px solid #30445d; padding: 18px 20px; background: #101d2d; border-radius: 12px; }\n.t66-progresso > div { flex: 1 1 260px; }\n.t66-progresso strong, .t66-progresso span { display: block; }\n.t66-progresso span { font-size: 12px; color: #acbfd4; margin-top: 4px; }\n.t66 progress { width: 180px; height: 9px; accent-color: #74b6ff; border: 0; border-radius: 20px; background: #28394f; overflow: hidden; }\n.t66 progress::-webkit-progress-bar { background: #28394f; border-radius: 20px; }\n.t66 progress::-webkit-progress-value { background: #74b6ff; border-radius: 20px; }\n.t66 progress::-moz-progress-bar { background: #74b6ff; border-radius: 20px; }\n.t66-confirmacao { padding: 18px 20px; border: 1px solid #6b82a0; margin-top: 14px; border-radius: 10px; background: #15263b; }\n.t66-aviso { min-height: 22px; margin: 10px 0; color: #a7e0c4; font-size: 13px; }\n.t66-corpo { display: grid; grid-template-columns: minmax(240px, 310px) minmax(0, 1fr); gap: 22px; align-items: start; }\n.t66-indice { padding: 18px; border: 1px solid #2c4058; border-radius: 12px; background: #0e1928; }\n.t66-busca { display: block; }\n.t66-busca > span { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 650; color: #c2d4e9; margin-bottom: 9px; }\n.t66 .t66-busca input { width: 100%; min-width: 0; min-height: 44px; padding: 11px 12px; color: #f0f6ff; background: #101f32; border: 1px solid #476080; border-radius: 8px; font: inherit; font-size: 13px; }\n.t66-busca input::placeholder { color: #9db1ca; opacity: 1; }\n.t66-resultado-busca { font-size: 11px; color: #a9bad0; margin: 10px 0 16px; }\n.t66-indice ol { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }\n.t66 .t66-item { display: flex; align-items: flex-start; gap: 10px; width: 100%; padding: 12px 9px; text-align: left; color: #c1d1e6; background: transparent; border: 1px solid transparent; border-radius: 8px; cursor: pointer; font: inherit; line-height: 1.4; }\n.t66 .t66-item:hover { background: #17283c; }\n.t66 .t66-item.t66-ativo { background: #173151; border-color: #4c83be; color: #f2f7ff; }\n.t66-numero { display: flex; align-items: center; justify-content: center; flex: 0 0 25px; width: 25px; height: 25px; border-radius: 50%; background: #263f5d; color: #c2e0ff; font-size: 11px; font-weight: 700; margin-top: 2px; }\n.t66-item small, .t66-item strong, .t66-lida { display: block; }\n.t66-item small { color: #a2b8d2; font-size: 10px; margin-bottom: 4px; }\n.t66-item strong { font-size: 12px; font-weight: 600; }\n.t66-lida { color: #a1dfbd; font-size: 10px; margin-top: 6px; }\n.t66-sem-resultado { color: #bacce1; font-size: 13px; }\n.t66-etapa { min-width: 0; padding: clamp(20px, 3vw, 34px); border: 1px solid #30455e; background: #101d2d; border-radius: 14px; }\n.t66-etiqueta { color: #96c7ff; font-size: 12px; font-weight: 650; margin-bottom: 12px; }\n.t66-etapa h2 { scroll-margin-top: 32px; }\n.t66-resumo { color: #b8c9df; font-size: 15px; margin-bottom: 24px; }\n.t66-onde { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; padding: 18px; background: #14283e; border: 1px solid #365979; border-radius: 10px; margin-bottom: 28px; }\n.t66-onde > div { flex: 1 1 160px; min-width: 0; overflow-wrap: anywhere; }\n.t66-onde small { display: block; color: #9bb9dc; font-size: 10px; font-weight: 700; letter-spacing: .9px; margin-bottom: 5px; }\n.t66-onde strong { font-size: 14px; }\n.t66-passos { margin: 0 0 26px; padding: 0; list-style: none; display: grid; gap: 17px; }\n.t66-passos li { display: flex; align-items: flex-start; gap: 13px; }\n.t66-passos li > span { display: flex; align-items: center; justify-content: center; flex: 0 0 28px; height: 28px; border-radius: 8px; color: #b9d9ff; background: #243c58; font-size: 12px; font-weight: 700; }\n.t66-passos p { font-size: 14px; color: #d0def0; margin: 1px 0 0; overflow-wrap: anywhere; }\n.t66-esperado, .t66-dica { padding: 17px 18px; border-left: 3px solid #64b595; background: #122c2a; margin-bottom: 18px; border-radius: 0 8px 8px 0; }\n.t66-esperado h3 { color: #b5ead7; font-size: 13px; }\n.t66-esperado p, .t66-dica p { font-size: 13px; margin: 0; color: #c9dcd7; }\n.t66-dica { border-left-color: #6d9fdd; background: #14273e; }\n.t66-dica h3 { color: #bdd8ff; font-size: 13px; }\n.t66-dica p { color: #bdcfe6; }\n.t66-acoes { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 22px; }\n.t66-leitura, .t66-retorno { color: #a8bbd2; font-size: 12px; margin: 12px 0 0; }\n.t66-sequencia { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; border-top: 1px solid #30445d; padding-top: 22px; margin-top: 26px; }\n.t66-duvidas { margin-top: 30px; padding: 24px; background: #101c2b; border: 1px solid #30445d; border-radius: 12px; }\n.t66-duvidas h2 { font-size: 20px; margin-bottom: 18px; }\n.t66-duvidas details { border-top: 1px solid #30445d; padding: 16px 0; }\n.t66-duvidas details:last-child { padding-bottom: 0; }\n.t66-duvidas summary { font-size: 14px; font-weight: 600; color: #d0e2fa; cursor: pointer; }\n.t66-duvidas details p { font-size: 13px; margin: 14px 0 0; color: #b5c8df; max-width: 1000px; }\n@media (max-width: 1000px) {\n  .t66-corpo { grid-template-columns: 1fr; }\n  .t66-indice nav { max-height: 280px; overflow-y: auto; }\n  .t66-indice ol { grid-template-columns: repeat(2, minmax(0, 1fr)); }\n  .t66-cabecalho { flex-direction: column; gap: 16px; }\n}\n@media (max-width: 600px) {\n  .t66-indice ol { grid-template-columns: 1fr; }\n  .t66-progresso { padding: 16px; gap: 14px; }\n  .t66 progress { flex: 1 1 100%; width: 100%; }\n  .t66-onde .t66-botao { width: 100%; }\n  .t66-sequencia .t66-botao { flex: 1 1 170px; }\n  .t66 h2 { font-size: 21px; }\n}\n@media (prefers-reduced-motion: reduce) { .t66 * { scroll-behavior: auto !important; } }\n', 'frontend/src/pages/tutorial/TutorialEntrada.tsx': 'import { lazy, Suspense } from "react";\nimport type { PerfilTutorial } from "./dadosTutorial";\n\nconst TutorialPage = lazy(() => import("./TutorialPage"));\n\nexport default function TutorialEntrada({ perfil }: { perfil: PerfilTutorial }) {\n  return <Suspense fallback={<section className="t66"><p role="status">Abrindo o tutorial…</p></section>}>\n    <TutorialPage perfil={perfil} />\n  </Suspense>;\n}\n', 'frontend/src/pages/tutorial/TutorialPage.tsx': 'import { useEffect, useRef, useState } from "react";\nimport { ArrowLeft, ArrowRight, BookOpen, Check, Search } from "lucide-react";\nimport { Link, useSearchParams } from "react-router-dom";\nimport { useAuth } from "../../auth/AuthContext";\nimport { GUIAS, filtrarEtapas, type PerfilTutorial } from "./dadosTutorial";\nimport { chaveTutorial, lerProgresso, salvarProgresso } from "./progressoTutorial";\nimport "./Tutorial.css";\n\nfunction armazenamentoLocal(): Storage | undefined {\n  try { return window.localStorage; } catch { return undefined; }\n}\n\nexport default function TutorialPage({ perfil }: { perfil: PerfilTutorial }) {\n  const { user } = useAuth();\n  if (!user || user.role !== perfil || user.deve_alterar_senha) {\n    return <section className="t66"><p role="alert">Entre com seu perfil e conclua a atualização do acesso para abrir o tutorial.</p></section>;\n  }\n  const chave = chaveTutorial(user.usuario_id, perfil, user.empresa_id);\n  return <ConteudoTutorial key={chave} perfil={perfil} chave={chave} />;\n}\n\nfunction ConteudoTutorial({ perfil, chave }: { perfil: PerfilTutorial; chave: string }) {\n  const guia = GUIAS[perfil];\n  const [parametros, setParametros] = useSearchParams();\n  const [progresso, setProgresso] = useState(() => lerProgresso(armazenamentoLocal(), chave, guia.etapas.map(etapa => etapa.id)));\n  const [busca, setBusca] = useState("");\n  const [salvo, setSalvo] = useState(true);\n  const [aviso, setAviso] = useState("");\n  const [reiniciando, setReiniciando] = useState(false);\n  const titulo = useRef<HTMLHeadingElement>(null);\n  const etapaUrl = parametros.get("etapa");\n  const indiceUrl = guia.etapas.findIndex(etapa => etapa.id === etapaUrl);\n  const indice = indiceUrl >= 0 ? indiceUrl : Math.max(0, guia.etapas.findIndex(etapa => etapa.id === progresso.ultima));\n  const atual = guia.etapas[indice];\n  const filtradas = filtrarEtapas(guia, busca);\n  const lida = progresso.lidas.includes(atual.id);\n\n  useEffect(() => {\n    titulo.current?.focus({ preventScroll: true });\n  }, [atual.id]);\n\n  function guardar(valor: typeof progresso) {\n    setProgresso(valor);\n    setSalvo(salvarProgresso(armazenamentoLocal(), chave, valor));\n  }\n  function selecionar(id: string) {\n    if (!guia.etapas.some(etapa => etapa.id === id)) return;\n    setAviso(""); setReiniciando(false);\n    guardar({ ...progresso, ultima: id });\n    setParametros({ etapa: id });\n    titulo.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });\n  }\n  function alternarLeitura() {\n    guardar({ ...progresso, ultima: atual.id, lidas: lida ? progresso.lidas.filter(id => id !== atual.id) : [...progresso.lidas, atual.id] });\n    setAviso(lida ? "Etapa marcada para reler." : "Leitura desta etapa concluída.");\n  }\n  function reiniciar() {\n    guardar({ versao: 1, lidas: [], ultima: guia.etapas[0].id });\n    setBusca(""); setParametros({ etapa: guia.etapas[0].id });\n    setReiniciando(false); setAviso("Progresso de leitura reiniciado.");\n  }\n\n  return <section className="t66" aria-label={`Tutorial do perfil ${guia.nome}`}>\n    <header className="t66-cabecalho">\n      <div><p className="t66-perfil"><BookOpen size={17} aria-hidden="true" /> GUIA DO PERFIL · {guia.nome}</p>\n        <h1>Ajuda e tutorial</h1><p className="t66-introducao">{guia.introducao}</p></div>\n      <Link className="t66-botao t66-secundario" to={perfil === "admin" ? "/admin" : `/${perfil}`}>Ir ao Dashboard <ArrowRight size={16} aria-hidden="true" /></Link>\n    </header>\n\n    <div className="t66-progresso">\n      <div><strong>{progresso.lidas.length} de {guia.etapas.length} etapas lidas</strong>\n        <span>{salvo ? "Sua leitura fica salva neste navegador para esta conta." : "Você pode continuar. A leitura ficará marcada enquanto esta página estiver aberta."}</span></div>\n      <progress value={progresso.lidas.length} max={guia.etapas.length} aria-label="Progresso de leitura do tutorial" />\n      <button className="t66-botao t66-secundario" type="button" onClick={() => setReiniciando(valor => !valor)} aria-expanded={reiniciando} aria-controls="t66-reiniciar">Reiniciar leitura</button>\n    </div>\n    {reiniciando && <div className="t66-confirmacao" id="t66-reiniciar"><p>Deseja limpar as marcações de leitura deste tutorial para sua conta neste navegador?</p>\n      <div className="t66-acoes"><button className="t66-botao" type="button" onClick={reiniciar}>Confirmar reinício da leitura</button>\n        <button className="t66-botao t66-secundario" type="button" onClick={() => setReiniciando(false)}>Continuar como está</button></div></div>}\n    <p className="t66-aviso" role="status" aria-live="polite">{aviso}</p>\n\n    <div className="t66-corpo">\n      <aside className="t66-indice" aria-label="Índice do tutorial">\n        <label className="t66-busca"><span><Search size={16} aria-hidden="true" /> Buscar no tutorial</span>\n          <input type="search" value={busca} maxLength={120} onChange={evento => setBusca(evento.target.value)} placeholder="Ex.: orçamento, produção…" /></label>\n        <p className="t66-resultado-busca" aria-live="polite">{busca.trim() ? `${filtradas.length} etapa(s) encontrada(s)` : "Escolha uma etapa ou siga a sequência."}</p>\n        <nav aria-label="Etapas do tutorial"><ol>{filtradas.map(etapa => <li key={etapa.id}>\n          <button type="button" className={`t66-item ${etapa.id === atual.id ? "t66-ativo" : ""}`} aria-current={etapa.id === atual.id ? "step" : undefined} onClick={() => selecionar(etapa.id)}>\n            <span className="t66-numero" aria-hidden="true">{progresso.lidas.includes(etapa.id) ? <Check size={16} /> : guia.etapas.indexOf(etapa) + 1}</span>\n            <span><small>{etapa.categoria}</small><strong>{etapa.titulo}</strong>{progresso.lidas.includes(etapa.id) && <span className="t66-lida">Leitura concluída</span>}</span>\n          </button>\n        </li>)}</ol></nav>\n        {!filtradas.length && <div className="t66-sem-resultado"><p>Nenhuma etapa corresponde à busca.</p><button className="t66-botao t66-secundario" type="button" onClick={() => setBusca("")}>Limpar busca</button></div>}\n      </aside>\n\n      <article className="t66-etapa" aria-labelledby="t66-titulo-etapa">\n        <p className="t66-etiqueta">Etapa {indice + 1} de {guia.etapas.length} · {atual.categoria}</p>\n        <h2 id="t66-titulo-etapa" ref={titulo} tabIndex={-1}>{atual.titulo}</h2>\n        <p className="t66-resumo">{atual.resumo}</p>\n        <div className="t66-onde"><div><small>ONDE FAZER</small><strong>{atual.onde}</strong></div>\n          <Link className="t66-botao" to={atual.caminho}>Abrir esta tela <ArrowRight size={16} aria-hidden="true" /></Link></div>\n        <h3>Passo a passo</h3><ol className="t66-passos">{atual.passos.map((passo, numero) => <li key={numero}><span aria-hidden="true">{numero + 1}</span><p>{passo}</p></li>)}</ol>\n        <div className="t66-esperado"><h3>O que esperar</h3><p>{atual.resultado}</p></div>\n        {atual.dica && <div className="t66-dica"><h3>Para conferir</h3><p>{atual.dica}</p></div>}\n        <div className="t66-acoes"><button className={`t66-botao ${lida ? "t66-secundario" : ""}`} type="button" aria-pressed={lida} onClick={alternarLeitura}><Check size={16} aria-hidden="true" />{lida ? "Marcar para reler" : "Concluir leitura desta etapa"}</button></div>\n        <p className="t66-leitura">A marcação acompanha sua leitura. Para executar o procedimento, abra a tela e confira os dados do serviço.</p>\n        <nav className="t66-sequencia" aria-label="Avançar no tutorial">\n          <button className="t66-botao t66-secundario" type="button" disabled={indice === 0} onClick={() => selecionar(guia.etapas[indice - 1].id)}><ArrowLeft size={16} aria-hidden="true" /> Etapa anterior</button>\n          <button className="t66-botao" type="button" disabled={indice === guia.etapas.length - 1} onClick={() => selecionar(guia.etapas[indice + 1].id)}>Próxima etapa <ArrowRight size={16} aria-hidden="true" /></button>\n        </nav>\n        <p className="t66-retorno">Depois de usar a tela, escolha <strong>Ajuda e tutorial</strong> no menu para voltar ao guia.</p>\n      </article>\n    </div>\n\n    <section className="t66-duvidas" aria-labelledby="t66-duvidas"><h2 id="t66-duvidas">Dúvidas frequentes</h2>\n      {guia.duvidas.map(duvida => <details key={duvida.pergunta}><summary>{duvida.pergunta}</summary><p>{duvida.resposta}</p></details>)}\n    </section>\n  </section>;\n}\n', 'frontend/src/pages/tutorial/dadosTutorial.ts': 'export type PerfilTutorial = "admin" | "cliente" | "fornecedor";\nexport type EtapaTutorial = {\n  id: string;\n  categoria: string;\n  titulo: string;\n  resumo: string;\n  onde: string;\n  caminho: string;\n  passos: string[];\n  resultado: string;\n  dica?: string;\n};\nexport type GuiaTutorial = {\n  nome: string;\n  introducao: string;\n  etapas: EtapaTutorial[];\n  duvidas: { pergunta: string; resposta: string }[];\n};\n\nexport const GUIAS: Record<PerfilTutorial, GuiaTutorial> = {\n  cliente: {\n    nome: "Cliente",\n    introducao: "Aprenda a solicitar um serviço, analisar o orçamento e acompanhar suas peças até a entrega.",\n    etapas: [\n      {\n        id: "inicio", categoria: "Primeiros passos", titulo: "Conheça seu painel",\n        resumo: "Encontre as pendências e acompanhe os serviços da sua empresa.",\n        onde: "Dashboard", caminho: "/cliente",\n        passos: ["Confira o nome da sua conta no topo da página.", "Abra o Dashboard e consulte os indicadores e os atalhos disponíveis.", "Anote o número da solicitação, da contratação ou da OS para localizar o mesmo serviço nas outras telas."],\n        resultado: "Você sabe onde encontrar seus pedidos e quais itens precisam de atenção.",\n        dica: "Solicitação, cotação, contratação e OS têm números próprios. Use o número correspondente ao filtro de cada tela.",\n      },\n      {\n        id: "solicitacao", categoria: "Solicitação e orçamento", titulo: "Crie uma solicitação de serviço",\n        resumo: "Informe o que precisa ser fabricado ou executado.",\n        onde: "Minhas Solicitações", caminho: "/cliente/solicitacoes",\n        passos: ["Clique na opção de nova solicitação e selecione processo e material.", "Informe quantidade, dimensões e os requisitos técnicos pedidos no formulário.", "Descreva as operações necessárias e as informações relevantes em Observações. Confira os dados e salve a solicitação."],\n        resultado: "A solicitação recebe um número e fica disponível para acompanhamento.",\n        dica: "Descreva o escopo real: uma peça de desbaste pode ter requisitos diferentes de uma peça acabada. Informe somente as exigências do serviço.",\n      },\n      {\n        id: "arquivos", categoria: "Solicitação e orçamento", titulo: "Envie o desenho e os arquivos técnicos",\n        resumo: "Vincule a documentação correta à solicitação.",\n        onde: "Arquivos Técnicos", caminho: "/cliente/arquivos-tecnicos",\n        passos: ["Localize a solicitação pelo número recebido na etapa anterior.", "Selecione o arquivo técnico e envie-o para essa solicitação.", "Confira a identificação do arquivo e acompanhe a revisão pela administração. Se precisar substituir o documento, comunique a alteração e confira a versão enviada."],\n        resultado: "A administração pode revisar a documentação e liberar o serviço para cotação.",\n        dica: "O fornecedor precisa de documentação técnica válida e liberada. O envio do arquivo é seguido pela revisão administrativa.",\n      },\n      {\n        id: "orcamento", categoria: "Solicitação e orçamento", titulo: "Analise o orçamento publicado",\n        resumo: "Confira o preço final, o prazo e as condições apresentadas.",\n        onde: "Cotações Recebidas", caminho: "/cliente/cotacoes",\n        passos: ["Pesquise a solicitação e abra Ver detalhes na cotação publicada para sua empresa.", "Confira valor total, quantidade, processo, material, prazo e validade da proposta.", "Use as opções de análise disponíveis para aprovar, solicitar revisão ou recusar. Revise sua decisão antes de confirmar."],\n        resultado: "Sua análise fica registrada para a administração dar continuidade ao pedido.",\n        dica: "A aprovação do orçamento é seguida pela formalização da contratação e da OS pela administração.",\n      },\n      {\n        id: "contratacao", categoria: "Execução e entrega", titulo: "Confira a contratação e a OS",\n        resumo: "Consulte a formalização do serviço aprovado.",\n        onde: "Minhas Contratações", caminho: "/cliente/contratacoes",\n        passos: ["Localize a solicitação e abra a contratação correspondente.", "Confira valor, prazo, situação e instruções de execução.", "Consulte Ordens de Serviço no menu e identifique a OS vinculada ao mesmo pedido."],\n        resultado: "Você identifica o serviço contratado e sua ordem de execução.",\n      },\n      {\n        id: "producao", categoria: "Execução e entrega", titulo: "Acompanhe a produção",\n        resumo: "Veja as etapas e as atualizações registradas pelo fornecedor.",\n        onde: "Acompanhamento de Produção", caminho: "/cliente/producao",\n        passos: ["Selecione a OS e abra Ver histórico.", "Confira a etapa atual e as datas das atualizações.", "Use Atualizar histórico para consultar uma alteração recente e acompanhe as notificações no topo do sistema."],\n        resultado: "Você acompanha o andamento da fabricação e as informações liberadas para sua empresa.",\n        dica: "Pronto para coleta indica uma etapa da produção. A coleta e a entrega ao cliente são acompanhadas pela administração.",\n      },\n      {\n        id: "entrega", categoria: "Execução e entrega", titulo: "Consulte a entrega das peças",\n        resumo: "Acompanhe a movimentação e o histórico da entrega.",\n        onde: "Entregas e Aceite", caminho: "/cliente/entregas",\n        passos: ["Localize a OS e clique em Ver histórico.", "Confira os registros de coleta, conferência e entrega disponíveis no seu portal.", "Comunique à administração qualquer divergência entre as peças recebidas e o serviço contratado."],\n        resultado: "Você confere a situação da entrega e mantém o acompanhamento do pedido.",\n      },\n      {\n        id: "pagamentos", categoria: "Financeiro e avaliação", titulo: "Acompanhe os pagamentos do serviço",\n        resumo: "Confira os valores e os registros financeiros da contratação.",\n        onde: "Pagamentos", caminho: "/cliente/pagamentos",\n        passos: ["Localize a contratação correspondente ao serviço.", "Confira o valor previsto, os recebimentos registrados e o saldo apresentado.", "Se houver diferença em relação ao pagamento realizado, encaminhe o comprovante à administração para conferência."],\n        resultado: "Você acompanha o saldo com base nos registros financeiros do serviço.",\n        dica: "Os registros no portal representam o controle do serviço. Confirme com a administração o meio de pagamento combinado.",\n      },\n      {\n        id: "avaliacao", categoria: "Financeiro e avaliação", titulo: "Avalie o serviço recebido",\n        resumo: "Registre sua nota quando a avaliação estiver disponível.",\n        onde: "Avaliações", caminho: "/cliente/avaliacoes",\n        passos: ["Pesquise a contratação ou a OS e abra os detalhes.", "Quando a avaliação estiver habilitada, selecione uma nota de 1 a 5 e, se desejar, escreva um comentário.", "Clique em Revisar avaliação, confira as informações e confirme o registro."],\n        resultado: "Sua avaliação fica vinculada ao serviço para acompanhamento da qualidade.",\n      },\n      {\n        id: "conta", categoria: "Primeiros passos", titulo: "Use as notificações e sua conta",\n        resumo: "Consulte novidades e mantenha seu acesso atualizado.",\n        onde: "Minha conta, no topo do sistema", caminho: "/conta",\n        passos: ["Consulte o centro de notificações no topo e abra os avisos relevantes para seus serviços.", "Use Minha conta para consultar seu acesso e alterar sua senha quando necessário.", "Ao voltar ao programa, use o menu Ajuda e tutorial para continuar esta leitura."],\n        resultado: "Você sabe acompanhar os avisos e gerenciar seu próprio acesso.",\n      },\n    ],\n    duvidas: [\n      { pergunta: "Enviei a solicitação. Por que ainda não recebi orçamento?", resposta: "Confira o envio dos arquivos técnicos e a revisão da administração. Depois da liberação, o orçamento passa pelo fornecedor e pela preparação administrativa antes de ser publicado para sua análise." },\n      { pergunta: "Aprovei o orçamento. Onde aparece a ordem de serviço?", resposta: "A administração formaliza a contratação e a abertura da OS. Acompanhe Minhas Contratações, Ordens de Serviço e as notificações." },\n      { pergunta: "Por que uma informação recente ainda não aparece?", resposta: "Confira a conta e a empresa selecionadas, o número pesquisado e os filtros. Use Atualizar na tela correspondente para consultar o registro mais recente." },\n    ],\n  },\n  fornecedor: {\n    nome: "Fornecedor",\n    introducao: "Aprenda a consultar oportunidades, enviar propostas e atualizar a execução dos serviços da sua empresa.",\n    etapas: [\n      {\n        id: "inicio", categoria: "Primeiros passos", titulo: "Conheça o painel do fornecedor",\n        resumo: "Consulte as oportunidades e as pendências da sua empresa.",\n        onde: "Dashboard", caminho: "/fornecedor",\n        passos: ["Confira a identificação da sua empresa no acesso ao portal.", "Consulte o Dashboard e os atalhos para oportunidades, contratos e ordens.", "Use o número da solicitação ou da OS para acompanhar o mesmo serviço nas diferentes telas."],\n        resultado: "Você identifica as pendências da sua empresa e as telas de trabalho.",\n      },\n      {\n        id: "oportunidades", categoria: "Oportunidades e propostas", titulo: "Consulte as oportunidades disponíveis",\n        resumo: "Encontre os serviços liberados para cotação.",\n        onde: "Solicitações Disponíveis", caminho: "/fornecedor/solicitacoes",\n        passos: ["Abra Solicitações Disponíveis e consulte as oportunidades apresentadas ao seu perfil.", "Abra a solicitação e confira processo, material, quantidade, dimensões e observações.", "Verifique se a capacidade da sua empresa atende às exigências antes de preparar a proposta."],\n        resultado: "Você identifica um serviço compatível com sua capacidade de execução.",\n        dica: "A disponibilidade depende da situação da solicitação, da documentação liberada e das regras de compatibilidade do cadastro.",\n      },\n      {\n        id: "arquivos", categoria: "Oportunidades e propostas", titulo: "Baixe e confira a documentação técnica",\n        resumo: "Use os documentos liberados para elaborar o orçamento.",\n        onde: "Arquivos Técnicos", caminho: "/fornecedor/arquivos-tecnicos",\n        passos: ["Localize a solicitação ou o serviço apresentado ao seu portal.", "Baixe os arquivos disponibilizados pela administração.", "Confira desenho, material, operações, revisões e requisitos técnicos. Encaminhe eventuais dúvidas à administração antes de confirmar preço e prazo."],\n        resultado: "Você tem a documentação liberada para conferir o escopo do orçamento.",\n      },\n      {\n        id: "cotacao", categoria: "Oportunidades e propostas", titulo: "Envie sua cotação",\n        resumo: "Informe o valor total e os prazos para executar o serviço.",\n        onde: "Solicitações Disponíveis", caminho: "/fornecedor/solicitacoes",\n        passos: ["Abra a oportunidade e o formulário de cotação disponível para ela.", "Informe valor total do serviço, prazo em dias, validade e observações necessárias.", "Revise os dados, confira especialmente os zeros e as casas decimais do valor e confirme o envio."],\n        resultado: "Sua proposta fica registrada para análise da administração.",\n        dica: "O envio da cotação é uma proposta. Aguarde a contratação e a liberação da execução para iniciar o serviço.",\n      },\n      {\n        id: "minhas-cotacoes", categoria: "Oportunidades e propostas", titulo: "Acompanhe suas propostas",\n        resumo: "Consulte a situação e os detalhes das cotações enviadas.",\n        onde: "Minhas Cotações", caminho: "/fornecedor/cotacoes",\n        passos: ["Pesquise a cotação ou a solicitação desejada.", "Confira valor, prazo, validade e situação atual.", "Acompanhe as notificações e as orientações da administração sobre a continuidade do serviço."],\n        resultado: "Você identifica quais propostas estão em análise e quais deram origem a serviços contratados.",\n      },\n      {\n        id: "contratacao", categoria: "Produção e coleta", titulo: "Confira a contratação e a ordem",\n        resumo: "Revise o que foi contratado antes da execução.",\n        onde: "Contratações", caminho: "/fornecedor/contratacoes",\n        passos: ["Abra a contratação vinculada à sua proposta.", "Confira as condições e as instruções de execução liberadas para sua empresa.", "Consulte Ordens de Serviço e confirme a OS e as orientações da administração sobre material e início do trabalho."],\n        resultado: "Você conhece as condições do serviço e a OS que receberá as atualizações.",\n      },\n      {\n        id: "producao", categoria: "Produção e coleta", titulo: "Atualize o andamento da produção",\n        resumo: "Registre a etapa real de execução das peças.",\n        onde: "Produção", caminho: "/fornecedor/producao",\n        passos: ["Selecione a OS correta e abra seu histórico.", "Escolha a etapa disponível que representa o andamento real e informe observações úteis.", "Revise a atualização e confirme. Confira o novo registro no histórico."],\n        resultado: "A etapa da produção fica registrada e os perfis envolvidos podem acompanhar a atualização.",\n        dica: "Registre o que realmente aconteceu. Em caso de retrabalho, siga as orientações administrativas e atualize novamente a produção.",\n      },\n      {\n        id: "coleta", categoria: "Produção e coleta", titulo: "Informe quando estiver pronto para coleta",\n        resumo: "Avise que o lote está preparado para a movimentação.",\n        onde: "Produção", caminho: "/fornecedor/producao",\n        passos: ["Confira se o lote da OS está pronto conforme o serviço combinado.", "Na atualização da produção, selecione Pronto para coleta quando essa etapa estiver disponível e confirme.", "Acompanhe o agendamento e os registros da administração na tela Entregas."],\n        resultado: "A administração pode dar continuidade à coleta e à conferência das peças.",\n      },\n      {\n        id: "pagamentos", categoria: "Financeiro e qualidade", titulo: "Acompanhe os repasses do serviço",\n        resumo: "Confira os valores financeiros apresentados à sua empresa.",\n        onde: "Pagamentos", caminho: "/fornecedor/pagamentos",\n        passos: ["Localize a contratação correspondente à OS executada.", "Confira os repasses registrados e o saldo exibido para o serviço.", "Solicite à administração a conferência de qualquer diferença nos registros."],\n        resultado: "Você acompanha o controle dos valores a receber pelo serviço.",\n      },\n      {\n        id: "notas", categoria: "Financeiro e qualidade", titulo: "Consulte as notas dos seus serviços",\n        resumo: "Veja as notas individuais disponibilizadas para sua empresa.",\n        onde: "Avaliações", caminho: "/fornecedor/avaliacoes",\n        passos: ["Pesquise a contratação ou a OS concluída.", "Abra o serviço para consultar as notas disponibilizadas ao seu perfil.", "Use o retorno recebido para revisar a execução e alinhar melhorias com a administração."],\n        resultado: "Você consulta as notas dos seus próprios serviços.",\n      },\n      {\n        id: "conta", categoria: "Primeiros passos", titulo: "Acompanhe notificações e gerencie sua conta",\n        resumo: "Consulte os avisos e as opções do seu acesso.",\n        onde: "Minha conta, no topo do sistema", caminho: "/conta",\n        passos: ["Consulte o centro de notificações e abra os avisos dos serviços da sua empresa.", "Use Minha conta para consultar seu acesso e alterar sua senha.", "Retorne ao menu Ajuda e tutorial sempre que precisar rever uma orientação."],\n        resultado: "Você sabe acompanhar as novidades e gerenciar seu acesso ao portal.",\n      },\n    ],\n    duvidas: [\n      { pergunta: "Por que uma solicitação ainda não aparece para minha empresa?", resposta: "A administração precisa liberar a documentação técnica e o serviço deve atender às condições de disponibilidade do portal. Confira também se as operações e capacidades da sua empresa estão atualizadas com a administração." },\n      { pergunta: "Enviei o orçamento. Já posso começar a produção?", resposta: "Aguarde a confirmação da contratação, a abertura da OS e as orientações da administração sobre material e execução." },\n      { pergunta: "As peças estão prontas. Como aviso a administração?", resposta: "Selecione a OS em Produção, registre a etapa Pronto para coleta e confirme a atualização. Depois acompanhe a movimentação em Entregas." },\n    ],\n  },\n  admin: {\n    nome: "Administração",\n    introducao: "Aprenda a coordenar a documentação, os orçamentos, a execução, as entregas e o resultado dos serviços.",\n    etapas: [\n      {\n        id: "inicio", categoria: "Preparação", titulo: "Organize o trabalho pelo painel",\n        resumo: "Localize pendências e acompanhe as contratações.",\n        onde: "Dashboard", caminho: "/admin",\n        passos: ["Confira os indicadores do Dashboard e consulte os serviços em andamento.", "Pesquise pelo número da OS ou da contratação para conferir um serviço específico.", "Abra os atalhos de pendências e relatórios disponíveis no painel para organizar as próximas ações."],\n        resultado: "Você identifica os serviços e as etapas que precisam de intervenção administrativa.",\n      },\n      {\n        id: "empresas", categoria: "Preparação", titulo: "Cadastre empresas, operações e capacidades",\n        resumo: "Mantenha o cadastro técnico dos clientes e fornecedores.",\n        onde: "Empresas e operações", caminho: "/admin/empresas",\n        passos: ["Pesquise a empresa ou abra a opção para cadastrar uma nova.", "Informe os dados solicitados e o tipo de empresa. Para fornecedores, selecione as operações executadas.", "Confira capacidades, dimensões, tolerâncias e materiais aceitos conforme os campos disponíveis. Revise e salve o cadastro."],\n        resultado: "O cadastro representa as condições de atendimento da empresa.",\n        dica: "O cadastro da empresa e o acesso do usuário são registros diferentes. Confira também a conta que ficará vinculada a cada perfil.",\n      },\n      {\n        id: "solicitacoes", categoria: "Documentos e orçamento", titulo: "Analise a solicitação do cliente",\n        resumo: "Confira os requisitos antes de encaminhar o serviço para cotação.",\n        onde: "Solicitações", caminho: "/admin/solicitacoes",\n        passos: ["Pesquise a solicitação e clique em Abrir solicitação.", "Confira cliente, processo, material, quantidade, dimensões e observações.", "Confirme se a documentação enviada atende ao escopo e encaminhe a revisão em Arquivos Técnicos."],\n        resultado: "Você conhece o pedido e as informações necessárias para cotar o serviço.",\n      },\n      {\n        id: "documentos", categoria: "Documentos e orçamento", titulo: "Revise e libere os arquivos para cotação",\n        resumo: "Confira o documento que será disponibilizado ao fornecedor.",\n        onde: "Arquivos Técnicos", caminho: "/admin/arquivos-tecnicos",\n        passos: ["Pesquise a solicitação e use Baixar para revisar no documento correto.", "Quando necessário, abra Preparar PDF com nossa logo, configure as áreas e os dados técnicos e confira a prévia comparada ao original.", "Após a revisão, use Liberar para cotação, confira a identificação do cliente, descreva o registro interno e clique em Confirmar registro."],\n        resultado: "A documentação aprovada fica disponível segundo as regras de acesso da solicitação.",\n        dica: "Preserve cotas, escala, revisões e requisitos técnicos relevantes. A preparação do PDF exige conferência do resultado antes de sua publicação.",\n      },\n      {\n        id: "cotacoes", categoria: "Documentos e orçamento", titulo: "Compare as cotações dos fornecedores",\n        resumo: "Analise preço, prazo e condições das propostas recebidas.",\n        onde: "Cotações", caminho: "/admin/cotacoes",\n        passos: ["Pesquise a solicitação ou a cotação e abra Analisar cotação.", "Confira preço do fornecedor, prazo de execução, validade e observações.", "Consulte o histórico e as avaliações administrativas disponíveis para apoiar a escolha do fornecedor."],\n        resultado: "Você reúne os dados para escolher a proposta e preparar o preço ao cliente.",\n      },\n      {\n        id: "preco", categoria: "Documentos e orçamento", titulo: "Prepare e publique o preço para o cliente",\n        resumo: "Defina o acréscimo em percentual ou em reais.",\n        onde: "Cotações > Analisar cotação", caminho: "/admin/cotacoes",\n        passos: ["Abra a cotação e clique em Preparar preço para o cliente.", "Escolha a modalidade de acréscimo, informe o percentual sobre o custo ou o valor fixo e confira o preço final calculado.", "Revise os dados e publique o orçamento para análise do cliente. Acompanhe a aprovação, a solicitação de revisão ou a recusa."],\n        resultado: "O cliente pode analisar o preço final publicado para o serviço.",\n        dica: "O percentual é um acréscimo sobre o custo do fornecedor. Despesas do serviço são acompanhadas separadamente no resultado da administração.",\n      },\n      {\n        id: "contratacao", categoria: "Contratação e execução", titulo: "Formalize a contratação e abra a OS",\n        resumo: "Dê continuidade ao orçamento aprovado pelo cliente.",\n        onde: "Contratações", caminho: "/admin/contratacoes",\n        passos: ["Confira a aprovação do orçamento pelo cliente e registre a decisão administrativa da cotação quando habilitada.", "Abra a solicitação em Contratações e confira fornecedor, valores, prazo e documentação.", "Informe as instruções de execução e o registro interno. Revise contratação e OS e confirme a operação."],\n        resultado: "O serviço fica formalizado e a OS passa a identificar a execução.",\n      },\n      {\n        id: "material", categoria: "Contratação e execução", titulo: "Inicie o ciclo e encaminhe o material",\n        resumo: "Registre as movimentações administrativas do serviço.",\n        onde: "Entregas e Aceite", caminho: "/admin/entregas",\n        passos: ["Localize a OS, abra Ver ciclo e inicie o ciclo administrativo quando disponível.", "Selecione a ação permitida de encaminhamento do material na situação atual.", "Informe registro interno e comprovante quando solicitado, revise os dados e confirme o registro."],\n        resultado: "O histórico do ciclo passa a acompanhar o encaminhamento do serviço.",\n      },\n      {\n        id: "producao", categoria: "Contratação e execução", titulo: "Acompanhe a produção informada",\n        resumo: "Consulte o avanço dos serviços nas empresas fornecedoras.",\n        onde: "Acompanhamento de Produção", caminho: "/admin/producao",\n        passos: ["Localize a OS pelo filtro ou pela lista de serviços.", "Confira a etapa atual, as datas e o histórico informado pelo fornecedor.", "Quando houver atraso ou divergência, alinhe o encaminhamento com os envolvidos e acompanhe as notificações."],\n        resultado: "Você acompanha a execução para coordenar os próximos movimentos.",\n      },\n      {\n        id: "coleta", categoria: "Conferência e entrega", titulo: "Registre a coleta e confira o lote",\n        resumo: "Acompanhe as peças prontas até a avaliação administrativa.",\n        onde: "Entregas e Aceite", caminho: "/admin/entregas",\n        passos: ["Confira se o fornecedor informou Pronto para coleta em Produção.", "No ciclo da OS, registre a solicitação de coleta e o recebimento das peças conforme as ações disponíveis.", "Confira a quantidade do lote e registre o parecer técnico ao aprovar as peças ou solicitar retrabalho."],\n        resultado: "A coleta e a conferência ficam registradas no histórico administrativo.",\n        dica: "O ciclo controla o lote completo da OS. Confira a quantidade pedida no formulário de cada movimentação.",\n      },\n      {\n        id: "entrega", categoria: "Conferência e entrega", titulo: "Conclua a entrega ao cliente",\n        resumo: "Registre a entrega física do lote aprovado.",\n        onde: "Entregas e Aceite", caminho: "/admin/entregas",\n        passos: ["Confira se as peças foram aprovadas e se a ação de entrega está disponível.", "Registre a entrega ao cliente, a quantidade conferida, o comprovante e as informações solicitadas.", "Revise e confirme. Confira a conclusão da OS e o histórico do ciclo."],\n        resultado: "A entrega e a conclusão da ordem ficam registradas para acompanhamento.",\n      },\n      {\n        id: "financeiro", categoria: "Financeiro e resultado", titulo: "Registre recebimentos e repasses",\n        resumo: "Controle os movimentos financeiros efetivamente realizados.",\n        onde: "Pagamentos", caminho: "/admin/pagamentos",\n        passos: ["Abra a contratação correta e confira os valores previstos para cliente e fornecedor.", "Registre o recebimento do cliente ou o repasse ao fornecedor com os dados e comprovantes solicitados.", "Confira saldos e histórico. Se precisar corrigir um registro, use o estorno disponível e descreva o motivo antes de lançar o movimento correto."],\n        resultado: "O controle financeiro reflete os movimentos registrados para o serviço.",\n        dica: "O sistema registra recebimentos e repasses. A transferência bancária deve ser realizada pelo meio combinado fora desse registro.",\n      },\n      {\n        id: "resultado", categoria: "Financeiro e resultado", titulo: "Registre despesas e acompanhe o resultado",\n        resumo: "Veja o efeito dos gastos no resultado da administração.",\n        onde: "Pagamentos > Resultado da administração", caminho: "/admin/resultado-administracao",\n        passos: ["Consulte o período desejado e localize a contratação para conferir suas despesas.", "Registre os gastos reais e sua situação conforme os campos disponíveis. Confira os registros e os estornos existentes.", "Compare resultado previsto, resultado após despesas pagas e resultado dos serviços liquidados; use os relatórios e as análises disponíveis para detalhar os valores."],\n        resultado: "Você acompanha o resultado dos serviços com os custos e as despesas registrados.",\n        dica: "Os indicadores usam critérios próprios. Confira a situação dos pagamentos e a explicação de cada valor antes de compará-los.",\n      },\n      {\n        id: "metas", categoria: "Financeiro e resultado", titulo: "Defina metas e consulte os relatórios",\n        resumo: "Compare o resultado liquidado com a meta de cada mês.",\n        onde: "Resultado da administração > Abrir metas mensais", caminho: "/admin/resultado-administracao",\n        passos: ["Abra metas mensais e selecione o ano da consulta.", "No seletor Mês para definir ou editar a meta, escolha o mês e abra a edição. Informe o valor e o motivo quando quiser registrar uma alteração.", "Confira tabela, gráfico, histórico e atingimento. Use Baixar CSV das metas ou Baixar PDF das metas para exportar a consulta."],\n        resultado: "Você acompanha as metas mensais e os resultados calculados na consulta.",\n        dica: "As metas são comparadas ao resultado dos serviços liquidados, agrupado pelo mês de criação da contratação. Mês sem meta e meta igual a zero têm tratamentos próprios no percentual.",\n      },\n      {\n        id: "avaliacoes", categoria: "Qualidade", titulo: "Avalie os serviços e consulte o ranking",\n        resumo: "Acompanhe a qualidade e o histórico de cada fornecedor.",\n        onde: "Ranking de Fornecedores", caminho: "/admin/ranking",\n        passos: ["Em Avaliações, localize o serviço apto e registre a nota administrativa após a revisão.", "Abra Ranking de Fornecedores e consulte gráfico, notas e histórico da empresa.", "Use a comparação como apoio à análise das próximas propostas, considerando também capacidade, preço e prazo."],\n        resultado: "Você reúne as informações de qualidade para apoiar decisões administrativas.",\n        dica: "O ranking é exclusivo da administração. O fornecedor consulta apenas as notas individuais disponibilizadas dos seus serviços.",\n      },\n      {\n        id: "conta", categoria: "Preparação", titulo: "Consulte avisos e gerencie seu acesso",\n        resumo: "Acompanhe as notificações relevantes para a administração.",\n        onde: "Minha conta, no topo do sistema", caminho: "/conta",\n        passos: ["Abra o centro de notificações para consultar alterações nos serviços.", "Use Minha conta para consultar seu acesso e alterar sua senha.", "Retorne ao menu Ajuda e tutorial para revisar o procedimento de cada etapa."],\n        resultado: "Você sabe onde consultar avisos e administrar seu próprio acesso.",\n      },\n    ],\n    duvidas: [\n      { pergunta: "Por que o fornecedor ainda não vê uma solicitação?", resposta: "Confira os arquivos ativos e íntegros, o registro de liberação para cotação, a situação da solicitação e a compatibilidade com o cadastro do fornecedor. Depois atualize a consulta no portal correspondente." },\n      { pergunta: "Onde preparo o valor que será apresentado ao cliente?", resposta: "Em Cotações, abra Analisar cotação e depois Preparar preço para o cliente. O acréscimo pode ser percentual sobre o custo ou um valor fixo em reais. Revise o preço final antes da publicação." },\n      { pergunta: "Por que a ação de coleta ainda não está disponível?", resposta: "Confira o ciclo administrativo e peça ao fornecedor que registre Pronto para coleta em Produção. Depois de retrabalho é necessário um novo registro dessa etapa." },\n      { pergunta: "Onde consulto o resultado e as metas da administração?", resposta: "Abra Pagamentos e Resultado da administração. Nessa área ficam despesas, análises e relatórios; use Abrir metas mensais para consultar as metas, o gráfico e as exportações." },\n    ],\n  },\n};\n\nexport function normalizarBusca(valor: string): string {\n  return valor.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLocaleLowerCase("pt-BR").trim();\n}\n\nexport function filtrarEtapas(guia: GuiaTutorial, busca: string): EtapaTutorial[] {\n  const termos = normalizarBusca(busca).split(/\\s+/).filter(Boolean);\n  return guia.etapas.filter(etapa => {\n    const texto = normalizarBusca([etapa.categoria, etapa.titulo, etapa.resumo, etapa.onde,\n      ...etapa.passos, etapa.resultado, etapa.dica ?? ""].join(" "));\n    return termos.every(termo => texto.includes(termo));\n  });\n}\n', 'frontend/src/pages/tutorial/progressoTutorial.ts': 'import type { PerfilTutorial } from "./dadosTutorial";\n\nexport type ProgressoTutorial = { versao: 1; lidas: string[]; ultima: string };\ntype Armazenamento = Pick<Storage, "getItem" | "setItem">;\n\nexport function chaveTutorial(usuario: number, perfil: PerfilTutorial, empresa: number | null): string {\n  return `mec-tutorial-d66:v1:${usuario}:${perfil}:${empresa ?? "administracao"}`;\n}\n\nexport function lerProgresso(armazenamento: Armazenamento | undefined, chave: string, permitidas: string[]): ProgressoTutorial {\n  const inicial: ProgressoTutorial = { versao: 1, lidas: [], ultima: permitidas[0] ?? "" };\n  try {\n    const salvo: unknown = JSON.parse(armazenamento?.getItem(chave) ?? "null");\n    if (!salvo || typeof salvo !== "object" || !("versao" in salvo) || salvo.versao !== 1) return inicial;\n    const valor = salvo as Partial<ProgressoTutorial>;\n    return {\n      versao: 1,\n      lidas: Array.isArray(valor.lidas) ? [...new Set(valor.lidas.filter(id => typeof id === "string" && permitidas.includes(id)))] : [],\n      ultima: typeof valor.ultima === "string" && permitidas.includes(valor.ultima) ? valor.ultima : inicial.ultima,\n    };\n  } catch { return inicial; }\n}\n\nexport function salvarProgresso(armazenamento: Armazenamento | undefined, chave: string, valor: ProgressoTutorial): boolean {\n  if (!armazenamento) return false;\n  try { armazenamento.setItem(chave, JSON.stringify(valor)); return true; }\n  catch { return false; }\n}\n', 'D66_CONTRATO_TUTORIAL_POR_PERFIL.txt': 'MEC-Serviços D66 — Tutorial por perfil\nREVISION=MEC-SERVICOS-V0.1-D66-TUTORIAL-POR-PERFIL-2026-10-14\n\nO QUE ESTA ETAPA ENTREGA\nMenu Ajuda e tutorial logo abaixo do Dashboard de Cliente, Fornecedor e Administração.\nCada perfil abre seu próprio guia com etapas, passos, resultado esperado, dicas,\nbusca, dúvidas frequentes e links para as telas reais do sistema.\nO cliente tem 10 etapas, o fornecedor 11 e a administração 16.\nO progresso representa leitura do tutorial. Para executar um procedimento,\nabra a tela, confira o serviço e registre a operação no formulário correspondente.\nAs marcações de leitura ficam no navegador, separadas por usuário, perfil e empresa.\nUsar outro computador ou limpar os dados do navegador pode remover as marcações.\nO tutorial continua utilizável se o navegador impedir o salvamento da leitura.\nO guia usa a sessão existente e não permite escolher outro perfil na própria ajuda.\n\nINSTALAÇÃO\nRequisito: D65 concluída com RESULTADO=OK.\n1. Pare o frontend com Ctrl+C no terminal em que npm run dev está rodando.\n2. Salve MEC_SERVICOS_V0_1_D66_TUTORIAL_POR_PERFIL.py na pasta MEC-Servicos.\n3. Execute, uma linha de cada vez:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_V0_1_D66_TUTORIAL_POR_PERFIL.py\n\nAguarde RESULTADO=OK. A compilação do frontend aparece ao vivo no terminal.\nO instalador faz backup das fontes alteradas e do build anterior.\nEm falha de compilação, restaura os arquivos que ele aplicou e o build anterior.\nAlterações posteriores de outra origem são preservadas e informadas no relatório.\nEsta etapa não instala bibliotecas, não executa operações de negócio e não acessa\nos bancos. Backend, contas, pagamentos, históricos e permissões permanecem com\nseus mecanismos atuais. A validação desta atualização é a integração e o build\ndo frontend; a suíte de negócio não precisa ser reexecutada para esta etapa.\n\nATIVAÇÃO\nO backend pode permanecer rodando. Se precisar iniciá-lo, use outra janela:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_INICIAR_TESTE_LOCAL.py\n\nNa janela do frontend:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\\frontend\nnpm.cmd run dev -- --host localhost --port 5173 --strictPort\n\nAbra http://localhost:5173 e atualize com Ctrl+F5.\n\nONDE ENCONTRAR\nLogo abaixo do Dashboard no menu lateral: Ajuda e tutorial.\nAdministração: http://localhost:5173/admin/ajuda\nCliente: http://localhost:5173/cliente/ajuda\nFornecedor: http://localhost:5173/fornecedor/ajuda\nO acesso depende da sessão do respectivo perfil.\n\nTESTE RÁPIDO\n1. Entre como ADM e abra Ajuda e tutorial logo abaixo do Dashboard no menu.\n2. Confira Guia do perfil · Administração e a sequência de 16 etapas.\n3. Busque preço e abra Prepare e publique o preço para o cliente.\n4. Leia as instruções e clique Abrir esta tela: deve abrir Cotações.\n5. Retorne a Ajuda e tutorial. A etapa selecionada deve continuar disponível.\n6. Clique Concluir leitura desta etapa. O contador deve aumentar uma unidade.\n7. Atualize a página: a leitura deve continuar marcada neste navegador.\n8. Use Etapa anterior e Próxima etapa e confira a mudança do passo a passo.\n9. Busque um texto inexistente e use Limpar busca para rever o índice.\n10. Abra Reiniciar leitura. Confira a pergunta e escolha Continuar como está.\n    As marcações devem continuar. Se confirmar o reinício, zera só a leitura.\n11. Entre como Cliente e abra sua ajuda: devem aparecer 10 etapas do cliente.\n    As marcações do ADM não devem aparecer nesta conta.\n12. Entre como Fornecedor e confira suas 11 etapas, com produção, coleta e notas.\n    As marcações das outras contas não devem aparecer neste perfil.\n13. Abra uma dúvida frequente de cada perfil para conferir a explicação.\n\nINFORMAÇÕES DO GUIA\nFornecedor envia cotação à administração. ADM prepara o preço e publica para\no cliente analisar. A contratação e a OS são formalizadas pela administração.\nOs documentos precisam passar pela revisão e liberação administrativa.\nFornecedor atualiza produção; ADM controla material, coleta, conferência e entrega.\nO controle financeiro registra os movimentos; não realiza transferência bancária.\nRanking, comparação, custos reservados e resultado administrativo continuam\nrestritos à administração pelos mecanismos existentes.\n', 'D66_FIX1_CONTRATO_CAMINHOS_WINDOWS.txt': 'MEC-Serviços D66 FIX1 — Caminhos do instalador no Windows\nREVISION=MEC-SERVICOS-V0.1-D66-FIX1-CAMINHOS-WINDOWS-2026-10-15\n\nMOTIVO DA CORREÇÃO\nA compilação da D66 terminou corretamente, mas a conferência de preservação\ncomparava nomes de arquivos do Windows com barras invertidas aos caminhos\ndo pacote com barras normais. Assim, identificava frontend/src/App.tsx como\numa alteração externa e restaurava a instalação.\nA FIX1 normaliza os caminhos para a comparação. A verificação de alterações\nexternas reais continua ativa. Os cinco arquivos do tutorial têm o mesmo\nconteúdo da D66 original, cuja compilação já foi conferida.\n\nBASE E INSTALAÇÃO\nRequer D65 concluída. Pode ser executada após a D66 ter sido restaurada.\nA FIX1 contém os arquivos necessários para instalar o tutorial completo.\nPare o frontend com Ctrl+C e execute na pasta MEC-Servicos:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_V0_1_D66_FIX1_CAMINHOS_WINDOWS.py\n\nAguarde CONFERENCIA_CAMINHOS_WINDOWS=True e RESULTADO=OK.\nO instalador faz backup antes da aplicação e compila o frontend.\nBackend, bancos e registros de negócio não são alterados.\n\nATIVAÇÃO DO FRONTEND\nCom o backend funcionando, execute na janela do frontend:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\\frontend\nnpm.cmd run dev -- --host localhost --port 5173 --strictPort\n\nSe precisar iniciar o backend, use outra janela PowerShell:\n\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_INICIAR_TESTE_LOCAL.py\n\nTESTE\n1. Abra http://localhost:5173 e atualize com Ctrl+F5.\n2. Entre como ADM e abra Ajuda e tutorial, logo abaixo de Dashboard.\n3. Busque preço e abra Prepare e publique o preço para o cliente.\n4. Clique Abrir esta tela: deve abrir Cotações.\n5. Retorne ao tutorial, conclua a leitura da etapa e atualize a página.\n   A marcação deve continuar salva para essa conta neste navegador.\n6. Confira o guia de Cliente e o de Fornecedor. Cada um abre o conteúdo\n   e o progresso de leitura próprios do perfil e da conta.\n\nO roteiro completo das funções do tutorial permanece em\nD66_CONTRATO_TUTORIAL_POR_PERFIL.txt.\n'}
PERFIS = {"admin": "Admin", "cliente": "Client", "fornecedor": "Supplier"}
LIMITE_BUILD = 600


def sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def caminho_seguro(raiz: Path, relativo: str) -> Path:
    parte = Path(relativo)
    if parte.is_absolute() or ".." in parte.parts:
        raise RuntimeError("Destino fora do projeto: " + relativo)
    alvo = raiz / parte
    for componente in [alvo, *alvo.parents]:
        if componente == raiz:
            break
        if componente.is_symlink() or getattr(componente, "is_junction", lambda: False)():
            raise RuntimeError("Destino simbólico preservado: " + relativo)
    if not alvo.resolve().is_relative_to(raiz.resolve()):
        raise RuntimeError("Destino fora do projeto: " + relativo)
    return alvo


def localizar_raiz() -> Path:
    for raiz in dict.fromkeys([Path.cwd().resolve(), Path(__file__).resolve().parent]):
        if (raiz / "frontend/package.json").is_file() and (raiz / "backend/app/principal.py").is_file():
            return raiz
    raise RuntimeError("Salve e execute este arquivo na pasta C:\\Users\\Omega\\Desktop\\MEC-Servicos.")


def conferir_origem(raiz: Path) -> None:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git não encontrado para conferir o projeto MEC-Servicos.")
    resultado = subprocess.run([git, "remote", "get-url", "--all", "origin"], cwd=raiz,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    urls = resultado.stdout.strip().splitlines()
    def permitida(url: str) -> bool:
        if url.startswith("git@github.com:"):
            caminho = url.split(":", 1)[1]
        else:
            valor = urlsplit(url)
            if valor.hostname != "github.com" or valor.scheme not in {"https", "ssh"}:
                return False
            if valor.scheme == "https" and (valor.username or valor.password):
                return False
            caminho = valor.path.lstrip("/")
        return caminho.lower().rstrip("/").removesuffix(".git") == "projetoxcadcam-byte/mec-servicos"
    if resultado.returncode or not urls or not all(permitida(url) for url in urls):
        raise RuntimeError("Origin não corresponde ao projeto MEC-Servicos.")


def conferir_base(raiz: Path) -> None:
    anterior = caminho_seguro(raiz, "MEC_SERVICOS_V0_1_D65_PDF_METAS_RELATORIO.json")
    try:
        registro = json.loads(anterior.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise RuntimeError("Conclua a D65 com RESULTADO=OK antes de aplicar a D66.") from None
    if registro.get("resultado") != "OK" or registro.get("revision") != REVISION_D65:
        raise RuntimeError("Conclua a D65 com RESULTADO=OK antes de aplicar a D66.")
    for nome in ["backend/app/services/pdf_metas_resultado.py", "frontend/src/pages/formacao-preco/MetasResultado.tsx",
                 "frontend/src/auth/ProtectedRoute.tsx", "frontend/src/auth/AuthContext.tsx"]:
        if not caminho_seguro(raiz, nome).is_file():
            raise RuntimeError("Arquivo da base D65 não encontrado; projeto preservado: " + nome)
    pacote = json.loads(caminho_seguro(raiz, "frontend/package.json").read_text(encoding="utf-8-sig"))
    if not pacote.get("scripts", {}).get("build"):
        raise RuntimeError("Comando build não encontrado no frontend.")


def texto_original(alvo: Path) -> tuple[bytes, str]:
    dados = alvo.read_bytes()
    try:
        return dados, dados.decode("utf-8-sig").replace("\r\n", "\n")
    except UnicodeError:
        raise RuntimeError("Arquivo fora do padrão UTF-8; preservado: " + alvo.name) from None


def mesmos_finais(conteudo: str, original: bytes) -> bytes:
    if b"\r\n" in original:
        conteudo = conteudo.replace("\n", "\r\n")
    return (b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b"") + conteudo.encode("utf-8")


def atualizar_app(conteudo: str) -> str:
    importar = 'import TutorialPage from "./pages/tutorial/TutorialEntrada";'
    if importar not in conteudo:
        if re.search(r"\bTutorialPage\b", conteudo):
            raise RuntimeError("Já existe outra implementação TutorialPage; App.tsx preservado.")
        conteudo = importar + "\n" + conteudo
    for perfil, componente in [("admin", "PainelAdministrativoPage"), ("cliente", "PainelPortalPage"), ("fornecedor", "PainelPortalPage")]:
        rota = f'<Route path="ajuda" element={{<TutorialPage perfil="{perfil}" />}} />'
        if rota in conteudo:
            if conteudo.count(rota) != 1:
                raise RuntimeError("Rota de ajuda duplicada; App.tsx preservado.")
            continue
        marcador = ('<Route index element={<PainelAdministrativoPage />} />' if perfil == "admin"
                    else f'<Route index element={{<PainelPortalPage perfil="{perfil}" />}} />')
        if conteudo.count(marcador) != 1:
            raise RuntimeError("Navegação do perfil diferente da base recebida; App.tsx preservado: " + perfil)
        conteudo = conteudo.replace(marcador, marcador + "\n          " + rota, 1)
    if conteudo.count('path="ajuda"') != 3:
        raise RuntimeError("Há outra rota de ajuda no aplicativo; App.tsx preservado.")
    return conteudo


def atualizar_menu(conteudo: str, perfil: str) -> str:
    item = f'  {{ label: "Ajuda e tutorial", path: "/{perfil}/ajuda", icon: FileText }},'
    marcador = re.compile(r"(const\s+menu\s*:\s*MenuItem\[\]\s*=\s*\[)(.*?)(\n\];)", re.S)
    encontrados = list(marcador.finditer(conteudo))
    if len(encontrados) != 1:
        raise RuntimeError("Menu diferente da base recebida; preservado: " + perfil)
    menu = encontrados[0]
    if item in menu.group(2):
        if menu.group(2).count(item) != 1:
            raise RuntimeError("Ajuda duplicada no menu; preservado: " + perfil)
        return conteudo
    if "/ajuda" in menu.group(2) or "Ajuda e tutorial" in menu.group(2):
        raise RuntimeError("Já existe outra ajuda neste menu; preservado: " + perfil)
    if not re.search(r"\bFileText\b", conteudo[:menu.start()]):
        raise RuntimeError("Ícone de documento não encontrado no menu; preservado: " + perfil)
    # Mantém o Dashboard como primeiro item e conserva o comportamento de retorno
    # dos layouts existentes. A ajuda fica logo abaixo, visível em menus extensos.
    dashboards = list(re.finditer(r'(?m)^[ \t]*\{[^\n]*\bpath:\s*"/' + re.escape(perfil) + r'"[^\n]*\},[ \t]*$', menu.group(2)))
    if len(dashboards) != 1:
        raise RuntimeError("Dashboard do menu diferente da base recebida; preservado: " + perfil)
    inicio = menu.start(2) + dashboards[0].end()
    return conteudo[:inicio] + "\n" + item + conteudo[inicio:]


def planejar(raiz: Path) -> dict[str, bytes]:
    plano = {}
    for nome, texto in FONTES.items():
        alvo = caminho_seguro(raiz, nome)
        novo = texto.encode("utf-8")
        if alvo.exists() and alvo.read_bytes() != novo:
            raise RuntimeError("Arquivo novo já existe com outro conteúdo; preservado: " + nome)
        if not alvo.exists():
            plano[nome] = novo
    nomes = {"frontend/src/App.tsx": atualizar_app}
    for perfil, layout in PERFIS.items():
        nomes[f"frontend/src/layouts/{layout}Layout.tsx"] = lambda valor, p=perfil: atualizar_menu(valor, p)
    for nome, alterar in nomes.items():
        alvo = caminho_seguro(raiz, nome)
        original, texto = texto_original(alvo)
        novo = mesmos_finais(alterar(texto), original)
        if original != novo:
            plano[nome] = novo
    return plano


def gravar_atomico(alvo: Path, dados: bytes) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=alvo.parent, delete=False, prefix="mec_d66_") as arquivo:
        arquivo.write(dados)
        temporario = Path(arquivo.name)
    try:
        os.replace(temporario, alvo)
    finally:
        temporario.unlink(missing_ok=True)


def nome_portavel(nome: str | Path) -> str:
    return str(nome).replace("\\", "/")


def snapshot(raiz: Path, pasta: str) -> dict[str, str]:
    inicio = caminho_seguro(raiz, pasta)
    return {nome_portavel(arquivo.relative_to(raiz)): sha(arquivo.read_bytes()) for arquivo in inicio.rglob("*")
            if arquivo.is_file() and "__pycache__" not in arquivo.parts and not arquivo.is_symlink()}


def conferir_preservacao_fontes(antes: dict[str, str], depois: dict[str, str], plano: dict[str, bytes]) -> None:
    permitidas = {nome_portavel(nome) for nome in plano}
    posteriores = {nome_portavel(nome): valor for nome, valor in depois.items()}
    for nome, valor in antes.items():
        chave = nome_portavel(nome)
        if chave not in permitidas and posteriores.get(chave) != valor:
            raise RuntimeError("Uma fonte externa à atualização mudou; preservada: " + nome)


def parar_processo(processo: subprocess.Popen) -> None:
    if processo.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(processo.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    else:
        try:
            os.killpg(processo.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        processo.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            processo.kill()
        else:
            try:
                os.killpg(processo.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        processo.wait(timeout=10)


def compilar(raiz: Path, npm: str, relatorio: dict) -> None:
    print("Executando npm_build... (saída ao vivo)", flush=True)
    fila = queue.Queue()
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "CI": "1"}
    opcoes = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    log = caminho_seguro(raiz, STEM + "_npm_build.log")
    processo = subprocess.Popen([npm, "run", "build"], cwd=raiz / "frontend", env=ambiente,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, **opcoes)
    def recolher():
        try:
            for linha in processo.stdout:
                fila.put(linha)
        finally:
            fila.put(None)
    leitor = threading.Thread(target=recolher, daemon=True)
    leitor.start()
    inicio = ultimo_aviso = time.monotonic()
    terminou = False
    try:
        with log.open("w", encoding="utf-8") as arquivo:
            while not terminou or processo.poll() is None:
                agora = time.monotonic()
                if agora - inicio > LIMITE_BUILD:
                    raise RuntimeError("A compilação ultrapassou dez minutos. Confira o log local.")
                try:
                    linha = fila.get(timeout=1)
                    if linha is None:
                        terminou = True
                    else:
                        print(linha, end="", flush=True)
                        arquivo.write(linha)
                        arquivo.flush()
                        ultimo_aviso = agora
                except queue.Empty:
                    if agora - ultimo_aviso >= 20:
                        print(f"[npm_build] Em execução há {int(agora-inicio)} segundos.", flush=True)
                        ultimo_aviso = agora
        codigo = processo.wait()
        relatorio["npm_build"] = {"return_code": codigo, "duracao_segundos": round(time.monotonic() - inicio, 2), "log": str(log)}
        print("NPM_BUILD_RETURN_CODE=" + str(codigo), flush=True)
        if codigo:
            raise RuntimeError("A compilação do frontend falhou. Confira o log local.")
    finally:
        parar_processo(processo)
        leitor.join(timeout=2)
        if processo.stdout:
            processo.stdout.close()


def salvar_relatorio(raiz: Path, relatorio: dict) -> None:
    dados = (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for extensao in ["json", "txt"]:
        alvo = caminho_seguro(raiz, STEM + "." + extensao)
        gravar_atomico(alvo, dados)
        print(extensao.upper() + "=" + str(alvo), flush=True)


def conferir_frontend_parado() -> None:
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, 5173), timeout=.35):
                pass
        except OSError:
            continue
        raise RuntimeError("Pare o frontend na porta 5173 com Ctrl+C no terminal dele e execute novamente a D66.")


def main() -> int:
    print("MEC-Serviços D66 FIX1 — Caminhos do instalador no Windows", flush=True)
    print("REVISION=" + REVISION, flush=True)
    raiz = None
    originais: dict[str, bytes | None] = {}
    aplicados: dict[str, bytes] = {}
    backup = None
    build_iniciado = False
    dist_existia = False
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapa": "inicio", "restaurado": False,
                 "atualizacao_apenas_frontend": True, "tabelas_criadas": 0, "operacoes_negocio_executadas": False}
    try:
        if sys.version_info < (3, 11):
            raise RuntimeError("Execute com o Python 3.11 ou mais recente da .venv do MEC-Serviços.")
        raiz = localizar_raiz()
        print("ROOT=" + str(raiz), flush=True)
        conferir_origem(raiz)
        print("ORIGIN_MEC_CONFIRMADO=True", flush=True)
        conferir_frontend_parado()
        relatorio["etapa"] = "conferir_base"
        conferir_base(raiz)
        print("BASE_D65_CONFIRMADA=True", flush=True)
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise RuntimeError("npm não encontrado. Use o mesmo ambiente que compilou a D65.")
        plano = planejar(raiz)
        backend_antes = snapshot(raiz, "backend/app")
        fontes_antes = snapshot(raiz, "frontend/src")
        dist = caminho_seguro(raiz, "frontend/dist")
        relatorio["etapa"] = "backup"
        backup = caminho_seguro(raiz, "_mec_backups/D66_FIX1_CAMINHOS_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        backup.mkdir(parents=True, exist_ok=False)
        relatorio["backup"] = str(backup)
        print("BACKUP_DIR=" + str(backup), flush=True)
        dist_existia = dist.exists()
        if dist_existia:
            shutil.copytree(dist, backup / "frontend_dist")
        for nome in plano:
            alvo = caminho_seguro(raiz, nome)
            originais[nome] = alvo.read_bytes() if alvo.exists() else None
            if originais[nome] is not None:
                copia = backup / "originais" / nome
                copia.parent.mkdir(parents=True, exist_ok=True)
                copia.write_bytes(originais[nome])
        (backup / "MANIFESTO.json").write_text(json.dumps({nome: None if dados is None else sha(dados) for nome, dados in originais.items()}, indent=2) + "\n", encoding="utf-8")
        relatorio["etapa"] = "aplicar_frontend"
        for nome, dados in plano.items():
            alvo = caminho_seguro(raiz, nome)
            if (alvo.read_bytes() if alvo.exists() else None) != originais[nome]:
                raise RuntimeError("Arquivo mudou durante a preparação; alteração externa preservada: " + nome)
            gravar_atomico(alvo, dados)
            aplicados[nome] = dados
        print("ARQUIVOS_D66_FIX1_APLICADOS=" + str(len(aplicados)), flush=True)
        relatorio["etapa"] = "npm_build"
        build_iniciado = True
        compilar(raiz, npm, relatorio)
        relatorio["etapa"] = "conferir_integracao"
        if planejar(raiz):
            raise RuntimeError("A integração do tutorial divergiu após a compilação.")
        if snapshot(raiz, "backend/app") != backend_antes:
            raise RuntimeError("Fontes do backend mudaram durante a execução. Alterações externas preservadas.")
        fontes_depois = snapshot(raiz, "frontend/src")
        conferir_preservacao_fontes(fontes_antes, fontes_depois, plano)
        relatorio.update(resultado="OK", etapa="concluido", arquivos_alterados=list(aplicados),
            tutorial_cliente=True, tutorial_fornecedor=True, tutorial_administracao=True,
            menu_ajuda_nos_tres_perfis=True, busca_no_tutorial=True, progresso_leitura_por_conta_e_perfil=True,
            backend_preservado=True, novas_dependencias_instaladas=False, compilacao_frontend=True,
            caminhos_portaveis_windows=True)
        print("CONFERENCIA_CAMINHOS_WINDOWS=True", flush=True)
        print("TUTORIAL_POR_PERFIL_DISPONIVEL=True", flush=True)
        print("AJUDA_NOS_TRES_MENUS=True", flush=True)
        print("PROGRESSO_LEITURA_SEPARADO_POR_CONTA=True", flush=True)
        print("BACKEND_PRESERVADO=True", flush=True)
        print("TABELAS_D66_CRIADAS=0", flush=True)
        salvar_relatorio(raiz, relatorio)
        print("RESULTADO=OK", flush=True)
        print("Inicie o frontend, atualize com Ctrl+F5 e abra Ajuda e tutorial no menu do seu perfil.", flush=True)
        print("Roteiro local: D66_FIX1_CONTRATO_CAMINHOS_WINDOWS.txt", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ETAPA=" + relatorio["etapa"], flush=True)
        print("ERRO=" + relatorio["erro"], flush=True)
        falhas = []
        if raiz and aplicados:
            for nome, instalado in reversed(list(aplicados.items())):
                alvo = raiz / nome
                try:
                    if not alvo.exists() or alvo.read_bytes() != instalado:
                        falhas.append("Alteração posterior preservada: " + nome)
                        continue
                    if originais[nome] is None:
                        alvo.unlink()
                    else:
                        gravar_atomico(alvo, originais[nome])
                except OSError as falha:
                    falhas.append(str(falha))
        if raiz and build_iniciado and backup:
            try:
                dist = caminho_seguro(raiz, "frontend/dist")
                if dist.exists():
                    shutil.rmtree(dist)
                if dist_existia:
                    shutil.copytree(backup / "frontend_dist", dist)
            except OSError as falha:
                falhas.append(str(falha))
        relatorio["restaurado"] = bool(aplicados) and not falhas
        if falhas:
            relatorio["falhas_restauracao"] = falhas
        if aplicados:
            print("RESTAURADO=" + str(relatorio["restaurado"]), flush=True)
        if raiz:
            try:
                salvar_relatorio(raiz, relatorio)
            except OSError:
                print("RELATORIO_NAO_GRAVADO=True; preserve a saída do terminal.", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
