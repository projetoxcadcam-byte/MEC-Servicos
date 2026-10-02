import type { CotacaoCliente } from "../client/cotacoesCliente";
import type { SolicitacaoFornecedor } from "../supplier/cotacoesFornecedor";

export type PerfilContratacoes = "cliente" | "fornecedor";
export type CotacaoParaContratar = CotacaoCliente & {
  fornecedor_razao_social: string;
  solicitacao: SolicitacaoFornecedor;
};
export type ContratacaoPortal = {
  id: number; solicitacao_id: number; cotacao_id: number;
  empresa_cliente_id: number; empresa_fornecedora_id: number;
  cliente_razao_social: string; fornecedor_razao_social: string;
  valor_total: string | number; prazo_dias: number; observacoes: string | null;
  status: string; criada_em: string; cancelada_em: string | null; encerrada_em: string | null;
  solicitacao: SolicitacaoFornecedor;
};
export type ContratacaoResposta = Omit<ContratacaoPortal, "cliente_razao_social" | "fornecedor_razao_social" | "solicitacao">;
export type PaginaContratacoes<T> = { itens: T[]; total: number; deslocamento: number; limite: number };

export function rotuloContratacao(status: string): string {
  return ({ ativa: "Ativa", cancelada: "Cancelada", encerrada: "Encerrada" } as Record<string, string>)[status] ?? "Situação indisponível";
}

export function formatarMedidaContrato(valor: string | number, casas = 3): string {
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero.toLocaleString("pt-BR", { maximumFractionDigits: casas }) : "—";
}

export function mensagemErroContratacao(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    const mensagens: Record<string, string> = {
      empresa_cliente_nao_encontrada: "A empresa cliente deste acesso não foi encontrada.",
      empresa_fornecedor_nao_encontrada: "A empresa fornecedora deste acesso não foi encontrada.",
      empresa_nao_e_cliente: "Entre com um acesso de cliente para consultar ou criar suas contratações.",
      empresa_nao_e_fornecedor: "Entre com um acesso de fornecedor para consultar suas contratações.",
      empresa_nao_e_cliente_da_solicitacao: "Esta solicitação pertence a outro cliente.",
      solicitacao_nao_encontrada: "A solicitação não foi encontrada. Atualize a lista.",
      solicitacao_nao_esta_aberta: "A solicitação já foi encerrada. Atualize as listas antes de continuar.",
      cotacao_nao_encontrada: "A cotação não foi encontrada nessa solicitação. Atualize a lista.",
      cotacao_nao_esta_aceita: "A cotação precisa estar aceita pelo cliente para ser contratada.",
      contratacao_ja_cadastrada: "Esta solicitação já possui uma contratação. Consulte a aba Contratações.",
      contratacao_nao_encontrada: "A contratação não está disponível para esta empresa. Atualize a lista.",
      arquivo_tecnico_nao_encontrado: "O arquivo não está mais disponível. Atualize os arquivos.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";
    if (Array.isArray(detalhe)) return "Confira os dados da contratação e limite as observações a 5000 caracteres.";
  }
  return "Não foi possível consultar os dados. Confira a conexão e atualize a tela.";
}
