"""MEC-Serviços D38 FIX1 — Botão Ver mês visível.
Execute na raiz do MEC com o backend parado e a instalação D38 concluída.
Corrige dois fontes do frontend; preserva dados, contas e modo local.
Valida a base, faz backup e executa somente o build do frontend.
"""

from __future__ import annotations

import ast

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

REVISION = 'MEC-SERVICOS-V0.1-D38-FIX1-VER-MES-VISIVEL-2026-10-06'

D38_REVISION = 'MEC-SERVICOS-V0.1-D38-RESUMO-GERENCIAL-MENSAL-2026-10-06'

STEM = 'MEC_SERVICOS_V0_1_D38_FIX1_VER_MES_VISIVEL_RELATORIO'

FONTES = {'D38_FIX1_VER_MES_VISIVEL.txt': 'MEC-Serviços D38 FIX1 — Botão Ver mês visível\n\nBASE: D38 concluído. Pare o backend e execute o instalador na raiz do MEC.\nCorrige a posição de Ver mês e Pendências do mês na tabela dos 12 meses.\nAs ações ficam na primeira coluna, junto ao nome do mês. Essa coluna permanece\nvisível ao rolar horizontalmente para consultar valores e situações.\n\nInstala dois fontes do frontend e este roteiro. Confere a base D38, faz backup\ndos fontes, do build e dos bancos; executa o build completo do frontend.\nA validação da correção concentra-se no frontend. Usa o executor ao vivo D38,\ncom aviso a cada 30 segundos sem saída e limite de 10 minutos para o build.\nPreserva o backend, regras, filtros, valores, CSV, contas, senhas e históricos.\nFalhas/Ctrl+C encerram a etapa antes de restaurar fontes/build; registros\nexternos no banco são preservados e sinalizados.\n\nVALIDAÇÃO:\n1. Após RESULTADO=OK, reinicie MEC_SERVICOS_INICIAR_TESTE_LOCAL.py e Ctrl+F5.\n2. Abra Resumo gerencial mensal. Role até Os 12 meses de 2026.\n3. Na primeira coluna da linha Outubro, clique Ver mês, abaixo do nome do mês.\n4. Confira o detalhe de Outubro. Pendências do mês fica no mesmo local.\n5. Ao rolar horizontalmente a tabela, mês e ações continuam visíveis à esquerda.\n6. Para repetir a conferência da OS #3, digite OS #3 na busca e clique Consultar.\n   Esperado: contratação #1 / OS #3 em Outubro, concluída, financeiro encerrado,\n   contratado/recebido/repassado R$ 12.500,00, sem saldo ou pendência atual.\n7. Com a busca vazia, o resumo inclui todas as contratações do ano. Os valores\n   maiores do resumo geral não alteram os valores individuais da OS #3.\n', 'frontend/src/pages/gerencial/ResumoGerencial.css': '.gerencial38-contagens { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 14px; margin: 18px 0; }\n.gerencial38-contagens > div { background: #edf4fb; border: 1px solid #d5e3f1; border-radius: 10px; padding: 16px; min-width: 0; }\n.gerencial38-contagens span { display: block; color: #526b87; font-size: 14px; }\n.gerencial38-contagens strong { display: block; font-size: 26px; margin-top: 6px; }\n.gerencial38-meses table { min-width: 1300px; }\n.gerencial38-meses .gerencial38-mes-acoes { position: sticky; left: 0; min-width: 180px; border-right: 1px solid #dce5ef; }\n.gerencial38-meses th.gerencial38-mes-acoes { z-index: 2; background: #f3f7fc; }\n.gerencial38-meses td.gerencial38-mes-acoes { z-index: 1; background: #fff; }\n.gerencial38-meses .gerencial38-selecionado td.gerencial38-mes-acoes { background: #edf5ff; }\n.gerencial38-mes-acoes nav { margin-top: 10px; }\n.gerencial38-meses td:nth-child(3) { min-width: 160px; }\n.gerencial38-meses td:nth-child(5) { min-width: 180px; }\n.gerencial38-meses td small { margin-top: 3px; }\n.gerencial38 td nav { display: grid; min-width: 135px; }\n.gerencial38 .gerencial38-selecionado { background: #edf5ff; }\n.gerencial38-detalhe > header { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 14px; }\n.gerencial38-detalhe table { min-width: 1250px; margin-top: 20px; }\n.gerencial38-detalhe td:nth-child(3) { min-width: 190px; max-width: 280px; overflow-wrap: anywhere; }\n.gerencial38 .gerencial38-filtros label:first-child { flex: 0 1 150px; }\n@media (max-width: 1100px) { .gerencial38-contagens { grid-template-columns: repeat(3,minmax(0,1fr)); } }\n@media (max-width: 620px) { .gerencial38-contagens { grid-template-columns: repeat(2,minmax(0,1fr)); } .gerencial38 .gerencial38-filtros label:first-child { flex-basis: 100%; } }\n', 'frontend/src/pages/gerencial/ResumoGerencialPage.tsx': 'import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";\nimport { Link, useSearchParams } from "react-router-dom";\nimport { CalendarDays, Download, RefreshCw, Search } from "lucide-react";\nimport { useAuth } from "../../auth/AuthContext";\nimport { api } from "../../services/api";\nimport { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";\nimport { filtrosPainel, situacoesPainel, type FiltroPainel } from "../painel/painelPortal";\nimport { diaUTC } from "../periodo/periodoPortal";\nimport { linkPendenciasGerencial, mensagemGerencial, nomeMes, type ConsultaGerencial, type FiltrosGerencial, type ResumoGerencial } from "./gerencialPortal";\nimport "../periodo/RelatorioPeriodo.css";\nimport "./ResumoGerencial.css";\n\nconst LIMITE = 20;\nfunction anoAtual() { return String(new Date().getUTCFullYear()); }\n\nfunction Valores({ resumo }: { resumo: ResumoGerencial }) {\n  const i = resumo.indicadores;\n  return <div className="periodo35-valores"><div><span>Valor contratado</span><strong>{dinheiro(resumo.valor_contratado)}</strong></div>\n    <div><span>Recebido confirmado</span><strong>{dinheiro(i.recebimentos_confirmados)}</strong></div><div><span>Repassado confirmado</span><strong>{dinheiro(i.repasses_confirmados)}</strong></div>\n    <div><span>Saldo a receber</span><strong>{dinheiro(i.saldo_clientes_controles_abertos)}</strong></div><div><span>Saldo a repassar</span><strong>{dinheiro(i.saldo_fornecedores_controles_abertos)}</strong></div><div><span>Disponível para repasse</span><strong>{dinheiro(i.disponivel_repasses)}</strong></div></div>;\n}\n\nexport default function ResumoGerencialPage() {\n  const { user } = useAuth();\n  const [parametros, setParametros] = useSearchParams();\n  const filtros = useMemo(() => ({ ano: parametros.get("ano") ?? anoAtual(), filtro: (parametros.get("filtro") || "todas") as FiltroPainel,\n    busca: parametros.get("busca") || "", mes: parametros.get("mes") ?? undefined }), [parametros]);\n  const [rascunho, setRascunho] = useState({ ano: filtros.ano, filtro: filtros.filtro, busca: filtros.busca });\n  const [dados, setDados] = useState<ConsultaGerencial | null>(null);\n  const [deslocamento, setDeslocamento] = useState(0);\n  const [revisao, setRevisao] = useState(0);\n  const [carregando, setCarregando] = useState(true);\n  const [baixando, setBaixando] = useState(false);\n  const [erro, setErro] = useState("");\n  const [erroFormulario, setErroFormulario] = useState("");\n  const [aviso, setAviso] = useState("");\n  const download = useRef<AbortController | null>(null);\n\n  useEffect(() => { setRascunho({ ano: filtros.ano, filtro: filtros.filtro, busca: filtros.busca }); setDeslocamento(0); setErroFormulario(""); }, [filtros]);\n  useEffect(() => {\n    const controle = new AbortController(); let vigente = true;\n    download.current?.abort(); download.current = null;\n    setDados(null); setErro(""); setAviso(""); setBaixando(false); setCarregando(true);\n    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }\n    void api.get<ConsultaGerencial>("/administracao/relatorios/gerencial", {\n      params: { ...filtros, deslocamento, limite: LIMITE }, signal: controle.signal, timeout: 20_000,\n    }).then(({ data }) => {\n      if (!vigente) return;\n      if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / LIMITE) * LIMITE); return; }\n      setDados(data);\n    }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemGerencial(falha)); })\n      .finally(() => { if (vigente) setCarregando(false); });\n    return () => { vigente = false; controle.abort(); download.current?.abort(); };\n  }, [filtros, deslocamento, revisao, user?.role]);\n\n  function aplicar(novos: FiltrosGerencial) {\n    const p: Record<string, string> = { ano: String(novos.ano) };\n    if (novos.filtro !== "todas") p.filtro = novos.filtro;\n    if (novos.busca) p.busca = novos.busca;\n    if (novos.mes) p.mes = String(novos.mes);\n    setDeslocamento(0); setErroFormulario(""); setParametros(p); setRevisao(v => v + 1);\n  }\n  function consultar(evento: FormEvent) {\n    evento.preventDefault();\n    if (!/^[0-9]{1,4}$/.test(rascunho.ano) || Number(rascunho.ano) < 1 || Number(rascunho.ano) > 9999) {\n      setErroFormulario("Informe um ano de 1 a 9999, como 2026."); return;\n    }\n    aplicar({ ano: Number(rascunho.ano), filtro: rascunho.filtro, busca: rascunho.busca.trim(), mes: null });\n  }\n  async function exportar() {\n    if (!dados || carregando || baixando || user?.role !== "admin") return;\n    const controle = new AbortController(); download.current = controle; setBaixando(true); setAviso("");\n    try {\n      const resposta = await api.get<Blob>("/administracao/relatorios/gerencial/csv", { params: dados.filtros,\n        responseType: "blob", signal: controle.signal, timeout: 30_000 });\n      if (controle.signal.aborted) return;\n      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");\n      const url = URL.createObjectURL(resposta.data); const a = document.createElement("a");\n      a.href = url; a.download = "MEC_SERVICOS_RESUMO_GERENCIAL_MENSAL.csv";\n      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com o resumo anual, os 12 meses e todas as contratações do detalhamento aplicado."); }\n      finally { a.remove(); URL.revokeObjectURL(url); }\n    } catch (falha: unknown) { if (!controle.signal.aborted) setAviso(mensagemGerencial(falha)); }\n    finally { if (download.current === controle) { download.current = null; setBaixando(false); } }\n  }\n\n  if (user?.role !== "admin") return <p role="alert">O resumo está disponível somente para a administração.</p>;\n  const r = dados?.resumo_ano;\n  const i = r?.indicadores;\n  return <article className="periodo35 gerencial38">\n    <header className="periodo35-cabecalho"><div><h1><CalendarDays aria-hidden="true" /> Resumo gerencial mensal</h1>\n      <p>Compare os 12 meses do ano e consulte as situações e os valores atuais das contratações de cada mês.</p></div>\n      <nav><Link to="/admin">Voltar ao Dashboard</Link><Link to="/admin/relatorios-periodo">Relatório por período</Link><Link to="/admin/pendencias">Central de pendências</Link>\n        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>\n        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" /> {baixando ? "Exportando…" : "Exportar CSV"}</button></nav></header>\n    <section className="periodo35-card"><h2>Selecionar o ano</h2>\n      <form className="periodo35-filtros gerencial38-filtros" onSubmit={consultar}>\n        <label>Ano (UTC)<input inputMode="numeric" maxLength={4} value={rascunho.ano} onChange={e => setRascunho(v => ({ ...v, ano: e.target.value }))} placeholder="2026" /></label>\n        <label>Exibir<select value={rascunho.filtro} onChange={e => setRascunho(v => ({ ...v, filtro: e.target.value as FiltroPainel }))}>{Object.entries(filtrosPainel).map(([v, rotulo]) => <option key={v} value={v}>{rotulo}</option>)}</select></label>\n        <label className="periodo35-busca">Buscar empresa, contratação ou OS<input type="search" maxLength={120} value={rascunho.busca} onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} placeholder="Ex.: oficina, Contratação #1 ou OS #3" /></label>\n        <button type="submit" disabled={carregando}><Search size={16} aria-hidden="true" /> Consultar</button>\n        <button type="button" disabled={carregando} onClick={() => aplicar({ ano: Number(anoAtual()), filtro: "todas", busca: "", mes: null })}>Limpar filtros</button>\n      </form>\n      {erroFormulario && <p role="alert" className="periodo35-erro">{erroFormulario}</p>}\n      <p className="periodo35-nota">O mês considera a criação da contratação em UTC. Situações, pendências, recebimentos e repasses mostram o estado e os acumulados atuais dessas contratações.</p>\n    </section>\n    {aviso && <p role="status" className="periodo35-aviso">{aviso}</p>}\n    {carregando ? <p role="status">Consultando o resumo mensal…</p> : erro ? <p role="alert" className="periodo35-erro">{erro}</p> : dados && r && i && <>\n      <section className="periodo35-card gerencial38-resumo"><h2>Resumo anual · {dados.filtros.ano}</h2>\n        <p className="periodo35-aplicados">{filtrosPainel[dados.filtros.filtro]} · Busca: {dados.filtros.busca || "Todas"} · Detalhamento: {dados.filtros.mes ? nomeMes(dados.filtros.mes) : "Ano inteiro no CSV"}</p>\n        <div className="gerencial38-contagens"><div><span>Contratações</span><strong>{i.total_contratacoes}</strong></div><div><span>Em andamento</span><strong>{r.em_andamento}</strong></div><div><span>Concluídas</span><strong>{i.contratacoes_concluidas}</strong></div><div><span>Canceladas</span><strong>{i.contratacoes_canceladas}</strong></div>\n          <div><span>Para conferência</span><strong>{i.para_conferencia}</strong></div><div><span>Financeiros encerrados</span><strong>{i.financeiros_encerrados}</strong></div><div><span>Com pendências</span><strong>{r.contratacoes_com_pendencias}</strong></div></div>\n        <Valores resumo={r} />\n        <p className="periodo35-nota">Cada contratação soma uma vez. Valores excluem estornos; saldos e disponibilidade consideram controles financeiros abertos. O resumo anual permanece completo ao abrir um mês.</p>\n        <small>Consultado em {dataFinanceiro(dados.gerado_em)}. O CSV consulta dados atuais com os filtros aplicados.</small>\n      </section>\n      <section className="periodo35-card gerencial38-meses"><h2>Os 12 meses de {dados.filtros.ano}</h2>\n        {!i.total_contratacoes && <p className="gerencial38-vazio">Nenhuma contratação corresponde aos filtros deste ano.</p>}\n        <div className="periodo35-scroll"><table><thead><tr><th className="gerencial38-mes-acoes">Mês / consulta</th><th>Contratações</th><th>Situações no painel</th><th>Financeiros</th><th>Pendências atuais</th><th>Valor contratado</th><th>Recebido confirmado</th><th>Repassado confirmado</th></tr></thead>\n          <tbody>{dados.meses.map(m => <tr key={m.mes} className={dados.filtros.mes === m.mes ? "gerencial38-selecionado" : ""}>\n            <td className="gerencial38-mes-acoes"><strong>{nomeMes(m.mes)}</strong><nav><button type="button" aria-pressed={dados.filtros.mes === m.mes} onClick={() => aplicar({ ...dados.filtros, mes: m.mes })}>Ver mês</button><Link to={linkPendenciasGerencial(dados.filtros, m)}>Pendências do mês</Link></nav></td><td>{m.indicadores.total_contratacoes}</td>\n            <td><small>Em andamento: {m.em_andamento}</small><small>Concluídas: {m.indicadores.contratacoes_concluidas}</small><small>Canceladas: {m.indicadores.contratacoes_canceladas}</small><small>Conferência: {m.indicadores.para_conferencia}</small></td>\n            <td>{m.indicadores.financeiros_encerrados} encerrado(s)<small>{m.indicadores.controles_abertos} aberto(s)</small></td>\n            <td>{m.contratacoes_com_pendencias} contratação(ões)<small>Ações operacionais: {m.pendencias_operacionais}</small><small>Ações financeiras: {m.pendencias_financeiras}</small><small>Ações de conferência: {m.pendencias_conferencia}</small></td>\n            <td>{dinheiro(m.valor_contratado)}</td><td>{dinheiro(m.indicadores.recebimentos_confirmados)}</td><td>{dinheiro(m.indicadores.repasses_confirmados)}</td>\n          </tr>)}</tbody></table></div>\n        <p className="periodo35-nota">Pendências contam ações por área. Uma contratação pode ter várias ações. Financeiros encerrados seguem a situação concluída do painel; divergências aparecem para conferência.</p>\n      </section>\n      {dados.resumo_mes && <section className="periodo35-card gerencial38-detalhe"><header><h2>Contratações de {nomeMes(dados.resumo_mes.mes)} · {dados.filtros.ano}</h2>\n        <button type="button" onClick={() => aplicar({ ...dados.filtros, mes: null })}>Fechar detalhamento</button></header>\n        <p>{dados.total} contratação(ões) · {dados.resumo_mes.contratacoes_com_pendencias} com pendências · {diaUTC(dados.resumo_mes.data_inicial)} até {diaUTC(dados.resumo_mes.data_final)}</p>\n        <Valores resumo={dados.resumo_mes} />\n        {!dados.total ? <p className="gerencial38-mes-vazio">Nenhuma contratação neste mês para os filtros aplicados.</p> : <>\n          <div className="periodo35-scroll"><table><thead><tr><th>Contratação / OS</th><th>Contratada em (UTC)</th><th>Cliente / fornecedor</th><th>Situação</th><th>Valor contratado</th><th>Recebido</th><th>Repassado</th><th>Consultar</th></tr></thead>\n            <tbody>{dados.itens.map(c => <tr key={c.contratacao_id}><td><strong>Contratação #{c.contratacao_id}</strong><small>{c.ordem_servico_id ? `OS #${c.ordem_servico_id}` : "Sem OS"}</small></td><td>{diaUTC(c.contratada_em)}</td>\n              <td>{c.cliente}<small>Cliente ID #{c.empresa_cliente_id}</small>{c.fornecedor}<small>Fornecedor ID #{c.empresa_fornecedora_id}</small></td>\n              <td>{situacoesPainel[c.situacao]}<small>{estados[c.financeiro_status]}</small></td><td>{dinheiro(c.valor_contratado)}</td><td>{dinheiro(c.total_recebido)}</td><td>{dinheiro(c.total_repassado)}</td>\n              <td><nav><Link to={`/admin/relatorios?contratacao=${c.contratacao_id}`}>Relatório #{c.contratacao_id}</Link><Link to={`/admin/pagamentos?contratacao=${c.contratacao_id}`}>Financeiro</Link>\n                {c.pendencias.length > 0 && <Link to={"/admin/pendencias?busca=" + encodeURIComponent("Contratação #" + c.contratacao_id)}>Pendências</Link>}</nav></td>\n            </tr>)}</tbody></table></div>\n          <nav className="periodo35-paginacao gerencial38-paginacao" aria-label="Páginas das contratações do mês"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total)} de {dados.total} contratações</span>\n            <button type="button" disabled={!deslocamento || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button><button type="button" disabled={deslocamento + LIMITE >= dados.total || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></nav>\n        </>}\n      </section>}\n    </>}\n  </article>;\n}\n'}

