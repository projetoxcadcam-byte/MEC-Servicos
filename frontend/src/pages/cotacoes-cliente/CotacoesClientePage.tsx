import { useEffect, useRef, useState } from "react";
import { FileText, RefreshCw, Search, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { dataJanela } from "../janelas/janelasPortal";
import { formatarValorCotacao, rotuloStatusCotacao } from "../client/cotacoesCliente";
import { detalheValido, filtrosValidos, paginaValida, useConsultaCotacoes, type DetalheCotacao, type FiltrosCotacoes, type PaginaCotacoes } from "./consultaCotacoes";
import AnaliseOrcamentoCliente from "../formacao-preco/AnaliseOrcamentoCliente";
import {rotuloAnalise} from "../formacao-preco/preco";
import "../client/ClientCotacoesPage.css";
import "./CotacoesCliente.css";

const LIMITE = 20;
export default function CotacoesClientePage() {
  const { user } = useAuth();
  const empresa = user?.role === "cliente" ? user.empresa_id ?? 0 : 0;
  const contexto = empresa && user ? `${user.usuario_id}:cliente:${empresa}` : "";
  const [url, setUrl] = useSearchParams();
  const filtros: FiltrosCotacoes = { solicitacao: url.get("solicitacao") ?? "", cotacao: url.get("cotacao") ?? "",
    situacao: url.get("situacao") ?? "todas", ordenacao: url.get("ordenacao") ?? "recentes" };
  const valorInicio = url.get("inicio") ?? "0";
  const inicioValido = /^(?:0|[1-9]\d{0,6})$/.test(valorInicio) && Number(valorInicio) <= 1_000_000;
  const inicio = inicioValido ? Number(valorInicio) : 0;
  const filtrosJson = JSON.stringify(filtros), chaveBase = `${contexto}:${filtrosJson}:${inicio}`;
  const [rascunho, setRascunho] = useState<FiltrosCotacoes>(filtros);
  const [erroFormulario, setErroFormulario] = useState("");
  const [atualizacao, setAtualizacao] = useState(0);
  const [selecao, setSelecao] = useState<{ chave: string; id: number } | null>(null);
  const [revisaoDetalhe, setRevisaoDetalhe] = useState(0);
  const refDetalhe = useRef<HTMLElement | null>(null);
  const consultaValida = filtrosValidos(filtros) && inicioValido;
  const parametros: Record<string, string | number> = { empresa_cliente_id: empresa, situacao: filtros.situacao,
    ordenacao: filtros.ordenacao, deslocamento: inicio, limite: LIMITE };
  if (filtros.solicitacao) parametros.solicitacao_id = filtros.solicitacao;
  if (filtros.cotacao) parametros.cotacao_id = filtros.cotacao;
  const pagina = useConsultaCotacoes<PaginaCotacoes>(empresa && consultaValida ? "/portal-cliente/cotacoes" : null,
    `${chaveBase}:${atualizacao}`, contexto, parametros, p => paginaValida(p, contexto, empresa, filtros, inicio, LIMITE));
  const selecionada = pagina.dados?.itens.find(c => c.id === (selecao?.chave === chaveBase ? selecao.id : Number(filtros.cotacao)));
  const detalhe = useConsultaCotacoes<DetalheCotacao>(selecionada ? `/portal-cliente/cotacoes/${selecionada.id}` : null,
    `${chaveBase}:${atualizacao}:${selecionada?.id ?? 0}:${revisaoDetalhe}`, contexto, { empresa_cliente_id: empresa },
    p => !!selecionada && detalheValido(p, contexto, empresa, selecionada));
  useEffect(() => { setRascunho(JSON.parse(filtrosJson)); setErroFormulario(""); }, [filtrosJson, contexto]);
  useEffect(() => { if (detalhe.dados) { refDetalhe.current?.focus(); refDetalhe.current?.scrollIntoView({ behavior: "smooth", block: "start" }); } }, [detalhe.dados]);
  if (!empresa || !contexto) return <main className="c23-page c59"><p role="alert">Entre como cliente para consultar as cotações da sua empresa.</p></main>;
  function gravarFiltros(f: FiltrosCotacoes, proximoInicio = 0) {
    const p: Record<string, string> = {};
    if (f.solicitacao) p.solicitacao = f.solicitacao;
    if (f.cotacao) p.cotacao = f.cotacao;
    if (f.situacao !== "todas") p.situacao = f.situacao;
    if (f.ordenacao !== "recentes") p.ordenacao = f.ordenacao;
    if (proximoInicio) p.inicio = String(proximoInicio);
    setSelecao(null); setUrl(p, { replace: true });
  }
  function consultar(e: React.FormEvent) {
    e.preventDefault();
    if (!filtrosValidos(rascunho)) { setErroFormulario("Informe somente números positivos de solicitação e cotação e selecione filtros válidos."); return; }
    setErroFormulario(""); gravarFiltros(rascunho); setAtualizacao(v => v + 1);
  }
  const total = pagina.dados?.total;
  const dados = detalhe.dados?.item;
  return <main className="c23-page c59" aria-busy={pagina.carregando}>
    <header className="c23-header"><div><div className="c23-eyebrow"><FileText size={16} /> PORTAL DO CLIENTE</div><h1>Cotações recebidas</h1>
      <p>Consulte as propostas e acompanhe as decisões da administração.</p></div>
      <button className="c23-button" disabled={pagina.carregando} onClick={() => setAtualizacao(v => v + 1)}><RefreshCw size={16} />Atualizar cotações</button></header>
    <p className="c23-alert">A administração registra a decisão sobre as propostas e coordena a contratação do serviço.</p>
    <form className="c23-panel c59-filtros" onSubmit={consultar}><label>Solicitação #<input aria-label="Solicitação #" inputMode="numeric" value={rascunho.solicitacao} onChange={e => setRascunho({ ...rascunho, solicitacao: e.target.value })} placeholder="Todas" /></label>
      <label>Cotação #<input aria-label="Cotação #" inputMode="numeric" value={rascunho.cotacao} onChange={e => setRascunho({ ...rascunho, cotacao: e.target.value })} placeholder="Todas" /></label>
      <label>Situação<select aria-label="Situação" value={rascunho.situacao} onChange={e => setRascunho({ ...rascunho, situacao: e.target.value })}>
        <option value="todas">Todas</option><option value="enviada">Aguardando decisão</option><option value="aceita">Aceitas</option><option value="recusada">Recusadas</option><option value="expirada">Expiradas</option><option value="cancelada">Canceladas</option></select></label>
      <label>Ordenação<select aria-label="Ordenação" value={rascunho.ordenacao} onChange={e => setRascunho({ ...rascunho, ordenacao: e.target.value })}>
        <option value="recentes">Mais recentes</option><option value="valor">Menor valor</option><option value="prazo">Menor prazo</option></select></label>
      <button className="c23-button c23-primary" disabled={pagina.carregando}><Search size={16} />Consultar cotações</button>
      <button className="c23-button" type="button" onClick={() => { gravarFiltros({ solicitacao: "", cotacao: "", situacao: "todas", ordenacao: "recentes" }); setRascunho({ solicitacao: "", cotacao: "", situacao: "todas", ordenacao: "recentes" }); setErroFormulario(""); setAtualizacao(v => v + 1); }}>Limpar filtros</button>
    </form>
    {(erroFormulario || !consultaValida) && <div className="c23-alert c23-alert-error" role="alert">{erroFormulario || "O endereço contém filtros inválidos. Confira os números e consulte novamente."}</div>}
    <div className="c23-metrics" aria-label="Totais com os filtros atuais">{[
      ["Cotações encontradas", total], ["Aguardando decisão", pagina.dados ? pagina.dados.por_status.enviada ?? 0 : undefined],
      ["Aceitas", pagina.dados ? pagina.dados.por_status.aceita ?? 0 : undefined], ["Expiradas", pagina.dados ? pagina.dados.por_status.expirada ?? 0 : undefined],
    ].map(([nome, valor]) => <article key={nome}><span>{nome}</span><strong>{valor ?? "—"}</strong><small>Com os filtros atuais, em todas as páginas</small></article>)}</div>
    <section className="c23-panel c59-listagem"><div className="c23-toolbar"><div><h2>Propostas recebidas</h2><p>Orçamentos publicados pela administração, com o preço final para análise.</p></div></div>
      {pagina.erro ? <p className="c23-empty" role="alert">{pagina.erro}</p> : pagina.carregando ? <p className="c23-empty" role="status">Consultando cotações…</p> :
        pagina.dados?.itens.length === 0 ? <div className="c23-empty"><p>Nenhuma cotação encontrada nesta página.</p>{inicio > 0 && <button className="c23-button" onClick={() => gravarFiltros(filtros)}>Voltar à primeira página</button>}</div> :
          pagina.dados && <div className="c23-table-scroll"><table><caption className="c23-sr">Cotações recebidas pela empresa cliente</caption><thead><tr><th>Proposta</th><th>Valor total</th><th>Prazo</th><th>Validade até</th><th>Situação</th><th>Consulta</th></tr></thead><tbody>{pagina.dados.itens.map(c =>
            <tr key={c.id}><td><strong>Cotação #{c.id}</strong><small>Solicitação #{c.solicitacao_id} · Fornecedor F-{String(c.empresa_fornecedora_id).padStart(4, "0")}</small></td><td>{formatarValorCotacao(c.valor_total)}</td>
              <td>{c.prazo_dias} dias</td><td>{dataJanela(c.vencimento_em)}</td><td><span className={`c23-badge c23-status-${c.status === "aceita" ? "success" : c.status === "enviada" ? "pending" : "closed"}`}>{rotuloStatusCotacao(c.status)}</span>{c.analise_cliente&&<small>{rotuloAnalise[c.analise_cliente]}</small>}</td>
              <td><button className="c23-button c23-small" aria-pressed={selecionada?.id === c.id} onClick={() => setSelecao({ chave: chaveBase, id: c.id })} aria-label={`Ver detalhes da cotação #${c.id}`}>Ver detalhes</button></td></tr>)}</tbody></table></div>}
      <div className="c59-paginacao"><button className="c23-button" disabled={pagina.carregando || inicio === 0 || !pagina.dados} onClick={() => gravarFiltros(filtros, Math.max(0, inicio - LIMITE))}>Anterior</button>
        <span>{pagina.dados ? `${pagina.dados.itens.length ? inicio + 1 : 0}–${pagina.dados.itens.length ? inicio + pagina.dados.itens.length : 0} de ${total} cotações` : "Aguardando consulta"}</span>
        <button className="c23-button" disabled={pagina.carregando || !pagina.dados || inicio + LIMITE >= pagina.dados.total} onClick={() => gravarFiltros(filtros, inicio + LIMITE)}>Próxima</button></div>
    </section>
    {selecionada && <section className="c23-panel c59-detalhe" tabIndex={-1} ref={refDetalhe} aria-label={`Detalhes da cotação #${selecionada.id}`} aria-busy={detalhe.carregando}>
      <div className="c59-cabecalho-detalhe"><h2>Detalhes da cotação #{selecionada.id}</h2><button className="c23-button" onClick={() => setRevisaoDetalhe(v => v + 1)} disabled={detalhe.carregando}>Atualizar detalhes</button>
        <button className="c23-button" aria-label="Fechar detalhes" onClick={() => { setSelecao({ chave: chaveBase, id: 0 }); }}><X size={16} /></button></div>
      {detalhe.erro ? <p role="alert">{detalhe.erro}</p> : detalhe.carregando ? <p role="status">Consultando detalhes…</p> : dados && <>
        <dl className="c59-campos"><div><dt>Solicitação</dt><dd>#{dados.solicitacao_id}</dd></div><div><dt>Fornecedor</dt><dd>F-{String(dados.empresa_fornecedora_id).padStart(4, "0")}</dd></div>
          <div><dt>Valor total</dt><dd>{formatarValorCotacao(dados.valor_total)}</dd></div><div><dt>Situação</dt><dd>{rotuloStatusCotacao(dados.status)}</dd></div>
          <div><dt>Prazo de execução</dt><dd>{dados.prazo_dias} dias</dd></div><div><dt>Validade da oferta</dt><dd>{dados.validade_dias} dias · até {dataJanela(dados.vencimento_em)}</dd></div>
          <div><dt>Processo</dt><dd>{dados.processo_nome}</dd></div><div><dt>Material</dt><dd>{dados.material_nome}</dd></div><div><dt>Quantidade</dt><dd>{dados.quantidade} unidades</dd></div>
          <div><dt>Proposta enviada em</dt><dd>{dataJanela(dados.criada_em)}</dd></div><div><dt>Contratação</dt><dd>{dados.contratacao_id ? `#${dados.contratacao_id}` : "Ainda não registrada"}</dd></div>
          <div><dt>Ordem de serviço</dt><dd>{dados.ordem_servico_id ? `#${dados.ordem_servico_id}` : "Ainda não registrada"}</dd></div></dl>
        <AnaliseOrcamentoCliente key={`${contexto}:${dados.id}:${dados.versao_preco??dados.analise_cliente}`} cotacao={dados} aoRegistrar={()=>{setAtualizacao(v=>v+1);setRevisaoDetalhe(v=>v+1);}}/>
        {dados.ordem_servico_id && <Link className="c23-link" to={`/cliente/producao?ordem=${dados.ordem_servico_id}`}>Acompanhar produção da OS #{dados.ordem_servico_id}</Link>}
        <p className="c59-horario">Detalhes consultados em {dataJanela(detalhe.dados?.consultado_em)}.</p></>}
    </section>}
    {pagina.dados && <p className="c59-horario">Consulta em {dataJanela(pagina.dados.consultado_em)}. A validade é conferida no momento da consulta.</p>}
    <nav className="c59-atalhos" aria-label="Atalhos de cotações"><Link className="c23-link" to="/cliente">Dashboard</Link><Link className="c23-link" to="/cliente/solicitacoes">Minhas solicitações</Link><Link className="c23-link" to="/cliente/arquivos-tecnicos">Arquivos técnicos</Link><Link className="c23-link" to="/cliente/contratacoes">Contratações</Link></nav>
  </main>;
}
