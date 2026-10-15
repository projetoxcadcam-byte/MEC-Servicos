'MEC-Serviços D53 — Gráfico do ranking administrativo.\nExige D52 FIX1 concluída. Backup, testes seletivos e build, sem modificar os bancos.\nRanking exclusivo do ADM; notas e históricos preservados.\n'

from __future__ import annotations

LIMITE_PYTEST_SEGUNDOS = 1800

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

REVISION = 'MEC-SERVICOS-V0.1-D53-GRAFICO-RANKING-ADMIN-2026-10-09'

LIMITE_BUILD_SEGUNDOS = 600

D41_REVISION = 'MEC-SERVICOS-V0.1-D41-CONSOLIDACAO-BACKUP-2026-10-06'

STEM = 'MEC_SERVICOS_V0_1_D53_GRAFICO_RANKING_ADMIN_RELATORIO'

FONTES = {'frontend/src/pages/avaliacoes/RankingAvaliacoesPage.tsx': 'import { useEffect, useState } from "react";\nimport { Link } from "react-router-dom";\nimport { useAuth } from "../../auth/AuthContext";\nimport { consultar, mensagem, raiz, type Ranking } from "./avaliacoesPortal";\nimport GraficoRanking from "./GraficoRanking";\nimport "./Avaliacoes.css";\n\nconst TAMANHO_PAGINA = 20;\n\nexport default function RankingAvaliacoesPage() {\n  const { user } = useAuth();\n  if (!user || user.role !== "admin") return <main className="mec-av"><p>Esta consulta está disponível somente para a administração.</p></main>;\n  const contexto = `${user.usuario_id}:${user.role}:${user.empresa_id ?? 0}`;\n  return <Conteudo key={contexto} contexto={contexto} />;\n}\n\nfunction Conteudo({ contexto }: { contexto: string }) {\n  const [origem, setOrigem] = useState<"cliente" | "admin">("cliente");\n  const [inicio, setInicio] = useState(0);\n  const [revisao, setRevisao] = useState(0);\n  const [resposta, setResposta] = useState<{ chave: string; dados: Ranking } | null>(null);\n  const [falha, setFalha] = useState<{ chave: string; mensagem: string } | null>(null);\n  const chave = `${contexto}:${origem}:${inicio}:${revisao}`;\n  const ranking = resposta?.chave === chave ? resposta.dados : null;\n  const erro = falha?.chave === chave ? falha.mensagem : "";\n\n  useEffect(() => {\n    const controle = new AbortController();\n    setResposta(null); setFalha(null);\n    void consultar<Ranking>(raiz("admin") + "/ranking", contexto, controle.signal,\n      { origem, inicio, limite: TAMANHO_PAGINA })\n      .then(dados => { if (!controle.signal.aborted) setResposta({ chave, dados }); })\n      .catch(e => { if (!controle.signal.aborted) setFalha({ chave, mensagem: mensagem(e) }); });\n    return () => controle.abort();\n  }, [contexto, origem, inicio, chave]);\n\n  return <main className="mec-av"><header className="mec-av-cabecalho"><div>\n    <p className="mec-av-sobre">Administração · Qualidade do serviço</p><h1>Reputação e ranking</h1>\n    <p>Compare as notas de cada empresa fornecedora no gráfico. Consulta exclusiva da administração.</p>\n  </div><Link className="mec-av-link" to="/admin/avaliacoes">Consultar avaliações</Link></header>\n    <div className="mec-av-abas" aria-label="Origem das avaliações">\n      <button type="button" aria-pressed={origem === "cliente"} onClick={() => { setOrigem("cliente"); setInicio(0); }}>Notas de clientes</button>\n      <button type="button" aria-pressed={origem === "admin"} onClick={() => { setOrigem("admin"); setInicio(0); }}>Notas da administração</button>\n      <button type="button" className="mec-av-secundario" onClick={() => setRevisao(v => v + 1)}>Atualizar</button>\n    </div>\n    <p className="mec-av-aviso">A classificação considera a média da nota e, em caso de empate, a quantidade de avaliações. A escolha do fornecedor continua sendo realizada pela administração.</p>\n    {erro && <p role="alert" className="mec-av-erro">{erro}</p>}\n    {!ranking && !erro && <p role="status">Consultando reputação…</p>}\n    {ranking && <>\n      <div className="mec-ranking-pagina">\n        <p>{ranking.total} {ranking.total === 1 ? "empresa fornecedora" : "empresas fornecedoras"} · até {TAMANHO_PAGINA} por página</p>\n        <nav className="mec-av-paginacao" aria-label="Páginas do ranking">\n          <button type="button" disabled={inicio === 0} onClick={() => setInicio(v => Math.max(0, v - TAMANHO_PAGINA))}>Anterior</button>\n          <span>{ranking.total ? `${inicio + 1}–${Math.min(inicio + TAMANHO_PAGINA, ranking.total)} de ${ranking.total}` : "0 resultados"}</span>\n          <button type="button" disabled={inicio + TAMANHO_PAGINA >= ranking.total} onClick={() => setInicio(v => v + TAMANHO_PAGINA)}>Próxima</button>\n        </nav>\n      </div>\n      <GraficoRanking ranking={ranking} />\n      {!!ranking.itens.length && <details className="mec-ranking-dados"><summary>Ver tabela de notas e posições</summary>\n        <div className="mec-av-tabela"><table><caption className="mec-av-sr">{origem === "cliente" ? "Notas de clientes" : "Notas da administração"} — página atual do ranking</caption>\n          <thead><tr><th scope="col">Posição</th><th scope="col">Fornecedor</th><th scope="col">Média / 5</th><th scope="col">Avaliações</th></tr></thead>\n          <tbody>{ranking.itens.map(i => <tr key={i.fornecedor_codigo}><td>{i.posicao === null ? "Sem posição" : `${i.posicao}º`}</td>\n            <td>{i.razao_social ? `${i.razao_social} · ${i.fornecedor_codigo}` : i.fornecedor_codigo}</td>\n            <td>{i.media === null ? "Sem notas" : i.media.replace(".", ",")}</td><td>{i.quantidade}</td></tr>)}</tbody>\n        </table></div>\n      </details>}\n    </>}\n  </main>;\n}\n', 'frontend/src/pages/avaliacoes/GraficoRanking.tsx': 'import { useId } from "react";\nimport type { Ranking } from "./avaliacoesPortal";\nimport "./RankingAdministrativo.css";\n\nexport default function GraficoRanking({ ranking }: { ranking: Ranking }) {\n  const titulo = useId();\n  const descricao = useId();\n  return <section className="mec-ranking-grafico" aria-labelledby={titulo} aria-describedby={descricao}>\n    <header className="mec-ranking-cabecalho">\n      <div><h2 id={titulo}>Gráfico do ranking</h2>\n        <p id={descricao}>{ranking.origem === "cliente" ? "Notas de clientes" : "Notas da administração"} · média de 0 a 5.\n          {" "}Cada barra representa a nota média de uma empresa fornecedora.</p></div>\n      <span className="mec-ranking-restrito">Somente ADM</span>\n    </header>\n    {ranking.itens.length ? <>\n      <div className="mec-ranking-eixo" aria-hidden="true"><span>Empresa / posição</span>\n        <div>{[0, 1, 2, 3, 4, 5].map(n => <span key={n}>{n}</span>)}</div><span>Média / 5</span></div>\n      <ol className="mec-ranking-lista">\n        {ranking.itens.map(item => {\n          const nota = item.media === null ? null : Number(item.media);\n          const avaliada = item.quantidade > 0 && nota !== null && Number.isFinite(nota) && nota >= 0 && nota <= 5;\n          const media = avaliada ? item.media!.replace(".", ",") : null;\n          return <li key={item.fornecedor_codigo} className="mec-ranking-linha">\n            <div className="mec-ranking-empresa">\n              <span className={item.posicao === null ? "mec-ranking-posicao sem-nota" : "mec-ranking-posicao"}>\n                {item.posicao === null ? "—" : `${item.posicao}º`}\n              </span>\n              <div><strong>{item.razao_social || item.fornecedor_codigo}</strong>\n                <small>{item.fornecedor_codigo}{item.posicao === null ? " · Sem posição" : ""}</small></div>\n            </div>\n            <div className="mec-ranking-trilho" aria-hidden="true">\n              {avaliada ? <div className="mec-ranking-barra" style={{ width: `${nota! * 20}%` }} />\n                : <span className="mec-ranking-sem-notas">Sem avaliações</span>}\n            </div>\n            <div className="mec-ranking-nota">\n              <strong>{media === null ? "Sem notas" : <>{media}<span className="mec-av-sr"> de 5</span></>}</strong>\n              <small>{item.quantidade} {item.quantidade === 1 ? "avaliação" : "avaliações"}</small>\n            </div>\n          </li>;\n        })}\n      </ol>\n    </> : <p className="mec-av-vazio">Nenhum fornecedor encontrado.</p>}\n    <p className="mec-ranking-rodape">Empresas sem avaliações ficam sem posição. As notas de clientes e da administração são consultadas separadamente.</p>\n  </section>;\n}\n', 'frontend/src/pages/avaliacoes/RankingAdministrativo.css': '.mec-ranking-grafico { border: 1px solid #d2e0e9; border-radius: 14px; padding: 24px; background: #fff; color: #173247; }\n.mec-ranking-cabecalho { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }\n.mec-ranking-cabecalho h2 { margin: 0 0 6px; }\n.mec-ranking-cabecalho p { color: #4b667a; margin: 0; max-width: 760px; font-size: 14px; }\n.mec-ranking-restrito { display: inline-block; white-space: nowrap; padding: 6px 10px; border-radius: 6px; background: #edf4f8; border: 1px solid #cfdee8; color: #31516a; font-size: 12px; font-weight: 700; }\n.mec-ranking-eixo, .mec-ranking-linha { display: grid; grid-template-columns: minmax(180px, 2fr) minmax(150px, 3fr) 100px; gap: 18px; align-items: center; }\n.mec-ranking-eixo { margin-bottom: 6px; color: #4b667a; font-size: 12px; }\n.mec-ranking-eixo > div { display: flex; justify-content: space-between; }\n.mec-ranking-eixo > span:last-child { text-align: right; }\n.mec-ranking-lista { padding: 0; margin: 0; list-style: none; }\n.mec-ranking-linha { padding: 15px 0; border-bottom: 1px solid #e5edf3; }\n.mec-ranking-empresa { display: flex; align-items: center; gap: 12px; min-width: 0; }\n.mec-ranking-empresa > div { min-width: 0; }\n.mec-ranking-empresa strong { display: block; overflow-wrap: anywhere; font-size: 14px; line-height: 1.4; }\n.mec-ranking-empresa small, .mec-ranking-nota small { display: block; color: #4b667a; margin-top: 4px; font-size: 12px; }\n.mec-ranking-posicao { display: flex; align-items: center; justify-content: center; min-width: 42px; height: 36px; padding: 0 6px; background: #edf4f8; color: #234d6b; border-radius: 7px; font-weight: 700; font-size: 14px; }\n.mec-ranking-posicao.sem-nota { background: #f1f4f6; color: #627583; }\n.mec-ranking-trilho { height: 28px; border-radius: 6px; overflow: hidden; background-color: #f1f6f9; background-image: linear-gradient(to right, transparent calc(100% - 1px), #d5e1e9 0); background-size: 20% 100%; }\n.mec-ranking-barra { height: 100%; background: #24688e; border-radius: 6px; }\n.mec-ranking-sem-notas { display: block; line-height: 28px; padding-left: 10px; color: #526b7d; font-size: 12px; }\n.mec-ranking-nota { text-align: right; font-variant-numeric: tabular-nums; }\n.mec-ranking-nota strong { font-size: 17px; }\n.mec-ranking-nota small { white-space: nowrap; }\n.mec-ranking-rodape { margin: 18px 0 0; color: #4b667a; font-size: 13px; }\n.mec-ranking-pagina { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin: 18px 0; }\n.mec-ranking-pagina .mec-av-paginacao { margin: 0; }\n.mec-ranking-pagina p { margin: 0; color: #4b667a; font-size: 14px; }\n.mec-ranking-dados { margin: 20px 0; }\n.mec-ranking-dados summary { cursor: pointer; padding: 12px 0; color: #214c6b; font-weight: 600; }\n.mec-ranking-dados summary:focus-visible { outline: 3px solid #5baad0; outline-offset: 3px; border-radius: 4px; }\n@media (max-width: 760px) {\n  .mec-ranking-grafico { padding: 18px 14px; }\n  .mec-ranking-eixo, .mec-ranking-linha { grid-template-columns: minmax(0, 1fr) 90px; gap: 10px; }\n  .mec-ranking-eixo > span:first-child { display: none; }\n  .mec-ranking-linha .mec-ranking-empresa { grid-column: 1 / -1; }\n  .mec-ranking-linha { padding: 14px 0; }\n  .mec-ranking-cabecalho { margin-bottom: 18px; }\n  .mec-ranking-pagina .mec-av-paginacao { flex-wrap: wrap; justify-content: flex-start; }\n}\n', 'D53_CONTRATO_GRAFICO_RANKING_ADMIN.txt': 'MEC-Serviços D53 — Gráfico do ranking administrativo\n\nREQUISITO\nD52 FIX1 concluída com RESULTADO=OK. Feche o teste local antes da instalação.\n\nO QUE FOI ADICIONADO\nGráfico de barras horizontais em Administração > Avaliações > Ver reputação e ranking.\nTambém pode ser aberto pelo endereço /admin/ranking no mesmo site do teste local.\nCada empresa fornecedora (incluindo empresas de tipo ambos) aparece com nome,\ncódigo, posição, nota média e quantidade de avaliações.\nEscala fixa de 0 a 5; notas de clientes e da administração ficam em consultas\nseparadas. Empresas sem notas aparecem sem posição e sem barra numérica.\nSão exibidas até 20 empresas por página. Anterior/Próxima permitem consultar todas.\nVer tabela de notas e posições abre os valores da página em formato de tabela.\nAtualizar consulta novamente as notas. Dados antigos são retirados ao trocar\norigem, página ou conta, enquanto a consulta atual estiver pendente.\n\nPRIVACIDADE\nRanking, médias comparativas, posições e gráfico são exclusivos do administrador.\nCliente e fornecedor continuam sem ranking, inclusive pelo endereço direto e API.\nO fornecedor continua podendo consultar somente as notas dos seus próprios serviços.\nAs regras existentes de cálculo e desempate não foram alteradas.\n\nATIVAÇÃO NO POWERSHELL\ncd C:\\Users\\Omega\\Desktop\\MEC-Servicos\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_V0_1_D53_GRAFICO_RANKING_ADMIN.py\n.\\.venv\\Scripts\\python.exe .\\MEC_SERVICOS_INICIAR_TESTE_LOCAL.py\nAtualize a página com Ctrl+F5 e entre com o perfil administrador.\n\nTESTE\n1. Abra Administração > Avaliações > Ver reputação e ranking.\n2. Confira no gráfico nome, posição, média / 5 e quantidade de avaliações.\n3. Abra Ver tabela de notas e posições: os números devem ser os mesmos.\n4. Alterne Notas de clientes e Notas da administração. As origens não se misturam.\n5. Se houver mais de 20 fornecedores, use Próxima e Anterior. As posições continuam\n   a classificação geral e todas as empresas são acessíveis pelas páginas.\n6. Empresas sem avaliações devem mostrar Sem notas / Sem posição, nunca nota zero.\n7. Entre como cliente e como fornecedor. O gráfico e o ranking não devem aparecer.\n   Tentar /admin/ranking deve ser recusado pelo controle de perfil.\n8. Confira que o fornecedor continua consultando suas notas em Avaliações.\n\nPRESERVAÇÃO\nNenhuma tabela nova, avaliação criada ou cálculo de nota modificado.\nNotas, operações, materiais, capacidades, PDFs, históricos, contas e senhas\npermanecem preservados. Fontes diferentes da base conhecida são recusadas.\nO instalador cria backup e executa testes seletivos de avaliações, ranking privado\ne autenticação, além da compilação do frontend, com saída ao vivo.\n'}

