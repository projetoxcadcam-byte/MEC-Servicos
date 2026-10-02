import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ClipboardList, Download, FileText, RefreshCw, Send, X, XCircle } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import {
  formatarInstanteCotacao, formatarValorCotacao, instanteUtc,
  rotuloStatusCotacao, statusCotacao, vencimentoCotacao, type CotacaoCliente,
} from "../client/cotacoesCliente";
import {
  formatarTamanhoArquivo, mensagemErroFornecedor, validarProposta,
  type ArquivoFornecedor, type CamposProposta, type CotacaoFornecedor,
  type DadosProposta, type PaginaFornecedor, type SolicitacaoFornecedor,
} from "./cotacoesFornecedor";
import "../client/ClientCotacoesPage.css";
import "./SupplierCotacoesPage.css";

type Modo = "oportunidades" | "cotacoes";
type Linha = { solicitacao: SolicitacaoFornecedor; cotacao?: CotacaoFornecedor };
type Grupo = { chave: string; total: number; itens: Linha[] };
type Rascunho = CamposProposta & { chave: string };
type Revisao = { chave: string; empresaId: number; solicitacao: SolicitacaoFornecedor; dados: DadosProposta };
const CAMPOS_VAZIOS: CamposProposta = { valor: "", prazo: "", validade: "10", observacoes: "" };
const LIMITE = 20;

