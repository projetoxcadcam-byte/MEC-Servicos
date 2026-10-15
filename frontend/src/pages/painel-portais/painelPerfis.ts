import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { erroJanela } from "../janelas/janelasPortal";

export type PerfilPainel = "cliente" | "fornecedor";
type Contagem = { total: number; por_status: Record<string, number> };
export type PainelPerfis = {
  contexto: string; perfil: PerfilPainel; empresa_id: number; consultado_em: string;
  solicitacoes: Contagem | null; cotacoes: Contagem; contratacoes: Contagem; ordens: Contagem; oportunidades: number | null;
  solicitacoes_recentes: { id: number; status: string; processo_nome: string; material_nome: string; quantidade: number; criada_em: string }[];
  cotacoes_recentes: { id: number; solicitacao_id: number; status: string; valor_total: string; criada_em: string }[];
  ordens_recentes: { id: number; solicitacao_id: number; contratacao_id: number; status: string; processo_nome: string; material_nome: string;
    etapa_atual: string | null; etapa_atual_em: string | null; criada_em: string }[];
};

const inteiro = (v: unknown) => typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const dataValida = (v: unknown) => typeof v === "string" && Number.isFinite(Date.parse(v));
function contagemValida(c: Contagem | null): boolean {
  return !!c && inteiro(c.total) && !!c.por_status && typeof c.por_status === "object" &&
    Object.values(c.por_status).every(inteiro) && Object.values(c.por_status).reduce((a, b) => a + b, 0) === c.total;
}
function listaValida<T>(v: T[], conferir: (item: T) => boolean) {
  return Array.isArray(v) && v.length <= 5 && v.every(item => item && conferir(item));
}
function painelValido(p: PainelPerfis, contexto: string, perfil: PerfilPainel, empresa: number) {
  return p && p.contexto === contexto && p.perfil === perfil && p.empresa_id === empresa && dataValida(p.consultado_em) &&
    [p.cotacoes, p.contratacoes, p.ordens].every(contagemValida) &&
    (perfil === "cliente" ? contagemValida(p.solicitacoes) && p.oportunidades === null : p.solicitacoes === null && inteiro(p.oportunidades)) &&
    listaValida(p.ordens_recentes, o => inteiro(o.id) && o.id > 0 && inteiro(o.solicitacao_id) && o.solicitacao_id > 0 &&
      inteiro(o.contratacao_id) && o.contratacao_id > 0 && typeof o.status === "string" && typeof o.processo_nome === "string" &&
      typeof o.material_nome === "string" && dataValida(o.criada_em) && (o.etapa_atual === null || typeof o.etapa_atual === "string") &&
      (o.etapa_atual_em === null || dataValida(o.etapa_atual_em))) &&
    listaValida(p.solicitacoes_recentes, s => inteiro(s.id) && s.id > 0 && typeof s.status === "string" &&
      typeof s.processo_nome === "string" && typeof s.material_nome === "string" && inteiro(s.quantidade) && s.quantidade > 0 && dataValida(s.criada_em)) &&
    listaValida(p.cotacoes_recentes, c => inteiro(c.id) && c.id > 0 && inteiro(c.solicitacao_id) && c.solicitacao_id > 0 &&
      typeof c.status === "string" && Number.isFinite(Number(c.valor_total)) && Number(c.valor_total) > 0 && dataValida(c.criada_em)) &&
    (perfil === "cliente" ? p.cotacoes_recentes.length === 0 : p.solicitacoes_recentes.length === 0);
}

export function usePainelPerfis(perfil: PerfilPainel, empresa: number, contexto: string, atualizacao: number) {
  const chave = `${contexto}:${perfil}:${empresa}:${atualizacao}`;
  const [resposta, setResposta] = useState<{ chave: string; dados: PainelPerfis } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; texto: string } | null>(null);
  useEffect(() => {
    const controle = new AbortController(); setResposta(null); setFalha(null);
    if (empresa > 0 && contexto) void api.get<PainelPerfis>(`/portal-${perfil}/painel`, {
      params: { [perfil === "cliente" ? "empresa_cliente_id" : "empresa_fornecedora_id"]: empresa },
      headers: { "X-MEC-Painel-Contexto": contexto }, signal: controle.signal, timeout: 20_000,
    }).then(({ data }) => {
      if (controle.signal.aborted) return;
      if (!painelValido(data, contexto, perfil, empresa)) throw new Error("painel_divergente");
      setResposta({ chave, dados: data });
    }).catch(e => {
      if (!controle.signal.aborted) setFalha({ chave, texto: e instanceof Error && e.message === "painel_divergente"
        ? "A resposta não corresponde ao seu painel. Atualize ou entre novamente."
        : (e as { response?: { status?: number } }).response?.status === 409
          ? "O acesso mudou durante a consulta. Entre novamente."
          : erroJanela(e) });
    });
    return () => controle.abort();
  }, [perfil, empresa, contexto, chave]);
  const dados = empresa > 0 && resposta?.chave === chave ? resposta.dados : null;
  const erro = empresa > 0 && falha?.chave === chave ? falha.texto : "";
  return { dados, erro, carregando: empresa > 0 && !dados && !erro };
}
