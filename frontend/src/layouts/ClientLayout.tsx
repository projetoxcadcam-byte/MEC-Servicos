
import {
  Archive,
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
  { label: "Dashboard", path: "/cliente", icon: Gauge },
  { label: "Minhas Solicitações", path: "/cliente/solicitacoes", icon: ClipboardList },
  { label: "Cotações Recebidas", path: "/cliente/cotacoes", icon: FileText },
  { label: "Minhas Contratações", path: "/cliente/contratacoes", icon: Handshake },
  { label: "Ordens de Serviço", path: "/cliente/ordens-servico", icon: Wrench },
  { label: "Acompanhamento de Produção", path: "/cliente/producao", icon: Settings2 },
  { label: "Entregas e Aceite", path: "/cliente/entregas", icon: PackageCheck },
  { label: "Pagamentos", path: "/cliente/pagamentos", icon: CreditCard },
  { label: "Avaliações", path: "/cliente/avaliacoes", icon: Star },
  { label: "Arquivos Técnicos", path: "/cliente/arquivos-tecnicos", icon: Archive },
];

function initials(nome: string) {
  return nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase())
    .join("") || "C";
}

export default function ClientLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const paginaAtual =
    [...menu]
      .sort((a, b) => b.path.length - a.path.length)
      .find((item) =>
        item.path === "/cliente"
          ? location.pathname === "/cliente"
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

        <div className="portal-role">Portal do Cliente</div>

        <nav className="portal-navigation">
          {menu.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/cliente"}
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
          <span>Plataforma B2B de fabricação mecânica</span>
          <small>Portal Cliente · V0.1</small>
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
              <span>Portal do Cliente · MEC Serviços</span>
            </div>
          </div>

          <div className="portal-user">
            <div className="portal-user-avatar">{initials(user?.nome ?? "Cliente")}</div>
            <div className="portal-user-copy">
              <strong>{user?.nome ?? "Cliente"}</strong>
              <span>{user?.email ?? "cliente@mec-servicos.local"}</span>
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