BASE_SHA256 = {'backend/app/principal.py': ['47b6523bc7e67b8d22269a26f12f4f146bf336583bc55b95b11c54fcd733e50d'], 'frontend/src/App.tsx': ['7778bee8c498f3982e94c21b2dba069f5b808b628ae6756018ebda030b48e34e'], 'frontend/src/pages/financeiro/FinanceiroPage.tsx': ['23ed691efa66f11158a22378226994affe1977fae586a9f9122797ad987d1ec0'], 'backend/app/services/financeiro_administrativo.py': ['472578665256b9aa5422a734fc10a0091e95ef103ba654e8a5b581c4ffacf22a'], 'backend/app/models/financeiro_administrativo.py': ['74efa682efd815f778782fb35701783d3081eddc4e689d0329ff9424b253d7e7'], 'frontend/src/pages/financeiro/financeiroPortal.ts': ['703c3d478e1c9f372c7eb21b4bf17670dfbd420305d74595789ce2ef3f6b8eb9'], 'frontend/src/pages/intermediacao/AdminIntermediacaoPage.tsx': ['825a4319b7b5b24137f6446503e2f5b41fa88fef74af1cc1e076bd14496594f3'], 'backend/app/services/intermediacao.py': ['8764c2cc920f9af14edfbc17029cf4875b02bcc6484725657ac69a90c436edfd'], 'backend/app/models/intermediacao.py': ['f6ed06fa32b5aae0d9b5d0b50b6d33759f7d19e2770acdfd1b45e1e3e9293db9'], 'frontend/src/pages/intermediacao/intermediacaoPortal.ts': ['ffc934f799789f13eea2437b99c9b7134318a8b8585c39dd48e2913c6a4d43cd'], 'backend/app/core/permissoes_acesso.py': ['5534eb6eb28423fe7ccce86e93534e34408de2a92887d9664eb730e792861604', '5aedd2d4bdc9be7bb7b0d6a53c87b933c40f9a6f697ab6a586a87e1c3b8a3da6'], 'frontend/src/auth/AuthContext.tsx': ['838f03f499b1374014428e0587d19589058d512ebca0520355b2f28867a9a7a6', '12ae647f73a80e4b1c8c00a01fb2e8cccb7114767d8292a659efe7a90f096c06'], 'frontend/src/services/api.ts': ['e5db9ea929d076ce6e2411d3d89c195a33acc5610af6035f23761a96fe543db3'], 'frontend/src/services/acesso.ts': ['c4c799053bcb9338a55c649a95ae80df45f4b294754c9bb751b0c4e062697ee5', '3dbe6b9d31ca74ab59362bf64740cdc776a209aedd81eafa44c7bc191c215d45'], 'D33_CONTRATO_PAINEL_ADMIN.txt': ['3fdf7577b59dba860bdf7c1f25e05ec0a62762f689a7d11492adb4041532ae15'], 'tests/test_painel_administrativo_d33.py': ['90cf716dc34755ad8db367caca4e77e25210d37c07710242bcc882728e65afab'], 'frontend/src/pages/painel/PainelAdministrativoPage.tsx': ['ad85b216a8d46568e4a46fa34e0d894f1ecc37a19aa5007d91411b6ed77c28c7'], 'frontend/src/pages/painel/painelPortal.ts': ['d077a53088d4023edba366997d77ef97719d17e80faddb8852dab4a6871b7ecd'], 'frontend/src/pages/painel/PainelAdministrativo.css': ['eea184d9069e3382243b0be6aac09cafd9a4ed50cc2063c19acb4625bdac17e2'], 'backend/app/services/painel_administrativo.py': ['60bfec3afcb0ef726f2f833ae9a4771fe05e96f29f35234916eed4575227e338'], 'backend/app/schemas/painel_administrativo.py': ['0fbb493e8132fbc1e5b220685e501860533e2c819b78d10fc30543510e8ab9b4'], 'backend/app/api/rotas/painel_administrativo.py': ['69000275b72a35814298075be18f2e95f04cd74320b7be2ee3deaa8a3872e883'], 'D34_CONTRATO_RELATORIO_ADMIN.txt': ['48c3bf12e576ba0efc391ede4c89dc3760e2c2e1e2b3c7bcc50d93e17d7bb9b2'], 'tests/test_relatorio_administrativo_d34.py': ['26032d692db416035331bc50db0911ba90489e199ace78ebba5a50564709e5bf'], 'frontend/src/pages/relatorios/RelatorioAdministrativoPage.tsx': ['b623fd9adf6d5519f8a636551097f9f6ad90e990ce9190889be4c36a910aa813'], 'frontend/src/pages/relatorios/relatorioPortal.ts': ['4b54d5346f81b065887d1cb8585f132f2418187c8e786c1124a45a75d796963d'], 'frontend/src/pages/relatorios/RelatorioAdministrativo.css': ['8862a85b43d1b282e5a556c2f0a6c35d77f51e20993966fb32282d25714278cb'], 'backend/app/services/relatorio_administrativo.py': ['0fa0ac56e453c32744f04635f64db876433bc5eb448165a08e336935d360d0ff'], 'backend/app/schemas/relatorio_administrativo.py': ['1a4123973bd6a61d82470798c9772924f85bbaeaea0db281f4d198fcd5277a88'], 'backend/app/api/rotas/relatorio_administrativo.py': ['79cad524f2632341685a4ed602eab3b3ed2ec6630bb3e1fd9d322845c87775f7'], 'D35_CONTRATO_RELATORIO_PERIODO.txt': ['f1754e201943e59cfaeb9bf955baaeb36225c217cd6f9cc5f6a59d6d67c33ab1'], 'backend/app/api/rotas/relatorio_periodo.py': ['8d6d5a2015f99668bbfed01bc82d5d45f4009c11d8bd3a0b7f6c0710e74e06d6'], 'backend/app/schemas/relatorio_periodo.py': ['36e2a56bee8b9a6a547930d04e36c47157852feab2ebcbb8b208ac7a0186bce0'], 'backend/app/services/relatorio_periodo.py': ['fa0bf2374a2110aec49ff6e4caebb6848a0e47003ec096e9ae5ab38ed090ab54'], 'frontend/src/pages/periodo/RelatorioPeriodo.css': ['b26d7c98c78774d1d6d185d8770af84159fbc5bcca7ba7e13db5ec2b92a5fbf8'], 'frontend/src/pages/periodo/RelatorioPeriodoPage.tsx': ['60acfd5067c7efc1953b200b617edeb3b2d2133e15b7c1df005d147e1e62d32e'], 'frontend/src/pages/periodo/periodoPortal.ts': ['3ff8c0077bf53414f06620e8d6a545a027d88587a5701132462ae2340b0619df'], 'tests/test_relatorio_periodo_d35.py': ['4d3e5a659815d121cdf466b23e26df322e21286db753257f1073de8061f0016d'], 'D36_CONTRATO_RELATORIO_EMPRESAS.txt': ['af900f57dd64409c244da20ea2417d39a9eb9d20992739fabf830503bc2f428d'], 'backend/app/api/rotas/relatorio_empresas.py': ['225efaa3e2fb99aaa89f4cfc053a6b29b03f4ea39a85c7b13477641b91cbad61'], 'backend/app/schemas/relatorio_empresas.py': ['4e76d3d6ef778ddf80a093e52f78209526e29c92c9dba60e74cbd7628b410df2'], 'backend/app/services/relatorio_empresas.py': ['ffa5df1f91dc6f8b6758e65aa49f41b17c732e9192eaabfa7e7853788833db66'], 'frontend/src/pages/empresas/RelatorioEmpresas.css': ['d86d463385bbb705da95755979e43a1b8db3c7efb71eaee2e7ec4bff28f03a57'], 'frontend/src/pages/empresas/RelatorioEmpresasPage.tsx': ['58785b939e6bb476c69934d2a5fece088224dd26ee18e259a5b2dfc3c2afafc0'], 'frontend/src/pages/empresas/empresasPortal.ts': ['697ab17c48bf729c96d7838e5ffb633aa8efea3c5da47c8e593d6be012f2ea0b'], 'tests/test_relatorio_empresas_d36.py': ['de7106423af5dceec98cdc4d9d84ab8e022191a4d655e0029e85fd4443e50140'], 'D37_CONTRATO_CENTRAL_PENDENCIAS.txt': ['a14a181f67b0df05bcd7e71f451170e6a74eb2041e913875f3342c6c90b53757'], 'backend/app/api/rotas/central_pendencias.py': ['78e947cb062b81cc6af4ba40d261d9bbaefb440fec11d01171d9e5ba09a12cc7'], 'backend/app/schemas/central_pendencias.py': ['7326f459a0a70cd54048620e464731ea53cb4a4a17cd03450a49a52e53e08711'], 'backend/app/services/central_pendencias.py': ['1865833db3b34606b869ef8eb9b1fe32ad0c52aa4337a8fc015734d256296963'], 'frontend/src/pages/pendencias/CentralPendencias.css': ['f7faf8ed21d8660e06a25921b8636824f7e4613f6382419a084c8b7712cace80'], 'frontend/src/pages/pendencias/CentralPendenciasPage.tsx': ['f72bb5826fd226903e7be0788d2dcfe91e4b62db109d366506e232b1d720867c'], 'frontend/src/pages/pendencias/pendenciasPortal.ts': ['93b74cc9d977c80f6b77bc237fa281c254f6e233d3b4bcec9e083d3a9b55cbe4'], 'tests/test_central_pendencias_d37.py': ['a476ed08c728ddd3fcc405f305e9a58c32e3559e8265a00ae55a0079500f5d47'], 'D38_CONTRATO_RESUMO_GERENCIAL.txt': ['346685fa01bd3721879f7aff20cdc51665c979a9e5aa3d4153b7c037d2536622'], 'backend/app/api/rotas/resumo_gerencial.py': ['66cd246932992d32fbd12f9e67ed5178d7f79c15f9e58464c53d6b72b24f7df2'], 'backend/app/schemas/resumo_gerencial.py': ['aa51ebaaae32057c7e3779616eafdf2187a4874ae9738c36cb95b19beb0c4108'], 'backend/app/services/resumo_gerencial.py': ['0bbae5c14ed90e6722975181615ccc8dea76240616f81f1d1827f967a68700ca'], 'frontend/src/pages/gerencial/ResumoGerencial.css': ['5074534060e4207ded8839ac922be37e4766e592c2b989cd4439d4db67eb9a46'], 'frontend/src/pages/gerencial/ResumoGerencialPage.tsx': ['113ad02487345d12f5f0cb5857b5e5019b928e3c25c8ace412596ef79569e9fe'], 'frontend/src/pages/gerencial/gerencialPortal.ts': ['fe6c0ec330f0382fb014b3844bf0402fb6edb8e1b973ce7a2d8d4614f3b8de5a'], 'tests/test_resumo_gerencial_d38.py': ['49b35f87181bcf9e244f716b8c477eeb94c2397cbf214f5644425b906748f22f']}