BASE_SHA256 = {'backend/app/principal.py': ['48fc7977d5a06f508e016364985aed89c457155c622b26143aa45db7161b18dc'], 'frontend/src/App.tsx': ['3e1c89a17c90aa634d75c0e9cab91435aa42e890b1925250d596f8ea9411bdab'], 'frontend/src/pages/financeiro/FinanceiroPage.tsx': ['670a078eae983c565a4e49743a5567acb4645ad068b7d82262b804a6e1cbe34a'], 'backend/app/services/financeiro_administrativo.py': ['472578665256b9aa5422a734fc10a0091e95ef103ba654e8a5b581c4ffacf22a'], 'backend/app/models/financeiro_administrativo.py': ['74efa682efd815f778782fb35701783d3081eddc4e689d0329ff9424b253d7e7'], 'frontend/src/pages/financeiro/financeiroPortal.ts': ['703c3d478e1c9f372c7eb21b4bf17670dfbd420305d74595789ce2ef3f6b8eb9'], 'frontend/src/pages/intermediacao/AdminIntermediacaoPage.tsx': ['825a4319b7b5b24137f6446503e2f5b41fa88fef74af1cc1e076bd14496594f3'], 'backend/app/services/intermediacao.py': ['8764c2cc920f9af14edfbc17029cf4875b02bcc6484725657ac69a90c436edfd'], 'backend/app/models/intermediacao.py': ['f6ed06fa32b5aae0d9b5d0b50b6d33759f7d19e2770acdfd1b45e1e3e9293db9'], 'frontend/src/pages/intermediacao/intermediacaoPortal.ts': ['ffc934f799789f13eea2437b99c9b7134318a8b8585c39dd48e2913c6a4d43cd'], 'backend/app/core/permissoes_acesso.py': ['76f8574acfe5f118e3653c0f4fa95da4bcb568497cca14e6d956bc21d97b435e'], 'frontend/src/auth/AuthContext.tsx': ['3ab2c8142ca86f6df51a72799f31a61c66e24f5fac59e20e83a8ff3532a5a795'], 'frontend/src/services/api.ts': ['e5db9ea929d076ce6e2411d3d89c195a33acc5610af6035f23761a96fe543db3'], 'frontend/src/services/acesso.ts': ['c4c799053bcb9338a55c649a95ae80df45f4b294754c9bb751b0c4e062697ee5', '3dbe6b9d31ca74ab59362bf64740cdc776a209aedd81eafa44c7bc191c215d45'], 'D33_CONTRATO_PAINEL_ADMIN.txt': ['3fdf7577b59dba860bdf7c1f25e05ec0a62762f689a7d11492adb4041532ae15'], 'tests/test_painel_administrativo_d33.py': ['90cf716dc34755ad8db367caca4e77e25210d37c07710242bcc882728e65afab'], 'frontend/src/pages/painel/PainelAdministrativoPage.tsx': ['a64dbcb85ce28909dc9510ab18ae876cdd82c2eb4781731e8bb63f8f5ff71fca'], 'frontend/src/pages/painel/painelPortal.ts': ['d077a53088d4023edba366997d77ef97719d17e80faddb8852dab4a6871b7ecd'], 'frontend/src/pages/painel/PainelAdministrativo.css': ['eea184d9069e3382243b0be6aac09cafd9a4ed50cc2063c19acb4625bdac17e2'], 'backend/app/services/painel_administrativo.py': ['60bfec3afcb0ef726f2f833ae9a4771fe05e96f29f35234916eed4575227e338'], 'backend/app/schemas/painel_administrativo.py': ['0fbb493e8132fbc1e5b220685e501860533e2c819b78d10fc30543510e8ab9b4'], 'backend/app/api/rotas/painel_administrativo.py': ['69000275b72a35814298075be18f2e95f04cd74320b7be2ee3deaa8a3872e883'], 'D34_CONTRATO_RELATORIO_ADMIN.txt': ['48c3bf12e576ba0efc391ede4c89dc3760e2c2e1e2b3c7bcc50d93e17d7bb9b2'], 'tests/test_relatorio_administrativo_d34.py': ['26032d692db416035331bc50db0911ba90489e199ace78ebba5a50564709e5bf'], 'frontend/src/pages/relatorios/RelatorioAdministrativoPage.tsx': ['b623fd9adf6d5519f8a636551097f9f6ad90e990ce9190889be4c36a910aa813'], 'frontend/src/pages/relatorios/relatorioPortal.ts': ['4b54d5346f81b065887d1cb8585f132f2418187c8e786c1124a45a75d796963d'], 'frontend/src/pages/relatorios/RelatorioAdministrativo.css': ['8862a85b43d1b282e5a556c2f0a6c35d77f51e20993966fb32282d25714278cb'], 'backend/app/services/relatorio_administrativo.py': ['0fa0ac56e453c32744f04635f64db876433bc5eb448165a08e336935d360d0ff'], 'backend/app/schemas/relatorio_administrativo.py': ['1a4123973bd6a61d82470798c9772924f85bbaeaea0db281f4d198fcd5277a88'], 'backend/app/api/rotas/relatorio_administrativo.py': ['79cad524f2632341685a4ed602eab3b3ed2ec6630bb3e1fd9d322845c87775f7'], 'D35_CONTRATO_RELATORIO_PERIODO.txt': ['f1754e201943e59cfaeb9bf955baaeb36225c217cd6f9cc5f6a59d6d67c33ab1'], 'backend/app/api/rotas/relatorio_periodo.py': ['8d6d5a2015f99668bbfed01bc82d5d45f4009c11d8bd3a0b7f6c0710e74e06d6'], 'backend/app/schemas/relatorio_periodo.py': ['36e2a56bee8b9a6a547930d04e36c47157852feab2ebcbb8b208ac7a0186bce0'], 'backend/app/services/relatorio_periodo.py': ['fa0bf2374a2110aec49ff6e4caebb6848a0e47003ec096e9ae5ab38ed090ab54'], 'frontend/src/pages/periodo/RelatorioPeriodo.css': ['b26d7c98c78774d1d6d185d8770af84159fbc5bcca7ba7e13db5ec2b92a5fbf8'], 'frontend/src/pages/periodo/RelatorioPeriodoPage.tsx': ['1dc0223179de83b01626f91e095c384e7929a992af698f28c8ac50e03ace1fbb'], 'frontend/src/pages/periodo/periodoPortal.ts': ['3ff8c0077bf53414f06620e8d6a545a027d88587a5701132462ae2340b0619df'], 'tests/test_relatorio_periodo_d35.py': ['4d3e5a659815d121cdf466b23e26df322e21286db753257f1073de8061f0016d'], 'D36_CONTRATO_RELATORIO_EMPRESAS.txt': ['af900f57dd64409c244da20ea2417d39a9eb9d20992739fabf830503bc2f428d'], 'backend/app/api/rotas/relatorio_empresas.py': ['225efaa3e2fb99aaa89f4cfc053a6b29b03f4ea39a85c7b13477641b91cbad61'], 'backend/app/schemas/relatorio_empresas.py': ['4e76d3d6ef778ddf80a093e52f78209526e29c92c9dba60e74cbd7628b410df2'], 'backend/app/services/relatorio_empresas.py': ['ffa5df1f91dc6f8b6758e65aa49f41b17c732e9192eaabfa7e7853788833db66'], 'frontend/src/pages/empresas/RelatorioEmpresas.css': ['d86d463385bbb705da95755979e43a1b8db3c7efb71eaee2e7ec4bff28f03a57'], 'frontend/src/pages/empresas/RelatorioEmpresasPage.tsx': ['58785b939e6bb476c69934d2a5fece088224dd26ee18e259a5b2dfc3c2afafc0'], 'frontend/src/pages/empresas/empresasPortal.ts': ['697ab17c48bf729c96d7838e5ffb633aa8efea3c5da47c8e593d6be012f2ea0b'], 'tests/test_relatorio_empresas_d36.py': ['de7106423af5dceec98cdc4d9d84ab8e022191a4d655e0029e85fd4443e50140'], 'D37_CONTRATO_CENTRAL_PENDENCIAS.txt': ['a14a181f67b0df05bcd7e71f451170e6a74eb2041e913875f3342c6c90b53757'], 'backend/app/api/rotas/central_pendencias.py': ['78e947cb062b81cc6af4ba40d261d9bbaefb440fec11d01171d9e5ba09a12cc7'], 'backend/app/schemas/central_pendencias.py': ['7326f459a0a70cd54048620e464731ea53cb4a4a17cd03450a49a52e53e08711'], 'backend/app/services/central_pendencias.py': ['1865833db3b34606b869ef8eb9b1fe32ad0c52aa4337a8fc015734d256296963'], 'frontend/src/pages/pendencias/CentralPendencias.css': ['f7faf8ed21d8660e06a25921b8636824f7e4613f6382419a084c8b7712cace80'], 'frontend/src/pages/pendencias/CentralPendenciasPage.tsx': ['f72bb5826fd226903e7be0788d2dcfe91e4b62db109d366506e232b1d720867c'], 'frontend/src/pages/pendencias/pendenciasPortal.ts': ['93b74cc9d977c80f6b77bc237fa281c254f6e233d3b4bcec9e083d3a9b55cbe4'], 'tests/test_central_pendencias_d37.py': ['a476ed08c728ddd3fcc405f305e9a58c32e3559e8265a00ae55a0079500f5d47'], 'D38_CONTRATO_RESUMO_GERENCIAL.txt': ['346685fa01bd3721879f7aff20cdc51665c979a9e5aa3d4153b7c037d2536622'], 'backend/app/api/rotas/resumo_gerencial.py': ['66cd246932992d32fbd12f9e67ed5178d7f79c15f9e58464c53d6b72b24f7df2'], 'backend/app/schemas/resumo_gerencial.py': ['aa51ebaaae32057c7e3779616eafdf2187a4874ae9738c36cb95b19beb0c4108'], 'backend/app/services/resumo_gerencial.py': ['0bbae5c14ed90e6722975181615ccc8dea76240616f81f1d1827f967a68700ca'], 'frontend/src/pages/gerencial/ResumoGerencial.css': ['6f79a62aaa42ab830c8a4bc6bc9d31beea3f6c535660ddcf15b2f1fb1f35dfc4'], 'frontend/src/pages/gerencial/ResumoGerencialPage.tsx': ['ffee2d228632e804024fa109d20c39bf6dec6abee05ac2e2344415bdc4bb32db'], 'frontend/src/pages/gerencial/gerencialPortal.ts': ['fe6c0ec330f0382fb014b3844bf0402fb6edb8e1b973ce7a2d8d4614f3b8de5a'], 'tests/test_resumo_gerencial_d38.py': ['49b35f87181bcf9e244f716b8c477eeb94c2397cbf214f5644425b906748f22f'], 'D38_FIX1_VER_MES_VISIVEL.txt': ['2391ed33d03302cdfd92171d9475274137d7b4e395c1bf899e24f6c403d5a705'], 'D39_CONTRATO_COMPARATIVO_GERENCIAL.txt': ['6a11efb401c00060a517510397edd6d6573621c1a6c65232b32eb781cf052efd'], 'backend/app/api/rotas/comparativo_gerencial.py': ['e4d7059ba75fc9d7f2ccbe750409675387746d62d6bd1a660c704956e0a6a605'], 'backend/app/schemas/comparativo_gerencial.py': ['e0c13912101874f2dc33912dea785992fd5e0e3949e4847eeb058a695ed01851'], 'backend/app/services/comparativo_gerencial.py': ['924072496b95bfa6ad235791cdf20d34a6075a67e55f3e886ae391f795106001'], 'frontend/src/pages/comparativo/ComparativoGerencial.css': ['969607ede26920ab36a78a6f7b422fb3de3d7ecc5f655cccc2baafe7c8388229'], 'frontend/src/pages/comparativo/ComparativoGerencialPage.tsx': ['34f149d93ee48562d1a6f42f313db422aaf80c7a89fd0b21e06c1078626e6887'], 'frontend/src/pages/comparativo/comparativoPortal.ts': ['654292aef1729e1449a58d54e6a9d830ccf78aac3321798c6098fd3d2bb9aeda'], 'tests/test_comparativo_gerencial_d39.py': ['fb5d10189e887ddbcc6068d05583ea98f2b10aa883b51d6490dd9c6f5ad55764'], 'D40_CONTRATO_EXTRATO_FINANCEIRO.txt': ['be535b740022b1bbaee6cf2287681762ebdf942fe4645b2027c111e0f601496a'], 'backend/app/api/rotas/extrato_financeiro.py': ['48c15f895665057302c4770e2500ec16d0e3cec664f8ca66e67469ae214543ee'], 'backend/app/schemas/extrato_financeiro.py': ['b2728c060f3c95dd4c793b314bf0605fd3fd6a226a6cdb25d90237cb5c3b4e24'], 'backend/app/services/extrato_financeiro.py': ['1bd9476755156adbfcaa8606443fa0c8d8c3a3fc57775f74ffe5a427f5e3fdcf'], 'frontend/src/pages/extrato/ExtratoFinanceiro.css': ['0a0284f29ca75a05d60e60c73eafbbc59f0262ac311f1e915f4cb5d3a1419bd9'], 'frontend/src/pages/extrato/ExtratoFinanceiroPage.tsx': ['aefb8802f6db300c8ec328f02097b988559f387a13c596a1694acb9592e56480'], 'frontend/src/pages/extrato/extratoPortal.ts': ['fe04c26177109b4346c563db25be32c49c41dd020c3ca5c0703df682a52a3c86'], 'tests/test_extrato_financeiro_d40.py': ['c9fb8d4172c45c6772659c2e4af0cfe5e406d6d0d9cd02ac1bc87e3c8296576c'], 'backend/app/api/rotas/portal_fornecedor.py': ['3821c6c2956cadd061fcdbbc3bccd056b58c3fd6a146b8ac6bce81380fbaf222'], 'backend/app/services/cotacao.py': ['d9b40d6df27a1d1e90fb446f486cdc7fb68f5a5bc37a92314ee94c8ffc6cd8ac'], 'backend/app/services/portal_fornecedor.py': ['99234f6e655332848eafce7b6941f02b6e987012290a37143a67ea9f18c42a94'], 'frontend/src/pages/supplier/SupplierCotacoesPage.tsx': ['bfbade69cf66263289f4efb86aa82ccb07a51ead1bedd157f434cd15cf41f741'], 'frontend/src/pages/supplier/cotacoesFornecedor.ts': ['13891d5297b62026cd72276d48f0a4a9f9813377bc3b7d189bca267124c2a5d3'], 'tests/test_acesso_d30.py': ['349a44f5b78b671fdea714afea5e36fe2311b5d9617cde487bf4a0df831716ee'], 'tests/test_cotacoes.py': ['a716b81c44d813d2c571686afca8e242159887c5cb7be320db8ce337510c0153'], 'tests/test_portal_fornecedor_cotacoes.py': ['f6b7976a14174ed72ea9ceb36f418c805a224856e90ab9080653bc3dbf5dcb32'], 'D42_CONTRATO_DOCUMENTACAO_COTACAO.txt': ['caeac8ef1a6db9bd02795367e0920d2b2a3ea2517ceae99c4f339480c089f9c4'], 'backend/app/api/rotas/documentacao_cotacao.py': ['c939a6604b29ba261f0c7423920693e53ce74be7448b670585a482a48bb1d8b7'], 'backend/app/models/documentacao_cotacao.py': ['66f4c3b0b8732321508dfd884e6daf6ae2263f94a4fcd50d7d3b48e7362c6682'], 'backend/app/schemas/documentacao_cotacao.py': ['155d09636e46849e50ee91f6fed815d7e3171ed5a8e2dd6c46ec57ccb24e8324'], 'backend/app/services/documentacao_cotacao.py': ['419fa116af4f022abb6537da2d66c79e314ca87933cfbd9469dbbd9923721ad8'], 'frontend/src/pages/documentacao/AdminDocumentacaoPage.tsx': ['9dbe827d0a093b93236f21f57d99ddcfab46a72f792ccec4036debf815a0dfac'], 'frontend/src/pages/documentacao/Documentacao.css': ['41110bc417dfeee06b96f926e91f6d5ce8bf2b235d0754da0c67397ca6315bb2'], 'tests/apoio_documentacao_d42.py': ['253114528d5753b93ebdbb1b40c391f027dd93770bae7b1eedceeaf5a481f5f2'], 'tests/test_documentacao_cotacao_d42.py': ['6ba4ad4c0196b4d45e1d0d1291d1a11a9dc54477f0010cc114b6ddee3e65b8a6'], 'D42_FIX1_COMPATIBILIDADE_MODELOS.txt': ['8f1d4ffa3700888e2c2e46382cdc119dc2bc555ff7f22aebf71ad6e3d033cef0'], 'D42_FIX2_COMPATIBILIDADE_BASE_LOCAL.txt': ['aa58c58da6528cb257996a5684ea5a492474a20c82d730cb4f2cb2c0592c660c'], 'D43_CONTRATO_COMERCIAL_ADMIN.txt': ['625bdd44b10eae8a52620e1f5de21d1d0a5d91f017b96e7c1ac46cf36272abd6'], 'backend/app/api/rotas/comercial_admin.py': ['65fee9ae4bbb055d227b816733a65530c175cafa52a4e357602a11080f390c0d'], 'backend/app/models/comercial_admin.py': ['9cafd943786e78460506f7fd81a3b2926fc7ee556c526e3109cf6f14642bd94f'], 'backend/app/schemas/comercial_admin.py': ['5615f49549c69be1f57bbe145c878c4fd02055a72a743dc4d94608761af52163'], 'backend/app/services/comercial_admin.py': ['783a206e54497ec02f298de2b8c07e7731c3106834585d6ed39bc4f120e8cf76'], 'frontend/src/pages/comercial/AdminComercialPage.tsx': ['99a82e7abc165817a21c575e15ba11e37f279cc98bfb44e8aba8433d5dfe4c64'], 'frontend/src/pages/comercial/ComercialAdmin.css': ['af27a1751e19b79a6a7cd38620c938e796101e72d3f10f4deabe460e2b551ac0'], 'tests/test_comercial_administrativo_d43.py': ['97324f42108bb8f52b66b15d6398bcec714065a5d96c2fccf8811f4ec75948eb'], 'backend/app/services/contratacao.py': ['5c310b91e1617face5022eeb0a44551f22136fcbe4c6d9375ebdb02ab0249a53'], 'backend/app/services/ordem_servico.py': ['f4800b8d033b32487bd1399ea8a5212cf51f1915d0ee7dd51b778cecb6170691'], 'D44_CONTRATO_CONTRATACAO_ADMIN.txt': ['66b1fea843f3e73bde865f97cc48d36a136af8631f5c12e2dc2ddee7656d6396'], 'backend/app/api/rotas/contratacao_admin.py': ['a488492f278fe4dc724bdcef4f1e9cae15335f3a57ac53ba5e987ef212d05f65'], 'backend/app/models/contratacao_admin.py': ['7c2ad9aab2781463bf91967edc7a5873644c0c6d23a053b002208e6470859023'], 'backend/app/schemas/contratacao_admin.py': ['ebf59d99669bd04ff731d1ae68c204f2e672b86dd43663be5302de3287b0ede8'], 'backend/app/services/contratacao_admin.py': ['0cc6e7a9f52863b38b57af719d00d15af953557e1129f6201a59e35ae0bff1a0'], 'frontend/src/pages/contratacao-admin/AdminContratacaoPage.tsx': ['3df0bb0862257abfbbf9408d9feb4ae87a7e47da0f7b14d377fb46f72918c83c'], 'tests/test_contratacao_administrativa_d44.py': ['13ac4e8e0d116dd25d097a2e906899c8604172a62fb5fa7dca42e50b3c16a3f5'], 'backend/app/services/portal_ordens_servico.py': ['9974a8943bcc6ba97c8deff0380255bca88bfdfb7c9901a3806b747e0ee53250'], 'frontend/src/pages/entregas/PortalEntregasPage.tsx': ['f084917c40cd93ae45bd2dc1d85084362b06da77e592eaf3fe32ca97530de057'], 'frontend/src/pages/producao/PortalProducaoPage.tsx': ['a36530fc8debc941ca12d99b62a73d2d1672b1666cefb752e9a4f2a18be11346'], 'D45_CONTRATO_NOTIFICACOES_PERFIS.txt': ['d25b6e43e0f510877b7ff4fbb43cb65281d4509a162bc2cf2a727c22902d2c52'], 'backend/app/api/rotas/notificacoes.py': ['f6af42f8154c50a795fa9d97809ed8c80c98e585b0d9c4259e777afae1d1604b'], 'backend/app/models/notificacao.py': ['dede9ef5ccbe90a0d9d342822fc9408693a03fb8536f317004a365ace099d916'], 'backend/app/schemas/notificacao.py': ['178458a3f5c1663f50cff447f438fa8b8b47578dd780374860e21549adb512a5'], 'backend/app/services/eventos_notificacoes.py': ['632f980a88d25fd2ad2923b9875f94804d8b957947ec36cc914e43b012675317'], 'backend/app/services/notificacoes.py': ['7b4c1fdfc4876fc34125c1f62f72ac4a929ed0f42c88fd8d3ce9f7f60290598b'], 'frontend/src/components/notificacoes/CentroNotificacoes.tsx': ['e67bef0b8804907b5a0885808fc76da6e8a44958f58d70209bcda447b90a7c12'], 'frontend/src/components/notificacoes/Notificacoes.css': ['1640d489b9c4603566aa2c1c0ebe7dbfa1384feb19aa0b2fd83e96455956b336'], 'tests/test_notificacoes_d45.py': ['3cf1f52e9f60695d3867388b43037d4eff4399b6e6614ac463c95e6b20e48e47'], 'backend/app/services/avaliacao.py': ['0d01b31a469b9e6def65e7377d034c6c35b2c57bd0577ec5d1921ef7bda819bb'], 'D46_CONTRATO_AVALIACOES_PERFIS.txt': ['781978fc764e582278340bb92753c25677dc0d587d70e34bb25ce48333f1cc7e'], 'backend/app/api/rotas/avaliacoes_perfis.py': ['ba14f36184a6a6a85a5ce6a987562df9c1fc088d8a0a9c2768bdc12b0fcfb26c'], 'backend/app/models/avaliacao_perfil.py': ['6a12d6082a478b1462ece24eed4f138784f5dbbe6d2c86285fc62dfbb0d8eea7'], 'backend/app/schemas/avaliacao_perfil.py': ['e0ca6db0af205499337c055956806cec997dee24c95fa6f68620ef1a662f59e8'], 'backend/app/services/avaliacoes_perfis.py': ['04a4c4c295eec76df4dee6f74a8c30b7ed41dca03b93cd49b3496c8f61ca858c'], 'frontend/src/pages/avaliacoes/Avaliacoes.css': ['a9021a11dfa5a323f266e0a076f03069c3f4eb1d163cc1a38ce09749f3e0e9f2'], 'frontend/src/pages/avaliacoes/AvaliacoesPage.tsx': ['293a7d9a003ffaa749609a4f4c680b856b18e9dbfc79ea68de6731f3a3f73359'], 'frontend/src/pages/avaliacoes/RankingAvaliacoesPage.tsx': ['77aa3c854ed0384ce0b5fdee020d478d1f01d19c5486a7a59862ac1ec7fe4e34'], 'frontend/src/pages/avaliacoes/avaliacoesPortal.ts': ['450f99c8ba8986f4686353d6a4a6956116c6abfe352e20de6ec7e2046727ecaa'], 'tests/test_avaliacoes_perfis_d46.py': ['f7162ce6063c4fcdf83af6c13ca470cd2aa7f6083602f33cf230b4493466fafd'], 'D46_FIX1_CONTRATO_RANKING_PRIVADO.txt': ['d9e33131f32680a97bb953d688c0575981e81e225fa5baded5655840989ef79d'], 'frontend/src/auth/PortalSemRanking.css': ['4aecb3fc37d014eabf8bc322f235b118238e7863b888429cafc87955eca31cbc'], 'frontend/src/auth/PortalSemRanking.tsx': ['0c7c7b8f57681bd496055b4dd946857956762d81935dd50f32bda5273667133e'], 'tests/test_ranking_privado_d46_fix1.py': ['f03b3f48d2656f5e3fae55b831eec2b0acd410c9a2aac61435c84181f0641392'], 'D47_CONTRATO_COMPARACAO_COTACOES.txt': ['3e8f1b0ccd6b8e2ef9e7f827f50b5bdac685bafc4bbe0ded2983ed6fe375a172'], 'tests/test_comparacao_cotacoes_d47.py': ['9d47e4f944abfebb220bb14a3dba6978fd189472112b5214bd3c0d5844fa2308'], 'backend/app/schemas/comparacao_cotacoes_admin.py': ['e663f38decdffe44fba854123df80972246eed177f55980708b3a77864b8d24f'], 'backend/app/services/comparacao_cotacoes_admin.py': ['2270592edcc03a8c47a03b65558a03522244a18ad9c9843e86648c7dfd88630a'], 'frontend/src/pages/comercial/ComparacaoCotacoesAdmin.css': ['70baac1d41474b6174a941b7e29ba7139075bf5b570a8f50dcb19b88fe485a2c'], 'frontend/src/pages/comercial/ComparacaoCotacoesAdmin.tsx': ['b66b74199d788c8b3091509a1feb7f77e61d2798ae1d8f93388eda19282f16a3'], 'D47_FIX1_CONTRATO_CONTRASTE_COMPARACAO.txt': ['c85a3cc6c6673898fc2c4d8ab5c3b1846f3e947db4a914113962866e706856f5'], 'D48_CONTRATO_PREPARACAO_PDF_COTACAO.txt': ['f1343071b629335e62b0a993fe254dee61c194c3877bba36d267bc8348abdf32'], 'requirements_pdf_d48.txt': ['fbc536fb745cb55cde440d6df7af508484df0823b340d766745cee82f0da0f13'], 'tests/test_preparacao_pdf_d48.py': ['e9fcd2a0f3712779b0de706983ae573f0b993bfd66f11b2793f3c8866d777803'], 'backend/app/schemas/preparacao_pdf.py': ['373e8c28dfc74b4405a6c50fbffd3458304ef5fe3143331bc1f75474cfaf316b'], 'backend/app/models/preparacao_pdf.py': ['9821621d9eb79979ed02e93d96b12b453d43afed22df92fa3fa466f317e2ddc9'], 'backend/app/services/preparacao_pdf.py': ['34f66fadc7c490a346b924051f4ce8338398b769fed2712ec2bfb7e9913580dd'], 'backend/app/services/motor_pdf_cotacao.py': ['0e6d701ff1eb1cc5e421cb404e38b9bf243ea61f6b20374d3a788e883540436a'], 'backend/app/api/rotas/preparacao_pdf.py': ['3fe59dbd5f928afca93c454fb8d44a4da6bfbf10d13bf02805763e43b64827f8'], 'frontend/src/pages/documentacao/PrepararPdfAdmin.tsx': ['543e8727a7680f3b3d651e87ee77ada64d076eb553adec41cf1128ccbd06ee1f'], 'frontend/src/pages/documentacao/PreparacaoPdf.css': ['408fcb0c68d194a0c2e3bd67e525e0effa289a9e8b0c0d546db3d5f431ec91cd'], 'backend/app/assets/mec_logo_pdf.png': ['bfd839a02bbbb72a405a2c2c6f2c4f9339b4de9de16cceb540d3afd2e3cb63a2'], 'D48_FIX1_CONTRATO_ABERTURA_PREPARACAO_PDF.txt': ['33f378bb090e47cb6b096233e8bac6447f3db3e2920331eb45059294a30df0d2'], 'tests/test_carimbo_compacto_d48_fix2.py': ['232827d35742400c39b1bab593f7c5c84cd4d833f4e748ed7d34c03b1598381f'], 'D48_FIX2_CONTRATO_CARIMBO_COMPACTO.txt': ['14fcb0466e8c809e1240010e3511bdb93cd93c4e040acd0545f085d8f0666752'], 'tests/test_preservacao_desenho_d48_fix3.py': ['05b8ed2d686c1995882249a72ed0690367b4c00880b9c1126d734e174471bbdc'], 'D48_FIX3_CONTRATO_PRESERVACAO_DESENHO.txt': ['3650de340dcf8fd17c577f16843695d43b56453326fe2e8720ba30d24d387a4a'], 'tests/test_escopo_usinagem_d49.py': ['fdbcfa03ba73a45bf53ef4b680f0c7ba656b94b6c2296fd9e2f5f7b1a07f8052'], 'D49_CONTRATO_ESCOPO_USINAGEM.txt': ['e84e736c1d9d78ac2e8fbf0aa272d8d4752c3b03179a8378f1829382ba6e618a'], 'backend/app/models/historico_campos_pdf.py': ['e8f93a921b65847b30a75e95d04edf50d87ac60cd7acf3ac0930be40ca2de578'], 'backend/app/schemas/historico_campos_pdf.py': ['f8a74b630670b61ee0c16d94c8ffe5a66d3c3c3c8a469bf8af8a4fcd53ba574c'], 'backend/app/services/historico_campos_pdf.py': ['7622f89427419ab6901e424b3c853235034aa3db51c66ddec7f3ffd486628e42'], 'frontend/src/pages/documentacao/CampoPdfComHistorico.tsx': ['d741313040a2fdb23fe0caf269a627e254ca7d8469387f4c76581904a186c73c'], 'tests/test_historico_campos_pdf_d50.py': ['b603973c2ccbc61d3f291af36f3b8a2d902520f6bcebb46101dd959266787e10'], 'D50_CONTRATO_HISTORICO_CAMPOS_PDF.txt': ['4f63851cc8a6c1c9b4d2263fd698084db2e89065a6a95e1ce380657192828f05'], 'backend/app/schemas/operacoes_pdf.py': ['a8f046cf45851172a4a151b6be0786e8d675131e017901628efb397d8ac5c672'], 'frontend/src/pages/documentacao/CatalogoCamposPdf.ts': ['c5fad081fa9561af6df5b0d3f9cfc0386c782c4f1548743cbfb296c14fcad544'], 'frontend/src/pages/documentacao/OperacoesServicoPdf.tsx': ['0f096939174c44e28972142cab19937bbf671a3bbab4d7c5f1b2cef639d15e9c'], 'tests/test_catalogo_servicos_pdf_d51.py': ['88b8f12fe042e5dde4e929a41532dd592fdafd17a278784bb85bb2498e7306b7'], 'D51_CONTRATO_CATALOGO_MATERIAIS_SERVICOS_PDF.txt': ['f5d5c3cea9535882f98aed04d814a2323133ebad4a34313a9ecd2594bcdf9f0a'], 'backend/app/models/operacao_empresa.py': ['e66553844339d94b9c7672e3366f3a93a5c6761c25107b1d6b0fe6d67fe5e299'], 'backend/app/schemas/empresas_operacoes.py': ['f8dbd574c86923c183612fbe35889dc1289efed9d8603798e0ede2746c8bbfcd'], 'backend/app/services/catalogo_operacoes_empresa.py': ['9d7857d92324063b408a68cafd0722689c3c226cb6c59e901393daeaf805f31f'], 'backend/app/services/empresas_operacoes.py': ['a69d9ca9bdef7788f3cdd4cdcdeade1cd41ae7535cd6c9bf2f82334b50dcc892'], 'backend/app/api/rotas/empresas_operacoes.py': ['9073a79bb5fa7bb9e982cad75ecadf6fc628bc7c2a1bb3ac639f2f51db6fa1c1'], 'frontend/src/pages/empresas/EmpresasOperacoesPage.tsx': ['d61caef8d769359e2b9e5ac3eb65396849d4ffdbbb2dfc8e773d699414702124'], 'frontend/src/pages/empresas/EmpresasOperacoes.css': ['6a09dcda9551913fc3c7408ea7dd52b70d218b14bb64d4786baad376a735acd2'], 'tests/test_empresas_operacoes_d52.py': ['d03fab5d14323a8e67135b8e13fd545bd75204a77c75affd3caab494bf9f9abf'], 'D52_CONTRATO_EMPRESAS_OPERACOES.txt': ['242170d0afe3657cae18ca107a949db5a0924c2cd5fe5addf863caaa246ed33e'], 'backend/app/services/catalogo_materiais_empresa.py': ['ff4596134634b075ad42c7560d72802f80d8e816a55d90f589462aff573a4b55'], 'tests/test_materiais_empresa_d52_fix1.py': ['fee4ba3ec608d0021f8a72ba9b1da00ad08a5b2e86770a4699c0f220d61b2aef'], 'D52_FIX1_CONTRATO_MATERIAIS_EMPRESA.txt': ['5d7a4e0b539d170556443e7c63c98cc33c44fc4c6bf86b5a41a5d0bcc2b870dc']}

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

