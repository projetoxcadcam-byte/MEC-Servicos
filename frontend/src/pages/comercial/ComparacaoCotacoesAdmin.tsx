import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import GraficoComparacaoAdmin from "./GraficoComparacaoAdmin";
import HistoricoFornecedorAdmin from "../avaliacoes/HistoricoFornecedorAdmin";
import "../avaliacoes/Avaliacoes.css";
import "./ComparacaoCotacoesAdmin.css";

type Props = { solicitacaoId: number; versao: string; ocupado: boolean; aoConferir: (cotacao: number) => void };
type Ordenacao = "valor" | "prazo" | "nota_cliente" | "nota_admin";
type Escopo = "disponiveis" | "todas";
export type Notas = { quantidade: number; media: string | null };
export type Proposta = { cotacao_id: number; empresa_fornecedora_id: number; fornecedor: string;
  valor_total: string; prazo_dias: number; vence_em: string; status: string; pode_decidir: boolean;
  notas_cliente: Notas; notas_admin: Notas };
type Comparacao = { contexto: string; solicitacao_id: number; versao: string; consultado_em: string;
  total: number; cotacoes_total: number; cotacoes_disponiveis: number; menor_valor_disponivel: string | null;
  menor_prazo_disponivel: number | null; deslocamento: number; limite: number; itens: Proposta[] };
