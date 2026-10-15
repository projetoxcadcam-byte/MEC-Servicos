import { useId } from "react";
import type { Ranking } from "./avaliacoesPortal";
import "./RankingAdministrativo.css";

export default function GraficoRanking({ ranking, aoVerHistorico }: { ranking: Ranking; aoVerHistorico?: (empresa: number) => void }) {
  const titulo = useId();
  const descricao = useId();
  return <section className="mec-ranking-grafico" aria-labelledby={titulo} aria-describedby={descricao}>
    <header className="mec-ranking-cabecalho">
      <div><h2 id={titulo}>Gráfico do ranking</h2>
        <p id={descricao}>{ranking.origem === "cliente" ? "Notas de clientes" : "Notas da administração"} · média de 0 a 5.
          {" "}Cada barra representa a nota média de uma empresa fornecedora.</p></div>
      <span className="mec-ranking-restrito">Somente ADM</span>
    </header>
    {ranking.itens.length ? <>
      <div className="mec-ranking-eixo" aria-hidden="true"><span>Empresa / posição</span>
        <div>{[0, 1, 2, 3, 4, 5].map(n => <span key={n}>{n}</span>)}</div><span>Média / 5</span></div>
      <ol className="mec-ranking-lista">
        {ranking.itens.map(item => {
          const nota = item.media === null ? null : Number(item.media);
          const avaliada = item.quantidade > 0 && nota !== null && Number.isFinite(nota) && nota >= 0 && nota <= 5;
          const media = avaliada ? item.media!.replace(".", ",") : null;
          return <li key={item.fornecedor_codigo} className="mec-ranking-linha">
            <div className="mec-ranking-empresa">
              <span className={item.posicao === null ? "mec-ranking-posicao sem-nota" : "mec-ranking-posicao"}>
                {item.posicao === null ? "—" : `${item.posicao}º`}
              </span>
              <div><strong>{item.razao_social || item.fornecedor_codigo}</strong>
                <small>{item.fornecedor_codigo}{item.posicao === null ? " · Sem posição" : ""}</small>
                {aoVerHistorico && item.empresa_id && <button type="button" className="mec-av-secundario mec-ranking-historico-botao"
                  aria-label={`Ver histórico de ${item.razao_social || item.fornecedor_codigo}`} onClick={() => aoVerHistorico(item.empresa_id!)}>Ver histórico</button>}
              </div>
            </div>
            <div className="mec-ranking-trilho" aria-hidden="true">
              {avaliada ? <div className="mec-ranking-barra" style={{ width: `${nota! * 20}%` }} />
                : <span className="mec-ranking-sem-notas">Sem avaliações</span>}
            </div>
            <div className="mec-ranking-nota">
              <strong>{media === null ? "Sem notas" : <>{media}<span className="mec-av-sr"> de 5</span></>}</strong>
              <small>{item.quantidade} {item.quantidade === 1 ? "avaliação" : "avaliações"}</small>
            </div>
          </li>;
        })}
      </ol>
    </> : <p className="mec-av-vazio">Nenhum fornecedor encontrado.</p>}
    <p className="mec-ranking-rodape">As posições correspondem à classificação geral, inclusive durante uma busca. Empresas sem avaliações ficam sem posição. As notas de clientes e da administração são consultadas separadamente.</p>
  </section>;
}
