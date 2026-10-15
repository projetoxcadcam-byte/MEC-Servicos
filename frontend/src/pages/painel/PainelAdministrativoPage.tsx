import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CircleCheck, ClipboardList, LayoutDashboard, RefreshCw, Search, TriangleAlert } from "lucide-react";
import { api } from "../../services/api";
import { useAuth } from "../../auth/AuthContext";
import { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";
import { statusVisivel } from "../intermediacao/intermediacaoPortal";
import { filtrosPainel, mensagemPainel, situacoesPainel, type ConsultaPainel, type FiltroPainel } from "./painelPortal";
import "./PainelAdministrativo.css";

const LIMITE = 20;
const areas = { operacional: "Operação", financeira: "Financeiro", conferencia: "Conferência" };

export default function PainelAdministrativoPage() {
  const { user } = useAuth();
  const [dados, setDados] = useState<ConsultaPainel | null>(null);
  const [filtro, setFiltro] = useState<FiltroPainel>("todas");
  const [textoBusca, setTextoBusca] = useState(""); const [busca, setBusca] = useState("");
  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(true); const [erro, setErro] = useState("");

  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setDados(null); setErro(""); setCarregando(true);
    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }
    void api.get<ConsultaPainel>("/administracao/painel", {
      params: { filtro, busca, deslocamento, limite: LIMITE }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (!vigente) return;
      if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / LIMITE) * LIMITE); return; }
      setDados(data);
    }).catch((falha: unknown) => {
      if (vigente && !controle.signal.aborted) setErro(mensagemPainel(falha));
    }).finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); };
  }, [filtro, busca, deslocamento, revisao, user?.role]);

  function filtrar(valor: FiltroPainel) { setFiltro(valor); setDeslocamento(0); }
  function pesquisar(evento: FormEvent) { evento.preventDefault(); setBusca(textoBusca.trim()); setDeslocamento(0); }
  function limpar() { setTextoBusca(""); setBusca(""); setFiltro("todas"); setDeslocamento(0); }
  const indicadores = dados?.indicadores;

  if (user?.role !== "admin") return <p role="alert">O painel está disponível somente para a administração.</p>;
  return <div className="painel33">
    <header className="painel33-cabecalho"><div><p className="painel33-eyebrow"><LayoutDashboard size={16} aria-hidden="true" /> ADMINISTRAÇÃO</p>
      <h1>Painel administrativo</h1><p>Acompanhe os serviços, os saldos registrados e os próximos passos de cada contratação.</p></div>
      <nav className="painel33-links" aria-label="Cadastros e relatórios administrativos"><Link to="/admin/empresas">Empresas e operações</Link><Link to="/admin/relatorios-periodo">Relatório por período</Link><Link to="/admin/relatorios-empresas">Por cliente e fornecedor</Link><Link to="/admin/pendencias">Central de pendências</Link><Link to="/admin/resumo-gerencial">Resumo gerencial mensal</Link><Link to="/admin/comparativo-gerencial">Comparativo entre períodos</Link><Link to="/admin/extrato-financeiro">Extrato financeiro</Link>
      <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button></nav></header>
    {erro && <p className="painel33-alerta" role="alert">{erro}</p>}
    {carregando && <p className="painel33-carregando" role="status">Carregando os dados atuais…</p>}
    {indicadores && <>
      <section className="painel33-indicadores" aria-label="Indicadores gerais">
        <div className="painel33-indicador"><span>Contratações ativas</span><strong>{indicadores.contratacoes_ativas}</strong><small>{indicadores.total_contratacoes} no histórico</small></div>
        <button type="button" className="painel33-indicador" onClick={() => filtrar("operacionais")}><span>Em acompanhamento operacional</span><strong>{indicadores.acompanhamento_operacional}</strong><small>Ver próximos passos <ArrowRight size={14} aria-hidden="true" /></small></button>
        <button type="button" className="painel33-indicador" onClick={() => filtrar("financeiras")}><span>Com pendência financeira</span><strong>{indicadores.pendencias_financeiras}</strong><small>Ver controles e saldos <ArrowRight size={14} aria-hidden="true" /></small></button>
        <button type="button" className="painel33-indicador" onClick={() => filtrar("concluidas")}><span>Contratações concluídas</span><strong>{indicadores.contratacoes_concluidas}</strong><small><CircleCheck size={14} aria-hidden="true" /> {indicadores.financeiros_encerrados} com financeiro encerrado</small></button>
        <button type="button" className={`painel33-indicador ${indicadores.para_conferencia ? "painel33-atencao" : ""}`} onClick={() => filtrar("verificar")}><span>Para conferência</span><strong>{indicadores.para_conferencia}</strong><small>Ver registros que precisam de revisão</small></button>
      </section>
      <section className="painel33-painel"><h2>Saldos e movimentos registrados</h2>
        <div className="painel33-valores">
          <div><span>Recebimentos confirmados</span><strong>{dinheiro(indicadores.recebimentos_confirmados)}</strong><small>Todo o histórico, sem estornos</small></div>
          <div><span>Repasses confirmados</span><strong>{dinheiro(indicadores.repasses_confirmados)}</strong><small>Todo o histórico, sem estornos</small></div>
          <div><span>Saldo a receber</span><strong>{dinheiro(indicadores.saldo_clientes_controles_abertos)}</strong><small>Somente controles abertos</small></div>
          <div><span>Saldo a repassar</span><strong>{dinheiro(indicadores.saldo_fornecedores_controles_abertos)}</strong><small>Somente controles abertos</small></div>
          <div><span>Disponível para repasse</span><strong>{dinheiro(indicadores.disponivel_repasses)}</strong><small>Controles abertos com entrega concluída</small></div>
        </div><p className="painel33-nota">{indicadores.controles_abertos} controle(s) financeiro(s) aberto(s). Consultar o painel não registra recebimentos, repasses ou encerramentos.</p>
      </section>
    </>}
    <section className="painel33-painel" aria-busy={carregando}><div className="painel33-titulo"><h2><ClipboardList size={20} aria-hidden="true" /> Contratações e próximos passos</h2>
      {dados && <small>Atualizado em {dataFinanceiro(dados.atualizado_em)}</small>}</div>
      <form className="painel33-filtros" onSubmit={pesquisar}>
        <label>Exibir<select value={filtro} onChange={e => filtrar(e.target.value as FiltroPainel)}>{Object.entries(filtrosPainel).map(([codigo, rotulo]) => <option key={codigo} value={codigo}>{rotulo}</option>)}</select></label>
        <label>Buscar contratação, OS ou empresa<input value={textoBusca} onChange={e => setTextoBusca(e.target.value)} maxLength={120} placeholder="OS #3, contratação #1 ou nome" /></label>
        <button type="submit"><Search size={16} aria-hidden="true" /> Buscar</button><button type="button" onClick={limpar}>Limpar filtros</button>
      </form>
      <p className="painel33-nota">Os indicadores gerais abrangem todo o histórico e não mudam com o filtro ou a página. Uma contratação pode ter próximos passos operacionais e financeiros.</p>
      {dados && !dados.total && <p role="status">{indicadores?.total_contratacoes ? "Nenhuma contratação corresponde aos filtros informados." : "Nenhuma contratação registrada até o momento."}</p>}
      {dados && dados.itens.length > 0 && <><div className="painel33-tabela"><table><thead><tr><th>Contratação / OS</th><th>Cliente / fornecedor</th><th>Andamento</th><th>Financeiro</th><th>Próximos passos</th><th>Abrir</th></tr></thead>
        <tbody>{dados.itens.map(item => <tr key={item.contratacao_id}>
          <td><strong>Contratação #{item.contratacao_id}</strong><small>{item.ordem_servico_id ? `OS #${item.ordem_servico_id}` : "Sem ordem de serviço"}</small><small>Solicitação #{item.solicitacao_id}</small></td>
          <td>{item.cliente}<small>{item.fornecedor}</small></td>
          <td><span className={`painel33-situacao painel33-${item.situacao}`}>{situacoesPainel[item.situacao]}</span>
            <small>{item.etapa_administrativa ? statusVisivel(item.etapa_administrativa) : item.contratacao_status !== "ativa" ? "Histórico anterior" : item.ordem_servico_id ? "Intermediação não iniciada" : "Ordem ainda não criada"}</small>
            {item.pendencias.some(p => p.codigo === "solicitar_coleta") && <small className="painel33-pronto">Produção pronta para coleta</small>}
            <small>Contrato: {estados[item.contratacao_status] ?? "Para conferência"}</small></td>
          <td><strong>{dinheiro(item.valor_contratado)}</strong><small>{estados[item.financeiro_status]}</small>
            <small>Recebido: {dinheiro(item.total_recebido)}</small><small>Repassado: {dinheiro(item.total_repassado)}</small></td>
          <td>{item.pendencias.length ? <ul className="painel33-passos">{item.pendencias.map(p => <li key={p.codigo}><span>{p.area === "conferencia" && <TriangleAlert size={13} aria-hidden="true" />}{areas[p.area]}</span> {p.descricao}</li>)}</ul> :
            <p>{item.situacao === "cancelada" ? "Contratação cancelada; histórico preservado." : item.financeiro_status === "encerrado" ? "Entrega e financeiro concluídos." : "Contratação encerrada no histórico anterior."}</p>}</td>
          <td><div className="painel33-links"><Link to={`/admin/pagamentos?contratacao=${item.contratacao_id}`}>Financeiro <ArrowRight size={14} aria-hidden="true" /></Link>
            {(item.ordem_servico_id || item.contratacao_status === "ativa") && <Link to={item.ordem_servico_id ? `/admin/intermediacao?ordem=${item.ordem_servico_id}` : `/admin/intermediacao?contratacao=${item.contratacao_id}`}>
              {item.ordem_servico_id ? "Intermediação" : "Criar OS"} <ArrowRight size={14} aria-hidden="true" /></Link>}
            <Link to={"/admin/relatorios?contratacao=" + item.contratacao_id}>Relatório <ArrowRight size={14} aria-hidden="true" /></Link>
            <small>{dataFinanceiro(item.atualizado_em ?? "")}</small></div></td>
        </tr>)}</tbody></table></div>
        <nav className="painel33-paginacao" aria-label="Páginas do painel"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total)} de {dados.total}</span>
          <div><button type="button" disabled={deslocamento === 0 || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button>
            <button type="button" disabled={deslocamento + LIMITE >= dados.total || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></div></nav>
      </>}
    </section>
  </div>;
}