D46_REVISION = 'MEC-SERVICOS-V0.1-D52-FIX1-MATERIAIS-EMPRESA-2026-10-09'

D46_RELATORIO = 'MEC_SERVICOS_V0_1_D52_FIX1_MATERIAIS_EMPRESA_RELATORIO.json'

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
    raise RuntimeError("A porta 8000 está em uso. Pare o backend com Ctrl+C no terminal dele antes de executar a D53.")

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
            raise RuntimeError("Fonte diferente da base D52 FIX1 conhecida; preservado: " + nome)
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

def conferir_base_d52_fix1(raiz, banco):
    arquivo = seguro(raiz, D46_RELATORIO)
    if not arquivo.is_file(): raise RuntimeError("Relatório D52 FIX1 não encontrado. Conclua Materiais aceitos pela empresa antes da D53.")
    dados = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    if (not isinstance(dados, dict) or dados.get("resultado") != "OK" or dados.get("revision") != D46_REVISION or
            dados.get("validacao_backend_e_frontend") is not True or dados.get("ranking_exclusivo_administracao") is not True or dados.get("contraste_comparacao_corrigido") is not True or dados.get("originais_preservados") is not True or dados.get("preparacao_pdf_exclusiva_administracao") is not True or dados.get("abertura_preparacao_pdf_corrigida") is not True or dados.get("carimbo_compacto_disponivel") is not True or dados.get("preservacao_transformacoes_corrigida") is not True or dados.get("comparacao_visual_pdf_ativa") is not True or dados.get("escopo_usinagem_disponivel") is not True or dados.get("idempotencia_pedidos_d48_preservada") is not True or dados.get("historico_campos_pdf_disponivel") is not True or dados.get("setinhas_campos_pdf_disponiveis") is not True or dados.get("historico_pdf_por_administrador") is not True or dados.get("catalogo_materiais_pdf_disponivel") is not True or dados.get("operacoes_servico_pdf_disponiveis") is not True or dados.get("historico_d50_preservado") is not True or dados.get("cadastro_empresas_operacoes_disponivel") is not True or dados.get("operacoes_por_empresa_disponiveis") is not True or dados.get("capacidades_tecnicas_anteriores_preservadas") is not True or dados.get("catalogo_materiais_empresa_disponivel") is not True or dados.get("material_proprio_empresa_disponivel") is not True or dados.get("historico_d52_preservado") is not True):
        raise RuntimeError("Conclua a D52 FIX1 antes de aplicar a D53.")
    with closing(sqlite3.connect(banco.as_uri()+"?mode=ro", uri=True)) as conexao:
        conexao.execute("PRAGMA query_only=ON"); conexao.execute("BEGIN")
        if not all((conferir_schema(conexao), conferir_schema_d32(conexao), conferir_schema_d42(conexao),
                    conferir_schema_d43(conexao), conferir_schema_d44(conexao), conferir_schema_d45(conexao),
                    conferir_schema_d46(conexao))):
            raise RuntimeError("Tabelas da base D48 não confirmadas; banco preservado.")
        if not conferir_schema_d48(conexao): raise RuntimeError("Tabelas D48 ausentes; banco preservado.")
        if not conferir_schema_d50(conexao): raise RuntimeError("Tabela do histórico D50 ausente; banco preservado.")
        if not conferir_schema_d52(conexao): raise RuntimeError("Tabela de operações D52 ausente; banco preservado.")
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
    print("MEC-Serviços D53 — Gráfico do ranking administrativo", flush=True)
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
        os.chdir(raiz); banco, acesso = configuracao_bancos(raiz); conferir_base_d52_fix1(raiz, banco)
        negocio_antes = ler_historico(banco); contas_antes = ler_historico(acesso)
        print("BASE_D52_FIX1_CONFIRMADA=True", flush=True)
        print("REGISTRO_MODELOS_EXISTENTE_PRESERVADO=True", flush=True)
        print("PAGINA_ARQUIVOS_CLIENTE_PRESERVADA=True", flush=True)
        print("REGISTRO_TESTES_LOCAL_PRESERVADO=True", flush=True)
        relatorio["etapa"] = "backup"
        backup = seguro(raiz, "_mec_backups/D53_GRAFICO_RANKING_ADMIN_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
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
        print("ARQUIVOS_D53_APLICADOS=" + str(len(plano)), flush=True)
        print("TESTES_SELETIVOS_AVALIACOES_RANKING=True", flush=True)
        print("SUITE_COMPLETA_D48_REEXECUTADA=False", flush=True)
        relatorio["etapa"] = "validar_avaliacoes_ranking"
        with tempfile.TemporaryDirectory(prefix="mec_d53_testes_") as pasta:
            ambiente = dict(os.environ)
            ambiente.update(MEC_URL_BANCO_DADOS="sqlite:///" + (Path(pasta) / "negocio.db").resolve().as_posix(),
                MEC_ACESSOS_DB=str(Path(pasta) / "acesso.db"), MEC_MODO_TESTE_LOCAL="0",
                MEC_AMBIENTE="teste", MEC_COOKIE_SEGURO="0", PYTEST_ADDOPTS="")
            executar(raiz, "pytest", [sys.executable, "-u", "-m", "pytest", "-vv", "-o", "addopts=",
                "tests/test_ranking_privado_d46_fix1.py", "tests/test_avaliacoes_perfis_d46.py", "tests/test_ranking_fornecedores.py", "tests/test_acesso_d30.py::test_rotas_da_aplicacao_exigem_sessao_real", "tests/test_acesso_d30.py::test_cookie_falso_e_cabecalho_de_perfil_nao_autorizam", "--durations=5"], ambiente, relatorio)
            relatorio["pytest"].update(executado=True, seletivo=True,
                arquivos=["tests/test_ranking_privado_d46_fix1.py", "tests/test_avaliacoes_perfis_d46.py", "tests/test_ranking_fornecedores.py", "tests/test_acesso_d30.py::test_rotas_da_aplicacao_exigem_sessao_real", "tests/test_acesso_d30.py::test_cookie_falso_e_cabecalho_de_perfil_nao_autorizam"])
            relatorio["etapa"] = "validar_frontend"
            build_iniciado = True
            executar(raiz / "frontend", "npm_build", [npm, "run", "build"], ambiente, relatorio)
        relatorio["etapa"] = "conferir_preservacao"
        conferir_base_d52_fix1(raiz, banco)
        if ler_historico(banco) != negocio_antes: raise RuntimeError("Banco mudou durante a validação; registros externos preservados.")
        if ler_historico(acesso) != contas_antes: raise RuntimeError("Banco de acesso mudou durante a validação; contas preservadas.")
        if plano_arquivos(raiz): raise RuntimeError("Fontes da correção divergiram após o build.")
        criadas = 0
        relatorio["tabelas_criadas"] = criadas
        concluido = True
        relatorio.update(resultado="OK", etapa="concluido", arquivos_alterados=alterados,
            grafico_ranking_admin_disponivel=True, grafico_ranking_exclusivo_administracao=True, ranking_notas_origens_separadas=True, ranking_todas_empresas_paginado=True, escala_maxima_grafico=5, novas_bibliotecas_frontend_instaladas=False, historico_d52_fix1_preservado=True, catalogo_materiais_empresa_disponivel=True, materiais_prontos_empresa=50, material_proprio_empresa_disponivel=True, materiais_cadastrados_automaticamente=False, historico_d52_preservado=True, cadastro_empresas_operacoes_disponivel=True, operacoes_por_empresa_disponiveis=True, capacidades_tecnicas_anteriores_preservadas=True, operacoes_automaticas_atribuidas=False, limite_operacoes_por_empresa=200, historico_d51_preservado=True, historico_negocio_preservado=True, historico_financeiro_d32_preservado=True, historico_administrativo_d33_preservado=True, relatorio_d34_preservado=True, relatorio_d35_preservado=True, relatorio_d36_preservado=True, central_d37_preservada=True, resumo_gerencial_d38_preservado=True, resumo_gerencial_d38_fix1_preservado=True, comparativo_gerencial_d39_preservado=True, contas_e_senhas_preservadas=True, cotacoes_anteriores_preservadas=True, liberacoes_automaticas_executadas=False, validacao_backend_e_frontend=True, documentacao_e_historico_d42_preservados=True, decisoes_automaticas_executadas=False, historico_comercial_d43_preservado=True, contratacoes_automaticas_executadas=False, ordens_automaticas_executadas=False, historico_contratacao_d44_preservado=True, notificacoes_historicas_geradas=False, avaliacoes_automaticas_geradas=False, ranking_exclusivo_administracao=True, comparacao_exclusiva_administracao=True, contraste_comparacao_corrigido=True, originais_preservados=True, abertura_preparacao_pdf_corrigida=True, catalogo_materiais_pdf_disponivel=True, operacoes_servico_pdf_disponiveis=True, materiais_prontos_pdf=50, operacoes_prontas_pdf=30, limite_operacoes_por_pagina=8, selecao_operacoes_automatica=False, historico_d50_preservado=True, cadastros_capacidades_preservados=True, idempotencia_pedidos_d50_preservada=True, historico_campos_pdf_disponivel=True, setinhas_campos_pdf_disponiveis=True, historico_pdf_por_administrador=True, historico_pdf_anterior_reutilizado=True, escopo_usinagem_disponivel=True, tolerancias_gerais_opcionais=True, sobremetal_automatico_informado=False, idempotencia_pedidos_d48_preservada=True, validacao_integral_d48_reutilizada=True, carimbo_compacto_disponivel=True, preservacao_transformacoes_corrigida=True, comparacao_visual_pdf_ativa=True, regravacao_objetos_pdfium_executada=False, suite_completa_d48_reexecutada=False, preparacoes_e_publicacoes_pdf_preservadas=True, preparacao_pdf_exclusiva_administracao=True, preparacoes_automaticas_executadas=False, avaliacoes_anteriores_preservadas=True, notificacoes_e_leituras_d45_preservadas=True,
            historico_negocio_sha256=negocio_antes, historico_acesso_sha256=contas_antes)
        print("TABELAS_D53_CRIADAS=0", flush=True)
        print("GRAFICO_RANKING_ADMIN_DISPONIVEL=True", flush=True)
        print("RANKING_EXCLUSIVO_ADMINISTRACAO=True", flush=True)
        print("NOTAS_CLIENTE_E_ADMIN_SEPARADAS=True", flush=True)
        print("AVALIACOES_ANTERIORES_PRESERVADAS=True", flush=True)
        print("HISTORICO_D52_FIX1_PRESERVADO=True", flush=True)
        print("HISTORICO_NEGOCIO_PRESERVADO=True", flush=True)
        print("CONTAS_E_SENHAS_PRESERVADAS=True", flush=True)
        try: salvar_relatorio(raiz, relatorio)
        except OSError: print("RELATORIO_NAO_GRAVADO=True; preserve a saída do terminal.", flush=True)
        print("RESULTADO=OK", flush=True)
        print("Reinicie o teste local e atualize com Ctrl+F5. Abra Administração > Avaliações > Ver reputação e ranking (ou /admin/ranking).", flush=True)
        print("Confira as barras, posições, médias e quantidade de notas. Alterne a origem e confira a tabela. Cliente e fornecedor continuam sem acesso ao ranking.", flush=True)
        print("Roteiro local: D53_CONTRATO_GRAFICO_RANKING_ADMIN.txt", flush=True)
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

DDL_D50 = {'historico_campos_pdf': 'CREATE TABLE historico_campos_pdf (\n\tid INTEGER NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tcampo VARCHAR(32) NOT NULL, \n\tchave_valor VARCHAR(64) NOT NULL, \n\tvalor VARCHAR(180) NOT NULL, \n\tatualizado_em VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_historico_campo_pdf_valor UNIQUE (usuario_admin_id, campo, chave_valor), \n\tCONSTRAINT ck_historico_campo_pdf_usuario CHECK (usuario_admin_id > 0)\n)'}

INDICES_D50 = {'ix_historico_campo_pdf_usuario_data': 'CREATE INDEX ix_historico_campo_pdf_usuario_data ON historico_campos_pdf (usuario_admin_id, atualizado_em)'}

def conferir_schema_d50(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D50)
    if not presentes: return False
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D50, **INDICES_D50}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D50 divergente; banco preservado: " + nome)
    return True

