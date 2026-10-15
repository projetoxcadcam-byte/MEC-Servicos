import type { FiltroPainel } from "../painel/painelPortal";
import type { ItemEmpresa } from "../empresas/empresasPortal";
import type { ResumoGerencial } from "../gerencial/gerencialPortal";
import { mensagemPeriodo } from "../periodo/periodoPortal";

export type PeriodoDetalhe = "a" | "b" | null;
export interface FiltrosComparativo {
  a_inicial: string; a_final: string; b_inicial: string; b_final: string;
  filtro: FiltroPainel; busca: string; periodo: PeriodoDetalhe;
}
export interface ResumoPeriodoComparativo extends ResumoGerencial { data_inicial: string; data_final: string; }
export interface MedidaComparativa {
  codigo: string; descricao: string; tipo: "quantidade" | "valor";
  valor_a: string; valor_b: string; diferenca: string; variacao_percentual: string | null;
}
export interface ConsultaComparativo {
  filtros: FiltrosComparativo; resumo_a: ResumoPeriodoComparativo; resumo_b: ResumoPeriodoComparativo;
  medidas: MedidaComparativa[]; periodos_sobrepostos: boolean; contratacoes_em_ambos: number;
  itens: ItemEmpresa[]; total: number; deslocamento: number; limite: number; gerado_em: string;
}
export const camposDatas = ["a_inicial", "a_final", "b_inicial", "b_final"] as const;
export function periodosPadrao(): FiltrosComparativo {
  const agora = new Date(); const ano = agora.getUTCFullYear(); const mes = agora.getUTCMonth();
  function intervalo(a: number, m: number) {
    const prefixo = `${String(a).padStart(4, "0")}-${String(m + 1).padStart(2, "0")}`;
    const ultimo = new Date(Date.UTC(a, m + 1, 0)).getUTCDate();
    return [prefixo + "-01", prefixo + "-" + String(ultimo).padStart(2, "0")];
  }
  const a = intervalo(mes === 0 ? ano - 1 : ano, mes === 0 ? 11 : mes - 1); const b = intervalo(ano, mes);
  return { a_inicial: a[0], a_final: a[1], b_inicial: b[0], b_final: b[1], filtro: "todas", busca: "", periodo: null };
}
export function datasValidas(f: FiltrosComparativo) {
  return camposDatas.every(c => {
    const v = f[c]; if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(v) || Number(v.slice(0, 4)) < 1) return false;
    const d = new Date(v + "T00:00:00Z"); return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === v;
  }) && f.a_inicial <= f.a_final && f.b_inicial <= f.b_final;
}
export function linkPeriodoComparativo(f: FiltrosComparativo, periodo: "a" | "b", destino: "periodo" | "pendencias") {
  const p = new URLSearchParams({ data_inicial: f[`${periodo}_inicial`], data_final: f[`${periodo}_final`], filtro: f.filtro });
  if (f.busca) p.set("busca", f.busca);
  return (destino === "periodo" ? "/admin/relatorios-periodo?" : "/admin/pendencias?") + p.toString();
}
export function mensagemComparativo(falha: unknown) {
  const status = (falha as { response?: { status?: number } })?.response?.status;
  if (status === 422) return "Preencha as quatro datas. Em cada período, o início deve ser igual ou anterior ao fim. Confira também a situação e a busca.";
  if (status === 409) return "Há dados registrados que precisam de conferência administrativa antes da comparação.";
  return mensagemPeriodo(falha);
}
