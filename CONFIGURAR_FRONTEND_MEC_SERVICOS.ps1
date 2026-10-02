$ErrorActionPreference = "Stop"

$root = Get-Location

$path = Join-Path $root "src\auth\AuthContext.tsx"
$directory = Split-Path $path -Parent
New-Item -ItemType Directory -Force $directory | Out-Null
Set-Content -Path $path -Value @'
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

const STORAGE_KEY = "mec-servicos-auth";

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const salvo = localStorage.getItem(STORAGE_KEY);

    if (!salvo) {
      return null;
    }

    try {
      return JSON.parse(salvo) as AuthUser;
    } catch {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(STORAGE_KEY);
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

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider.");
  }

  return context;
}

'@ -Encoding UTF8

$path = Join-Path $root "src\auth\ProtectedRoute.tsx"
$directory = Split-Path $path -Parent
New-Item -ItemType Directory -Force $directory | Out-Null
Set-Content -Path $path -Value @'
import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth, type UserRole } from "./AuthContext";

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

'@ -Encoding UTF8

$path = Join-Path $root "src\pages\auth\LoginPage.tsx"
$directory = Split-Path $path -Parent
New-Item -ItemType Directory -Force $directory | Out-Null
Set-Content -Path $path -Value @'
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth, type UserRole } from "../../auth/AuthContext";
import "./LoginPage.css";

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

export default function LoginPage() {
  const { user, isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");

  if (isAuthenticated && user) {
    return <Navigate to={homeForRole(user.role)} replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro("");

    const usuario = login(email, senha);

    if (!usuario) {
      setErro("E-mail ou senha inválidos.");
      return;
    }

    const destino = location.state?.from?.pathname;
    navigate(destino || homeForRole(usuario.role), { replace: true });
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-label="Acesso à plataforma MEC Serviços">
        <div className="login-brand">
          <div className="login-logo">M</div>
          <div>
            <strong>MEC</strong>
            <span>Serviços</span>
          </div>
        </div>

        <div className="login-heading">
          <span>ACESSO À PLATAFORMA</span>
          <h1>Entrar</h1>
          <p>Acesse o portal correspondente ao seu perfil.</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            E-mail
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="seu@email.com"
              autoComplete="email"
              required
            />
          </label>

          <label>
            Senha
            <input
              type="password"
              value={senha}
              onChange={(event) => setSenha(event.target.value)}
              placeholder="Digite sua senha"
              autoComplete="current-password"
              required
            />
          </label>

          {erro && <div className="login-error">{erro}</div>}

          <button type="submit" className="login-button">
            Entrar
          </button>
        </form>

        <div className="login-demo">
          <strong>Acessos de demonstração</strong>
          <span>Administrador: admin@mec-servicos.local / admin123</span>
          <span>Cliente: cliente@mec-servicos.local / cliente123</span>
          <span>Fornecedor: fornecedor@mec-servicos.local / fornecedor123</span>
        </div>
      </section>
    </main>
  );
}

'@ -Encoding UTF8

$path = Join-Path $root "src\pages\auth\LoginPage.css"
$directory = Split-Path $path -Parent
New-Item -ItemType Directory -Force $directory | Out-Null
Set-Content -Path $path -Value @'
 .login-page {
  min-height: 100vh;
  min-width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at 85% 10%, rgba(37, 99, 235, 0.16), transparent 34%),
    radial-gradient(circle at 10% 90%, rgba(59, 130, 246, 0.08), transparent 28%),
    #090d14;
}

.login-card {
  width: min(440px, 100%);
  padding: 36px;
  border: 1px solid #263244;
  border-radius: 18px;
  background: #111822;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 42px;
}

.login-logo {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
  background: #2563eb;
  color: #fff;
  font-size: 28px;
  font-weight: 800;
}

.login-brand strong,
.login-brand span {
  display: block;
}

.login-brand strong {
  color: #f8fafc;
  font-size: 22px;
  letter-spacing: 0.04em;
}

.login-brand span {
  margin-top: 3px;
  color: #7f8da3;
}

.login-heading > span {
  color: #3b82f6;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.login-heading h1 {
  margin: 8px 0;
  color: #f8fafc;
  font-size: 34px;
}

.login-heading p {
  margin: 0 0 28px;
  color: #8c9ab0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.login-form label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #cbd5e1;
  font-size: 14px;
  font-weight: 600;
}

