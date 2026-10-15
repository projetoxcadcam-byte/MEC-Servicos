import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Building2, Download, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";
import { filtrosPainel, situacoesPainel, type FiltroPainel } from "../painel/painelPortal";
import { diaUTC, mensagemPeriodo } from "../periodo/periodoPortal";
import type { AgrupamentoEmpresas, ConsultaEmpresas, FiltrosEmpresas } from "./empresasPortal";
import "../periodo/RelatorioPeriodo.css";
import "./RelatorioEmpresas.css";

const LIMITE = 20;
const iniciais: FiltrosEmpresas = { agrupamento: "clientes", empresa_id: null, data_inicial: null, data_final: null, filtro: "todas", busca: "" };

export default function RelatorioEmpresasPage() {
  const { user } = useAuth();
  const [rascunho, setRascunho] = useState<FiltrosEmpresas>(iniciais);
  const [filtros, setFiltros] = useState<FiltrosEmpresas>(iniciais);
  const [dados, setDados] = useState<ConsultaEmpresas | null>(null);
  const [deslocamento, setDeslocamento] = useState(0);
  const [deslocamentoItens, setDeslocamentoItens] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState("");
  const [erroFormulario, setErroFormulario] = useState("");
  const [aviso, setAviso] = useState("");
  const download = useRef<AbortController | null>(null);

  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    download.current?.abort(); download.current = null;
    setDados(null); setErro(""); setAviso(""); setBaixando(false); setCarregando(true);
    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }
    void api.get<ConsultaEmpresas>("/administracao/relatorios/empresas", {
      params: { ...filtros, deslocamento, deslocamento_itens: deslocamentoItens, limite: LIMITE }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (!vigente) return;
      if (data.total_empresas && deslocamento >= data.total_empresas) {
        setDeslocamento(Math.floor((data.total_empresas - 1) / LIMITE) * LIMITE); return;
      }
      if (filtros.empresa_id && data.total_contratacoes && deslocamentoItens >= data.total_contratacoes) {
        setDeslocamentoItens(Math.floor((data.total_contratacoes - 1) / LIMITE) * LIMITE); return;
      }
      setDados(data);
    }).catch((falha: unknown) => {
      if (vigente && !controle.signal.aborted) setErro(mensagemPeriodo(falha));
    }).finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); download.current?.abort(); };
  }, [filtros, deslocamento, deslocamentoItens, revisao, user?.role]);

  function aplicar(novos: FiltrosEmpresas) {
    setErroFormulario(""); setDeslocamento(0); setDeslocamentoItens(0); setFiltros(novos); setRascunho(novos);
  }
  function pesquisar(evento: FormEvent) {
    evento.preventDefault();
    if (rascunho.data_inicial && rascunho.data_final && rascunho.data_inicial > rascunho.data_final) {
      setErroFormulario("A data inicial deve ser igual ou anterior à data final."); return;
    }
    aplicar({ ...rascunho, busca: rascunho.busca.trim(), empresa_id: null });
  }
  async function exportar() {
    if (!dados || carregando || baixando || user?.role !== "admin") return;
    const controle = new AbortController(); download.current = controle;
    setBaixando(true); setAviso("");
    try {
      const resposta = await api.get<Blob>("/administracao/relatorios/empresas/csv", {
        params: dados.filtros, responseType: "blob", signal: controle.signal, timeout: 30_000,
      });
      if (controle.signal.aborted) return;
      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");
      const url = URL.createObjectURL(resposta.data);
      const a = document.createElement("a"); a.href = url; a.download = "MEC_SERVICOS_RELATORIO_EMPRESAS.csv";
      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com todas as empresas e contratações dos filtros aplicados."); }
      finally { a.remove(); URL.revokeObjectURL(url); }
    } catch (falha: unknown) {
      if (!controle.signal.aborted) setAviso(mensagemPeriodo(falha));
    } finally {
      if (download.current === controle) { download.current = null; setBaixando(false); }
    }
  }

  if (user?.role !== "admin") return <p role="alert">O relatório está disponível somente para a administração.</p>;
  const i = dados?.indicadores;
  return <article className="periodo35 empresas36">
    <header className="periodo35-cabecalho"><div><h1><Building2 aria-hidden="true" /> Relatório por cliente e fornecedor</h1>
      <p>Compare os valores e as pendências de cada empresa nas contratações selecionadas.</p></div>
      <nav><Link to="/admin">Voltar ao Dashboard</Link><Link to="/admin/relatorios-periodo">Relatório por período</Link><Link to="/admin/pendencias">Central de pendências</Link><Link to="/admin/resumo-gerencial">Resumo gerencial mensal</Link>
        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>
        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" /> {baixando ? "Exportando…" : "Exportar CSV"}</button></nav></header>
    <section className="periodo35-card"><h2>Selecionar contratações</h2>
      <form className="periodo35-filtros empresas36-filtros" onSubmit={pesquisar}>
        <label>Agrupar por<select value={rascunho.agrupamento} onChange={e => setRascunho(v => ({ ...v, agrupamento: e.target.value as AgrupamentoEmpresas }))}><option value="clientes">Clientes</option><option value="fornecedores">Fornecedores</option></select></label>
        <label>Data inicial (UTC)<input type="date" value={rascunho.data_inicial ?? ""} onChange={e => setRascunho(v => ({ ...v, data_inicial: e.target.value || null }))} /></label>
        <label>Data final (UTC)<input type="date" value={rascunho.data_final ?? ""} onChange={e => setRascunho(v => ({ ...v, data_final: e.target.value || null }))} /></label>
        <label>Exibir<select value={rascunho.filtro} onChange={e => setRascunho(v => ({ ...v, filtro: e.target.value as FiltroPainel }))}>{Object.entries(filtrosPainel).map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}</select></label>
        <label className="periodo35-busca">Buscar empresa, contratação ou OS<input type="search" maxLength={120} placeholder="Ex.: oficina, Contratação #1 ou OS #3" value={rascunho.busca} onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} /></label>
        <button type="submit" disabled={carregando}><Search size={16} aria-hidden="true" /> Consultar</button>
        <button type="button" disabled={carregando} onClick={() => aplicar({ ...iniciais })}>Limpar filtros</button>
      </form>
      {erroFormulario && <p role="alert" className="periodo35-erro">{erroFormulario}</p>}
      <p className="periodo35-nota">O período considera a criação da contratação em UTC, com os dois dias incluídos. Os valores são acumulados até a consulta; movimentos estornados são excluídos.</p>
    </section>
    {aviso && <p role="status" className="periodo35-aviso">{aviso}</p>}
    {carregando ? <p role="status">Consultando empresas e contratações…</p> : erro ? <p role="alert" className="periodo35-erro">{erro}</p> : dados && i && <>
      <section className="periodo35-card empresas36-resumo"><h2>Totais da seleção</h2>
        <p className="periodo35-aplicados">Agrupamento: {dados.filtros.agrupamento === "clientes" ? "Clientes" : "Fornecedores"} · {diaUTC(dados.filtros.data_inicial)} até {diaUTC(dados.filtros.data_final)} · {filtrosPainel[dados.filtros.filtro]} · Busca: {dados.filtros.busca || "Todas"}</p>
        {dados.filtros.empresa_id && <div className="empresas36-selecionada"><p>Empresa selecionada: <strong>{dados.empresa_selecionada?.empresa ?? "Sem correspondência"}</strong> · ID #{dados.filtros.empresa_id}</p>
          <button type="button" onClick={() => aplicar({ ...dados.filtros, empresa_id: null })}>Todas as empresas</button></div>}
        <div className="periodo35-contagens"><strong>{dados.total_empresas} empresa(s) · {dados.total_contratacoes} contratação(ões)</strong>
          <span>{i.contratacoes_concluidas} concluída(s)</span><span>{i.acompanhamento_operacional} com pendência operacional</span>
          <span>{i.pendencias_financeiras} com pendência financeira</span><span>{i.para_conferencia} para conferência</span></div>
        <div className="periodo35-valores">
          <div><span>Valor contratado</span><strong>{dinheiro(dados.valor_contratado)}</strong></div>
          <div><span>Recebido confirmado</span><strong>{dinheiro(i.recebimentos_confirmados)}</strong></div>
          <div><span>Repassado confirmado</span><strong>{dinheiro(i.repasses_confirmados)}</strong></div>
          <div><span>Saldo a receber</span><strong>{dinheiro(i.saldo_clientes_controles_abertos)}</strong><small>Somente controles abertos</small></div>
          <div><span>Saldo a repassar</span><strong>{dinheiro(i.saldo_fornecedores_controles_abertos)}</strong><small>Somente controles abertos</small></div>
          <div><span>Disponível para repasse</span><strong>{dinheiro(i.disponivel_repasses)}</strong><small>Controles abertos, conforme entrega e cobertura</small></div>
        </div>
        <p className="periodo35-nota">{i.controles_abertos} controle(s) aberto(s) · {i.financeiros_encerrados} financeiro(s) encerrado(s). Os totais incluem todas as páginas. As pendências contam contratações; uma contratação pode aparecer em mais de uma categoria.</p>
        <small>Consultado em {dataFinanceiro(dados.gerado_em)}. O CSV consulta dados atuais com os filtros aplicados.</small>
      </section>
      {!dados.total_contratacoes ? <section className="periodo35-card"><p>Nenhuma contratação corresponde aos filtros aplicados.</p></section> : <>
        <section className="periodo35-card empresas36-grupos"><h2>{dados.filtros.agrupamento === "clientes" ? "Comparação por cliente" : "Comparação por fornecedor"}</h2>
          <p className="periodo35-nota">Ordenado pelo valor contratado, do maior para o menor. Empresas com o mesmo nome permanecem separadas pelo ID.</p>
          <div className="periodo35-scroll"><table><thead><tr><th>Empresa</th><th>Contratações</th><th>Valor contratado</th><th>Recebido</th><th>Repassado</th><th>Saldo a receber</th><th>Saldo a repassar</th><th>Disponível para repasse</th><th>Pendências</th><th>Consultar</th></tr></thead>
            <tbody>{dados.grupos.map(g => <tr key={g.empresa_id}><td><strong>{g.empresa}</strong><small>ID #{g.empresa_id}</small></td>
              <td>{g.indicadores.total_contratacoes}<small>{g.indicadores.contratacoes_concluidas} concluída(s)</small></td>
              <td>{dinheiro(g.valor_contratado)}</td><td>{dinheiro(g.indicadores.recebimentos_confirmados)}</td><td>{dinheiro(g.indicadores.repasses_confirmados)}</td>
              <td>{dinheiro(g.indicadores.saldo_clientes_controles_abertos)}</td><td>{dinheiro(g.indicadores.saldo_fornecedores_controles_abertos)}</td><td>{dinheiro(g.indicadores.disponivel_repasses)}</td>
              <td><small>{g.indicadores.acompanhamento_operacional} operacional</small><small>{g.indicadores.pendencias_financeiras} financeira</small><small>{g.indicadores.para_conferencia} conferência</small></td>
              <td><button type="button" onClick={() => aplicar({ ...dados.filtros, empresa_id: g.empresa_id })}>Ver contratações</button></td></tr>)}</tbody></table></div>
          {!dados.filtros.empresa_id && <nav className="periodo35-paginacao empresas36-paginacao" aria-label="Páginas das empresas"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.grupos.length, dados.total_empresas)} de {dados.total_empresas} empresas</span>
            <button type="button" disabled={!deslocamento || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button>
            <button type="button" disabled={deslocamento + LIMITE >= dados.total_empresas || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></nav>}
        </section>
        {dados.filtros.empresa_id && <section className="periodo35-card empresas36-itens"><h2>Contratações da empresa selecionada</h2>
          <div className="periodo35-scroll"><table><thead><tr><th>Contratação / OS</th><th>Criada em (UTC)</th><th>Cliente / fornecedor</th><th>Situação</th><th>Valor contratado</th><th>Recebido</th><th>Repassado</th><th>Consultar</th></tr></thead>
            <tbody>{dados.itens.map(item => <tr key={item.contratacao_id}><td><strong>Contratação #{item.contratacao_id}</strong><small>{item.ordem_servico_id ? `OS #${item.ordem_servico_id}` : "Sem OS"}</small></td>
              <td><time dateTime={item.contratada_em}>{diaUTC(item.contratada_em)}</time></td><td>{item.cliente}<small>Cliente ID #{item.empresa_cliente_id}</small>{item.fornecedor}<small>Fornecedor ID #{item.empresa_fornecedora_id}</small></td>
              <td>{situacoesPainel[item.situacao]}<small>{estados[item.financeiro_status] ?? "Sem controle financeiro"}</small>{item.pendencias.map(p => <small key={p.codigo}>{p.descricao}</small>)}</td>
              <td>{dinheiro(item.valor_contratado)}</td><td>{dinheiro(item.total_recebido)}</td><td>{dinheiro(item.total_repassado)}</td>
              <td><Link to={`/admin/relatorios?contratacao=${item.contratacao_id}`}>Relatório #{item.contratacao_id}</Link>{item.pendencias.length > 0 && <small><Link to={"/admin/pendencias?busca=" + encodeURIComponent("Contratação #" + item.contratacao_id)}>Pendências</Link></small>}<small><Link to={`/admin/pagamentos?contratacao=${item.contratacao_id}`}>Financeiro</Link></small></td></tr>)}</tbody></table></div>
          <nav className="periodo35-paginacao empresas36-paginacao-itens" aria-label="Páginas das contratações da empresa"><span>{deslocamentoItens + 1}–{Math.min(deslocamentoItens + dados.itens.length, dados.total_contratacoes)} de {dados.total_contratacoes} contratações</span>
            <button type="button" disabled={!deslocamentoItens || carregando} onClick={() => setDeslocamentoItens(v => Math.max(0, v - LIMITE))}>Anterior</button>
            <button type="button" disabled={deslocamentoItens + LIMITE >= dados.total_contratacoes || carregando} onClick={() => setDeslocamentoItens(v => v + LIMITE)}>Próxima</button></nav>
        </section>}
      </>}
    </>}
  </article>;
}
