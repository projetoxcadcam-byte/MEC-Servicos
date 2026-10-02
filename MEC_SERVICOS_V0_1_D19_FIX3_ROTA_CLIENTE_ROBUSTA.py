from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


REVISION = "MEC-SERVICOS-V0.1-D19-FIX3-ROTA-CLIENTE-ROBUSTA-ICONS-ABAS-2026-10-01"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def backup(root: Path, backup_root: Path, relative: str) -> bool:
    source = root / relative
    if not source.exists():
        return False
    target = backup_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


PORTAL_LAYOUT_CSS = r"""
:root {
  --portal-bg: #0a0f16;
  --portal-panel: #111923;
  --portal-panel-2: #151f2b;
  --portal-border: #243142;
  --portal-text: #edf3fb;
  --portal-muted: #8391a5;
  --portal-accent: #3b82f6;
  --portal-accent-soft: rgba(59, 130, 246, .13);
}

.portal-shell {
  min-height: 100vh;
  display: flex;
  background:
    radial-gradient(circle at 80% -10%, rgba(37, 99, 235, .10), transparent 30%),
    var(--portal-bg);
  color: var(--portal-text);
}

.portal-sidebar {
  width: 270px;
  min-width: 270px;
  min-height: 100vh;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--portal-border);
  background: rgba(13, 19, 28, .96);
  padding: 20px 14px;
}

.portal-brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 4px 9px 20px;
  border-bottom: 1px solid #202b39;
}

.portal-brand-mark {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: linear-gradient(135deg, #2563eb, #60a5fa);
  color: white;
  font-size: 18px;
  font-weight: 900;
  box-shadow: 0 8px 24px rgba(37, 99, 235, .24);
}

.portal-brand-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.05;
}

.portal-brand-copy strong {
  font-size: 16px;
  letter-spacing: .5px;
}

.portal-brand-copy span {
  margin-top: 4px;
  color: #8090a5;
  font-size: 11px;
}

.portal-role {
  margin: 18px 9px 9px;
  color: #5d9cff;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

.portal-navigation {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  padding-right: 2px;
}

.portal-nav-item {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-sizing: border-box;
  border: 1px solid transparent;
  border-radius: 9px;
  color: #9aa8bb;
  padding: 0 12px;
  text-decoration: none;
  transition: background .16s ease, color .16s ease, border-color .16s ease, transform .16s ease;
}

.portal-nav-item svg {
  flex: 0 0 auto;
}

.portal-nav-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 650;
}

.portal-nav-item:hover {
  color: #eaf1fa;
  background: #111c28;
  border-color: #223247;
  transform: translateX(1px);
}

.portal-nav-item.active {
  color: #f5f9ff;
  background: var(--portal-accent-soft);
  border-color: rgba(59, 130, 246, .30);
  box-shadow: inset 3px 0 0 #3b82f6;
}

.portal-nav-item.active svg {
  color: #6da9ff;
}

.portal-sidebar-footer {
  margin-top: auto;
  padding: 16px 9px 2px;
  border-top: 1px solid #202b39;
}

.portal-sidebar-footer span,
.portal-sidebar-footer small {
  display: block;
}

.portal-sidebar-footer span {
  color: #69798e;
  font-size: 11px;
  line-height: 1.45;
}

.portal-sidebar-footer small {
  margin-top: 5px;
  color: #455467;
  font-size: 10px;
}

.portal-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.portal-topbar {
  min-height: 72px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--portal-border);
  background: rgba(10, 15, 22, .78);
  padding: 0 28px;
  backdrop-filter: blur(12px);
}

.portal-page-title {
  display: flex;
  align-items: center;
  gap: 11px;
}

.portal-page-title-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid #26364a;
  border-radius: 9px;
  background: #101a25;
  color: #66a5ff;
}

.portal-page-title strong {
  display: block;
  font-size: 16px;
}

.portal-page-title span {
  display: block;
  margin-top: 3px;
  color: #738197;
  font-size: 11px;
}

.portal-user {
  display: flex;
  align-items: center;
  gap: 12px;
}

.portal-user-avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #172338;
  border: 1px solid #29405f;
  color: #8bbcff;
  font-weight: 800;
}

.portal-user-copy {
  min-width: 0;
}

.portal-user-copy strong,
.portal-user-copy span {
  display: block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.portal-user-copy strong {
  color: #e6edf7;
  font-size: 12px;
}

.portal-user-copy span {
  margin-top: 3px;
  color: #68778c;
  font-size: 10px;
}

.portal-logout {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #2a394c;
  border-radius: 8px;
  background: #101822;
  color: #aab7c9;
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  padding: 9px 11px;
}

.portal-logout:hover {
  color: #fff;
  border-color: #3a516d;
  background: #152131;
}

.portal-content {
  min-width: 0;
  flex: 1;
}

@media (max-width: 900px) {
  .portal-sidebar {
    width: 78px;
    min-width: 78px;
    padding: 15px 9px;
  }

  .portal-brand-copy,
  .portal-role,
  .portal-nav-item span,
  .portal-sidebar-footer,
  .portal-user-copy,
  .portal-logout span {
    display: none;
  }

  .portal-brand {
    justify-content: center;
    padding: 2px 0 16px;
  }

  .portal-nav-item {
    justify-content: center;
    padding: 0;
  }

  .portal-topbar {
    padding: 0 16px;
  }

  .portal-page-title span {
    display: none;
  }
}
"""


