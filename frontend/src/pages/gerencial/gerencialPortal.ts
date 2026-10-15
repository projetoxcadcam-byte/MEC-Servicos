import type { ConsultaPainel, FiltroPainel } from "../painel/painelPortal";
import type { ItemEmpresa } from "../empresas/empresasPortal";
import { mensagemPeriodo } from "../periodo/periodoPortal";

export interface FiltrosGerencial { ano: number; filtro: FiltroPainel; busca: string; mes: number | null; }
export interface ResumoGerencial {
  indicadores: ConsultaPainel["indicadores"]; valor_contratado: string; em_andamento: number;
  contratacoes_com_pendencias: number; pendencias_operacionais: number; pendencias_financeiras: number; pendencias_conferencia: number;
}
export interface MesGerencial extends ResumoGerencial { mes: number; data_inicial: string; data_final: string; }
export interface ConsultaGerencial {
  filtros: FiltrosGerencial; resumo_ano: ResumoGerencial; meses: MesGerencial[];
  resumo_mes: MesGerencial | null; itens: ItemEmpresa[]; total: number; deslocamento: number; limite: number; gerado_em: string;
}
export const mesesGerencial = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
export function nomeMes(mes: number) { return mesesGerencial[mes - 1] ?? "Mês"; }
export function mensagemGerencial(falha: unknown) {
  if ((falha as { response?: { status?: number } })?.response?.status === 422)
    return "Confira o ano, o mês, a situação e a busca. Use um ano de 1 a 9999 e um mês de 1 a 12.";
  return mensagemPeriodo(falha);
}
export function linkPendenciasGerencial(f: FiltrosGerencial, m?: MesGerencial) {
  const parametros = new URLSearchParams({ data_inicial: m?.data_inicial ?? `${String(f.ano).padStart(4, "0")}-01-01`,
    data_final: m?.data_final ?? `${String(f.ano).padStart(4, "0")}-12-31`, filtro: f.filtro });
  if (f.busca) parametros.set("busca", f.busca);
  return "/admin/pendencias?" + parametros.toString();
}
