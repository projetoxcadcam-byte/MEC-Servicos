import type { ConsultaPainel, ItemPainel, FiltroPainel } from "../painel/painelPortal";

export interface FiltrosPeriodo { data_inicial: string | null; data_final: string | null; filtro: FiltroPainel; busca: string; }
export interface ItemPeriodo extends ItemPainel { contratada_em: string; }
export interface MesPeriodo { mes: string; total_contratacoes: number; valor_contratado: string; recebido_confirmado: string; repassado_confirmado: string; }
export interface ConsultaPeriodo {
  filtros: FiltrosPeriodo; indicadores: ConsultaPainel["indicadores"]; valor_contratado: string;
  meses: MesPeriodo[]; itens: ItemPeriodo[]; total: number; deslocamento: number; limite: number; gerado_em: string;
}
export function diaUTC(valor: string | null) { return valor ? valor.slice(0, 10).split("-").reverse().join("/") : "Sem limite"; }
export function mensagemPeriodo(falha: unknown): string {
  const r = (falha as { response?: { status?: number } })?.response;
  if (r?.status === 401) return "A sessão expirou. Entre novamente para consultar o relatório.";
  if (r?.status === 403) return "O relatório está disponível somente para a administração.";
  if (r?.status === 422) return "Confira as datas, a situação e a busca. A data inicial deve ser igual ou anterior à final.";
  if (r?.status === 409) return "Há uma data registrada que precisa de conferência administrativa.";
  return "Não foi possível consultar os dados. Confira o backend e tente atualizar.";
}