TABELAS_D31 = ('ciclos_intermediacao', 'eventos_intermediacao')

DDL_TABELAS = {'ciclos_intermediacao': "CREATE TABLE ciclos_intermediacao (\n\tid INTEGER NOT NULL, \n\tordem_servico_id INTEGER NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\tversao INTEGER NOT NULL, \n\tultima_etapa_coleta_id INTEGER NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tatualizado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_ciclo_intermediacao_ordem UNIQUE (ordem_servico_id), \n\tCONSTRAINT ck_ciclo_intermediacao_versao CHECK (versao > 0), \n\tCONSTRAINT ck_ciclo_intermediacao_status CHECK (status IN ('aguardando_material','material_recebido','material_encaminhado','coleta_solicitada','pecas_recebidas','em_avaliacao','retrabalho','retrabalho_encaminhado','aprovado_para_entrega','entregue_cliente','cancelado')), \n\tFOREIGN KEY(ordem_servico_id) REFERENCES ordens_servico (id) ON DELETE RESTRICT\n)", 'eventos_intermediacao': 'CREATE TABLE eventos_intermediacao (\n\tid INTEGER NOT NULL, \n\tciclo_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(40) NOT NULL, \n\tstatus_anterior VARCHAR(40), \n\tstatus_resultante VARCHAR(40) NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\treferencia VARCHAR(200), \n\tparecer_tecnico TEXT, \n\tquantidade_conferida INTEGER, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_evento_intermediacao_versao UNIQUE (ciclo_id, versao), \n\tFOREIGN KEY(ciclo_id) REFERENCES ciclos_intermediacao (id) ON DELETE RESTRICT\n)'}

