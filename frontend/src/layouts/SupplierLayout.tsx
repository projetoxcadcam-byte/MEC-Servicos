import { NavLink, Outlet } from "react-router-dom";

const menu = [
  ["Dashboard", "/fornecedor"],
  ["Solicitações Disponíveis", "/fornecedor/solicitacoes"],
  ["Minhas Cotações", "/fornecedor/cotacoes"],
  ["Contratações", "/fornecedor/contratacoes"],
  ["Ordens de Serviço", "/fornecedor/ordens-servico"],
  ["Produção", "/fornecedor/producao"],
  ["Entregas", "/fornecedor/entregas"],
  ["Pagamentos", "/fornecedor/pagamentos"],
  ["Avaliações", "/fornecedor/avaliacoes"],
  ["Ranking", "/fornecedor/ranking"],
  ["Arquivos Técnicos", "/fornecedor/arquivos-tecnicos"],
];

export default function SupplierLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <strong>MEC</strong>
            <span>Fornecedor</span>
          </div>
        </div>

        <nav className="navigation">
          {menu.map(([label, path]) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/fornecedor"}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span>Portal do Fornecedor</span>
          <small>MEC-Serviços V0.1</small>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="topbar-label">MEC-SERVICOS / FORNECEDOR</span>
            <h1>Portal do Fornecedor</h1>
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
