import type { ItemPainel } from "../painel/painelPortal";
import type { Movimento } from "../financeiro/financeiroPortal";

export type CadastroRelatorio = {
  cotacao_id: number; empresa_cliente_id: number; empresa_fornecedora_id: number;
  quantidade: number | null; prazo_dias: number; processo: string | null; material: string | null;
  observacoes_contratacao: string | null; contratada_em: string; encerrada_em: string | null; cancelada_em: string | null;
  ordem_criada_em: string | null; ordem_iniciada_em: string | null; ordem_concluida_em: string | null; ordem_cancelada_em: string | null;
};
export type RegistroRelatorio = {
  origem: "producao" | "intermediacao" | "financeiro"; registro_id: number; versao: number | null; data_utc: string;
  acao: string; descricao: string; situacao: string | null; responsavel: string | null;
  usuario_admin_id: number | null; empresa_fornecedora_id: number | null;
  pagamento_id: number | null; repasse_id: number | null; valor: string | null; quantidade: number | null;
  referencia: string | null; registro_interno: string | null; parecer_tecnico: string | null;
};
export type Relatorio = {
  gerado_em: string; resumo: ItemPainel; cadastro: CadastroRelatorio; recebimentos: Movimento[]; repasses: Movimento[];
  linha_tempo: RegistroRelatorio[]; avisos: string[];
};
export const origensRelatorio = { producao: "Produção", intermediacao: "Intermediação", financeiro: "Financeiro" };
export function erroRelatorio(erro: unknown): string {
  const e = erro as { response?: { status?: number } };
  if (e.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (e.response?.status === 403) return "O relatório exige uma conta administrativa.";
  if (e.response?.status === 404) return "A contratação não foi encontrada.";
  if (e.response?.status === 409) return "Há um registro inconsistente. Confira os dados desta contratação na administração.";
  if (e.response?.status === 422) return "Informe um número de contratação válido.";
  return "Não foi possível consultar o relatório. Confira o servidor e tente atualizar.";
}
