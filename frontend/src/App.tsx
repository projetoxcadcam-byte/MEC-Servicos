import TutorialPage from "./pages/tutorial/TutorialEntrada";
import PortalSemRanking from "./auth/PortalSemRanking";
import AvaliacoesPage from "./pages/avaliacoes/AvaliacoesPage";
import RankingAvaliacoesPage from "./pages/avaliacoes/RankingAvaliacoesPage";
import AdminContratacaoPage from "./pages/contratacao-admin/AdminContratacaoPage";
import AdminComercialPage from "./pages/comercial/AdminComercialPage";
import AdminDocumentacaoPage from "./pages/documentacao/AdminDocumentacaoPage";
import ResultadoAdministracaoPage from "./pages/formacao-preco/ResultadoAdministracaoPage";
import FinanceiroPage from "./pages/financeiro/FinanceiroPage";
import AdminIntermediacaoPage from "./pages/intermediacao/AdminIntermediacaoPage";
import PortalEntregasPage from "./pages/entregas/PortalEntregasPage";
import PortalProducaoPage from "./pages/producao/PortalProducaoPage";
import PortalOrdensServicoPage from "./pages/ordens/PortalOrdensServicoPage";
import PortalContratacoesPage from "./pages/contratacoes/PortalContratacoesPage";
import SupplierCotacoesPage from "./pages/supplier/SupplierCotacoesPage";
import CotacoesClientePage from "./pages/cotacoes-cliente/CotacoesClientePage";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./auth/AuthContext";
import ContaAcessoPage from "./pages/auth/ContaAcessoPage";

import ProtectedRoute from "./auth/ProtectedRoute";

import AdminLayout from "./layouts/AdminLayout";
import ClientLayout from "./layouts/ClientLayout";
import SupplierLayout from "./layouts/SupplierLayout";

import ResumoGerencialPage from "./pages/gerencial/ResumoGerencialPage";
import ComparativoGerencialPage from "./pages/comparativo/ComparativoGerencialPage";
import ExtratoFinanceiroPage from "./pages/extrato/ExtratoFinanceiroPage";
import CentralPendenciasPage from "./pages/pendencias/CentralPendenciasPage";
import RelatorioEmpresasPage from "./pages/empresas/RelatorioEmpresasPage";
import EmpresasOperacoesPage from "./pages/empresas/EmpresasOperacoesPage";
import RelatorioPeriodoPage from "./pages/periodo/RelatorioPeriodoPage";
import RelatorioAdministrativoPage from "./pages/relatorios/RelatorioAdministrativoPage";
import PainelAdministrativoPage from "./pages/painel/PainelAdministrativoPage";
import PainelPortalPage from "./pages/painel-portais/PainelPortalPage";
import ClientArquivosTecnicosPage from "./pages/client/ClientArquivosTecnicosPage";
import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";
import AdminProducaoPage from "./pages/producao-admin/AdminProducaoPage";
import ArquivosTecnicosFornecedorPage from "./pages/supplier/ArquivosTecnicosFornecedorPage";
import LoginPage from "./pages/auth/LoginPage";

