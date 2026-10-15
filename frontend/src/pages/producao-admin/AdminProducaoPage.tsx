import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { rotuloEtapa, type EtapaProducao } from "../producao/producaoPortal";
import { dataJanela, numeroUrl, numeroValido, useConsultaJanela } from "../janelas/janelasPortal";
import "../janelas/Janelas.css";

type Ordem = { id: number; solicitacao_id: number; ordem_servico_id: number; empresa_cliente_id: number;
  empresa_fornecedora_id: number; cliente: string; fornecedor: string; quantidade: number;
  processo: string; material: string; ordem_status: string; etapa_administrativa: string | null };
type Pagina = { total: number; itens: Ordem[] };
type Historico = { ordem_servico_id: number; etapa_atual: string | null; historico: EtapaProducao[] };
const SITUACOES: Record<string, string> = { aberta: "Aberta", em_execucao: "Em execução", concluida: "Concluída", cancelada: "Cancelada" };

export default function AdminProducaoPage() {
  const { user } = useAuth();
  if (!user || user.role !== "admin") return <main className="jan57">Acompanhamento disponível somente para a administração.</main>;
  return <Conteudo key={`${user.usuario_id}:${user.role}`} contexto={`${user.usuario_id}:${user.role}`} />;
}

function Conteudo({ contexto }: { contexto: string }) {
  const [url, setUrl] = useSearchParams();
  const filtro = { ordem: numeroUrl(url.get("ordem")), solicitacao: numeroUrl(url.get("solicitacao")), contratacao: numeroUrl(url.get("contratacao")), situacao: SITUACOES[url.get("situacao") ?? ""] ? url.get("situacao")! : "" };
  const filtroChave = JSON.stringify(filtro);
  const [rascunho, setRascunho] = useState(filtro);
  const [erroFiltro, setErroFiltro] = useState("");
  const [pagina, setPagina] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [selecao, setSelecao] = useState<{ chave: string; ordem: number; abertura: number } | null>(null);
  const chave = `${contexto}:${filtroChave}:${pagina}:${revisao}`;
  useEffect(() => { setSelecao(null); }, [chave]);
  const consulta = useConsultaJanela<Pagina>("/administracao/ordens-servico", chave, { deslocamento: pagina * 20, limite: 20,
    ...(filtro.ordem ? { ordem_servico_id: Number(filtro.ordem) } : {}), ...(filtro.solicitacao ? { solicitacao_id: Number(filtro.solicitacao) } : {}),
    ...(filtro.contratacao ? { contratacao_id: Number(filtro.contratacao) } : {}), ...(filtro.situacao ? { status: filtro.situacao } : {}) });
  useEffect(() => { setRascunho(JSON.parse(filtroChave)); setPagina(0); setErroFiltro(""); }, [filtroChave]);
  useEffect(() => { if (consulta.dados?.total && pagina * 20 >= consulta.dados.total) setPagina(Math.floor((consulta.dados.total - 1) / 20)); }, [consulta.dados, pagina]);
  const selecionada = consulta.dados?.itens.find(o => o.ordem_servico_id === (selecao?.chave === chave ? selecao.ordem : filtro.ordem ? Number(filtro.ordem) : 0));
  function consultar(e: FormEvent) {
    e.preventDefault();
    if (![rascunho.ordem, rascunho.solicitacao, rascunho.contratacao].every(v => numeroValido(v.trim()))) { setErroFiltro("Informe números de OS, solicitação e contratação maiores que zero."); return; }
    setUrl(Object.fromEntries(Object.entries(rascunho).map(([k,v]) => [k,v.trim()]).filter(([,v]) => v))); setPagina(0); setRevisao(v => v + 1); setErroFiltro("");
  }
  return <main className="jan57 jan57-producao"><header className="jan57-header"><div><h1>Acompanhamento de produção</h1><p>Consulte a produção de todas as oficinas e o histórico de cada ordem de serviço.</p></div><button onClick={() => setRevisao(v => v + 1)}>Atualizar produção</button></header>
    <nav className="jan57-nav"><Link to="/admin/ordens-servico">Ordens de serviço</Link><Link to="/admin/intermediacao">Entregas e intermediação</Link></nav>
    <form className="jan57-filtros" onSubmit={consultar}>{([ ["ordem","OS #"], ["solicitacao","Solicitação #"], ["contratacao","Contratação #"] ] as const).map(([campo,nome]) => <label key={campo}>{nome}<input aria-label={nome} inputMode="numeric" maxLength={13} value={rascunho[campo]} onChange={e => setRascunho(v => ({ ...v, [campo]: e.target.value }))} /></label>)}
      <label>Situação da OS<select aria-label="Situação da OS" value={rascunho.situacao} onChange={e => setRascunho(v => ({ ...v, situacao: e.target.value }))}><option value="">Todas</option>{Object.entries(SITUACOES).map(([v,n]) => <option key={v} value={v}>{n}</option>)}</select></label><button>Consultar produção</button><button type="button" onClick={() => { setUrl({}); setPagina(0); setRevisao(v => v + 1); }}>Limpar filtros</button></form>
    {(erroFiltro || consulta.erro) && <p role="alert" className="jan57-erro">{erroFiltro || consulta.erro}</p>}{consulta.carregando && <p role="status">Consultando ordens de serviço…</p>}
    {consulta.dados && <><p>{consulta.dados.total} ordens de serviço · até 20 por página</p>{!consulta.dados.itens.length ? <p>Nenhuma OS encontrada para estes filtros.</p> : <div className="jan57-tabela"><table><thead><tr><th>OS / contratação</th><th>Cliente / fornecedor</th><th>Processo / material</th><th>Situação</th><th>Acompanhamento</th></tr></thead><tbody>{consulta.dados.itens.map(o => <tr key={o.ordem_servico_id} className={selecionada?.ordem_servico_id === o.ordem_servico_id ? "selecionada" : ""}><td><strong>OS #{o.ordem_servico_id}</strong><small>Contratação #{o.id} · Solicitação #{o.solicitacao_id}</small></td><td>{o.cliente}<small>{o.fornecedor} · F-{o.empresa_fornecedora_id}</small></td><td>{o.processo}<small>{o.material} · {o.quantidade} unidades</small></td><td>{SITUACOES[o.ordem_status] ?? o.ordem_status}</td><td><button onClick={() => setSelecao(v => ({ chave, ordem: o.ordem_servico_id, abertura: (v?.abertura ?? 0) + 1 }))}>Ver produção da OS #{o.ordem_servico_id}</button></td></tr>)}</tbody></table></div>}
      <nav className="jan57-paginacao" aria-label="Páginas da produção"><button disabled={pagina === 0} onClick={() => setPagina(v => v - 1)}>Anterior</button><span>{consulta.dados.total ? `${pagina * 20 + 1}–${Math.min(pagina * 20 + 20, consulta.dados.total)} de ${consulta.dados.total}` : "0 resultados"}</span><button disabled={(pagina + 1) * 20 >= consulta.dados.total} onClick={() => setPagina(v => v + 1)}>Próxima</button></nav></>}
    {selecionada && <Detalhe key={`${chave}:${selecionada.ordem_servico_id}:${selecao?.abertura ?? 0}`} ordem={selecionada} contexto={contexto} />}
  </main>;
}

function Detalhe({ ordem, contexto }: { ordem: Ordem; contexto: string }) {
  const [revisao, setRevisao] = useState(0); const ref = useRef<HTMLElement>(null);
  const consulta = useConsultaJanela<Historico>(`/ordens-servico/${ordem.ordem_servico_id}/acompanhamento-producao`, `${contexto}:${ordem.ordem_servico_id}:${revisao}`);
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth", block: "start" }); ref.current?.focus({ preventScroll: true }); }, []);
  const valida = consulta.dados?.ordem_servico_id === ordem.ordem_servico_id && consulta.dados.historico.every(e => e.ordem_servico_id === ordem.ordem_servico_id && e.empresa_fornecedora_id === ordem.empresa_fornecedora_id);
  const dados = valida ? consulta.dados : null;
  return <section className="jan57-detalhe" ref={ref} tabIndex={-1} aria-label={`Produção da OS #${ordem.ordem_servico_id}`}><div className="jan57-header"><h2>Produção da OS #{ordem.ordem_servico_id}</h2><button onClick={() => setRevisao(v => v + 1)}>Atualizar histórico da produção</button></div><p>{ordem.fornecedor} · Contratação #{ordem.id} · Solicitação #{ordem.solicitacao_id}</p>
    <nav className="jan57-nav"><Link to={`/admin/ordens-servico?ordem=${ordem.ordem_servico_id}`}>Abrir ordem de serviço</Link><Link to={`/admin/intermediacao?ordem=${ordem.ordem_servico_id}`}>Acompanhar entrega desta OS</Link></nav>
    {(consulta.erro || consulta.dados && !valida) && <p role="alert" className="jan57-erro">{consulta.erro || "A resposta não corresponde à OS selecionada. Atualize o histórico."}</p>}{consulta.carregando && <p role="status">Consultando etapas da produção…</p>}
    {dados && <><div className="jan57-resumo"><div><small>Situação da OS</small><strong>{SITUACOES[ordem.ordem_status] ?? ordem.ordem_status}</strong></div><div><small>Etapa da produção</small><strong>{rotuloEtapa(dados.etapa_atual)}</strong></div><div><small>Última atualização</small><strong>{dataJanela(dados.historico.at(-1)?.criada_em)}</strong></div></div><h3>Histórico de produção · {dados.historico.length} atualizações</h3>{!dados.historico.length ? <p>Nenhuma etapa de produção registrada para esta OS.</p> : <ol className="jan57-historico">{dados.historico.map(e => <li key={e.id}><strong>{rotuloEtapa(e.etapa)}</strong><time dateTime={e.criada_em}>{dataJanela(e.criada_em)}</time><small>Fornecedor F-{e.empresa_fornecedora_id} · Registro #{e.id}</small>{e.observacoes && <p>{e.observacoes}</p>}</li>)}</ol>}</>}
  </section>;
}
