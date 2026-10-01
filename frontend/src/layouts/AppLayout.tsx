import { NavLink, Outlet } from "react-router-dom";

const menu = [
  ["Dashboard", "/"],
  ["Solicitações", "/solicitacoes"],
  ["Cotações", "/cotacoes"],
  ["Contratações", "/contratacoes"],
  ["Ordens de Serviço", "/ordens-servico"],
  ["Produção", "/producao"],
  ["Entregas e Aceite", "/entregas"],
  ["Pagamentos", "/pagamentos"],
  ["Avaliações", "/avaliacoes"],
  ["Ranking de Fornecedores", "/ranking"],
  ["Arquivos Técnicos", "/arquivos-tecnicos"],
];

export default function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <strong>MEC</strong>
            <span>Serviços</span>
          </div>
        </div>

        <nav className="navigation">
          {menu.map(([label, path]) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span>Plataforma de Serviços Mecânicos</span>
          <small>V0.1</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="topbar-label">MEC-SERVICOS</span>
            <h1>Gestão de Serviços Mecânicos</h1>
          </div>
          <div className="status">
            <span className="status-dot" />
            Sistema operacional
          </div>
        </header>

        <section className="content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}
