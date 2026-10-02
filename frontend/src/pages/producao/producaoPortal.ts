import type { OrdemPortal } from "../ordens/ordensPortal";

export const ETAPAS_PRODUCAO = [
  { valor: "aguardando_material", rotulo: "Aguardando material" },
  { valor: "em_usinagem", rotulo: "Em usinagem" },
  { valor: "em_solda_dobra", rotulo: "Em solda/dobra" },
  { valor: "em_acabamento", rotulo: "Em acabamento" },
  { valor: "pronto_para_envio", rotulo: "Pronto para envio" },
] as const;
export type EtapaValor = typeof ETAPAS_PRODUCAO[number]["valor"];
export type EtapaProducao = {
  id: number; ordem_servico_id: number; empresa_fornecedora_id: number;
  etapa: string; observacoes: string | null; criada_em: string;
};
export type OrdemProducao = OrdemPortal & {
  etapa_atual: string | null; ultima_etapa_id: number; etapa_atual_em: string | null; total_atualizacoes: number;
};
export type AcompanhamentoProducao = {
  ordem: OrdemProducao; etapa_atual: string | null; ultima_etapa_id: number; historico: EtapaProducao[];
};

export function rotuloEtapa(etapa: string | null): string {
  return ETAPAS_PRODUCAO.find((item) => item.valor === etapa)?.rotulo ?? (etapa ? "Etapa indisponível" : "Sem etapa registrada");
}

export function etapaValida(valor: string): valor is EtapaValor {
  return ETAPAS_PRODUCAO.some((item) => item.valor === valor);
}

export function mensagemErroProducao(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    const mensagens: Record<string, string> = {
      empresa_cliente_nao_encontrada: "A empresa cliente deste acesso não foi encontrada.",
      empresa_fornecedor_nao_encontrada: "A empresa fornecedora deste acesso não foi encontrada.",
      empresa_nao_e_cliente: "Entre como cliente para consultar a produção dos seus serviços.",
      empresa_nao_e_fornecedor: "Entre como fornecedor para consultar e atualizar a produção dos seus serviços.",
      ordem_servico_nao_encontrada: "A ordem não está disponível para esta empresa. Atualize a lista.",
      contratacao_nao_esta_ativa: "A contratação precisa estar ativa para registrar etapas. Atualize a tela.",
      ordem_servico_nao_pode_atualizar_producao: "Ordens concluídas ou canceladas permitem consultar o histórico. Atualize a tela.",
      empresa_nao_e_fornecedora_da_ordem_servico: "Somente o fornecedor responsável pode atualizar esta ordem.",
      producao_alterada_atualize: "A produção já recebeu outra atualização. Atualize o histórico e confira a etapa atual antes de continuar.",
      ordem_servico_alterada_atualize: "A ordem foi alterada durante a operação. Atualize a tela antes de continuar.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";
    if (Array.isArray(detalhe)) return "Selecione uma etapa válida e limite as observações a 5000 caracteres.";
  }
  return "Não foi possível consultar os dados. Confira a conexão e atualize a tela.";
}
