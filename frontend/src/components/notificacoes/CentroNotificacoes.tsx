import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, CheckCheck, RefreshCw, X } from "lucide-react";
import type { AuthUser } from "../../auth/AuthContext";
import { api } from "../../services/api";
import "./Notificacoes.css";

type Aviso = { id: number; assunto: string; mensagem: string; destino: string;
  perfil_origem: "admin" | "cliente" | "fornecedor"; criada_em: string; lida_em: string | null };
type Resumo = { usuario_id: number; perfil: AuthUser["role"]; empresa_id: number | null; nao_lidas: number; ultimo_id: number };
type Pagina = Resumo & { itens: Aviso[]; proximo_antes_id: number | null };
const ORIGENS = { admin: "Administração", cliente: "Cliente", fornecedor: "Fornecedor" };
const ACESSO_ALTERADO = "O acesso mudou em outra aba. Atualize a página ou entre novamente para ver as notificações deste perfil.";

export function destinoPermitido(destino: string, perfil: AuthUser["role"]): boolean {
  const raiz = perfil === "admin" ? "admin" : perfil;
  return new RegExp(`^/${raiz}/(?:solicitacoes|cotacoes|ordens-servico|producao|entregas|pagamentos|arquivos-tecnicos|avaliacoes)(?:\\?(?:ordem|contratacao|solicitacao)=[1-9]\\d*)?$`).test(destino);
}

