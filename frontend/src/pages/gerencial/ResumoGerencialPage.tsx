import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CalendarDays, Download, RefreshCw, Search } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { dataFinanceiro, dinheiro, estados } from "../financeiro/financeiroPortal";
import { filtrosPainel, situacoesPainel, type FiltroPainel } from "../painel/painelPortal";
import { diaUTC } from "../periodo/periodoPortal";
import { linkPendenciasGerencial, mensagemGerencial, nomeMes, type ConsultaGerencial, type FiltrosGerencial, type ResumoGerencial } from "./gerencialPortal";
import "../periodo/RelatorioPeriodo.css";
import "./ResumoGerencial.css";

const LIMITE = 20;
function anoAtual() { return String(new Date().getUTCFullYear()); }

function Valores({ resumo }: { resumo: ResumoGerencial }) {
  const i = resumo.indicadores;
  return <div className="periodo35-valores"><div><span>Valor contratado</span><strong>{dinheiro(resumo.valor_contratado)}</strong></div>
    <div><span>Recebido confirmado</span><strong>{dinheiro(i.recebimentos_confirmados)}</strong></div><div><span>Repassado confirmado</span><strong>{dinheiro(i.repasses_confirmados)}</strong></div>
    <div><span>Saldo a receber</span><strong>{dinheiro(i.saldo_clientes_controles_abertos)}</strong></div><div><span>Saldo a repassar</span><strong>{dinheiro(i.saldo_fornecedores_controles_abertos)}</strong></div><div><span>Disponível para repasse</span><strong>{dinheiro(i.disponivel_repasses)}</strong></div></div>;
}

