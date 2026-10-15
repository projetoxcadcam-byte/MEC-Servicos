import { identificador } from "../painel/painelPortal";
import IntermediacaoConsulta from "../intermediacao/IntermediacaoConsulta";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Factory, History, PackageCheck, RefreshCw } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from "../client/cotacoesCliente";
import { rotuloContratacao, type PaginaContratacoes } from "../contratacoes/contratacoesPortal";
import { rotuloOrdem, type PerfilOrdens } from "../ordens/ordensPortal";
import { rotuloEtapa } from "../producao/producaoPortal";
import { mensagemErroEntrega, rotuloEntrega, type EntregasDetalhe, type OrdemEntrega } from "./entregasPortal";
import "./PortalEntregasPage.css";

function dataVisivel(valor: string | null) { return valor ? formatarInstanteCotacao(instanteUtc(valor)) : "—"; }
export default function PortalEntregasPage({ perfil }: { perfil: PerfilOrdens }) {
  const { user } = useAuth(); const empresaId = user?.role === perfil ? user.id : 0;
  const base = `/portal-${perfil}/entregas`;
  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);
  const [lista, setLista] = useState<{ chave: string; pagina: PaginaContratacoes<OrdemEntrega> } | null>(null);
  const [parametrosSelecao, setParametrosSelecao] = useSearchParams();
  const selecao = identificador(parametrosSelecao.get("ordem"));
  function setSelecao(id: number) { setParametrosSelecao(id ? { ordem: String(id) } : {}, { replace: true }); }
  const [carregando, setCarregando] = useState(true); const [erro, setErro] = useState("");
  const [detalhe, setDetalhe] = useState<{ chave: string; dados: EntregasDetalhe } | null>(null);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false); const [erroDetalhe, setErroDetalhe] = useState("");
  const chave = `${perfil}:${empresaId}:${deslocamento}:${revisao}`;
  const pagina = lista?.chave === chave ? lista.pagina : null;
  const selecionada = selecao ? pagina?.itens.find((item) => item.id === selecao) : pagina?.itens[0];
  const ordemId = selecao || selecionada?.id || 0;
  const chaveDetalhe = `${chave}:${ordemId}`;
  const dados = detalhe?.chave === chaveDetalhe ? detalhe.dados : null;
  const contexto = useRef({ chave, chaveDetalhe }); contexto.current = { chave, chaveDetalhe };
  useEffect(() => { setDeslocamento(0); }, [empresaId, perfil]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setCarregando(true); setErro("");
    if (!empresaId) { setCarregando(false); return () => controle.abort(); }
    const parametros = perfil === "cliente" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };
    void api.get<PaginaContratacoes<OrdemEntrega>>(base, { params: { ...parametros, deslocamento, limite: 20 }, signal: controle.signal, timeout: 20_000 })
      .then(({ data }) => {
        if (!vigente || contexto.current.chave !== chave) return;
        if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }
        if (!data.total && deslocamento) { setDeslocamento(0); return; }
        if (data.itens.some((item) => (perfil === "cliente" ? item.empresa_cliente_id : item.empresa_fornecedora_id) !== empresaId)) throw new Error("Empresa divergente.");
        setLista({ chave, pagina: data });
      }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted && contexto.current.chave === chave) setErro(mensagemErroEntrega(falha)); })
      .finally(() => { if (vigente && contexto.current.chave === chave) setCarregando(false); });
    return () => { vigente = false; controle.abort(); };
  }, [base, chave, empresaId, perfil, deslocamento]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setCarregandoDetalhe(Boolean(ordemId)); setErroDetalhe("");
    if (!ordemId || !empresaId) return () => controle.abort();
    const oid = ordemId; const parametros = perfil === "cliente" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };
    void api.get<EntregasDetalhe>(`${base}/${oid}`, { params: parametros, signal: controle.signal, timeout: 20_000 })
      .then(({ data }) => {
        if (!vigente || contexto.current.chaveDetalhe !== chaveDetalhe) return;
        if (data.ordem.id !== oid || (perfil === "cliente" ? data.ordem.empresa_cliente_id : data.ordem.empresa_fornecedora_id) !== empresaId
          || data.historico.some((item) => item.ordem_servico_id !== oid || item.empresa_cliente_id !== data.ordem.empresa_cliente_id || item.empresa_fornecedora_id !== data.ordem.empresa_fornecedora_id)) throw new Error("Histórico divergente.");
        setDetalhe({ chave: chaveDetalhe, dados: data });
      }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted && contexto.current.chaveDetalhe === chaveDetalhe) setErroDetalhe(mensagemErroEntrega(falha)); })
      .finally(() => { if (vigente && contexto.current.chaveDetalhe === chaveDetalhe) setCarregandoDetalhe(false); });
    return () => { vigente = false; controle.abort(); };
  }, [base, chaveDetalhe, empresaId, perfil, ordemId]);
  return <main className="p28-page"><header className="p28-header"><div><p className="p28-eyebrow"><PackageCheck size={16} /> PORTAL DO {perfil === "cliente" ? "CLIENTE" : "FORNECEDOR"}</p>
    <h1>Entregas</h1><p>Consulte o histórico das entregas da sua empresa.</p></div><button className="p28-button" disabled={carregando} onClick={() => setRevisao((v) => v + 1)}><RefreshCw size={16} /> Atualizar</button></header>
    <p className="p28-readonly">A administração coordena o material, a coleta, a avaliação das peças e a entrega final. {perfil === "fornecedor" ? "Quando terminar a produção, registre Pronto para coleta na página Produção." : "As decisões e os encaminhamentos são realizados pela administração."}</p>
    <p className="p28-readonly">Consulte o ciclo administrativo e os registros anteriores de entrega.</p>
    <nav className="p28-tabs"><Link className="p28-button" to={`/${perfil}/producao`}><Factory size={16} /> Produção</Link></nav>
    {erro && <p className="p28-alert p28-error" role="alert">{erro}</p>}
    <section className="p28-panel" aria-busy={carregando}><h2>Ordens e entregas</h2>
      {carregando ? <p role="status">Carregando ordens…</p> : pagina?.itens.length === 0 ? <p>Nenhuma ordem disponível. A administração fará o encaminhamento dos serviços.</p>
        : pagina && <div className="p28-table-wrap"><table><thead><tr><th>Ordem</th><th>{perfil === "cliente" ? "Fornecedor" : "Cliente"}</th><th>Entrega</th><th>OS</th><th>Data</th><th>Consulta</th></tr></thead><tbody>{pagina.itens.map((item) => <tr key={item.id} className={item.id === ordemId ? "p28-selected" : ""}>
          <td><strong>OS #{item.id}</strong><small>Solicitação #{item.solicitacao_id}</small></td><td>{perfil === "cliente" ? item.fornecedor_razao_social : item.cliente_razao_social}</td>
          <td>{rotuloEntrega(item.ultima_entrega_status)}</td><td>{rotuloOrdem(item.status)}</td><td>{dataVisivel(item.ultima_entrega_em)}</td>
          <td><button className="p28-button" onClick={() => setSelecao(item.id)} aria-pressed={item.id === ordemId}>Ver histórico</button></td>
        </tr>)}</tbody></table></div>}
      {pagina && pagina.total > 0 && <div className="p28-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + pagina.itens.length, pagina.total)} de {pagina.total}</span><div>
        <button className="p28-button" disabled={carregando || deslocamento === 0} onClick={() => { setSelecao(0); setDeslocamento((v) => Math.max(0, v - 20)); }}>Anterior</button>
        <button className="p28-button" disabled={carregando || deslocamento + 20 >= pagina.total} onClick={() => { setSelecao(0); setDeslocamento((v) => v + 20); }}>Próxima</button></div></div>}
    </section>
    <IntermediacaoConsulta ordemId={ordemId} perfil={perfil} revisao={revisao} />
    {ordemId > 0 && <section className="p28-panel" aria-busy={carregandoDetalhe}><h2><History size={20} /> Histórico da OS #{ordemId}</h2>
      {carregandoDetalhe ? <p role="status">Carregando histórico…</p> : erroDetalhe ? <p role="alert">{erroDetalhe}</p> : dados && <>
        <dl className="p28-fields"><div><dt>Valor total</dt><dd>{formatarValorCotacao(dados.ordem.valor_total)}</dd></div><div><dt>Prazo</dt><dd>{dados.ordem.prazo_dias} dias</dd></div>
          <div><dt>Contratação</dt><dd>#{dados.ordem.contratacao_id} · {rotuloContratacao(dados.ordem.contratacao_status)}</dd></div><div><dt>Produção</dt><dd>{rotuloEtapa(dados.ordem.etapa_atual)}</dd></div></dl>
        {dados.historico.length === 0 ? <p>Sem registro anterior de entrega.</p> : <ol className="p28-timeline">{dados.historico.slice().reverse().map((entrega) => <li key={entrega.id}><article>
          <h3>Entrega #{entrega.id} · {rotuloEntrega(entrega.status)}</h3><p>Registro: {dataVisivel(entrega.entregue_em)}</p>
          {entrega.aceita_em && <p>Aceite registrado no histórico: {dataVisivel(entrega.aceita_em)}</p>}{entrega.recusada_em && <p>Recusa registrada no histórico: {dataVisivel(entrega.recusada_em)}</p>}
        </article></li>)}</ol>}
      </>}
    </section>}
  </main>;
}
