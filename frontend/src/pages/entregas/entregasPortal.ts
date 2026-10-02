import type { OrdemProducao } from "../producao/producaoPortal";

export type EntregaServico = {
  id: number; ordem_servico_id: number; empresa_fornecedora_id: number; empresa_cliente_id: number;
  status: string; observacoes: string | null; motivo_recusa: string | null;
  criada_em: string; entregue_em: string; aceita_em: string | null; recusada_em: string | null;
};
export type OrdemEntrega = OrdemProducao & {
  ultima_entrega_id: number; ultima_entrega_status: string | null; ultima_entrega_em: string | null;
  total_entregas: number; entrega_pendente_id: number | null;
};
export type EntregasDetalhe = { ordem: OrdemEntrega; historico: EntregaServico[] };
export type AcaoEntrega = "registrar" | "aceitar" | "recusar";

export function rotuloEntrega(situacao: string | null): string {
  return ({ entregue: "Aguardando aceite", aceita: "Aceita", recusada: "Recusada" } as Record<string, string>)[situacao ?? ""]
    ?? (situacao ? "Situação indisponível" : "Sem entrega registrada");
}

export function mensagemErroEntrega(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    const mensagens: Record<string, string> = {
      empresa_cliente_nao_encontrada: "A empresa cliente deste acesso não foi encontrada.",
      empresa_fornecedor_nao_encontrada: "A empresa fornecedora deste acesso não foi encontrada.",
      empresa_nao_e_cliente: "Entre como cliente para consultar e decidir suas entregas.",
      empresa_nao_e_fornecedor: "Entre como fornecedor para consultar e registrar suas entregas.",
      ordem_servico_nao_encontrada: "A ordem não está disponível para esta empresa. Atualize a lista.",
      entrega_nao_encontrada: "A entrega não está disponível nesta ordem. Atualize o histórico.",
      contratacao_nao_esta_ativa: "A contratação precisa estar ativa. Atualize a tela.",
      ordem_servico_nao_pode_receber_entrega: "A ordem precisa estar em execução para registrar ou decidir a entrega. Atualize a tela.",
      ordem_servico_nao_esta_pronta_para_entrega: "Registre Pronto para envio como etapa atual na página Produção antes de entregar.",
      empresa_nao_e_fornecedora_da_ordem_servico: "Somente o fornecedor responsável pode registrar esta entrega.",
      empresa_nao_e_cliente_da_ordem_servico: "Somente o cliente responsável pode decidir esta entrega.",
      entrega_pendente_ja_existe: "Já existe uma entrega aguardando aceite nesta ordem. Atualize o histórico.",
      entrega_nao_esta_pendente: "Esta entrega já recebeu uma decisão. Atualize o histórico antes de continuar.",
      motivo_recusa_obrigatorio: "Informe o motivo da recusa para que o fornecedor possa corrigir a entrega.",
      entregas_alteradas_atualize: "As entregas desta ordem foram alteradas. Atualize o histórico antes de continuar.",
      producao_alterada_atualize: "A produção recebeu outra atualização. Atualize a tela e confira a etapa atual.",
      ordem_servico_alterada_atualize: "A ordem foi alterada durante a operação. Atualize a tela antes de continuar.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";
    if (Array.isArray(detalhe)) return "Confira os campos e limite as observações e o motivo da recusa a 5000 caracteres.";
  }
  return "Não foi possível consultar os dados. Confira a conexão e atualize a tela.";
}