.login-form input {
  box-sizing: border-box;
  width: 100%;
  padding: 13px 14px;
  border: 1px solid #2a3648;
  border-radius: 9px;
  outline: none;
  background: #0c121b;
  color: #f8fafc;
  font-size: 15px;
}

.login-form input::placeholder {
  color: #64748b;
}

.login-form input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.login-button {
  margin-top: 8px;
  padding: 13px 16px;
  border: 0;
  border-radius: 9px;
  background: #2563eb;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.login-button:hover {
  background: #1d4ed8;
}

.login-button:active {
  transform: translateY(1px);
}

.login-error {
  padding: 11px 13px;
  border: 1px solid #7f1d1d;
  border-radius: 8px;
  background: #2a1115;
  color: #fca5a5;
  font-size: 14px;
}

.login-demo {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid #263244;
  color: #7f8da3;
  font-size: 12px;
  line-height: 1.45;
}

.login-demo strong {
  margin-bottom: 4px;
  color: #cbd5e1;
}

@media (max-width: 560px) {
  .login-page {
    padding: 16px;
  }

  .login-card {
    padding: 26px 22px;
  }
}

'@ -Encoding UTF8

$path = Join-Path $root "src\App.tsx"
$directory = Split-Path $path -Parent
New-Item -ItemType Directory -Force $directory | Out-Null
Set-Content -Path $path -Value @'
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "./auth/ProtectedRoute";

import AdminLayout from "./layouts/AdminLayout";
import ClientLayout from "./layouts/ClientLayout";
import SupplierLayout from "./layouts/SupplierLayout";

