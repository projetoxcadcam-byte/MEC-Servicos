import { useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { consultar, dataNota, mensagem, raiz, type HistoricoFornecedor, type Nota } from "./avaliacoesPortal";
import "./RankingAdministrativo.css";

export default function HistoricoFornecedorAdmin({ empresaId, aoFechar }: { empresaId: number; aoFechar: () => void }) {
  const { user } = useAuth();
  if (!user || user.role !== "admin") return null;
  const contexto = `${user.usuario_id}:${user.role}:${user.empresa_id ?? 0}`;
  return <Conteudo key={`${contexto}:${empresaId}`} empresaId={empresaId} contexto={contexto} aoFechar={aoFechar} />;
}

function NotaHistorica({ nota, origem }: { nota: Nota | null; origem: string }) {
  return <div className="mec-av-nota"><h3>{origem}</h3>{nota ? <>
    <p><strong>{nota.nota} / 5</strong> · {dataNota(nota.criada_em)}</p>
    {nota.historica && <p className="mec-av-data">Histórico anterior</p>}
    {nota.autor && <p className="mec-av-data">Registrada por {nota.autor.nome}</p>}
    {nota.comentario && <p className="mec-av-comentario">{nota.comentario}</p>}
  </> : <p className="mec-av-vazio">Ainda não registrada</p>}</div>;
}

function Conteudo({ empresaId, contexto, aoFechar }: { empresaId: number; contexto: string; aoFechar: () => void }) {
  const [inicio, setInicio] = useState(0);
  const [revisao, setRevisao] = useState(0);
  const [resposta, setResposta] = useState<{ chave: string; dados: HistoricoFornecedor } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; mensagem: string } | null>(null);
  const chave = `${contexto}:${empresaId}:${inicio}:${revisao}`;
  const dados = resposta?.chave === chave ? resposta.dados : null;
  const erro = falha?.chave === chave ? falha.mensagem : "";
  const ref = useRef<HTMLElement>(null);
  const titulo = useId();
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth", block: "start" }); ref.current?.focus({ preventScroll: true }); }, []);
  useEffect(() => {
    const controle = new AbortController(); setResposta(null); setFalha(null);
    void consultar<HistoricoFornecedor>(`${raiz("admin")}/fornecedores/${empresaId}/historico`, contexto,
      controle.signal, { inicio, limite: 20 }).then(d => {
        if (controle.signal.aborted) return;
        if (d.fornecedor.empresa_id !== empresaId) throw new Error("Contexto de acesso alterado.");
        setResposta({ chave, dados: d });
      }).catch(e => { if (!controle.signal.aborted) setFalha({ chave, mensagem: mensagem(e) }); });
    return () => controle.abort();
  }, [empresaId, contexto, inicio, chave]);
  return <section className="mec-av-detalhe mec-historico-fornecedor" ref={ref} tabIndex={-1} aria-labelledby={titulo}>
    <header className="mec-av-linha"><div><h2 id={titulo}>Histórico de avaliações · F-{empresaId}</h2>
      {dados && <p>{dados.fornecedor.razao_social}</p>}</div><div className="mec-av-linha">
        <button type="button" className="mec-av-secundario" onClick={() => setRevisao(v => v + 1)}>Atualizar histórico</button>
        <button type="button" className="mec-av-secundario" onClick={aoFechar}>Fechar histórico</button>
      </div></header>
    <p className="mec-av-aviso">Consulta exclusiva do ADM. As médias consideram todas as avaliações da empresa, separadas por origem. Os comentários permanecem restritos ao autor e à administração.</p>
    {erro && <p role="alert" className="mec-av-erro">{erro}</p>}
    {!dados && !erro && <p role="status">Consultando o histórico do fornecedor…</p>}
    {dados && <>
      <div className="mec-historico-resumo">{([ ["Clientes", dados.fornecedor.notas_cliente], ["Administração", dados.fornecedor.notas_admin] ] as const).map(([origem, notas]) =>
        <div key={origem}><h3>{origem}</h3><p><strong>{notas.media === null ? "Sem notas" : `${notas.media.replace(".", ",")} / 5`}</strong> · {notas.quantidade} {notas.quantidade === 1 ? "avaliação" : "avaliações"}</p></div>)}</div>
      <p className="mec-av-contagem">{dados.total} {dados.total === 1 ? "contratação com avaliação" : "contratações com avaliação"} · mais recentes por número de contratação</p>
      {dados.itens.map(item => <article className="mec-historico-registro" key={item.contratacao_id}>
        <div className="mec-av-linha"><div><h3>Contratação #{item.contratacao_id} · {item.ordem_servico_id ? `OS #${item.ordem_servico_id}` : "Sem OS"}</h3>
          <p>{item.fornecedor_codigo} · {item.cliente_codigo}</p></div>
          <Link className="mec-av-link" to={`/admin/avaliacoes?contratacao=${item.contratacao_id}`}>Abrir avaliação da contratação #{item.contratacao_id}</Link></div>
        <div className="mec-av-notas"><NotaHistorica nota={item.cliente} origem="Nota do cliente" /><NotaHistorica nota={item.admin} origem="Nota da administração" /></div>
      </article>)}
      {!dados.itens.length && <p className="mec-av-vazio">Nenhuma avaliação registrada para este fornecedor nesta página.</p>}
      <nav className="mec-av-paginacao" aria-label="Páginas do histórico do fornecedor">
        <button type="button" disabled={inicio === 0} onClick={() => setInicio(v => Math.max(0, v - 20))}>Anterior</button>
        <span>{dados.total ? `${Math.min(inicio + 1, dados.total)}–${Math.min(inicio + 20, dados.total)} de ${dados.total}` : "0 resultados"}</span>
        <button type="button" disabled={inicio + 20 >= dados.total} onClick={() => setInicio(v => v + 20)}>Próxima</button>
      </nav>
    </>}
  </section>;
}
