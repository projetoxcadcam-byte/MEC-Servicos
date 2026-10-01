import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type UserRole = "cliente" | "fornecedor" | "admin";

export interface AuthUser {
  id: number;
  nome: string;
  email: string;
  role: UserRole;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email: string, senha: string) => AuthUser | null;
  logout: () => void;
}

const SESSION_KEY = "mec-servicos-auth";
const LEGACY_STORAGE_KEY = "mec-servicos-auth";

const USUARIOS: Array<AuthUser & { senha: string }> = [
  {
    id: 1,
    nome: "Administrador",
    email: "admin@mec-servicos.local",
    senha: "admin123",
    role: "admin",
  },
  {
    id: 2,
    nome: "Cliente Demo",
    email: "cliente@mec-servicos.local",
    senha: "cliente123",
    role: "cliente",
  },
  {
    id: 3,
    nome: "Fornecedor Demo",
    email: "fornecedor@mec-servicos.local",
    senha: "fornecedor123",
    role: "fornecedor",
  },
];

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function carregarSessao(): AuthUser | null {
  // Remove a sessÃ£o antiga que usava localStorage.
  localStorage.removeItem(LEGACY_STORAGE_KEY);

  const salvo = sessionStorage.getItem(SESSION_KEY);

  if (!salvo) {
    return null;
  }

  try {
    return JSON.parse(salvo) as AuthUser;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(carregarSessao);

  useEffect(() => {
    if (user) {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
    } else {
      sessionStorage.removeItem(SESSION_KEY);
    }
  }, [user]);

  const login = (email: string, senha: string): AuthUser | null => {
    const usuario = USUARIOS.find(
      (item) =>
        item.email.toLowerCase() === email.trim().toLowerCase() &&
        item.senha === senha,
    );

    if (!usuario) {
      return null;
    }

    const { senha: _senha, ...usuarioSeguro } = usuario;

    setUser(usuarioSeguro);
    return usuarioSeguro;
  };

  const logout = () => {
    sessionStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
    setUser(null);
  };

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      login,
      logout,
    }),
    [user],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider.");
  }

  return context;
}
