export type PerfilFinanceiro = "admin" | "cliente" | "fornecedor";
export type Movimento = { id: number; tipo: string; valor: string; forma_pagamento: string; status: string; registrado_em: string; estornado_em: string | null };
export type Resumo = {
  contratacao_id: number; ordem_servico_id: number | null; contratacao_status: string; valor_contratado: string; valor_fornecedor:string;acrescimo_administracao:string;
  total_recebido: string; saldo_cliente: string; total_repassado: string; saldo_fornecedor: string;
  disponivel_repasse: string; entrega_concluida: boolean; status: string; versao: number;
  atualizado_em: string | null; cliente: string; fornecedor: string; pode_iniciar: boolean;
};
export type Consulta = { contratacao_id: number; ordem_servico_id: number | null; valor_contratado: string;
  total_confirmado: string; saldo: string; status: string; entrega_concluida: boolean; movimentos: Movimento[] };
export type Evento = { id: number; versao: number; acao: string; pagamento_id: number | null; repasse_id: number | null;
  valor_centavos: number | null; administrador_nome: string; registro_interno: string; referencia: string | null; criado_em: string };
export type Detalhe = { resumo: Resumo; acoes_permitidas: string[]; recebimentos: Movimento[]; repasses: Movimento[]; historico: Evento[] };
export type Pagina<T> = { itens: T[]; total: number; deslocamento: number; limite: number };
export const acoes: Record<string, string> = { iniciar: "Iniciar controle financeiro", recebimento: "Registrar recebimento do cliente",
  repasse: "Registrar repasse ao fornecedor", estornar_recebimento: "Estornar recebimento", estornar_repasse: "Estornar repasse",
  encerrar: "Encerrar financeiro e contratação", reabrir: "Reabrir financeiro e contratação" };
export const formas: Record<string, string> = { pix: "Pix", transferencia: "Transferência", boleto: "Boleto", cartao: "Cartão", dinheiro: "Dinheiro", outro: "Outro" };
export const estados: Record<string, string> = { aberto: "Em acompanhamento", encerrado: "Financeiro encerrado", sem_controle: "Controle ainda não iniciado",
  confirmado: "Confirmado", estornado: "Estornado", ativa: "Ativa", encerrada: "Encerrada", cancelada: "Cancelada" };
export function dinheiro(valor: string | number) { return Number(valor).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); }
export function dataFinanceiro(valor: string) { const data = new Date(valor); return Number.isNaN(data.getTime()) ? "—" : data.toLocaleString("pt-BR"); }
export function lerValor(texto: string): string | null {
  const t = texto.trim();
  if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(t)) return null;
  const [reais, centavos = "00"] = t.replace(/\./g, "").split(",");
  const valor = `${reais}.${centavos.padEnd(2, "0")}`;
  return Number(valor) > 0 ? valor : null;
}
export function erroFinanceiro(erro: unknown): string {
  const e = erro as { response?: { status?: number; data?: { detail?: unknown } } };
  const m: Record<string, string> = {
    financeiro_alterado_atualize: "Outro registro alterou os saldos. Atualize e confira antes de continuar.",
    financeiro_ja_iniciado: "O controle já foi iniciado. Atualize a página.", financeiro_nao_iniciado: "Inicie o controle financeiro desta contratação.",
    recebimento_supera_saldo: "O recebimento supera o saldo do cliente.", repasse_supera_disponivel: "O repasse supera o valor disponível.",
    repasse_aguarda_entrega: "O repasse aguarda a entrega ao cliente concluída na intermediação.",
    referencia_financeira_duplicada: "Esta referência já foi registrada. Confira o histórico antes de continuar.",
    chave_financeira_reutilizada: "Esta operação já foi usada com outros dados. Atualize a página.",
    estorno_recebimento_descobre_repasse: "Este estorno deixaria repasses sem cobertura. Confira os repasses e registre primeiro a devolução correspondente.",
    movimento_ja_estornado: "O movimento já foi estornado. Atualize os dados.",
    financeiro_tem_pendencias: "Conclua a entrega e zere os saldos de recebimentos e repasses antes de encerrar.",
    financeiro_fechado: "O financeiro está encerrado ou a contratação não está ativa.",
    financeiro_nao_encerrado: "Este financeiro não está encerrado. Atualize os dados.",
    contratacao_sem_condicoes_financeiras: "O controle exige contratação ativa e recebimentos dentro do valor contratado.",
    contratacao_usa_financeiro_administrativo: "Use o Financeiro administrativo para esta contratação.",
    valor_financeiro_inconsistente: "O valor contratado diverge do controle. Solicite revisão à administração.",
    contratacao_nao_encontrada: "A contratação não foi encontrada para esta conta.", movimento_financeiro_nao_encontrado: "O movimento não pertence a esta contratação.",
  };
  const detail = e.response?.data?.detail;
  if (typeof detail === "string" && m[detail]) return m[detail];
  if (e.response?.status === 422) return "Confira os campos obrigatórios. Use valores positivos com até duas casas decimais.";
  if (e.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (e.response?.status === 403) return "Esta conta não tem permissão para a operação.";
  return "Não foi possível confirmar a operação. Confira o servidor; para repetir, mantenha os mesmos dados e a mesma referência.";
}
