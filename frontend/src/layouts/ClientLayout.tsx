import { NavLink, Outlet } from "react-router-dom";

const menu = [
  ["Dashboard", "/cliente"],
  ["Solicitações", "/cliente/solicitacoes"],
  ["Cotações", "/cliente/cotacoes"],
  ["Contratações", "/cliente/contratacoes"],
  ["Ordens de Serviço", "/cliente/ordens-servico"],
  ["Produção", "/cliente/producao"],
  ["Entregas e Aceite", "/cliente/entregas"],
  ["Pagamentos", "/cliente/pagamentos"],
  ["Avaliações", "/cliente/avaliacoes"],
  ["Arquivos Técnicos", "/cliente/arquivos-tecnicos"],
];

export default function ClientLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <strong>MEC</strong>
            <span>Cliente</span>
          </div>
        </div>

        <nav className="navigation">
          {menu.map(([label, path]) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/cliente"}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span>Portal do Cliente</span>
          <small>MEC-Serviços V0.1</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="topbar-label">MEC-SERVICOS / CLIENTE</span>
            <h1>Portal do Cliente</h1>
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
