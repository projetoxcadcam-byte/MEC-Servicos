import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import FormacaoPrecoAdmin from "../formacao-preco/FormacaoPrecoAdmin";
import {rotuloAnalise} from "../formacao-preco/preco";
import ComparacaoCotacoesAdmin from "./ComparacaoCotacoesAdmin";
import "./ComercialAdmin.css";

type Modo = "solicitacoes" | "cotacoes";
type Solicitacao = {
  id: number; empresa_cliente_id: number; cliente: string; processo: string; material: string;
  dimensao_x_maxima_mm: string; dimensao_y_maxima_mm: string; dimensao_z_maxima_mm: string;
  tolerancia_requerida_mm: string; quantidade: number; observacoes: string | null; status: string;
  criada_em: string; cotacoes_total: number; cotacoes_aceitas: number; arquivos_ativos: number; contratacao_id: number | null;
};
type Cotacao = {
  id: number; solicitacao_id: number; empresa_cliente_id: number; cliente: string;
  empresa_fornecedora_id: number; fornecedor: string; processo: string; material: string;
  valor_total: string; prazo_dias: number; validade_dias: number; observacoes: string | null;
  status: string; status_registrado: string; criada_em: string; vence_em: string; encerrada_em: string | null;
  contratacao_id: number | null; pode_decidir: boolean; pode_aceitar: boolean; preco_cliente_estado: string | null;
};
type Arquivo = { id: number; nome_original: string; tamanho_bytes: number; ativo: boolean; conteudo_valido: boolean; liberado: boolean };
type Evento = { id: number; cotacao_id: number; acao: string; administrador_nome: string; registro_interno: string; criado_em: string; cotacoes_recusadas: number[]; cotacoes_expiradas: number[] };
type Detalhe = { solicitacao: Solicitacao; cotacoes: Cotacao[]; arquivos: Arquivo[]; historico: Evento[]; versao: string };
type Pagina = { itens: Array<Solicitacao | Cotacao>; total: number; limite: number; deslocamento: number };
type Operacao = { cotacao: Cotacao; acao: "aceitar" | "recusar"; versao: string; chave: string; outras: number[] };
type Resultado = { evento_id: number; solicitacao_id: number; cotacao_id: number; status: string; cotacoes_recusadas: number[]; cotacoes_expiradas: number[] };
const BASE = "/administracao/comercial";
const ROTULOS: Record<string, string> = {
  aberta: "Aberta", encerrada: "Encerrada", cancelada: "Cancelada", enviada: "Aguardando decisão",
  aceita: "Aceita", recusada: "Recusada", expirada: "Expirada",
};
const moeda = (v: string) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const data = (v: string | null) => v ? new Date(v).toLocaleString("pt-BR") : "—";
const dimensao = (v: string) => Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 4 });
const idValido = (v: string) => !v || /^[1-9]\d{0,12}$/.test(v);
const numeroUrl = (v: string | null) => v && idValido(v) ? v : "";
function mensagem(erro: unknown) {
  const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  const mensagens: Record<string, string> = {
    orcamento_cliente_aguarda_aprovacao: "Publique o preço final e aguarde a aprovação do cliente antes de aceitar.",
    analise_comercial_alterada_atualize: "A solicitação ou suas cotações mudaram. Atualize e confira os dados antes de decidir.",
    cotacao_expirada: "A validade desta cotação terminou. Atualize para conferir a situação.",
    cotacao_nao_esta_pendente: "Esta cotação já recebeu uma decisão. Atualize a lista.",
    solicitacao_ja_possui_cotacao_aceita: "Esta solicitação já tem uma cotação aceita.",
    solicitacao_nao_esta_aberta: "A solicitação precisa estar aberta para receber uma decisão.",
    solicitacao_ja_contratada: "Esta solicitação já possui uma contratação.",
    registro_interno_obrigatorio: "Informe um registro interno com pelo menos três caracteres.",
    chave_operacao_reutilizada: "A confirmação mudou. Atualize a análise e abra novamente a decisão.",
    solicitacao_nao_encontrada: "Solicitação não encontrada.",
    cotacao_nao_encontrada: "Cotação não encontrada para esta solicitação.",
    arquivo_tecnico_nao_encontrado: "Arquivo não encontrado.",
    sessao_alterada_entre_novamente: "Entre novamente para continuar.",
  };
  return typeof detalhe === "string" ? mensagens[detalhe] ?? "Não foi possível concluir. Atualize a análise e tente novamente." : "Não foi possível consultar o servidor. Confira a conexão e tente novamente.";
}

