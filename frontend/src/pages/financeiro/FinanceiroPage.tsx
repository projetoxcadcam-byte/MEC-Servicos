import { useEffect, useRef, useState, type FormEvent } from "react";
import { Banknote, RefreshCw, History } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { identificador } from "../painel/painelPortal";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { acoes, dataFinanceiro, dinheiro, erroFinanceiro, estados, formas, lerValor,
  type Consulta, type Detalhe, type Movimento, type Pagina, type PerfilFinanceiro, type Resumo } from "./financeiroPortal";
import "./Financeiro.css";
import "./FinanceiroTema.css";

const ADMIN = "/administracao/financeiro/contratacoes";
type Corpo = { registro_interno: string; acao?: string; versao?: number; chave_operacao?: string;
  valor?: string; forma_pagamento?: string; referencia?: string; movimento_id?: number };

function Movimentos({ itens, titulo }: { itens: Movimento[]; titulo: string }) {
  return <section className="fin-card"><h3>{titulo}</h3>{!itens.length ? <p>Nenhum movimento registrado.</p> :
    <div className="fin-scroll"><table><thead><tr><th>Registro</th><th>Valor</th><th>Forma</th><th>Situação</th><th>Data</th></tr></thead>
      <tbody>{itens.map(m => <tr key={`${m.tipo}-${m.id}`}><td>#{m.id}</td><td>{dinheiro(m.valor)}</td><td>{formas[m.forma_pagamento] ?? "Outro"}</td>
        <td>{estados[m.status] ?? "Indisponível"}{m.estornado_em && <small>{dataFinanceiro(m.estornado_em)}</small>}</td><td>{dataFinanceiro(m.registrado_em)}</td></tr>)}</tbody></table></div>}</section>;
}

