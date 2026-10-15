import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ClipboardList, Download, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";
import { filtrosPainel, situacoesPainel, type FiltroPainel } from "../painel/painelPortal";
import { diaUTC, mensagemPeriodo } from "../periodo/periodoPortal";
import { areasFila, type AreaFila, type ConsultaPendencias, type FiltrosPendencias } from "./pendenciasPortal";
import "../periodo/RelatorioPeriodo.css";
import "./CentralPendencias.css";

const LIMITE = 20;
const iniciais: FiltrosPendencias = { data_inicial: null, data_final: null, filtro: "todas", busca: "", area: "todas", acao: "" };

export default function CentralPendenciasPage() {
  const { user } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const filtros = useMemo<FiltrosPendencias>(() => ({ data_inicial: parametros.get("data_inicial") || null,
    data_final: parametros.get("data_final") || null, filtro: (parametros.get("filtro") || "todas") as FiltroPainel,
    busca: parametros.get("busca") || "", area: (parametros.get("area") || "todas") as AreaFila, acao: parametros.get("acao") || "" }), [parametros]);
  const [rascunho, setRascunho] = useState<FiltrosPendencias>(filtros);
  const [dados, setDados] = useState<ConsultaPendencias | null>(null);
  const [deslocamento, setDeslocamento] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState("");
  const [erroFormulario, setErroFormulario] = useState("");
  const [aviso, setAviso] = useState("");
  const download = useRef<AbortController | null>(null);

  useEffect(() => { setRascunho(filtros); setDeslocamento(0); setErroFormulario(""); }, [filtros]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    download.current?.abort(); download.current = null;
    setDados(null); setErro(""); setAviso(""); setBaixando(false); setCarregando(true);
    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }
    void api.get<ConsultaPendencias>("/administracao/pendencias", {
      params: { ...filtros, deslocamento, limite: LIMITE }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (!vigente) return;
      if (data.total_pendencias && deslocamento >= data.total_pendencias) { setDeslocamento(Math.floor((data.total_pendencias - 1) / LIMITE) * LIMITE); return; }
      setDados(data);
    }).catch((falha: unknown) => {
      if (vigente && !controle.signal.aborted) setErro(mensagemPeriodo(falha));
    }).finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); download.current?.abort(); };
  }, [filtros, deslocamento, revisao, user?.role]);

  function aplicar(novos: FiltrosPendencias) {
    const params: Record<string, string> = {};
    for (const [campo, valor] of Object.entries(novos)) if (valor && valor !== "todas") params[campo] = valor;
    setDeslocamento(0); setErroFormulario(""); setParametros(params); setRevisao(v => v + 1);
  }
  function pesquisar(evento: FormEvent) {
    evento.preventDefault();
    if (rascunho.data_inicial && rascunho.data_final && rascunho.data_inicial > rascunho.data_final) {
      setErroFormulario("A data inicial deve ser igual ou anterior à data final."); return;
    }
    aplicar({ ...rascunho, busca: rascunho.busca.trim() });
  }
  async function exportar() {
    if (!dados || carregando || baixando || user?.role !== "admin") return;
    const controle = new AbortController(); download.current = controle; setBaixando(true); setAviso("");
    try {
      const resposta = await api.get<Blob>("/administracao/pendencias/csv", { params: dados.filtros,
        responseType: "blob", signal: controle.signal, timeout: 30_000 });
      if (controle.signal.aborted) return;
      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");
      const url = URL.createObjectURL(resposta.data); const a = document.createElement("a");
      a.href = url; a.download = "MEC_SERVICOS_CENTRAL_PENDENCIAS.csv";
      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com todas as pendências dos filtros aplicados e uma linha financeira por contratação."); }
      finally { a.remove(); URL.revokeObjectURL(url); }
    } catch (falha: unknown) { if (!controle.signal.aborted) setAviso(mensagemPeriodo(falha)); }
    finally { if (download.current === controle) { download.current = null; setBaixando(false); } }
  }

  if (user?.role !== "admin") return <p role="alert">A central está disponível somente para a administração.</p>;
  const i = dados?.indicadores;
  const destino = { intermediacao: "Intermediação", financeiro: "Financeiro", relatorio: "Conferir relatório" };
  return <article className="periodo35 pendencias37">
    <header className="periodo35-cabecalho"><div><h1><ClipboardList aria-hidden="true" /> Central de pendências</h1>
      <p>Consulte as ações administrativas atuais e abra o registro correspondente para conferência.</p></div>
      <nav><Link to="/admin">Voltar ao Dashboard</Link><Link to="/admin/relatorios-empresas">Por cliente e fornecedor</Link><Link to="/admin/resumo-gerencial">Resumo gerencial mensal</Link>
        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>
        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" /> {baixando ? "Exportando…" : "Exportar CSV"}</button></nav></header>
    <section className="periodo35-card"><h2>Selecionar pendências</h2>
      <form className="periodo35-filtros pendencias37-filtros" onSubmit={pesquisar}>
        <label>Área<select value={rascunho.area} onChange={e => setRascunho(v => ({ ...v, area: e.target.value as AreaFila, acao: "" }))}>{Object.entries(areasFila).map(([v, r]) => <option key={v} value={v}>{r}</option>)}</select></label>
        <label>Ação<select value={rascunho.acao} onChange={e => setRascunho(v => ({ ...v, acao: e.target.value }))}><option value="">Todas as ações</option>
          {dados?.catalogo_acoes.filter(a => rascunho.area === "todas" || a.area === rascunho.area).map(a => <option key={a.codigo} value={a.codigo}>{a.rotulo}</option>)}</select></label>
        <label>Data inicial (UTC)<input type="date" value={rascunho.data_inicial ?? ""} onChange={e => setRascunho(v => ({ ...v, data_inicial: e.target.value || null }))} /></label>
        <label>Data final (UTC)<input type="date" value={rascunho.data_final ?? ""} onChange={e => setRascunho(v => ({ ...v, data_final: e.target.value || null }))} /></label>
        <label>Exibir<select value={rascunho.filtro} onChange={e => setRascunho(v => ({ ...v, filtro: e.target.value as FiltroPainel }))}>{Object.entries(filtrosPainel).map(([v, r]) => <option key={v} value={v}>{r}</option>)}</select></label>
        <label className="periodo35-busca">Buscar empresa, contratação ou OS<input type="search" maxLength={120} placeholder="Ex.: oficina, Contratação #1 ou OS #3" value={rascunho.busca} onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} /></label>
        <button type="submit" disabled={carregando}><Search size={16} aria-hidden="true" /> Consultar</button>
        <button type="button" disabled={carregando} onClick={() => aplicar({ ...iniciais })}>Limpar filtros</button>
      </form>
      {erroFormulario && <p role="alert" className="periodo35-erro">{erroFormulario}</p>}
      <p className="periodo35-nota">O período considera a criação da contratação em UTC, incluindo os dois dias. A fila mostra as pendências atuais, ordenadas da contratação mais antiga à mais recente.</p>
    </section>
    {aviso && <p role="status" className="periodo35-aviso">{aviso}</p>}
    {carregando ? <p role="status">Consultando pendências atuais…</p> : erro ? <p role="alert" className="periodo35-erro">{erro}</p> : dados && i && <>
      <section className="periodo35-card pendencias37-resumo"><h2>Fila da seleção</h2>
        <p className="periodo35-aplicados">{areasFila[dados.filtros.area]} · Ação: {dados.catalogo_acoes.find(a => a.codigo === dados.filtros.acao)?.rotulo ?? "Todas"} · {diaUTC(dados.filtros.data_inicial)} até {diaUTC(dados.filtros.data_final)} · {filtrosPainel[dados.filtros.filtro]} · Busca: {dados.filtros.busca || "Todas"}</p>
        <p className="pendencias37-contagem"><strong>{dados.total_pendencias} pendência(s)</strong> em <strong>{dados.total_contratacoes} contratação(ões)</strong></p>
        <div className="pendencias37-areas"><div><span>Operacionais</span><strong>{dados.pendencias_operacionais}</strong></div><div><span>Financeiras</span><strong>{dados.pendencias_financeiras}</strong></div><div><span>Para conferência</span><strong>{dados.pendencias_conferencia}</strong></div></div>
        <p className="periodo35-nota">Uma contratação pode ter várias ações na fila. As contagens incluem todas as páginas.</p>
        <h2>Valores das contratações com pendências</h2>
        <div className="periodo35-valores"><div><span>Valor contratado</span><strong>{dinheiro(dados.valor_contratado)}</strong></div><div><span>Recebido confirmado</span><strong>{dinheiro(i.recebimentos_confirmados)}</strong></div><div><span>Repassado confirmado</span><strong>{dinheiro(i.repasses_confirmados)}</strong></div>
          <div><span>Saldo a receber</span><strong>{dinheiro(i.saldo_clientes_controles_abertos)}</strong></div><div><span>Saldo a repassar</span><strong>{dinheiro(i.saldo_fornecedores_controles_abertos)}</strong></div><div><span>Disponível para repasse</span><strong>{dinheiro(i.disponivel_repasses)}</strong></div></div>
        <p className="periodo35-nota">Cada contratação soma uma vez. Recebimentos e repasses excluem estornos; saldos e disponibilidade consideram somente controles financeiros abertos.</p>
        <small>Consultado em {dataFinanceiro(dados.gerado_em)}. O CSV consulta dados atuais com os filtros aplicados.</small>
      </section>
      {!dados.total_pendencias ? <section className="periodo35-card pendencias37-vazia"><p>Nenhuma pendência corresponde aos filtros aplicados.</p></section> : <section className="periodo35-card pendencias37-fila"><h2>Ações administrativas</h2>
        <div className="periodo35-scroll"><table><thead><tr><th>Contratação / OS</th><th>Contratada em (UTC)</th><th>Cliente / fornecedor</th><th>Área e ação</th><th>Orientação</th><th>Situação</th><th>Consultar</th></tr></thead>
          <tbody>{dados.itens.map(item => { const c = item.contratacao; return <tr key={`${c.contratacao_id}-${item.pendencia.codigo}`}>
            <td><strong>Contratação #{c.contratacao_id}</strong><small>{c.ordem_servico_id ? `OS #${c.ordem_servico_id}` : "Sem OS"}</small></td><td>{diaUTC(c.contratada_em)}</td>
            <td>{c.cliente}<small>Cliente ID #{c.empresa_cliente_id}</small>{c.fornecedor}<small>Fornecedor ID #{c.empresa_fornecedora_id}</small></td>
            <td><strong>{areasFila[item.pendencia.area]}</strong><small>{item.acao}</small></td><td>{item.pendencia.descricao}</td>
            <td>{situacoesPainel[c.situacao]}<small>{estados[c.financeiro_status]}</small></td>
            <td><nav><Link className="pendencias37-destino" to={item.caminho}>{destino[item.destino]}</Link>{item.destino !== "relatorio" && <Link to={`/admin/relatorios?contratacao=${c.contratacao_id}`}>Relatório #{c.contratacao_id}</Link>}</nav></td>
          </tr>; })}</tbody></table></div>
        <nav className="periodo35-paginacao pendencias37-paginacao" aria-label="Páginas da fila"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total_pendencias)} de {dados.total_pendencias} pendências</span>
          <button type="button" disabled={!deslocamento || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button><button type="button" disabled={deslocamento + LIMITE >= dados.total_pendencias || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></nav>
      </section>}
    </>}
  </article>;
}
