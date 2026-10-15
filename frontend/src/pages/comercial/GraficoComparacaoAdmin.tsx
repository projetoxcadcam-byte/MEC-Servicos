import { useId } from "react";
import type { Notas, Proposta } from "./ComparacaoCotacoesAdmin";
import "./GraficoComparacaoAdmin.css";

function SerieNotas({ origem, notas }: { origem: "cliente" | "admin"; notas: Notas }) {
  const nota = notas.media === null ? null : Number(notas.media);
  const avaliada = notas.quantidade > 0 && nota !== null && Number.isFinite(nota) && nota >= 0 && nota <= 5;
  return <div className={`com54-serie ${origem}`}>
    <span className="com54-origem">{origem === "cliente" ? "Clientes" : "ADM"}</span>
    <div className="com54-trilho" aria-hidden="true">
      {avaliada ? <div className="com54-barra" style={{ width: `${nota! * 20}%` }} /> : <span>Sem avaliações</span>}
    </div>
    <div className="com54-valor"><strong>{avaliada ? `${notas.media!.replace(".", ",")} / 5` : "Sem notas"}</strong>
      <small>{notas.quantidade} {notas.quantidade === 1 ? "avaliação" : "avaliações"}</small></div>
  </div>;
}

export default function GraficoComparacaoAdmin({ itens, aoVerHistorico, historicoBloqueado = false }: {
  itens: Proposta[]; aoVerHistorico?: (proposta: Proposta, botao: HTMLButtonElement) => void; historicoBloqueado?: boolean;
}) {
  const titulo = useId();
  const descricao = useId();
  if (!itens.length) return null;
  return <section className="com54-grafico" aria-labelledby={titulo} aria-describedby={descricao}>
    <header className="com54-cabecalho"><div><h4 id={titulo}>Comparação visual de avaliações</h4>
      <p id={descricao}>Médias históricas dos fornecedores das cotações desta página. Escala fixa de 0 a 5; cada origem permanece separada.</p></div>
      <span className="com54-privado">Somente ADM</span></header>
    <div className="com54-eixo" aria-hidden="true"><span>Fornecedor / cotação</span><div className="com54-regua"><span>Nota / 5</span><div>{[0, 1, 2, 3, 4, 5].map(n => <span key={n}>{n}</span>)}</div><span /></div></div>
    <ul className="com54-lista">{itens.map(q => <li key={q.cotacao_id} className="com54-proposta" data-cotacao={q.cotacao_id}>
      <div className="com54-fornecedor"><strong>{q.fornecedor}</strong><span>Cotação #{q.cotacao_id} · F-{q.empresa_fornecedora_id}</span>
        <small>{Number(q.valor_total).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })} · {q.prazo_dias} {q.prazo_dias === 1 ? "dia" : "dias"} de execução</small>
        {!q.pode_decidir && <small className="com54-consulta">Somente consulta</small>}
        {aoVerHistorico && <button type="button" className="com56-ver-historico" disabled={historicoBloqueado}
          aria-label={`Ver histórico do fornecedor F-${q.empresa_fornecedora_id} da cotação #${q.cotacao_id}`}
          onClick={e => aoVerHistorico(q, e.currentTarget)}>Ver histórico do fornecedor</button>}
      </div>
      <div className="com54-series"><SerieNotas origem="cliente" notas={q.notas_cliente} /><SerieNotas origem="admin" notas={q.notas_admin} /></div>
    </li>)}</ul>
    <p className="com54-rodape">As barras usam as mesmas notas da tabela abaixo. O gráfico não escolhe um fornecedor; use Conferir cotação para revisar a proposta antes de decidir.</p>
  </section>;
}
