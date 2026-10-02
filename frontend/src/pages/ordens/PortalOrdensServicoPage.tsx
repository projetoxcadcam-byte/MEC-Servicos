import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, ClipboardList, Download, FileText, Handshake, Play, RefreshCw, Wrench, X } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { formatarInstanteCotacao, formatarValorCotacao, instanteUtc } from "../client/cotacoesCliente";
import { formatarMedidaContrato, rotuloContratacao, type ContratacaoPortal, type PaginaContratacoes } from "../contratacoes/contratacoesPortal";
import { formatarTamanhoArquivo, type ArquivoFornecedor } from "../supplier/cotacoesFornecedor";
import { mensagemErroOrdem, rotuloOrdem, type AcaoOrdem, type OrdemPortal, type OrdemResposta, type PerfilOrdens } from "./ordensPortal";
import "./PortalOrdensServicoPage.css";

type Visao = "ordens" | "contratos";
type Grupo = { chave: string; ordens: PaginaContratacoes<OrdemPortal>; contratos: PaginaContratacoes<ContratacaoPortal> };
type Revisao = { chave: string; dono: string } & (
  { acao: "gerar"; contrato: ContratacaoPortal } | { acao: "iniciar" | "concluir"; ordem: OrdemPortal }
);
const LIMITE = 20;
const PAGINA_VAZIA = { itens: [], total: 0, deslocamento: 0, limite: LIMITE };
const TITULOS: Record<AcaoOrdem, string> = { gerar: "Gerar ordem de serviço", iniciar: "Confirmar início", concluir: "Confirmar conclusão" };

