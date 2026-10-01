import { NavLink, Outlet } from "react-router-dom";

const menu = [
  ["Dashboard", "/admin"],
  ["Solicitações", "/admin/solicitacoes"],
  ["Cotações", "/admin/cotacoes"],
  ["Contratações", "/admin/contratacoes"],
  ["Ordens de Serviço", "/admin/ordens-servico"],
  ["Produção", "/admin/producao"],
  ["Entregas e Aceite", "/admin/entregas"],
  ["Pagamentos", "/admin/pagamentos"],
  ["Avaliações", "/admin/avaliacoes"],
  ["Ranking de Fornecedores", "/admin/ranking"],
  ["Arquivos Técnicos", "/admin/arquivos-tecnicos"],
];

export default function AdminLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <strong>MEC</strong>
            <span>Administração</span>
          </div>
        </div>

        <nav className="navigation">
          {menu.map(([label, path]) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/admin"}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span>Portal Administrativo</span>
          <small>MEC-Serviços V0.1</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="topbar-label">MEC-SERVICOS / ADMIN</span>
            <h1>Gestão Administrativa</h1>
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