function dataAviso(valor: string) {
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? "Data indisponível" : data.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export default function CentroNotificacoes({ usuario }: { usuario: AuthUser }) {
  const [aberto, setAberto] = useState(false);
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [pagina, setPagina] = useState<Pagina | null>(null);
  const [antes, setAntes] = useState<number | null>(null);
  const [anteriores, setAnteriores] = useState<Array<number | null>>([]);
  const [somenteNovas, setSomenteNovas] = useState(false);
  const [revisao, setRevisao] = useState(0);
  const [carregando, setCarregando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState("");
  const [falhaResumo, setFalhaResumo] = useState(false);
  const [acessoAlterado, setAcessoAlterado] = useState(false);
  const elemento = useRef<HTMLDivElement | null>(null);
  const sino = useRef<HTMLButtonElement | null>(null);
  const fechar = useRef<HTMLButtonElement | null>(null);
  const montado = useRef(true);
  const trava = useRef(false);
  const leitura = useRef<AbortController | null>(null);
  const controladorResumo = useRef<AbortController | null>(null);
  const versaoResumo = useRef(0);
  const atual = useRef({ aberto, antes, ultimo: 0 });
  atual.current = { aberto, antes, ultimo: resumo?.ultimo_id ?? 0 };
  const headers = { "X-MEC-NOTIFICACOES-CONTEXTO": `${usuario.usuario_id}:${usuario.role}:${usuario.empresa_id ?? 0}` };
  const contextoIgual = (dados: Resumo) => dados.usuario_id === usuario.usuario_id && dados.perfil === usuario.role && dados.empresa_id === usuario.empresa_id;
  function mudouAcesso(falha: unknown) {
    const detalhe = (falha as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    if (detalhe !== "contexto_notificacoes_alterado") return false;
    setAcessoAlterado(true); setResumo(null); setPagina(null); setErro(ACESSO_ALTERADO); return true;
  }

  const atualizarResumo = useCallback(async () => {
    controladorResumo.current?.abort();
    const controlador = new AbortController(); controladorResumo.current = controlador;
    const versao = ++versaoResumo.current;
    try {
      const { data } = await api.get<Resumo>("/notificacoes/resumo", { headers, signal: controlador.signal, timeout: 12_000 });
      if (!montado.current || versao !== versaoResumo.current || controlador.signal.aborted) return;
      if (!contextoIgual(data)) { setAcessoAlterado(true); setResumo(null); setPagina(null); setErro(ACESSO_ALTERADO); return; }
      const mudou = data.ultimo_id !== atual.current.ultimo;
      setResumo(data); setFalhaResumo(false); setAcessoAlterado(false);
      if (mudou && atual.current.aberto && atual.current.antes === null) setRevisao(v => v + 1);
    } catch (falha) {
      if (montado.current && versao === versaoResumo.current && !controlador.signal.aborted && !mudouAcesso(falha)) setFalhaResumo(true);
    }
  }, [usuario.usuario_id, usuario.role, usuario.empresa_id]);

  useEffect(() => {
    montado.current = true;
    let vigente = true;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    const agendar = () => { if (temporizador) clearTimeout(temporizador); if (vigente) temporizador = setTimeout(() => { void consultar(); }, 15_000); };
    const consultar = async () => {
      if (temporizador) clearTimeout(temporizador);
      if (document.visibilityState !== "hidden" && navigator.onLine !== false) await atualizarResumo();
      if (vigente && montado.current) agendar();
    };
    const retomar = () => { if (document.visibilityState !== "hidden") void consultar(); };
    void consultar();
    document.addEventListener("visibilitychange", retomar); window.addEventListener("online", retomar); window.addEventListener("focus", retomar);
    return () => {
      vigente = false; montado.current = false; ++versaoResumo.current;
      if (temporizador) clearTimeout(temporizador);
      controladorResumo.current?.abort(); leitura.current?.abort();
      document.removeEventListener("visibilitychange", retomar); window.removeEventListener("online", retomar); window.removeEventListener("focus", retomar);
    };
  }, [atualizarResumo]);

  useEffect(() => {
    if (!aberto) return;
    const controlador = new AbortController(); let vigente = true;
    setCarregando(true); setPagina(null); setErro("");
    void api.get<Pagina>("/notificacoes", { params: { ...(antes ? { antes_id: antes } : {}), limite: 20, somente_nao_lidas: somenteNovas },
      headers, signal: controlador.signal, timeout: 15_000 }).then(({ data }) => {
        if (vigente && montado.current) {
          if (!contextoIgual(data)) { setAcessoAlterado(true); setResumo(null); setPagina(null); setErro(ACESSO_ALTERADO); return; }
          setPagina(data); setResumo(data); setFalhaResumo(false); setAcessoAlterado(false);
        }
      }).catch(falha => { if (vigente && !controlador.signal.aborted && !mudouAcesso(falha)) setErro("Não foi possível carregar as notificações. Use Atualizar."); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controlador.abort(); };
  }, [aberto, antes, somenteNovas, revisao]);

  function encerrar() { setAberto(false); sino.current?.focus(); }
  useEffect(() => {
    if (!aberto) return;
    fechar.current?.focus();
    const fora = (e: PointerEvent) => { if (!elemento.current?.contains(e.target as Node)) setAberto(false); };
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); encerrar(); } };
    document.addEventListener("pointerdown", fora); document.addEventListener("keydown", tecla);
    return () => { document.removeEventListener("pointerdown", fora); document.removeEventListener("keydown", tecla); };
  }, [aberto]);

  async function marcar(aviso?: Aviso, navegar = false) {
    if (trava.current || acessoAlterado || (!aviso && !pagina)) return;
    if (navegar && aviso && !destinoPermitido(aviso.destino, usuario.role)) { setErro("O endereço desta notificação está indisponível."); return; }
    trava.current = true; setOcupado(true); setErro("");
    controladorResumo.current?.abort(); ++versaoResumo.current;
    const controlador = new AbortController(); leitura.current = controlador;
    try {
      if (aviso) await api.post<Aviso>(`/notificacoes/${aviso.id}/ler`, {}, { headers, signal: controlador.signal, timeout: 15_000 });
      else await api.post<Resumo>("/notificacoes/ler-ate", { ate_id: pagina!.ultimo_id }, { headers, signal: controlador.signal, timeout: 15_000 });
      if (!montado.current || controlador.signal.aborted) return;
      if (navegar && aviso) { window.location.assign(aviso.destino); return; }
      setRevisao(v => v + 1); void atualizarResumo();
    } catch (falha) {
      if (montado.current && !controlador.signal.aborted && !mudouAcesso(falha)) setErro("Não foi possível registrar a leitura. Tente novamente.");
    } finally { trava.current = false; if (montado.current) setOcupado(false); }
  }

  return <div className="mec-notificacoes" ref={elemento}>
    <button ref={sino} type="button" className="mec-not-sino" aria-label={acessoAlterado ? "Notificações: acesso alterado" : falhaResumo ? "Notificações: conexão indisponível" : `Notificações: ${resumo?.nao_lidas ?? 0} não lidas`}
      aria-expanded={aberto} aria-controls="mec-painel-notificacoes" onClick={() => { setAberto(v => !v); if (!aberto) { setAntes(null); setAnteriores([]); void atualizarResumo(); } }}>
      <Bell size={20} aria-hidden="true" /><span>Notificações</span>
      {Boolean(resumo?.nao_lidas) && <span className="mec-not-contador" aria-hidden="true">{resumo!.nao_lidas > 99 ? "99+" : resumo!.nao_lidas}</span>}
      {(falhaResumo || acessoAlterado) && <span className="mec-not-desconectado" aria-hidden="true">!</span>}
    </button>
    <span className="mec-not-sr" role="status" aria-live="polite">{resumo ? `${resumo.nao_lidas} notificações não lidas.` : ""}</span>
    {aberto && <section id="mec-painel-notificacoes" className="mec-not-painel" role="region" aria-label="Notificações do seu perfil">
      <header><div><h2>Notificações</h2><p>{resumo?.nao_lidas ?? 0} não lidas · {ORIGENS[usuario.role]}</p></div>
        <button ref={fechar} type="button" aria-label="Fechar notificações" onClick={encerrar}><X size={20} /></button></header>
      <div className="mec-not-acoes"><label><input type="checkbox" checked={somenteNovas} disabled={ocupado} onChange={e => { setSomenteNovas(e.target.checked); setAntes(null); setAnteriores([]); }} />Somente não lidas</label>
        <button type="button" disabled={carregando || ocupado} onClick={() => { setRevisao(v => v + 1); void atualizarResumo(); }}><RefreshCw size={15} />Atualizar</button>
        <button type="button" disabled={acessoAlterado || !pagina || ocupado || carregando || !pagina.nao_lidas} onClick={() => void marcar()}><CheckCheck size={15} />Marcar todas como lidas</button></div>
      {acessoAlterado && <p className="mec-not-erro" role="alert">{ACESSO_ALTERADO}</p>}
      {falhaResumo && <p className="mec-not-erro" role="alert">A conexão com as notificações está indisponível. Os avisos permanecem salvos.</p>}
      {erro && !acessoAlterado && <p className="mec-not-erro" role="alert">{erro}</p>}
      {carregando ? <p className="mec-not-vazio" role="status">Carregando notificações…</p> : pagina && <>
        {!pagina.itens.length ? <p className="mec-not-vazio">{somenteNovas ? "Nenhuma notificação não lida neste trecho." : "Nenhuma notificação por enquanto. Novas atualizações aparecerão aqui."}</p>
          : <ol className="mec-not-lista">{pagina.itens.map(aviso => <li key={aviso.id} className={aviso.lida_em ? "" : "mec-not-nova"}>
            <article><div className="mec-not-cabecalho"><strong>{aviso.assunto}</strong><span>{aviso.lida_em ? "Lida" : "Não lida"}</span></div>
              <p>{aviso.mensagem}</p><small>{ORIGENS[aviso.perfil_origem]} · <time dateTime={aviso.criada_em}>{dataAviso(aviso.criada_em)}</time></small>
              <div className="mec-not-item-acoes">{destinoPermitido(aviso.destino, usuario.role) && <a href={aviso.destino} aria-disabled={ocupado}
                onClick={e => { if (ocupado) { e.preventDefault(); return; } if (e.ctrlKey || e.metaKey) { void marcar(aviso); return; } e.preventDefault(); void marcar(aviso, true); }}>Abrir</a>}
                {!aviso.lida_em && <button type="button" disabled={ocupado} onClick={() => void marcar(aviso)}>Marcar como lida</button>}</div>
            </article></li>)}</ol>}
        {(anteriores.length > 0 || pagina.proximo_antes_id !== null) && <footer className="mec-not-paginacao">
          <button type="button" disabled={ocupado || !anteriores.length} onClick={() => { setAntes(anteriores.at(-1) ?? null); setAnteriores(v => v.slice(0, -1)); }}>Mais recentes</button>
          <button type="button" disabled={ocupado || pagina.proximo_antes_id === null} onClick={() => { setAnteriores(v => [...v, antes]); setAntes(pagina.proximo_antes_id); }}>Mais antigas</button></footer>}
      </>}
      <p className="mec-not-rodape">Atualização automática enquanto o sistema estiver aberto. Abrir um aviso registra sua leitura.</p>
    </section>}
  </div>;
}
