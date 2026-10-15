import { useSearchParams } from "react-router-dom";
import { identificador } from "../painel/painelPortal";
import { useEffect, useRef, useState } from "react";
import { api } from "../../services/api";
import { useAuth } from "../../auth/AuthContext";
import PrepararPdfAdmin, { erroPdf, type PreparacaoPdf } from "./PrepararPdfAdmin";
import "./Documentacao.css";

type Evento = { versao: number; acao: string; registro_interno: string; administrador_nome: string; criado_em: string; versao_pdf_preparada?: number | null };
type Arquivo = { id: number; solicitacao_id: number; nome_original: string; extensao: string; tamanho_bytes: number; sha256: string; versao: number; liberado: boolean; conteudo_valido: boolean; ativo: boolean; historico: Evento[]; preparacao_pdf_publicada_id?: number | null; versao_pdf_publicada?: number | null };
type Solicitacao = { id: number; cliente: string; processo: string; material: string; quantidade: number; status: string; arquivos_ativos: number; arquivos_disponiveis: number; arquivos: Arquivo[] };
type Pagina = { itens: Solicitacao[]; total: number; deslocamento: number; limite: number };
type Operacao = { arquivo: Arquivo; acao: "liberar" | "bloquear"; chave: string; preparacao?: PreparacaoPdf };
const BASE = "/administracao/documentacao-cotacao";