SCHEMA_D31 = {'ciclos_intermediacao': [('id', 'INTEGER', True, True), ('ordem_servico_id', 'INTEGER', True, False), ('status', 'VARCHAR(40)', True, False), ('versao', 'INTEGER', True, False), ('ultima_etapa_coleta_id', 'INTEGER', True, False), ('criado_em', 'VARCHAR(40)', True, False), ('atualizado_em', 'VARCHAR(40)', True, False)], 'eventos_intermediacao': [('id', 'INTEGER', True, True), ('ciclo_id', 'INTEGER', True, False), ('versao', 'INTEGER', True, False), ('acao', 'VARCHAR(40)', True, False), ('status_anterior', 'VARCHAR(40)', False, False), ('status_resultante', 'VARCHAR(40)', True, False), ('usuario_admin_id', 'INTEGER', True, False), ('administrador_nome', 'VARCHAR(120)', True, False), ('registro_interno', 'TEXT', True, False), ('referencia', 'VARCHAR(200)', False, False), ('parecer_tecnico', 'TEXT', False, False), ('quantidade_conferida', 'INTEGER', False, False), ('criado_em', 'VARCHAR(40)', True, False)]}

DDL_D32 = {'controles_financeiros_admin': "CREATE TABLE controles_financeiros_admin (\n\tcontratacao_id INTEGER NOT NULL, \n\tvalor_contratado_centavos INTEGER NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tversao INTEGER NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tatualizado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (contratacao_id), \n\tCONSTRAINT ck_financeiro_valor CHECK (valor_contratado_centavos > 0), \n\tCONSTRAINT ck_financeiro_versao CHECK (versao > 0), \n\tCONSTRAINT ck_financeiro_status CHECK (status IN ('aberto','encerrado')), \n\tFOREIGN KEY(contratacao_id) REFERENCES contratacoes_servico (id) ON DELETE RESTRICT\n)", 'repasses_administrativos': "CREATE TABLE repasses_administrativos (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tvalor_centavos INTEGER NOT NULL, \n\tforma_pagamento VARCHAR(20) NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tregistrado_em VARCHAR(40) NOT NULL, \n\testornado_em VARCHAR(40), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_repasse_valor CHECK (valor_centavos > 0), \n\tCONSTRAINT ck_repasse_status CHECK (status IN ('confirmado','estornado')), \n\tFOREIGN KEY(contratacao_id) REFERENCES controles_financeiros_admin (contratacao_id) ON DELETE RESTRICT\n)", 'eventos_financeiros_admin': 'CREATE TABLE eventos_financeiros_admin (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(32) NOT NULL, \n\tchave_operacao VARCHAR(36), \n\tresumo_operacao VARCHAR(64), \n\tpagamento_id INTEGER, \n\trepasse_id INTEGER, \n\tvalor_centavos INTEGER, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\treferencia VARCHAR(200), \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_financeiro_evento_versao UNIQUE (contratacao_id, versao), \n\tCONSTRAINT uq_financeiro_chave UNIQUE (contratacao_id, chave_operacao), \n\tCONSTRAINT uq_financeiro_referencia UNIQUE (contratacao_id, referencia), \n\tFOREIGN KEY(contratacao_id) REFERENCES controles_financeiros_admin (contratacao_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(pagamento_id) REFERENCES pagamentos_contratacao (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(repasse_id) REFERENCES repasses_administrativos (id) ON DELETE RESTRICT\n)'}