export default function FinanceiroPage({ perfil }: { perfil: PerfilFinanceiro }) {
  const { user } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const selecao = identificador(parametros.get("contratacao"));
  function setSelecao(id: number) { setParametros(id ? { contratacao: String(id) } : {}, { replace: true }); }
  const [pagina, setPagina] = useState<Pagina<Resumo | Consulta> | null>(null);
  const [detalhe, setDetalhe] = useState<Detalhe | Consulta | null>(null);
  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(false); const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState(""); const [aviso, setAviso] = useState("");
  const [acao, setAcao] = useState(""); const [valor, setValor] = useState(""); const [forma, setForma] = useState("pix");
  const [referencia, setReferencia] = useState(""); const [registro, setRegistro] = useState(""); const [movimento, setMovimento] = useState("");
  const [confirmacao, setConfirmacao] = useState<Corpo | null>(null);
  const repeticao = useRef<{ assinatura: string; corpo: Corpo } | null>(null);
  const trava = useRef(false); const operacao = useRef(0);
  const admin = perfil === "admin";
  const endpoint = admin ? ADMIN : `/portal-${perfil}/financeiro`;
  const params = admin ? {} : { [perfil === "cliente" ? "empresa_cliente_id" : "empresa_fornecedora_id"]: user?.empresa_id };
  const escolhida = pagina?.itens.find(c => c.contratacao_id === selecao) ?? pagina?.itens[0];
  const cid = selecao || escolhida?.contratacao_id || 0;
  const dadosAdmin = detalhe && "resumo" in detalhe && detalhe.resumo.contratacao_id === cid ? detalhe : null;
  const dadosPortal = detalhe && "movimentos" in detalhe && detalhe.contratacao_id === cid ? detalhe : null;
  const resumo = dadosAdmin?.resumo;
  const permitidas = resumo?.pode_iniciar ? ["iniciar"] : dadosAdmin?.acoes_permitidas ?? [];
  const atual = permitidas.includes(acao) ? acao : permitidas[0] ?? "";
  const novo = ["recebimento", "repasse"].includes(atual); const estorno = atual.startsWith("estornar_");
  const alvos = (atual === "estornar_recebimento" ? dadosAdmin?.recebimentos : dadosAdmin?.repasses)?.filter(m => m.status === "confirmado") ?? [];

  useEffect(() => {
    operacao.current += 1; trava.current = false; setOcupado(false);
    return () => { operacao.current += 1; };
  }, [perfil, user?.usuario_id]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setPagina(null); setDetalhe(null); setErro(""); setCarregando(true);
    void api.get<Pagina<Resumo | Consulta>>(endpoint, { params: { ...params, deslocamento, limite: 20 }, signal: controle.signal, timeout: 20000 })
      .then(({ data }) => { if (vigente) { if (data.total && deslocamento >= data.total) setDeslocamento(0); else setPagina(data); } })
      .catch(e => { if (vigente && !controle.signal.aborted) setErro(erroFinanceiro(e)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); };
  }, [perfil, user?.usuario_id, deslocamento, revisao]);

  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setDetalhe(null); setAcao(""); setValor(""); setReferencia(""); setRegistro(""); setMovimento(""); setConfirmacao(null); repeticao.current = null;
    if (cid) void api.get<Detalhe | Consulta>(`${endpoint}/${cid}`, { params, signal: controle.signal, timeout: 20000 })
      .then(({ data }) => { if (vigente) setDetalhe(data); })
      .catch(e => { if (vigente && !controle.signal.aborted) setErro(erroFinanceiro(e)); });
    return () => { vigente = false; controle.abort(); };
  }, [cid, perfil, user?.usuario_id, revisao]);

  function conferir(e: FormEvent) {
    e.preventDefault(); if (!resumo || !atual || trava.current) return;
    const quantia = novo ? lerValor(valor) : null;
    if (novo && !quantia) { setErro("Informe o valor em reais, como 12500,00. Use até duas casas decimais."); return; }
    if (registro.trim().length < 3 || ((novo || estorno) && referencia.trim().length < 3) || (estorno && !movimento)) {
      setErro("Preencha o registro interno, a referência e o movimento quando solicitado."); return;
    }
    const corpo: Corpo = { registro_interno: registro.trim(), ...(atual === "iniciar" ? {} : { acao: atual, versao: resumo.versao }),
      ...(novo ? { valor: quantia!, forma_pagamento: forma } : {}), ...((novo || estorno) ? { referencia: referencia.trim() } : {}),
      ...(estorno ? { movimento_id: Number(movimento) } : {}) };
    const assinatura = JSON.stringify(corpo);
    if (repeticao.current?.assinatura === assinatura) setConfirmacao(repeticao.current.corpo);
    else {
      if (atual !== "iniciar") corpo.chave_operacao = crypto.randomUUID();
      repeticao.current = { assinatura, corpo }; setConfirmacao(corpo);
    }
    setErro(""); setAviso("");
  }

  async function salvar() {
    if (!confirmacao || trava.current || !resumo) return;
    trava.current = true; setOcupado(true); const vigente = ++operacao.current;
    try {
      await api.post(`${ADMIN}/${cid}/${confirmacao.acao ? "eventos" : "iniciar"}`, confirmacao, { timeout: 20000 });
      if (vigente !== operacao.current) return;
      setAviso("Registro financeiro salvo. Os saldos foram atualizados."); setConfirmacao(null); setRevisao(v => v + 1);
    } catch (e) {
      if (vigente === operacao.current) { setErro(erroFinanceiro(e)); setConfirmacao(null); }
    } finally { trava.current = false; if (vigente === operacao.current) setOcupado(false); }
  }

  return <div className="fin-page">
    <header><div><h1><Banknote size={28} aria-hidden="true" />{admin ? "Financeiro administrativo" : perfil === "cliente" ? "Pagamentos e saldo" : "Repasses e saldo"}</h1>
      <p>{admin ? "Registre recebimentos e repasses já realizados. Cada operação exige conferência e fica no histórico administrativo." :
        perfil === "cliente" ? "Consulte os recebimentos confirmados pela administração e o saldo das suas contratações." : "Consulte os repasses confirmados pela administração e os valores a receber."}</p></div>
      <div className="fin-header-acoes">{admin && <Link className="fin-button" to="/admin/resultado-administracao">Resultado da administração</Link>}{admin && <Link className="fin-button" to={"/admin/extrato-financeiro?data_inicial=&data_final=" + (cid ? "&contratacao_id=" + cid : "")}>Extrato financeiro{cid ? ` da contratação #${cid}` : ""}</Link>}
      <button type="button" disabled={ocupado || carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} />Atualizar</button></div></header>
    {erro && <p className="fin-error" role="alert">{erro}</p>}{aviso && <p className="fin-success" role="status">{aviso}</p>}
    <section className="fin-card"><h2>Contratações</h2>{carregando ? <p role="status">Carregando contratações…</p> : !pagina?.itens.length ? <p>Nenhuma contratação disponível para esta conta.</p> : <>
      <div className="fin-scroll"><table><thead><tr><th>Contratação / OS</th>{admin && <th>Cliente / fornecedor</th>}<th>Valor contratado</th><th>Situação</th><th>Consulta</th></tr></thead><tbody>
        {pagina.itens.map(c => <tr key={c.contratacao_id} className={cid === c.contratacao_id ? "fin-selected" : ""}>
          <td>#{c.contratacao_id}<small>{c.ordem_servico_id ? `OS #${c.ordem_servico_id}` : "Sem ordem de serviço"}</small></td>
          {admin && "cliente" in c && <td>{c.cliente}<small>{c.fornecedor}</small></td>}<td>{dinheiro(c.valor_contratado)}</td><td>{estados[c.status] ?? "Indisponível"}</td>
          <td><button type="button" aria-pressed={cid === c.contratacao_id} disabled={ocupado} onClick={() => { setSelecao(c.contratacao_id); setErro(""); setAviso(""); }}>Abrir</button></td></tr>)}
      </tbody></table></div><nav className="fin-pagination" aria-label="Páginas de contratações"><span>{deslocamento + 1}–{Math.min(deslocamento + 20, pagina.total)} de {pagina.total}</span>
        <button disabled={ocupado || deslocamento === 0} onClick={() => setDeslocamento(d => Math.max(0, d - 20))}>Anterior</button>
        <button disabled={ocupado || deslocamento + 20 >= pagina.total} onClick={() => setDeslocamento(d => d + 20)}>Próxima</button></nav></>}</section>
    {cid > 0 && !detalhe && <p role="status">Carregando financeiro da contratação #{cid}…</p>}
    {(resumo || dadosPortal) && <section className="fin-card"><h2>Contratação #{cid}{(resumo ?? dadosPortal)!.ordem_servico_id ? ` · OS #${(resumo ?? dadosPortal)!.ordem_servico_id}` : ""}</h2>
      <div className="fin-totals"><div><span>Valor contratado</span><strong>{dinheiro((resumo ?? dadosPortal)!.valor_contratado)}</strong></div>
        {resumo ? <><div><span>Valor devido ao fornecedor</span><strong>{dinheiro(resumo.valor_fornecedor)}</strong></div><div><span>Ganho bruto previsto do ADM</span><strong>{dinheiro(resumo.acrescimo_administracao)}</strong></div><div><span>Recebido do cliente</span><strong>{dinheiro(resumo.total_recebido)}</strong></div><div><span>Saldo do cliente</span><strong>{dinheiro(resumo.saldo_cliente)}</strong></div>
          <div><span>Repassado ao fornecedor</span><strong>{dinheiro(resumo.total_repassado)}</strong></div><div><span>Saldo do fornecedor</span><strong>{dinheiro(resumo.saldo_fornecedor)}</strong></div>
          <div><span>Disponível para repasse</span><strong>{dinheiro(resumo.disponivel_repasse)}</strong></div></> : <><div><span>{perfil === "cliente" ? "Recebimentos confirmados" : "Repasses confirmados"}</span><strong>{dinheiro(dadosPortal!.total_confirmado)}</strong></div>
          <div><span>{perfil === "cliente" ? "Saldo a pagar" : "Saldo a receber"}</span><strong>{dinheiro(dadosPortal!.saldo)}</strong></div></>}</div>
      <p>{(resumo ?? dadosPortal)!.entrega_concluida ? "Entrega ao cliente concluída." : "Entrega ao cliente aguardando conclusão administrativa."}</p>
      {resumo && <p>Contratação: {estados[resumo.contratacao_status] ?? "Indisponível"}. Recebimentos pelo preço final ao cliente; repasses limitados ao custo contratado do fornecedor.</p>}</section>}
    {resumo && <section className="fin-card"><h2>Registrar operação</h2>{!permitidas.length ? <p>Nenhuma operação disponível para a situação atual.</p> :
      <form onSubmit={conferir}><fieldset disabled={ocupado || !!confirmacao}><label>Ação<select value={atual} onChange={e => { setAcao(e.target.value); setMovimento(""); }}>
        {permitidas.map(a => <option key={a} value={a}>{acoes[a]}</option>)}</select></label>
        {novo && <div className="fin-fields"><label>Valor em reais<input inputMode="decimal" value={valor} onChange={e => setValor(e.target.value)} placeholder="12500,00" maxLength={20} required /></label>
          <label>Forma de pagamento<select value={forma} onChange={e => setForma(e.target.value)}>{Object.entries(formas).map(([v,r]) => <option key={v} value={v}>{r}</option>)}</select></label></div>}
        {estorno && <label>Movimento a estornar<select value={movimento} onChange={e => setMovimento(e.target.value)} required><option value="">Escolha o registro</option>
          {alvos.map(m => <option key={m.id} value={m.id}>#{m.id} · {dinheiro(m.valor)} · {dataFinanceiro(m.registrado_em)}</option>)}</select></label>}
        {(novo || estorno) && <label>Referência do comprovante<input value={referencia} onChange={e => setReferencia(e.target.value)} minLength={3} maxLength={200} required placeholder="Ex.: TESTE-RECEB-OS3-001" /></label>}
        <label>Registro interno<textarea value={registro} onChange={e => setRegistro(e.target.value)} required minLength={3} maxLength={2000} rows={3} placeholder="Descreva a conferência ou o motivo. Visível somente à administração." /></label>
        <button className="fin-primary" type="submit">Conferir registro</button></fieldset></form>}
      {confirmacao && <div className="fin-confirm" role="region" aria-label="Confirmação do registro"><h3>{acoes[confirmacao.acao ?? "iniciar"]}</h3>
        {confirmacao.valor && <p>Valor: <strong>{dinheiro(confirmacao.valor)}</strong> · {formas[confirmacao.forma_pagamento!]}</p>}
        {confirmacao.movimento_id && <p>Movimento #{confirmacao.movimento_id}</p>}{confirmacao.referencia && <p>Comprovante: {confirmacao.referencia}</p>}
        <p>{confirmacao.registro_interno}</p><p>Confirme somente após conferir a operação realizada.</p>
        <button className="fin-primary" disabled={ocupado} onClick={salvar}>{ocupado ? "Salvando…" : "Confirmar registro"}</button>
        <button disabled={ocupado} onClick={() => setConfirmacao(null)}>Voltar à conferência</button></div>}</section>}
    {dadosAdmin && <><Movimentos itens={dadosAdmin.recebimentos} titulo="Recebimentos do cliente" /><Movimentos itens={dadosAdmin.repasses} titulo="Repasses ao fornecedor" />
      <section className="fin-card"><h2><History size={20} aria-hidden="true" /> Histórico administrativo</h2>{!dadosAdmin.historico.length ? <p>O histórico começa ao iniciar o controle financeiro. Pagamentos anteriores permanecem na lista de recebimentos.</p> :
        <ol className="fin-history">{dadosAdmin.historico.map(h => <li key={h.id}><strong>{acoes[h.acao] ?? "Registro financeiro"}</strong><small>{dataFinanceiro(h.criado_em)} · {h.administrador_nome}</small>
          {h.valor_centavos !== null && <p>{dinheiro(h.valor_centavos / 100)}</p>}{h.referencia && <p>Comprovante: {h.referencia}</p>}<p>{h.registro_interno}</p></li>)}</ol>}</section></>}
    {dadosPortal && <Movimentos itens={dadosPortal.movimentos} titulo={perfil === "cliente" ? "Recebimentos registrados" : "Repasses registrados"} />}
  </div>;
}
