const indicadores = [
  ["Solicitações", "0", "Solicitações abertas"],
  ["Ordens em produção", "0", "Em acompanhamento"],
  ["Entregas pendentes", "0", "Aguardando aceite"],
  ["Pagamentos", "R$ 0,00", "Saldo financeiro"],
];

export default function Dashboard() {
  return (
    <div>
      <div className="page-heading">
        <div>
          <span className="eyebrow">VISÃO GERAL</span>
          <h2>Dashboard</h2>
          <p>Acompanhe a operação da plataforma em um único lugar.</p>
        </div>
      </div>

      <div className="indicator-grid">
        {indicadores.map(([titulo, valor, descricao]) => (
          <article className="indicator-card" key={titulo}>
            <span>{titulo}</span>
            <strong>{valor}</strong>
            <small>{descricao}</small>
          </article>
        ))}
      </div>

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">OPERAÇÃO</span>
              <h3>Fluxo de serviços</h3>
            </div>
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
            <div>
              <span className="eyebrow">SISTEMA</span>
              <h3>Módulos disponíveis</h3>
            </div>
          </div>

          <ul className="module-list">
            <li>Solicitações e requisitos</li>
            <li>Cotações de fornecedores</li>
            <li>Ordens de serviço</li>
            <li>Acompanhamento de produção</li>
            <li>Entrega e aceite</li>
            <li>Pagamentos</li>
            <li>Avaliações e reputação</li>
            <li>Arquivos técnicos</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