DDL_D52 = {'operacoes_empresa': 'CREATE TABLE operacoes_empresa (\n\tid INTEGER NOT NULL, \n\tempresa_id INTEGER NOT NULL, \n\tprocesso_id INTEGER NOT NULL, \n\tativo BOOLEAN NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tatualizado_em VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_operacao_empresa_processo UNIQUE (empresa_id, processo_id), \n\tCONSTRAINT ck_operacao_empresa_admin CHECK (usuario_admin_id > 0), \n\tCONSTRAINT ck_operacao_empresa_ativo CHECK (ativo IN (0, 1)), \n\tFOREIGN KEY(empresa_id) REFERENCES empresas (id) ON DELETE CASCADE, \n\tFOREIGN KEY(processo_id) REFERENCES processos_fabricacao (id) ON DELETE RESTRICT\n)'}

INDICES_D52 = {'ix_operacoes_empresa_empresa_id': 'CREATE INDEX ix_operacoes_empresa_empresa_id ON operacoes_empresa (empresa_id)', 'ix_operacoes_empresa_processo_id': 'CREATE INDEX ix_operacoes_empresa_processo_id ON operacoes_empresa (processo_id)'}

def conferir_schema_d52(conexao):
    presentes = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")} & set(DDL_D52)
    if not presentes: return False
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in {**DDL_D52, **INDICES_D52}.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE name=?", (nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Estrutura D52 divergente; banco preservado: " + nome)
    return True

if __name__ == "__main__":
    raise SystemExit(main())