INDICES_D32 = {'ix_repasses_administrativos_contratacao_id': 'CREATE INDEX ix_repasses_administrativos_contratacao_id ON repasses_administrativos (contratacao_id)', 'ix_eventos_financeiros_admin_contratacao_id': 'CREATE INDEX ix_eventos_financeiros_admin_contratacao_id ON eventos_financeiros_admin (contratacao_id)'}

SCHEMA_D32 = {'controles_financeiros_admin': [('contratacao_id', 'INTEGER', True, True), ('valor_contratado_centavos', 'INTEGER', True, False), ('status', 'VARCHAR(16)', True, False), ('versao', 'INTEGER', True, False), ('criado_em', 'VARCHAR(40)', True, False), ('atualizado_em', 'VARCHAR(40)', True, False)], 'repasses_administrativos': [('id', 'INTEGER', True, True), ('contratacao_id', 'INTEGER', True, False), ('valor_centavos', 'INTEGER', True, False), ('forma_pagamento', 'VARCHAR(20)', True, False), ('status', 'VARCHAR(16)', True, False), ('registrado_em', 'VARCHAR(40)', True, False), ('estornado_em', 'VARCHAR(40)', False, False)], 'eventos_financeiros_admin': [('id', 'INTEGER', True, True), ('contratacao_id', 'INTEGER', True, False), ('versao', 'INTEGER', True, False), ('acao', 'VARCHAR(32)', True, False), ('chave_operacao', 'VARCHAR(36)', False, False), ('resumo_operacao', 'VARCHAR(64)', False, False), ('pagamento_id', 'INTEGER', False, False), ('repasse_id', 'INTEGER', False, False), ('valor_centavos', 'INTEGER', False, False), ('usuario_admin_id', 'INTEGER', True, False), ('administrador_nome', 'VARCHAR(120)', True, False), ('registro_interno', 'TEXT', True, False), ('referencia', 'VARCHAR(200)', False, False), ('criado_em', 'VARCHAR(40)', True, False)]}

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
    raise RuntimeError("A porta 8000 está em uso. Pare o backend com Ctrl+C no terminal dele antes de executar o D38 FIX1.")