function SenhaInicial({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const local = useLocation();
  if (user?.deve_alterar_senha && local.pathname !== "/conta") return <Navigate to="/conta" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <SenhaInicial><Routes>
        <Route path="/conta" element={<ContaAcessoPage />} />
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
          <Route index element={<PainelAdministrativoPage />} />
          <Route path="ajuda" element={<TutorialPage perfil="admin" />} />
          <Route path="empresas" element={<EmpresasOperacoesPage />} />

          <Route path="solicitacoes" element={<AdminComercialPage modo="solicitacoes" />} />

          <Route path="cotacoes" element={<AdminComercialPage modo="cotacoes" />} />

          <Route path="contratacoes" element={<AdminContratacaoPage modo="contratacoes" />} />

          <Route path="ordens-servico" element={<AdminContratacaoPage modo="ordens-servico" />} />

          <Route
            path="producao"
            element={
              <AdminProducaoPage />
            }
          />

          <Route path="entregas" element={<AdminIntermediacaoPage />} />
          <Route path="intermediacao" element={<AdminIntermediacaoPage />} />

          <Route path="pagamentos" element={<FinanceiroPage perfil="admin" />} />
          <Route path="resultado-administracao" element={<ResultadoAdministracaoPage />} />
          <Route path="relatorios" element={<RelatorioAdministrativoPage />} />
          <Route path="relatorios-periodo" element={<RelatorioPeriodoPage />} />
          <Route path="relatorios-empresas" element={<RelatorioEmpresasPage />} />
          <Route path="pendencias" element={<CentralPendenciasPage />} />
          <Route path="resumo-gerencial" element={<ResumoGerencialPage />} />
          <Route path="comparativo-gerencial" element={<ComparativoGerencialPage />} />
          <Route path="extrato-financeiro" element={<ExtratoFinanceiroPage />} />

          <Route path="avaliacoes" element={<AvaliacoesPage perfil="admin" />} />

          <Route path="ranking" element={<RankingAvaliacoesPage />} />

          <Route
            path="arquivos-tecnicos"
            element={
              <AdminDocumentacaoPage />
            }
          />
        </Route>

        <Route
          path="/cliente"
          element={
            <ProtectedRoute role="cliente">
              <PortalSemRanking><ClientLayout /></PortalSemRanking>
            </ProtectedRoute>
          }
        >
          <Route index element={<PainelPortalPage perfil="cliente" />} />
          <Route path="ajuda" element={<TutorialPage perfil="cliente" />} />

                    <Route path="solicitacoes" element={<ClientSolicitacoesPage />} />

          <Route path="cotacoes" element={<CotacoesClientePage />} />

          <Route
            path="contratacoes"
            element={
              <PortalContratacoesPage perfil="cliente" />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <PortalOrdensServicoPage perfil="cliente" />
            }
          />

          <Route
            path="producao"
            element={
              <PortalProducaoPage perfil="cliente" />
            }
          />

          <Route
            path="entregas"
            element={
              <PortalEntregasPage perfil="cliente" />
            }
          />

          <Route path="pagamentos" element={<FinanceiroPage perfil="cliente" />} />

          <Route path="avaliacoes" element={<AvaliacoesPage perfil="cliente" />} />
          <Route path="ranking" element={<Navigate to="/cliente/avaliacoes" replace />} />

          <Route path="arquivos-tecnicos" element={<ClientArquivosTecnicosPage />} />
        </Route>

        <Route
          path="/fornecedor"
          element={
            <ProtectedRoute role="fornecedor">
              <PortalSemRanking><SupplierLayout /></PortalSemRanking>
            </ProtectedRoute>
          }
        >
          <Route index element={<PainelPortalPage perfil="fornecedor" />} />
          <Route path="ajuda" element={<TutorialPage perfil="fornecedor" />} />

          <Route
            path="solicitacoes"
            element={
              <SupplierCotacoesPage modo="oportunidades" />
            }
          />

          <Route
            path="cotacoes"
            element={
              <SupplierCotacoesPage modo="cotacoes" />
            }
          />

          <Route
            path="contratacoes"
            element={
              <PortalContratacoesPage perfil="fornecedor" />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <PortalOrdensServicoPage perfil="fornecedor" />
            }
          />

          <Route
            path="producao"
            element={
              <PortalProducaoPage perfil="fornecedor" />
            }
          />

          <Route
            path="entregas"
            element={
              <PortalEntregasPage perfil="fornecedor" />
            }
          />

          <Route path="pagamentos" element={<FinanceiroPage perfil="fornecedor" />} />

          <Route path="avaliacoes" element={<AvaliacoesPage perfil="fornecedor" />} />

          <Route path="ranking" element={<Navigate to="/fornecedor/avaliacoes" replace />} />

          <Route
            path="arquivos-tecnicos"
            element={
              <ArquivosTecnicosFornecedorPage />
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
      </Routes></SenhaInicial>
    </BrowserRouter>
  );
}
