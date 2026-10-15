import { isAxiosError } from "axios";

export type FiltroPainel = "todas" | "operacionais" | "financeiras" | "verificar" | "concluidas" | "canceladas";
export type SituacaoPainel = "em_andamento" | "concluida" | "cancelada" | "verificar";
export type PendenciaPainel = { codigo: string; area: "operacional" | "financeira" | "conferencia"; descricao: string };
export type ItemPainel = {
  contratacao_id: number; solicitacao_id: number; ordem_servico_id: number | null;
  cliente: string; fornecedor: string; contratacao_status: string; ordem_status: string | null;
  etapa_administrativa: string | null; etapa_producao: string | null;
  financeiro_status: "sem_controle" | "aberto" | "encerrado"; situacao: SituacaoPainel;
  valor_contratado: string; total_recebido: string; total_repassado: string;
  saldo_cliente: string; saldo_fornecedor: string; disponivel_repasse: string;
  entrega_concluida: boolean; atualizado_em: string | null; pendencias: PendenciaPainel[];
};
export type IndicadoresPainel = {
  total_contratacoes: number; contratacoes_ativas: number; acompanhamento_operacional: number;
  pendencias_financeiras: number; para_conferencia: number; contratacoes_concluidas: number;
  contratacoes_canceladas: number; financeiros_encerrados: number; controles_abertos: number;
  recebimentos_confirmados: string; repasses_confirmados: string;
  saldo_clientes_controles_abertos: string; saldo_fornecedores_controles_abertos: string; disponivel_repasses: string;
};
export type ConsultaPainel = { indicadores: IndicadoresPainel; itens: ItemPainel[]; total: number;
  deslocamento: number; limite: number; filtro: FiltroPainel; busca: string; atualizado_em: string };

export function identificador(valor: string | null): number {
  if (!valor || !/^[1-9]\d{0,12}$/.test(valor)) return 0;
  const id = Number(valor);
  return Number.isSafeInteger(id) ? id : 0;
}

export const filtrosPainel: Record<FiltroPainel, string> = {
  todas: "Todas as contratações", operacionais: "Em acompanhamento operacional",
  financeiras: "Com pendência financeira", verificar: "Para conferência", concluidas: "Concluídas", canceladas: "Canceladas",
};
export const situacoesPainel: Record<SituacaoPainel, string> = {
  em_andamento: "Em andamento", concluida: "Concluída", cancelada: "Cancelada", verificar: "Para conferência",
};

export function mensagemPainel(erro: unknown): string {
  if (isAxiosError(erro)) {
    const codigo = erro.response?.status;
    if (codigo === 401) return "A sessão terminou. Entre novamente para consultar o painel.";
    if (codigo === 403) return "O painel está disponível somente para a administração.";
    if (codigo === 422) return "Confira os filtros e a busca antes de consultar o painel.";
    if (erro.code === "ECONNABORTED") return "A consulta demorou mais que o esperado. Tente atualizar.";
  }
  return "Não foi possível carregar o painel. Confira o backend e tente atualizar.";
}
