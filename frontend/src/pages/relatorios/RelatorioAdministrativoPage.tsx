import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Download, FileText, Printer, RefreshCw } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { identificador, situacoesPainel } from "../painel/painelPortal";
import { dataFinanceiro, dinheiro, estados, formas, type Movimento } from "../financeiro/financeiroPortal";
import { rotulosStatus, statusVisivel } from "../intermediacao/intermediacaoPortal";
import { erroRelatorio, origensRelatorio, type Relatorio } from "./relatorioPortal";
import "./RelatorioAdministrativo.css";

const ENDPOINT = "/administracao/relatorios/contratacoes/";
const etapas: Record<string, string> = { aguardando_material: "Aguardando material", em_usinagem: "Em usinagem",
  em_solda_dobra: "Em solda/dobra", em_acabamento: "Em acabamento", pronto_para_envio: "Pronto para coleta" };
const ordens: Record<string, string> = { aberta: "Aberta", em_execucao: "Em execução", concluida: "Concluída", cancelada: "Cancelada" };
function data(valor: string | null) { return valor ? dataFinanceiro(valor) : "—"; }

function MovimentosRelatorio({ itens, titulo }: { itens: Movimento[]; titulo: string }) {
  return <section className="rel34-card"><h2>{titulo}</h2>{!itens.length ? <p>Nenhum movimento registrado.</p> :
    <div className="rel34-scroll"><table><thead><tr><th>Registro</th><th>Valor</th><th>Forma</th><th>Situação</th><th>Registrado em</th><th>Estornado em</th></tr></thead>
      <tbody>{itens.map(m => <tr key={m.id}><td>#{m.id}</td><td>{dinheiro(m.valor)}</td><td>{formas[m.forma_pagamento] ?? "Outro"}</td>
        <td>{estados[m.status] ?? "Situação indisponível"}</td><td>{data(m.registrado_em)}</td><td>{data(m.estornado_em)}</td></tr>)}</tbody></table></div>}</section>;
}