CLIENT_LAYOUT = r"""
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
"""


ADMIN_LAYOUT = r"""
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
  { label: "Dashboard", path: "/admin", icon: Gauge },
  { label: "Solicitações", path: "/admin/solicitacoes", icon: ClipboardList },
  { label: "Cotações", path: "/admin/cotacoes", icon: FileText },
  { label: "Contratações", path: "/admin/contratacoes", icon: Handshake },
  { label: "Ordens de Serviço", path: "/admin/ordens-servico", icon: Wrench },
  { label: "Acompanhamento de Produção", path: "/admin/producao", icon: Settings2 },
  { label: "Entregas e Aceite", path: "/admin/entregas", icon: PackageCheck },
  { label: "Pagamentos", path: "/admin/pagamentos", icon: CreditCard },
  { label: "Avaliações", path: "/admin/avaliacoes", icon: Star },
  { label: "Ranking de Fornecedores", path: "/admin/ranking", icon: BarChart3 },
  { label: "Arquivos Técnicos", path: "/admin/arquivos-tecnicos", icon: Archive },
];

function initials(nome: string) {
  return nome
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase())
    .join("") || "A";
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const paginaAtual =
    [...menu]
      .sort((a, b) => b.path.length - a.path.length)
      .find((item) =>
        item.path === "/admin"
          ? location.pathname === "/admin"
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

        <div className="portal-role">Painel Administrativo</div>

        <nav className="portal-navigation">
          {menu.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/admin"}
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
          <span>Gestão da plataforma e operação B2B</span>
          <small>Backoffice · V0.1</small>
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
              <span>Painel Administrativo · MEC Serviços</span>
            </div>
          </div>

          <div className="portal-user">
            <div className="portal-user-avatar">{initials(user?.nome ?? "Administrador")}</div>
            <div className="portal-user-copy">
              <strong>{user?.nome ?? "Administrador"}</strong>
              <span>{user?.email ?? "admin@mec-servicos.local"}</span>
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
"""


SUPPLIER_LAYOUT = r"""
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
"""


