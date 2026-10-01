import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "./auth/ProtectedRoute";

import AdminLayout from "./layouts/AdminLayout";
import ClientLayout from "./layouts/ClientLayout";
import SupplierLayout from "./layouts/SupplierLayout";

import Dashboard from "./pages/Dashboard";
import ClientDashboard from "./pages/client/ClientDashboard";
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
                title="SolicitaÃ§Ãµes"
                description="Gerenciamento das solicitaÃ§Ãµes de serviÃ§os mecÃ¢nicos."
              />
            }
          />

          <Route
            path="cotacoes"
            element={
              <ModulePage
                title="CotaÃ§Ãµes"
                description="CotaÃ§Ãµes e propostas dos fornecedores."
              />
            }
          />

          <Route
            path="contratacoes"
            element={
              <ModulePage
                title="ContrataÃ§Ãµes"
                description="ContrataÃ§Ãµes de serviÃ§os entre clientes e fornecedores."
              />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <ModulePage
                title="Ordens de ServiÃ§o"
                description="ExecuÃ§Ã£o e controle das ordens de serviÃ§o."
              />
            }
          />

          <Route
            path="producao"
            element={
              <ModulePage
                title="Acompanhamento de ProduÃ§Ã£o"
                description="Acompanhamento das etapas de produÃ§Ã£o."
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
                description="Controle financeiro e pagamentos das contrataÃ§Ãµes."
              />
            }
          />

          <Route
            path="avaliacoes"
            element={
              <ModulePage
                title="AvaliaÃ§Ãµes"
                description="AvaliaÃ§Ãµes e reputaÃ§Ã£o dos fornecedores."
              />
            }
          />

          <Route
            path="ranking"
            element={
              <ModulePage
                title="Ranking de Fornecedores"
                description="Consulta da classificaÃ§Ã£o derivada das avaliaÃ§Ãµes."
              />
            }
          />

          <Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos TÃ©cnicos"
                description="Gerenciamento dos arquivos tÃ©cnicos dos serviÃ§os."
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

          <Route
            path="solicitacoes"
            element={
              <ModulePage
                title="Minhas SolicitaÃ§Ãµes"
                description="Crie e acompanhe suas solicitaÃ§Ãµes de serviÃ§os mecÃ¢nicos."
              />
            }
          />

          <Route
            path="cotacoes"
            element={
              <ModulePage
                title="CotaÃ§Ãµes Recebidas"
                description="Visualize e compare as cotaÃ§Ãµes recebidas."
              />
            }
          />

          <Route
            path="contratacoes"
            element={
              <ModulePage
                title="Minhas ContrataÃ§Ãµes"
                description="Acompanhe os serviÃ§os contratados."
              />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <ModulePage
                title="Ordens de ServiÃ§o"
                description="Acompanhe as ordens relacionadas aos seus serviÃ§os."
              />
            }
          />

          <Route
            path="producao"
            element={
              <ModulePage
                title="Acompanhamento de ProduÃ§Ã£o"
                description="Acompanhe a produÃ§Ã£o dos seus serviÃ§os."
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
                description="Consulte pagamentos e situaÃ§Ã£o financeira das contrataÃ§Ãµes."
              />
            }
          />

          <Route
            path="avaliacoes"
            element={
              <ModulePage
                title="AvaliaÃ§Ãµes"
                description="Avalie os fornecedores dos serviÃ§os contratados."
              />
            }
          />

          <Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos TÃ©cnicos"
                description="Gerencie os arquivos tÃ©cnicos das suas solicitaÃ§Ãµes."
              />
            }
          />
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
                title="SolicitaÃ§Ãµes DisponÃ­veis"
                description="Consulte solicitaÃ§Ãµes de clientes e oportunidades para cotaÃ§Ã£o."
              />
            }
          />

          <Route
            path="cotacoes"
            element={
              <ModulePage
                title="Minhas CotaÃ§Ãµes"
                description="Gerencie as cotaÃ§Ãµes enviadas aos clientes."
              />
            }
          />

          <Route
            path="contratacoes"
            element={
              <ModulePage
                title="ContrataÃ§Ãµes"
                description="Acompanhe os serviÃ§os contratados pelos clientes."
              />
            }
          />

          <Route
            path="ordens-servico"
            element={
              <ModulePage
                title="Ordens de ServiÃ§o"
                description="Gerencie suas ordens de serviÃ§o."
              />
            }
          />

          <Route
            path="producao"
            element={
              <ModulePage
                title="ProduÃ§Ã£o"
                description="Acompanhe e atualize a execuÃ§Ã£o dos serviÃ§os."
              />
            }
          />

          <Route
            path="entregas"
            element={
              <ModulePage
                title="Entregas"
                description="Gerencie as entregas dos serviÃ§os concluÃ­dos."
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
                title="AvaliaÃ§Ãµes"
                description="Consulte as avaliaÃ§Ãµes recebidas dos clientes."
              />
            }
          />

          <Route
            path="ranking"
            element={
              <ModulePage
                title="Ranking de Fornecedores"
                description="Consulte sua posiÃ§Ã£o e histÃ³rico de avaliaÃ§Ãµes."
              />
            }
          />

          <Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos TÃ©cnicos"
                description="Consulte os arquivos tÃ©cnicos disponibilizados pelos clientes."
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
