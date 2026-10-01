interface ModulePageProps {
  title: string;
  description: string;
}

export default function ModulePage({
  title,
  description,
}: ModulePageProps) {
  return (
    <div>
      <div className="page-heading">
        <div>
          <span className="eyebrow">MÓDULO MEC-SERVICOS</span>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>

      <section className="panel empty-panel">
        <div className="empty-icon">+</div>
        <h3>Módulo preparado</h3>
        <p>
          A estrutura da interface está pronta para conexão com a API
          FastAPI existente.
        </p>
      </section>
    </div>
  );
}
