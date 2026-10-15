import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarDays, Download, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";
import { filtrosPainel, situacoesPainel, type FiltroPainel } from "../painel/painelPortal";
import { diaUTC, mensagemPeriodo, type ConsultaPeriodo, type FiltrosPeriodo } from "./periodoPortal";
import "./RelatorioPeriodo.css";

const LIMITE = 20;
const iniciais: FiltrosPeriodo = { data_inicial: null, data_final: null, filtro: "todas", busca: "" };

export default function RelatorioPeriodoPage() {
  const { user } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const filtros = useMemo<FiltrosPeriodo>(() => ({
    data_inicial: parametros.get("data_inicial") || null, data_final: parametros.get("data_final") || null,
    filtro: (parametros.get("filtro") || "todas") as FiltroPainel, busca: parametros.get("busca") || "",
  }), [parametros]);
  const [rascunho, setRascunho] = useState<FiltrosPeriodo>(filtros);
  const [dados, setDados] = useState<ConsultaPeriodo | null>(null);
  const [deslocamento, setDeslocamento] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState("");
  const [erroFormulario, setErroFormulario] = useState("");
  const [aviso, setAviso] = useState("");
  const download = useRef<AbortController | null>(null);

  useEffect(() => { setRascunho(filtros); setDeslocamento(0); setErroFormulario(""); }, [filtros]);
  function aplicar(novos: FiltrosPeriodo) {
    const p: Record<string, string> = {};
    if (novos.data_inicial) p.data_inicial = novos.data_inicial;
    if (novos.data_final) p.data_final = novos.data_final;
    if (novos.filtro !== "todas") p.filtro = novos.filtro;
    if (novos.busca) p.busca = novos.busca;
    setParametros(p); setDeslocamento(0); setErroFormulario(""); setRevisao(v => v + 1);
  }

  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    download.current?.abort(); download.current = null;
    setDados(null); setErro(""); setAviso(""); setBaixando(false); setCarregando(true);
    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }
    void api.get<ConsultaPeriodo>("/administracao/relatorios/periodo", {
      params: { ...filtros, deslocamento, limite: LIMITE }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (!vigente) return;
      if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / LIMITE) * LIMITE); return; }
      setDados(data);
    }).catch((falha: unknown) => {
      if (vigente && !controle.signal.aborted) setErro(mensagemPeriodo(falha));
    }).finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); download.current?.abort(); };
  }, [filtros, deslocamento, revisao, user?.role]);

  function pesquisar(evento: FormEvent) {
    evento.preventDefault();
    if (rascunho.data_inicial && rascunho.data_final && rascunho.data_inicial > rascunho.data_final) {
      setErroFormulario("A data inicial deve ser igual ou anterior à data final."); return;
    }
    aplicar({ ...rascunho, busca: rascunho.busca.trim() });
  }
  function limpar() { aplicar({ ...iniciais }); }
  async function exportar() {
    if (!dados || carregando || baixando || user?.role !== "admin") return;
    const controle = new AbortController(); download.current = controle;
    setBaixando(true); setAviso("");
    try {
      const resposta = await api.get<Blob>("/administracao/relatorios/periodo/csv", {
        params: dados.filtros, responseType: "blob", signal: controle.signal, timeout: 30_000,
      });
      if (controle.signal.aborted) return;
      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");
      const url = URL.createObjectURL(resposta.data);
      const a = document.createElement("a"); a.href = url; a.download = "MEC_SERVICOS_RELATORIO_PERIODO.csv";
      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com todas as contratações dos filtros aplicados."); }
      finally { a.remove(); URL.revokeObjectURL(url); }
    } catch (falha: unknown) {
      if (!controle.signal.aborted) setAviso(mensagemPeriodo(falha));
    } finally {
      if (download.current === controle) { download.current = null; setBaixando(false); }
    }
  }

  if (user?.role !== "admin") return <p role="alert">O relatório está disponível somente para a administração.</p>;
  const i = dados?.indicadores;
  return <article className="periodo35">
    <header className="periodo35-cabecalho"><div><h1><CalendarDays aria-hidden="true" /> Relatório por período</h1>
      <p>Selecione contratações pela data de criação e confira seus valores acumulados até a consulta.</p></div>
      <nav><Link to="/admin">Voltar ao Dashboard</Link><Link to="/admin/relatorios-empresas">Por cliente e fornecedor</Link>
        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>
        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" /> {baixando ? "Exportando…" : "Exportar CSV"}</button></nav></header>
    <section className="periodo35-card"><h2>Selecionar contratações</h2>
      <form className="periodo35-filtros" onSubmit={pesquisar}>
        <label>Data inicial (UTC)<input type="date" value={rascunho.data_inicial ?? ""} onChange={e => setRascunho(v => ({ ...v, data_inicial: e.target.value || null }))} /></label>
        <label>Data final (UTC)<input type="date" value={rascunho.data_final ?? ""} onChange={e => setRascunho(v => ({ ...v, data_final: e.target.value || null }))} /></label>
        <label>Exibir<select value={rascunho.filtro} onChange={e => setRascunho(v => ({ ...v, filtro: e.target.value as FiltroPainel }))}>
          {Object.entries(filtrosPainel).map(([codigo, rotulo]) => <option key={codigo} value={codigo}>{rotulo}</option>)}</select></label>
        <label className="periodo35-busca">Buscar contratação, OS ou empresa<input maxLength={120} value={rascunho.busca} placeholder="OS #3, contratação #1 ou nome"
          onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} /></label>
        <button type="submit"><Search size={16} aria-hidden="true" /> Consultar</button><button type="button" onClick={limpar}>Limpar filtros</button>
      </form>
      <p className="periodo35-nota">Os dois dias são incluídos, em UTC. Datas vazias não limitam o período. Recebimentos e repasses são os acumulados atuais das contratações selecionadas.</p>
      {erroFormulario && <p role="alert" className="periodo35-erro">{erroFormulario}</p>}
    </section>
    {erro && <p role="alert" className="periodo35-erro">{erro}</p>}
    {aviso && <p role="status" className="periodo35-aviso">{aviso}</p>}
    {carregando && <p role="status">Carregando o relatório…</p>}
    {dados && i && <>
      <section className="periodo35-card"><h2>Resumo da seleção</h2>
        <p className="periodo35-aplicados">Período aplicado: {diaUTC(dados.filtros.data_inicial)} até {diaUTC(dados.filtros.data_final)} · {filtrosPainel[dados.filtros.filtro]}
          {dados.filtros.busca && <> · Busca: {dados.filtros.busca}</>}</p>
        <div className="periodo35-contagens"><span><strong>{dados.total}</strong> contratação(ões)</span><span><strong>{i.contratacoes_ativas}</strong> ativas</span>
          <span><strong>{i.contratacoes_concluidas}</strong> concluídas</span><span><strong>{i.contratacoes_canceladas}</strong> canceladas</span><span><strong>{i.para_conferencia}</strong> para conferência</span></div>
        <div className="periodo35-valores">
          <div><span>Valor contratado</span><strong>{dinheiro(dados.valor_contratado)}</strong><small>Todas as contratações selecionadas</small></div>
          <div><span>Recebido confirmado</span><strong>{dinheiro(i.recebimentos_confirmados)}</strong><small>Acumulado atual, sem estornos</small></div>
          <div><span>Repassado confirmado</span><strong>{dinheiro(i.repasses_confirmados)}</strong><small>Acumulado atual, sem estornos</small></div>
          <div><span>Saldo a receber</span><strong>{dinheiro(i.saldo_clientes_controles_abertos)}</strong><small>Somente controles abertos</small></div>
          <div><span>Saldo a repassar</span><strong>{dinheiro(i.saldo_fornecedores_controles_abertos)}</strong><small>Somente controles abertos</small></div>
          <div><span>Disponível para repasse</span><strong>{dinheiro(i.disponivel_repasses)}</strong><small>Controles abertos, conforme entrega e cobertura</small></div>
        </div>
        <p className="periodo35-nota">{i.controles_abertos} controle(s) aberto(s) · {i.financeiros_encerrados} financeiro(s) encerrado(s). Os totais e os meses incluem todas as correspondências dos filtros, em todas as páginas.</p>
        <small>Consultado em {dataFinanceiro(dados.gerado_em)}. O CSV consulta dados atuais com os filtros aplicados.</small>
      </section>
      {!dados.total ? <section className="periodo35-card"><p role="status">Nenhuma contratação corresponde aos filtros aplicados.</p></section> : <>
        <section className="periodo35-card"><h2>Comparação por mês da contratação</h2><p className="periodo35-nota">Agrupamento pela criação em UTC. Os valores financeiros são acumulados até a consulta.</p>
          <div className="periodo35-scroll"><table><thead><tr><th>Mês (UTC)</th><th>Contratações</th><th>Valor contratado</th><th>Recebido confirmado</th><th>Repassado confirmado</th></tr></thead>
            <tbody>{dados.meses.map(m => <tr key={m.mes}><td>{m.mes.split("-").reverse().join("/")}</td><td>{m.total_contratacoes}</td><td>{dinheiro(m.valor_contratado)}</td><td>{dinheiro(m.recebido_confirmado)}</td><td>{dinheiro(m.repassado_confirmado)}</td></tr>)}</tbody></table></div>
        </section>
        <section className="periodo35-card"><h2>Contratações selecionadas</h2><div className="periodo35-scroll"><table><thead><tr><th>Contratação / OS</th><th>Criada em (UTC)</th><th>Cliente / fornecedor</th><th>Situação</th><th>Valor contratado</th><th>Recebido</th><th>Repassado</th><th>Consultar</th></tr></thead>
          <tbody>{dados.itens.map(item => <tr key={item.contratacao_id}>
            <td><strong>Contratação #{item.contratacao_id}</strong><small>{item.ordem_servico_id ? `OS #${item.ordem_servico_id}` : "Sem OS"}</small></td>
            <td><time dateTime={item.contratada_em}>{diaUTC(item.contratada_em)}</time></td><td>{item.cliente}<small>{item.fornecedor}</small></td>
            <td>{situacoesPainel[item.situacao]}<small>{estados[item.financeiro_status]}</small></td><td>{dinheiro(item.valor_contratado)}</td><td>{dinheiro(item.total_recebido)}</td><td>{dinheiro(item.total_repassado)}</td>
            <td><Link to={`/admin/relatorios?contratacao=${item.contratacao_id}`}>Relatório #{item.contratacao_id}</Link><small><Link to={`/admin/pagamentos?contratacao=${item.contratacao_id}`}>Financeiro</Link></small></td>
          </tr>)}</tbody></table></div>
          <nav className="periodo35-paginacao" aria-label="Páginas das contratações"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total)} de {dados.total}</span>
            <button type="button" disabled={!deslocamento || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button>
            <button type="button" disabled={deslocamento + LIMITE >= dados.total || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></nav>
        </section>
      </>}
    </>}
  </article>;
}