export default function AdminComercialPage({ modo }: { modo: Modo }) {
  const [params, setParams] = useSearchParams();
  const sid = numeroUrl(params.get("solicitacao"));
  const cid = modo === "cotacoes" ? numeroUrl(params.get("cotacao")) : "";
  const opcoes = modo === "solicitacoes" ? ["aberta", "encerrada", "cancelada"] : ["enviada", "aceita", "recusada", "expirada", "cancelada"];
  const statusUrl = params.get("situacao") ?? "";
  const status = opcoes.includes(statusUrl) ? statusUrl : "";
  const [filtroSid, setFiltroSid] = useState(sid);
  const [filtroCid, setFiltroCid] = useState(cid);
  const [filtroStatus, setFiltroStatus] = useState(status);
  const [pagina, setPagina] = useState<Pagina | null>(null);
  const [detalhe, setDetalhe] = useState<Detalhe | null>(null);
  const [deslocamento, setDeslocamento] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(false);
  const [abrindo, setAbrindo] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [baixando, setBaixando] = useState<number | null>(null);
  const [erro, setErro] = useState("");
  const [erroDetalhe, setErroDetalhe] = useState("");
  const [aviso, setAviso] = useState("");
  const [operacao, setOperacao] = useState<Operacao | null>(null);
  const [registro, setRegistro] = useState("");
  const [cotacaoPreco,setCotacaoPreco]=useState<number|null>(null);
  const [cotacaoComparada, setCotacaoComparada] = useState<number | null>(null);
  const montada = useRef(true);
  const trava = useRef(false);
  const detalheRef = useRef<HTMLElement>(null);
  const confirmacaoRef = useRef<HTMLElement>(null);
  const downloadRef = useRef<AbortController | null>(null);
  const decisaoRef = useRef<AbortController | null>(null);

  useEffect(() => {
    montada.current = true;
    return () => { montada.current = false; downloadRef.current?.abort(); decisaoRef.current?.abort(); };
  }, []);
  useEffect(() => {
    setFiltroSid(sid); setFiltroCid(cid); setFiltroStatus(status); setDeslocamento(0);
    setOperacao(null); setErro(""); setErroDetalhe(""); setAviso("");
    setCotacaoComparada(null);setCotacaoPreco(null);
  }, [modo, sid, cid, status]);
  useEffect(() => {
    const controle = new AbortController(); setCarregando(true); setErro(""); setPagina(null);
    void api.get<Pagina>(BASE + "/" + modo, {
      params: { ...(sid ? { solicitacao_id: Number(sid) } : {}), ...(cid ? { cotacao_id: Number(cid) } : {}),
        ...(status ? { status } : {}), deslocamento, limite: 20 }, signal: controle.signal, timeout: 20_000,
    }).then(({ data: resposta }) => { if (!controle.signal.aborted) setPagina(resposta); })
      .catch(e => { if (!controle.signal.aborted) setErro(mensagem(e)); })
      .finally(() => { if (!controle.signal.aborted) setCarregando(false); });
    return () => controle.abort();
  }, [modo, sid, cid, status, deslocamento, revisao]);
  useEffect(() => {
    if (!sid) { setDetalhe(null); setAbrindo(false); return; }
    const controle = new AbortController(); setAbrindo(true); setDetalhe(null); setErroDetalhe("");
    void api.get<Detalhe>(BASE + "/solicitacoes/" + sid, { signal: controle.signal, timeout: 20_000 })
      .then(({ data: resposta }) => { if (!controle.signal.aborted) setDetalhe(resposta); })
      .catch(e => { if (!controle.signal.aborted) setErroDetalhe(mensagem(e)); })
      .finally(() => { if (!controle.signal.aborted) setAbrindo(false); });
    return () => controle.abort();
  }, [sid, revisao]);
  useEffect(() => { if (sid) detalheRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [sid]);
  useEffect(() => { if (operacao) confirmacaoRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [operacao]);

  function abrir(solicitacao: number, cotacao?: number) {
    if (trava.current) return;
    setDeslocamento(0); setParams({ solicitacao: String(solicitacao), ...(cotacao ? { cotacao: String(cotacao) } : {}) });
  }
  function decidir(q: Cotacao, acao: "aceitar" | "recusar") {
    if (!detalhe || !q.pode_decidir || trava.current || (acao==="aceitar"&&!q.pode_aceitar)) return;
    setOperacao({ cotacao: q, acao, versao: detalhe.versao, chave: crypto.randomUUID(),
      outras: detalhe.cotacoes.filter(c => c.id !== q.id && c.status === "enviada").map(c => c.id) });
    setRegistro(""); setErroDetalhe(""); setAviso("");
  }
  async function registrar() {
    if (!operacao || trava.current || registro.trim().length < 3) return;
    const atual = operacao; trava.current = true; setOcupado(true); setErroDetalhe("");
    const controle = new AbortController(); decisaoRef.current = controle;
    try {
      const { data: resultado } = await api.post<Resultado>(BASE + "/solicitacoes/" + atual.cotacao.solicitacao_id + "/cotacoes/" + atual.cotacao.id + "/decisoes",
        { acao: atual.acao, versao: atual.versao, registro_interno: registro.trim(), chave_operacao: atual.chave }, { signal: controle.signal, timeout: 30_000 });
      if (montada.current) {
        setOperacao(null); setAviso("Cotação #" + resultado.cotacao_id + " " + (resultado.status === "aceita" ? "aceita" : "recusada") + ". Decisão registrada pela administração.");
        setRevisao(v => v + 1);
      }
    } catch (e) { if (montada.current && !controle.signal.aborted) setErroDetalhe(mensagem(e)); }
    finally { trava.current = false; if (montada.current) setOcupado(false); }
  }
  async function baixar(a: Arquivo) {
    if (baixando || ocupado) return;
    const controle = new AbortController(); downloadRef.current = controle; setBaixando(a.id); setErroDetalhe("");
    try {
      const { data: conteudo } = await api.get<Blob>("/arquivos-tecnicos/" + a.id + "/download", { responseType: "blob", signal: controle.signal, timeout: 60_000 });
      if (!montada.current || controle.signal.aborted) return;
      const url = URL.createObjectURL(conteudo); const link = document.createElement("a");
      link.href = url; link.download = a.nome_original.split(/[\\/]/).pop() || "arquivo-tecnico-" + a.id;
      document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { if (montada.current && !controle.signal.aborted) setErroDetalhe(mensagem(e)); }
    finally { if (montada.current) setBaixando(null); }
  }

  const s = detalhe?.solicitacao;
  return <main className="com43">
    <header className="com43-cabecalho"><div><span>ADMINISTRAÇÃO</span><h1>{modo === "solicitacoes" ? "Solicitações de serviços" : "Cotações dos fornecedores"}</h1>
      <p>Confira as propostas, prepare o preço final e publique ao cliente. Após a aprovação, confirme o aceite e a contratação.</p></div>
      <button disabled={ocupado || carregando || abrindo} onClick={() => { setOperacao(null); setAviso(""); setRevisao(v => v + 1); }}>Atualizar</button></header>
    <nav className="com43-navegacao" aria-label="Gestão comercial"><Link to="/admin/solicitacoes">Solicitações</Link><Link to="/admin/cotacoes">Cotações</Link><Link to="/admin/arquivos-tecnicos">Revisar arquivos técnicos</Link></nav>
    <form className="com43-filtros" onSubmit={e => {
      e.preventDefault(); if (trava.current) return;
      const fs = filtroSid.trim(), fc = filtroCid.trim();
      if (!idValido(fs) || !idValido(fc)) { setErro("Informe números de solicitação e cotação maiores que zero."); return; }
      setDeslocamento(0); setOperacao(null); setAviso(""); setParams({ ...(fs ? { solicitacao: fs } : {}), ...(modo === "cotacoes" && fc ? { cotacao: fc } : {}), ...(filtroStatus ? { situacao: filtroStatus } : {}) });
      setRevisao(v => v + 1);
    }}>
      <label>Solicitação #<input aria-label="Número da solicitação" inputMode="numeric" placeholder="Todas" value={filtroSid} disabled={ocupado} onChange={e => setFiltroSid(e.target.value)} /></label>
      {modo === "cotacoes" && <label>Cotação #<input aria-label="Número da cotação" inputMode="numeric" placeholder="Todas" value={filtroCid} disabled={ocupado} onChange={e => setFiltroCid(e.target.value)} /></label>}
      <label>Situação<select aria-label="Situação" value={filtroStatus} disabled={ocupado} onChange={e => setFiltroStatus(e.target.value)}><option value="">Todas</option>{opcoes.map(op => <option key={op} value={op}>{ROTULOS[op]}</option>)}</select></label>
      <button disabled={ocupado || carregando}>Consultar</button><button type="button" disabled={ocupado} onClick={() => { setDeslocamento(0); setParams({}); setRevisao(v => v + 1); }}>Limpar filtros</button>
    </form>
    {erro && <p role="alert" className="com43-erro">{erro}</p>}
    {carregando && <p role="status">Consultando registros…</p>}
    {pagina && <section className="com43-lista" aria-label={modo === "solicitacoes" ? "Lista de solicitações" : "Lista de cotações"}>
      <p>{pagina.total} {modo === "solicitacoes" ? "solicitação(ões)" : "cotação(ões)"} · Página {Math.floor(deslocamento / 20) + 1}</p>
      {!pagina.itens.length ? <p className="com43-vazio">Nenhum registro encontrado para estes filtros.</p> :
      <div className="com43-tabela"><table><thead><tr><th>{modo === "solicitacoes" ? "Solicitação / cliente" : "Cotação / solicitação"}</th><th>{modo === "solicitacoes" ? "Processo / material" : "Fornecedor / cliente"}</th><th>{modo === "solicitacoes" ? "Quantidade / propostas" : "Valor total / prazo"}</th><th>Situação</th><th>Consulta</th></tr></thead>
        <tbody>{pagina.itens.map(item => modo === "solicitacoes" ? (() => { const q = item as Solicitacao; return <tr key={q.id}><td><strong>Solicitação #{q.id}</strong><small>{q.cliente} · Empresa #{q.empresa_cliente_id}</small></td><td>{q.processo}<small>{q.material}</small></td><td>{q.quantidade} unidades<small>{q.cotacoes_total} cotações · {q.arquivos_ativos} arquivos ativos</small></td><td><span className={"com43-situacao " + q.status}>{ROTULOS[q.status]}</span>{q.contratacao_id && <small>Contratação #{q.contratacao_id}</small>}</td><td><button disabled={ocupado} onClick={() => abrir(q.id)}>Abrir solicitação</button></td></tr>; })() :
          (() => { const q = item as Cotacao; return <tr key={q.id}><td><strong>Cotação #{q.id}</strong><small>Solicitação #{q.solicitacao_id}</small></td><td>{q.fornecedor}<small>{q.cliente}</small></td><td><strong>{moeda(q.valor_total)}</strong><small>{q.prazo_dias} dias de execução</small></td><td><span className={"com43-situacao " + q.status}>{ROTULOS[q.status]}</span><small>Válida até {data(q.vence_em)}</small></td><td><button disabled={ocupado} onClick={() => abrir(q.solicitacao_id, q.id)}>Analisar cotação</button></td></tr>; })())}</tbody></table></div>}
      <div className="com43-acoes"><button disabled={ocupado || deslocamento === 0} onClick={() => setDeslocamento(v => Math.max(0, v - 20))}>Anterior</button><button disabled={ocupado || deslocamento + 20 >= pagina.total} onClick={() => setDeslocamento(v => v + 20)}>Próxima</button></div>
    </section>}
    {sid && <section ref={detalheRef} className="com43-detalhe" aria-label="Análise da solicitação">
      <h2>Solicitação #{sid}</h2>
      {abrindo && <p role="status">Abrindo solicitação e cotações…</p>}
      {erroDetalhe && <p role="alert" className="com43-erro">{erroDetalhe}</p>}
      {aviso && <p role="status" className="com43-aviso">{aviso}</p>}
      {detalhe && s && <>
        <div className="com43-resumo"><div><small>Cliente</small><strong>{s.cliente}</strong><span>Empresa #{s.empresa_cliente_id}</span></div><div><small>Processo / material</small><strong>{s.processo}</strong><span>{s.material}</span></div>
          <div><small>Dimensões X × Y × Z</small><strong>{[s.dimensao_x_maxima_mm, s.dimensao_y_maxima_mm, s.dimensao_z_maxima_mm].map(dimensao).join(" × ")} mm</strong><span>Tolerância: {dimensao(s.tolerancia_requerida_mm)} mm</span></div>
          <div><small>Quantidade / situação</small><strong>{s.quantidade} unidades · {ROTULOS[s.status]}</strong><span>Criada em {data(s.criada_em)}</span></div></div>
        {s.observacoes && <div className="com43-texto"><h3>Observações do cliente</h3><p>{s.observacoes}</p></div>}
        {detalhe.cotacoes.some(q => q.status === "aceita") && <p className="com43-aviso"><Link to={"/admin/contratacoes?solicitacao=" + s.id}>{s.contratacao_id ? "Consultar contratação e OS" : "Preparar contratação e abertura da OS"}</Link></p>}
        {s.contratacao_id && <p className="com43-aviso">Contratação #{s.contratacao_id} já registrada. Consulte seu acompanhamento no <Link to="/admin">Dashboard administrativo</Link>.</p>}
        <div className="com43-arquivos"><h3>Documentos técnicos</h3><p>A liberação dos documentos é registrada em <Link to="/admin/arquivos-tecnicos">Arquivos Técnicos</Link>.</p>
          {!detalhe.arquivos.length ? <p>Nenhum documento enviado para esta solicitação.</p> : detalhe.arquivos.map(a => <article key={a.id}><div><strong>{a.nome_original}</strong><small>Arquivo #{a.id} · {a.tamanho_bytes.toLocaleString("pt-BR")} bytes · {a.liberado ? "Liberado para cotação" : !a.ativo ? "Desvinculado pelo cliente" : !a.conteudo_valido ? "Conteúdo indisponível ou divergente" : "Aguardando revisão e liberação"}</small></div><button disabled={!a.ativo || !a.conteudo_valido || ocupado || baixando !== null} onClick={() => void baixar(a)}>{baixando === a.id ? "Baixando…" : "Baixar documento"}</button></article>)}</div>
        <ComparacaoCotacoesAdmin solicitacaoId={s.id} versao={detalhe.versao} ocupado={ocupado} aoConferir={id => {
          if (trava.current) return;
          setCotacaoComparada(id);
          document.getElementById(`mec-cotacao-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }} />
        <div className="com43-propostas"><h3>Cotações desta solicitação</h3>
          {!detalhe.cotacoes.length && <p>Nenhuma cotação registrada.</p>}
          {detalhe.cotacoes.map(q => <article key={q.id} id={`mec-cotacao-${q.id}`} className={"com43-proposta" + (cid === String(q.id) || cotacaoComparada === q.id ? " selecionada" : "")}>
            <header><div><h3>Cotação #{q.id} · {q.fornecedor}</h3><small>Fornecedor #{q.empresa_fornecedora_id}</small></div><span className={"com43-situacao " + q.status}>{ROTULOS[q.status]}</span></header>
            <div className="com43-valores"><strong>{moeda(q.valor_total)} · custo do fornecedor</strong><span>Execução: {q.prazo_dias} dias</span><span>Validade: {q.validade_dias} dias</span></div>
            <p>Enviada em {data(q.criada_em)} · Válida até {data(q.vence_em)}{q.encerrada_em ? " · Encerrada em " + data(q.encerrada_em) : ""}</p>
            {q.observacoes && <p className="com43-texto">{q.observacoes}</p>}
            <p className="com43-nota">{q.preco_cliente_estado?rotuloAnalise[q.preco_cliente_estado]:q.status==="enviada"?"Orçamento recebido pelo ADM · ainda não publicado ao cliente":"Histórico da cotação"}</p>
            <button disabled={ocupado} onClick={()=>setCotacaoPreco(cotacaoPreco===q.id?null:q.id)}>{cotacaoPreco===q.id?"Fechar preço":q.pode_decidir?"Preparar preço para o cliente":"Consultar formação do preço"}</button>
            {cotacaoPreco===q.id&&<FormacaoPrecoAdmin key={`${q.id}:${revisao}`} cotacaoId={q.id} solicitacaoId={q.solicitacao_id} aoRegistrar={()=>setRevisao(v=>v+1)}/>}
            {q.pode_decidir ? <div className="com43-acoes"><button className="com43-aceitar" disabled={ocupado||!q.pode_aceitar} onClick={() => decidir(q, "aceitar")}>Aceitar cotação</button><button disabled={ocupado} onClick={() => decidir(q, "recusar")}>Recusar cotação</button></div> :
              <p className="com43-nota">{q.status === "expirada" ? "A validade terminou; esta cotação não pode receber aceite." : "Registro disponível para consulta do histórico."}</p>}
          </article>)}
        </div>
        {operacao && <section ref={confirmacaoRef} className="com43-confirmacao" aria-label="Confirmar decisão administrativa"><h3>{operacao.acao === "aceitar" ? "Aceitar" : "Recusar"} cotação #{operacao.cotacao.id}</h3>
          <p>Solicitação #{operacao.cotacao.solicitacao_id} · {operacao.cotacao.fornecedor} · <strong>{moeda(operacao.cotacao.valor_total)} no total</strong> · {operacao.cotacao.prazo_dias} dias de execução.</p>
          {operacao.acao === "aceitar" && <p>{operacao.outras.length ? "As demais propostas pendentes desta solicitação serão recusadas: " + operacao.outras.map(n => "#" + n).join(", ") + "." : "Esta é a única proposta pendente desta solicitação."} A contratação será uma etapa posterior ao aceite.</p>}
          <label>Registro interno da decisão<textarea autoFocus maxLength={2000} value={registro} disabled={ocupado} onChange={e => setRegistro(e.target.value)} placeholder="Registre o motivo e a conferência administrativa." /></label>
          <div className="com43-acoes"><button disabled={ocupado || registro.trim().length < 3} onClick={() => void registrar()}>{ocupado ? "Registrando…" : "Confirmar " + (operacao.acao === "aceitar" ? "aceite" : "recusa")}</button><button disabled={ocupado} onClick={() => setOperacao(null)}>Voltar</button></div>
        </section>}
        <section className="com43-historico"><h3>Histórico das decisões administrativas</h3>
          {!detalhe.historico.length && <p>Nenhuma decisão registrada por esta tela. Decisões anteriores continuam preservadas nas situações das cotações.</p>}
          {detalhe.historico.map(h => <article key={h.id}><strong>{h.acao === "aceitar" ? "Aceite" : "Recusa"} da cotação #{h.cotacao_id} · {h.administrador_nome}</strong><small>{data(h.criado_em)}</small><p>{h.registro_interno}</p>
            {!!h.cotacoes_recusadas.length && <p>Outras cotações recusadas por esta seleção: {h.cotacoes_recusadas.map(n => "#" + n).join(", ")}.</p>}
            {!!h.cotacoes_expiradas.length && <p>Cotações com validade encerrada: {h.cotacoes_expiradas.map(n => "#" + n).join(", ")}.</p>}</article>)}
        </section>
      </>}
    </section>}
  </main>;
}