export default function PortalOrdensServicoPage({ perfil }: { perfil: PerfilOrdens }) {
  const { user } = useAuth();
  const empresaId = user?.role === perfil ? user.id : 0;
  const base = `/portal-${perfil}`;
  const dono = `${perfil}:${empresaId}`;
  const [visao, setVisao] = useState<Visao>("ordens");
  const visaoAtual = perfil === "cliente" ? visao : "ordens";
  const [deslocamento, setDeslocamento] = useState(0);
  const [atualizacao, setAtualizacao] = useState(0);
  const [grupo, setGrupo] = useState<Grupo | null>(null);
  const [selecionadoId, setSelecionadoId] = useState(0);
  const [carregando, setCarregando] = useState(true);
  const [erroLista, setErroLista] = useState("");
  const [revisao, setRevisao] = useState<Revisao | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [avisoAcao, setAvisoAcao] = useState<{ dono: string; texto: string } | null>(null);
  const [sucesso, setSucesso] = useState<{ dono: string; texto: string } | null>(null);
  const [revalidar, setRevalidar] = useState<{ dono: string; atualizacao: number } | null>(null);
  const [arquivos, setArquivos] = useState<{ chave: string; itens: ArquivoFornecedor[] } | null>(null);
  const [erroArquivos, setErroArquivos] = useState("");
  const [carregandoArquivos, setCarregandoArquivos] = useState(false);
  const [atualizacaoArquivos, setAtualizacaoArquivos] = useState(0);
  const [baixando, setBaixando] = useState<number | null>(null);
  const paginaChave = `${dono}:${visaoAtual}:${deslocamento}:${atualizacao}`;
  const grupoAtual = grupo?.chave === paginaChave ? grupo : null;
  const ordens = grupoAtual?.ordens.itens ?? [];
  const contratos = grupoAtual?.contratos.itens ?? [];
  const ordem = visaoAtual === "ordens" ? ordens.find((item) => item.id === selecionadoId) ?? ordens[0] : undefined;
  const contrato = visaoAtual === "contratos" ? contratos.find((item) => item.id === selecionadoId) ?? contratos[0] : undefined;
  const item = ordem ?? contrato;
  const selecaoChave = `${dono}:${visaoAtual}:${item?.id ?? 0}`;
  const arquivosChave = `${paginaChave}:${selecaoChave}:${atualizacaoArquivos}`;
  const precisaAtualizar = revalidar?.dono === dono && revalidar.atualizacao === atualizacao;
  const bloquear = carregando || enviando || !grupoAtual || precisaAtualizar;
  const modalAtual = revisao?.chave === selecaoChave && revisao.dono === dono && grupoAtual && !precisaAtualizar ? revisao : null;
  const arquivosAtuais = arquivos?.chave === arquivosChave ? arquivos.itens : [];
  const parametrosEmpresa = perfil === "cliente" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };
  const contexto = useRef({ paginaChave, selecaoChave, arquivosChave, dono });
  contexto.current = { paginaChave, selecaoChave, arquivosChave, dono };
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
    setVisao("ordens"); setDeslocamento(0); setSelecionadoId(0); setRevisao(null);
    envio.current?.abort(); download.current?.abort();
  }, [empresaId, perfil]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setCarregando(true); setErroLista(""); setRevisao(null);
    if (!empresaId) {
      setErroLista(`Entre como ${perfil} para consultar suas ordens de serviço.`); setCarregando(false);
      return () => { vigente = false; controlador.abort(); };
    }
    async function carregar() {
      try {
        const config = { params: { ...parametrosEmpresa, deslocamento: visaoAtual === "ordens" ? deslocamento : 0, limite: LIMITE }, signal: controlador.signal, timeout: 20_000 };
        const [resposta, candidatas] = await Promise.all([
          api.get<PaginaContratacoes<OrdemPortal>>(`${base}/ordens-servico`, config),
          perfil === "cliente" ? api.get<PaginaContratacoes<ContratacaoPortal>>("/portal-cliente/contratacoes-para-ordem", {
            ...config, params: { empresa_cliente_id: empresaId, deslocamento: visaoAtual === "contratos" ? deslocamento : 0, limite: LIMITE },
          }) : Promise.resolve({ data: PAGINA_VAZIA as PaginaContratacoes<ContratacaoPortal> }),
        ]);
        if (!vigente || contexto.current.paginaChave !== paginaChave) return;
        const total = visaoAtual === "contratos" ? candidatas.data.total : resposta.data.total;
        if (total > 0 && deslocamento >= total) { setDeslocamento(Math.floor((total - 1) / LIMITE) * LIMITE); return; }
        if (total === 0 && deslocamento > 0) { setDeslocamento(0); return; }
        const proprias = resposta.data.itens.filter((os) => (perfil === "cliente" ? os.empresa_cliente_id : os.empresa_fornecedora_id) === empresaId);
        const aptas = candidatas.data.itens.filter((c) => c.empresa_cliente_id === empresaId && c.status === "ativa");
        setGrupo({ chave: paginaChave, ordens: { ...resposta.data, itens: proprias }, contratos: { ...candidatas.data, itens: aptas } });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.paginaChave === paginaChave) setErroLista(mensagemErroOrdem(erro));
      } finally {
        if (vigente && contexto.current.paginaChave === paginaChave) setCarregando(false);
      }
    }
    void carregar();
    return () => { vigente = false; controlador.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, empresaId, perfil, visaoAtual, deslocamento, paginaChave]);

  useEffect(() => {
    setRevisao(null); setErroArquivos(""); setBaixando(null); download.current?.abort();
  }, [selecaoChave]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setErroArquivos(""); setCarregandoArquivos(Boolean(ordem));
    if (!ordem) return () => { vigente = false; controlador.abort(); };
    async function carregarArquivos() {
      try {
        const { data } = await api.get<ArquivoFornecedor[]>(`${base}/ordens-servico/${ordem!.id}/arquivos`, {
          params: parametrosEmpresa, signal: controlador.signal, timeout: 20_000,
        });
        if (vigente && contexto.current.arquivosChave === arquivosChave) setArquivos({ chave: arquivosChave, itens: data.filter((a) => a.ativo && a.solicitacao_id === ordem!.solicitacao_id) });
      } catch (erro) {
        if (vigente && !controlador.signal.aborted && contexto.current.arquivosChave === arquivosChave) setErroArquivos(mensagemErroOrdem(erro));
      } finally {
        if (vigente && contexto.current.arquivosChave === arquivosChave) setCarregandoArquivos(false);
      }
    }
    void carregarArquivos();
    return () => { vigente = false; controlador.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base, perfil, empresaId, ordem?.id, arquivosChave]);

  useEffect(() => {
    const elemento = dialogo.current;
    if (!elemento) return;
    if (modalAtual && !elemento.open) elemento.showModal();
    if (!modalAtual && elemento.open) elemento.close();
  }, [modalAtual]);

  function mudarVisao(nova: Visao) {
    if (trava.current) return;
    setVisao(nova); setDeslocamento(0); setSelecionadoId(0); setRevisao(null);
  }

  function revisar(acao: AcaoOrdem) {
    if (bloquear || trava.current) return;
    setAvisoAcao(null); setSucesso(null);
    if (acao === "gerar" && contrato && perfil === "cliente") setRevisao({ chave: selecaoChave, dono, acao, contrato });
    if (acao !== "gerar" && ordem && perfil === "fornecedor" && ordem.contratacao_status === "ativa"
        && ordem.status === (acao === "iniciar" ? "aberta" : "em_execucao")) setRevisao({ chave: selecaoChave, dono, acao, ordem });
  }

  async function confirmar() {
    if (!modalAtual || bloquear || trava.current) return;
    const confirmado = modalAtual;
    const controlador = new AbortController();
    envio.current = controlador; trava.current = true; setEnviando(true); setAvisoAcao(null);
    try {
      const url = confirmado.acao === "gerar" ? `/portal-cliente/contratacoes/${confirmado.contrato.id}/ordem-servico`
        : `/portal-fornecedor/ordens-servico/${confirmado.ordem.id}/${confirmado.acao}`;
      const dados = confirmado.acao === "gerar" ? { empresa_cliente_id: empresaId } : { empresa_fornecedora_id: empresaId };
      const { data } = await api.post<OrdemResposta>(url, dados, { signal: controlador.signal, timeout: 30_000 });
      if (!montada.current || controlador.signal.aborted || contexto.current.dono !== confirmado.dono || contexto.current.selecaoChave !== confirmado.chave) return;
      const origem = confirmado.acao === "gerar" ? confirmado.contrato : confirmado.ordem;
      const statusEsperado = confirmado.acao === "gerar" ? "aberta" : confirmado.acao === "iniciar" ? "em_execucao" : "concluida";
      if (data.solicitacao_id !== origem.solicitacao_id || data.empresa_cliente_id !== origem.empresa_cliente_id
          || data.empresa_fornecedora_id !== origem.empresa_fornecedora_id || data.status !== statusEsperado
          || (confirmado.acao === "gerar" ? data.contratacao_id !== confirmado.contrato.id : data.id !== confirmado.ordem.id)) throw new Error("Resposta da ordem divergente.");
      setSucesso({ dono, texto: confirmado.acao === "gerar" ? `Ordem de serviço #${data.id} gerada para a contratação #${data.contratacao_id}. O fornecedor já pode iniciar o serviço.`
        : confirmado.acao === "iniciar" ? `Ordem de serviço #${data.id} iniciada. O cliente já pode acompanhar a execução.` : `Ordem de serviço #${data.id} concluída. O cliente já pode consultar a conclusão.` });
      setRevisao(null); setVisao("ordens"); setSelecionadoId(data.id);
      if (confirmado.acao === "gerar") setDeslocamento(0);
      setAtualizacao((valor) => valor + 1);
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.dono === confirmado.dono && contexto.current.selecaoChave === confirmado.chave) {
        const status = typeof erro === "object" && erro !== null && "response" in erro ? (erro as { response?: { status?: number } }).response?.status : undefined;
        const incerta = !status || status >= 500;
        setAvisoAcao({ dono, texto: incerta ? "A operação não pôde ser confirmada. Clique em Atualizar e confira a situação da ordem antes de tentar novamente." : mensagemErroOrdem(erro) });
        if (incerta) setRevalidar({ dono, atualizacao });
        setRevisao(null);
      }
    } finally {
      if (envio.current === controlador) envio.current = null;
      trava.current = false;
      if (montada.current) setEnviando(false);
    }
  }

  async function baixar(arquivo: ArquivoFornecedor) {
    if (!ordem || baixando !== null || download.current) return;
    const controlador = new AbortController();
    const chave = arquivosChave;
    download.current = controlador; setBaixando(arquivo.id); setErroArquivos("");
    try {
      const { data } = await api.get<Blob>(`${base}/ordens-servico/${ordem.id}/arquivos/${arquivo.id}/download`, {
        params: parametrosEmpresa, signal: controlador.signal, responseType: "blob", timeout: 60_000,
      });
      if (!montada.current || controlador.signal.aborted || contexto.current.arquivosChave !== chave) return;
      const url = URL.createObjectURL(data); const link = document.createElement("a");
      try { link.href = url; link.download = arquivo.nome_original.replace(/[\\/]/g, "_"); document.body.appendChild(link); link.click(); }
      finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
    } catch (erro) {
      if (montada.current && !controlador.signal.aborted && contexto.current.arquivosChave === chave) setErroArquivos(mensagemErroOrdem(erro));
    } finally {
      if (download.current === controlador) download.current = null;
      if (montada.current && contexto.current.arquivosChave === chave) setBaixando(null);
    }
  }

  const pagina = visaoAtual === "contratos" ? grupoAtual?.contratos : grupoAtual?.ordens;
  const linhas = visaoAtual === "contratos" ? contratos : ordens;
  const total = pagina?.total ?? 0;
  const pedido = item?.solicitacao;
  const revisado = modalAtual ? modalAtual.acao === "gerar" ? modalAtual.contrato : modalAtual.ordem : null;
  return <main className="o26-page">
    <header className="o26-header"><div><p className="o26-eyebrow"><Wrench size={16} /> PORTAL DO {perfil === "cliente" ? "CLIENTE" : "FORNECEDOR"}</p>
      <h1>Ordens de Serviço</h1><p>{perfil === "cliente" ? "Gere a ordem da contratação e acompanhe a execução do serviço." : "Consulte suas ordens e registre o início e a conclusão do serviço."}</p></div>
      <button className="o26-button" disabled={enviando || carregando} onClick={() => { setAvisoAcao(null); setAtualizacao((v) => v + 1); }}><RefreshCw size={16} /> Atualizar</button></header>
    {sucesso?.dono === dono && <p className="o26-alert o26-success" role="status"><CheckCircle2 size={18} /> {sucesso.texto}</p>}
    {avisoAcao?.dono === dono && <p className="o26-alert o26-error" role="alert">{avisoAcao.texto}</p>}
    {erroLista && <p className="o26-alert o26-error" role="alert">{erroLista}</p>}
    <div className="o26-summary"><article><span>Ordens da sua empresa</span><strong>{grupoAtual ? grupoAtual.ordens.total : "—"}</strong><small>Inclui abertas, em execução, concluídas e canceladas</small></article>
      {perfil === "cliente" && <article><span>Contratações prontas para gerar ordem</span><strong>{grupoAtual ? grupoAtual.contratos.total : "—"}</strong><small>Ativas e ainda sem ordem de serviço</small></article>}</div>
    <nav className="o26-tabs" aria-label="Consultas de ordens de serviço">
      <button className={`o26-button ${visaoAtual === "ordens" ? "o26-tab-active" : ""}`} aria-pressed={visaoAtual === "ordens"} disabled={enviando} onClick={() => mudarVisao("ordens")}><Wrench size={16} /> Ordens de Serviço</button>
      {perfil === "cliente" && <button className={`o26-button ${visaoAtual === "contratos" ? "o26-tab-active" : ""}`} aria-pressed={visaoAtual === "contratos"} disabled={enviando} onClick={() => mudarVisao("contratos")}><ClipboardList size={16} /> Contratações para gerar ordem</button>}
      <Link className="o26-button" to={`/${perfil}/contratacoes`}><Handshake size={16} /> Contratações</Link>
    </nav>
    <section className="o26-panel" aria-busy={carregando}><div className="o26-section-head"><div><h2>{visaoAtual === "contratos" ? "Contratações disponíveis" : "Ordens da sua empresa"}</h2><p>{visaoAtual === "contratos" ? "Selecione a contratação e revise os dados antes de gerar a ordem." : "Selecione a ordem para consultar os dados, as datas e os arquivos técnicos."}</p></div></div>
      {carregando ? <div className="o26-empty" role="status">Carregando {visaoAtual === "contratos" ? "contratações" : "ordens"}…</div>
        : !erroLista && linhas.length === 0 ? <div className="o26-empty"><Wrench size={32} /><h3>{visaoAtual === "contratos" ? "Nenhuma contratação pronta para gerar ordem" : "Nenhuma ordem de serviço cadastrada"}</h3><p>{visaoAtual === "contratos" ? "Crie uma contratação ativa. Cada contratação pode ter uma única ordem de serviço." : perfil === "cliente" ? "Abra Contratações para gerar ordem e selecione uma contratação ativa." : "A ordem aparecerá aqui quando o cliente gerá-la a partir da contratação."}</p></div>
        : grupoAtual && <div className="o26-table-wrap"><table><thead><tr><th>Ordem / referência</th><th>{perfil === "cliente" ? "Fornecedor" : "Cliente"}</th><th>Valor total</th><th>Prazo</th><th>Situação</th><th><span className="o26-sr-only">Ações</span></th></tr></thead><tbody>
          {linhas.map((linha) => { const os = "contratacao_id" in linha; const ativa = linha.id === item?.id;
            return <tr key={linha.id} className={ativa ? "o26-selected" : ""}><td><strong>{os ? `OS #${linha.id}` : `Contratação #${linha.id}`}</strong><small>{`Solicitação #${linha.solicitacao_id} · ${os ? `Contratação #${linha.contratacao_id}` : `Cotação #${linha.cotacao_id}`}`}</small></td>
              <td>{perfil === "cliente" ? linha.fornecedor_razao_social : linha.cliente_razao_social}<small>{os ? linha.processo_nome : linha.solicitacao.processo_nome} · {os ? linha.material_nome : linha.solicitacao.material_nome}</small></td>
              <td className="o26-nowrap"><strong>{formatarValorCotacao(linha.valor_total)}</strong></td><td className="o26-nowrap">{linha.prazo_dias} dias</td>
              <td><span className={`o26-badge o26-status-${os && ["aberta", "em_execucao", "concluida", "cancelada"].includes(linha.status) ? linha.status : "ativa"}`}>{os ? rotuloOrdem(linha.status) : "Pronta para gerar"}</span></td>
              <td><button className="o26-button" disabled={enviando} onClick={() => setSelecionadoId(linha.id)} aria-pressed={ativa}>{ativa ? "Selecionada" : "Ver detalhes"}</button></td></tr>;
          })}</tbody></table></div>}
      {grupoAtual && total > 0 && <div className="o26-pagination"><span>{deslocamento + 1}–{Math.min(deslocamento + linhas.length, total)} de {total}</span><div>
        <button className="o26-button" disabled={enviando || carregando || deslocamento === 0} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => Math.max(0, v - LIMITE)); }}>Anterior</button>
        <button className="o26-button" disabled={enviando || carregando || deslocamento + LIMITE >= total} onClick={() => { setSelecionadoId(0); setDeslocamento((v) => v + LIMITE); }}>Próxima</button></div></div>}
    </section>
    {pedido && item && <div className="o26-columns">
      <section className="o26-panel o26-detail"><div className="o26-section-head"><h2>Solicitação #{pedido.id}</h2><ClipboardList size={21} /></div>
        <dl className="o26-fields"><div><dt>Cliente</dt><dd>{item.cliente_razao_social}</dd></div><div><dt>Fornecedor</dt><dd>{item.fornecedor_razao_social}</dd></div>
          <div><dt>Processo {ordem ? "da ordem" : ""}</dt><dd>{ordem?.processo_nome ?? pedido.processo_nome}</dd></div><div><dt>Material {ordem ? "da ordem" : ""}</dt><dd>{ordem?.material_nome ?? pedido.material_nome}</dd></div>
          <div><dt>Quantidade {ordem ? "da ordem" : ""}</dt><dd>{ordem?.quantidade ?? pedido.quantidade} unidades</dd></div><div><dt>Tolerância requerida</dt><dd>{formatarMedidaContrato(pedido.tolerancia_requerida_mm, 4)} mm</dd></div>
          <div className="o26-wide"><dt>Dimensões máximas X / Y / Z</dt><dd>{[pedido.dimensao_x_maxima_mm, pedido.dimensao_y_maxima_mm, pedido.dimensao_z_maxima_mm].map((v) => formatarMedidaContrato(v)).join(" × ")} mm</dd></div></dl>
        <h3>Observações da solicitação</h3><p className="o26-observacoes">{pedido.observacoes || "Sem observações."}</p>
        {ordem && <><div className="o26-section-head o26-files-head"><h3>Arquivos técnicos</h3><button className="o26-button" disabled={carregandoArquivos || baixando !== null} onClick={() => setAtualizacaoArquivos((v) => v + 1)}>Atualizar arquivos</button></div>
          {erroArquivos && <p className="o26-alert o26-error" role="alert">{erroArquivos}</p>}
          {carregandoArquivos ? <p role="status">Carregando arquivos…</p> : !erroArquivos && arquivosAtuais.length === 0 ? <p>Nenhum arquivo ativo vinculado a esta solicitação.</p> : <ul className="o26-files">{arquivosAtuais.map((a) => <li key={a.id}><FileText size={19} /><span><strong>{a.nome_original}</strong><small>{a.extensao.toUpperCase()} · {formatarTamanhoArquivo(a.tamanho_bytes)}</small></span><button className="o26-button" disabled={baixando !== null} onClick={() => void baixar(a)}><Download size={15} /> {baixando === a.id ? "Baixando…" : "Baixar"}</button></li>)}</ul>}
        </>}
      </section>
      <section className="o26-panel o26-detail"><div className="o26-section-head"><h2>{ordem ? `Ordem de serviço #${ordem.id}` : `Gerar ordem da contratação #${contrato!.id}`}</h2><Wrench size={21} /></div>
        <dl className="o26-fields"><div><dt>Valor total</dt><dd className="o26-value">{formatarValorCotacao(item.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{item.prazo_dias} dias</dd></div>
          <div><dt>Contratação</dt><dd>#{ordem?.contratacao_id ?? contrato!.id} · {rotuloContratacao(ordem?.contratacao_status ?? contrato!.status)}</dd></div><div><dt>Cotação</dt><dd>#{item.cotacao_id}</dd></div>
          {ordem && <><div><dt>Situação da ordem</dt><dd>{rotuloOrdem(ordem.status)}</dd></div><div><dt>Criada em</dt><dd>{formatarInstanteCotacao(instanteUtc(ordem.criada_em))}</dd></div>
            <div><dt>Iniciada em</dt><dd>{ordem.iniciada_em ? formatarInstanteCotacao(instanteUtc(ordem.iniciada_em)) : "Ainda não iniciada"}</dd></div><div><dt>Concluída em</dt><dd>{ordem.concluida_em ? formatarInstanteCotacao(instanteUtc(ordem.concluida_em)) : "Ainda não concluída"}</dd></div>
            {ordem.cancelada_em && <div><dt>Cancelada em</dt><dd>{formatarInstanteCotacao(instanteUtc(ordem.cancelada_em))}</dd></div>}</>}
        </dl><h3>{ordem ? "Observações da ordem" : "Observações da contratação"}</h3><p className="o26-observacoes">{item.observacoes || "Sem observações."}</p>
        {contrato && perfil === "cliente" && <div className="o26-operacao"><p>A ordem será aberta com o valor e o prazo contratados e a quantidade da solicitação.</p><button className="o26-button o26-primary" disabled={bloquear} onClick={() => revisar("gerar")}><ClipboardList size={16} /> Revisar ordem de serviço</button></div>}
        {ordem && perfil === "fornecedor" && <div className="o26-operacao">
          {ordem.contratacao_status !== "ativa" ? <p>A contratação está {rotuloContratacao(ordem.contratacao_status).toLowerCase()}. A execução da ordem está indisponível.</p>
            : ordem.status === "aberta" ? <><p>Registre o início quando começar a executar o serviço.</p><button className="o26-button o26-primary" disabled={bloquear} onClick={() => revisar("iniciar")}><Play size={16} /> Iniciar serviço</button></>
            : ordem.status === "em_execucao" ? <><p>Registre a conclusão após finalizar a execução do serviço.</p><button className="o26-button o26-primary" disabled={bloquear} onClick={() => revisar("concluir")}><CheckCircle2 size={16} /> Concluir serviço</button></>
            : <p>{ordem.status === "concluida" ? "O serviço foi concluído." : "Esta ordem não permite novas ações de execução."}</p>}
        </div>}
        {ordem && perfil === "cliente" && <p>A execução é atualizada pelo fornecedor responsável. Use Atualizar para conferir a situação mais recente.</p>}
      </section>
    </div>}
    <dialog ref={dialogo} className="o26-dialog" aria-labelledby="o26-dialog-title" onCancel={(e) => { if (trava.current) e.preventDefault(); else setRevisao(null); }} onClose={() => { if (!trava.current) setRevisao(null); }}>
      {modalAtual && revisado && <><div className="o26-section-head"><h2 id="o26-dialog-title">{TITULOS[modalAtual.acao]}</h2><button className="o26-button" aria-label="Fechar revisão" disabled={enviando} onClick={() => setRevisao(null)}><X size={18} /></button></div>
        <p>{modalAtual.acao === "gerar" ? "Confira os dados antes de gerar a ordem." : modalAtual.acao === "iniciar" ? "Confirme que o serviço será iniciado agora." : "Confirme que a execução deste serviço foi finalizada."}</p>
        <dl className="o26-fields"><div><dt>Solicitação</dt><dd>#{revisado.solicitacao_id}</dd></div><div><dt>{modalAtual.acao === "gerar" ? "Contratação" : "Ordem de serviço"}</dt><dd>#{revisado.id}</dd></div>
          <div className="o26-wide"><dt>Fornecedor</dt><dd>{revisado.fornecedor_razao_social}</dd></div><div><dt>Valor total</dt><dd>{formatarValorCotacao(revisado.valor_total)}</dd></div><div><dt>Prazo de execução</dt><dd>{revisado.prazo_dias} dias</dd></div></dl>
        <p className="o26-review-note">{modalAtual.acao === "gerar" ? "A ordem ficará aberta para o fornecedor iniciar o serviço." : modalAtual.acao === "iniciar" ? "A ordem ficará Em execução e terá a data de início registrada." : "A ordem ficará Concluída e terá a data de conclusão registrada."}</p>
        <div className="o26-dialog-actions"><button className="o26-button" disabled={enviando} onClick={() => setRevisao(null)}>Voltar</button><button className="o26-button o26-primary" disabled={enviando} onClick={() => void confirmar()}>{enviando ? "Registrando…" : TITULOS[modalAtual.acao]}</button></div>
      </>}
    </dialog>
  </main>;
}