def configuracao_bancos(raiz: Path):
    sys.path.insert(0, str(raiz))
    from backend.app.core.configuracao import configuracoes
    if configuracoes.prefixo_api.rstrip("/") != "/api/v1": raise RuntimeError("Confira o prefixo /api/v1.")
    url = configuracoes.url_banco_dados
    if not url.startswith("sqlite:///"): raise RuntimeError("O D33 foi preparado para o banco SQLite local.")
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
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=raiz, delete=False, prefix="mec_d38_fix1_relatorio_") as temp:
            temp.write(conteudo); caminho = Path(temp.name)
        try: os.replace(caminho, alvo)
        finally: caminho.unlink(missing_ok=True)
        print(("JSON=" if extensao == "json" else "RELATORIO=") + str(alvo), flush=True)

def gravar_atomico(alvo: Path, conteudo: bytes) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=alvo.parent, delete=False, prefix="mec_d38_fix1_") as temp:
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
    limite = limite_segundos if limite_segundos is not None else (1800 if rotulo == "pytest" else 600)
    print("Executando " + rotulo + "... (saída ao vivo)", flush=True)
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
                "duracao_segundos": round(time.monotonic() - inicio, 2)}
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
                "duracao_segundos": round(time.monotonic() - inicio, 2)}
            raise
        finally:
            if processo is not None and processo.stdout is not None: processo.stdout.close()

