import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import "../comercial/ComercialAdmin.css";

type Modo = "contratacoes" | "ordens-servico";
type Contrato = {
  id: number; solicitacao_id: number; cotacao_id: number; cliente: string; fornecedor: string;
  valor_total: string; prazo_dias: number; quantidade: number; processo: string; material: string;
  status: string; criada_em: string; observacoes: string | null; ordem_servico_id: number | null;
  ordem_status: string | null; etapa_administrativa: string | null;
};
type Arquivo = { id: number; nome_original: string; ativo: boolean; conteudo_valido: boolean; liberado: boolean };
type Preparacao = {
  solicitacao: { id: number; cliente: string; processo: string; material: string; quantidade: number; status: string;
    observacoes: string | null; dimensao_x_maxima_mm: string; dimensao_y_maxima_mm: string;
    dimensao_z_maxima_mm: string; tolerancia_requerida_mm: string };
  cotacao: { id: number; fornecedor: string; valor_total: string; prazo_dias: number; status: string } | null;
  contratacao: Contrato | null; arquivos: Arquivo[]; versao: string;
  acao_disponivel: "contratar_e_abrir_os" | "abrir_os" | null; motivo_indisponivel: string | null;
  historico: Array<{ id: number; acao: string; contratacao_id: number; ordem_servico_id: number;
    administrador_nome: string; registro_interno: string; criado_em: string }>;
};
type Pagina = { itens: Contrato[]; total: number };
type Operacao = { solicitacao: number; cotacao_id: number; acao: "contratar_e_abrir_os" | "abrir_os";
  versao: string; registro_interno: string; observacoes_execucao: string | null; chave_operacao: string;
  fornecedor: string; valor: string; prazo: number; quantidade: number };
type Resultado = { evento_id: number; solicitacao_id: number; contratacao_id: number; ordem_servico_id: number };
const BASE = "/administracao/contratacoes";
const idValido = (v: string) => !v || /^[1-9]\d{0,12}$/.test(v);
const numeroUrl = (v: string | null) => v && idValido(v) ? v : "";
const moeda = (v: string) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const data = (v: string) => new Date(v).toLocaleString("pt-BR");
const medida = (v: string) => Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 4 });
const ROTULOS: Record<string, string> = { ativa: "Ativa", encerrada: "Encerrada", cancelada: "Cancelada",
  aberta: "Aberta", em_execucao: "Em execução", concluida: "Concluída", aguardando_material: "Aguardando material",
  material_recebido: "Material recebido", material_encaminhado: "Material encaminhado", coleta_solicitada: "Coleta solicitada",
  pecas_recebidas: "Peças recebidas", em_avaliacao: "Em avaliação", retrabalho: "Retrabalho",
  retrabalho_encaminhado: "Retrabalho encaminhado", aprovado_para_entrega: "Aprovado para entrega",
  entregue_cliente: "Entregue ao cliente", cancelado: "Cancelado" };
const MENSAGENS: Record<string, string> = {
  preparacao_contratacao_alterada_atualize: "Os dados mudaram desde a conferência. Atualize e revise a contratação novamente.",
  contratacao_ja_possui_ordem: "A contratação já possui uma OS. Consulte a ordem e seu acompanhamento administrativo.",
  contratacao_nao_esta_ativa: "Esta contratação está encerrada ou cancelada. Seu histórico permanece disponível.",
  solicitacao_nao_esta_aberta: "A solicitação precisa estar aberta para uma nova contratação.",
  solicitacao_sem_cotacao_aceita_unica: "É necessário ter uma única cotação aceita para preparar a contratação.",
  aceite_sem_vinculo_com_cliente: "Confira o vínculo do aceite com o cliente antes de contratar.",
  vinculos_da_contratacao_divergentes: "Os vínculos da contratação precisam ser conferidos pela administração.",
  documentacao_para_contratacao_nao_disponivel: "Revise e libere um documento técnico íntegro antes de confirmar a contratação ou abrir a OS.",
  proposta_da_contratacao_divergente: "A proposta selecionada mudou. Atualize a conferência.",
  abertura_os_preserva_instrucoes_contratadas: "A OS deve manter as instruções da contratação existente.",
  registro_interno_obrigatorio: "Descreva a conferência administrativa com pelo menos três caracteres.",
  chave_operacao_reutilizada: "Atualize para conferir o registro existente antes de preparar outra confirmação.",
  solicitacao_nao_encontrada: "Solicitação não encontrada.", contratacao_nao_encontrada: "Contratação não encontrada.",
  sessao_alterada_entre_novamente: "Entre novamente para continuar.",
};
function mensagem(erro: unknown) {
  const d = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  return typeof d === "string" ? MENSAGENS[d] ?? "Não foi possível concluir. Atualize a conferência e tente novamente." :
    "Não foi possível obter a resposta do servidor. Tente confirmar novamente ou atualize para conferir o resultado.";
}