export default function SupplierCotacoesPage({ modo = "oportunidades" }: { modo?: Modo }) {
  const { user } = useAuth();
  const empresaId = user?.role === "fornecedor" ? user.id : 0;
  const [deslocamento, setDeslocamento] = useState(0);
  const [atualizacao, setAtualizacao] = useState(0);
  const [grupo, setGrupo] = useState<Grupo | null>(null);
  const [selecionadoId, setSelecionadoId] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erroLista, setErroLista] = useState("");
  const [rascunho, setRascunho] = useState<Rascunho>({ chave: "", ...CAMPOS_VAZIOS });
  const [erroEnvio, setErroEnvio] = useState("");
  const [sucesso, setSucesso] = useState<{ empresaId: number; texto: string } | null>(null);
  const [revisao, setRevisao] = useState<Revisao | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [arquivos, setArquivos] = useState<{ chave: string; itens: ArquivoFornecedor[] } | null>(null);
  const [erroArquivos, setErroArquivos] = useState("");
  const [carregandoArquivos, setCarregandoArquivos] = useState(false);
  const [atualizacaoArquivos, setAtualizacaoArquivos] = useState(0);
  const [baixando, setBaixando] = useState<number | null>(null);
  const [agora, setAgora] = useState(Date.now);
  const dialogo = useRef<HTMLDialogElement | null>(null);
  const travaEnvio = useRef(false);
  const envio = useRef<AbortController | null>(null);
  const download = useRef<AbortController | null>(null);
  const montada = useRef(true);
  const urls = useRef(new Set<string>());
  const paginaChave = `${empresaId}:${modo}:${deslocamento}:${atualizacao}`;
  const grupoAtual = grupo?.chave === paginaChave ? grupo : null;
  const linhas = useMemo(() => grupoAtual?.itens ?? [], [grupoAtual]);
  const linha = linhas.find((item) => (item.cotacao?.id ?? item.solicitacao.id) === selecionadoId) ?? linhas[0];
  const solicitacao = linha?.solicitacao;
  const cotacao = linha?.cotacao;
  const selecaoChave = `${empresaId}:${modo}:${solicitacao?.id ?? 0}:${cotacao?.id ?? 0}`;
  const contexto = useRef({ empresaId, paginaChave, selecaoChave });
  contexto.current = { empresaId, paginaChave, selecaoChave };
  const campos = rascunho.chave === selecaoChave ? rascunho : CAMPOS_VAZIOS;
  const modalAtual = revisao?.chave === selecaoChave && revisao.empresaId === empresaId && grupoAtual ? revisao : null;
  const arquivosAtuais = arquivos?.chave === selecaoChave ? arquivos.itens : [];
  const total = grupoAtual?.total ?? 0;
  const bloquear = carregando || enviando || !grupoAtual;

  useEffect(() => {
    montada.current = true;
    const intervalo = window.setInterval(() => setAgora(Date.now()), 30_000);
    return () => {
      montada.current = false;
      window.clearInterval(intervalo);
      envio.current?.abort();
      download.current?.abort();
      for (const url of urls.current) URL.revokeObjectURL(url);
      urls.current.clear();
    };
  }, []);

  useEffect(() => {
    setDeslocamento(0);
    setSelecionadoId(0);
    setErroEnvio("");
    setRevisao(null);
    envio.current?.abort();
  }, [empresaId, modo]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setCarregando(true);
    setErroLista("");
    if (!empresaId) {
      setErroLista("Entre com um acesso de fornecedor para consultar suas solicitações e propostas.");
      setCarregando(false);
      return () => { vigente = false; controlador.abort(); };
    }
    async function carregar() {
      try {
        const config = { params: { empresa_fornecedora_id: empresaId, deslocamento, limite: LIMITE }, signal: controlador.signal, timeout: 20_000 };
        let itens: Linha[];
        let quantidade: number;
        if (modo === "oportunidades") {
          const { data } = await api.get<PaginaFornecedor<SolicitacaoFornecedor>>("/portal-fornecedor/oportunidades", config);
          itens = data.itens.map((item) => ({ solicitacao: item }));
          quantidade = data.total;
        } else {
          const { data } = await api.get<PaginaFornecedor<CotacaoFornecedor>>("/portal-fornecedor/cotacoes", config);
          itens = data.itens.filter((item) => item.empresa_fornecedora_id === empresaId).map((item) => ({ solicitacao: item.solicitacao, cotacao: item }));
          quantidade = data.total;
        }
        if (!vigente || contexto.current.paginaChave !== paginaChave) return;
        if (quantidade > 0 && deslocamento >= quantidade) {
          setDeslocamento(Math.floor((quantidade - 1) / LIMITE) * LIMITE);
          return;
        }
        setGrupo({ chave: paginaChave, total: quantidade, itens });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.paginaChave === paginaChave) setErroLista(mensagemErroFornecedor(erro));
      } finally {
        if (vigente && contexto.current.paginaChave === paginaChave) setCarregando(false);
      }
    }
    void carregar();
    return () => { vigente = false; controlador.abort(); };
  }, [empresaId, modo, deslocamento, paginaChave]);

  useEffect(() => {
    setErroEnvio("");
    setRevisao(null);
    setErroArquivos("");
    setBaixando(null);
    download.current?.abort();
  }, [selecaoChave]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setCarregandoArquivos(Boolean(solicitacao));
    setErroArquivos("");
    if (!solicitacao) return () => { vigente = false; controlador.abort(); };
    async function carregarArquivos() {
      try {
        const { data } = await api.get<ArquivoFornecedor[]>(`/portal-fornecedor/solicitacoes/${solicitacao!.id}/arquivos`, {
          params: { empresa_fornecedora_id: empresaId }, signal: controlador.signal, timeout: 20_000,
        });
        if (vigente && contexto.current.selecaoChave === selecaoChave) setArquivos({ chave: selecaoChave, itens: data.filter((item) => item.ativo && item.solicitacao_id === solicitacao!.id) });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.selecaoChave === selecaoChave) setErroArquivos(mensagemErroFornecedor(erro));
      } finally {
        if (vigente && contexto.current.selecaoChave === selecaoChave) setCarregandoArquivos(false);
      }
    }
    void carregarArquivos();
    return () => { vigente = false; controlador.abort(); };
  }, [empresaId, selecaoChave, solicitacao?.id, atualizacaoArquivos]);

  useEffect(() => {
    const elemento = dialogo.current;
    if (!elemento) return;
    if (modalAtual && !elemento.open) elemento.showModal();
    if (!modalAtual && elemento.open) elemento.close();
  }, [modalAtual]);

  function alterarCampo(nome: keyof CamposProposta, valor: string) {
    setRascunho({ chave: selecaoChave, ...campos, [nome]: valor });
    setErroEnvio("");
  }

  function revisar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!solicitacao || bloquear || modo !== "oportunidades" || travaEnvio.current) return;
    const resultado = validarProposta(campos);
    setErroEnvio(resultado.erro);
    if (resultado.dados) setRevisao({ chave: selecaoChave, empresaId, solicitacao, dados: resultado.dados });
  }

  async function confirmarEnvio() {
    if (!modalAtual || travaEnvio.current || bloquear) return;
    const confirmado = modalAtual;
    const chavePaginaEnvio = paginaChave;
    const controlador = new AbortController();
    envio.current = controlador;
    travaEnvio.current = true;
    setEnviando(true);
    setErroEnvio("");
    try {
      const { data } = await api.post<CotacaoCliente>(`/portal-fornecedor/solicitacoes/${confirmado.solicitacao.id}/cotacoes`, {
        empresa_fornecedora_id: confirmado.empresaId, ...confirmado.dados,
      }, { signal: controlador.signal, timeout: 30_000 });
      if (!montada.current || controlador.signal.aborted || contexto.current.empresaId !== confirmado.empresaId || contexto.current.selecaoChave !== confirmado.chave) return;
      if (data.solicitacao_id !== confirmado.solicitacao.id || data.empresa_fornecedora_id !== confirmado.empresaId) throw new Error("Resposta divergente da proposta enviada.");
      setRevisao(null);
      setRascunho({ chave: "", ...CAMPOS_VAZIOS });
      setSucesso({ empresaId: confirmado.empresaId, texto: `Cotação #${data.id} enviada para a solicitação #${data.solicitacao_id}. O cliente já pode consultá-la.` });
      setAtualizacao((valor) => valor + 1);
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.paginaChave === chavePaginaEnvio) {
        const possuiResposta = typeof erro === "object" && erro !== null && "response" in erro && Boolean((erro as { response?: unknown }).response);
        setErroEnvio(possuiResposta ? mensagemErroFornecedor(erro) : "O envio não pôde ser confirmado. Consulte Minhas Cotações antes de tentar enviar novamente.");
        setRevisao(null);
      }
    } finally {
      if (envio.current === controlador) envio.current = null;
      travaEnvio.current = false;
      if (montada.current) setEnviando(false);
    }
  }

  async function baixarArquivo(arquivo: ArquivoFornecedor) {
    if (baixando !== null || download.current || arquivo.solicitacao_id !== solicitacao?.id) return;
    const chave = selecaoChave;
    const controlador = new AbortController();
    download.current = controlador;
    setBaixando(arquivo.id);
    setErroArquivos("");
    try {
      const { data } = await api.get<Blob>(`/portal-fornecedor/arquivos/${arquivo.id}/download`, {
        params: { empresa_fornecedora_id: empresaId }, responseType: "blob", signal: controlador.signal, timeout: 60_000,
      });
      if (!montada.current || controlador.signal.aborted || contexto.current.selecaoChave !== chave) return;
      const url = URL.createObjectURL(data);
      urls.current.add(url);
      const ancora = document.createElement("a");
      ancora.href = url;
      ancora.download = arquivo.nome_original;
      document.body.appendChild(ancora);
      ancora.click();
      ancora.remove();
      window.setTimeout(() => { URL.revokeObjectURL(url); urls.current.delete(url); }, 30_000);
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.selecaoChave === chave) setErroArquivos(mensagemErroFornecedor(erro));
    } finally {
      if (download.current === controlador) download.current = null;
      if (montada.current && contexto.current.selecaoChave === chave) setBaixando(null);
    }
  }

  return (
    <div className="c23-page f24-page">
      <header className="c23-header">
        <div><span className="c23-eyebrow"><ClipboardList size={15} /> PORTAL DO FORNECEDOR</span>
          <h1>{modo === "oportunidades" ? "Solicitações Compatíveis" : "Minhas Cotações"}</h1>
          <p>{modo === "oportunidades" ? "Consulte os requisitos e envie sua proposta ao cliente." : "Acompanhe suas propostas, prazos e decisões do cliente."}</p></div>
        <button className="c23-button" disabled={carregando || enviando} onClick={() => setAtualizacao((valor) => valor + 1)}><RefreshCw size={15} className={carregando ? "c23-spin" : ""} /> Atualizar</button>
      </header>
      <nav className="f24-tabs" aria-label="Cotações do fornecedor">
        <Link className={modo === "oportunidades" ? "f24-tab f24-tab-active" : "f24-tab"} to="/fornecedor/solicitacoes"><ClipboardList size={16} /> Solicitações Compatíveis</Link>
        <Link className={modo === "cotacoes" ? "f24-tab f24-tab-active" : "f24-tab"} to="/fornecedor/cotacoes"><FileText size={16} /> Minhas Cotações</Link>
      </nav>
      {sucesso?.empresaId === empresaId && <div className="c23-alert c23-alert-success" role="status"><CheckCircle2 size={18} /><span>{sucesso.texto} <Link to="/fornecedor/cotacoes">Ver minhas cotações</Link></span></div>}
      {erroEnvio && <div className="c23-alert c23-alert-error" role="alert"><XCircle size={18} /><span>{erroEnvio} <Link to="/fornecedor/cotacoes">Minhas Cotações</Link></span></div>}
      {erroLista && <div className="c23-alert c23-alert-error" role="alert"><XCircle size={18} />{erroLista}</div>}
      <section className="c23-panel">
        <div className="c23-toolbar"><div><h2>{modo === "oportunidades" ? "Oportunidades para sua empresa" : "Propostas enviadas"}</h2><p>{grupoAtual ? `${total} ${modo === "oportunidades" ? "solicitações disponíveis" : "cotações da sua empresa"}` : "Consultando suas informações"}</p></div>
          <span className="c23-footnote">{modo === "oportunidades" ? "Processo · material · dimensões · tolerância" : "As decisões são atualizadas ao consultar a lista."}</span></div>
        {carregando ? <div className="c23-empty" role="status"><RefreshCw className="c23-spin" size={26} /><strong>Carregando...</strong></div>
          : !erroLista && linhas.length === 0 ? <div className="c23-empty"><ClipboardList size={34} /><strong>{modo === "oportunidades" ? "Nenhuma solicitação disponível" : "Sua empresa ainda não enviou cotações"}</strong><p>{modo === "oportunidades" ? "As oportunidades precisam estar abertas e atender aos processos, materiais, dimensões e tolerância cadastrados para sua empresa. Solicitações já cotadas ficam em Minhas Cotações." : "Escolha uma solicitação compatível e envie sua primeira proposta."}</p>{modo === "cotacoes" && <Link className="c23-link" to="/fornecedor/solicitacoes">Consultar solicitações</Link>}</div>
            : linhas.length > 0 && <>
              <div className="c23-table-scroll"><table><thead><tr><th>Solicitação / cliente</th><th>Processo / material</th><th>{modo === "oportunidades" ? "Quantidade" : "Valor total"}</th><th>{modo === "oportunidades" ? "Dimensões X × Y × Z" : "Situação"}</th><th><span className="c23-sr">Ações</span></th></tr></thead>
                <tbody>{linhas.map((item) => {
                  const s = item.solicitacao;
                  const c = item.cotacao;
                  const id = c?.id ?? s.id;
                  const selecionada = id === (linha?.cotacao?.id ?? linha?.solicitacao.id);
                  const status = c ? statusCotacao(c, agora) : "";
                  return <tr key={id} className={selecionada ? "f24-selected" : ""}>
                    <td><strong>Solicitação #{s.id}{c ? ` · Cotação #${c.id}` : ""}</strong><small>{s.cliente_razao_social}</small></td>
                    <td><strong>{s.processo_nome}</strong><small>{s.material_nome}</small></td>
                    <td>{c ? <strong className="c23-price">{formatarValorCotacao(c.valor_total)}</strong> : `${s.quantidade} un.`}</td>
                    <td>{c ? <span className={`c23-badge ${status === "aceita" ? "c23-status-success" : status === "enviada" ? "c23-status-pending" : "c23-status-closed"}`}>{rotuloStatusCotacao(status)}</span> : <span>{s.dimensao_x_maxima_mm} × {s.dimensao_y_maxima_mm} × {s.dimensao_z_maxima_mm} mm</span>}</td>
                    <td><button className="c23-button c23-small" aria-pressed={selecionada} disabled={enviando} onClick={() => setSelecionadoId(id)}>{selecionada ? "Selecionada" : "Ver detalhes"}</button></td>
                  </tr>;
                })}</tbody></table></div>
              <div className="f24-pagination"><span>{deslocamento + 1}–{deslocamento + linhas.length} de {total}</span><div><button className="c23-button c23-small" disabled={bloquear || deslocamento === 0} onClick={() => setDeslocamento((valor) => Math.max(0, valor - LIMITE))}>Anterior</button><button className="c23-button c23-small" disabled={bloquear || deslocamento + LIMITE >= total} onClick={() => setDeslocamento((valor) => valor + LIMITE)}>Próxima</button></div></div>
            </>}
      </section>
      {solicitacao && !carregando && !erroLista && <div className="f24-columns">
        <section className="c23-panel f24-detail"><div className="f24-section-head"><h2>Solicitação #{solicitacao.id}</h2><span className="c23-footnote">{solicitacao.cliente_razao_social}</span></div>
          <div className="c23-detail-grid"><div><span>Processo</span><strong>{solicitacao.processo_nome}</strong></div><div><span>Material</span><strong>{solicitacao.material_nome}</strong></div>
            <div><span>Dimensões X × Y × Z (mm)</span><strong>{solicitacao.dimensao_x_maxima_mm} × {solicitacao.dimensao_y_maxima_mm} × {solicitacao.dimensao_z_maxima_mm}</strong></div><div><span>Tolerância requerida (mm)</span><strong>{solicitacao.tolerancia_requerida_mm}</strong></div>
            <div><span>Quantidade</span><strong>{solicitacao.quantidade} unidades</strong></div><div><span>Solicitada em</span><strong>{formatarInstanteCotacao(instanteUtc(solicitacao.criada_em))}</strong></div></div>
          <div className="c23-observacoes"><span>Observações do cliente</span><p>{solicitacao.observacoes || "Sem observações."}</p></div>
          <div className="f24-section-head f24-files-head"><h3>Arquivos técnicos</h3><button className="c23-button c23-small" disabled={carregandoArquivos || baixando !== null} onClick={() => setAtualizacaoArquivos((valor) => valor + 1)} aria-label="Atualizar arquivos técnicos"><RefreshCw size={14} /></button></div>
          {erroArquivos && <p className="c23-alert c23-alert-error" role="alert">{erroArquivos}</p>}
          {carregandoArquivos ? <p className="c23-footnote" role="status">Carregando arquivos...</p> : !erroArquivos && (arquivosAtuais.length ? <ul className="f24-files">{arquivosAtuais.map((arquivo) => <li key={arquivo.id}><FileText size={19} /><span><strong>{arquivo.nome_original}</strong><small>{arquivo.extensao.replace(".", "").toUpperCase()} · {formatarTamanhoArquivo(arquivo.tamanho_bytes)}</small></span><button className="c23-button c23-small" disabled={baixando !== null} onClick={() => void baixarArquivo(arquivo)} aria-label={`Baixar ${arquivo.nome_original}`}><Download size={15} />{baixando === arquivo.id ? "Baixando..." : "Baixar"}</button></li>)}</ul> : <p className="c23-footnote">O cliente ainda não vinculou arquivos a esta solicitação.</p>)}
        </section>
        {modo === "oportunidades" ? <section className="c23-panel f24-form-panel"><div className="f24-section-head"><h2>Sua proposta</h2><Send size={20} /></div><p className="c23-footnote">Informe o valor total para as {solicitacao.quantidade} unidades solicitadas.</p>
          <form onSubmit={revisar} className="f24-form"><fieldset disabled={bloquear}>
            <label htmlFor="f24-valor">Valor total (R$)</label><input id="f24-valor" inputMode="decimal" autoComplete="off" maxLength={24} placeholder="Ex.: 1.250,50" value={campos.valor} onChange={(evento) => alterarCampo("valor", evento.target.value)} required />
            <div className="f24-form-grid"><div><label htmlFor="f24-prazo">Prazo de execução (dias)</label><input id="f24-prazo" type="number" min={1} max={3650} step={1} value={campos.prazo} onChange={(evento) => alterarCampo("prazo", evento.target.value)} required /></div><div><label htmlFor="f24-validade">Validade da proposta (dias)</label><input id="f24-validade" type="number" min={1} max={3650} step={1} value={campos.validade} onChange={(evento) => alterarCampo("validade", evento.target.value)} required /></div></div>
            <label htmlFor="f24-observacoes">Observações da proposta</label><textarea id="f24-observacoes" maxLength={5000} rows={5} placeholder="Condições, itens inclusos e informações para o cliente." value={campos.observacoes} onChange={(evento) => alterarCampo("observacoes", evento.target.value)} /><small className="c23-footnote">{campos.observacoes.length}/5000 caracteres</small>
            <p className="c23-footnote">Após o envio, a proposta fica registrada para esta solicitação. A validade começa no envio.</p>
            <button className="c23-button c23-primary f24-submit" type="submit"><Send size={16} />{enviando ? "Enviando..." : "Revisar e enviar proposta"}</button>
          </fieldset></form></section>
          : cotacao && <section className="c23-panel f24-detail"><div className="f24-section-head"><h2>Cotação #{cotacao.id}</h2><FileText size={20} /></div><div className="c23-detail-grid"><div><span>Valor total</span><strong>{formatarValorCotacao(cotacao.valor_total)}</strong></div><div><span>Situação</span><strong>{rotuloStatusCotacao(statusCotacao(cotacao, agora))}</strong></div><div><span>Prazo de execução</span><strong>{cotacao.prazo_dias} dias</strong></div><div><span>Validade</span><strong>{cotacao.validade_dias} dias</strong></div></div>
            <div className="c23-observacoes"><span>Observações da proposta</span><p>{cotacao.observacoes || "Sem observações."}</p></div><p className="c23-dates">Enviada em {formatarInstanteCotacao(instanteUtc(cotacao.criada_em))}<br />Validade até {formatarInstanteCotacao(vencimentoCotacao(cotacao))}{cotacao.encerrada_em && <><br />Encerrada em {formatarInstanteCotacao(instanteUtc(cotacao.encerrada_em))}</>}</p></section>}
      </div>}
      <dialog ref={dialogo} className="c23-dialog" aria-labelledby="f24-confirmacao" onCancel={(evento) => { evento.preventDefault(); if (!travaEnvio.current) setRevisao(null); }}>
        {modalAtual && <><div className="c23-dialog-head"><div><span className="c23-eyebrow">REVISÃO DA PROPOSTA</span><h2 id="f24-confirmacao">Enviar cotação ao cliente?</h2></div><button className="c23-icon-button" disabled={enviando} aria-label="Fechar revisão" onClick={() => setRevisao(null)}><X size={22} /></button></div>
          <p className="c23-footnote">Solicitação #{modalAtual.solicitacao.id} · {modalAtual.solicitacao.cliente_razao_social} · {modalAtual.solicitacao.quantidade} unidades</p><div className="c23-detail-grid f24-review"><div><span>Valor total</span><strong>{formatarValorCotacao(modalAtual.dados.valor_total)}</strong></div><div><span>Prazo de execução</span><strong>{modalAtual.dados.prazo_dias} dias</strong></div><div><span>Validade após o envio</span><strong>{modalAtual.dados.validade_dias} dias</strong></div><div><span>Processo / material</span><strong>{modalAtual.solicitacao.processo_nome} · {modalAtual.solicitacao.material_nome}</strong></div></div>
          <div className="c23-observacoes"><span>Observações que o cliente receberá</span><p>{modalAtual.dados.observacoes || "Sem observações."}</p></div><p className="c23-footnote f24-review">Ao confirmar, sua proposta será registrada e o cliente poderá aceitá-la ou recusá-la.</p><div className="c23-dialog-actions"><button className="c23-button" disabled={enviando} autoFocus onClick={() => setRevisao(null)}>Voltar ao formulário</button><button className="c23-button c23-primary" disabled={enviando || bloquear} onClick={() => void confirmarEnvio()}><Send size={16} />{enviando ? "Enviando..." : "Confirmar envio"}</button></div></>}
      </dialog>
    </div>
  );
}
