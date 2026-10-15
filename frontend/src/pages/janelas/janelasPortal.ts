import { useEffect, useState } from "react";
import { api } from "../../services/api";

export const numeroValido = (v: string) => !v || /^[1-9]\d{0,12}$/.test(v);
export function numeroUrl(v: string | null) { return v && numeroValido(v) ? v : ""; }
export const dataJanela = (v: string | null | undefined) => v ? new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(v) ? v : v + "Z").toLocaleString("pt-BR") : "Sem registro";
export function erroJanela(e: unknown): string {
  const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response;
  if (r?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (r?.status === 403) return r.data?.detail === "arquivo_aguarda_liberacao_administrativa"
    ? "Os documentos aguardam revisão e liberação da administração."
    : "Este acesso não pode consultar o registro. Atualize a tela ou entre novamente.";
  if (r?.status === 404) return "Registro não encontrado. Atualize a lista.";
  return "Não foi possível consultar o servidor. Confira a conexão e tente novamente.";
}

export function useConsultaJanela<T>(url: string | null, chave: string, parametros: Record<string, string | number | boolean> = {}) {
  const [resposta, setResposta] = useState<{ chave: string; dados: T } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; texto: string } | null>(null);
  const params = JSON.stringify(parametros);
  useEffect(() => {
    const controle = new AbortController(); setResposta(null); setFalha(null);
    if (url) void api.get<T>(url, { params: JSON.parse(params), signal: controle.signal, timeout: 20_000 })
      .then(({ data }) => { if (!controle.signal.aborted) setResposta({ chave, dados: data }); })
      .catch(e => { if (!controle.signal.aborted) setFalha({ chave, texto: erroJanela(e) }); });
    return () => controle.abort();
  }, [url, chave, params]);
  const dados = url && resposta?.chave === chave ? resposta.dados : null;
  const erro = url && falha?.chave === chave ? falha.texto : "";
  return { dados, erro, carregando: !!url && !dados && !erro };
}
