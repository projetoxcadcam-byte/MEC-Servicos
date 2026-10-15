import axios from "axios";

export type FiltroExtrato = "todos" | "recebimentos" | "repasses" | "estornos";
export type TipoMovimentoExtrato = "recebimento" | "repasse" | "estorno_recebimento" | "estorno_repasse";
export interface FiltrosExtrato {
  data_inicial: string | null; data_final: string | null; tipo: FiltroExtrato; busca: string; contratacao_id: number | null;
}
export interface ItemExtrato {
  tipo: TipoMovimentoExtrato; movimento_id: number; contratacao_id: number; ordem_servico_id: number | null;
  empresa_cliente_id: number; empresa_fornecedora_id: number; cliente: string; fornecedor: string;
  financeiro_status: "sem_controle" | "aberto" | "encerrado"; situacao_atual: "confirmado" | "estornado";
  data_utc: string; data_original_utc: string; estornado_em_utc: string | null; forma_pagamento: string;
  valor: string; efeito_liquido: string;
}
export interface ResumoExtrato {
  recebimentos_brutos: string; estornos_recebimentos: string; recebimentos_liquidos: string;
  repasses_brutos: string; estornos_repasses: string; repasses_liquidos: string;
  entradas: string; saidas: string; resultado_periodo: string; total_movimentos: number; total_contratacoes: number;
}
export interface ConsultaExtrato {
  filtros: FiltrosExtrato; resumo: ResumoExtrato; itens: ItemExtrato[]; total: number;
  deslocamento: number; limite: number; gerado_em: string;
}
export const tiposExtrato: Record<FiltroExtrato, string> = { todos: "Todos os movimentos", recebimentos: "Recebimentos e seus estornos",
  repasses: "Repasses e seus estornos", estornos: "Somente estornos" };
export const movimentosExtrato: Record<TipoMovimentoExtrato, string> = { recebimento: "Recebimento", repasse: "Repasse",
  estorno_recebimento: "Estorno de recebimento", estorno_repasse: "Estorno de repasse" };
export function periodoPadrao(): FiltrosExtrato {
  const agora = new Date(), ano = agora.getUTCFullYear(), mes = agora.getUTCMonth();
  const inicial = new Date(0), final = new Date(0);
  inicial.setUTCFullYear(ano, mes, 1); final.setUTCFullYear(ano, mes + 1, 0);
  return { data_inicial: inicial.toISOString().slice(0, 10), data_final: final.toISOString().slice(0, 10),
    tipo: "todos", busca: "", contratacao_id: null };
}
export function datasValidas(filtros: FiltrosExtrato) {
  const a = filtros.data_inicial ?? "", b = filtros.data_final ?? "";
  function validar(v: string) { if (!v) return true; const d = new Date(v + "T00:00:00Z");
    return /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(v) && v >= "0001-01-01" && v <= "9999-12-31" &&
      !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v; }
  return validar(a) && validar(b) && (!a || !b || a <= b);
}
export function parametrosExtrato(f: FiltrosExtrato) {
  return { ...f, data_inicial: f.data_inicial ?? "", data_final: f.data_final ?? "" };
}
export function dataExtrato(valor: string) {
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? "Data indisponível" : new Intl.DateTimeFormat("pt-BR", {
    timeZone: "UTC", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(d) + " UTC";
}
export function mensagemExtrato(erro: unknown) {
  if (axios.isAxiosError(erro)) {
    if (erro.response?.status === 401) return "Sua sessão terminou. Entre novamente para consultar o extrato.";
    if (erro.response?.status === 403) return "O extrato está disponível somente para a administração.";
    if (erro.response?.status === 422) return "Confira as datas, o tipo de movimento, a contratação e a busca informados.";
    if (erro.response?.status === 409) return "Há um movimento com valor, situação ou data de estorno inconsistente. Confira o histórico no Financeiro antes de consultar o extrato.";
  }
  return "Não foi possível consultar ou exportar o extrato. Tente atualizar novamente.";
}
