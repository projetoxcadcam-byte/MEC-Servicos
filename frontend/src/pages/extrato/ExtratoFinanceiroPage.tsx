import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Download, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { dinheiro, estados, formas } from "../financeiro/financeiroPortal";
import { diaUTC } from "../periodo/periodoPortal";
import { dataExtrato, datasValidas, mensagemExtrato, movimentosExtrato, parametrosExtrato, periodoPadrao, tiposExtrato,
  type ConsultaExtrato, type FiltroExtrato, type FiltrosExtrato } from "./extratoPortal";
import "../periodo/RelatorioPeriodo.css";
import "./ExtratoFinanceiro.css";

const LIMITE = 20;
function efeito(valor: string) { return (Number(valor) > 0 ? "+ " : "") + dinheiro(valor); }

export default function ExtratoFinanceiroPage() {
  const { user } = useAuth(); const [parametros, setParametros] = useSearchParams();
  const filtros = useMemo<FiltrosExtrato>(() => {
    const padrao = periodoPadrao(); const temDatas = parametros.has("data_inicial") || parametros.has("data_final");
    return { data_inicial: temDatas ? parametros.get("data_inicial") ?? "" : padrao.data_inicial,
      data_final: temDatas ? parametros.get("data_final") ?? "" : padrao.data_final,
      tipo: (parametros.get("tipo") || "todos") as FiltroExtrato, busca: parametros.get("busca") || "",
      contratacao_id: parametros.has("contratacao_id") ? Number(parametros.get("contratacao_id")) : null };
  }, [parametros]);
  const [rascunho, setRascunho] = useState(filtros); const [dados, setDados] = useState<ConsultaExtrato | null>(null);
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
    void api.get<ConsultaExtrato>("/administracao/financeiro/extrato", { params: { ...parametrosExtrato(filtros), deslocamento, limite: LIMITE },
      signal: controle.signal, timeout: 20_000 }).then(({ data }) => {
      if (!vigente) return;
      if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / LIMITE) * LIMITE); return; }
      setDados(data);
    }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemExtrato(falha)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); download.current?.abort(); };
  }, [filtros, deslocamento, revisao, user?.role]);

  function aplicar(novos: FiltrosExtrato) {
    const p: Record<string, string> = { data_inicial: novos.data_inicial ?? "", data_final: novos.data_final ?? "" };
    if (novos.tipo !== "todos") p.tipo = novos.tipo;
    if (novos.busca) p.busca = novos.busca;
    if (novos.contratacao_id !== null) p.contratacao_id = String(novos.contratacao_id);
    setDeslocamento(0); setErroFormulario(""); setParametros(p); setRevisao(v => v + 1);
  }
  function consultar(e: FormEvent) {
    e.preventDefault();
    if (!datasValidas(rascunho)) { setErroFormulario("Confira as datas: o início deve ser igual ou anterior ao fim. Datas vazias deixam o período sem limite."); return; }
    aplicar({ ...rascunho, busca: rascunho.busca.trim() });
  }
  async function exportar() {
    if (!dados || carregando || baixando || user?.role !== "admin") return;
    const controle = new AbortController(); download.current = controle; setBaixando(true); setAviso("");
    try {
      const resposta = await api.get<Blob>("/administracao/financeiro/extrato/csv", { params: parametrosExtrato(dados.filtros),
        responseType: "blob", signal: controle.signal, timeout: 30_000 });
      if (controle.signal.aborted) return;
      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");
      const url = URL.createObjectURL(resposta.data); const a = document.createElement("a");
      a.href = url; a.download = "MEC_SERVICOS_EXTRATO_FINANCEIRO.csv";
      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com os totais e todos os movimentos dos filtros aplicados."); }
      finally { a.remove(); URL.revokeObjectURL(url); }
    } catch (falha: unknown) { if (!controle.signal.aborted) setAviso(mensagemExtrato(falha)); }
    finally { if (download.current === controle) { download.current = null; setBaixando(false); } }
  }

  if (user?.role !== "admin") return <p role="alert">O extrato está disponível somente para a administração.</p>;
  const r = dados?.resumo;
  return <div className="periodo35 extrato40">
    <header className="periodo35-cabecalho"><div><p className="periodo35-eyebrow">ADMINISTRAÇÃO</p><h1>Extrato de movimentações financeiras</h1>
      <p>Consulte recebimentos, repasses e estornos pelas datas em que foram registrados.</p></div>
      <nav className="periodo35-acoes" aria-label="Ações do extrato"><Link to="/admin">Painel administrativo</Link><Link to="/admin/pagamentos">Financeiro</Link>
        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>
        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" />{baixando ? "Exportando…" : "Exportar CSV"}</button></nav>
    </header>
    <section className="periodo35-card"><h2>Selecionar movimentos</h2><form className="periodo35-filtros extrato40-filtros" onSubmit={consultar}>
      <label>Data inicial (UTC)<input type="date" min="0001-01-01" max="9999-12-31" value={rascunho.data_inicial ?? ""} onChange={e => setRascunho(v => ({ ...v, data_inicial: e.target.value }))} /></label>
      <label>Data final (UTC)<input type="date" min="0001-01-01" max="9999-12-31" value={rascunho.data_final ?? ""} onChange={e => setRascunho(v => ({ ...v, data_final: e.target.value }))} /></label>
      <label>Exibir<select value={rascunho.tipo} onChange={e => setRascunho(v => ({ ...v, tipo: e.target.value as FiltroExtrato }))}>{Object.entries(tiposExtrato).map(([v, rotulo]) => <option key={v} value={v}>{rotulo}</option>)}</select></label>
      <label className="periodo35-busca">Buscar empresa, contratação ou OS<input type="search" maxLength={120} value={rascunho.busca} onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} placeholder="Ex.: oficina, Contratação #1 ou OS #3" /></label>
      <button type="submit" disabled={carregando}><Search size={16} aria-hidden="true" /> Consultar</button>
      <button type="button" disabled={carregando} onClick={() => aplicar(periodoPadrao())}>Limpar filtros</button>
      <button type="button" disabled={carregando} onClick={() => aplicar({ ...filtros, data_inicial: "", data_final: "" })}>Todo o histórico</button>
    </form>
      {rascunho.contratacao_id !== null && <p className="extrato40-selecao">Contratação selecionada: #{rascunho.contratacao_id}
        <button type="button" disabled={carregando} onClick={() => aplicar({ ...filtros, contratacao_id: null })}>Todas as contratações</button></p>}
      {erroFormulario && <p className="periodo35-erro" role="alert">{erroFormulario}</p>}
      <p className="periodo35-nota">O período usa a data de cada movimento em UTC, com os dias inicial e final incluídos. O lançamento original e seu estorno aparecem em linhas separadas, nas respectivas datas.</p>
    </section>
    {aviso && <p className="periodo35-aviso" role="status">{aviso}</p>}
    {carregando ? <p role="status">Consultando o extrato…</p> : erro ? <p className="periodo35-erro" role="alert">{erro}</p> : dados && r && <>
      <section className="periodo35-card extrato40-aplicados"><p>{diaUTC(dados.filtros.data_inicial ?? "") || "Sem início"} até {diaUTC(dados.filtros.data_final ?? "") || "Sem fim"} · {tiposExtrato[dados.filtros.tipo]} · Busca: {dados.filtros.busca || "Todas"}
        {dados.filtros.contratacao_id !== null && ` · Contratação #${dados.filtros.contratacao_id}`}</p>
        <p>{r.total_movimentos} movimento(s) em {r.total_contratacoes} contratação(ões). Consultado em {dataExtrato(dados.gerado_em)}.</p></section>
      <section className="extrato40-resumos" aria-label="Totais dos movimentos selecionados">
        <div className="periodo35-card" data-resumo="recebimentos"><h2>Recebimentos</h2><dl><dt>Registrados no período</dt><dd>{dinheiro(r.recebimentos_brutos)}</dd>
          <dt>Estornos no período</dt><dd>{dinheiro(r.estornos_recebimentos)}</dd><dt>Líquido do período</dt><dd className="extrato40-total">{dinheiro(r.recebimentos_liquidos)}</dd></dl></div>
        <div className="periodo35-card" data-resumo="repasses"><h2>Repasses</h2><dl><dt>Registrados no período</dt><dd>{dinheiro(r.repasses_brutos)}</dd>
          <dt>Estornos no período</dt><dd>{dinheiro(r.estornos_repasses)}</dd><dt>Líquido do período</dt><dd className="extrato40-total">{dinheiro(r.repasses_liquidos)}</dd></dl></div>
        <div className="periodo35-card" data-resumo="resultado"><h2>Resultado dos movimentos</h2><dl><dt>Entradas</dt><dd>{dinheiro(r.entradas)}</dd><dt>Saídas</dt><dd>{dinheiro(r.saidas)}</dd>
          <dt>Entradas menos saídas</dt><dd className="extrato40-total">{efeito(r.resultado_periodo)}</dd></dl></div>
      </section>
      <p className="periodo35-nota">Os totais abrangem todas as páginas dos filtros aplicados. Entradas incluem recebimentos e estornos de repasses; saídas incluem repasses e estornos de recebimentos. O resultado representa os registros selecionados, sem indicar saldo bancário ou lucro.</p>
      <section className="periodo35-card extrato40-movimentos"><h2>Movimentos registrados</h2>
        {!dados.total ? <p role="status">Nenhum movimento corresponde aos filtros informados.</p> : <>
          <div className="periodo35-scroll"><table><thead><tr><th>Movimento / acesso</th><th>Data UTC</th><th>Contratação / OS</th><th>Cliente / fornecedor</th><th>Forma</th><th>Valor</th><th>Efeito no resultado</th></tr></thead>
            <tbody>{dados.itens.map(c => <tr key={`${c.tipo}:${c.movimento_id}`} data-movimento={`${c.tipo}:${c.movimento_id}`}>
              <th scope="row"><strong>{movimentosExtrato[c.tipo]} #{c.movimento_id}</strong>
                <nav aria-label={`Acessos de ${movimentosExtrato[c.tipo]} ${c.movimento_id}`}><Link to={`/admin/pagamentos?contratacao=${c.contratacao_id}`}>Financeiro</Link>
                  <Link to={`/admin/relatorios?contratacao=${c.contratacao_id}`}>Relatório</Link></nav>
                <small>{c.situacao_atual === "estornado" ? "Movimento original estornado" : "Movimento confirmado"}</small></th>
              <td>{dataExtrato(c.data_utc)}{c.tipo.startsWith("estorno_") && <small>Original: {dataExtrato(c.data_original_utc)}</small>}
                {!c.tipo.startsWith("estorno_") && c.estornado_em_utc && <small>Estornado em: {dataExtrato(c.estornado_em_utc)}</small>}</td>
              <td>Contratação #{c.contratacao_id}<small>{c.ordem_servico_id ? `OS #${c.ordem_servico_id}` : "Sem ordem de serviço"}</small><small>{estados[c.financeiro_status]}</small></td>
              <td>{c.cliente}<small>{c.fornecedor}</small></td><td>{formas[c.forma_pagamento] ?? c.forma_pagamento}</td><td>{dinheiro(c.valor)}</td>
              <td className="extrato40-efeito">{efeito(c.efeito_liquido)}</td>
            </tr>)}</tbody></table></div>
          <nav className="periodo35-paginacao" aria-label="Páginas dos movimentos"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total)} de {dados.total}</span><div>
            <button type="button" disabled={carregando || deslocamento === 0} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button>
            <button type="button" disabled={carregando || deslocamento + LIMITE >= dados.total} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></div></nav>
        </>}
      </section>
    </>}
  </div>;
}