import Dashboard from "./pages/Dashboard";
import ClientDashboard from "./pages/client/ClientDashboard";
import SupplierDashboard from "./pages/supplier/SupplierDashboard";
import ModulePage from "./pages/ModulePage";
import LoginPage from "./pages/auth/LoginPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/login" replace />} />

        <Route
          path="/admin"
          element={
            <ProtectedRoute role="admin">
              <AdminLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />

          <Route
            path="solicitacoes"
            element={
              <ModulePage
                title="Solicitações"
                description="Gerenciamento das solicitações de serviços mecânicos."
              />
            }
          />

          <Route
            path="cotacoes"
            element={
              <ModulePage
                title="Cotações"
                description="Cotações e propostas dos fornecedores."
              />
            }
          />

          <Route
            path="contratacoes"
            element={
              <ModulePage
                title="Contratações"
                description="Contratações de serviços entre clientes e fornecedores."
              />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <ModulePage
                title="Ordens de Serviço"
                description="Execução e controle das ordens de serviço."
              />
            }
          />

          <Route
            path="producao"
            element={
              <ModulePage
                title="Acompanhamento de Produção"
                description="Acompanhamento das etapas de produção."
              />
            }
          />

          <Route
            path="entregas"
            element={
              <ModulePage
                title="Entregas e Aceite"
                description="Controle das entregas e aceite pelo cliente."
              />
            }
          />

          <Route
            path="pagamentos"
            element={
              <ModulePage
                title="Pagamentos"
                description="Controle financeiro e pagamentos das contratações."
              />
            }
          />

          <Route
            path="avaliacoes"
            element={
              <ModulePage
                title="Avaliações"
                description="Avaliações e reputação dos fornecedores."
              />
            }
          />

          <Route
            path="ranking"
            element={
              <ModulePage
                title="Ranking de Fornecedores"
                description="Consulta da classificação derivada das avaliações."
              />
            }
          />

          <Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos Técnicos"
                description="Gerenciamento dos arquivos técnicos dos serviços."
              />
            }
          />
        </Route>

        <Route
          path="/cliente"
          element={
            <ProtectedRoute role="cliente">
              <ClientLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<ClientDashboard />} />

          <Route
            path="solicitacoes"
            element={
              <ModulePage
                title="Minhas Solicitações"
                description="Crie e acompanhe suas solicitações de serviços mecânicos."
              />
            }
          />

          <Route
            path="cotacoes"
            element={
              <ModulePage
                title="Cotações Recebidas"
                description="Visualize e compare as cotações recebidas."
              />
            }
          />

          <Route
            path="contratacoes"
            element={
              <ModulePage
                title="Minhas Contratações"
                description="Acompanhe os serviços contratados."
              />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <ModulePage
                title="Ordens de Serviço"
                description="Acompanhe as ordens relacionadas aos seus serviços."
              />
            }
          />

          <Route
            path="producao"
            element={
              <ModulePage
                title="Acompanhamento de Produção"
                description="Acompanhe a produção dos seus serviços."
              />
            }
          />

          <Route
            path="entregas"
            element={
              <ModulePage
                title="Entregas e Aceite"
                description="Receba, aceite ou rejeite suas entregas."
              />
            }
          />

          <Route
            path="pagamentos"
            element={
              <ModulePage
                title="Pagamentos"
                description="Consulte pagamentos e situação financeira das contratações."
              />
            }
          />

          <Route
            path="avaliacoes"
            element={
              <ModulePage
                title="Avaliações"
                description="Avalie os fornecedores dos serviços contratados."
              />
            }
          />

          <Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos Técnicos"
                description="Gerencie os arquivos técnicos das suas solicitações."
              />
            }
          />
        </Route>

        <Route
          path="/fornecedor"
          element={
            <ProtectedRoute role="fornecedor">
              <SupplierLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<SupplierDashboard />} />

          <Route
            path="solicitacoes"
            element={
              <ModulePage
                title="Solicitações Disponíveis"
                description="Consulte solicitações de clientes e oportunidades para cotação."
              />
            }
          />

          <Route
            path="cotacoes"
            element={
              <ModulePage
                title="Minhas Cotações"
                description="Gerencie as cotações enviadas aos clientes."
              />
            }
          />

          <Route
            path="contratacoes"
            element={
              <ModulePage
                title="Contratações"
                description="Acompanhe os serviços contratados pelos clientes."
              />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <ModulePage
                title="Ordens de Serviço"
                description="Gerencie suas ordens de serviço."
              />
            }
          />

          <Route
            path="producao"
            element={
              <ModulePage
                title="Produção"
                description="Acompanhe e atualize a execução dos serviços."
              />
            }
          />

          <Route
            path="entregas"
            element={
              <ModulePage
                title="Entregas"
                description="Gerencie as entregas dos serviços concluídos."
              />
            }
          />

          <Route
            path="pagamentos"
            element={
              <ModulePage
                title="Pagamentos"
                description="Consulte os pagamentos e valores a receber."
              />
            }
          />

          <Route
            path="avaliacoes"
            element={
              <ModulePage
                title="Avaliações"
                description="Consulte as avaliações recebidas dos clientes."
              />
            }
          />

          <Route
            path="ranking"
            element={
              <ModulePage
                title="Ranking de Fornecedores"
                description="Consulte sua posição e histórico de avaliações."
              />
            }
          />

          <Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos Técnicos"
                description="Consulte os arquivos técnicos disponibilizados pelos clientes."
              />
            }
          />
        </Route>

        <Route
          path="/solicitacoes"
          element={<Navigate to="/admin/solicitacoes" replace />}
        />
        <Route
          path="/cotacoes"
          element={<Navigate to="/admin/cotacoes" replace />}
        />
        <Route
          path="/contratacoes"
          element={<Navigate to="/admin/contratacoes" replace />}
        />
        <Route
          path="/ordens-servico"
          element={<Navigate to="/admin/ordens-servico" replace />}
        />
        <Route
          path="/producao"
          element={<Navigate to="/admin/producao" replace />}
        />
        <Route
          path="/entregas"
          element={<Navigate to="/admin/entregas" replace />}
        />
        <Route
          path="/pagamentos"
          element={<Navigate to="/admin/pagamentos" replace />}
        />
        <Route
          path="/avaliacoes"
          element={<Navigate to="/admin/avaliacoes" replace />}
        />
        <Route
          path="/ranking"
          element={<Navigate to="/admin/ranking" replace />}
        />
        <Route
          path="/arquivos-tecnicos"
          element={<Navigate to="/admin/arquivos-tecnicos" replace />}
        />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

'@ -Encoding UTF8

$path = Join-Path $root "src\main.tsx"
$directory = Split-Path $path -Parent
New-Item -ItemType Directory -Force $directory | Out-Null
Set-Content -Path $path -Value @'
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { AuthProvider } from "./auth/AuthContext";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);

'@ -Encoding UTF8

Write-Host ""
Write-Host "MEC-Servicos frontend configurado." -ForegroundColor Green
Write-Host "Autenticacao, login e roteamento por perfil foram gravados."
Write-Host ""
Write-Host "Proximo comando:" -ForegroundColor Cyan
Write-Host "npm run build"