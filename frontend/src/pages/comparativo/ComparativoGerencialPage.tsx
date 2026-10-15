import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeftRight, Download, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";
import { filtrosPainel, situacoesPainel, type FiltroPainel } from "../painel/painelPortal";
import { diaUTC } from "../periodo/periodoPortal";
import { camposDatas, datasValidas, linkPeriodoComparativo, mensagemComparativo, periodosPadrao,
  type ConsultaComparativo, type FiltrosComparativo, type PeriodoDetalhe, type ResumoPeriodoComparativo } from "./comparativoPortal";
import "../periodo/RelatorioPeriodo.css";
import "./ComparativoGerencial.css";

const LIMITE = 20;
function valor(texto: string, tipo: "quantidade" | "valor", sinal = false) {
  const formatado = tipo === "valor" ? dinheiro(texto) : Number(texto).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  return (sinal && Number(texto) > 0 ? "+ " : "") + formatado;
}
function variacao(texto: string | null) {
  return texto === null ? "Sem base" : (Number(texto) > 0 ? "+ " : "") +
    Number(texto).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "%";
}

export default function ComparativoGerencialPage() {
  const { user } = useAuth(); const [parametros, setParametros] = useSearchParams();
  const filtros = useMemo<FiltrosComparativo>(() => {
    const padrao = periodosPadrao(); const temDatas = camposDatas.some(c => parametros.has(c));
    return { a_inicial: temDatas ? parametros.get("a_inicial") ?? "" : padrao.a_inicial,
      a_final: temDatas ? parametros.get("a_final") ?? "" : padrao.a_final,
      b_inicial: temDatas ? parametros.get("b_inicial") ?? "" : padrao.b_inicial,
      b_final: temDatas ? parametros.get("b_final") ?? "" : padrao.b_final,
      filtro: (parametros.get("filtro") || "todas") as FiltroPainel, busca: parametros.get("busca") || "",
      periodo: (parametros.get("periodo") ?? null) as PeriodoDetalhe };
  }, [parametros]);
  const [rascunho, setRascunho] = useState(filtros);
  const [dados, setDados] = useState<ConsultaComparativo | null>(null);
  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(true); const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState(""); const [erroFormulario, setErroFormulario] = useState(""); const [aviso, setAviso] = useState("");
  const download = useRef<AbortController | null>(null);
  useEffect(() => { setRascunho(filtros); setDeslocamento(0); setErroFormulario(""); }, [filtros]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    download.current?.abort(); download.current = null;
    setDados(null); setErro(""); setAviso(""); setBaixando(false); setCarregando(true);
    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }
    void api.get<ConsultaComparativo>("/administracao/relatorios/comparativo", {
      params: { ...filtros, deslocamento, limite: LIMITE }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (!vigente) return;
      if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / LIMITE) * LIMITE); return; }
      setDados(data);
    }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemComparativo(falha)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); download.current?.abort(); };
  }, [filtros, deslocamento, revisao, user?.role]);

  function aplicar(novos: FiltrosComparativo) {
    const p: Record<string, string> = Object.fromEntries(camposDatas.map(c => [c, novos[c]]));
    if (novos.filtro !== "todas") p.filtro = novos.filtro;
    if (novos.busca) p.busca = novos.busca;
    if (novos.periodo) p.periodo = novos.periodo;
    setDeslocamento(0); setErroFormulario(""); setParametros(p); setRevisao(v => v + 1);
  }
  function consultar(e: FormEvent) {
    e.preventDefault();
    if (!datasValidas(rascunho)) { setErroFormulario("Preencha as quatro datas, com o início igual ou anterior ao fim em cada período."); return; }
    aplicar({ ...rascunho, busca: rascunho.busca.trim(), periodo: null });
  }
  async function exportar() {
    if (!dados || carregando || baixando || user?.role !== "admin") return;
    const controle = new AbortController(); download.current = controle; setBaixando(true); setAviso("");
    try {
      const resposta = await api.get<Blob>("/administracao/relatorios/comparativo/csv", { params: dados.filtros,
        responseType: "blob", signal: controle.signal, timeout: 30_000 });
      if (controle.signal.aborted) return;
      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");
      const url = URL.createObjectURL(resposta.data); const a = document.createElement("a");
      a.href = url; a.download = "MEC_SERVICOS_COMPARATIVO_GERENCIAL.csv";
      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com A, B, diferenças e todas as contratações de ambos os períodos."); }
      finally { a.remove(); URL.revokeObjectURL(url); }
    } catch (falha: unknown) { if (!controle.signal.aborted) setAviso(mensagemComparativo(falha)); }
    finally { if (download.current === controle) { download.current = null; setBaixando(false); } }
  }
  function inverter() {
    if (!dados) return;
    const f = dados.filtros;
    aplicar({ ...f, a_inicial: f.b_inicial, a_final: f.b_final, b_inicial: f.a_inicial, b_final: f.a_final, periodo: null });
  }
  function cartao(periodo: "a" | "b", r: ResumoPeriodoComparativo) {
    return <section className={`periodo35-card comparativo39-periodo comparativo39-periodo-${periodo}`}>
      <h2>Período {periodo.toUpperCase()} · {periodo === "a" ? "Base" : "Comparado"}</h2>
      <p>{diaUTC(r.data_inicial)} até {diaUTC(r.data_final)}</p>
      <p><strong>{r.indicadores.total_contratacoes}</strong> contratação(ões) · {r.indicadores.contratacoes_concluidas} concluída(s) · {r.contratacoes_com_pendencias} com pendências</p>
      <div className="comparativo39-valores"><div><span>Valor contratado</span><strong>{dinheiro(r.valor_contratado)}</strong></div>
        <div><span>Recebido confirmado</span><strong>{dinheiro(r.indicadores.recebimentos_confirmados)}</strong></div>
        <div><span>Repassado confirmado</span><strong>{dinheiro(r.indicadores.repasses_confirmados)}</strong></div></div>
      <nav aria-label={`Consultas do período ${periodo.toUpperCase()}`}>
        <button type="button" aria-pressed={dados?.filtros.periodo === periodo} onClick={() => dados && aplicar({ ...dados.filtros, periodo })}>Ver contratações de {periodo.toUpperCase()}</button>
        <Link to={linkPeriodoComparativo(dados!.filtros, periodo, "periodo")}>Relatório de {periodo.toUpperCase()}</Link>
        <Link to={linkPeriodoComparativo(dados!.filtros, periodo, "pendencias")}>Pendências de {periodo.toUpperCase()}</Link>
      </nav>
    </section>;
  }

  if (user?.role !== "admin") return <p role="alert">O comparativo está disponível somente para a administração.</p>;
  return <article className="periodo35 comparativo39">
    <header className="periodo35-cabecalho"><div><h1><ArrowLeftRight aria-hidden="true" /> Comparativo entre períodos</h1>
      <p>Compare as contratações de dois intervalos, com valores, situações e pendências atuais.</p></div>
      <nav><Link to="/admin">Voltar ao Dashboard</Link><Link to="/admin/resumo-gerencial">Resumo gerencial mensal</Link>
        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>
        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" /> {baixando ? "Exportando…" : "Exportar CSV"}</button></nav>
    </header>
    <section className="periodo35-card"><h2>Selecionar A e B</h2>
      <form className="periodo35-filtros comparativo39-filtros" onSubmit={consultar}>
        {(["a", "b"] as const).map(p => <fieldset key={p}><legend>Período {p.toUpperCase()} · {p === "a" ? "Base" : "Comparado"}</legend>
          <label>Início de {p.toUpperCase()} (UTC)<input type="date" required min="0001-01-01" max="9999-12-31" value={rascunho[`${p}_inicial`]} onChange={e => setRascunho(v => ({ ...v, [`${p}_inicial`]: e.target.value }))} /></label>
          <label>Fim de {p.toUpperCase()} (UTC)<input type="date" required min="0001-01-01" max="9999-12-31" value={rascunho[`${p}_final`]} onChange={e => setRascunho(v => ({ ...v, [`${p}_final`]: e.target.value }))} /></label>
        </fieldset>)}
        <div className="comparativo39-filtros-comuns"><label>Exibir<select value={rascunho.filtro} onChange={e => setRascunho(v => ({ ...v, filtro: e.target.value as FiltroPainel }))}>{Object.entries(filtrosPainel).map(([v, rotulo]) => <option key={v} value={v}>{rotulo}</option>)}</select></label>
          <label className="periodo35-busca">Buscar empresa, contratação ou OS<input type="search" maxLength={120} value={rascunho.busca} onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} placeholder="Ex.: oficina, Contratação #1 ou OS #3" /></label>
          <button type="submit" disabled={carregando}><Search size={16} aria-hidden="true" /> Consultar</button>
          <button type="button" disabled={carregando} onClick={() => aplicar(periodosPadrao())}>Limpar filtros</button>
        </div>
      </form>
      {erroFormulario && <p role="alert" className="periodo35-erro">{erroFormulario}</p>}
      <p className="periodo35-nota">Os períodos consideram a criação da contratação em UTC, incluindo o início e o fim. Valores, situações e pendências são atuais; recebimentos e repasses são acumulados dessas contratações.</p>
    </section>
    {aviso && <p role="status" className="periodo35-aviso">{aviso}</p>}
    {carregando ? <p role="status">Consultando o comparativo…</p> : erro ? <p role="alert" className="periodo35-erro">{erro}</p> : dados && <>
      <section className="periodo35-card comparativo39-aplicados"><p className="periodo35-aplicados">{filtrosPainel[dados.filtros.filtro]} · Busca: {dados.filtros.busca || "Todas"} · Detalhamento: {dados.filtros.periodo?.toUpperCase() || "Fechado"}</p>
        <p><strong>A:</strong> {diaUTC(dados.filtros.a_inicial)} até {diaUTC(dados.filtros.a_final)} · <strong>B:</strong> {diaUTC(dados.filtros.b_inicial)} até {diaUTC(dados.filtros.b_final)}</p>
        <button type="button" onClick={inverter}><ArrowLeftRight size={16} aria-hidden="true" /> Inverter A e B</button>
        {dados.periodos_sobrepostos && <p role="status" className="comparativo39-sobreposicao">Os períodos se sobrepõem: {dados.contratacoes_em_ambos} contratação(ões) presente(s) em ambos. Compare cada grupo separadamente.</p>}
        <small>Consultado em {dataFinanceiro(dados.gerado_em)}. O CSV consulta os dados atuais com os filtros aplicados.</small>
      </section>
      <div className="comparativo39-periodos">{cartao("a", dados.resumo_a)}{cartao("b", dados.resumo_b)}</div>
      <section className="periodo35-card comparativo39-medidas"><h2>Diferenças entre A e B</h2>
        <p>Diferença = B − A. Variação = (B − A) ÷ A × 100. O sinal indica aumento ou redução.</p>
        <div className="periodo35-scroll"><table><thead><tr><th>Indicador</th><th>Período A</th><th>Período B</th><th>Diferença (B − A)</th><th>Variação (%)</th></tr></thead>
          <tbody>{dados.medidas.map(m => <tr key={m.codigo} data-medida={m.codigo}><th scope="row">{m.descricao}</th><td>{valor(m.valor_a, m.tipo)}</td><td>{valor(m.valor_b, m.tipo)}</td>
            <td className="comparativo39-diferenca">{valor(m.diferenca, m.tipo, true)}</td><td>{variacao(m.variacao_percentual)}</td></tr>)}</tbody></table></div>
        <p className="periodo35-nota">Sem base: A é zero e B é diferente de zero. Se ambos são zero, a variação é 0,00%. Valores excluem estornos; saldos e disponibilidade consideram controles abertos. Ações e contratações com pendências são contagens distintas.</p>
      </section>
      {dados.filtros.periodo && <section className="periodo35-card comparativo39-detalhe"><header><h2>Contratações do período {dados.filtros.periodo.toUpperCase()}</h2>
        <button type="button" onClick={() => aplicar({ ...dados.filtros, periodo: null })}>Fechar detalhamento</button></header>
        <p>{dados.total} contratação(ões) · {diaUTC(dados.filtros[`${dados.filtros.periodo}_inicial`])} até {diaUTC(dados.filtros[`${dados.filtros.periodo}_final`])}</p>
        {!dados.total ? <p>Nenhuma contratação neste período para os filtros aplicados.</p> : <>
          <div className="periodo35-scroll"><table><thead><tr><th>Contratação / OS</th><th>Contratada em (UTC)</th><th>Cliente / fornecedor</th><th>Situação</th><th>Valor contratado</th><th>Recebido</th><th>Repassado</th><th>Consultar</th></tr></thead>
            <tbody>{dados.itens.map(c => <tr key={c.contratacao_id}><td><strong>Contratação #{c.contratacao_id}</strong><small>{c.ordem_servico_id ? `OS #${c.ordem_servico_id}` : "Sem OS"}</small></td><td>{diaUTC(c.contratada_em)}</td>
              <td>{c.cliente}<small>Cliente ID #{c.empresa_cliente_id}</small>{c.fornecedor}<small>Fornecedor ID #{c.empresa_fornecedora_id}</small></td>
              <td>{situacoesPainel[c.situacao]}<small>{estados[c.financeiro_status]}</small></td><td>{dinheiro(c.valor_contratado)}</td><td>{dinheiro(c.total_recebido)}</td><td>{dinheiro(c.total_repassado)}</td>
              <td><nav><Link to={`/admin/relatorios?contratacao=${c.contratacao_id}`}>Relatório #{c.contratacao_id}</Link><Link to={`/admin/pagamentos?contratacao=${c.contratacao_id}`}>Financeiro</Link>
                {c.pendencias.length > 0 && <Link to={"/admin/pendencias?busca=" + encodeURIComponent("Contratação #" + c.contratacao_id)}>Pendências</Link>}</nav></td>
            </tr>)}</tbody></table></div>
          <nav className="periodo35-paginacao comparativo39-paginacao" aria-label="Páginas das contratações do período"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total)} de {dados.total} contratações</span>
            <button type="button" disabled={!deslocamento || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button><button type="button" disabled={deslocamento + LIMITE >= dados.total || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></nav>
        </>}
      </section>}
    </>}
  </article>;
}
