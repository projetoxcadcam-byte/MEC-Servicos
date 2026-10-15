import type { ConsultaPainel } from "../painel/painelPortal";
import type { FiltrosPeriodo, ItemPeriodo } from "../periodo/periodoPortal";

export type AgrupamentoEmpresas = "clientes" | "fornecedores";
export interface FiltrosEmpresas extends FiltrosPeriodo { agrupamento: AgrupamentoEmpresas; empresa_id: number | null; }
export interface ItemEmpresa extends ItemPeriodo { empresa_cliente_id: number; empresa_fornecedora_id: number; }
export interface GrupoEmpresa { empresa_id: number; empresa: string; valor_contratado: string; indicadores: ConsultaPainel["indicadores"]; }
export interface ConsultaEmpresas {
  filtros: FiltrosEmpresas; indicadores: ConsultaPainel["indicadores"]; valor_contratado: string;
  grupos: GrupoEmpresa[]; empresa_selecionada: GrupoEmpresa | null; itens: ItemEmpresa[];
  total_empresas: number; total_contratacoes: number; deslocamento: number; deslocamento_itens: number; limite: number; gerado_em: string;
}
