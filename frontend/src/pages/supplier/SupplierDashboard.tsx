export default function SupplierDashboard() {
  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">ÁREA DO FORNECEDOR</span>
        <h2>Meu Dashboard</h2>
        <p>Gerencie oportunidades, serviços e sua operação.</p>
      </div>

      <div className="indicator-grid">
        <div className="indicator-card">
          <span>Solicitações disponíveis</span>
          <strong>0</strong>
          <small>Oportunidades para cotar</small>
        </div>

        <div className="indicator-card">
          <span>Minhas cotações</span>
          <strong>0</strong>
          <small>Propostas enviadas</small>
        </div>

        <div className="indicator-card">
          <span>Em produção</span>
          <strong>0</strong>
          <small>Ordens em execução</small>
        </div>

        <div className="indicator-card">
          <span>A receber</span>
          <strong>R$ 0,00</strong>
          <small>Saldo financeiro</small>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <span className="eyebrow">OPERAÇÃO</span>
            <h3>Fluxo do fornecedor</h3>
          </div>

          <div className="flow">
            <div><strong>01</strong><span>Solicitação</span></div>
            <div><strong>02</strong><span>Cotação</span></div>
            <div><strong>03</strong><span>Contratação</span></div>
            <div><strong>04</strong><span>Produção</span></div>
            <div><strong>05</strong><span>Entrega</span></div>
            <div><strong>06</strong><span>Recebimento</span></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <span className="eyebrow">DESEMPENHO</span>
            <h3>Minha empresa</h3>
          </div>

          <ul className="module-list">
            <li>Avaliações recebidas</li>
            <li>Minha reputação</li>
            <li>Ranking de fornecedores</li>
            <li>Ordens de serviço</li>
            <li>Pagamentos a receber</li>
          </ul>
        </section>
      </div>
    </>
  );
}
