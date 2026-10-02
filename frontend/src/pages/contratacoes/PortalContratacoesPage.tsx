import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ClipboardList, Download, FileText, Handshake, RefreshCw, X } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from "../client/cotacoesCliente";
import { formatarTamanhoArquivo, type ArquivoFornecedor } from "../supplier/cotacoesFornecedor";
import {
  formatarMedidaContrato, mensagemErroContratacao, rotuloContratacao,
  type ContratacaoPortal, type ContratacaoResposta, type CotacaoParaContratar, type PaginaContratacoes, type PerfilContratacoes,
} from "./contratacoesPortal";
import "./PortalContratacoesPage.css";

type Visao = "contratacoes" | "aceitas";
type Grupo = { chave: string; contratos: PaginaContratacoes<ContratacaoPortal>; aceitas: PaginaContratacoes<CotacaoParaContratar> };
type Revisao = { chave: string; empresaId: number; cotacao: CotacaoParaContratar; observacoes: string | null };
const LIMITE = 20;
const PAGINA_VAZIA = { itens: [], total: 0, deslocamento: 0, limite: LIMITE };

export default function PortalContratacoesPage({ perfil }: { perfil: PerfilContratacoes }) {
  const { user } = useAuth();
  const empresaId = user?.role === perfil ? user.id : 0;
  const base = `/portal-${perfil}`;
  const [visao, setVisao] = useState<Visao>("contratacoes");
  const visaoAtual = perfil === "cliente" ? visao : "contratacoes";
  const [deslocamento, setDeslocamento] = useState(0);
  const [atualizacao, setAtualizacao] = useState(0);
  const [grupo, setGrupo] = useState<Grupo | null>(null);
  const [selecionadoId, setSelecionadoId] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erroLista, setErroLista] = useState("");
  const [rascunho, setRascunho] = useState({ chave: "", texto: "" });
  const [revisao, setRevisao] = useState<Revisao | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erroEnvio, setErroEnvio] = useState("");
  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);
  const [arquivos, setArquivos] = useState<{ chave: string; itens: ArquivoFornecedor[] } | null>(null);
  const [erroArquivos, setErroArquivos] = useState("");
  const [carregandoArquivos, setCarregandoArquivos] = useState(false);
  const [atualizacaoArquivos, setAtualizacaoArquivos] = useState(0);
  const [baixando, setBaixando] = useState<number | null>(null);
  const paginaChave = `${perfil}:${empresaId}:${visaoAtual}:${deslocamento}:${atualizacao}`;
  const grupoAtual = grupo?.chave === paginaChave ? grupo : null;
  const pagina = visaoAtual === "aceitas" ? grupoAtual?.aceitas : grupoAtual?.contratos;
  const contratos = grupoAtual?.contratos.itens ?? [];
  const aceitas = grupoAtual?.aceitas.itens ?? [];
  const contrato = visaoAtual === "contratacoes" ? contratos.find((item) => item.id === selecionadoId) ?? contratos[0] : undefined;
  const cotacao = visaoAtual === "aceitas" ? aceitas.find((item) => item.id === selecionadoId) ?? aceitas[0] : undefined;
  const solicitacao = contrato?.solicitacao ?? cotacao?.solicitacao;
  const selecaoChave = `${perfil}:${empresaId}:${visaoAtual}:${contrato?.id ?? cotacao?.id ?? 0}`;
  const textoObservacoes = rascunho.chave === selecaoChave ? rascunho.texto : "";
  const modalAtual = revisao?.chave === selecaoChave && revisao.empresaId === empresaId && perfil === "cliente" && grupoAtual ? revisao : null;
  const arquivosAtuais = arquivos?.chave === selecaoChave ? arquivos.itens : [];
  const bloquear = carregando || enviando || !grupoAtual;
  const parametrosEmpresa = perfil === "cliente" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };
  const contexto = useRef({ paginaChave, selecaoChave, dono: `${perfil}:${empresaId}` });
  contexto.current = { paginaChave, selecaoChave, dono: `${perfil}:${empresaId}` };
  const montada = useRef(true);
  const dialogo = useRef<HTMLDialogElement | null>(null);
  const trava = useRef(false);
  const envio = useRef<AbortController | null>(null);
  const download = useRef<AbortController | null>(null);

  useEffect(() => {
    montada.current = true;
    return () => { montada.current = false; envio.current?.abort(); download.current?.abort(); };
  }, []);

  useEffect(() => {
    setVisao("contratacoes"); setDeslocamento(0); setSelecionadoId(0);
    setRevisao(null); setErroEnvio(""); envio.current?.abort();
  }, [empresaId, perfil]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setCarregando(true); setErroLista(""); setRevisao(null);
    if (!empresaId) {
      setErroLista(`Entre com um acesso de ${perfil} para consultar suas contratações.`);
      setCarregando(false);
      return () => { vigente = false; controlador.abort(); };
    }
    async function carregar() {
      try {
        const config = { params: { ...parametrosEmpresa, deslocamento: visaoAtual === "contratacoes" ? deslocamento : 0, limite: LIMITE }, signal: controlador.signal, timeout: 20_000 };
        const [resposta, candidatas] = await Promise.all([
          api.get<PaginaContratacoes<ContratacaoPortal>>(`${base}/contratacoes`, config),
          perfil === "cliente" ? api.get<PaginaContratacoes<CotacaoParaContratar>>("/portal-cliente/cotacoes-aceitas", {
            ...config, params: { empresa_cliente_id: empresaId, deslocamento: visaoAtual === "aceitas" ? deslocamento : 0, limite: LIMITE },
          }) : Promise.resolve({ data: PAGINA_VAZIA as PaginaContratacoes<CotacaoParaContratar> }),
        ]);
        if (!vigente || contexto.current.paginaChave !== paginaChave) return;
        const quantidade = visaoAtual === "aceitas" ? candidatas.data.total : resposta.data.total;
        if (quantidade > 0 && deslocamento >= quantidade) {
          setDeslocamento(Math.floor((quantidade - 1) / LIMITE) * LIMITE); return;
        }
        if (quantidade === 0 && deslocamento > 0) { setDeslocamento(0); return; }
        const proprios = resposta.data.itens.filter((item) => (perfil === "cliente" ? item.empresa_cliente_id : item.empresa_fornecedora_id) === empresaId);
        const aptas = candidatas.data.itens.filter((item) => item.solicitacao.empresa_cliente_id === empresaId && item.status === "aceita" && item.decidida_por_empresa_id === empresaId);
        setGrupo({ chave: paginaChave, contratos: { ...resposta.data, itens: proprios }, aceitas: { ...candidatas.data, itens: aptas } });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.paginaChave === paginaChave) setErroLista(mensagemErroContratacao(erro));
      } finally {
        if (vigente && contexto.current.paginaChave === paginaChave) setCarregando(false);
      }
    }
    void carregar();
    return () => { vigente = false; controlador.abort(); };
    // Os parâmetros da empresa são derivados do perfil e da empresaId.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, empresaId, perfil, visaoAtual, deslocamento, paginaChave]);

  useEffect(() => {
    setRevisao(null); setErroEnvio(""); setErroArquivos(""); setBaixando(null);
    download.current?.abort();
  }, [selecaoChave]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setErroArquivos(""); setCarregandoArquivos(Boolean(contrato));
    if (!contrato) return () => { vigente = false; controlador.abort(); };
    async function carregarArquivos() {
      try {
        const { data } = await api.get<ArquivoFornecedor[]>(`${base}/contratacoes/${contrato!.id}/arquivos`, {
          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,
        });
        if (vigente && contexto.current.selecaoChave === selecaoChave) setArquivos({ chave: selecaoChave, itens: data.filter((item) => item.ativo && item.solicitacao_id === contrato!.solicitacao_id) });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.selecaoChave === selecaoChave) setErroArquivos(mensagemErroContratacao(erro));
      } finally {
        if (vigente && contexto.current.selecaoChave === selecaoChave) setCarregandoArquivos(false);
      }
    }
    void carregarArquivos();
    return () => { vigente = false; controlador.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, perfil, empresaId, contrato?.id, selecaoChave, atualizacaoArquivos]);

  useEffect(() => {
    const elemento = dialogo.current;
    if (!elemento) return;
    if (modalAtual && !elemento.open) elemento.showModal();
    if (!modalAtual && elemento.open) elemento.close();
  }, [modalAtual]);

  function mudarVisao(nova: Visao) {
    if (trava.current) return;
    setVisao(nova); setDeslocamento(0); setSelecionadoId(0); setRevisao(null); setErroEnvio("");
  }

  function revisar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!cotacao || perfil !== "cliente" || bloquear || trava.current) return;
    if (textoObservacoes.length > 5000) { setErroEnvio("As observações podem ter até 5000 caracteres."); return; }
    setErroEnvio("");
    setRevisao({ chave: selecaoChave, empresaId, cotacao, observacoes: textoObservacoes.trim() || null });
  }

  async function confirmar() {
    if (!modalAtual || bloquear || trava.current) return;
    const confirmado = modalAtual;
    const dono = `${perfil}:${empresaId}`;
    const controlador = new AbortController();
    envio.current = controlador; trava.current = true; setEnviando(true); setErroEnvio("");
    try {
      const { data } = await api.post<ContratacaoResposta>(`/portal-cliente/solicitacoes/${confirmado.cotacao.solicitacao_id}/contratacao`, {
        empresa_cliente_id: confirmado.empresaId, cotacao_id: confirmado.cotacao.id, observacoes: confirmado.observacoes,
      }, { signal: controlador.signal, timeout: 30_000 });
      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== dono || contexto.current.selecaoChave !== confirmado.chave) return;
      if (data.solicitacao_id !== confirmado.cotacao.solicitacao_id || data.cotacao_id !== confirmado.cotacao.id || data.empresa_cliente_id !== confirmado.empresaId) throw new Error("Resposta da contratação divergente.");
      setSucesso({ dono, texto: `Contratação #${data.id} criada para a solicitação #${data.solicitacao_id}. O fornecedor já pode consultá-la.` });
      setRascunho({ chave: "", texto: "" }); setRevisao(null);
      setVisao("contratacoes"); setDeslocamento(0); setSelecionadoId(data.id); setAtualizacao((valor) => valor + 1);
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.dono === dono && contexto.current.selecaoChave === confirmado.chave) {
        const respondeu = typeof erro === "object" && erro !== null && "response" in erro && Boolean((erro as { response?: unknown }).response);
        setErroEnvio(respondeu ? mensagemErroContratacao(erro) : "A criação não pôde ser confirmada. Atualize a aba Contratações antes de tentar contratar novamente.");
        setRevisao(null);
      }
    } finally {
      if (envio.current === controlador) envio.current = null;
      trava.current = false;
      if (montada.current) setEnviando(false);
    }
  }

  async function baixar(arquivo: ArquivoFornecedor) {
    if (!contrato || baixando !== null || download.current) return;
    const controlador = new AbortController();
    const chave = selecaoChave;
    download.current = controlador; setBaixando(arquivo.id); setErroArquivos("");
    try {
      const { data } = await api.get<Blob>(`${base}/contratacoes/${contrato.id}/arquivos/${arquivo.id}/download`, {
        params: parametrosEmpresa, signal: controlador.signal, responseType: "blob", timeout: 60_000,
      });
      if (!montada.current || controlador.signal.aborted || contexto.current.selecaoChave !== chave) return;
      const url = URL.createObjectURL(data);
      const link = document.createElement("a");
      try {
        link.href = url; link.download = arquivo.nome_original.replace(/[\\/]/g, "_");
        document.body.appendChild(link); link.click();
      } finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.selecaoChave === chave) setErroArquivos(mensagemErroContratacao(erro));
    } finally {
      if (download.current === controlador) download.current = null;
      if (montada.current && contexto.current.selecaoChave === chave) setBaixando(null);
    }
  }

  const total = pagina?.total ?? 0;
  const linhas = visaoAtual === "aceitas" ? aceitas : contratos;
  return <main className="k25-page">
    <header className="k25-header">
      <div><p className="k25-eyebrow"><Handshake size={16} /> PORTAL DO {perfil === "cliente" ? "CLIENTE" : "FORNECEDOR"}</p>
        <h1>{perfil === "cliente" ? "Minhas Contratações" : "Contratações"}</h1>
        <p>{perfil === "cliente" ? "Contrate uma proposta aceita e acompanhe os serviços da sua empresa." : "Consulte os serviços contratados pelos seus clientes."}</p></div>
      <button className="k25-button" disabled={enviando || carregando} onClick={() => setAtualizacao((valor) => valor + 1)}><RefreshCw size={16} /> Atualizar</button>
    </header>
    {sucesso?.dono === `${perfil}:${empresaId}` && <p className="k25-alert k25-success" role="status"><CheckCircle2 size={18} /> {sucesso.texto}</p>}
    {erroLista && <p className="k25-alert k25-error" role="alert">{erroLista}</p>}
    <div className="k25-summary">
      <article><span>Contratações da sua empresa</span><strong>{grupoAtual ? grupoAtual.contratos.total : "—"}</strong><small>Inclui ativas, canceladas e encerradas</small></article>
      {perfil === "cliente" && <article><span>Cotações prontas para contratar</span><strong>{grupoAtual ? grupoAtual.aceitas.total : "—"}</strong><small>Aceitas e ainda sem contratação</small></article>}
    </div>
    <nav className="k25-tabs" aria-label="Consultas de contratação">
      <button className={`k25-button ${visaoAtual === "contratacoes" ? "k25-tab-active" : ""}`} aria-pressed={visaoAtual === "contratacoes"} disabled={enviando} onClick={() => mudarVisao("contratacoes")}><Handshake size={16} /> Contratações</button>
      {perfil === "cliente" && <button className={`k25-button ${visaoAtual === "aceitas" ? "k25-tab-active" : ""}`} aria-pressed={visaoAtual === "aceitas"} disabled={enviando} onClick={() => mudarVisao("aceitas")}><CheckCircle2 size={16} /> Cotações para contratar</button>}
      <Link className="k25-button" to={`/${perfil}/cotacoes`}><FileText size={16} /> {perfil === "cliente" ? "Cotações Recebidas" : "Minhas Cotações"}</Link>
    </nav>
    <section className="k25-panel" aria-busy={carregando}>
      <div className="k25-section-head"><div><h2>{visaoAtual === "aceitas" ? "Propostas aceitas pelo cliente" : "Serviços contratados"}</h2><p>{visaoAtual === "aceitas" ? "Confira a proposta e revise os dados antes de criar a contratação." : "Selecione uma contratação para consultar os detalhes e os arquivos técnicos."}</p></div></div>
      {carregando ? <div className="k25-empty" role="status">Carregando {visaoAtual === "aceitas" ? "cotações" : "contratações"}…</div>
        : !erroLista && linhas.length === 0 ? <div className="k25-empty"><Handshake size={32} /><h3>{visaoAtual === "aceitas" ? "Nenhuma cotação pronta para contratar" : "Nenhuma contratação cadastrada"}</h3><p>{visaoAtual === "aceitas" ? "Aceite uma proposta em Cotações Recebidas. Solicitações já contratadas não aparecem nesta lista." : perfil === "cliente" ? "Abra Cotações para contratar para criar uma contratação a partir de uma proposta aceita." : "As contratações aparecerão aqui quando o cliente contratar uma proposta da sua empresa."}</p></div>
        : grupoAtual && <div className="k25-table-wrap"><table><thead><tr><th>Solicitação / referência</th><th>{perfil === "cliente" ? "Fornecedor" : "Cliente"}</th><th>Valor total</th><th>Prazo</th><th>Situação</th><th><span className="k25-sr-only">Ações</span></th></tr></thead><tbody>
          {linhas.map((item) => { const criado = "cotacao_id" in item; const ativo = item.id === (contrato?.id ?? cotacao?.id);
            return <tr key={item.id} className={ativo ? "k25-selected" : ""}><td><strong>Solicitação #{item.solicitacao_id}</strong><small>{criado ? `Contratação #${item.id} · Cotação #${item.cotacao_id}` : `Cotação #${item.id}`}</small></td>
              <td>{perfil === "cliente" ? item.fornecedor_razao_social : criado ? item.cliente_razao_social : ""}<small>{item.solicitacao.processo_nome} · {item.solicitacao.material_nome}</small></td>
              <td className="k25-nowrap"><strong>{formatarValorCotacao(item.valor_total)}</strong></td><td className="k25-nowrap">{item.prazo_dias} dias</td>
              <td><span className={`k25-badge k25-status-${criado && ["ativa", "cancelada", "encerrada"].includes(item.status) ? item.status : "aceita"}`}>{criado ? rotuloContratacao(item.status) : "Pronta para contratar"}</span></td>
              <td><button className="k25-button" disabled={enviando} onClick={() => setSelecionadoId(item.id)} aria-pressed={ativo}>{ativo ? "Selecionada" : "Ver detalhes"}</button></td></tr>;
          })}
        </tbody></table></div>}
      {grupoAtual && total > 0 && <div className="k25-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + linhas.length, total)} de {total}</span><div>
        <button className="k25-button" disabled={bloquear || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((valor) => Math.max(0, valor - LIMITE)); }}>Anterior</button>
        <button className="k25-button" disabled={bloquear || deslocamento + LIMITE >= total} onClick={() => { setSelecionadoId(0); setDeslocamento((valor) => valor + LIMITE); }}>Próxima</button></div></div>}
    </section>
    {solicitacao && <div className="k25-columns">
      <section className="k25-panel k25-detail"><div className="k25-section-head"><h2>Solicitação #{solicitacao.id}</h2><ClipboardList size={21} /></div>
        <dl className="k25-fields"><div><dt>Cliente</dt><dd>{solicitacao.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{contrato?.fornecedor_razao_social ?? cotacao?.fornecedor_razao_social}</dd></div>
          <div><dt>Processo</dt><dd>{solicitacao.processo_nome}</dd></div><div><dt>Material</dt><dd>{solicitacao.material_nome}</dd></div>
          <div><dt>Quantidade</dt><dd>{solicitacao.quantidade} unidades</dd></div><div><dt>Tolerância requerida</dt><dd>{formatarMedidaContrato(solicitacao.tolerancia_requerida_mm, 4)} mm</dd></div>
          <div className="k25-wide"><dt>Dimensões máximas X / Y / Z</dt><dd>{[solicitacao.dimensao_x_maxima_mm, solicitacao.dimensao_y_maxima_mm, solicitacao.dimensao_z_maxima_mm].map((valor) => formatarMedidaContrato(valor)).join(" × ")} mm</dd></div></dl>
        <h3>Observações da solicitação</h3><p className="k25-observacoes">{solicitacao.observacoes || "Sem observações."}</p>
        {perfil === "cliente" && <Link className="k25-button" to={`/cliente/cotacoes?solicitacao=${solicitacao.id}`}>Consultar cotações desta solicitação</Link>}
        {contrato && <><div className="k25-section-head k25-files-head"><h3>Arquivos técnicos</h3><button className="k25-button" disabled={carregandoArquivos || baixando !== null} onClick={() => setAtualizacaoArquivos((valor) => valor + 1)}>Atualizar arquivos</button></div>
          {erroArquivos && <p className="k25-alert k25-error" role="alert">{erroArquivos}</p>}
          {carregandoArquivos ? <p role="status">Carregando arquivos…</p> : !erroArquivos && arquivosAtuais.length === 0 ? <p>Nenhum arquivo ativo vinculado a esta solicitação.</p> : <ul className="k25-files">{arquivosAtuais.map((arquivo) => <li key={arquivo.id}><FileText size={19} /><span><strong>{arquivo.nome_original}</strong><small>{arquivo.extensao.toUpperCase()} · {formatarTamanhoArquivo(arquivo.tamanho_bytes)}</small></span><button className="k25-button" disabled={baixando !== null} onClick={() => void baixar(arquivo)}><Download size={15} /> {baixando === arquivo.id ? "Baixando…" : "Baixar"}</button></li>)}</ul>}
        </>}
      </section>
      <section className="k25-panel k25-detail"><div className="k25-section-head"><h2>{contrato ? `Contratação #${contrato.id}` : `Contratar cotação #${cotacao!.id}`}</h2><Handshake size={21} /></div>
        <dl className="k25-fields"><div><dt>Valor total</dt><dd className="k25-value">{formatarValorCotacao((contrato ?? cotacao)!.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{(contrato ?? cotacao)!.prazo_dias} dias</dd></div>
          {contrato && <><div><dt>Situação</dt><dd>{rotuloContratacao(contrato.status)}</dd></div><div><dt>Criada em</dt><dd>{formatarInstanteCotacao(instanteUtc(contrato.criada_em))}</dd></div>
            {contrato.cancelada_em && <div><dt>Cancelada em</dt><dd>{formatarInstanteCotacao(instanteUtc(contrato.cancelada_em))}</dd></div>}
            {contrato.encerrada_em && <div><dt>Encerrada em</dt><dd>{formatarInstanteCotacao(instanteUtc(contrato.encerrada_em))}</dd></div>}</>}
          {cotacao && <div className="k25-wide"><dt>Proposta aceita em</dt><dd>{formatarInstanteCotacao(instanteUtc(cotacao.encerrada_em))}</dd></div>}
        </dl>
        <h3>{contrato ? "Observações da contratação" : "Observações da proposta aceita"}</h3><p className="k25-observacoes">{(contrato ?? cotacao)!.observacoes || "Sem observações."}</p>
        {cotacao && perfil === "cliente" && <form className="k25-form" onSubmit={revisar}><fieldset disabled={bloquear}><label htmlFor="k25-observacoes">Observações da contratação (opcional)</label>
          <textarea id="k25-observacoes" maxLength={5000} rows={4} value={textoObservacoes} onChange={(evento) => { setRascunho({ chave: selecaoChave, texto: evento.target.value }); setErroEnvio(""); }} placeholder="Registre os termos adicionais já acordados com o fornecedor." />
          <p>O valor e o prazo serão os da cotação aceita. Ao contratar, a solicitação será encerrada para novas propostas.</p>
          {erroEnvio && <p className="k25-alert k25-error" role="alert">{erroEnvio}</p>}
          <button type="submit" className="k25-button k25-primary"><Handshake size={16} /> Revisar contratação</button>
        </fieldset></form>}
      </section>
    </div>}
    <dialog ref={dialogo} className="k25-dialog" aria-labelledby="k25-dialog-title" onCancel={(evento) => { if (trava.current) evento.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>
      {modalAtual && <><div className="k25-section-head"><h2 id="k25-dialog-title">Confirmar contratação</h2><button className="k25-button" aria-label="Fechar revisão" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>
        <p>Confira os dados antes de contratar esta proposta.</p>
        <dl className="k25-fields"><div><dt>Solicitação</dt><dd>#{modalAtual.cotacao.solicitacao_id}</dd></div><div><dt>Cotação aceita</dt><dd>#{modalAtual.cotacao.id}</dd></div>
          <div className="k25-wide"><dt>Fornecedor</dt><dd>{modalAtual.cotacao.fornecedor_razao_social}</dd></div><div><dt>Valor total</dt><dd>{formatarValorCotacao(modalAtual.cotacao.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{modalAtual.cotacao.prazo_dias} dias</dd></div></dl>
        <h3>Observações da contratação</h3><p className="k25-observacoes">{modalAtual.observacoes || "Sem observações."}</p>
        <p>A contratação ficará ativa e a solicitação será encerrada para novas propostas.</p>
        <div className="k25-dialog-actions"><button className="k25-button" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button><button className="k25-button k25-primary" disabled={enviando} onClick={() => void confirmar()}>{enviando ? "Criando contratação…" : "Confirmar contratação"}</button></div>
      </>}
    </dialog>
  </main>;
}