export default function RelatorioAdministrativoPage() {
  const { user } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const valores = parametros.getAll("contratacao");
  const cid = valores.length === 1 ? identificador(valores[0]) : 0;
  const invalido = valores.length > 0 && !cid;
  const [texto, setTexto] = useState(cid ? String(cid) : "");
  const [relatorio, setRelatorio] = useState<Relatorio | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [revisao, setRevisao] = useState(0);
  const download = useRef<AbortController | null>(null);
  const operacao = useRef(0);
  const admin = user?.role === "admin";
  useEffect(() => { setTexto(cid ? String(cid) : ""); }, [cid]);
  useEffect(() => {
    operacao.current += 1; download.current?.abort(); setBaixando(false); setAviso("");
    return () => { operacao.current += 1; download.current?.abort(); };
  }, [cid, user?.usuario_id]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setRelatorio(null); setErro(invalido ? "Informe um número de contratação válido." : ""); setCarregando(false);
    if (admin && cid) {
      setCarregando(true);
      void api.get<Relatorio>(ENDPOINT + cid, { signal: controle.signal, timeout: 20000 })
        .then(({ data: dados }) => { if (vigente) {
          if (dados.resumo.contratacao_id !== cid) throw new Error("contratacao_diverge");
          setRelatorio(dados);
        } })
        .catch(e => { if (vigente && !controle.signal.aborted) setErro(erroRelatorio(e)); })
        .finally(() => { if (vigente) setCarregando(false); });
    }
    return () => { vigente = false; controle.abort(); };
  }, [cid, invalido, admin, user?.usuario_id, revisao]);
  function consultar(e: FormEvent) {
    e.preventDefault();
    const numero = identificador(texto.trim());
    if (!numero) { setErro("Informe um número de contratação válido."); return; }
    setErro(""); setAviso("");
    if (numero === cid) setRevisao(v => v + 1);
    else setParametros({ contratacao: String(numero) });
  }
  async function exportar() {
    if (!relatorio || !cid || download.current && !download.current.signal.aborted || !admin) return;
    const controle = new AbortController(); download.current = controle; const atual = operacao.current;
    setBaixando(true); setErro(""); setAviso("");
    try {
      const resposta = await api.get<Blob>(ENDPOINT + cid + "/csv", { responseType: "blob", signal: controle.signal, timeout: 30000 });
      if (controle.signal.aborted || atual !== operacao.current) return;
      if (!resposta.data.type.startsWith("text/csv")) throw new Error("exportacao_invalida");
      const url = URL.createObjectURL(resposta.data);
      const link = document.createElement("a"); link.href = url; link.download = "MEC_SERVICOS_CONTRATACAO_" + cid + ".csv";
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setAviso("Exportação CSV preparada com os registros atuais da contratação #" + cid + ".");
    } catch (e) {
      if (!controle.signal.aborted && atual === operacao.current) setErro(erroRelatorio(e));
    } finally {
      if (atual === operacao.current) { setBaixando(false); download.current = null; }
    }
  }
  if (!admin) return <p role="alert">O relatório exige uma conta administrativa.</p>;
  const r = relatorio?.resumo; const c = relatorio?.cadastro;
  const anterior = r?.financeiro_status === "sem_controle" && r.contratacao_status !== "ativa";
  return <article className="rel34-page">
    <header className="rel34-cabecalho"><div><h1><FileText aria-hidden="true" /> Relatório da contratação</h1>
      <p>Produção, intermediação e financeiro reunidos para conferência administrativa.</p>
      {relatorio && <small>Consultado em {data(relatorio.gerado_em)} · Datas exibidas no horário deste computador.</small>}</div>
      <div className="rel34-acoes rel34-no-print"><button disabled={!cid || carregando || baixando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} /> Atualizar</button>
        <button disabled={!relatorio || carregando || baixando} onClick={() => window.print()}><Printer size={16} /> Imprimir / salvar PDF</button>
        <button disabled={!relatorio || carregando || baixando} onClick={() => void exportar()}><Download size={16} />{baixando ? "Preparando CSV…" : "Exportar CSV"}</button></div></header>
    <nav className="rel34-links rel34-no-print" aria-label="Consultas da contratação"><Link to="/admin">Voltar ao Dashboard</Link>
      {!!cid && <Link to={"/admin/pagamentos?contratacao=" + cid}>Financeiro</Link>}
      {!!r?.ordem_servico_id && <Link to={"/admin/intermediacao?ordem=" + r.ordem_servico_id}>Intermediação</Link>}</nav>
    <form className="rel34-consulta rel34-no-print" onSubmit={consultar}><label>Número da contratação<input value={texto} inputMode="numeric" maxLength={13}
      onChange={e => setTexto(e.target.value)} placeholder="Ex.: 1" /></label><button disabled={baixando} type="submit">Consultar</button></form>
    {erro && <p className="rel34-erro" role="alert">{erro}</p>}{aviso && <p className="rel34-sucesso rel34-no-print" role="status">{aviso}</p>}
    {carregando && <p role="status">Carregando relatório da contratação #{cid}…</p>}
    {!cid && !erro && <p>Abra uma contratação pelo Dashboard ou informe seu número acima.</p>}
    {relatorio && r && c && <>
      <section className="rel34-card"><h2>Contratação #{r.contratacao_id}{r.ordem_servico_id ? " · OS #" + r.ordem_servico_id : " · Sem OS"}</h2>
        <div className="rel34-dados"><div><span>Cliente</span><strong>{r.cliente}</strong><small>Empresa #{c.empresa_cliente_id}</small></div>
          <div><span>Fornecedor</span><strong>{r.fornecedor}</strong><small>Empresa #{c.empresa_fornecedora_id}</small></div>
          <div><span>Situação no painel</span><strong>{situacoesPainel[r.situacao]}</strong><small>Contratação: {estados[r.contratacao_status]}</small></div>
          <div><span>Ordem de serviço</span><strong>{r.ordem_status ? ordens[r.ordem_status] ?? "Situação indisponível" : "Sem OS"}</strong><small>{statusVisivel(r.etapa_administrativa)}</small></div>
          <div><span>Solicitação / cotação</span><strong>#{r.solicitacao_id} / #{c.cotacao_id}</strong></div>
          <div><span>Lote / prazo contratado</span><strong>{c.quantidade ?? "—"} peças · {c.prazo_dias} dias</strong></div>
          <div><span>Processo</span><strong>{c.processo ?? "Sem registro"}</strong></div><div><span>Material</span><strong>{c.material ?? "Sem registro"}</strong></div>
        </div>
        <dl className="rel34-datas"><div><dt>Contratada em</dt><dd>{data(c.contratada_em)}</dd></div>
          {c.encerrada_em && <div><dt>Contratação encerrada em</dt><dd>{data(c.encerrada_em)}</dd></div>}
          {c.cancelada_em && <div><dt>Contratação cancelada em</dt><dd>{data(c.cancelada_em)}</dd></div>}
          {c.ordem_criada_em && <div><dt>OS criada em</dt><dd>{data(c.ordem_criada_em)}</dd></div>}
          {c.ordem_iniciada_em && <div><dt>OS iniciada em</dt><dd>{data(c.ordem_iniciada_em)}</dd></div>}
          {c.ordem_concluida_em && <div><dt>OS concluída em</dt><dd>{data(c.ordem_concluida_em)}</dd></div>}
          {c.ordem_cancelada_em && <div><dt>OS cancelada em</dt><dd>{data(c.ordem_cancelada_em)}</dd></div>}</dl>
        {c.observacoes_contratacao && <p className="rel34-texto">Observações da contratação: {c.observacoes_contratacao}</p>}
      </section>
      <section className="rel34-card"><h2>Resumo financeiro · {estados[r.financeiro_status]}</h2><div className="rel34-dados">
        <div><span>Valor contratado</span><strong>{dinheiro(r.valor_contratado)}</strong></div>
        <div><span>Recebido confirmado</span><strong>{dinheiro(r.total_recebido)}</strong></div>
        <div><span>Repassado confirmado</span><strong>{dinheiro(r.total_repassado)}</strong></div>
        <div><span>{anterior ? "Diferença registrada do cliente" : "Saldo do cliente"}</span><strong>{dinheiro(r.saldo_cliente)}</strong></div>
        <div><span>{anterior ? "Diferença registrada do fornecedor" : "Saldo do fornecedor"}</span><strong>{dinheiro(r.saldo_fornecedor)}</strong></div>
        <div><span>Disponível para repasse</span><strong>{dinheiro(r.disponivel_repasse)}</strong></div></div>
        <p>Os totais consideram movimentos confirmados. Os estornos permanecem nas listas e no histórico.</p></section>
      {(r.pendencias.length > 0 || relatorio.avisos.length > 0) && <section className="rel34-card rel34-conferencia"><h2>Próximos passos e informações do histórico</h2>
        {!!r.pendencias.length && <ul>{r.pendencias.map(p => <li key={p.codigo}>{p.descricao}</li>)}</ul>}
        {!!relatorio.avisos.length && <ul>{relatorio.avisos.map(a => <li key={a}>{a}</li>)}</ul>}</section>}
      <MovimentosRelatorio itens={relatorio.recebimentos} titulo="Recebimentos do cliente" />
      <MovimentosRelatorio itens={relatorio.repasses} titulo="Repasses ao fornecedor" />
      <section className="rel34-card"><h2>Histórico consolidado · {relatorio.linha_tempo.length} registros</h2><p>Registros apresentados do mais antigo ao mais recente.</p>
        {!relatorio.linha_tempo.length ? <p>Sem eventos de produção, intermediação ou financeiro administrativo registrados.</p> :
          <ol className="rel34-historico">{relatorio.linha_tempo.map(e => <li key={e.origem + "-" + e.registro_id}>
            <div className="rel34-evento-titulo"><strong>{e.descricao}</strong><span>{origensRelatorio[e.origem]} · registro #{e.registro_id}{e.versao ? " · versão " + e.versao : ""}</span></div>
            <small>{data(e.data_utc)}</small>
            {e.situacao && <p>{e.origem === "producao" ? etapas[e.situacao] ?? "Etapa registrada" : rotulosStatus[e.situacao] ?? e.situacao}</p>}
            {e.responsavel && <p>Responsável: {e.responsavel}{e.usuario_admin_id ? " · conta #" + e.usuario_admin_id : e.empresa_fornecedora_id ? " · empresa #" + e.empresa_fornecedora_id : ""}</p>}
            {e.valor !== null && <p>Valor do registro: <strong>{dinheiro(e.valor)}</strong></p>}
            {e.quantidade !== null && <p>Quantidade conferida: {e.quantidade}</p>}
            {e.pagamento_id !== null && <p>Recebimento #{e.pagamento_id}</p>}{e.repasse_id !== null && <p>Repasse #{e.repasse_id}</p>}
            {e.referencia && <p className="rel34-texto">Referência: {e.referencia}</p>}
            {e.registro_interno && <p className="rel34-texto">{e.registro_interno}</p>}
            {e.parecer_tecnico && <p className="rel34-texto">Parecer técnico: {e.parecer_tecnico}</p>}
          </li>)}</ol>}</section>
      <footer className="rel34-rodape">MEC-Serviços · Relatório administrativo da contratação #{cid} · Consulta em {data(relatorio.gerado_em)}.</footer>
    </>}
  </article>;
}
