
import {
  Archive,
  BarChart3,
  ClipboardList,
  CreditCard,
  FileText,
  Gauge,
  Handshake,
  PackageCheck,
  Settings2,
  Star,
  Wrench,
  LogOut,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import "./PortalLayout.css";

type MenuItem = {
  label: string;
  path: string;
  icon: LucideIcon;
};

const menu: MenuItem[] = [
  { label: "Dashboard", path: "/fornecedor", icon: Gauge },
  { label: "Solicitações Disponíveis", path: "/fornecedor/solicitacoes", icon: ClipboardList },
  { label: "Minhas Cotações", path: "/fornecedor/cotacoes", icon: FileText },
  { label: "Contratações", path: "/fornecedor/contratacoes", icon: Handshake },
  { label: "Ordens de Serviço", path: "/fornecedor/ordens-servico", icon: Wrench },
  { label: "Produção", path: "/fornecedor/producao", icon: Settings2 },
  { label: "Entregas", path: "/fornecedor/entregas", icon: PackageCheck },
  { label: "Pagamentos", path: "/fornecedor/pagamentos", icon: CreditCard },
  { label: "Avaliações", path: "/fornecedor/avaliacoes", icon: Star },
  { label: "Ranking de Fornecedores", path: "/fornecedor/ranking", icon: BarChart3 },
  { label: "Arquivos Técnicos", path: "/fornecedor/arquivos-tecnicos", icon: Archive },
];

function initials(nome: string) {
  return nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase())
    .join("") || "F";
}

export default function SupplierLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const paginaAtual =
    [...menu]
      .sort((a, b) => b.path.length - a.path.length)
      .find((item) =>
        item.path === "/fornecedor"
          ? location.pathname === "/fornecedor"
          : location.pathname.startsWith(item.path),
      ) ?? menu[0];

  const IconAtual = paginaAtual.icon;

  return (
    <div className="portal-shell">
      <aside className="portal-sidebar">
        <div className="portal-brand">
          <div className="portal-brand-mark">M</div>
          <div className="portal-brand-copy">
            <strong>MEC</strong>
            <span>Serviços Mecânicos</span>
          </div>
        </div>

        <div className="portal-role">Portal do Fornecedor</div>

        <nav className="portal-navigation">
          {menu.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/fornecedor"}
              className={({ isActive }) =>
                `portal-nav-item ${isActive ? "active" : ""}`
              }
              title={label}
            >
              <Icon size={19} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="portal-sidebar-footer">
          <span>Central de negócios e execução dos serviços</span>
          <small>Portal Fornecedor · V0.1</small>
        </div>
      </aside>

      <main className="portal-main">
        <header className="portal-topbar">
          <div className="portal-page-title">
            <div className="portal-page-title-icon">
              <IconAtual size={18} />
            </div>
            <div>
              <strong>{paginaAtual.label}</strong>
              <span>Portal do Fornecedor · MEC Serviços</span>
            </div>
          </div>

          <div className="portal-user">
            <div className="portal-user-avatar">{initials(user?.nome ?? "Fornecedor")}</div>
            <div className="portal-user-copy">
              <strong>{user?.nome ?? "Fornecedor"}</strong>
              <span>{user?.email ?? "fornecedor@mec-servicos.local"}</span>
            </div>
            <button className="portal-logout" type="button" onClick={logout} title="Sair">
              <LogOut size={15} />
              <span>Sair</span>
            </button>
          </div>
        </header>

        <div className="portal-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
