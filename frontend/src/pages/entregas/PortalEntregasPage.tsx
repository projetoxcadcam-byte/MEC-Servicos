import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ClipboardList, Factory, History, PackageCheck, RefreshCw, Wrench, X } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from "../client/cotacoesCliente";
import { formatarMedidaContrato, rotuloContratacao, type PaginaContratacoes } from "../contratacoes/contratacoesPortal";
import { rotuloOrdem, type PerfilOrdens } from "../ordens/ordensPortal";
import { rotuloEtapa } from "../producao/producaoPortal";
import { mensagemErroEntrega, rotuloEntrega, type AcaoEntrega, type EntregaServico, type EntregasDetalhe, type OrdemEntrega } from "./entregasPortal";
import "./PortalEntregasPage.css";

type Revisao = { chave: string; dono: string; ordem: OrdemEntrega; acao: AcaoEntrega; entregaId: number | null; texto: string | null };

function dataHora(valor: string): string | undefined {
  const instante = instanteUtc(valor);
  return instante === null ? undefined : new Date(instante).toISOString();
}
function dataVisivel(valor: string | null): string {
  return valor ? formatarInstanteCotacao(instanteUtc(valor)) : "—";
}

export default function PortalEntregasPage({ perfil }: { perfil: PerfilOrdens }) {
  const { user } = useAuth();
  const empresaId = user?.role === perfil ? user.id : 0;
  const dono = `${perfil}:${empresaId}`;
  const base = `/portal-${perfil}/entregas`;
  const [deslocamento, setDeslocamento] = useState(0);
  const [atualizacao, setAtualizacao] = useState(0);
  const [lista, setLista] = useState<{ chave: string; pagina: PaginaContratacoes<OrdemEntrega> } | null>(null);
  const [selecionadoId, setSelecionadoId] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erroLista, setErroLista] = useState("");
  const [detalhe, setDetalhe] = useState<{ chave: string; dados: EntregasDetalhe } | null>(null);
  const [carregandoDetalhe, setCarregandoDetalhe] = useState(false);
  const [erroDetalhe, setErroDetalhe] = useState("");
  const [atualizacaoDetalhe, setAtualizacaoDetalhe] = useState(0);
  const [rascunho, setRascunho] = useState({ chave: "", observacoes: "", motivo: "" });
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
  const rascunhoAtual = rascunho.chave === chaveSelecao ? rascunho : { observacoes: "", motivo: "" };
  const pendente = dados?.historico.find((e) => e.id === dados.ordem.entrega_pendente_id && e.status === "entregue");
  const ativa = dados?.ordem.contratacao_status === "ativa" && dados.ordem.status === "em_execucao";
  const podeRegistrar = perfil === "fornecedor" && ativa && !pendente && dados?.ordem.etapa_atual === "pronto_para_envio";
  const podeDecidir = perfil === "cliente" && ativa && Boolean(pendente);
  const bloquear = enviando || carregando || carregandoDetalhe || !dados || revalidar === chaveDetalhe;
  const revisaoPermitida = revisao?.acao === "registrar" ? podeRegistrar : podeDecidir && revisao?.entregaId === pendente?.id;
  const modalAtual = revisao?.chave === chaveDetalhe && revisao.dono === dono && revisaoPermitida && (!bloquear || enviando) ? revisao : null;
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
      setErroLista(`Entre como ${perfil} para consultar as entregas.`); setCarregando(false);
      return () => { vigente = false; controlador.abort(); };
    }
    async function carregar() {
      try {
        const { data } = await api.get<PaginaContratacoes<OrdemEntrega>>(base, {
          params: { ...parametrosEmpresa, deslocamento, limite: 20 }, signal: controlador.signal, timeout: 20_000,
        });
        if (!vigente || contexto.current.chaveLista !== chaveLista) return;
        if (data.total > 0 && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }
        if (data.total === 0 && deslocamento > 0) { setDeslocamento(0); return; }
        const proprias = data.itens.filter((o) => (perfil === "cliente" ? o.empresa_cliente_id : o.empresa_fornecedora_id) === empresaId);
        setLista({ chave: chaveLista, pagina: { ...data, itens: proprias } });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.chaveLista === chaveLista) setErroLista(mensagemErroEntrega(erro));
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
        const { data } = await api.get<EntregasDetalhe>(`${base}/${ordemId}`, {
          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,
        });
        if (!vigente || contexto.current.chaveDetalhe !== chaveDetalhe) return;
        const empresa = perfil === "cliente" ? data.ordem.empresa_cliente_id : data.ordem.empresa_fornecedora_id;
        if (data.ordem.id !== ordemId || empresa !== empresaId || data.historico.some((e) => e.ordem_servico_id !== ordemId
          || e.empresa_cliente_id !== data.ordem.empresa_cliente_id || e.empresa_fornecedora_id !== data.ordem.empresa_fornecedora_id)) throw new Error("Histórico divergente.");
        setDetalhe({ chave: chaveDetalhe, dados: data });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.chaveDetalhe === chaveDetalhe) setErroDetalhe(mensagemErroEntrega(erro));
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

  function revisar(acao: AcaoEntrega) {
    if (!dados || bloquear || trava.current || !(acao === "registrar" ? podeRegistrar : podeDecidir)) return;
    const texto = acao === "registrar" ? rascunhoAtual.observacoes : acao === "recusar" ? rascunhoAtual.motivo : "";
    if (texto.length > 5000 || (acao === "recusar" && !texto.trim())) {
      setAviso({ dono, texto: acao === "recusar" && !texto.trim() ? "Informe o motivo da recusa para que o fornecedor possa corrigir a entrega." : "Limite o texto a 5000 caracteres." }); return;
    }
    setAviso(null); setSucesso(null);
    setRevisao({ chave: chaveDetalhe, dono, ordem: dados.ordem, acao,
      entregaId: acao === "registrar" ? null : pendente!.id, texto: texto.trim() || null });
  }

  async function confirmar() {
    if (!modalAtual || bloquear || trava.current) return;
    const confirmado = modalAtual; const controlador = new AbortController();
    envio.current = controlador; trava.current = true; setEnviando(true); setAviso(null);
    const url = confirmado.acao === "registrar" ? `/portal-fornecedor/entregas/${confirmado.ordem.id}/registrar`
      : `/portal-cliente/entregas/${confirmado.ordem.id}/${confirmado.entregaId}/${confirmado.acao}`;
    const corpo = confirmado.acao === "registrar" ? { empresa_fornecedora_id: empresaId, observacoes: confirmado.texto,
      ultima_entrega_id: confirmado.ordem.ultima_entrega_id, ultima_etapa_id: confirmado.ordem.ultima_etapa_id }
      : confirmado.acao === "recusar" ? { empresa_cliente_id: empresaId, motivo: confirmado.texto } : { empresa_cliente_id: empresaId };
    try {
      const { data } = await api.post<EntregaServico>(url, corpo, { signal: controlador.signal, timeout: 30_000 });
      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== confirmado.dono || contexto.current.chaveDetalhe !== confirmado.chave) return;
      const situacao = { registrar: "entregue", aceitar: "aceita", recusar: "recusada" }[confirmado.acao];
      if (data.ordem_servico_id !== confirmado.ordem.id || data.empresa_cliente_id !== confirmado.ordem.empresa_cliente_id
        || data.empresa_fornecedora_id !== confirmado.ordem.empresa_fornecedora_id || data.status !== situacao
        || (confirmado.entregaId !== null && data.id !== confirmado.entregaId)) throw new Error("Resultado de entrega divergente.");
      const texto = confirmado.acao === "registrar" ? `Entrega #${data.id} registrada na OS #${data.ordem_servico_id}. Aguardando aceite do cliente.`
        : confirmado.acao === "aceitar" ? `Entrega #${data.id} aceita. A OS #${data.ordem_servico_id} foi concluída e a contratação #${confirmado.ordem.contratacao_id} encerrada.`
        : `Entrega #${data.id} recusada. O fornecedor já pode consultar o motivo e registrar uma nova entrega após a correção.`;
      setSucesso({ dono, texto }); setRascunho({ chave: "", observacoes: "", motivo: "" }); setRevisao(null); setAtualizacao((v) => v + 1);
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.dono === confirmado.dono && contexto.current.chaveDetalhe === confirmado.chave) {
        const status = typeof erro === "object" && erro !== null && "response" in erro ? (erro as { response?: { status?: number } }).response?.status : undefined;
        const incerta = !status || status >= 500;
        setAviso({ dono, texto: incerta ? "A operação não pôde ser confirmada. Atualize o histórico e confira a entrega antes de tentar novamente." : mensagemErroEntrega(erro) });
        if (incerta || status === 409) setRevalidar(chaveDetalhe);
        setRevisao(null);
      }
    } finally {
      if (envio.current === controlador) envio.current = null;
      trava.current = false; if (montada.current) setEnviando(false);
    }
  }

  function enviarFormulario(evento: FormEvent<HTMLFormElement>) { evento.preventDefault(); revisar("registrar"); }

  return <main className="p28-page">
    <header className="p28-header"><div><p className="p28-eyebrow"><PackageCheck size={16} /> PORTAL DO {perfil === "cliente" ? "CLIENTE" : "FORNECEDOR"}</p>
      <h1>{perfil === "cliente" ? "Entregas e Aceite" : "Entregas"}</h1><p>{perfil === "cliente" ? "Confira as entregas, aceite o serviço ou informe o motivo da recusa." : "Registre as entregas e acompanhe a decisão dos seus clientes."}</p></div>
      <button className="p28-button" disabled={enviando || carregando} onClick={() => { setAviso(null); setAtualizacao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>
    {sucesso?.dono === dono && <p className="p28-alert p28-success" role="status"><CheckCircle2 size={18} /> {sucesso.texto}</p>}
    {aviso?.dono === dono && <p className="p28-alert p28-error" role="alert">{aviso.texto}</p>}
    {erroLista && <p className="p28-alert p28-error" role="alert">{erroLista}</p>}
    <div className="p28-summary"><article><span>Ordens da sua empresa</span><strong>{pagina ? pagina.total : "—"}</strong><small>Inclui ordens abertas, em execução e finalizadas</small></article>
      <article><span>Entrega da OS selecionada</span><strong className="p28-summary-stage">{ordem ? rotuloEntrega(ordem.ultima_entrega_status) : "—"}</strong><small>{ordem ? `OS #${ordem.id} · ${rotuloOrdem(ordem.status)}` : "Selecione uma ordem de serviço"}</small></article>
      <article><span>Entregas desta OS</span><strong>{ordem?.total_entregas ?? "—"}</strong><small>{ordem?.ultima_entrega_em ? `Última entrega: ${dataVisivel(ordem.ultima_entrega_em)}` : "Ainda sem registro de entrega"}</small></article></div>
    <nav className="p28-tabs"><Link className="p28-button" to={`/${perfil}/producao`}><Factory size={16} /> {perfil === "cliente" ? "Acompanhamento de Produção" : "Produção"}</Link>
      <Link className="p28-button" to={`/${perfil}/ordens-servico`}><Wrench size={16} /> Ordens de Serviço e arquivos técnicos</Link></nav>
    <section className="p28-panel" aria-busy={carregando}><div className="p28-section-head"><div><h2>Entregas dos serviços</h2><p>Selecione a ordem para consultar as entregas e as decisões do cliente.</p></div></div>
      {carregando ? <div className="p28-empty" role="status">Carregando ordens…</div>
        : !erroLista && pagina?.itens.length === 0 ? <div className="p28-empty"><PackageCheck size={32} /><h3>Nenhuma ordem disponível</h3><p>{perfil === "cliente" ? "Gere uma ordem de serviço a partir de uma contratação ativa." : "O cliente precisa gerar a ordem de serviço para que ela apareça aqui."}</p></div>
        : pagina && <div className="p28-table-wrap"><table><thead><tr><th>Ordem / referência</th><th>{perfil === "cliente" ? "Fornecedor" : "Cliente"}</th><th>Última entrega</th><th>Situação da OS</th><th>Data da entrega</th><th><span className="p28-sr-only">Ações</span></th></tr></thead><tbody>
          {pagina.itens.map((linha) => { const selecionada = linha.id === ordem?.id; const atual = selecionada && dados ? dados.ordem : linha;
            return <tr key={linha.id} className={selecionada ? "p28-selected" : ""}><td><strong>OS #{linha.id}</strong><small>Solicitação #{linha.solicitacao_id} · Contratação #{linha.contratacao_id}</small></td>
              <td>{perfil === "cliente" ? linha.fornecedor_razao_social : linha.cliente_razao_social}<small>{linha.processo_nome} · {linha.material_nome}</small></td>
              <td><span className={`p28-badge p28-entrega-${atual.ultima_entrega_status ?? "vazia"}`}>{rotuloEntrega(atual.ultima_entrega_status)}</span></td>
              <td>{rotuloOrdem(atual.status)}</td><td>{dataVisivel(atual.ultima_entrega_em)}</td>
              <td><button className="p28-button" disabled={enviando} aria-pressed={selecionada} onClick={() => setSelecionadoId(linha.id)}>{selecionada ? "Selecionada" : "Ver entregas"}</button></td></tr>;
          })}</tbody></table></div>}
      {pagina && pagina.total > 0 && <div className="p28-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + pagina.itens.length, pagina.total)} de {pagina.total}</span><div>
        <button className="p28-button" disabled={enviando || carregando || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => Math.max(0, v - 20)); }}>Anterior</button>
        <button className="p28-button" disabled={enviando || carregando || deslocamento + 20 >= pagina.total} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => v + 20); }}>Próxima</button></div></div>}
    </section>
    {selecionada && <section className="p28-panel p28-detail" aria-busy={carregandoDetalhe}><div className="p28-section-head"><h2><History size={20} /> Entregas da OS #{selecionada.id}</h2><button className="p28-button" disabled={enviando || carregandoDetalhe} onClick={() => { setAviso(null); setAtualizacaoDetalhe((v) => v + 1); }}>Atualizar histórico</button></div>
      {carregandoDetalhe ? <p role="status">Carregando entregas…</p> : erroDetalhe ? <p className="p28-alert p28-error" role="alert">{erroDetalhe}</p> : dados && <div className="p28-columns"><div><dl className="p28-fields">
        <div><dt>Cliente</dt><dd>{dados.ordem.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{dados.ordem.fornecedor_razao_social}</dd></div>
        <div><dt>Valor total</dt><dd>{formatarValorCotacao(dados.ordem.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{dados.ordem.prazo_dias} dias</dd></div>
        <div><dt>Quantidade da ordem</dt><dd>{dados.ordem.quantidade} unidades</dd></div><div><dt>Contratação</dt><dd>#{dados.ordem.contratacao_id} · {rotuloContratacao(dados.ordem.contratacao_status)}</dd></div>
        <div><dt>Processo da ordem</dt><dd>{dados.ordem.processo_nome}</dd></div><div><dt>Material da ordem</dt><dd>{dados.ordem.material_nome}</dd></div>
        <div className="p28-wide"><dt>Dimensões máximas X / Y / Z</dt><dd>{[dados.ordem.solicitacao.dimensao_x_maxima_mm,dados.ordem.solicitacao.dimensao_y_maxima_mm,dados.ordem.solicitacao.dimensao_z_maxima_mm].map((v) => formatarMedidaContrato(v)).join(" × ")} mm</dd></div>
        <div><dt>Situação da OS</dt><dd>{rotuloOrdem(dados.ordem.status)}</dd></div><div><dt>Etapa de produção</dt><dd>{rotuloEtapa(dados.ordem.etapa_atual)}</dd></div></dl>
        {perfil === "fornecedor" && (podeRegistrar ? <form className="p28-form" onSubmit={enviarFormulario}><fieldset disabled={bloquear}>
          <h3>Registrar entrega</h3><label htmlFor="p28-observacoes">Observações da entrega (opcional)</label><textarea id="p28-observacoes" maxLength={5000} rows={4} value={rascunhoAtual.observacoes}
            onChange={(e) => setRascunho({ chave: chaveSelecao, observacoes: e.target.value, motivo: rascunhoAtual.motivo })} placeholder="Descreva a entrega e as informações necessárias para o recebimento." />
          <p>O cliente poderá aceitar a entrega ou recusá-la com um motivo.</p><button type="submit" className="p28-button p28-primary" disabled={bloquear}><ClipboardList size={16} /> Revisar entrega</button>
        </fieldset></form> : <p className="p28-readonly">{dados.ordem.contratacao_status !== "ativa" ? "A contratação está finalizada. As entregas continuam disponíveis para consulta."
          : ["concluida", "cancelada"].includes(dados.ordem.status) ? "Esta OS está concluída ou cancelada. As entregas continuam disponíveis para consulta."
          : pendente ? `A entrega #${pendente.id} aguarda a decisão do cliente. Consulte o histórico para acompanhar o aceite ou a recusa.`
          : dados.ordem.status !== "em_execucao" ? "Inicie esta OS em Ordens de Serviço antes de registrar a entrega."
          : "Registre Pronto para envio como etapa atual na página Produção antes de entregar."}</p>)}
        {perfil === "cliente" && (podeDecidir ? <div className="p28-form"><fieldset disabled={bloquear}><h3>Decidir entrega #{pendente!.id}</h3>
          <p>Confira os dados e as observações da entrega no histórico antes de decidir.</p><label htmlFor="p28-motivo">Motivo da recusa (obrigatório para recusar)</label><textarea id="p28-motivo" maxLength={5000} rows={4} value={rascunhoAtual.motivo}
            onChange={(e) => setRascunho({ chave: chaveSelecao, motivo: e.target.value, observacoes: rascunhoAtual.observacoes })} placeholder="Explique o que precisa ser corrigido, caso recuse a entrega." />
          <div className="p28-decision-actions"><button className="p28-button p28-primary" disabled={bloquear} onClick={() => revisar("aceitar")}>Aceitar entrega</button>
            <button className="p28-button p28-danger" disabled={bloquear} onClick={() => revisar("recusar")}>Recusar entrega</button></div></fieldset></div>
          : <p className="p28-readonly">{pendente ? "A ordem ou a contratação está finalizada. A entrega permanece disponível para consulta." : "Nenhuma entrega aguardando sua decisão. Use Atualizar histórico para conferir novos registros."}</p>)}
      </div><div className="p28-history"><h3>Histórico de entregas</h3>{dados.historico.length === 0 ? <div className="p28-history-empty"><PackageCheck size={25} /><p>Nenhuma entrega registrada para esta ordem.</p></div>
        : <ol className="p28-timeline">{dados.historico.slice().reverse().map((entrega) => <li key={entrega.id}><span className="p28-timeline-dot" /><article><h4>Entrega #{entrega.id} <span className={`p28-badge p28-entrega-${entrega.status}`}>{rotuloEntrega(entrega.status)}</span></h4>
          <p className="p28-history-date">Entregue em <time dateTime={dataHora(entrega.entregue_em)}>{dataVisivel(entrega.entregue_em)}</time></p><p className="p28-observacoes">{entrega.observacoes || "Sem observações da entrega."}</p>
          {entrega.aceita_em && <p className="p28-history-date">Aceita em <time dateTime={dataHora(entrega.aceita_em)}>{dataVisivel(entrega.aceita_em)}</time></p>}
          {entrega.recusada_em && <><p className="p28-history-date">Recusada em <time dateTime={dataHora(entrega.recusada_em)}>{dataVisivel(entrega.recusada_em)}</time></p><h5>Motivo da recusa</h5><p className="p28-observacoes p28-refusal-reason">{entrega.motivo_recusa || "Motivo não informado no registro anterior."}</p></>}
        </article></li>)}</ol>}</div></div>}
    </section>}
    <dialog ref={dialogo} className="p28-dialog" aria-labelledby="p28-dialog-title" onCancel={(e) => { if (trava.current) e.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>
      {modalAtual && <><div className="p28-section-head"><h2 id="p28-dialog-title">{modalAtual.acao === "registrar" ? "Confirmar registro de entrega" : modalAtual.acao === "aceitar" ? "Confirmar aceite da entrega" : "Confirmar recusa da entrega"}</h2>
        <button className="p28-button" aria-label="Fechar revisão" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>
        <dl className="p28-fields"><div><dt>Ordem de serviço</dt><dd>#{modalAtual.ordem.id}</dd></div><div><dt>Contratação</dt><dd>#{modalAtual.ordem.contratacao_id}</dd></div>
          <div><dt>Cliente</dt><dd>{modalAtual.ordem.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{modalAtual.ordem.fornecedor_razao_social}</dd></div>
          {modalAtual.entregaId && <div><dt>Entrega</dt><dd>#{modalAtual.entregaId}</dd></div>}</dl>
        {modalAtual.acao === "aceitar" ? <p className="p28-review-effect">Ao confirmar o aceite, esta entrega será aceita, a OS será concluída e a contratação encerrada.</p>
          : <><h3>{modalAtual.acao === "registrar" ? "Observações da entrega" : "Motivo da recusa"}</h3><p className="p28-observacoes">{modalAtual.texto || "Sem observações da entrega."}</p>
            <p className="p28-review-effect">{modalAtual.acao === "registrar" ? "A entrega ficará aguardando o aceite do cliente. A OS continuará em execução e a contratação ativa."
              : "A entrega será recusada com este motivo. A OS continuará em execução e a contratação ativa, permitindo outra entrega após a correção."}</p></>}
        <div className="p28-dialog-actions"><button className="p28-button" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button>
          <button className={`p28-button ${modalAtual.acao === "recusar" ? "p28-danger" : "p28-primary"}`} disabled={enviando} onClick={() => void confirmar()}>{enviando ? "Confirmando…" : modalAtual.acao === "registrar" ? "Confirmar entrega" : modalAtual.acao === "aceitar" ? "Confirmar aceite" : "Confirmar recusa"}</button></div>
      </>}
    </dialog>
  </main>;
}
