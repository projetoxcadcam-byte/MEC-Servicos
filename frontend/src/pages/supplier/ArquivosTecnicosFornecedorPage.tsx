import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { erroJanela, numeroUrl, numeroValido, useConsultaJanela } from "../janelas/janelasPortal";
import { formatarTamanhoArquivo, type ArquivoFornecedor, type CotacaoFornecedor, type PaginaFornecedor, type SolicitacaoFornecedor } from "./cotacoesFornecedor";
import "../janelas/Janelas.css";

type Linha = { solicitacao: SolicitacaoFornecedor; cotacao: CotacaoFornecedor | null };
const SITUACOES: Record<string, string> = { enviada: "Aguardando decisão", aceita: "Aceita", recusada: "Recusada", expirada: "Expirada", cancelada: "Cancelada" };

export default function ArquivosTecnicosFornecedorPage() {
  const { user } = useAuth();
  if (!user || user.role !== "fornecedor" || !user.empresa_id) return <main className="jan57">Entre como fornecedor para consultar os documentos da sua empresa.</main>;
  const contexto = `${user.usuario_id}:${user.role}:${user.empresa_id}`;
  return <Conteudo key={contexto} contexto={contexto} empresa={user.empresa_id} />;
}

function Conteudo({ contexto, empresa }: { contexto: string; empresa: number }) {
  const [url, setUrl] = useSearchParams();
  const modo = url.get("aba") === "oportunidades" ? "oportunidades" : "cotacoes";
  const sid = numeroUrl(url.get("solicitacao"));
  const [texto, setTexto] = useState(sid); const [erroFiltro, setErroFiltro] = useState("");
  const [pagina, setPagina] = useState(0); const [revisao, setRevisao] = useState(0);
  const [selecao, setSelecao] = useState<{ chave: string; id: number; abertura: number } | null>(null);
  const chave = `${contexto}:${modo}:${sid}:${pagina}:${revisao}`;
  useEffect(() => { setSelecao(null); }, [chave]);
  const consulta = useConsultaJanela<PaginaFornecedor<SolicitacaoFornecedor | CotacaoFornecedor>>(`/portal-fornecedor/${modo}`, chave,
    { empresa_fornecedora_id: empresa, deslocamento: pagina * 20, limite: 20, ...(sid ? { solicitacao_id: Number(sid) } : {}), ...(modo === "cotacoes" ? { somente_leitura: true } : {}) });
  useEffect(() => { setTexto(sid); setPagina(0); setErroFiltro(""); }, [sid, modo]);
  useEffect(() => { if (consulta.dados?.total && pagina * 20 >= consulta.dados.total) setPagina(Math.floor((consulta.dados.total - 1) / 20)); }, [consulta.dados, pagina]);
  const linhas: Linha[] = consulta.dados?.itens.flatMap<Linha>(item => {
    if (modo === "oportunidades") return [{ solicitacao: item as SolicitacaoFornecedor, cotacao: null }];
    const q = item as CotacaoFornecedor;
    return q.empresa_fornecedora_id === empresa && q.solicitacao_id === q.solicitacao.id ? [{ solicitacao: q.solicitacao, cotacao: q }] : [];
  }) ?? [];
  const divergente = consulta.dados && linhas.length !== consulta.dados.itens.length;
  const selecionada = !divergente && linhas.find(l => l.solicitacao.id === (selecao?.chave === chave ? selecao.id : sid ? Number(sid) : 0));
  function consultar(e: FormEvent) {
    e.preventDefault(); if (!numeroValido(texto.trim())) { setErroFiltro("Informe um número de solicitação maior que zero."); return; }
    setUrl({ aba: modo, ...(texto.trim() ? { solicitacao: texto.trim() } : {}) }); setPagina(0); setRevisao(v => v + 1); setErroFiltro("");
  }
  return <main className="jan57 jan57-documentos"><header className="jan57-header"><div><h1>Arquivos técnicos</h1><p>Localize os documentos liberados para sua empresa nas oportunidades e cotações.</p></div><button onClick={() => setRevisao(v => v + 1)}>Atualizar documentos</button></header>
    <nav className="jan57-nav"><Link to="/fornecedor/solicitacoes">Oportunidades para cotar</Link><Link to="/fornecedor/cotacoes">Minhas cotações</Link><Link to="/fornecedor/producao">Minha produção</Link></nav>
    <div className="jan57-abas" aria-label="Origem das solicitações"><button aria-pressed={modo === "cotacoes"} onClick={() => { setUrl({ aba: "cotacoes", ...(sid ? { solicitacao: sid } : {}) }); setPagina(0); }}>Cotações e serviços</button><button aria-pressed={modo === "oportunidades"} onClick={() => { setUrl({ aba: "oportunidades", ...(sid ? { solicitacao: sid } : {}) }); setPagina(0); }}>Oportunidades liberadas</button></div>
    <form className="jan57-filtros" onSubmit={consultar}><label>Solicitação #<input aria-label="Solicitação #" inputMode="numeric" maxLength={13} value={texto} onChange={e => setTexto(e.target.value)} /></label><button>Consultar documentos</button><button type="button" onClick={() => { setUrl({ aba: modo }); setPagina(0); setRevisao(v => v + 1); }}>Limpar busca</button></form>
    <p className="jan57-aviso">Os arquivos ficam disponíveis após a revisão e liberação da administração. A versão preparada com a identificação MEC é utilizada quando publicada.</p>
    {(erroFiltro || consulta.erro || divergente) && <p role="alert" className="jan57-erro">{erroFiltro || consulta.erro || "A resposta não corresponde à empresa deste acesso. Atualize a lista."}</p>}
    {consulta.carregando && <p role="status">Consultando solicitações com documentos…</p>}
    {consulta.dados && !divergente && <><p>{consulta.dados.total} solicitações · até 20 por página</p>{!linhas.length ? <p>Nenhuma solicitação encontrada nesta consulta.</p> : <div className="jan57-tabela"><table><thead><tr><th>Solicitação / cotação</th><th>Processo / material</th><th>Quantidade</th><th>Documentação</th></tr></thead><tbody>{linhas.map(l => <tr key={l.solicitacao.id} className={selecionada && selecionada.solicitacao.id === l.solicitacao.id ? "selecionada" : ""}><td><strong>Solicitação #{l.solicitacao.id}</strong><small>{l.cotacao ? `Cotação #${l.cotacao.id} · ${SITUACOES[l.cotacao.status] ?? l.cotacao.status}` : "Oportunidade liberada para cotação"}</small></td><td>{l.solicitacao.processo_nome}<small>{l.solicitacao.material_nome}</small></td><td>{l.solicitacao.quantidade} unidades</td><td><button onClick={() => setSelecao(v => ({ chave, id: l.solicitacao.id, abertura: (v?.abertura ?? 0) + 1 }))}>Ver arquivos da solicitação #{l.solicitacao.id}</button></td></tr>)}</tbody></table></div>}
      <nav className="jan57-paginacao" aria-label="Páginas das solicitações com documentos"><button disabled={pagina === 0} onClick={() => setPagina(v => v - 1)}>Anterior</button><span>{consulta.dados.total ? `${pagina * 20 + 1}–${Math.min(pagina * 20 + 20, consulta.dados.total)} de ${consulta.dados.total}` : "0 resultados"}</span><button disabled={(pagina + 1) * 20 >= consulta.dados.total} onClick={() => setPagina(v => v + 1)}>Próxima</button></nav></>}
    {selecionada && <DetalheArquivos key={`${chave}:${selecionada.solicitacao.id}:${selecao?.abertura ?? 0}`} linha={selecionada} empresa={empresa} contexto={contexto} />}
  </main>;
}

function DetalheArquivos({ linha, empresa, contexto }: { linha: Linha; empresa: number; contexto: string }) {
  const sid = linha.solicitacao.id; const [revisao, setRevisao] = useState(0); const [baixando, setBaixando] = useState<number | null>(null);
  const [erroDownload, setErroDownload] = useState(""); const download = useRef<AbortController | null>(null); const urls = useRef(new Set<string>()); const ref = useRef<HTMLElement>(null);
  const consulta = useConsultaJanela<ArquivoFornecedor[]>(`/portal-fornecedor/solicitacoes/${sid}/arquivos`, `${contexto}:${sid}:${revisao}`, { empresa_fornecedora_id: empresa });
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth", block: "start" }); ref.current?.focus({ preventScroll: true }); return () => { download.current?.abort(); for (const url of urls.current) URL.revokeObjectURL(url); urls.current.clear(); }; }, []);
  const valida = consulta.dados?.every(a => a.solicitacao_id === sid && a.ativo && Number.isInteger(a.id) && a.id > 0);
  const arquivos = valida ? consulta.dados : null;
  async function baixar(a: ArquivoFornecedor) {
    if (download.current || !arquivos?.some(v => v.id === a.id)) return;
    const controle = new AbortController(); download.current = controle; setBaixando(a.id); setErroDownload("");
    try {
      const { data } = await api.get<Blob>(`/portal-fornecedor/arquivos/${a.id}/download`, { params: { empresa_fornecedora_id: empresa }, responseType: "blob", signal: controle.signal, timeout: 60_000 });
      if (controle.signal.aborted) return;
      const url = URL.createObjectURL(data); urls.current.add(url); const link = document.createElement("a");
      link.href = url; link.download = `arquivo-tecnico-${a.id}${/^\.[a-z0-9]{1,10}$/i.test(a.extensao) ? a.extensao : ".bin"}`; document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => { URL.revokeObjectURL(url); urls.current.delete(url); }, 30_000);
    } catch (e) { if (!controle.signal.aborted) setErroDownload(erroJanela(e)); }
    finally { if (download.current === controle) download.current = null; if (!controle.signal.aborted) setBaixando(null); }
  }
  return <section className="jan57-detalhe" ref={ref} tabIndex={-1} aria-label={`Arquivos da solicitação #${sid}`}><div className="jan57-header"><h2>Arquivos da solicitação #{sid}</h2><button disabled={baixando !== null} onClick={() => { setErroDownload(""); setRevisao(v => v + 1); }}>Atualizar arquivos liberados</button></div>
    <p>{linha.solicitacao.processo_nome} · {linha.solicitacao.material_nome} · {linha.solicitacao.quantidade} unidades</p><Link to={`/fornecedor/${linha.cotacao ? "cotacoes" : "solicitacoes"}?solicitacao=${sid}`}>{linha.cotacao ? "Abrir minha cotação" : "Abrir oportunidade para cotar"}</Link>
    {(consulta.erro || erroDownload || consulta.dados && !valida) && <p role="alert" className="jan57-erro">{consulta.erro || erroDownload || "A resposta não corresponde à solicitação selecionada. Atualize os arquivos."}</p>}
    {consulta.carregando && <p role="status">Consultando arquivos liberados…</p>}
    {arquivos && <><p>{arquivos.length} arquivos liberados para consulta</p>{!arquivos.length ? <p>Nenhum documento liberado disponível. Confira a revisão com a administração.</p> : arquivos.map(a => <article className="jan57-arquivo" key={a.id}><div><strong>Arquivo técnico #{a.id}</strong><small>{a.extensao.toUpperCase().replace(".", "")} · {formatarTamanhoArquivo(a.tamanho_bytes)}</small></div><button disabled={baixando !== null} onClick={() => void baixar(a)}>{baixando === a.id ? "Baixando…" : `Baixar arquivo #${a.id}`}</button></article>)}</>}
  </section>;
}