def plano_arquivos(raiz: Path) -> dict[str, bytes]:
    for nome, esperados in BASE_SHA256.items():
        alvo = seguro(raiz, nome)
        finais = [sha(FONTES[nome].encode("utf-8"))] if nome in FONTES else []
        if not alvo.is_file() or not any(fonte_confere(alvo.read_bytes(), h) for h in esperados + finais):
            raise RuntimeError("Fonte diferente da base D38 conhecida; preservado: " + nome)
    novos = {n: texto.encode("utf-8") for n, texto in FONTES.items()}
    for nome, conteudo in novos.items():
        alvo = seguro(raiz, nome)
        if alvo.exists() and nome not in BASE_SHA256 and not fonte_confere(alvo.read_bytes(), sha(conteudo)):
            raise RuntimeError("Arquivo existente com outro conteúdo; preservado: " + nome)
        if nome.endswith(".py"): ast.parse(conteudo, filename=nome)
    return {n: b for n, b in novos.items() if not (raiz / n).is_file() or not fonte_confere((raiz / n).read_bytes(), sha(b))}

def conferir_base_d38(raiz, banco):
    arquivo = seguro(raiz, "MEC_SERVICOS_V0_1_D38_RESUMO_GERENCIAL_MENSAL_RELATORIO.json")
    if not arquivo.is_file(): raise RuntimeError("Relatório da instalação D38 não encontrado.")
    dados = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    if dados.get("resultado") != "OK" or dados.get("revision") != D38_REVISION:
        raise RuntimeError("Conclua a instalação D38 antes do D38 FIX1.")
    with closing(sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True)) as conexao:
        conexao.execute("PRAGMA query_only=ON")
        if not conferir_schema(conexao) or not conferir_schema_d32(conexao):
            raise RuntimeError("Tabelas D31/D32 ausentes; banco preservado.")
        for nome in ("contratacoes_servico", "pagamentos_contratacao", "ordens_servico", "etapas_producao"):
            if not conexao.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone():
                raise RuntimeError("Tabela de negócio necessária ausente: " + nome)