const moeda = (v: string) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const situacoes: Record<string, string> = { enviada: "Aguardando decisão", aceita: "Aceita", recusada: "Recusada", expirada: "Expirada", cancelada: "Cancelada" };
function NotasFornecedor({ notas }: { notas: Notas }) {
  return <>{notas.media === null ? <span>Sem avaliações</span> : <><strong>{notas.media.replace(".", ",")} / 5</strong><small>{notas.quantidade} avaliação(ões)</small></>}</>;
}
function mensagem(erro: unknown) {
  const e = erro as { response?: { status?: number; data?: { detail?: string } } };
  if (e.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (e.response?.status === 403) return "A comparação está disponível somente para a administração.";
  if (e.response?.data?.detail === "contexto_comercial_alterado" || erro instanceof Error && erro.message === "contexto_comercial_alterado")
    return "O perfil foi alterado em outra aba. Entre novamente para consultar a comparação.";
  if (e.response?.status === 404) return "Solicitação não encontrada. Atualize a análise.";
  return "Não foi possível consultar a comparação. Confira a conexão e tente novamente.";
}

export default function ComparacaoCotacoesAdmin(props: Props) {
  const { user } = useAuth();
  if (!user || user.role !== "admin") return null;
  const contexto = `${user.usuario_id}:${user.role}:${user.empresa_id ?? 0}`;
  return <Conteudo key={`${contexto}:${props.solicitacaoId}:${props.versao}`} {...props} contexto={contexto} />;
}

function Conteudo({ solicitacaoId, versao, ocupado, aoConferir, contexto }: Props & { contexto: string }) {
  const [aberta, setAberta] = useState(false);
  const [ordenacao, setOrdenacao] = useState<Ordenacao>("valor");
  const [escopo, setEscopo] = useState<Escopo>("disponiveis");
  const [deslocamento, setDeslocamento] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [historico, setHistorico] = useState<{ empresa: number; cotacao: number; abertura: number } | null>(null);
  const botaoHistorico = useRef<HTMLButtonElement | null>(null);
  const aberturaHistorico = useRef(0);
  const [resposta, setResposta] = useState<{ chave: string; dados: Comparacao } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; mensagem: string } | null>(null);
  const chave = `${contexto}:${solicitacaoId}:${versao}:${aberta}:${ordenacao}:${escopo}:${deslocamento}:${revisao}`;
  const dados = resposta?.chave === chave ? resposta.dados : null;
  const erro = falha?.chave === chave ? falha.mensagem : "";
  const carregando = aberta && !dados && !erro;
  useEffect(() => { if (ocupado) setHistorico(null); }, [ocupado]);
  useEffect(() => {
    setHistorico(null);
    if (!aberta) { setResposta(null); setFalha(null); return; }
    const controle = new AbortController(); setResposta(null); setFalha(null);
    void api.get<Comparacao>(`/administracao/comercial/solicitacoes/${solicitacaoId}/comparacao`, {
      params: { ordenacao, escopo, deslocamento, limite: 20 }, signal: controle.signal, timeout: 20_000,
      headers: { "X-MEC-COMERCIAL-CONTEXTO": contexto },
    }).then(({ data }) => {
      if (controle.signal.aborted) return;
      if (data.contexto !== contexto || data.solicitacao_id !== solicitacaoId) throw new Error("contexto_comercial_alterado");
      setResposta({ chave, dados: data });
    }).catch(e => { if (!controle.signal.aborted) setFalha({ chave, mensagem: mensagem(e) }); });
    return () => controle.abort();
  }, [aberta, solicitacaoId, contexto, ordenacao, escopo, deslocamento, chave]);
  const alterada = dados !== null && dados.versao !== versao;
  const historicoAtual = !ocupado && !alterada && dados?.itens.some(q => q.cotacao_id === historico?.cotacao && q.empresa_fornecedora_id === historico.empresa) ? historico : null;
  function abrirHistorico(q: Proposta, botao: HTMLButtonElement) {
    if (ocupado || alterada || !dados?.itens.some(item => item.cotacao_id === q.cotacao_id && item.empresa_fornecedora_id === q.empresa_fornecedora_id)) return;
    botaoHistorico.current = botao;
    setHistorico({ empresa: q.empresa_fornecedora_id, cotacao: q.cotacao_id, abertura: ++aberturaHistorico.current });
  }
  function fecharHistorico() {
    setHistorico(null);
    const botao = botaoHistorico.current;
    if (botao?.isConnected && !botao.disabled) {
      botao.scrollIntoView({ behavior: "smooth", block: "center" });
      botao.focus({ preventScroll: true });
    }
  }
  return <section className="com47" aria-label="Comparação administrativa de cotações">
    <div className="com47-cabecalho"><div><h3>Comparação de cotações</h3><p>Preço, prazo e gráfico de avaliações dos fornecedores.</p></div>
      <button type="button" disabled={ocupado} aria-expanded={aberta} onClick={() => setAberta(v => !v)}>{aberta ? "Fechar comparação" : "Comparar propostas"}</button></div>
    {aberta && <>
      <p className="com47-nota">As médias consideram todas as notas recebidas pelo fornecedor, separadas por origem. A escolha e a confirmação da cotação são realizadas pelo ADM.</p>
      <div className="com47-filtros"><label>Ordenar por<select aria-label="Ordenação da comparação" disabled={ocupado} value={ordenacao} onChange={e => { setOrdenacao(e.target.value as Ordenacao); setDeslocamento(0); }}>
        <option value="valor">Menor valor total</option><option value="prazo">Menor prazo de execução</option><option value="nota_cliente">Maior nota de clientes</option><option value="nota_admin">Maior nota da administração</option></select></label>
        <label>Propostas<select aria-label="Propostas da comparação" disabled={ocupado} value={escopo} onChange={e => { setEscopo(e.target.value as Escopo); setDeslocamento(0); }}><option value="disponiveis">Disponíveis para decisão</option><option value="todas">Todas, incluindo histórico</option></select></label>
        <button type="button" disabled={ocupado || carregando} onClick={() => setRevisao(v => v + 1)}>Atualizar comparação</button><Link to="/admin/ranking">Consultar ranking completo</Link></div>
      {erro && <p role="alert" className="com47-erro">{erro}</p>}{carregando && <p role="status">Consultando propostas e avaliações…</p>}
      {dados && <>
        {alterada && <p role="alert" className="com47-erro">As propostas mudaram desde a abertura da análise. Use Atualizar no início da página e confira os dados antes de decidir.</p>}
        <div className="com47-resumo"><span><strong>{dados.cotacoes_disponiveis}</strong> cotações disponíveis de {dados.cotacoes_total}</span>
          <span>Menor valor disponível: <strong>{dados.menor_valor_disponivel === null ? "—" : moeda(dados.menor_valor_disponivel)}</strong></span>
          <span>Menor prazo disponível: <strong>{dados.menor_prazo_disponivel === null ? "—" : `${dados.menor_prazo_disponivel} dias`}</strong></span></div>
        <GraficoComparacaoAdmin itens={dados.itens} aoVerHistorico={abrirHistorico} historicoBloqueado={ocupado || alterada} />
        {!dados.itens.length ? <p>{escopo === "disponiveis" ? "Nenhuma cotação disponível para decisão nesta página. Selecione Todas, incluindo histórico para consultar as propostas registradas." : "Nenhuma cotação encontrada nesta página."}</p> :
          <div className="com47-tabela"><table><thead><tr><th>Cotação / fornecedor</th><th>Valor total</th><th>Execução</th><th>Validade / situação</th><th>Notas de clientes</th><th>Notas da administração</th><th>Consulta</th></tr></thead>
            <tbody>{dados.itens.map(q => <tr key={q.cotacao_id}><td><strong>Cotação #{q.cotacao_id}</strong><small>{q.fornecedor} · F-{q.empresa_fornecedora_id}</small></td><td><strong>{moeda(q.valor_total)}</strong></td><td>{q.prazo_dias} dias</td>
              <td>{new Date(q.vence_em).toLocaleString("pt-BR")}<small>{situacoes[q.status] ?? q.status}{!q.pode_decidir && q.status === "enviada" ? " · Somente consulta" : ""}</small></td>
              <td><NotasFornecedor notas={q.notas_cliente} /></td><td><NotasFornecedor notas={q.notas_admin} /></td><td><div className="com56-consultas">
                <button type="button" disabled={ocupado || alterada} onClick={() => { setHistorico(null); aoConferir(q.cotacao_id); }}>Conferir cotação #{q.cotacao_id}</button>
                <button type="button" className="com56-ver-historico" disabled={ocupado || alterada}
                  aria-label={`Ver histórico do fornecedor F-${q.empresa_fornecedora_id} da cotação #${q.cotacao_id}`}
                  onClick={e => abrirHistorico(q, e.currentTarget)}>Ver histórico do fornecedor</button>
              </div></td></tr>)}</tbody></table></div>}
        <nav className="com47-paginacao" aria-label="Páginas da comparação"><button type="button" disabled={ocupado || deslocamento === 0} onClick={() => setDeslocamento(v => Math.max(0, v - 20))}>Anterior</button>
          <span>{dados.total ? `${Math.min(deslocamento + 1, dados.total)}–${Math.min(deslocamento + 20, dados.total)} de ${dados.total}` : "0 resultados"}</span>
          <button type="button" disabled={ocupado || deslocamento + 20 >= dados.total} onClick={() => setDeslocamento(v => v + 20)}>Próxima</button></nav>
        <small className="com47-atualizacao">Consulta em {new Date(dados.consultado_em).toLocaleString("pt-BR")}.</small>
        {historicoAtual && <div className="mec-av com56-historico">
          <div className="mec-av-linha"><p>Fornecedor F-{historicoAtual.empresa} da cotação #{historicoAtual.cotacao} · Solicitação #{solicitacaoId}</p>
            <button type="button" className="mec-av-secundario" onClick={fecharHistorico}>Voltar à comparação</button></div>
          <p className="com56-contexto">O histórico é consultado ao abrir. Use Atualizar comparação para consultar novamente as médias junto das propostas.</p>
          <HistoricoFornecedorAdmin key={`${contexto}:${historicoAtual.empresa}:${historicoAtual.abertura}`}
            empresaId={historicoAtual.empresa} aoFechar={fecharHistorico} />
        </div>}
      </>}
    </>}
  </section>;
}
