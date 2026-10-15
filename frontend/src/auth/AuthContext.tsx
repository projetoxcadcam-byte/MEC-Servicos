import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  definirCsrf, ErroAcesso, instalarTransporteAcesso, observarExpiracao, requisitarAcesso, validarSessao,
  type SessaoServidor, type UsuarioServidor,
} from "../services/acesso";

import CentroNotificacoes from "../components/notificacoes/CentroNotificacoes";

export type UserRole = "cliente" | "fornecedor" | "admin";
export type AuthUser = UsuarioServidor;
interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email: string, senha: string) => Promise<AuthUser>;
  loginTesteLocal: (usuarioId: number) => Promise<AuthUser>;
  logout: () => Promise<void>;
}
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [falha, setFalha] = useState("");
  const versao = useRef(0);
  const ocupado = useRef(false);
  const montado = useRef(true);

  useEffect(() => {
    montado.current = true;
    instalarTransporteAcesso();
    // Nenhum perfil ou empresa armazenado no navegador autoriza o acesso.
    localStorage.removeItem("mec-servicos-auth");
    sessionStorage.removeItem("mec-servicos-auth");
    const atual = ++versao.current;
    const parar = observarExpiracao(() => {
      ++versao.current; definirCsrf(""); setUser(null); setCarregando(false);
      setFalha("Sua sessão foi encerrada ou expirou. Entre novamente.");
    });
    void requisitarAcesso<SessaoServidor>("/sessao").then((valor) => {
      const dados = validarSessao(valor);
      if (!montado.current || versao.current !== atual) return;
      definirCsrf(dados.csrf); setUser(dados.usuario);
    }).catch((erro: unknown) => {
      if (!montado.current || versao.current !== atual) return;
      definirCsrf(""); setUser(null);
      if (!(erro instanceof ErroAcesso && erro.status === 401)) setFalha(erro instanceof Error ? erro.message : "Não foi possível conferir a sessão.");
    }).finally(() => { if (montado.current && versao.current === atual) setCarregando(false); });
    return () => { montado.current = false; ++versao.current; parar(); };
  }, []);

  const login = async (email: string, senha: string): Promise<AuthUser> => {
    if (ocupado.current) throw new Error("Aguarde a operação de acesso em andamento.");
    ocupado.current = true; const atual = ++versao.current; setFalha("");
    try {
      const dados = validarSessao(await requisitarAcesso<SessaoServidor>("/entrar", { email, senha }));
      if (!montado.current || versao.current !== atual) throw new Error("O contexto de acesso foi alterado. Entre novamente.");
      definirCsrf(dados.csrf); setUser(dados.usuario); return dados.usuario;
    } finally { ocupado.current = false; }
  };

  const loginTesteLocal = async (usuarioId: number): Promise<AuthUser> => {
    if (ocupado.current) throw new Error("Aguarde a operação de acesso em andamento.");
    ocupado.current = true; const atual = ++versao.current; setFalha("");
    try {
      const dados = validarSessao(await requisitarAcesso<SessaoServidor>("/teste-local/entrar", { usuario_id: usuarioId }, "POST", { "X-MEC-TESTE-LOCAL": "1" }));
      if (!montado.current || versao.current !== atual) throw new Error("O contexto de acesso foi alterado. Escolha o perfil novamente.");
      definirCsrf(dados.csrf); setUser(dados.usuario); return dados.usuario;
    } finally { ocupado.current = false; }
  };

  const logout = async () => {
    if (ocupado.current) return;
    ocupado.current = true; const atual = ++versao.current; setCarregando(true); setFalha("");
    try {
      await requisitarAcesso("/sair", {});
      if (montado.current && versao.current === atual) { definirCsrf(""); setUser(null); }
    } catch (erro) {
      if (montado.current && versao.current === atual) {
        if (erro instanceof ErroAcesso && erro.status === 401) { definirCsrf(""); setUser(null); }
        else setFalha("Não foi possível encerrar a sessão no servidor. Use Sair novamente quando a conexão voltar.");
      }
    } finally {
      ocupado.current = false;
      if (montado.current && versao.current === atual) setCarregando(false);
    }
  };
  const value = useMemo(() => ({ user, isAuthenticated: Boolean(user), login, loginTesteLocal, logout }), [user]);
  return <AuthContext.Provider value={value}>
    {user?.teste_local && <div role="status" style={{ padding: "12px 20px", background: "#15344b", color: "#eef7ff", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}><span>Modo de teste local · {user.nome}{user.empresa_id !== null ? ` · Empresa #${user.empresa_id}` : ""}</span><button type="button" onClick={() => void logout()} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #91b7d0", background: "#204861", color: "#fff", cursor: "pointer" }}>Trocar perfil</button></div>}
    {falha && <div role="alert" style={{ padding: "12px 20px", background: "#fff2dc", color: "#684411" }}>{falha}</div>}
    {user && !carregando && <div className="mec-acesso-topo">{!user.deve_alterar_senha && <CentroNotificacoes key={`${user.usuario_id}:${user.role}:${user.empresa_id}`} usuario={user} />}<a href="/conta">Minha conta</a></div>}
    {carregando ? <main style={{ padding: 32 }} role="status">Conferindo acesso ao servidor…</main> : children}
  </AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth deve ser usado dentro de AuthProvider.");
  return context;
}
