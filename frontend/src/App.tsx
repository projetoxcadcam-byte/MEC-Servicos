import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "./auth/ProtectedRoute";

import AdminLayout from "./layouts/AdminLayout";
import ClientLayout from "./layouts/ClientLayout";
import SupplierLayout from "./layouts/SupplierLayout";

import Dashboard from "./pages/Dashboard";
import ClientDashboard from "./pages/client/ClientDashboard";
import ClientArquivosTecnicosPage from "./pages/client/ClientArquivosTecnicosPage";
import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";
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

                    <Route path="solicitacoes" element={<ClientSolicitacoesPage />} />

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

          <Route path="arquivos-tecnicos" element={<ClientArquivosTecnicosPage />} />
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
