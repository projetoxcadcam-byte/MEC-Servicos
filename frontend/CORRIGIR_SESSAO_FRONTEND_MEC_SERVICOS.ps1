$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " MEC-Servicos - CORRECAO DE SESSAO FRONTEND" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".\\package.json")) {
    throw "Execute este script dentro de C:\\Users\\Omega\\Desktop\\MEC-Servicos\\frontend"
}

$authDir = ".\\src\\auth"
New-Item -ItemType Directory -Force $authDir | Out-Null

$authPath = ".\\src\\auth\\AuthContext.tsx"
$protectedPath = ".\\src\\auth\\ProtectedRoute.tsx"

if (Test-Path $authPath) {
    $backup = ".\\src\\auth\\AuthContext.tsx.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $authPath $backup
    Write-Host "Backup criado: $backup" -ForegroundColor DarkGray
}

if (Test-Path $protectedPath) {
    $backup = ".\\src\\auth\\ProtectedRoute.tsx.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $protectedPath $backup
    Write-Host "Backup criado: $backup" -ForegroundColor DarkGray
}

Set-Content -Path $authPath -Encoding UTF8 -Value @'
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
  // Remove a sessão antiga que usava localStorage.
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

'@

Set-Content -Path $protectedPath -Encoding UTF8 -Value @'
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, type UserRole } from "./AuthContext";
import type { ReactNode } from "react";

interface ProtectedRouteProps {
  role: UserRole;
  children: ReactNode;
}

function homeForRole(role: UserRole) {
  switch (role) {
    case "admin":
      return "/admin";
    case "fornecedor":
      return "/fornecedor";
    case "cliente":
      return "/cliente";
  }
}

export default function ProtectedRoute({
  role,
  children,
}: ProtectedRouteProps) {
  const { user, isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated || !user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname }}
      />
    );
  }

  if (user.role !== role) {
    return <Navigate to={homeForRole(user.role)} replace />;
  }

  return <>{children}</>;
}

'@

Write-Host ""
Write-Host "CORRECAO APLICADA COM SUCESSO." -ForegroundColor Green
Write-Host "A autenticacao agora usa sessionStorage." -ForegroundColor Green
Write-Host "A chave antiga do localStorage sera removida automaticamente." -ForegroundColor Green
Write-Host ""
Write-Host "Proximos comandos:" -ForegroundColor Yellow
Write-Host "npm run build" -ForegroundColor White
Write-Host "npm run dev" -ForegroundColor White
Write-Host ""
