export const rotulosStatus: Record<string, string> = {
  aguardando_material: "Aguardando material", material_recebido: "Material recebido pela administração",
  material_encaminhado: "Material encaminhado ao fornecedor", coleta_solicitada: "Coleta solicitada",
  pecas_recebidas: "Peças recebidas pela administração", em_avaliacao: "Em avaliação administrativa",
  retrabalho: "Retrabalho solicitado", retrabalho_encaminhado: "Peças encaminhadas para retrabalho",
  aprovado_para_entrega: "Peças aprovadas para entrega", entregue_cliente: "Entrega ao cliente concluída", cancelado: "Ciclo cancelado",
};
export const rotulosAcao: Record<string, string> = {
  iniciar_ciclo: "Iniciar ciclo administrativo", receber_material: "Registrar recebimento do material",
  encaminhar_material: "Registrar encaminhamento do material", solicitar_coleta: "Solicitar coleta das peças",
  receber_pecas: "Registrar recebimento das peças", iniciar_avaliacao: "Iniciar avaliação das peças",
  aprovar_pecas: "Aprovar peças para entrega", solicitar_retrabalho: "Solicitar retrabalho",
  encaminhar_retrabalho: "Encaminhar peças para retrabalho", entregar_cliente: "Concluir entrega ao cliente e OS", cancelar: "Cancelar ciclo e OS",
};
export function statusVisivel(status: string | null) { return status ? rotulosStatus[status] ?? "Situação indisponível" : "Sem ciclo administrativo"; }
export function dataIntermediacao(valor: string | null) {
  if (!valor) return "—";
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? "—" : data.toLocaleString("pt-BR");
}
export type OrdemIntermediacao = {
  ordem_servico_id: number; solicitacao_id: number; contratacao_id: number; empresa_cliente_id: number; empresa_fornecedora_id: number;
  cliente: string; fornecedor: string; quantidade: number; ordem_status: string; contratacao_status: string; producao_etapa: string | null;
  ciclo_id: number | null; status: string | null; versao: number; atualizado_em: string | null; pode_iniciar: boolean;
};
export type EventoIntermediacao = {
  id: number; versao: number; acao: string; status_resultante: string; administrador_nome: string; usuario_admin_id: number;
  registro_interno: string; referencia: string | null; parecer_tecnico: string | null; quantidade_conferida: number | null; criado_em: string;
};
export type DetalheIntermediacao = { ordem: OrdemIntermediacao; acoes_permitidas: string[]; historico: EventoIntermediacao[] };
export type PaginaIntermediacao = { itens: OrdemIntermediacao[]; total: number; deslocamento: number; limite: number };
export type ContratacaoSemOrdem = { id: number; solicitacao_id: number; cliente: string; fornecedor: string };
export type ConsultaIntermediacao = {
  ordem_servico_id: number; status: string | null; atualizado_em: string | null;
  historico: { acao: string; status_resultante: string; criado_em: string }[];
};
export function mensagemIntermediacao(erro: unknown): string {
  const falha = erro as { response?: { status?: number; data?: { detail?: unknown } } };
  const detalhe = falha?.response?.data?.detail;
  const mensagens: Record<string, string> = {
    acao_exclusiva_da_administracao: "Este registro é realizado pela administração.",
    ordem_usa_intermediacao_administrativa: "Use o painel de intermediação para concluir ou cancelar esta ordem.",
    producao_aguarda_encaminhamento_administrativo: "A produção aguarda o encaminhamento do material ou das peças pela administração.",
    ordem_sem_condicoes_para_intermediacao: "A ordem precisa estar aberta ou em execução e vinculada a uma contratação ativa.",
    ciclo_ja_iniciado: "Esta ordem já possui um ciclo. Atualize a página.",
    intermediacao_alterada_atualize: "Outro registro alterou o ciclo. Atualize e confira a etapa antes de continuar.",
    etapa_intermediacao_incompativel: "Esta ação não corresponde à etapa atual. Atualize o andamento.",
    confira_quantidade_total_da_ordem: "Informe a quantidade total de peças da ordem. Este ciclo registra o lote completo.",
    parecer_tecnico_obrigatorio: "Registre o parecer técnico antes de decidir sobre as peças.",
    referencia_comprovante_obrigatoria: "Informe a referência do comprovante desta movimentação.",
    fornecedor_precisa_informar_pronto_para_coleta: "O fornecedor precisa registrar Pronto para coleta em Produção. Após retrabalho, é necessário um novo registro.",
    contratacao_ja_possui_ordem: "Esta contratação já possui uma ordem. Atualize a lista.",
    ordem_servico_nao_encontrada: "A ordem não foi encontrada para esta conta.",
  };
  if (typeof detalhe === "string" && mensagens[detalhe]) return mensagens[detalhe];
  if (falha?.response?.status === 422) return "Confira os campos obrigatórios e os limites de texto.";
  if (falha?.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (falha?.response?.status === 403) return "Esta conta não tem permissão para acessar este registro.";
  return "Não foi possível concluir a operação. Confira o servidor e atualize a página.";
}
