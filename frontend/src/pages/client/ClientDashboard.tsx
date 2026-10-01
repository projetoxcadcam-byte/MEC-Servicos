export default function ClientDashboard() {
  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">ÁREA DO CLIENTE</span>
        <h2>Meu Dashboard</h2>
        <p>Acompanhe suas solicitações e serviços em um único lugar.</p>
      </div>

      <div className="indicator-grid">
        <div className="indicator-card">
          <span>Solicitações</span>
          <strong>0</strong>
          <small>Solicitações abertas</small>
        </div>

        <div className="indicator-card">
          <span>Em produção</span>
          <strong>0</strong>
          <small>Serviços em execução</small>
        </div>

        <div className="indicator-card">
          <span>Entregas</span>
          <strong>0</strong>
          <small>Aguardando aceite</small>
        </div>

        <div className="indicator-card">
          <span>Pagamentos</span>
          <strong>R$ 0,00</strong>
          <small>Saldo financeiro</small>
        </div>
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <span className="eyebrow">MEUS SERVIÇOS</span>
            <h3>Fluxo do serviço</h3>
          </div>

          <div className="flow">
            <div><strong>01</strong><span>Solicitação</span></div>
            <div><strong>02</strong><span>Cotação</span></div>
            <div><strong>03</strong><span>Contratação</span></div>
            <div><strong>04</strong><span>Produção</span></div>
            <div><strong>05</strong><span>Entrega</span></div>
            <div><strong>06</strong><span>Pagamento</span></div>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <span className="eyebrow">ACESSO RÁPIDO</span>
            <h3>Minhas atividades</h3>
          </div>

          <ul className="module-list">
            <li>Nova solicitação</li>
            <li>Cotações recebidas</li>
            <li>Serviços em produção</li>
            <li>Entregas pendentes</li>
            <li>Pagamentos</li>
          </ul>
        </section>
      </div>
    </>
  );
}
