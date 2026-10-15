import { useState } from "react";
import { ArrowRight, BriefcaseBusiness, CircleCheck, ClipboardList, FileText, RefreshCw, Search, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { dataJanela } from "../janelas/janelasPortal";
import { rotuloOrdem } from "../ordens/ordensPortal";
import { rotuloEtapa } from "../producao/producaoPortal";
import { usePainelPerfis, type PerfilPainel } from "./painelPerfis";
import "./PainelPortal.css";

const situacao = (v: string) => ({ aberta: "Aberta", encerrada: "Encerrada", cancelada: "Cancelada", enviada: "Em análise",
  aceita: "Aceita", recusada: "Recusada", expirada: "Expirada" }[v] ?? "Situação indisponível");
const dinheiro = (v: string) => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function PainelPortalPage({ perfil }: { perfil: PerfilPainel }) {
  const { user } = useAuth();
  const valido = user?.role === perfil && !!user.empresa_id && user.usuario_id > 0;
  const empresa = valido ? user.empresa_id! : 0;
  const contexto = valido ? `${user.usuario_id}:${user.role}:${empresa}` : "";
  const [atualizacao, setAtualizacao] = useState(0);
  const { dados, erro, carregando } = usePainelPerfis(perfil, empresa, contexto, atualizacao);
  const base = `/${perfil}`, cliente = perfil === "cliente";
  if (!valido) return <main className="pp58"><p role="alert">Entre como {perfil} para consultar o painel da sua empresa.</p></main>;
  const quantidade = (grupo: "solicitacoes" | "cotacoes" | "contratacoes" | "ordens", status: string) =>
    dados ? dados[grupo]?.por_status[status] ?? 0 : null;
  const cards = [
    { nome: cliente ? "Solicitações abertas" : "Oportunidades liberadas", valor: cliente ? quantidade("solicitacoes", "aberta") : dados?.oportunidades,
      detalhe: cliente ? "Pedidos da sua empresa" : "Compatíveis com seu cadastro e documentos", destino: "solicitacoes", Icone: cliente ? ClipboardList : Search },
    { nome: "Cotações em análise", valor: quantidade("cotacoes", "enviada"), detalhe: cliente ? "Propostas recebidas dentro da validade" : "Suas propostas dentro da validade", destino: "cotacoes", Icone: FileText },
    { nome: "Contratações ativas", valor: quantidade("contratacoes", "ativa"), detalhe: "Serviços contratados da sua empresa", destino: "contratacoes", Icone: BriefcaseBusiness },
    { nome: "OS abertas", valor: quantidade("ordens", "aberta"), detalhe: "Serviços ainda não iniciados", destino: "ordens-servico", Icone: ClipboardList },
    { nome: "OS em execução", valor: quantidade("ordens", "em_execucao"), detalhe: "Acompanhe as etapas de produção", destino: "producao", Icone: Wrench },
    { nome: "OS concluídas", valor: quantidade("ordens", "concluida"), detalhe: "Histórico dos serviços concluídos", destino: "ordens-servico", Icone: CircleCheck },
  ];
  return <main className="pp58" aria-busy={carregando}>
    <header className="pp58-cabecalho"><div><span className="pp58-selo">MEC · {cliente ? "Cliente" : "Fornecedor"}</span>
      <h1>Visão geral</h1><p>{cliente ? "Acompanhe seus pedidos e a execução dos seus serviços." : "Acompanhe suas oportunidades, propostas e produção."}</p></div>
      <button className="pp58-botao" disabled={carregando} onClick={() => setAtualizacao(v => v + 1)}><RefreshCw size={16} />Atualizar painel</button></header>
    {erro && <div className="pp58-erro" role="alert">{erro}</div>}
    {carregando && <p className="pp58-consulta" role="status">Consultando dados da sua empresa…</p>}
    <section className="pp58-cards" aria-label="Totais da empresa">{cards.map(({ nome, valor, detalhe, destino, Icone }) =>
      <Link className="pp58-card" to={`${base}/${destino}`} key={nome} aria-label={`${nome}: ${valor ?? "aguardando consulta"}`}>
        <div><span>{nome}</span><Icone size={20} aria-hidden="true" /></div><strong>{valor ?? "—"}</strong><small>{detalhe}</small>
        <span className="pp58-card-link">Abrir <ArrowRight size={14} aria-hidden="true" /></span></Link>)}</section>
    {dados && <><div className="pp58-resumo"><span>{dados.ordens.total} OS no histórico</span><span>{dados.cotacoes.total} cotações no histórico</span>
      <span>{quantidade("ordens", "cancelada")} OS canceladas</span><span>{quantidade("cotacoes", "expirada")} cotações expiradas</span></div>
      <div className="pp58-colunas"><section className="pp58-painel"><div className="pp58-titulo"><div><h2>Ordens mais recentes</h2><p>As últimas cinco OS da sua empresa.</p></div>
        <Link to={`${base}/ordens-servico`}>Ver todas <ArrowRight size={15} /></Link></div>
        {dados.ordens_recentes.length === 0 ? <p className="pp58-vazio">Sua empresa ainda não tem ordens de serviço.</p> :
          <ul className="pp58-lista pp58-ordens">{dados.ordens_recentes.map(o => <li key={o.id}><div className="pp58-linha"><strong>OS #{o.id}</strong>
            <span className={`pp58-status pp58-status-${o.status}`}>{rotuloOrdem(o.status)}</span></div><p>{o.processo_nome} · {o.material_nome}</p>
            <small>Solicitação #{o.solicitacao_id} · Contratação #{o.contratacao_id}</small><div className="pp58-etapa"><Wrench size={14} aria-hidden="true" />
              <span>{rotuloEtapa(o.etapa_atual)}{o.etapa_atual_em && <small>{dataJanela(o.etapa_atual_em)}</small>}</span></div>
            <Link className="pp58-acao" to={`${base}/producao?ordem=${o.id}`} aria-label={`Acompanhar produção da OS #${o.id}`}>Acompanhar produção <ArrowRight size={15} /></Link></li>)}</ul>}
      </section><section className="pp58-painel"><div className="pp58-titulo"><div><h2>{cliente ? "Solicitações mais recentes" : "Cotações mais recentes"}</h2>
        <p>{cliente ? "Os últimos cinco pedidos registrados." : "As últimas cinco propostas enviadas."}</p></div><Link to={`${base}/${cliente ? "solicitacoes" : "cotacoes"}`}>Ver todas <ArrowRight size={15} /></Link></div>
        {cliente ? (dados.solicitacoes_recentes.length === 0 ? <p className="pp58-vazio">Nenhuma solicitação registrada. Abra Solicitações para cadastrar seu pedido.</p> :
          <ul className="pp58-lista pp58-solicitacoes">{dados.solicitacoes_recentes.map(s => <li key={s.id}><div className="pp58-linha"><strong>Solicitação #{s.id}</strong>
            <span className="pp58-status">{situacao(s.status)}</span></div><p>{s.processo_nome} · {s.material_nome}</p><small>{s.quantidade} unidades · {dataJanela(s.criada_em)}</small></li>)}</ul>) :
          (dados.cotacoes_recentes.length === 0 ? <p className="pp58-vazio">Nenhuma proposta enviada. Abra Oportunidades para conferir os serviços liberados.</p> :
            <ul className="pp58-lista pp58-cotacoes">{dados.cotacoes_recentes.map(c => <li key={c.id}><div className="pp58-linha"><strong>Cotação #{c.id}</strong>
              <span className="pp58-status">{situacao(c.status)}</span></div><p>Solicitação #{c.solicitacao_id} · {dinheiro(c.valor_total)}</p><small>{dataJanela(c.criada_em)}</small>
              <Link className="pp58-acao" to={`${base}/cotacoes?solicitacao=${c.solicitacao_id}`} aria-label={`Ver cotação #${c.id}`}>Ver proposta <ArrowRight size={15} /></Link></li>)}</ul>)}
      </section></div><footer className="pp58-rodape">Totais de todos os registros da empresa. Consultado em {dataJanela(dados.consultado_em)}.</footer></>}
    <nav className="pp58-atalhos" aria-label="Atalhos do painel"><Link to={`${base}/arquivos-tecnicos`}>Arquivos técnicos</Link><Link to={`${base}/entregas`}>Entregas</Link>
      <Link to={`${base}/pagamentos`}>Pagamentos</Link><Link to={`${base}/avaliacoes`}>Avaliações</Link></nav>
  </main>;
}
