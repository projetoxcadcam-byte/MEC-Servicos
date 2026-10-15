import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { erroJanela, numeroValido } from "../janelas/janelasPortal";

export const SITUACOES = ["todas", "enviada", "aceita", "recusada", "expirada", "cancelada"] as const;
export const ORDENACOES = ["recentes", "valor", "prazo"] as const;
export type FiltrosCotacoes = { solicitacao: string; cotacao: string; situacao: string; ordenacao: string };
export type CotacaoConsulta = {
  id: number; solicitacao_id: number; empresa_cliente_id: number; empresa_fornecedora_id: number; status: string;
  valor_total: string; prazo_dias: number; validade_dias: number; criada_em: string; vencimento_em: string; encerrada_em: string | null;
  solicitacao_status: string; processo_nome: string; material_nome: string; quantidade: number;
  contratacao_id: number | null; ordem_servico_id: number | null;
  analise_cliente:string|null;pode_analisar:boolean;versao_preco:string|null;
};
export type PaginaCotacoes = { contexto: string; empresa_id: number; consultado_em: string; total: number;
  por_status: Record<string, number>; deslocamento: number; limite: number; itens: CotacaoConsulta[] };
export type DetalheCotacao = { contexto: string; empresa_id: number; consultado_em: string; item: CotacaoConsulta };
export const filtrosValidos = (f: FiltrosCotacoes) => numeroValido(f.solicitacao) && numeroValido(f.cotacao) &&
  SITUACOES.some(s => s === f.situacao) && ORDENACOES.some(o => o === f.ordenacao);
const inteiro = (n: unknown): n is number => typeof n === "number" && Number.isSafeInteger(n) && n >= 0;
const id = (n: unknown) => inteiro(n) && n > 0;
const data = (s: unknown) => typeof s === "string" && Number.isFinite(Date.parse(s));
const opcional = (n: unknown) => n === null || id(n);
function itemValido(c: CotacaoConsulta, empresa: number) {
  return c && id(c.id) && id(c.solicitacao_id) && c.empresa_cliente_id === empresa && id(c.empresa_fornecedora_id) &&
    SITUACOES.slice(1).some(s => s === c.status) && Number.isFinite(Number(c.valor_total)) && Number(c.valor_total) > 0 &&
    (c.analise_cliente===null || ["publicada","aprovada_cliente","revisao_cliente","recusada_cliente","contratada"].includes(c.analise_cliente)) &&
    typeof c.pode_analisar==='boolean' && (c.versao_preco===null||/^[a-f0-9]{64}$/.test(c.versao_preco)) &&
    (!c.pode_analisar || (c.analise_cliente==='publicada'&&c.versao_preco!==null&&['enviada','aceita'].includes(c.status))) &&
    id(c.prazo_dias) && id(c.validade_dias) && id(c.quantidade) && data(c.criada_em) && data(c.vencimento_em) &&
    (c.encerrada_em === null || data(c.encerrada_em)) && typeof c.solicitacao_status === "string" &&
    typeof c.processo_nome === "string" && typeof c.material_nome === "string" && opcional(c.contratacao_id) && opcional(c.ordem_servico_id);
}
export function paginaValida(p: PaginaCotacoes, contexto: string, empresa: number, filtros: FiltrosCotacoes, inicio: number, limite: number) {
  return p && p.contexto === contexto && p.empresa_id === empresa && data(p.consultado_em) && inteiro(p.total) &&
    p.deslocamento === inicio && p.limite === limite && p.por_status && Object.values(p.por_status).every(inteiro) &&
    Object.values(p.por_status).reduce((a, b) => a + b, 0) === p.total &&
    Array.isArray(p.itens) && p.itens.length <= limite && p.itens.length <= Math.max(0, p.total - inicio) &&
    new Set(p.itens.map(c => c.id)).size === p.itens.length && p.itens.every(c => itemValido(c, empresa) &&
      (!filtros.solicitacao || c.solicitacao_id === Number(filtros.solicitacao)) && (!filtros.cotacao || c.id === Number(filtros.cotacao)) &&
      (filtros.situacao === "todas" || c.status === filtros.situacao));
}
export const detalheValido = (p: DetalheCotacao, contexto: string, empresa: number, cotacao: CotacaoConsulta) =>
  p && p.contexto === contexto && p.empresa_id === empresa && data(p.consultado_em) && itemValido(p.item, empresa) &&
  p.item.id === cotacao.id && p.item.solicitacao_id === cotacao.solicitacao_id;

export function useConsultaCotacoes<T>(url: string | null, chave: string, contexto: string, parametros: Record<string, string | number>, validar: (p: T) => boolean) {
  const [resposta, setResposta] = useState<{ chave: string; dados: T } | null>(null);
  const [falha, setFalha] = useState<{ chave: string; texto: string } | null>(null);
  const params = JSON.stringify(parametros);
  useEffect(() => {
    const controle = new AbortController(); setResposta(null); setFalha(null);
    if (url) void api.get<T>(url, { params: JSON.parse(params), headers: { "X-MEC-Cotacoes-Contexto": contexto }, signal: controle.signal, timeout: 20_000 })
      .then(({ data }) => {
        if (controle.signal.aborted) return;
        if (!validar(data)) throw new Error("consulta_cotacoes_divergente");
        setResposta({ chave, dados: data });
      }).catch(e => {
        if (controle.signal.aborted) return;
        const r = (e as { response?: { status?: number; data?: { detail?: string } } }).response;
        const texto = e instanceof Error && e.message === "consulta_cotacoes_divergente" ? "A resposta não corresponde à sua consulta. Atualize ou entre novamente."
          : r?.status === 404 ? "Solicitação ou cotação não encontrada para sua empresa. Confira o número informado."
            : r?.status === 409 ? "O acesso mudou durante a consulta. Entre novamente." : erroJanela(e);
        setFalha({ chave, texto });
      });
    return () => controle.abort();
    // A chave inclui empresa, usuário, filtros, página, seleção e atualização.
    // O validador é o da fotografia que iniciou esta consulta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, chave, contexto, params]);
  const dados = url && resposta?.chave === chave ? resposta.dados : null;
  const erro = url && falha?.chave === chave ? falha.texto : "";
  return { dados, erro, carregando: !!url && !dados && !erro };
}
