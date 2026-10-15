import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { useAuth } from "../../auth/AuthContext";
import { dataIntermediacao, mensagemIntermediacao, rotulosAcao, statusVisivel, type ConsultaIntermediacao } from "./intermediacaoPortal";
import "./Intermediacao.css";

export default function IntermediacaoConsulta({ ordemId, perfil, revisao }: { ordemId: number; perfil: "cliente" | "fornecedor"; revisao: number }) {
  const { user } = useAuth(); const empresa = user?.role === perfil ? user.id : 0;
  const [dados, setDados] = useState<ConsultaIntermediacao | null>(null); const [erro, setErro] = useState(""); const [carregando, setCarregando] = useState(false);
  useEffect(() => {
    const controle = new AbortController(); let vigente = true;
    setDados(null); setErro(""); setCarregando(Boolean(ordemId && empresa));
    if (!ordemId || !empresa) return () => controle.abort();
    const params = perfil === "cliente" ? { empresa_cliente_id: empresa } : { empresa_fornecedora_id: empresa };
    void api.get<ConsultaIntermediacao>(`/portal-${perfil}/intermediacao/${ordemId}`, { params, signal: controle.signal, timeout: 20_000 })
      .then(({ data }) => { if (vigente && data.ordem_servico_id === ordemId) setDados(data); })
      .catch((falha: unknown) => { if (vigente && !controle.signal.aborted) setErro(mensagemIntermediacao(falha)); })
      .finally(() => { if (vigente) setCarregando(false); });
    return () => { vigente = false; controle.abort(); };
  }, [ordemId, perfil, empresa, revisao]);
  if (!ordemId) return null;
  return <section className="p31-panel" aria-busy={carregando}><h2>Andamento administrativo · OS #{ordemId}</h2>
    {carregando ? <p role="status">Carregando andamento…</p> : erro ? <p role="alert">{erro}</p> : dados && <>
      <p><strong>{statusVisivel(dados.status)}</strong></p><p>A administração coordena o material, a coleta, a avaliação das peças e a entrega final.</p>
      {!dados.status ? <p>Sem ciclo administrativo D31. Consulte abaixo os registros anteriores de entrega.</p> : <ol className="p31-timeline">{dados.historico.slice().reverse().map((item, indice) =>
        <li key={`${item.criado_em}:${indice}`}><strong>{rotulosAcao[item.acao]}</strong><p>{statusVisivel(item.status_resultante)} · {dataIntermediacao(item.criado_em)}</p></li>)}</ol>}
    </>}
  </section>;
}
