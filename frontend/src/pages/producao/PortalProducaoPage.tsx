import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ClipboardList, Clock3, Factory, History, RefreshCw, Wrench, X } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from "../client/cotacoesCliente";
import { formatarMedidaContrato, rotuloContratacao, type PaginaContratacoes } from "../contratacoes/contratacoesPortal";
import { rotuloOrdem, type PerfilOrdens } from "../ordens/ordensPortal";
import { ETAPAS_PRODUCAO, etapaValida, mensagemErroProducao, rotuloEtapa, type AcompanhamentoProducao, type EtapaProducao, type EtapaValor, type OrdemProducao } from "./producaoPortal";
import "./PortalProducaoPage.css";

type Revisao = { chave: string; dono: string; ordem: OrdemProducao; etapa: EtapaValor; observacoes: string | null; ultimaId: number };

function dataHoraEtapa(valor: string): string | undefined {
  const instante = instanteUtc(valor);
  return instante === null ? undefined : new Date(instante).toISOString();
}

export default function PortalProducaoPage({ perfil }: { perfil: PerfilOrdens }) {
  const { user } = useAuth();
  const empresaId = user?.role === perfil ? user.id : 0;
  const dono = `${perfil}:${empresaId}`;
  const base = `/portal-${perfil}/producao`;
  const [deslocamento, setDeslocamento] = useState(0);
  const [atualizacao, setAtualizacao] = useState(0);
  const [lista, setLista] = useState<{ chave: string; pagina: PaginaContratacoes<OrdemProducao> } | null>(null);
  const [selecionadoId, setSelecionadoId] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erroLista, setErroLista] = useState("");
  const [detalhe, setDetalhe] = useState<{ chave: string; dados: AcompanhamentoProducao } | null>(null);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);
  const [erroDetalhe, setErroDetalhe] = useState("");
  const [atualizacaoDetalhe, setAtualizacaoDetalhe] = useState(0);
  const [rascunho, setRascunho] = useState({ chave: "", etapa: "", observacoes: "" });
  const [revisao, setRevisao] = useState<Revisao | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState<{ dono: string; texto: string } | null>(null);
  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);
  const [revalidar, setRevalidar] = useState("");
  const chaveLista = `${dono}:${deslocamento}:${atualizacao}`;
  const pagina = lista?.chave === chaveLista ? lista.pagina : null;
  const selecionada = pagina?.itens.find((o) => o.id === selecionadoId) ?? pagina?.itens[0];
  const chaveSelecao = `${dono}:${selecionada?.id ?? 0}`;
  const chaveDetalhe = `${chaveLista}:${chaveSelecao}:${atualizacaoDetalhe}`;
  const dados = detalhe?.chave === chaveDetalhe ? detalhe.dados : null;
  const ordem = dados?.ordem ?? selecionada;
  const rascunhoAtual = rascunho.chave === chaveSelecao ? rascunho : { etapa: "", observacoes: "" };
  const podeRegistrar = perfil === "fornecedor" && dados?.ordem.contratacao_status === "ativa" && ["aberta", "em_execucao"].includes(dados.ordem.status);
  const bloquear = enviando || carregando || carregandoDetalhe || !dados || revalidar === chaveDetalhe;
  const modalAtual = revisao?.chave === chaveDetalhe && revisao.dono === dono && podeRegistrar && !bloquear ? revisao
    : revisao?.chave === chaveDetalhe && revisao.dono === dono && podeRegistrar && enviando ? revisao : null;
  const parametrosEmpresa = perfil === "cliente" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };
  const contexto = useRef({ chaveLista, chaveDetalhe, dono });
  contexto.current = { chaveLista, chaveDetalhe, dono };
  const montada = useRef(true);
  const trava = useRef(false);
  const envio = useRef<AbortController | null>(null);
  const dialogo = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    montada.current = true;
    return () => { montada.current = false; envio.current?.abort(); };
  }, []);

  useEffect(() => { setDeslocamento(0); setSelecionadoId(0); setRevisao(null); envio.current?.abort(); }, [perfil, empresaId]);

  useEffect(() => {
    const controlador = new AbortController(); let vigente = true;
    setCarregando(true); setErroLista(""); setRevisao(null);
    if (!empresaId) {
      setErroLista(`Entre como ${perfil} para consultar a produção.`); setCarregando(false);
      return () => { vigente = false; controlador.abort(); };
    }
    async function carregar() {
      try {
        const { data } = await api.get<PaginaContratacoes<OrdemProducao>>(base, {
          params: { ...parametrosEmpresa, deslocamento, limite: 20 }, signal: controlador.signal, timeout: 20_000,
        });
        if (!vigente || contexto.current.chaveLista !== chaveLista) return;
        if (data.total > 0 && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }
        if (data.total === 0 && deslocamento > 0) { setDeslocamento(0); return; }
        const proprias = data.itens.filter((o) => (perfil === "cliente" ? o.empresa_cliente_id : o.empresa_fornecedora_id) === empresaId);
        setLista({ chave: chaveLista, pagina: { ...data, itens: proprias } });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.chaveLista === chaveLista) setErroLista(mensagemErroProducao(erro));
      } finally { if (vigente && contexto.current.chaveLista === chaveLista) setCarregando(false); }
    }
    void carregar();
    return () => { vigente = false; controlador.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, perfil, empresaId, deslocamento, chaveLista]);

  useEffect(() => {
    const controlador = new AbortController(); let vigente = true;
    setCarregandoDetalhe(Boolean(selecionada)); setErroDetalhe(""); setRevisao(null);
    if (!selecionada) return () => { vigente = false; controlador.abort(); };
    const ordemId = selecionada.id;
    async function carregar() {
      try {
        const { data } = await api.get<AcompanhamentoProducao>(`${base}/${ordemId}`, {
          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,
        });
        if (!vigente || contexto.current.chaveDetalhe !== chaveDetalhe) return;
        const empresa = perfil === "cliente" ? data.ordem.empresa_cliente_id : data.ordem.empresa_fornecedora_id;
        if (data.ordem.id !== ordemId || empresa !== empresaId || data.historico.some((e) => e.ordem_servico_id !== ordemId)) throw new Error("Acompanhamento divergente.");
        setDetalhe({ chave: chaveDetalhe, dados: data });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.chaveDetalhe === chaveDetalhe) setErroDetalhe(mensagemErroProducao(erro));
      } finally { if (vigente && contexto.current.chaveDetalhe === chaveDetalhe) setCarregandoDetalhe(false); }
    }
    void carregar();
    return () => { vigente = false; controlador.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, perfil, empresaId, selecionada?.id, chaveDetalhe]);

  useEffect(() => {
    const elemento = dialogo.current;
    if (!elemento) return;
    if (modalAtual && !elemento.open) elemento.showModal();
    if (!modalAtual && elemento.open) elemento.close();
  }, [modalAtual]);

  function revisar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!dados || !podeRegistrar || bloquear || trava.current) return;
    if (!etapaValida(rascunhoAtual.etapa) || rascunhoAtual.observacoes.length > 5000) {
      setAviso({ dono, texto: "Selecione uma etapa e limite as observações a 5000 caracteres." }); return;
    }
    setAviso(null); setSucesso(null);
    setRevisao({ chave: chaveDetalhe, dono, ordem: dados.ordem, etapa: rascunhoAtual.etapa,
      observacoes: rascunhoAtual.observacoes.trim() || null, ultimaId: dados.ultima_etapa_id });
  }

  async function confirmar() {
    if (!modalAtual || bloquear || trava.current) return;
    const confirmado = modalAtual; const controlador = new AbortController();
    envio.current = controlador; trava.current = true; setEnviando(true); setAviso(null);
    try {
      const { data } = await api.post<EtapaProducao>(`/portal-fornecedor/producao/${confirmado.ordem.id}/etapas`, {
        empresa_fornecedora_id: empresaId, etapa: confirmado.etapa, observacoes: confirmado.observacoes, ultima_etapa_id: confirmado.ultimaId,
      }, { signal: controlador.signal, timeout: 30_000 });
      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== confirmado.dono || contexto.current.chaveDetalhe !== confirmado.chave) return;
      if (data.ordem_servico_id !== confirmado.ordem.id || data.empresa_fornecedora_id !== empresaId || data.etapa !== confirmado.etapa) throw new Error("Registro de produção divergente.");
      setSucesso({ dono, texto: `${rotuloEtapa(data.etapa)} registrada na OS #${data.ordem_servico_id}. O cliente já pode consultar a atualização.` });
      setRascunho({ chave: "", etapa: "", observacoes: "" }); setRevisao(null); setAtualizacao((v) => v + 1);
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.dono === confirmado.dono && contexto.current.chaveDetalhe === confirmado.chave) {
        const status = typeof erro === "object" && erro !== null && "response" in erro ? (erro as { response?: { status?: number } }).response?.status : undefined;
        const incerta = !status || status >= 500;
        setAviso({ dono, texto: incerta ? "O registro não pôde ser confirmado. Atualize o histórico e confira se a etapa já aparece antes de tentar novamente." : mensagemErroProducao(erro) });
        if (incerta || status === 409) setRevalidar(chaveDetalhe);
        setRevisao(null);
      }
    } finally {
      if (envio.current === controlador) envio.current = null;
      trava.current = false; if (montada.current) setEnviando(false);
    }
  }

  return <main className="p27-page">
    <header className="p27-header"><div><p className="p27-eyebrow"><Factory size={16} /> PORTAL DO {perfil === "cliente" ? "CLIENTE" : "FORNECEDOR"}</p>
      <h1>Acompanhamento de Produção</h1><p>{perfil === "cliente" ? "Consulte a etapa atual e o histórico dos seus serviços." : "Registre as etapas e mantenha seus clientes informados sobre a produção."}</p></div>
      <button className="p27-button" disabled={enviando || carregando} onClick={() => { setAviso(null); setAtualizacao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>
    {sucesso?.dono === dono && <p className="p27-alert p27-success" role="status"><CheckCircle2 size={18} /> {sucesso.texto}</p>}
    {aviso?.dono === dono && <p className="p27-alert p27-error" role="alert">{aviso.texto}</p>}
    {erroLista && <p className="p27-alert p27-error" role="alert">{erroLista}</p>}
    <div className="p27-summary"><article><span>Ordens da sua empresa</span><strong>{pagina ? pagina.total : "—"}</strong><small>Inclui ordens abertas, em execução e finalizadas</small></article>
      <article><span>Etapa da OS selecionada</span><strong className="p27-summary-stage">{ordem ? rotuloEtapa(ordem.etapa_atual) : "—"}</strong><small>{ordem ? `OS #${ordem.id} · ${rotuloOrdem(ordem.status)}` : "Selecione uma ordem de serviço"}</small></article>
      <article><span>Atualizações desta OS</span><strong>{ordem?.total_atualizacoes ?? "—"}</strong><small>{ordem?.etapa_atual_em ? `Último registro: ${formatarInstanteCotacao(instanteUtc(ordem.etapa_atual_em))}` : "Ainda sem registro de etapa"}</small></article></div>
    <nav className="p27-tabs"><Link className="p27-button" to={`/${perfil}/ordens-servico`}><Wrench size={16} /> Ordens de Serviço e arquivos técnicos</Link></nav>
    <section className="p27-panel" aria-busy={carregando}><div className="p27-section-head"><div><h2>Produção dos serviços</h2><p>Selecione a ordem para acompanhar as etapas registradas pelo fornecedor.</p></div></div>
      {carregando ? <div className="p27-empty" role="status">Carregando ordens…</div>
        : !erroLista && pagina?.itens.length === 0 ? <div className="p27-empty"><Factory size={32} /><h3>Nenhuma ordem disponível</h3><p>{perfil === "cliente" ? "Gere uma ordem de serviço a partir de uma contratação ativa para acompanhar a produção." : "O cliente precisa gerar a ordem de serviço para que ela apareça neste acompanhamento."}</p></div>
        : pagina && <div className="p27-table-wrap"><table><thead><tr><th>Ordem / referência</th><th>{perfil === "cliente" ? "Fornecedor" : "Cliente"}</th><th>Etapa de produção</th><th>Situação da OS</th><th>Última atualização</th><th><span className="p27-sr-only">Ações</span></th></tr></thead><tbody>
          {pagina.itens.map((linha) => { const selecionada = linha.id === ordem?.id; const atual = selecionada && dados ? dados.ordem : linha;
            return <tr key={linha.id} className={selecionada ? "p27-selected" : ""}><td><strong>OS #{linha.id}</strong><small>Solicitação #{linha.solicitacao_id} · Contratação #{linha.contratacao_id}</small></td>
              <td>{perfil === "cliente" ? linha.fornecedor_razao_social : linha.cliente_razao_social}<small>{linha.processo_nome} · {linha.material_nome}</small></td>
              <td><span className={`p27-badge ${atual.etapa_atual === "pronto_para_envio" ? "p27-stage-ready" : "p27-stage-current"}`}>{rotuloEtapa(atual.etapa_atual)}</span></td>
              <td>{rotuloOrdem(linha.status)}</td><td>{atual.etapa_atual_em ? formatarInstanteCotacao(instanteUtc(atual.etapa_atual_em)) : "—"}</td>
              <td><button className="p27-button" disabled={enviando} aria-pressed={selecionada} onClick={() => setSelecionadoId(linha.id)}>{selecionada ? "Selecionada" : "Ver histórico"}</button></td></tr>;
          })}</tbody></table></div>}
      {pagina && pagina.total > 0 && <div className="p27-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + pagina.itens.length, pagina.total)} de {pagina.total}</span><div>
        <button className="p27-button" disabled={enviando || carregando || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => Math.max(0, v - 20)); }}>Anterior</button>
        <button className="p27-button" disabled={enviando || carregando || deslocamento + 20 >= pagina.total} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => v + 20); }}>Próxima</button></div></div>}
    </section>
    {selecionada && <section className="p27-panel p27-detail" aria-busy={carregandoDetalhe}><div className="p27-section-head"><h2><History size={20} /> Histórico da OS #{selecionada.id}</h2><button className="p27-button" disabled={enviando || carregandoDetalhe} onClick={() => { setAviso(null); setAtualizacaoDetalhe((v) => v + 1); }}>Atualizar histórico</button></div>
      {carregandoDetalhe ? <p role="status">Carregando histórico…</p> : erroDetalhe ? <p className="p27-alert p27-error" role="alert">{erroDetalhe}</p> : dados && <>
        <div className="p27-columns"><div><dl className="p27-fields"><div><dt>Cliente</dt><dd>{dados.ordem.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{dados.ordem.fornecedor_razao_social}</dd></div>
          <div><dt>Valor total</dt><dd>{formatarValorCotacao(dados.ordem.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{dados.ordem.prazo_dias} dias</dd></div>
          <div><dt>Quantidade da ordem</dt><dd>{dados.ordem.quantidade} unidades</dd></div><div><dt>Contratação</dt><dd>#{dados.ordem.contratacao_id} · {rotuloContratacao(dados.ordem.contratacao_status)}</dd></div>
          <div><dt>Processo da ordem</dt><dd>{dados.ordem.processo_nome}</dd></div><div><dt>Material da ordem</dt><dd>{dados.ordem.material_nome}</dd></div>
          <div className="p27-wide"><dt>Dimensões máximas X / Y / Z</dt><dd>{[dados.ordem.solicitacao.dimensao_x_maxima_mm,dados.ordem.solicitacao.dimensao_y_maxima_mm,dados.ordem.solicitacao.dimensao_z_maxima_mm].map((v) => formatarMedidaContrato(v)).join(" × ")} mm</dd></div></dl>
          <h3>Etapa atual</h3><p className="p27-current"><Factory size={18} /> {rotuloEtapa(dados.etapa_atual)}</p>
          {perfil === "fornecedor" && (podeRegistrar ? <form className="p27-form" onSubmit={revisar}><fieldset disabled={bloquear}>
            <label htmlFor="p27-etapa">Etapa de produção</label><select id="p27-etapa" required value={rascunhoAtual.etapa} onChange={(e) => setRascunho({ chave: chaveSelecao, etapa: e.target.value, observacoes: rascunhoAtual.observacoes })}><option value="">Selecione a etapa atual</option>{ETAPAS_PRODUCAO.map((e) => <option key={e.valor} value={e.valor}>{e.rotulo}</option>)}</select>
            <label htmlFor="p27-observacoes">Observações da atualização (opcional)</label><textarea id="p27-observacoes" maxLength={5000} rows={4} value={rascunhoAtual.observacoes} onChange={(e) => setRascunho({ chave: chaveSelecao, etapa: rascunhoAtual.etapa, observacoes: e.target.value })} placeholder="Informe o andamento, uma previsão ou um detalhe relevante para o cliente." />
            <p>Escolha a etapa que representa a situação atual. Cada registro será acrescentado ao histórico.</p><button type="submit" className="p27-button p27-primary" disabled={bloquear || !etapaValida(rascunhoAtual.etapa)}><ClipboardList size={16} /> Revisar atualização</button>
          </fieldset></form> : <p className="p27-readonly">{dados.ordem.contratacao_status !== "ativa" ? "A contratação está finalizada. O histórico continua disponível para consulta." : "Esta ordem está concluída ou cancelada. O histórico continua disponível para consulta."}</p>)}
          {perfil === "cliente" && <p className="p27-readonly">As etapas são registradas pelo fornecedor responsável. Use Atualizar histórico para conferir novos registros.</p>}
        </div><div className="p27-history"><h3>Atualizações registradas</h3>
          {dados.historico.length === 0 ? <div className="p27-history-empty"><Clock3 size={25} /><p>Nenhuma etapa de produção registrada para esta ordem.</p></div> : <ol className="p27-timeline">{dados.historico.slice().reverse().map((etapa) => <li key={etapa.id}><span className="p27-timeline-dot" /><article><h4>{rotuloEtapa(etapa.etapa)}</h4><time dateTime={dataHoraEtapa(etapa.criada_em)}>{formatarInstanteCotacao(instanteUtc(etapa.criada_em))}</time><p className="p27-observacoes">{etapa.observacoes || "Sem observações."}</p></article></li>)}</ol>}
        </div></div>
      </>}
    </section>}
    <dialog ref={dialogo} className="p27-dialog" aria-labelledby="p27-dialog-title" onCancel={(e) => { if (trava.current) e.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>
      {modalAtual && <><div className="p27-section-head"><h2 id="p27-dialog-title">Confirmar atualização de produção</h2><button className="p27-button" aria-label="Fechar revisão" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>
        <p>Confira a etapa e as observações que o cliente poderá consultar.</p><dl className="p27-fields"><div><dt>Ordem de serviço</dt><dd>#{modalAtual.ordem.id}</dd></div><div><dt>Solicitação</dt><dd>#{modalAtual.ordem.solicitacao_id}</dd></div><div className="p27-wide"><dt>Nova etapa</dt><dd>{rotuloEtapa(modalAtual.etapa)}</dd></div></dl>
        <h3>Observações da atualização</h3><p className="p27-observacoes">{modalAtual.observacoes || "Sem observações."}</p><p>Este registro será acrescentado ao histórico da ordem.</p>
        <div className="p27-dialog-actions"><button className="p27-button" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button><button className="p27-button p27-primary" disabled={enviando} onClick={() => void confirmar()}>{enviando ? "Registrando…" : "Confirmar atualização"}</button></div>
      </>}
    </dialog>
  </main>;
}
