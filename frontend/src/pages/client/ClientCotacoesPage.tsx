import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Clock3, FileText, RefreshCw, Search, XCircle } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import {
  formatarInstanteCotacao, formatarValorCotacao, instanteUtc, mensagemErroCotacao,
  ordenarCotacoes, podeDecidirCotacao, rotuloStatusCotacao, statusCotacao, vencimentoCotacao,
  type AcaoCotacao, type CotacaoCliente, type OrdenacaoCotacoes, type SolicitacaoCliente,
} from "./cotacoesCliente";
import "./ClientCotacoesPage.css";

type GrupoCotacoes = {
  empresaId: number;
  solicitacaoId: number;
  itens: CotacaoCliente[];
  fornecedores: Record<number, string>;
};
type ModalCotacao = {
  empresaId: number;
  solicitacaoId: number;
  cotacaoId: number;
  acao: AcaoCotacao | "detalhes";
};
type EmpresaFornecedor = { id: number; razao_social: string };

function resumoSolicitacao(item: SolicitacaoCliente): string {
  return `Solicitação #${item.id} · ${item.quantidade} un. · ${item.dimensao_x_maxima_mm} × ${item.dimensao_y_maxima_mm} × ${item.dimensao_z_maxima_mm} mm`;
}

export default function ClientCotacoesPage() {
  const { user } = useAuth();
  const empresaId = user?.id ?? 0;
  const [parametros, setParametros] = useSearchParams();
  const [solicitacoes, setSolicitacoes] = useState<SolicitacaoCliente[]>([]);
  const [grupo, setGrupo] = useState<GrupoCotacoes | null>(null);
  const [carregandoSolicitacoes, setCarregandoSolicitacoes] = useState(true);
  const [carregandoCotacoes, setCarregandoCotacoes] = useState(false);
  const [erroSolicitacoes, setErroSolicitacoes] = useState("");
  const [erroCotacoes, setErroCotacoes] = useState("");
  const [erroDecisao, setErroDecisao] = useState("");
  const [avisoFornecedores, setAvisoFornecedores] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [revisaoSolicitacoes, setRevisaoSolicitacoes] = useState(0);
  const [revisaoCotacoes, setRevisaoCotacoes] = useState(0);
  const [ordenacao, setOrdenacao] = useState<OrdenacaoCotacoes>("valor");
  const [filtro, setFiltro] = useState("todas");
  const [busca, setBusca] = useState("");
  const [agora, setAgora] = useState(Date.now);
  const [modal, setModal] = useState<ModalCotacao | null>(null);
  const [decidindo, setDecidindo] = useState(false);
  const dialogoRef = useRef<HTMLDialogElement | null>(null);
  const envioRef = useRef(false);
  const montadaRef = useRef(true);

  const minhasSolicitacoes = useMemo(() => solicitacoes.filter((item) => item.empresa_cliente_id === empresaId), [solicitacoes, empresaId]);
  const idPedido = Number(parametros.get("solicitacao"));
  const solicitacaoId = minhasSolicitacoes.some((item) => item.id === idPedido) ? idPedido : minhasSolicitacoes[0]?.id ?? 0;
  const solicitacao = minhasSolicitacoes.find((item) => item.id === solicitacaoId);
  const visaoRef = useRef({ empresaId, solicitacaoId });
  visaoRef.current = { empresaId, solicitacaoId };
  const grupoAtual = grupo?.empresaId === empresaId && grupo.solicitacaoId === solicitacaoId ? grupo : null;
  const cotacoes = grupoAtual?.itens ?? [];
  const fornecedores = grupoAtual?.fornecedores ?? {};
  const possuiAceita = cotacoes.some((item) => item.status === "aceita");
  const modalAtual = modal?.empresaId === empresaId && modal.solicitacaoId === solicitacaoId ? modal : null;
  const cotacaoModal = modalAtual ? cotacoes.find((item) => item.id === modalAtual.cotacaoId) : undefined;
  const nomeFornecedor = (id: number) => fornecedores[id] ?? `Fornecedor #${id}`;

  useEffect(() => {
    montadaRef.current = true;
    const intervalo = window.setInterval(() => setAgora(Date.now()), 30_000);
    return () => { montadaRef.current = false; window.clearInterval(intervalo); };
  }, []);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setCarregandoSolicitacoes(true);
    setErroSolicitacoes("");
    if (!empresaId) {
      setSolicitacoes([]);
      setErroSolicitacoes("Entre com uma conta cliente associada a uma empresa.");
      setCarregandoSolicitacoes(false);
      return () => controlador.abort();
    }
    void (async () => {
      try {
        const resposta = await api.get<SolicitacaoCliente[]>("/solicitacoes-servico", {
          params: { empresa_cliente_id: empresaId }, signal: controlador.signal,
        });
        if (!Array.isArray(resposta.data)) throw new Error("Resposta de solicitações inválida.");
        if (vigente) setSolicitacoes(resposta.data.filter((item) => item.empresa_cliente_id === empresaId).sort((a, b) => b.id - a.id));
      } catch (erro) {
        if (vigente && !controlador.signal.aborted) { setErroSolicitacoes(mensagemErroCotacao(erro)); setSolicitacoes([]); }
      } finally {
        if (vigente) setCarregandoSolicitacoes(false);
      }
    })();
    return () => { vigente = false; controlador.abort(); };
  }, [empresaId, revisaoSolicitacoes]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setErroCotacoes("");
    setAvisoFornecedores("");
    setGrupo(null);
    if (!empresaId || !solicitacaoId) { setCarregandoCotacoes(false); return () => controlador.abort(); }
    setCarregandoCotacoes(true);
    void (async () => {
      try {
        const resposta = await api.get<CotacaoCliente[]>(`/solicitacoes-servico/${solicitacaoId}/cotacoes`, { signal: controlador.signal });
        if (!Array.isArray(resposta.data) || resposta.data.some((item) => item.solicitacao_id !== solicitacaoId)) throw new Error("Resposta de cotações inválida.");
        if (!vigente) return;
        const itens = resposta.data;
        const nomes: Record<number, string> = {};
        setGrupo({ empresaId, solicitacaoId, itens, fornecedores: nomes });
        setCarregandoCotacoes(false);
        const ids = [...new Set(itens.map((item) => item.empresa_fornecedora_id))];
        let falhas = 0;
        for (let inicio = 0; inicio < ids.length && vigente; inicio += 8) {
          const resultados = await Promise.allSettled(ids.slice(inicio, inicio + 8).map(async (id) => {
            const empresa = await api.get<EmpresaFornecedor>(`/empresas/${id}`, { signal: controlador.signal });
            if (empresa.data.id !== id || !empresa.data.razao_social) throw new Error("Fornecedor indisponível.");
            return empresa.data;
          }));
          if (!vigente) return;
          for (const resultado of resultados) {
            if (resultado.status === "fulfilled") nomes[resultado.value.id] = resultado.value.razao_social;
            else falhas += 1;
          }
          setGrupo({ empresaId, solicitacaoId, itens, fornecedores: { ...nomes } });
        }
        if (vigente && falhas) setAvisoFornecedores("Alguns nomes de fornecedores estão indisponíveis. As propostas continuam identificadas pelo número da empresa.");
      } catch (erro) {
        if (vigente && !controlador.signal.aborted) setErroCotacoes(mensagemErroCotacao(erro));
      } finally {
        if (vigente) setCarregandoCotacoes(false);
      }
    })();
    return () => { vigente = false; controlador.abort(); };
  }, [empresaId, solicitacaoId, revisaoCotacoes]);

  useEffect(() => {
    setModal(null); setSucesso(""); setErroDecisao(""); setFiltro("todas"); setBusca("");
  }, [empresaId, solicitacaoId]);

  useEffect(() => {
    const dialogo = dialogoRef.current;
    if (!dialogo) return;
    if (modalAtual && cotacaoModal && !dialogo.open) dialogo.showModal();
    else if ((!modalAtual || !cotacaoModal) && dialogo.open) dialogo.close();
  }, [modalAtual, cotacaoModal]);

  const disponiveis = cotacoes.filter((item) => podeDecidirCotacao(item, possuiAceita, agora));
  const menorValor = disponiveis.length ? Math.min(...disponiveis.map((item) => Number(item.valor_total))) : null;
  const menorPrazo = disponiveis.length ? Math.min(...disponiveis.map((item) => item.prazo_dias)) : null;
  const textoBusca = busca.trim().toLocaleLowerCase("pt-BR");
  const exibidas = ordenarCotacoes(cotacoes, ordenacao).filter((item) =>
    (filtro === "todas" || statusCotacao(item, agora) === filtro)
    && (!textoBusca || `${item.id} ${item.empresa_fornecedora_id} ${nomeFornecedor(item.empresa_fornecedora_id)}`.toLocaleLowerCase("pt-BR").includes(textoBusca)),
  );

  function abrirModal(item: CotacaoCliente, acao: ModalCotacao["acao"]) {
    if (envioRef.current || carregandoCotacoes) return;
    if (acao !== "detalhes" && !podeDecidirCotacao(item, possuiAceita, Date.now())) {
      setErroDecisao("Esta proposta não está disponível para decisão. Atualize as cotações.");
      return;
    }
    setErroDecisao("");
    setModal({ empresaId, solicitacaoId, cotacaoId: item.id, acao });
  }

  async function confirmarDecisao() {
    if (!modalAtual || !cotacaoModal || modalAtual.acao === "detalhes" || envioRef.current) return;
    const item = cotacaoModal;
    const acao = modalAtual.acao;
    const contexto = { empresaId, solicitacaoId };
    if (!podeDecidirCotacao(item, possuiAceita, Date.now())) {
      setModal(null); setErroDecisao("Esta proposta não está disponível para decisão. Atualize as cotações.");
      setRevisaoCotacoes((valor) => valor + 1);
      return;
    }
    envioRef.current = true;
    setDecidindo(true); setErroDecisao(""); setSucesso("");
    const mesmaVisao = () => montadaRef.current && visaoRef.current.empresaId === contexto.empresaId && visaoRef.current.solicitacaoId === contexto.solicitacaoId;
    try {
      const resposta = await api.post<CotacaoCliente>(`/solicitacoes-servico/${contexto.solicitacaoId}/cotacoes/${item.id}/${acao}`, { empresa_cliente_id: contexto.empresaId });
      if (resposta.data.id !== item.id || resposta.data.solicitacao_id !== contexto.solicitacaoId || resposta.data.status !== (acao === "aceitar" ? "aceita" : "recusada")) throw new Error("Não foi possível confirmar o resultado.");
      if (mesmaVisao()) {
        setModal(null);
        setSucesso(acao === "aceitar" ? `Cotação #${item.id} aceita. As demais propostas pendentes desta solicitação foram recusadas.` : `Cotação #${item.id} recusada.`);
        setRevisaoCotacoes((valor) => valor + 1);
      }
    } catch (erro) {
      if (mesmaVisao()) {
        setModal(null); setErroDecisao(mensagemErroCotacao(erro));
        setRevisaoCotacoes((valor) => valor + 1);
      }
    } finally {
      envioRef.current = false;
      if (montadaRef.current) setDecidindo(false);
    }
  }

  function atualizar() {
    if (envioRef.current) return;
    setErroDecisao(""); setSucesso("");
    setRevisaoSolicitacoes((valor) => valor + 1);
    setRevisaoCotacoes((valor) => valor + 1);
  }

  return <div className="c23-page">
    <header className="c23-header">
      <div><div className="c23-eyebrow"><FileText size={16} /> PORTAL DO CLIENTE</div><h1>Cotações Recebidas</h1><p>Compare as propostas e escolha a mais adequada ao seu serviço.</p></div>
      <button type="button" className="c23-button" onClick={atualizar} disabled={carregandoSolicitacoes || carregandoCotacoes || decidindo}><RefreshCw size={16} className={carregandoSolicitacoes || carregandoCotacoes ? "c23-spin" : ""} /> Atualizar</button>
    </header>

    {erroSolicitacoes && <div className="c23-alert c23-alert-error" role="alert">{erroSolicitacoes}</div>}
    {erroDecisao && <div className="c23-alert c23-alert-error" role="alert">{erroDecisao}</div>}
    {sucesso && <div className="c23-alert c23-alert-success" role="status"><CheckCircle2 size={18} /> {sucesso}</div>}

    <section className="c23-panel c23-selector" aria-label="Selecionar solicitação">
      <label htmlFor="c23-solicitacao">Solicitação de serviço</label>
      <div className="c23-selector-row"><select id="c23-solicitacao" value={solicitacaoId || ""} disabled={carregandoSolicitacoes || decidindo || !minhasSolicitacoes.length} onChange={(evento) => {
        const proximos = new URLSearchParams(parametros); proximos.set("solicitacao", evento.target.value); setParametros(proximos);
      }}>
        {!minhasSolicitacoes.length && <option value="">{carregandoSolicitacoes ? "Carregando solicitações..." : "Nenhuma solicitação disponível"}</option>}
        {minhasSolicitacoes.map((item) => <option key={item.id} value={item.id}>{resumoSolicitacao(item)}</option>)}
      </select><Link className="c23-link" to="/cliente/solicitacoes">Minhas solicitações</Link><Link className="c23-link" to="/cliente/arquivos-tecnicos">Arquivos técnicos</Link></div>
      {solicitacao?.observacoes && <p className="c23-request-note">{solicitacao.observacoes}</p>}
    </section>

    <div className="c23-metrics" aria-label="Resumo das propostas da solicitação">
      <article><span>Propostas recebidas</span><strong>{carregandoCotacoes ? "—" : cotacoes.length}</strong><small>Nesta solicitação</small></article>
      <article><span>Aguardando decisão</span><strong>{carregandoCotacoes ? "—" : disponiveis.length}</strong><small>Dentro da validade</small></article>
      <article><span>Menor valor disponível</span><strong className="c23-metric-value">{menorValor === null ? "—" : formatarValorCotacao(menorValor)}</strong><small>Entre as propostas válidas</small></article>
      <article><span>Menor prazo disponível</span><strong>{menorPrazo === null ? "—" : `${menorPrazo} dias`}</strong><small>Entre as propostas válidas</small></article>
    </div>

    {possuiAceita && <div className="c23-alert c23-alert-success"><CheckCircle2 size={18} /> Esta solicitação já possui uma cotação aceita. Consulte os detalhes abaixo.</div>}
    {avisoFornecedores && <div className="c23-alert" role="status">{avisoFornecedores}</div>}

    <section className="c23-panel" aria-label="Comparação de cotações" aria-busy={carregandoCotacoes}>
      <div className="c23-toolbar"><div><h2>Propostas dos fornecedores</h2><p>Valores totais, prazo de execução e validade da oferta.</p></div>
        <div className="c23-filters"><label className="c23-search"><Search size={16} /><span className="c23-sr">Buscar fornecedor ou cotação</span><input type="search" value={busca} placeholder="Fornecedor ou cotação" onChange={(evento) => setBusca(evento.target.value)} /></label>
          <label><span className="c23-sr">Filtrar por situação</span><select value={filtro} onChange={(evento) => setFiltro(evento.target.value)}><option value="todas">Todas as situações</option><option value="enviada">Aguardando decisão</option><option value="aceita">Aceitas</option><option value="recusada">Recusadas</option><option value="expirada">Expiradas</option><option value="cancelada">Canceladas</option></select></label>
          <label><span className="c23-sr">Ordenar propostas</span><select value={ordenacao} onChange={(evento) => setOrdenacao(evento.target.value as OrdenacaoCotacoes)}><option value="valor">Menor valor</option><option value="prazo">Menor prazo</option><option value="recentes">Mais recentes</option></select></label>
        </div>
      </div>
      {erroCotacoes ? <div className="c23-empty" role="alert"><XCircle size={32} /><strong>Não foi possível carregar as propostas</strong><p>{erroCotacoes}</p><button type="button" className="c23-button" onClick={() => setRevisaoCotacoes((valor) => valor + 1)}>Tentar novamente</button></div>
        : carregandoSolicitacoes || carregandoCotacoes ? <div className="c23-empty" role="status"><RefreshCw className="c23-spin" size={30} /><strong>Carregando cotações...</strong></div>
          : !minhasSolicitacoes.length ? <div className="c23-empty"><FileText size={32} /><strong>Comece por uma solicitação</strong><p>Cadastre seu serviço para receber propostas dos fornecedores.</p><Link className="c23-button c23-primary" to="/cliente/solicitacoes">Ir para solicitações</Link></div>
            : !cotacoes.length ? <div className="c23-empty"><Clock3 size={32} /><strong>Nenhuma cotação recebida nesta solicitação</strong><p>As propostas aparecerão aqui quando os fornecedores enviarem suas cotações.</p></div>
              : !exibidas.length ? <div className="c23-empty"><Search size={32} /><strong>Nenhuma proposta corresponde aos filtros</strong><button type="button" className="c23-button" onClick={() => { setFiltro("todas"); setBusca(""); }}>Limpar filtros</button></div>
                : <div className="c23-table-scroll"><table><caption className="c23-sr">Cotações da solicitação #{solicitacaoId}</caption><thead><tr><th scope="col">Fornecedor / cotação</th><th scope="col">Valor total</th><th scope="col">Prazo</th><th scope="col">Validade até</th><th scope="col">Situação</th><th scope="col">Ações</th></tr></thead><tbody>
                  {exibidas.map((item) => {
                    const status = statusCotacao(item, agora);
                    const podeDecidir = podeDecidirCotacao(item, possuiAceita, agora) && !decidindo;
                    return <tr key={item.id}><td><strong>{nomeFornecedor(item.empresa_fornecedora_id)}</strong><small>Cotação #{item.id} · Empresa #{item.empresa_fornecedora_id}</small></td>
                      <td><strong className="c23-price">{formatarValorCotacao(item.valor_total)}</strong>{podeDecidir && Number(item.valor_total) === menorValor && <small className="c23-highlight">Menor valor</small>}</td>
                      <td><strong>{item.prazo_dias} dias</strong>{podeDecidir && item.prazo_dias === menorPrazo && <small className="c23-highlight">Menor prazo</small>}</td>
                      <td>{formatarInstanteCotacao(vencimentoCotacao(item))}</td><td><span className={`c23-badge c23-status-${status === "aceita" ? "success" : status === "enviada" ? "pending" : "closed"}`}>{rotuloStatusCotacao(status)}</span></td>
                      <td><div className="c23-actions"><button type="button" className="c23-button c23-small" onClick={() => abrirModal(item, "detalhes")} disabled={decidindo}>Detalhes</button>
                        {podeDecidir && <><button type="button" className="c23-button c23-primary c23-small" onClick={() => abrirModal(item, "aceitar")}>Aceitar</button><button type="button" className="c23-button c23-small c23-danger-text" onClick={() => abrirModal(item, "recusar")}>Recusar</button></>}
                      </div></td></tr>;
                  })}
                </tbody></table></div>}
    </section>

    <p className="c23-footnote">As propostas são comparadas dentro da mesma solicitação. Uma oferta expirada não pode ser aceita ou recusada.</p>

    <dialog ref={dialogoRef} className="c23-dialog" aria-labelledby="c23-dialog-title" onCancel={(evento) => { if (envioRef.current) evento.preventDefault(); else setModal(null); }} onClose={() => { if (!envioRef.current) setModal(null); }}>
      {modalAtual && cotacaoModal && <><div className="c23-dialog-head"><div><div className="c23-eyebrow">COTAÇÃO #{cotacaoModal.id}</div><h2 id="c23-dialog-title">{modalAtual.acao === "detalhes" ? "Detalhes da proposta" : modalAtual.acao === "aceitar" ? "Aceitar esta cotação?" : "Recusar esta cotação?"}</h2></div><button type="button" className="c23-icon-button" aria-label="Fechar" disabled={decidindo} onClick={() => setModal(null)}><XCircle size={22} /></button></div>
        <div className="c23-detail-grid"><div><span>Fornecedor</span><strong>{nomeFornecedor(cotacaoModal.empresa_fornecedora_id)}</strong></div><div><span>Solicitação</span><strong>#{cotacaoModal.solicitacao_id}</strong></div><div><span>Valor total</span><strong>{formatarValorCotacao(cotacaoModal.valor_total)}</strong></div><div><span>Prazo de execução</span><strong>{cotacaoModal.prazo_dias} dias</strong></div><div><span>Validade até</span><strong>{formatarInstanteCotacao(vencimentoCotacao(cotacaoModal))}</strong></div><div><span>Situação</span><strong>{rotuloStatusCotacao(statusCotacao(cotacaoModal, agora))}</strong></div></div>
        {modalAtual.acao === "detalhes" ? <><div className="c23-observacoes"><span>Observações do fornecedor</span><p>{cotacaoModal.observacoes?.trim() || "Nenhuma observação informada."}</p></div><p className="c23-dates">Enviada em {formatarInstanteCotacao(instanteUtc(cotacaoModal.criada_em))}{cotacaoModal.encerrada_em ? ` · Encerrada em ${formatarInstanteCotacao(instanteUtc(cotacaoModal.encerrada_em))}` : ""}</p></>
          : <div className={`c23-alert ${modalAtual.acao === "aceitar" ? "" : "c23-alert-warning"}`}>{modalAtual.acao === "aceitar" ? "Ao confirmar, esta será a cotação escolhida e as demais propostas pendentes desta solicitação serão recusadas automaticamente." : "Ao confirmar, esta proposta será recusada. As outras cotações da solicitação continuarão disponíveis."}</div>}
        <div className="c23-dialog-actions"><button type="button" className="c23-button" disabled={decidindo} onClick={() => setModal(null)}>{modalAtual.acao === "detalhes" ? "Fechar" : "Voltar"}</button>
          {modalAtual.acao === "detalhes" ? podeDecidirCotacao(cotacaoModal, possuiAceita, agora) && <><button type="button" className="c23-button c23-danger-text" onClick={() => abrirModal(cotacaoModal, "recusar")}>Recusar</button><button type="button" className="c23-button c23-primary" onClick={() => abrirModal(cotacaoModal, "aceitar")}>Aceitar</button></>
            : <button type="button" className={`c23-button ${modalAtual.acao === "aceitar" ? "c23-primary" : "c23-danger"}`} disabled={decidindo || !podeDecidirCotacao(cotacaoModal, possuiAceita, agora)} onClick={() => { void confirmarDecisao(); }}>{decidindo ? <><RefreshCw className="c23-spin" size={16} /> Registrando...</> : modalAtual.acao === "aceitar" ? "Confirmar aceite" : "Confirmar recusa"}</button>}
        </div></>}
    </dialog>
  </div>;
}