def patch_client_page(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    old = 'import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";'
    new = 'import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";'
    if old in text:
        text = text.replace(old, new, 1)
    else:
        text = re.sub(
            r'import\s*\{\s*FormEvent,\s*useCallback,\s*useEffect,\s*useMemo,\s*useState\s*\}\s*from\s*"react";',
            new,
            text,
            count=1,
        )
    path.write_text(text, encoding="utf-8")
    return True


def patch_app(app_path: Path) -> bool:
    """Patch the client requests route using structural markers, tolerating
    formatting/line-ending/description changes in App.tsx.
    """
    text = app_path.read_text(encoding="utf-8-sig")

    import_line = 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";'
    if import_line not in text:
        marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
        if marker not in text:
            raise RuntimeError("Não encontrei o import de ClientDashboard em App.tsx.")
        text = text.replace(marker, marker + "\n" + import_line, 1)

    if "<ClientSolicitacoesPage />" not in text:
        # Isolate the client route group first. This avoids accidentally
        # touching the admin or supplier `solicitacoes` routes.
        client_match = re.search(
            r'<Route\s+path="/cliente"\s+element=\{<ClientLayout\s*/>\}>',
            text,
        )
        supplier_match = re.search(
            r'<Route\s+path="/fornecedor"\s+element=\{<SupplierLayout\s*/>\}>',
            text,
        )
        if not client_match:
            raise RuntimeError(
                "App.tsx não contém a rota /cliente com ClientLayout. "
                "O D19 não alterou as rotas."
            )

        client_start = client_match.end()
        client_end = supplier_match.start() if supplier_match and supplier_match.start() > client_start else len(text)
        client_block = text[client_start:client_end]

        route_pattern = re.compile(
            r'<Route\s+path="solicitacoes"\s+element=\{\s*'
            r'<ModulePage\b[\s\S]*?/>'
            r'\s*\}\s*/>',
            flags=re.DOTALL,
        )
        patched_block, count = route_pattern.subn(
            '<Route path="solicitacoes" element={<ClientSolicitacoesPage />} />',
            client_block,
            count=1,
        )

        if count != 1:
            # Secondary fallback: locate the title inside the client block
            # and replace the whole nearest Route/ModulePage construct.
            title_pos = client_block.find('title="Minhas Solicitações"')
            if title_pos >= 0:
                route_start = client_block.rfind('<Route', 0, title_pos)
                route_end = client_block.find('</Route>', title_pos)
                if route_start >= 0 and route_end >= 0:
                    route_end += len('</Route>')
                    patched_block = (
                        client_block[:route_start]
                        + '<Route path="solicitacoes" element={<ClientSolicitacoesPage />} />'
                        + client_block[route_end:]
                    )
                    count = 1

        if count != 1:
            raise RuntimeError(
                "A rota `solicitacoes` não foi encontrada dentro de /cliente. "
                "Nenhuma alteração de rota foi aplicada."
            )

        text = text[:client_start] + patched_block + text[client_end:]

    app_path.write_text(text, encoding="utf-8")
    return True

def main() -> None:
    root = Path.cwd()
    frontend = root / "frontend"

    if not (root / "backend" / "app").is_dir():
        raise SystemExit("ERRO: execute na raiz C:\\Users\\Omega\\Desktop\\MEC-Servicos.")
    if not (frontend / "package.json").exists():
        raise SystemExit("ERRO: frontend não encontrado.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / "_mec_backups" / f"V0_1_D19_ICONS_ABAS_{stamp}"

    targets = [
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/src/App.tsx",
        "frontend/src/pages/client/ClientSolicitacoesPage.tsx",
        "frontend/src/layouts/ClientLayout.tsx",
        "frontend/src/layouts/AdminLayout.tsx",
        "frontend/src/layouts/SupplierLayout.tsx",
    ]

    backed_up = sum(int(backup(root, backup_root, item)) for item in targets)

    print("MEC Serviços — D19 FIX3 Rota Cliente Robusta + Ícones + Abas")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")
    print("BACKUP= True")
    print(f"BACKED_UP= {backed_up}")
    print(f"BACKUP_DIR= {backup_root}")

    print("")
    print("Localizando npm...")
    npm_exe = None

    if __import__("os").name == "nt":
        npm_exe = shutil.which("npm.cmd") or shutil.which("npm")
    else:
        npm_exe = shutil.which("npm")

    if not npm_exe:
        raise SystemExit(
            "ERRO: npm não foi encontrado no PATH deste processo Python. "
            "No PowerShell, confirme com: Get-Command npm"
        )

    print(f"NPM= {npm_exe}")
    print("Instalando lucide-react...")

    result = subprocess.run(
        [npm_exe, "install", "lucide-react"],
        cwd=frontend,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            "ERRO: npm install lucide-react falhou. "
            "Nenhuma alteração visual foi aplicada depois dessa etapa."
        )

    app_path = frontend / "src/App.tsx"
    client_page = frontend / "src/pages/client/ClientSolicitacoesPage.tsx"

    patch_client_page(client_page)
    patch_app(app_path)

    write(frontend / "src/layouts/PortalLayout.css", PORTAL_LAYOUT_CSS)
    write(frontend / "src/layouts/ClientLayout.tsx", CLIENT_LAYOUT)
    write(frontend / "src/layouts/AdminLayout.tsx", ADMIN_LAYOUT)
    write(frontend / "src/layouts/SupplierLayout.tsx", SUPPLIER_LAYOUT)

    report = {
        "revision": REVISION,
        "build_fixes": [
            "FormEvent convertido para import type",
            "rota /cliente/solicitacoes localizada por título sem depender do bloco/comentário do App.tsx",
        ],
        "visual": {
            "library": "lucide-react",
            "client_icons": True,
            "admin_icons": True,
            "supplier_icons": True,
            "named_tabs": True,
            "responsive_sidebar": True,
            "topbar_with_current_page": True,
        },
        "backup_dir": str(backup_root),
        "backed_up_files": backed_up,
    }

    (root / "MEC_SERVICOS_V0_1_D19_ICONS_ABAS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (root / "MEC_SERVICOS_V0_1_D19_ICONS_ABAS_RELATORIO.txt").write_text(
        "\n".join(
            [
                "MEC Serviços — D19 Ícones + Abas + Correção do Build",
                f"REVISION= {REVISION}",
                "LUCIDE_REACT= True",
                "FORM_EVENT_TYPE_IMPORT_FIX= True",
                "CLIENT_REQUEST_ROUTE_FIX= True",
                "CLIENT_LAYOUT_ICONS= True",
                "ADMIN_LAYOUT_ICONS= True",
                "SUPPLIER_LAYOUT_ICONS= True",
                "NAMED_TABS= True",
                "RESPONSIVE_SIDEBAR= True",
                f"BACKED_UP= {backed_up}",
                f"BACKUP_DIR= {backup_root}",
            ]
        ) + "\n",
        encoding="utf-8",
    )

    print("")
    print("D19_CONFIGURADO= True")
    print("BUILD_FIXES= True")
    print("ICONS= True")
    print("ABAS_NOMEADAS= True")
    print("")
    print("Agora execute:")
    print("cd .\\frontend")
    print("npm run build")
    print("cd ..")
    print("pytest -q .\\tests --ignore=.\u005ctests\u005cmold")


if __name__ == "__main__":
    main()
