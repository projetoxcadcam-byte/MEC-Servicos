import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { consultar, mensagem, raiz, type Ranking } from "./avaliacoesPortal";
import GraficoRanking from "./GraficoRanking";
import HistoricoFornecedorAdmin from "./HistoricoFornecedorAdmin";
import "./Avaliacoes.css";

const TAMANHO_PAGINA = 20;

export default function RankingAvaliacoesPage() {
  const { user } = useAuth();
  if (!user || user.role !== "admin") return <main className="mec-av"><p>Esta consulta está disponível somente para a administração.</p></main>;
  const contexto = `${user.usuario_id}:${user.role}:${user.empresa_id ?? 0}`;
  return <Conteudo key={contexto} contexto={contexto} />;
}

function Conteudo({ contexto }: { contexto: string }) {
  const [origem, setOrigem] = useState<"cliente" | "admin">("cliente");
  const [inicio, setInicio] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [busca, setBusca] = useState("");
  const [campoBusca, setCampoBusca] = useState("");
  const [empresaHistorico, setEmpresaHistorico] = useState<number | null>(null);
  const [resposta, setResposta] = useState<{ chave: string; dados: Ranking } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; mensagem: string } | null>(null);
  const chave = `${contexto}:${origem}:${inicio}:${revisao}:${busca}`;
  const ranking = resposta?.chave === chave ? resposta.dados : null;
  const erro = falha?.chave === chave ? falha.mensagem : "";

  useEffect(() => {
    const controle = new AbortController();
    setResposta(null); setFalha(null); setEmpresaHistorico(null);
    void consultar<Ranking>(raiz("admin") + "/ranking", contexto, controle.signal,
      { origem, inicio, limite: TAMANHO_PAGINA, busca })
      .then(dados => { if (!controle.signal.aborted) setResposta({ chave, dados }); })
      .catch(e => { if (!controle.signal.aborted) setFalha({ chave, mensagem: mensagem(e) }); });
    return () => controle.abort();
  }, [contexto, origem, inicio, busca, chave]);

  return <main className="mec-av"><header className="mec-av-cabecalho"><div>
    <p className="mec-av-sobre">Administração · Qualidade do serviço</p><h1>Reputação e ranking</h1>
    <p>Compare as notas de cada empresa fornecedora no gráfico. Consulta exclusiva da administração.</p>
  </div><Link className="mec-av-link" to="/admin/avaliacoes">Consultar avaliações</Link></header>
    <div className="mec-av-abas" aria-label="Origem das avaliações">
      <button type="button" aria-pressed={origem === "cliente"} onClick={() => { setOrigem("cliente"); setInicio(0); }}>Notas de clientes</button>
      <button type="button" aria-pressed={origem === "admin"} onClick={() => { setOrigem("admin"); setInicio(0); }}>Notas da administração</button>
      <button type="button" className="mec-av-secundario" onClick={() => setRevisao(v => v + 1)}>Atualizar</button>
    </div>
    <form className="mec-av-filtros mec-ranking-busca" onSubmit={e => {
      e.preventDefault(); setBusca(campoBusca.trim()); setInicio(0); setEmpresaHistorico(null); setRevisao(v => v + 1);
    }}>
      <label>Buscar empresa<input value={campoBusca} onChange={e => setCampoBusca(e.target.value)} maxLength={160} placeholder="Nome, F-1 ou número da empresa" /></label>
      <button type="submit">Buscar</button><button type="button" className="mec-av-secundario" onClick={() => {
        setCampoBusca(""); setBusca(""); setInicio(0); setEmpresaHistorico(null); setRevisao(v => v + 1);
      }}>Limpar busca</button>
    </form>
    <p className="mec-av-aviso">A classificação considera a média da nota e, em caso de empate, a quantidade de avaliações. A escolha do fornecedor continua sendo realizada pela administração.</p>
    {erro && <p role="alert" className="mec-av-erro">{erro}</p>}
    {!ranking && !erro && <p role="status">Consultando reputação…</p>}
    {ranking && <>
      <div className="mec-ranking-pagina">
        <p>{ranking.total} {ranking.total === 1 ? "empresa fornecedora" : "empresas fornecedoras"}{busca ? ` ${ranking.total === 1 ? "encontrada" : "encontradas"} de ${ranking.total_fornecedores}` : ""} · até {TAMANHO_PAGINA} por página</p>
        <nav className="mec-av-paginacao" aria-label="Páginas do ranking">
          <button type="button" disabled={inicio === 0} onClick={() => setInicio(v => Math.max(0, v - TAMANHO_PAGINA))}>Anterior</button>
          <span>{ranking.total ? `${inicio + 1}–${Math.min(inicio + TAMANHO_PAGINA, ranking.total)} de ${ranking.total}` : "0 resultados"}</span>
          <button type="button" disabled={inicio + TAMANHO_PAGINA >= ranking.total} onClick={() => setInicio(v => v + TAMANHO_PAGINA)}>Próxima</button>
        </nav>
      </div>
      <GraficoRanking ranking={ranking} aoVerHistorico={setEmpresaHistorico} />
      {!!ranking.itens.length && <details className="mec-ranking-dados"><summary>Ver tabela de notas e posições</summary>
        <div className="mec-av-tabela"><table><caption className="mec-av-sr">{origem === "cliente" ? "Notas de clientes" : "Notas da administração"} — página atual do ranking</caption>
          <thead><tr><th scope="col">Posição</th><th scope="col">Fornecedor</th><th scope="col">Média / 5</th><th scope="col">Avaliações</th></tr></thead>
          <tbody>{ranking.itens.map(i => <tr key={i.fornecedor_codigo}><td>{i.posicao === null ? "Sem posição" : `${i.posicao}º`}</td>
            <td>{i.razao_social ? `${i.razao_social} · ${i.fornecedor_codigo}` : i.fornecedor_codigo}</td>
            <td>{i.media === null ? "Sem notas" : i.media.replace(".", ",")}</td><td>{i.quantidade}</td></tr>)}</tbody>
        </table></div>
      </details>}
    </>}
    {ranking && empresaHistorico !== null && <HistoricoFornecedorAdmin key={`${contexto}:${empresaHistorico}`} empresaId={empresaHistorico} aoFechar={() => setEmpresaHistorico(null)} />}
  </main>;
}
