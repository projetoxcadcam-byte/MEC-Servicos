import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth, type UserRole } from "../../auth/AuthContext";
import { requisitarAcesso, type UsuarioServidor } from "../../services/acesso";
import "./LoginPage.css";

type AcessoTeste = { ativo: boolean; contas: UsuarioServidor[] };
const nomesPerfil: Record<UserRole, string> = { admin: "Administrador", cliente: "Cliente", fornecedor: "Fornecedor" };
function inicio(perfil: UserRole) { return `/${perfil}`; }

export default function LoginPage() {
  const { user, login, loginTesteLocal } = useAuth();
  const navigate = useNavigate(); const location = useLocation();
  const [email, setEmail] = useState(""); const [senha, setSenha] = useState("");
  const [erro, setErro] = useState(""); const [enviando, setEnviando] = useState(false);
  const [teste, setTeste] = useState<AcessoTeste | null>(null);
  const [carregandoModo, setCarregandoModo] = useState(true);
  const trava = useRef(false);

  useEffect(() => {
    let ativo = true;
    void requisitarAcesso<AcessoTeste>("/teste-local").then((dados) => {
      if (ativo) setTeste(dados.ativo && Array.isArray(dados.contas) ? dados : null);
    }).catch((falha: unknown) => {
      if (ativo) setErro(falha instanceof Error ? falha.message : "Não foi possível conferir o acesso local.");
    }).finally(() => { if (ativo) setCarregandoModo(false); });
    return () => { ativo = false; };
  }, []);

  if (user) return <Navigate to={user.deve_alterar_senha ? "/conta" : inicio(user.role)} replace />;

  function abrirPortal(usuario: UsuarioServidor) {
    const pedido: unknown = location.state?.from?.pathname;
    const home = inicio(usuario.role);
    const destino = typeof pedido === "string" && (pedido === home || pedido.startsWith(home + "/")) ? pedido : home;
    navigate(usuario.deve_alterar_senha ? "/conta" : destino, { replace: true });
  }

  async function entrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault(); if (trava.current) return;
    trava.current = true; setEnviando(true); setErro("");
    try { const usuario = await login(email.trim(), senha); setSenha(""); abrirPortal(usuario); }
    catch (falha) { setErro(falha instanceof Error ? falha.message : "Não foi possível entrar. Tente novamente."); }
    finally { trava.current = false; setEnviando(false); }
  }

  async function entrarTeste(usuarioId: number) {
    if (trava.current) return;
    trava.current = true; setEnviando(true); setErro("");
    try { abrirPortal(await loginTesteLocal(usuarioId)); }
    catch (falha) { setErro(falha instanceof Error ? falha.message : "Não foi possível abrir o perfil de teste."); }
    finally { trava.current = false; setEnviando(false); }
  }

  return <main className="login-page"><section className="login-card" aria-label="Acesso à plataforma MEC Serviços">
    <div className="login-brand"><div className="login-logo">M</div><div><strong>MEC</strong><span>Serviços</span></div></div>
    <div className="login-heading"><span>{teste ? "MODO DE TESTE LOCAL" : "ACESSO À PLATAFORMA"}</span><h1>{teste ? "Escolher perfil" : "Entrar"}</h1><p>{teste ? "Abra uma conta para testar o fluxo de atendimento." : "Use a conta fornecida pela administração."}</p></div>
    {carregandoModo ? <p role="status">Conferindo acesso…</p> : teste ? <div className="login-form" aria-busy={enviando}>
      {teste.contas.map((conta) => <button key={conta.usuario_id} type="button" className="login-button" disabled={enviando} onClick={() => void entrarTeste(conta.usuario_id)} style={{ height: "auto", minHeight: 56, padding: "12px 16px", whiteSpace: "normal" }}>
        {nomesPerfil[conta.role]} · {conta.nome}{conta.empresa_id !== null ? ` · Empresa #${conta.empresa_id}` : ""}
      </button>)}
      {teste.contas.length === 0 && <p>Nenhuma conta ativa disponível para teste.</p>}
      {erro && <div className="login-error" role="alert">{erro}</div>}
    </div> : <form onSubmit={entrar} className="login-form" aria-busy={enviando}>
      <label>E-mail<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" maxLength={254} required disabled={enviando} placeholder="seu@email.com" /></label>
      <label>Senha<input type="password" value={senha} onChange={(e) => setSenha(e.target.value)} autoComplete="current-password" maxLength={128} required disabled={enviando} placeholder="Digite sua senha" /></label>
      {erro && <div className="login-error" role="alert">{erro}</div>}
      <button type="submit" className="login-button" disabled={enviando}>{enviando ? "Conferindo acesso…" : "Entrar"}</button>
    </form>}
    <p>{teste ? "Use Trocar perfil no portal para alternar entre as contas durante o teste." : "Solicite à administração o cadastro ou a recuperação do seu acesso."}</p>
  </section></main>;
}