function mensagem(erro: unknown) {
  const falha = erro as { response?: { status?: number; data?: { detail?: unknown } } };
  const textos: Record<string, string> = {
    documentacao_alterada_atualize: "O arquivo ou sua liberação mudou. Atualize e revise novamente.",
    documentacao_ja_nesta_situacao: "O arquivo já está nessa situação. Atualize a lista.",
    arquivo_tecnico_sem_conteudo_valido: "O arquivo precisa estar ativo e ter conteúdo físico íntegro para ser liberado.",
    revisao_administrativa_obrigatoria: "Confirme a revisão do conteúdo antes de liberar o arquivo.",
    registro_interno_obrigatorio: "Informe um registro interno com pelo menos três caracteres.",
    chave_operacao_reutilizada: "A conferência desta operação mudou. Atualize e revise novamente.",
  };
  const detalhe = falha.response?.data?.detail;
  if (typeof detalhe === "string" && textos[detalhe]) return textos[detalhe];
  if (falha.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (falha.response?.status === 403) return "Esta revisão exige acesso administrativo.";
  return "Não foi possível confirmar a operação. Atualize a lista antes de continuar.";
}

export default function AdminDocumentacaoPage() {
  const { user } = useAuth(); const contexto = user?.role === "admin" ? String(user.usuario_id) : "";
  const vigente = useRef(contexto); vigente.current = contexto;
  const [parametrosUrl] = useSearchParams();
  const solicitacaoInicial = identificador(parametrosUrl.get("solicitacao"));
  const [filtro, setFiltro] = useState(solicitacaoInicial ? String(solicitacaoInicial) : ""); const [aplicado, setAplicado] = useState(solicitacaoInicial ? String(solicitacaoInicial) : "");
  const [deslocamento, setDeslocamento] = useState(0); const [revisao, setRevisao] = useState(0);
  const [pagina, setPagina] = useState<Pagina | null>(null); const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(""); const [aviso, setAviso] = useState("");
  const [operacao, setOperacao] = useState<Operacao | null>(null); const [registro, setRegistro] = useState("");
  const [revisado, setRevisado] = useState(false); const [ocupado, setOcupado] = useState(false);
  const [baixando, setBaixando] = useState<number | null>(null);
  const [preparando, setPreparando] = useState<Arquivo | null>(null);
  const [focoPreparacao, setFocoPreparacao] = useState(0);
  const areaPreparacao = useRef<HTMLDivElement | null>(null);
  const areaConferencia = useRef<HTMLElement | null>(null);
  const botaoPreparacao = useRef<HTMLButtonElement | null>(null);
  const montada = useRef(true); const trava = useRef(false); const controladorDownload = useRef<AbortController | null>(null);
  useEffect(() => { montada.current = true; return () => { montada.current = false; controladorDownload.current?.abort(); }; }, []);
  useEffect(() => {
    const controlador = new AbortController(); let vigente = true;
    setPagina(null); setCarregando(true); setErro("");
    if (!contexto) { setCarregando(false); return; }
    void api.get<Pagina>(BASE, { params: { ...(aplicado ? { solicitacao_id: aplicado } : {}), deslocamento, limite: 20 }, signal: controlador.signal, timeout: 20_000 })
      .then(({ data }) => { if (vigente) {
        if (data.total > 0 && deslocamento >= data.total) { setDeslocamento(Math.floor((data.total - 1) / 20) * 20); return; }
        setPagina(data);
      } }).catch(e => { if (vigente && !controlador.signal.aborted) setErro(mensagem(e)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controlador.abort(); };
  }, [aplicado, deslocamento, revisao, contexto]);

  useEffect(() => { setOperacao(null); setPreparando(null); }, [contexto]);
  useEffect(() => {
    const area = operacao ? areaConferencia.current : preparando ? areaPreparacao.current : null;
    if (!area) return;
    area.focus({ preventScroll: true });
    area.scrollIntoView({ block: "start", behavior: "auto" });
  }, [preparando?.id, operacao?.chave, focoPreparacao, contexto]);

  function abrirPreparacao(arquivo: Arquivo, botao: HTMLButtonElement) {
    if (ocupado) return;
    botaoPreparacao.current = botao;
    setErro(""); setAviso(""); setOperacao(null); setPreparando(arquivo);
    setFocoPreparacao(v => v + 1);
  }
  function fecharPreparacao() {
    if (ocupado) return;
    setPreparando(null); setOperacao(null);
    botaoPreparacao.current?.focus();
  }
  function abrir(arquivo: Arquivo, acao: "liberar" | "bloquear", preparacao?: PreparacaoPdf) {
    if (ocupado) return;
    if (!preparacao) setPreparando(null);
    setOperacao({ arquivo, acao, chave: crypto.randomUUID(), preparacao }); setRegistro(""); setRevisado(false); setErro(""); setAviso("");
  }
  async function salvar() {
    if (!operacao || trava.current || registro.trim().length < 3 || (operacao.acao === "liberar" && !revisado)) return;
    const op = operacao; const ctx = contexto; if (!ctx) return; trava.current = true; setOcupado(true); setErro("");
    try {
      await api.post<Arquivo>(`${BASE}/arquivos/${op.arquivo.id}/eventos`, { acao: op.acao, versao: op.arquivo.versao,
        sha256: op.arquivo.sha256, registro_interno: registro.trim(), revisado_sem_contatos: revisado, chave_operacao: op.chave,
        ...(op.preparacao ? { preparacao_pdf_id: op.preparacao.id } : {}) }, { timeout: 30_000 });
      if (montada.current && vigente.current === ctx) { setOperacao(null); setPreparando(null); setAviso(`Arquivo #${op.arquivo.id}${op.preparacao ? ` · cópia MEC versão ${op.preparacao.versao}` : ""} ${op.acao === "liberar" ? "liberado para cotação" : "bloqueado para novas consultas"}.`); setRevisao(v => v + 1); }
    } catch (e) { if (montada.current && vigente.current === ctx) setErro(op.preparacao ? erroPdf(e) : mensagem(e)); }
    finally { trava.current = false; if (montada.current && vigente.current === ctx) setOcupado(false); }
  }
  async function baixar(arquivo: Arquivo) {
    if (baixando !== null) return;
    const ctx = contexto; if (!ctx) return;
    const controlador = new AbortController(); controladorDownload.current = controlador; setBaixando(arquivo.id); setErro("");
    try {
      const { data } = await api.get<Blob>(`/arquivos-tecnicos/${arquivo.id}/download`, { responseType: "blob", signal: controlador.signal, timeout: 30_000 });
      if (!montada.current || controlador.signal.aborted || vigente.current !== ctx) return;
      const url = URL.createObjectURL(data); const ancora = document.createElement("a");
      ancora.href = url; ancora.download = arquivo.nome_original; document.body.appendChild(ancora); ancora.click(); ancora.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (e) { if (montada.current && !controlador.signal.aborted && vigente.current === ctx) setErro(mensagem(e)); }
    finally { if (montada.current && controladorDownload.current === controlador && vigente.current === ctx) setBaixando(null); }
  }
  if (!contexto) return <p role="alert">A revisão de arquivos exige acesso administrativo.</p>;
  return <div className="doc42-page">
    <header><div><p>ADMINISTRAÇÃO</p><h1>Arquivos para cotação</h1><p>Revise os documentos antes de disponibilizar as solicitações aos fornecedores.</p></div>
      <button disabled={ocupado || carregando} onClick={() => { setOperacao(null); setPreparando(null); setAviso(""); setRevisao(v => v + 1); }}>Atualizar</button></header>
    <div className="doc42-alert">A oportunidade exige pelo menos um arquivo ativo, íntegro e liberado. Cotações já registradas permanecem no histórico.</div>
    <form className="doc42-filtro" onSubmit={e => { e.preventDefault(); if (ocupado) return; const n = filtro.trim(); if (n && !/^[1-9]\d*$/.test(n)) { setErro("Informe um número de solicitação válido."); return; } setOperacao(null); setPreparando(null); setDeslocamento(0); setAplicado(n); setRevisao(v => v + 1); }}>
      <label>Solicitação #<input inputMode="numeric" value={filtro} disabled={ocupado} onChange={e => setFiltro(e.target.value)} placeholder="Todas" /></label>
      <button type="submit" disabled={ocupado}>Consultar</button></form>
    {erro && !operacao && <p className="doc42-alert doc42-erro" role="alert">{erro}</p>}{aviso && <p className="doc42-alert" role="status">{aviso}</p>}
    {carregando && <p role="status">Carregando documentação…</p>}
    {pagina && <><p>{pagina.total} solicitação(ões) · Página {Math.floor(deslocamento / 20) + 1}</p>
      {!pagina.itens.length && <p className="doc42-alert">Nenhuma solicitação encontrada.</p>}
      {pagina.itens.map(s => <section className="doc42-card" key={s.id}><h2>Solicitação #{s.id} · {s.cliente}</h2>
        <p>{s.processo} · {s.material} · {s.quantidade} unidades · {s.status}</p>
        <p><strong>{s.arquivos_disponiveis} arquivo(s) disponível(is)</strong> de {s.arquivos_ativos} ativo(s)</p>
        {!s.arquivos.length && <p className="doc42-alert">Aguardando envio de arquivo técnico pelo cliente.</p>}
        {s.arquivos.map(a => <article className="doc42-arquivo" key={a.id}>
          <div><h3>{a.nome_original}</h3><p>Arquivo #{a.id} · {a.tamanho_bytes.toLocaleString("pt-BR")} bytes · {a.liberado ? "Liberado para cotação" : !a.ativo ? "Desvinculado pelo cliente" : !a.conteudo_valido ? "Conteúdo físico indisponível ou divergente" : "Aguardando revisão e liberação"}</p></div>
          {a.versao_pdf_publicada && <p>Cópia MEC versão {a.versao_pdf_publicada}{a.liberado ? " disponível para o fornecedor" : " indisponível; confira o arquivo e a liberação"}.</p>}
          <div className="doc42-acoes"><button disabled={!a.ativo || !a.conteudo_valido || baixando !== null} onClick={() => void baixar(a)}>{baixando === a.id ? "Baixando…" : "Baixar para revisar"}</button>
            {a.ativo && a.conteudo_valido && <button disabled={ocupado} onClick={() => abrir(a, a.liberado ? "bloquear" : "liberar")}>{a.liberado ? "Bloquear liberação" : "Liberar para cotação"}</button>}</div>
          {a.ativo && a.conteudo_valido && a.extensao.toLowerCase() === ".pdf" && <div className="doc42-acoes"><button id={`doc42-preparar-${a.id}`} disabled={ocupado} aria-expanded={preparando?.id === a.id} aria-controls={`doc42-preparacao-${a.id}`} onClick={e => abrirPreparacao(a, e.currentTarget)}>Preparar PDF com nossa logo{preparando?.id === a.id && " · aberta"}</button></div>}
          {preparando?.id === a.id && <div id={`doc42-preparacao-${a.id}`} className="doc42-preparacao" ref={areaPreparacao} tabIndex={-1} role="region" aria-label={`Preparação do arquivo #${a.id}`}>
            <PrepararPdfAdmin key={`${contexto}:${a.id}`} arquivo={preparando} onFechar={fecharPreparacao} onLiberar={p => abrir(preparando, "liberar", p)} />
          </div>}
          {operacao?.arquivo.id === a.id && <section ref={areaConferencia} tabIndex={-1} className="doc42-confirmacao" aria-label="Conferência da documentação"><h2>{operacao.acao === "liberar" ? "Liberar arquivo para cotação" : "Bloquear a liberação do arquivo"}</h2>
      {erro && <p className="doc42-alert doc42-erro" role="alert">{erro}</p>}
      <p>Solicitação #{operacao.arquivo.solicitacao_id} · {operacao.arquivo.nome_original}</p>
      {operacao.acao === "liberar" && <p><strong>{operacao.preparacao ? `O fornecedor receberá a cópia MEC versão ${operacao.preparacao.versao}.` : "O fornecedor receberá o arquivo original revisado."}</strong></p>}
      {operacao.acao === "liberar" && <label className="doc42-check"><input type="checkbox" checked={revisado} disabled={ocupado} onChange={e => setRevisado(e.target.checked)} />Revisei o conteúdo e confirmei que não contém contatos nem identifica o cliente.</label>}
      <label>Registro interno da revisão<textarea value={registro} disabled={ocupado} minLength={3} maxLength={2000} onChange={e => setRegistro(e.target.value)} /></label>
      <div className="doc42-acoes"><button disabled={ocupado || registro.trim().length < 3 || (operacao.acao === "liberar" && !revisado)} onClick={() => void salvar()}>{ocupado ? "Registrando…" : "Confirmar registro"}</button><button disabled={ocupado} onClick={() => setOperacao(null)}>Voltar</button></div>
    </section>}
          {!!a.historico.length && <details><summary>Histórico da revisão</summary>{a.historico.map(h => <p key={h.versao}><strong>{h.acao === "liberar" ? "Liberação" : "Bloqueio"} · {h.administrador_nome}</strong> · {h.criado_em}{h.acao === "liberar" && <><br />{h.versao_pdf_preparada ? `Cópia MEC versão ${h.versao_pdf_preparada}` : "Original revisado"}</>}<br />{h.registro_interno}</p>)}</details>}
        </article>)}
      </section>)}
      <nav className="doc42-acoes" aria-label="Paginação"><button disabled={ocupado || deslocamento === 0} onClick={() => { setOperacao(null); setPreparando(null); setDeslocamento(v => Math.max(0, v - 20)); }}>Anterior</button><button disabled={ocupado || deslocamento + 20 >= pagina.total} onClick={() => { setOperacao(null); setPreparando(null); setDeslocamento(v => v + 20); }}>Próxima</button></nav></>}

  </div>;
}