export default function ResumoGerencialPage() {
  const { user } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const filtros = useMemo(() => ({ ano: parametros.get("ano") ?? anoAtual(), filtro: (parametros.get("filtro") || "todas") as FiltroPainel,
    busca: parametros.get("busca") || "", mes: parametros.get("mes") ?? undefined }), [parametros]);
  const [rascunho, setRascunho] = useState({ ano: filtros.ano, filtro: filtros.filtro, busca: filtros.busca });
  const [dados, setDados] = useState<ConsultaGerencial | null>(null);
  const [deslocamento, setDeslocamento] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [baixando, setBaixando] = useState(false);
  const [erro, setErro] = useState("");
  const [erroFormulario, setErroFormulario] = useState("");
  const [aviso, setAviso] = useState("");
  const download = useRef<AbortController | null>(null);

  useEffect(() => { setRascunho({ ano: filtros.ano, filtro: filtros.filtro, busca: filtros.busca }); setDeslocamento(0); setErroFormulario(""); }, [filtros]);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    download.current?.abort(); download.current = null;
    setDados(null); setErro(""); setAviso(""); setBaixando(false); setCarregando(true);
    if (user?.role !== "admin") { setCarregando(false); return () => controle.abort(); }
    void api.get<ConsultaGerencial>("/administracao/relatorios/gerencial", {
      params: { ...filtros, deslocamento, limite: LIMITE }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (!vigente) return;
      if (data.total && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / LIMITE) * LIMITE); return; }
      setDados(data);
    }).catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemGerencial(falha)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); download.current?.abort(); };
  }, [filtros, deslocamento, revisao, user?.role]);

  function aplicar(novos: FiltrosGerencial) {
    const p: Record<string, string> = { ano: String(novos.ano) };
    if (novos.filtro !== "todas") p.filtro = novos.filtro;
    if (novos.busca) p.busca = novos.busca;
    if (novos.mes) p.mes = String(novos.mes);
    setDeslocamento(0); setErroFormulario(""); setParametros(p); setRevisao(v => v + 1);
  }
  function consultar(evento: FormEvent) {
    evento.preventDefault();
    if (!/^[0-9]{1,4}$/.test(rascunho.ano) || Number(rascunho.ano) < 1 || Number(rascunho.ano) > 9999) {
      setErroFormulario("Informe um ano de 1 a 9999, como 2026."); return;
    }
    aplicar({ ano: Number(rascunho.ano), filtro: rascunho.filtro, busca: rascunho.busca.trim(), mes: null });
  }
  async function exportar() {
    if (!dados || carregando || baixando || user?.role !== "admin") return;
    const controle = new AbortController(); download.current = controle; setBaixando(true); setAviso("");
    try {
      const resposta = await api.get<Blob>("/administracao/relatorios/gerencial/csv", { params: dados.filtros,
        responseType: "blob", signal: controle.signal, timeout: 30_000 });
      if (controle.signal.aborted) return;
      if (!resposta.data.type.toLowerCase().startsWith("text/csv")) throw new Error("formato_csv_invalido");
      const url = URL.createObjectURL(resposta.data); const a = document.createElement("a");
      a.href = url; a.download = "MEC_SERVICOS_RESUMO_GERENCIAL_MENSAL.csv";
      try { document.body.appendChild(a); a.click(); setAviso("CSV exportado com o resumo anual, os 12 meses e todas as contratações do detalhamento aplicado."); }
      finally { a.remove(); URL.revokeObjectURL(url); }
    } catch (falha: unknown) { if (!controle.signal.aborted) setAviso(mensagemGerencial(falha)); }
    finally { if (download.current === controle) { download.current = null; setBaixando(false); } }
  }

  if (user?.role !== "admin") return <p role="alert">O resumo está disponível somente para a administração.</p>;
  const r = dados?.resumo_ano;
  const i = r?.indicadores;
  return <article className="periodo35 gerencial38">
    <header className="periodo35-cabecalho"><div><h1><CalendarDays aria-hidden="true" /> Resumo gerencial mensal</h1>
      <p>Compare os 12 meses do ano e consulte as situações e os valores atuais das contratações de cada mês.</p></div>
      <nav><Link to="/admin/resultado-administracao">Resultado da administração</Link><Link to="/admin">Voltar ao Dashboard</Link><Link to="/admin/relatorios-periodo">Relatório por período</Link><Link to="/admin/pendencias">Central de pendências</Link><Link to="/admin/comparativo-gerencial">Comparativo entre períodos</Link>
        <button type="button" disabled={carregando} onClick={() => setRevisao(v => v + 1)}><RefreshCw size={16} aria-hidden="true" /> Atualizar</button>
        <button type="button" disabled={!dados || carregando || baixando} onClick={() => void exportar()}><Download size={16} aria-hidden="true" /> {baixando ? "Exportando…" : "Exportar CSV"}</button></nav></header>
    <section className="periodo35-card"><h2>Selecionar o ano</h2>
      <form className="periodo35-filtros gerencial38-filtros" onSubmit={consultar}>
        <label>Ano (UTC)<input inputMode="numeric" maxLength={4} value={rascunho.ano} onChange={e => setRascunho(v => ({ ...v, ano: e.target.value }))} placeholder="2026" /></label>
        <label>Exibir<select value={rascunho.filtro} onChange={e => setRascunho(v => ({ ...v, filtro: e.target.value as FiltroPainel }))}>{Object.entries(filtrosPainel).map(([v, rotulo]) => <option key={v} value={v}>{rotulo}</option>)}</select></label>
        <label className="periodo35-busca">Buscar empresa, contratação ou OS<input type="search" maxLength={120} value={rascunho.busca} onChange={e => setRascunho(v => ({ ...v, busca: e.target.value }))} placeholder="Ex.: oficina, Contratação #1 ou OS #3" /></label>
        <button type="submit" disabled={carregando}><Search size={16} aria-hidden="true" /> Consultar</button>
        <button type="button" disabled={carregando} onClick={() => aplicar({ ano: Number(anoAtual()), filtro: "todas", busca: "", mes: null })}>Limpar filtros</button>
      </form>
      {erroFormulario && <p role="alert" className="periodo35-erro">{erroFormulario}</p>}
      <p className="periodo35-nota">O mês considera a criação da contratação em UTC. Situações, pendências, recebimentos e repasses mostram o estado e os acumulados atuais dessas contratações.</p>
    </section>
    {aviso && <p role="status" className="periodo35-aviso">{aviso}</p>}
    {carregando ? <p role="status">Consultando o resumo mensal…</p> : erro ? <p role="alert" className="periodo35-erro">{erro}</p> : dados && r && i && <>
      <section className="periodo35-card gerencial38-resumo"><h2>Resumo anual · {dados.filtros.ano}</h2>
        <p className="periodo35-aplicados">{filtrosPainel[dados.filtros.filtro]} · Busca: {dados.filtros.busca || "Todas"} · Detalhamento: {dados.filtros.mes ? nomeMes(dados.filtros.mes) : "Ano inteiro no CSV"}</p>
        <div className="gerencial38-contagens"><div><span>Contratações</span><strong>{i.total_contratacoes}</strong></div><div><span>Em andamento</span><strong>{r.em_andamento}</strong></div><div><span>Concluídas</span><strong>{i.contratacoes_concluidas}</strong></div><div><span>Canceladas</span><strong>{i.contratacoes_canceladas}</strong></div>
          <div><span>Para conferência</span><strong>{i.para_conferencia}</strong></div><div><span>Financeiros encerrados</span><strong>{i.financeiros_encerrados}</strong></div><div><span>Com pendências</span><strong>{r.contratacoes_com_pendencias}</strong></div></div>
        <Valores resumo={r} />
        <p className="periodo35-nota">Cada contratação soma uma vez. Valores excluem estornos; saldos e disponibilidade consideram controles financeiros abertos. O resumo anual permanece completo ao abrir um mês.</p>
        <small>Consultado em {dataFinanceiro(dados.gerado_em)}. O CSV consulta dados atuais com os filtros aplicados.</small>
      </section>
      <section className="periodo35-card gerencial38-meses"><h2>Os 12 meses de {dados.filtros.ano}</h2>
        {!i.total_contratacoes && <p className="gerencial38-vazio">Nenhuma contratação corresponde aos filtros deste ano.</p>}
        <div className="periodo35-scroll"><table><thead><tr><th className="gerencial38-mes-acoes">Mês / consulta</th><th>Contratações</th><th>Situações no painel</th><th>Financeiros</th><th>Pendências atuais</th><th>Valor contratado</th><th>Recebido confirmado</th><th>Repassado confirmado</th></tr></thead>
          <tbody>{dados.meses.map(m => <tr key={m.mes} className={dados.filtros.mes === m.mes ? "gerencial38-selecionado" : ""}>
            <td className="gerencial38-mes-acoes"><strong>{nomeMes(m.mes)}</strong><nav><button type="button" aria-pressed={dados.filtros.mes === m.mes} onClick={() => aplicar({ ...dados.filtros, mes: m.mes })}>Ver mês</button><Link to={linkPendenciasGerencial(dados.filtros, m)}>Pendências do mês</Link></nav></td><td>{m.indicadores.total_contratacoes}</td>
            <td><small>Em andamento: {m.em_andamento}</small><small>Concluídas: {m.indicadores.contratacoes_concluidas}</small><small>Canceladas: {m.indicadores.contratacoes_canceladas}</small><small>Conferência: {m.indicadores.para_conferencia}</small></td>
            <td>{m.indicadores.financeiros_encerrados} encerrado(s)<small>{m.indicadores.controles_abertos} aberto(s)</small></td>
            <td>{m.contratacoes_com_pendencias} contratação(ões)<small>Ações operacionais: {m.pendencias_operacionais}</small><small>Ações financeiras: {m.pendencias_financeiras}</small><small>Ações de conferência: {m.pendencias_conferencia}</small></td>
            <td>{dinheiro(m.valor_contratado)}</td><td>{dinheiro(m.indicadores.recebimentos_confirmados)}</td><td>{dinheiro(m.indicadores.repasses_confirmados)}</td>
          </tr>)}</tbody></table></div>
        <p className="periodo35-nota">Pendências contam ações por área. Uma contratação pode ter várias ações. Financeiros encerrados seguem a situação concluída do painel; divergências aparecem para conferência.</p>
      </section>
      {dados.resumo_mes && <section className="periodo35-card gerencial38-detalhe"><header><h2>Contratações de {nomeMes(dados.resumo_mes.mes)} · {dados.filtros.ano}</h2>
        <button type="button" onClick={() => aplicar({ ...dados.filtros, mes: null })}>Fechar detalhamento</button></header>
        <p>{dados.total} contratação(ões) · {dados.resumo_mes.contratacoes_com_pendencias} com pendências · {diaUTC(dados.resumo_mes.data_inicial)} até {diaUTC(dados.resumo_mes.data_final)}</p>
        <Valores resumo={dados.resumo_mes} />
        {!dados.total ? <p className="gerencial38-mes-vazio">Nenhuma contratação neste mês para os filtros aplicados.</p> : <>
          <div className="periodo35-scroll"><table><thead><tr><th>Contratação / OS</th><th>Contratada em (UTC)</th><th>Cliente / fornecedor</th><th>Situação</th><th>Valor contratado</th><th>Recebido</th><th>Repassado</th><th>Consultar</th></tr></thead>
            <tbody>{dados.itens.map(c => <tr key={c.contratacao_id}><td><strong>Contratação #{c.contratacao_id}</strong><small>{c.ordem_servico_id ? `OS #${c.ordem_servico_id}` : "Sem OS"}</small></td><td>{diaUTC(c.contratada_em)}</td>
              <td>{c.cliente}<small>Cliente ID #{c.empresa_cliente_id}</small>{c.fornecedor}<small>Fornecedor ID #{c.empresa_fornecedora_id}</small></td>
              <td>{situacoesPainel[c.situacao]}<small>{estados[c.financeiro_status]}</small></td><td>{dinheiro(c.valor_contratado)}</td><td>{dinheiro(c.total_recebido)}</td><td>{dinheiro(c.total_repassado)}</td>
              <td><nav><Link to={`/admin/relatorios?contratacao=${c.contratacao_id}`}>Relatório #{c.contratacao_id}</Link><Link to={`/admin/pagamentos?contratacao=${c.contratacao_id}`}>Financeiro</Link>
                {c.pendencias.length > 0 && <Link to={"/admin/pendencias?busca=" + encodeURIComponent("Contratação #" + c.contratacao_id)}>Pendências</Link>}</nav></td>
            </tr>)}</tbody></table></div>
          <nav className="periodo35-paginacao gerencial38-paginacao" aria-label="Páginas das contratações do mês"><span>{deslocamento + 1}–{Math.min(deslocamento + dados.itens.length, dados.total)} de {dados.total} contratações</span>
            <button type="button" disabled={!deslocamento || carregando} onClick={() => setDeslocamento(v => Math.max(0, v - LIMITE))}>Anterior</button><button type="button" disabled={deslocamento + LIMITE >= dados.total || carregando} onClick={() => setDeslocamento(v => v + LIMITE)}>Próxima</button></nav>
        </>}
      </section>}
    </>}
  </article>;
}
