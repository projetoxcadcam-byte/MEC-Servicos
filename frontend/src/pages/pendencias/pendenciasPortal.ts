import type { ConsultaPainel, PendenciaPainel } from "../painel/painelPortal";
import type { FiltrosPeriodo } from "../periodo/periodoPortal";
import type { ItemEmpresa } from "../empresas/empresasPortal";

export type AreaFila = "todas" | "operacional" | "financeira" | "conferencia";
export interface FiltrosPendencias extends FiltrosPeriodo { area: AreaFila; acao: string; }
export interface AcaoPendencia { codigo: string; area: Exclude<AreaFila, "todas">; rotulo: string; }
export interface ItemPendencia { contratacao: ItemEmpresa; pendencia: PendenciaPainel; acao: string; caminho: string; destino: "intermediacao" | "financeiro" | "relatorio"; }
export interface ConsultaPendencias {
  filtros: FiltrosPendencias; catalogo_acoes: AcaoPendencia[]; itens: ItemPendencia[];
  total_pendencias: number; total_contratacoes: number; pendencias_operacionais: number; pendencias_financeiras: number; pendencias_conferencia: number;
  indicadores: ConsultaPainel["indicadores"]; valor_contratado: string; deslocamento: number; limite: number; gerado_em: string;
}
export const areasFila: Record<AreaFila, string> = { todas: "Todas as áreas", operacional: "Operacional", financeira: "Financeira", conferencia: "Conferência" };
