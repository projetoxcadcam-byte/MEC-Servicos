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
