import { api } from "../../services/api";
export type Perfil = "admin" | "cliente" | "fornecedor";
export type Nota = { id: number; origem: "cliente" | "admin"; nota: number; criada_em: string;
  historica: boolean; comentario?: string | null; autor?: { usuario_id: number; nome: string } | null };
export type Item = { contratacao_id: number; ordem_servico_id: number | null; cliente_codigo: string;
  fornecedor_codigo: string; status_ordem: string | null; status_entrega: string | null; status_contratacao: string;
  pode_avaliar: boolean; motivo_disponibilidade: string | null; versao: string; cliente: Nota | null; admin: Nota | null };
export type Pagina = { contexto: string; total: number; inicio: number; limite: number; itens: Item[] };
export type Detalhe = { contexto: string; item: Item; repetida?: boolean };
export type Operacao = { nota: number; comentario: string | null; versao: string; chave_operacao: string };
export type Ranking = { contexto: string; origem: "cliente" | "admin"; total: number; total_fornecedores: number;
  inicio: number; limite: number; busca?: string; itens: Array<{ fornecedor_codigo: string; empresa_id?: number; razao_social?: string;
    quantidade: number; media: string | null; posicao: number | null }> };
export type HistoricoFornecedor = { contexto: string; fornecedor: { empresa_id: number; fornecedor_codigo: string;
  razao_social: string; notas_cliente: { quantidade: number; media: string | null }; notas_admin: { quantidade: number; media: string | null } };
  total: number; inicio: number; limite: number; itens: Item[] };
export const raiz = (p: Perfil) => (p === "admin" ? "/administracao" : `/portal-${p}`) + "/avaliacoes";
export const idValido = (v: string | null) => v !== null && /^[1-9]\d{0,12}$/.test(v);
export const dataNota = (v: string) => new Date(v).toLocaleString("pt-BR");
export const motivos: Record<string, string> = {
  contratacao_cancelada: "Contratação cancelada.", ordem_servico_nao_encontrada: "Aguardando abertura da OS.",
  vinculos_da_ordem_inconsistentes: "A administração precisa conferir os vínculos da OS.",
  aguardando_conclusao_da_ordem: "Aguardando a conclusão da OS e a entrega ao cliente.",
  aguardando_entrega_ao_cliente: "Aguardando a entrega ao cliente registrada pela administração.",
  avaliacao_ja_registrada: "Sua avaliação já foi registrada.",
  fornecedor_consulta_avaliacoes: "Consulta das notas recebidas.",
};
export function mensagem(erro: unknown): string {
  const e = erro as { response?: { status?: number; data?: { detail?: unknown } } };
  const detalhe = e.response?.data?.detail;
  const m: Record<string, string> = { ...motivos,
    contratacao_nao_encontrada: "Esta contratação não foi encontrada para a sua conta.",
    fornecedor_nao_encontrado: "Este fornecedor não foi encontrado. Atualize o ranking e confira a empresa.",
    avaliacao_contexto_alterado: "O serviço mudou desde a conferência. Atualize e revise a avaliação.",
    contexto_avaliacoes_alterado: "O perfil foi alterado em outra aba. Entre novamente para continuar.",
    chave_operacao_ja_utilizada: "Esta confirmação já foi usada com outros dados. Atualize para conferir o registro.",
    avaliacao_ja_registrada: "A avaliação já foi registrada. Atualize para consultá-la.",
  };
  if (typeof detalhe === "string" && m[detalhe]) return m[detalhe];
  if (e.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (e.response?.status === 403) return "Esta conta não tem permissão para esta operação. Confira o perfil de acesso.";
  if (e.response?.status === 422) return "Confira os filtros, a nota de 1 a 5 e o comentário de até 2.000 caracteres.";
  return "Não foi possível receber a confirmação. Confira sua conexão; você pode repetir a mesma confirmação ou atualizar para consultar o resultado.";
}
export async function consultar<T extends { contexto: string }>(url: string, contexto: string, signal: AbortSignal,
  params?: Record<string, string | number>) {
  const { data } = await api.get<T>(url, { params, signal, timeout: 20_000, headers: { "X-MEC-AVALIACOES-CONTEXTO": contexto } });
  if (data.contexto !== contexto) throw new Error("Contexto de acesso alterado.");
  return data;
}