export default function AdminContratacaoPage({ modo }: { modo: Modo }) {
  const [params, setParams] = useSearchParams();
  const sid = numeroUrl(params.get("solicitacao"));
  const cid = numeroUrl(params.get("contratacao"));
  const oid = modo === "ordens-servico" ? numeroUrl(params.get("ordem")) : "";
  const opcoes = modo === "contratacoes" ? ["ativa", "encerrada", "cancelada"] : ["aberta", "em_execucao", "concluida", "cancelada"];
  const situacao = params.get("situacao") ?? "";
  const status = opcoes.includes(situacao) ? situacao : "";
  const [filtroSid, setFiltroSid] = useState(sid); const [filtroCid, setFiltroCid] = useState(cid);
  const [filtroOid, setFiltroOid] = useState(oid); const [filtroStatus, setFiltroStatus] = useState(status);
  const [pagina, setPagina] = useState<Pagina | null>(null); const [preparacao, setPreparacao] = useState<Preparacao | null>(null);
  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(false); const [abrindo, setAbrindo] = useState(false);
  const [ocupado, setOcupado] = useState(false); const [baixando, setBaixando] = useState<number | null>(null);
  const [erro, setErro] = useState(""); const [erroDetalhe, setErroDetalhe] = useState("");
  const [registro, setRegistro] = useState(""); const [instrucoes, setInstrucoes] = useState("");
  const [operacao, setOperacao] = useState<Operacao | null>(null); const [resultado, setResultado] = useState<Resultado | null>(null);
  const trava = useRef(false); const montada = useRef(true);
  const detalheRef = useRef<HTMLElement>(null); const confirmacaoRef = useRef<HTMLElement>(null);
  const decisaoRef = useRef<AbortController | null>(null); const downloadRef = useRef<AbortController | null>(null);
  useEffect(() => { montada.current = true; return () => { montada.current = false; decisaoRef.current?.abort(); downloadRef.current?.abort(); }; }, []);
  useEffect(() => {
    setFiltroSid(sid); setFiltroCid(cid); setFiltroOid(oid); setFiltroStatus(status); setDeslocamento(0);
    setOperacao(null); setRegistro(""); setInstrucoes(""); setResultado(null); setErroDetalhe("");
  }, [modo, sid, cid, oid, status]);
  useEffect(() => {
    const controle = new AbortController(); setCarregando(true); setPagina(null); setErro("");
    void api.get<Pagina>("/administracao/" + modo, { params: {
      ...(sid ? { solicitacao_id: Number(sid) } : {}), ...(cid ? { contratacao_id: Number(cid) } : {}),
      ...(oid ? { ordem_servico_id: Number(oid) } : {}), ...(status ? { status } : {}), deslocamento, limite: 20,
    }, signal: controle.signal, timeout: 20_000 }).then(({ data: resposta }) => { if (!controle.signal.aborted) setPagina(resposta); })
      .catch(e => { if (!controle.signal.aborted) setErro(mensagem(e)); })
      .finally(() => { if (!controle.signal.aborted) setCarregando(false); });
    return () => controle.abort();
  }, [modo, sid, cid, oid, status, deslocamento, revisao]);
  useEffect(() => {
    setPreparacao(null); setErroDetalhe(""); setAbrindo(Boolean(sid));
    if (!sid) return;
    const controle = new AbortController();
    void api.get<Preparacao>(BASE + "/preparacao/" + sid, { signal: controle.signal, timeout: 30_000 })
      .then(({ data: resposta }) => { if (!controle.signal.aborted) setPreparacao(resposta); })
      .catch(e => { if (!controle.signal.aborted) setErroDetalhe(mensagem(e)); })
      .finally(() => { if (!controle.signal.aborted) setAbrindo(false); });
    return () => controle.abort();
  }, [sid, revisao]);
  useEffect(() => { if (sid) detalheRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [sid]);
  useEffect(() => { if (operacao) confirmacaoRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [operacao]);

  function revisar() {
    if (!preparacao?.acao_disponivel || !preparacao.cotacao || trava.current || registro.trim().length < 3) return;
    setErroDetalhe("");
    setOperacao({ solicitacao: preparacao.solicitacao.id, cotacao_id: preparacao.cotacao.id, acao: preparacao.acao_disponivel,
      versao: preparacao.versao, registro_interno: registro.trim(), observacoes_execucao: preparacao.contratacao ? null : instrucoes.trim() || null,
      chave_operacao: crypto.randomUUID(), fornecedor: preparacao.cotacao.fornecedor,
      valor: preparacao.contratacao?.valor_total ?? preparacao.cotacao.valor_total,
      prazo: preparacao.contratacao?.prazo_dias ?? preparacao.cotacao.prazo_dias, quantidade: preparacao.solicitacao.quantidade });
  }
  async function confirmar() {
    if (!operacao || trava.current) return;
    const atual = operacao; trava.current = true; setOcupado(true); setErroDetalhe("");
    const controle = new AbortController(); decisaoRef.current = controle;
    try {
      const { data: resposta } = await api.post<Resultado>(BASE + "/preparacao/" + atual.solicitacao + "/confirmar", {
        acao: atual.acao, cotacao_id: atual.cotacao_id, versao: atual.versao, registro_interno: atual.registro_interno,
        observacoes_execucao: atual.observacoes_execucao, chave_operacao: atual.chave_operacao,
      }, { signal: controle.signal, timeout: 30_000 });
      if (montada.current) { setOperacao(null); setResultado(resposta); setRevisao(v => v + 1); }
    } catch (e) { if (montada.current && !controle.signal.aborted) setErroDetalhe(mensagem(e)); }
    finally { trava.current = false; if (montada.current) setOcupado(false); }
  }
  async function baixar(a: Arquivo) {
    if (baixando !== null || ocupado) return;
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

  const s = preparacao?.solicitacao; const q = preparacao?.cotacao; const c = preparacao?.contratacao;
  return <main className="com43">
    <header className="com43-cabecalho"><div><span>ADMINISTRAÇÃO</span><h1>{modo === "contratacoes" ? "Contratações de serviços" : "Ordens de serviço"}</h1>
      <p>Confira a proposta aceita, registre a contratação e acompanhe a OS sob responsabilidade da administração.</p></div>
      <button disabled={ocupado || carregando || abrindo} onClick={() => { setOperacao(null); setRevisao(v => v + 1); }}>Atualizar</button></header>
    <nav className="com43-navegacao" aria-label="Contratação e execução"><Link to="/admin/contratacoes">Contratações</Link><Link to="/admin/ordens-servico">Ordens de serviço</Link><Link to="/admin/cotacoes">Cotações</Link><Link to="/admin/intermediacao">Acompanhar material e entregas</Link></nav>
    <p>Informe a solicitação para preparar a contratação de uma proposta aceita ou consultar seu contrato e sua OS.</p>
    <form className="com43-filtros" onSubmit={e => {
      e.preventDefault(); if (trava.current) return;
      const fs = filtroSid.trim(), fc = filtroCid.trim(), fo = filtroOid.trim();
      if (![fs, fc, fo].every(idValido)) { setErro("Informe números maiores que zero nos filtros."); return; }
      setOperacao(null); setDeslocamento(0); setParams({ ...(fs ? { solicitacao: fs } : {}), ...(fc ? { contratacao: fc } : {}),
        ...(modo === "ordens-servico" && fo ? { ordem: fo } : {}), ...(filtroStatus ? { situacao: filtroStatus } : {}) }); setRevisao(v => v + 1);
    }}>
      <label>Solicitação #<input aria-label="Número da solicitação" inputMode="numeric" placeholder="Todas" disabled={ocupado} value={filtroSid} onChange={e => setFiltroSid(e.target.value)} /></label>
      <label>Contratação #<input aria-label="Número da contratação" inputMode="numeric" placeholder="Todas" disabled={ocupado} value={filtroCid} onChange={e => setFiltroCid(e.target.value)} /></label>
      {modo === "ordens-servico" && <label>OS #<input aria-label="Número da OS" inputMode="numeric" placeholder="Todas" disabled={ocupado} value={filtroOid} onChange={e => setFiltroOid(e.target.value)} /></label>}
      <label>Situação<select aria-label="Situação" disabled={ocupado} value={filtroStatus} onChange={e => setFiltroStatus(e.target.value)}><option value="">Todas</option>{opcoes.map(op => <option key={op} value={op}>{ROTULOS[op]}</option>)}</select></label>
      <button disabled={ocupado || carregando}>Consultar</button><button type="button" disabled={ocupado} onClick={() => { setParams({}); setRevisao(v => v + 1); }}>Limpar filtros</button>
    </form>
    {erro && <p role="alert" className="com43-erro">{erro}</p>}{carregando && <p role="status">Consultando registros…</p>}
    {pagina && <section className="com43-lista" aria-label="Registros de contratação e OS"><p>{pagina.total} registro(s) · Página {Math.floor(deslocamento / 20) + 1}</p>
      {!pagina.itens.length ? <p className="com43-vazio">Nenhum registro encontrado para estes filtros.</p> : <div className="com43-tabela"><table><thead><tr>
        <th>{modo === "contratacoes" ? "Contratação" : "Ordem de serviço"}</th><th>Cliente / fornecedor</th><th>Valor total / prazo</th><th>Situação / material</th><th>Consulta</th>
      </tr></thead><tbody>{pagina.itens.map(item => <tr key={item.id}><td><strong>{modo === "contratacoes" ? "Contratação #" + item.id : "OS #" + item.ordem_servico_id}</strong>
        <small>Solicitação #{item.solicitacao_id} · Cotação #{item.cotacao_id}</small><small>{item.quantidade} unidades · {item.processo} · {item.material}</small></td>
        <td>{item.cliente}<small>{item.fornecedor}</small></td><td><strong>{moeda(item.valor_total)}</strong><small>{item.prazo_dias} dias de execução</small></td>
        <td>{ROTULOS[modo === "contratacoes" ? item.status : item.ordem_status ?? ""] ?? "—"}<small>{item.ordem_servico_id ? "OS #" + item.ordem_servico_id : "Sem OS"} · {item.etapa_administrativa ? ROTULOS[item.etapa_administrativa] : "Sem ciclo administrativo"}</small></td>
        <td><button disabled={ocupado} onClick={() => { setParams({ solicitacao: String(item.solicitacao_id) }); setRevisao(v => v + 1); }}>Ver contratação e OS</button></td></tr>)}</tbody></table></div>}
      <div className="com43-acoes"><button disabled={ocupado || deslocamento === 0} onClick={() => setDeslocamento(v => Math.max(0, v - 20))}>Anterior</button><button disabled={ocupado || deslocamento + 20 >= pagina.total} onClick={() => setDeslocamento(v => v + 20)}>Próxima</button></div></section>}
    {sid && <section ref={detalheRef} className="com43-detalhe" aria-label="Conferência da contratação"><h2>Solicitação #{sid} · Contratação e OS</h2>
      {abrindo && <p role="status">Conferindo proposta e documentos…</p>}{erroDetalhe && <p role="alert" className="com43-erro">{erroDetalhe}</p>}
      {resultado && <p role="status" className="com43-aviso">Contratação #{resultado.contratacao_id} · OS #{resultado.ordem_servico_id} registrada. Etapa: Aguardando material.</p>}
      {preparacao && s && <>
        <div className="com43-resumo"><div><small>Cliente / fornecedor</small><strong>{s.cliente}</strong><span>{q?.fornecedor ?? c?.fornecedor ?? "Sem proposta aceita"}</span></div>
          <div><small>Processo / material / lote</small><strong>{s.processo} · {s.material}</strong><span>{s.quantidade} unidades</span></div>
          <div><small>Dimensões X × Y × Z</small><strong>{[s.dimensao_x_maxima_mm, s.dimensao_y_maxima_mm, s.dimensao_z_maxima_mm].map(medida).join(" × ")} mm</strong><span>Tolerância: {medida(s.tolerancia_requerida_mm)} mm</span></div>
          <div><small>Proposta aceita</small><strong>{q ? "Cotação #" + q.id + " · " + moeda(c?.valor_total ?? q.valor_total) + " no total" : "Sem cotação aceita"}</strong><span>{q ? (c?.prazo_dias ?? q.prazo_dias) + " dias de execução" : "Confira as cotações da solicitação"}</span></div></div>
        {s.observacoes && <div className="com43-texto"><h3>Observações do cliente</h3><p>{s.observacoes}</p></div>}
        <p><Link to={"/admin/solicitacoes?solicitacao=" + s.id}>Consultar a solicitação e o aceite</Link></p>
        <div className="com43-arquivos"><h3>Documentos técnicos</h3>{!preparacao.arquivos.length ? <p>Nenhum documento enviado.</p> : preparacao.arquivos.map(a => <article key={a.id}><div><strong>{a.nome_original}</strong><small>Arquivo #{a.id} · {a.liberado ? "Liberado e íntegro" : "Documento não disponível para contratação"}</small></div>
          <button disabled={!a.ativo || !a.conteudo_valido || ocupado || baixando !== null} onClick={() => void baixar(a)}>{baixando === a.id ? "Baixando…" : "Baixar documento"}</button></article>)}</div>
        {c && <section className="com43-proposta"><h3>Contratação #{c.id} · {ROTULOS[c.status]}</h3><p>Registrada em {data(c.criada_em)}.</p>
          <p>{c.ordem_servico_id ? "OS #" + c.ordem_servico_id + " · " + ROTULOS[c.ordem_status ?? ""] : "Esta contratação ainda não possui uma ordem de serviço."}</p>
          {c.etapa_administrativa && <p>Etapa administrativa: <strong>{ROTULOS[c.etapa_administrativa]}</strong></p>}{c.observacoes && <p className="com43-texto">Instruções de execução: {c.observacoes}</p>}
          {c.ordem_servico_id && <div className="com43-acoes"><Link to={"/admin/ordens-servico?solicitacao=" + s.id + "&ordem=" + c.ordem_servico_id}>Ver OS #{c.ordem_servico_id}</Link><Link to={"/admin/intermediacao?ordem=" + c.ordem_servico_id}>Acompanhar material e entregas</Link></div>}</section>}
        {preparacao.acao_disponivel ? <section className="com43-proposta"><h3>{c ? "Abrir OS para esta contratação" : "Preparar contratação e abertura da OS"}</h3>
          <p>O valor, o prazo, o fornecedor e o lote serão copiados dos registros conferidos. A OS começará em <strong>Aguardando material</strong>; a administração registra o recebimento e o encaminhamento antes da produção.</p>
          {!c && <label>Instruções de execução (visíveis nos portais)<textarea disabled={ocupado || operacao !== null} maxLength={4000} value={instrucoes} onChange={e => setInstrucoes(e.target.value)} placeholder="Opcional: instruções de execução para o serviço." /></label>}
          <label>Registro interno da conferência<textarea disabled={ocupado || operacao !== null} maxLength={2000} value={registro} onChange={e => setRegistro(e.target.value)} placeholder="Registre a conferência da proposta, dos documentos e do lote." /></label>
          <button disabled={ocupado || operacao !== null || registro.trim().length < 3} onClick={revisar}>{c ? "Revisar abertura da OS" : "Revisar contratação e OS"}</button></section> :
          <p className="com43-nota">{MENSAGENS[preparacao.motivo_indisponivel ?? ""] ?? "Consulta do histórico disponível."}</p>}
        {operacao && <section ref={confirmacaoRef} className="com43-confirmacao" aria-label="Confirmar contratação e OS"><h3>{operacao.acao === "abrir_os" ? "Confirmar abertura da OS" : "Confirmar contratação e abertura da OS"}</h3>
          <p>Solicitação #{operacao.solicitacao} · Cotação #{operacao.cotacao_id} · {operacao.fornecedor}.</p>
          <p><strong>{moeda(operacao.valor)} no total</strong> · {operacao.quantidade} unidades · {operacao.prazo} dias de execução.</p>
          <p>Etapa inicial: <strong>Aguardando material</strong>.</p><p className="com43-texto">Registro interno: {operacao.registro_interno}</p>
          {operacao.observacoes_execucao && <p className="com43-texto">Instruções visíveis nos portais: {operacao.observacoes_execucao}</p>}
          <div className="com43-acoes"><button disabled={ocupado} onClick={() => void confirmar()}>{ocupado ? "Registrando…" : operacao.acao === "abrir_os" ? "Confirmar abertura da OS" : "Confirmar contratação e OS"}</button><button disabled={ocupado} onClick={() => setOperacao(null)}>Voltar</button></div></section>}
        <section className="com43-historico"><h3>Histórico da contratação e abertura da OS</h3>{!preparacao.historico.length ? <p>Sem novos registros administrativos de contratação. Os registros anteriores permanecem disponíveis nos módulos de acompanhamento.</p> : preparacao.historico.map(e => <article key={e.id}><strong>{e.acao === "abrir_os" ? "Abertura da OS" : "Contratação e abertura da OS"} · Contratação #{e.contratacao_id} · OS #{e.ordem_servico_id}</strong><small>{e.administrador_nome} · {data(e.criado_em)}</small><p>{e.registro_interno}</p></article>)}</section>
      </>}
    </section>}
  </main>;
}
