import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { identificador } from "../painel/painelPortal";
import { ClipboardCheck, History, RefreshCw, Truck } from "lucide-react";
import { api } from "../../services/api";
import { useAuth } from "../../auth/AuthContext";
import { dataIntermediacao, mensagemIntermediacao, rotulosAcao, statusVisivel,
  type ContratacaoSemOrdem, type DetalheIntermediacao, type PaginaIntermediacao } from "./intermediacaoPortal";
import "./Intermediacao.css";

const BASE = "/administracao/intermediacao";
const ACOES_QUANTIDADE = ["receber_pecas", "aprovar_pecas", "entregar_cliente"];
const ACOES_REFERENCIA = ["encaminhar_material", "receber_pecas", "encaminhar_retrabalho", "entregar_cliente"];
const ACOES_PARECER = ["aprovar_pecas", "solicitar_retrabalho"];

export default function AdminIntermediacaoPage() {
  const { user } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const selecao = identificador(parametros.get("ordem"));
  const contratoDireto = identificador(parametros.get("contratacao"));
  function setSelecao(id: number) { setParametros(id ? { ordem: String(id) } : {}, { replace: true }); }
  const [pagina, setPagina] = useState<PaginaIntermediacao | null>(null);
  const [contratos, setContratos] = useState<ContratacaoSemOrdem[]>([]);
  const [contrato, setContrato] = useState(contratoDireto);
  useEffect(() => setContrato(contratoDireto), [contratoDireto]);
  const [detalhe, setDetalhe] = useState<DetalheIntermediacao | null>(null);
  const [filtro, setFiltro] = useState("todos"); const [deslocamento, setDeslocamento] = useState(0);
  const [revisao, setRevisao] = useState(0); const [carregando, setCarregando] = useState(true);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false); const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState(""); const [aviso, setAviso] = useState("");
  const [acao, setAcao] = useState(""); const [registro, setRegistro] = useState("");
  const [referencia, setReferencia] = useState(""); const [parecer, setParecer] = useState(""); const [quantidade, setQuantidade] = useState("");
  const [confirmacao, setConfirmacao] = useState<"evento" | "ordem" | null>(null);
  const trava = useRef(false); const operacao = useRef(0);
  const selecionada = pagina?.itens.find((item) => item.ordem_servico_id === selecao) ?? pagina?.itens[0];
  const ordemId = selecao || selecionada?.ordem_servico_id || 0;
  const dados = detalhe?.ordem.ordem_servico_id === ordemId ? detalhe : null;
  const acoes = dados?.ordem.pode_iniciar ? ["iniciar_ciclo"] : dados?.acoes_permitidas ?? [];
  const acaoAtual = acoes.includes(acao) ? acao : acoes[0] ?? "";

  useEffect(() => () => { operacao.current += 1; }, []);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setCarregando(true); setErro(""); setPagina(null);
    void Promise.all([
      api.get<PaginaIntermediacao>(`${BASE}/ordens`, { params: { filtro, deslocamento, limite: 20 }, signal: controle.signal, timeout: 20_000 }),
      api.get<ContratacaoSemOrdem[]>(`${BASE}/contratacoes-sem-ordem`, { signal: controle.signal, timeout: 20_000 }),
    ]).then(([lista, novas]) => {
      if (!vigente) return;
      if (lista.data.total && deslocamento >= lista.data.total) { setDeslocamento(Math.floor((lista.data.total - 1) / 20) * 20); return; }
      setPagina(lista.data); setContratos(novas.data);
    }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemIntermediacao(falha)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); };
  }, [filtro, deslocamento, revisao]);

  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setDetalhe(null); setCarregandoDetalhe(Boolean(ordemId));
    setAcao(""); setRegistro(""); setReferencia(""); setParecer(""); setQuantidade(""); setConfirmacao(null);
    if (!ordemId) return () => controle.abort();
    void api.get<DetalheIntermediacao>(`${BASE}/ordens/${ordemId}`, { signal: controle.signal, timeout: 20_000 })
      .then(({ data }) => { if (vigente && data.ordem.ordem_servico_id === ordemId) setDetalhe(data); })
      .catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemIntermediacao(falha)); })
      .finally(() => { if (vigente) setCarregandoDetalhe(false); });
    return () => { vigente = false; controle.abort(); };
  }, [ordemId, revisao]);

  function validarEvento() {
    if (!dados || !acaoAtual || registro.trim().length < 3) { setErro("Descreva o registro interno com pelo menos 3 caracteres."); return; }
    if (ACOES_REFERENCIA.includes(acaoAtual) && referencia.trim().length < 3) { setErro("Informe a referência do comprovante."); return; }
    if (ACOES_PARECER.includes(acaoAtual) && parecer.trim().length < 3) { setErro("Informe o parecer técnico da avaliação."); return; }
    if (ACOES_QUANTIDADE.includes(acaoAtual) && (!Number.isInteger(Number(quantidade)) || Number(quantidade) !== dados.ordem.quantidade)) {
      setErro(`Confira a quantidade total do lote: ${dados.ordem.quantidade} peças.`); return;
    }
    setErro(""); setConfirmacao("evento");
  }
  async function confirmar() {
    if (trava.current || !confirmacao) return;
    const tipo = confirmacao; const vigente = ++operacao.current;
    trava.current = true; setOcupado(true); setErro(""); setAviso("");
    try {
      let resposta: DetalheIntermediacao;
      if (tipo === "ordem") {
        resposta = (await api.post<DetalheIntermediacao>(`${BASE}/contratacoes/${contrato}/ordem`, {
          registro_interno: registro.trim(),
        }, { timeout: 20_000 })).data;
      } else {
        if (!dados) return;
        const corpo = acaoAtual === "iniciar_ciclo" ? { registro_interno: registro.trim() } : {
          acao: acaoAtual, versao: dados.ordem.versao, registro_interno: registro.trim(),
          ...(ACOES_REFERENCIA.includes(acaoAtual) ? { referencia: referencia.trim() } : {}),
          ...(ACOES_PARECER.includes(acaoAtual) ? { parecer_tecnico: parecer.trim() } : {}),
          ...(ACOES_QUANTIDADE.includes(acaoAtual) ? { quantidade_conferida: Number(quantidade) } : {}),
        };
        resposta = (await api.post<DetalheIntermediacao>(`${BASE}/ordens/${dados.ordem.ordem_servico_id}/${acaoAtual === "iniciar_ciclo" ? "iniciar" : "eventos"}`,
          corpo, { timeout: 20_000 })).data;
      }
      if (vigente !== operacao.current) return;
      setSelecao(resposta.ordem.ordem_servico_id); setAviso(tipo === "ordem" ? "Ordem criada. Inicie o ciclo administrativo." : "Registro administrativo concluído.");
      setConfirmacao(null); setFiltro("todos"); setDeslocamento(0); setRevisao((v) => v + 1);
    } catch (falha: unknown) {
      if (vigente === operacao.current) { setErro(mensagemIntermediacao(falha)); setConfirmacao(null); }
    } finally {
      trava.current = false;
      if (vigente === operacao.current) setOcupado(false);
    }
  }

  return <main className="p31-page">
    <header className="p31-header"><div><p className="p31-eyebrow"><Truck size={16} /> ADMINISTRAÇÃO</p>
      <h1>Intermediação de serviços</h1><p>Material, coleta, avaliação das peças e entrega final sob responsabilidade da administração.</p></div>
      <button className="p31-button" disabled={carregando || ocupado} onClick={() => { setAviso(""); setRevisao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>
    <p className="p31-notice">Cliente e fornecedor acompanham o andamento pelos portais. Os registros internos, pareceres e comprovantes ficam com a administração. Cada ciclo controla o lote completo da ordem.</p>
    {erro && <p className="p31-alert p31-error" role="alert">{erro}</p>}{aviso && <p className="p31-alert p31-success" role="status">{aviso}</p>}
    {contratos.length > 0 && <section className="p31-panel"><h2>Contratações ativas sem ordem</h2><p>Crie a ordem a partir de uma contratação já registrada.</p>
      <label>Contratação<select disabled={ocupado} value={contrato} onChange={(e) => setContrato(Number(e.target.value))}><option value={0}>Selecione</option>{contratos.map((item) =>
        <option key={item.id} value={item.id}>#{item.id} · Solicitação #{item.solicitacao_id} · {item.cliente} / {item.fornecedor}</option>)}</select></label>
      <label>Registro interno para criação<textarea disabled={ocupado} value={registro} maxLength={2000} onChange={(e) => setRegistro(e.target.value)} /></label>
      <button className="p31-button" disabled={!contratos.some(c => c.id === contrato) || ocupado || registro.trim().length < 3} onClick={() => setConfirmacao("ordem")}>Revisar criação da ordem</button></section>}
    <section className="p31-panel" aria-busy={carregando}><div className="p31-header"><h2>Ordens de serviço</h2><label>Exibir<select value={filtro} disabled={ocupado} onChange={(e) => { setSelecao(0); setDeslocamento(0); setFiltro(e.target.value); }}>
      <option value="todos">Todas</option><option value="sem_ciclo">Sem ciclo</option><option value="em_andamento">Ciclos em andamento</option><option value="finalizados">Ciclos finalizados</option></select></label></div>
      {carregando ? <p role="status">Carregando ordens…</p> : pagina?.itens.length === 0 ? <p>Nenhuma ordem neste filtro.</p> : pagina && <div className="p31-table"><table><thead><tr><th>Ordem</th><th>Cliente / fornecedor</th><th>Etapa administrativa</th><th>OS</th><th>Consulta</th></tr></thead><tbody>{pagina.itens.map((item) =>
        <tr key={item.ordem_servico_id} className={ordemId === item.ordem_servico_id ? "p31-selected" : ""}><td><strong>OS #{item.ordem_servico_id}</strong><small>Solicitação #{item.solicitacao_id} · {item.quantidade} peças</small></td>
          <td>{item.cliente}<small>{item.fornecedor}</small></td><td>{statusVisivel(item.status)}</td><td>{item.ordem_status === "concluida" ? "Concluída" : item.ordem_status === "cancelada" ? "Cancelada" : item.ordem_status === "em_execucao" ? "Em execução" : "Aberta"}</td>
          <td><button className="p31-button" disabled={ocupado} onClick={() => setSelecao(item.ordem_servico_id)}>Ver ciclo</button></td></tr>)}</tbody></table></div>}
      {pagina && pagina.total > 0 && <div className="p31-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + pagina.itens.length, pagina.total)} de {pagina.total}</span><div>
        <button className="p31-button" disabled={ocupado || carregando || deslocamento === 0} onClick={() => setDeslocamento((v) => Math.max(0, v - 20))}>Anterior</button>
        <button className="p31-button" disabled={ocupado || carregando || deslocamento + 20 >= pagina.total} onClick={() => setDeslocamento((v) => v + 20)}>Próxima</button></div></div>}
    </section>
    {ordemId > 0 && <section className="p31-panel" aria-busy={carregandoDetalhe}><h2><ClipboardCheck size={20} /> Ciclo da OS #{ordemId}</h2>
      {carregandoDetalhe ? <p role="status">Carregando ciclo…</p> : dados && <>
        <dl className="p31-fields"><div><dt>Etapa</dt><dd>{statusVisivel(dados.ordem.status)}</dd></div><div><dt>Quantidade do lote</dt><dd>{dados.ordem.quantidade} peças</dd></div>
          <div><dt>Produção informada</dt><dd>{dados.ordem.producao_etapa === "pronto_para_envio" ? "Pronto para coleta" : dados.ordem.producao_etapa ? "Em acompanhamento" : "Sem atualização"}</dd></div>
          <div><dt>Último registro</dt><dd>{dataIntermediacao(dados.ordem.atualizado_em)}</dd></div></dl>
        {!dados.ordem.ciclo_id && !dados.ordem.pode_iniciar && <p className="p31-notice">Ordem anterior concluída/cancelada ou contratação sem condição de execução. O histórico permanece disponível em Entregas dos portais. Um novo ciclo exige uma ordem aberta ou em execução e contratação ativa.</p>}
        {acoes.length > 0 && <form onSubmit={(e) => { e.preventDefault(); validarEvento(); }}><h3>Próximo registro administrativo</h3>
          <label>Ação<select value={acaoAtual} disabled={ocupado} onChange={(e) => { setAcao(e.target.value); setConfirmacao(null); }}>{acoes.map((item) => <option key={item} value={item}>{rotulosAcao[item]}</option>)}</select></label>
          {acaoAtual === "solicitar_coleta" && <p className="p31-notice">O fornecedor precisa informar Pronto para coleta na página Produção. A administração registra a solicitação e o recebimento físico das peças.</p>}
          <label>Registro interno<textarea required minLength={3} maxLength={2000} disabled={ocupado} value={registro} onChange={(e) => setRegistro(e.target.value)} /></label>
          {ACOES_REFERENCIA.includes(acaoAtual) && <label>Referência do comprovante<input required minLength={3} maxLength={200} disabled={ocupado} value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="Número ou identificação do documento de movimentação" /></label>}
          {ACOES_QUANTIDADE.includes(acaoAtual) && <label>Quantidade conferida do lote completo<input type="number" required min={1} step={1} disabled={ocupado} value={quantidade} onChange={(e) => setQuantidade(e.target.value)} /></label>}
          {ACOES_PARECER.includes(acaoAtual) && <label>Parecer técnico interno<textarea required minLength={3} maxLength={4000} disabled={ocupado} value={parecer} onChange={(e) => setParecer(e.target.value)} placeholder="Registre verificações, resultados e a decisão sobre o lote." /></label>}
          <button className="p31-button p31-primary" disabled={ocupado} type="submit">Revisar registro</button></form>}
        <h3><History size={18} /> Histórico administrativo</h3>
        {!dados.historico.length ? <p>Sem registros administrativos neste ciclo.</p> : <ol className="p31-timeline">{dados.historico.slice().reverse().map((item) => <li key={item.id}><strong>{rotulosAcao[item.acao]}</strong>
          <p>{statusVisivel(item.status_resultante)} · {dataIntermediacao(item.criado_em)}</p><p>Registrado por {item.administrador_nome} · conta #{item.usuario_admin_id}</p><p className="p31-text">{item.registro_interno}</p>
          {item.referencia && <p>Comprovante: {item.referencia}</p>}{item.quantidade_conferida !== null && <p>Quantidade conferida: {item.quantidade_conferida}</p>}{item.parecer_tecnico && <p className="p31-text">Parecer: {item.parecer_tecnico}</p>}</li>)}</ol>}
      </>}
    </section>}
    {confirmacao && <div className="p31-overlay"><section className="p31-modal" role="dialog" aria-modal="true" aria-labelledby="p31-confirmar"><h2 id="p31-confirmar">Confirmar registro</h2>
      <p>{confirmacao === "ordem" ? `Criar ordem para a contratação #${contrato}` : `${rotulosAcao[acaoAtual]} · OS #${ordemId}`}</p>
      <p>Responsável: {user?.nome}</p><p className="p31-text">{registro}</p>{referencia && confirmacao === "evento" && <p>Comprovante: {referencia}</p>}
      {parecer && confirmacao === "evento" && <p className="p31-text">Parecer: {parecer}</p>}{ACOES_QUANTIDADE.includes(acaoAtual) && confirmacao === "evento" && <p>Quantidade conferida: {quantidade}</p>}
      {confirmacao === "evento" && acaoAtual === "entregar_cliente" && <p>Este registro confirma a entrega física ao cliente e conclui a ordem de serviço.</p>}
      {confirmacao === "evento" && acaoAtual === "cancelar" && <p>Este registro cancela o ciclo e a ordem. Descreva no registro interno o encaminhamento do material e das peças sob responsabilidade da administração.</p>}
      <div className="p31-actions"><button className="p31-button" disabled={ocupado} onClick={() => setConfirmacao(null)}>Voltar</button><button className="p31-button p31-primary" disabled={ocupado} onClick={() => void confirmar()}>{ocupado ? "Registrando…" : "Confirmar"}</button></div></section></div>}
  </main>;
}
