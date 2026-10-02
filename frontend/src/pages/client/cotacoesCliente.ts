export type SolicitacaoCliente = {
  id: number;
  empresa_cliente_id: number;
  quantidade: number;
  dimensao_x_maxima_mm: string | number;
  dimensao_y_maxima_mm: string | number;
  dimensao_z_maxima_mm: string | number;
  observacoes?: string | null;
  status: string;
};

export type CotacaoCliente = {
  id: number;
  solicitacao_id: number;
  empresa_fornecedora_id: number;
  valor_total: string | number;
  prazo_dias: number;
  validade_dias: number;
  observacoes: string | null;
  status: string;
  criada_em: string;
  encerrada_em: string | null;
  decidida_por_empresa_id: number | null;
};

export type OrdenacaoCotacoes = "valor" | "prazo" | "recentes";
export type AcaoCotacao = "aceitar" | "recusar";

export function instanteUtc(valor: string | null): number | null {
  if (!valor) return null;
  // O backend considera UTC as datas sem indicação de fuso.
  const texto = valor.trim().replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  const comFuso = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(texto);
  const instante = Date.parse(comFuso ? texto : `${texto}Z`);
  return Number.isFinite(instante) ? instante : null;
}

export function vencimentoCotacao(cotacao: CotacaoCliente): number | null {
  const criada = instanteUtc(cotacao.criada_em);
  if (criada === null || !Number.isInteger(cotacao.validade_dias) || cotacao.validade_dias <= 0) return null;
  return criada + cotacao.validade_dias * 86_400_000;
}

export function statusCotacao(cotacao: CotacaoCliente, agora = Date.now()): string {
  const vencimento = vencimentoCotacao(cotacao);
  if (cotacao.status === "enviada" && vencimento !== null && agora >= vencimento) return "expirada";
  return cotacao.status;
}

export function podeDecidirCotacao(cotacao: CotacaoCliente, possuiAceita: boolean, agora = Date.now()): boolean {
  const vencimento = vencimentoCotacao(cotacao);
  return !possuiAceita && cotacao.status === "enviada" && vencimento !== null && agora < vencimento;
}

export function rotuloStatusCotacao(status: string): string {
  const rotulos: Record<string, string> = {
    enviada: "Aguardando decisão", aceita: "Aceita", recusada: "Recusada", expirada: "Expirada", cancelada: "Cancelada",
  };
  return rotulos[status] ?? "Situação indisponível";
}

export function formatarValorCotacao(valor: string | number): string {
  const numero = Number(valor);
  return Number.isFinite(numero) && numero > 0
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numero)
    : "Valor indisponível";
}

export function formatarInstanteCotacao(instante: number | null): string {
  return instante === null ? "Data indisponível" : new Date(instante).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function ordenarCotacoes(itens: CotacaoCliente[], ordenacao: OrdenacaoCotacoes): CotacaoCliente[] {
  return [...itens].sort((a, b) => {
    const diferenca = ordenacao === "prazo" ? a.prazo_dias - b.prazo_dias
      : ordenacao === "recentes" ? (instanteUtc(b.criada_em) ?? 0) - (instanteUtc(a.criada_em) ?? 0)
      : Number(a.valor_total) - Number(b.valor_total);
    return diferenca || a.id - b.id;
  });
}

export function mensagemErroCotacao(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const resposta = (erro as { response?: { data?: { detail?: unknown } } }).response;
    const detalhe = resposta?.data?.detail;
    const mensagens: Record<string, string> = {
      solicitacao_nao_encontrada: "A solicitação não foi encontrada. Atualize a lista.",
      cotacao_nao_encontrada: "A cotação não foi encontrada. Atualize as propostas.",
      empresa_nao_e_cliente_da_solicitacao: "Esta solicitação pertence a outro cliente.",
      cotacao_expirada: "A validade desta cotação terminou. Atualize as propostas.",
      cotacao_nao_esta_pendente: "Esta cotação já foi encerrada. Atualize as propostas.",
      solicitacao_ja_possui_cotacao_aceita: "Esta solicitação já possui uma cotação aceita.",
      empresa_cliente_nao_encontrada: "A empresa cliente não foi encontrada.",
      empresa_nao_e_cliente: "A empresa selecionada não é uma empresa cliente.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize as cotações e tente novamente.";
    if (Array.isArray(detalhe)) return "Os dados enviados não foram aceitos. Atualize a página e tente novamente.";
  }
  return "Não foi possível confirmar a operação. Verifique a conexão e atualize as cotações antes de tentar novamente.";
}