def main() -> int:
    print("MEC-Serviços D38 FIX1 — Botão Ver mês visível", flush=True)
    print("REVISION=" + REVISION, flush=True)
    raiz = None; originais = {}; alterados = []; pastas_novas = []; backup = None
    dist_existia = False; build_iniciado = False; concluido = False
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapa": "inicio", "restaurado": False,
                 "operacoes_negocio_executadas": False, "tabelas_criadas": 0}
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
        os.chdir(raiz); banco, acesso = configuracao_bancos(raiz); conferir_base_d38(raiz, banco)
        negocio_antes = ler_historico(banco); contas_antes = ler_historico(acesso)
        print("BASE_D38_CONFIRMADA=True", flush=True)
        relatorio["etapa"] = "backup"
        backup = seguro(raiz, "_mec_backups/D38_FIX1_VER_MES_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
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
        print("ARQUIVOS_D38_FIX1_APLICADOS=" + str(len(plano)), flush=True)
        with tempfile.TemporaryDirectory(prefix="mec_d38_fix1_build_") as pasta:
            ambiente = dict(os.environ)
            ambiente["MEC_URL_BANCO_DADOS"] = "sqlite:///" + (Path(pasta) / "negocio.db").resolve().as_posix()
            ambiente["MEC_ACESSOS_DB"] = str(Path(pasta) / "acesso.db")
            ambiente["MEC_MODO_TESTE_LOCAL"] = "0"; ambiente["MEC_AMBIENTE"] = "teste"; ambiente["MEC_COOKIE_SEGURO"] = "0"
            build_iniciado = True; executar(raiz / "frontend", "npm_build", [npm, "run", "build"], ambiente, relatorio)
        relatorio["etapa"] = "conferir_preservacao"
        conferir_base_d38(raiz, banco)
        if ler_historico(banco) != negocio_antes: raise RuntimeError("Banco mudou durante a validação; registros externos preservados.")
        if ler_historico(acesso) != contas_antes: raise RuntimeError("Banco de acesso mudou durante a validação; contas preservadas.")
        concluido = True
        relatorio.update(resultado="OK", etapa="concluido", arquivos_alterados=alterados,
            historico_negocio_preservado=True, historico_financeiro_d32_preservado=True, historico_administrativo_d33_preservado=True, relatorio_d34_preservado=True, relatorio_d35_preservado=True, relatorio_d36_preservado=True, central_d37_preservada=True, resumo_gerencial_d38_preservado=True, contas_e_senhas_preservadas=True, validacao_frontend=True,
            historico_negocio_sha256=negocio_antes, historico_acesso_sha256=contas_antes)
        print("TABELAS_D38_FIX1_CRIADAS=0", flush=True)
        print("HISTORICO_NEGOCIO_PRESERVADO=True", flush=True)
        print("HISTORICO_FINANCEIRO_D32_PRESERVADO=True", flush=True)
        print("PAINEL_E_HISTORICO_D33_PRESERVADOS=True", flush=True)
        print("RELATORIO_E_HISTORICO_D34_PRESERVADOS=True", flush=True)
        print("RELATORIO_E_HISTORICO_D35_PRESERVADOS=True", flush=True)
        print("RELATORIO_E_HISTORICO_D36_PRESERVADOS=True", flush=True)
        print("CENTRAL_E_HISTORICO_D37_PRESERVADOS=True", flush=True)
        print("RESUMO_GERENCIAL_D38_PRESERVADO=True", flush=True)
        print("CONTAS_E_SENHAS_PRESERVADAS=True", flush=True)
        try: salvar_relatorio(raiz, relatorio)
        except OSError: print("RELATORIO_NAO_GRAVADO=True; preserve a saída do terminal.", flush=True)
        print("RESULTADO=OK", flush=True)
        print("Reinicie o backend, atualize o frontend e abra Administração > Dashboard.", flush=True)
        print("Abra Resumo gerencial mensal e role até Os 12 meses de 2026. Ver mês agora fica na primeira coluna, abaixo de Outubro.", flush=True)
        print("Roteiro local: D38_FIX1_VER_MES_VISIVEL.txt", flush=True)
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
