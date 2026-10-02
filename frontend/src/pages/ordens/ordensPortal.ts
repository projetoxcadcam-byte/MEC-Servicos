import type { SolicitacaoFornecedor } from "../supplier/cotacoesFornecedor";

export type PerfilOrdens = "cliente" | "fornecedor";
export type AcaoOrdem = "gerar" | "iniciar" | "concluir";
export type OrdemResposta = {
  id: number; contratacao_id: number; solicitacao_id: number; cotacao_id: number;
  empresa_cliente_id: number; empresa_fornecedora_id: number;
  processo_id: number; material_id: number; quantidade: number;
  valor_total: string | number; prazo_dias: number; status: string; observacoes: string | null;
  criada_em: string; iniciada_em: string | null; concluida_em: string | null; cancelada_em: string | null;
};
export type OrdemPortal = OrdemResposta & {
  cliente_razao_social: string; fornecedor_razao_social: string;
  processo_nome: string; material_nome: string; contratacao_status: string;
  solicitacao: SolicitacaoFornecedor;
};

export function rotuloOrdem(status: string): string {
  return ({ aberta: "Aberta", em_execucao: "Em execução", concluida: "Concluída", cancelada: "Cancelada" } as Record<string, string>)[status] ?? "Situação indisponível";
}

export function mensagemErroOrdem(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    const mensagens: Record<string, string> = {
      empresa_cliente_nao_encontrada: "A empresa cliente deste acesso não foi encontrada.",
      empresa_fornecedor_nao_encontrada: "A empresa fornecedora deste acesso não foi encontrada.",
      empresa_nao_e_cliente: "Entre como cliente para consultar ou gerar suas ordens de serviço.",
      empresa_nao_e_fornecedor: "Entre como fornecedor para consultar e executar suas ordens de serviço.",
      empresa_nao_e_cliente_da_contratacao: "Esta contratação pertence a outro cliente.",
      contratacao_nao_encontrada: "A contratação não está disponível. Atualize a lista.",
      contratacao_nao_esta_ativa: "A contratação precisa estar ativa para gerar ou executar uma ordem. Atualize a tela.",
      ordem_servico_ja_cadastrada_para_esta_contratacao: "Esta contratação já possui uma ordem de serviço. Consulte a aba Ordens de Serviço.",
      ordem_servico_nao_encontrada: "A ordem não está disponível para esta empresa. Atualize a lista.",
      ordem_servico_nao_pode_ser_iniciada: "Somente uma ordem aberta pode ser iniciada. Atualize a tela.",
      ordem_servico_nao_pode_ser_concluida: "Somente uma ordem em execução pode ser concluída. Atualize a tela.",
      ordem_servico_alterada_atualize: "A ordem foi alterada durante a operação. Atualize a tela antes de continuar.",
      arquivo_tecnico_nao_encontrado: "O arquivo não está mais disponível. Atualize os arquivos.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";
    if (Array.isArray(detalhe)) return "Confira a empresa deste acesso e atualize a tela.";
  }
  return "Não foi possível consultar os dados. Confira a conexão e atualize a tela.";
}
