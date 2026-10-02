import type { CotacaoCliente } from "../client/cotacoesCliente";

export type SolicitacaoFornecedor = {
  id: number;
  empresa_cliente_id: number;
  cliente_razao_social: string;
  processo_id: number;
  processo_nome: string;
  material_id: number;
  material_nome: string;
  dimensao_x_maxima_mm: string | number;
  dimensao_y_maxima_mm: string | number;
  dimensao_z_maxima_mm: string | number;
  tolerancia_requerida_mm: string | number;
  quantidade: number;
  observacoes: string | null;
  status: string;
  criada_em: string;
};
export type CotacaoFornecedor = CotacaoCliente & { solicitacao: SolicitacaoFornecedor };
export type PaginaFornecedor<T> = { itens: T[]; total: number; deslocamento: number; limite: number };
export type ArquivoFornecedor = {
  id: number; solicitacao_id: number; nome_original: string; extensao: string;
  tamanho_bytes: number; ativo: boolean;
};
export type CamposProposta = { valor: string; prazo: string; validade: string; observacoes: string };
export type DadosProposta = { valor_total: string; prazo_dias: number; validade_dias: number; observacoes: string | null };

export function normalizarValorProposta(entrada: string): string | null {
  // Normalização textual: centavos nunca passam por arredondamento em ponto flutuante.
  const texto = entrada.trim().replace(/^R\$\s*/, "");
  let inteiro: string;
  let fracao: string;
  if (/^\d+(?:,\d{1,2})?$/.test(texto)) {
    [inteiro, fracao = ""] = texto.split(",");
  } else if (/^\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?$/.test(texto)) {
    const partes = texto.split(",");
    inteiro = partes[0].replaceAll(".", "");
    fracao = partes[1] ?? "";
  } else if (/^\d+\.\d{1,2}$/.test(texto)) {
    [inteiro, fracao] = texto.split(".");
  } else {
    return null;
  }
  inteiro = inteiro.replace(/^0+(?=\d)/, "");
  if (inteiro.length > 12) return null;
  const centavos = fracao.padEnd(2, "0");
  return inteiro === "0" && centavos === "00" ? null : `${inteiro}.${centavos}`;
}

export function validarProposta(campos: CamposProposta): { dados: DadosProposta | null; erro: string } {
  const valor = normalizarValorProposta(campos.valor);
  if (valor === null) return { dados: null, erro: "Informe um valor maior que zero, com até 12 dígitos inteiros e 2 casas decimais. Exemplo: 1.250,50." };
  const prazo = /^\d+$/.test(campos.prazo.trim()) ? Number(campos.prazo) : NaN;
  const validade = /^\d+$/.test(campos.validade.trim()) ? Number(campos.validade) : NaN;
  if (!Number.isInteger(prazo) || prazo < 1 || prazo > 3650) return { dados: null, erro: "Informe o prazo de execução entre 1 e 3650 dias." };
  if (!Number.isInteger(validade) || validade < 1 || validade > 3650) return { dados: null, erro: "Informe a validade da proposta entre 1 e 3650 dias." };
  if (campos.observacoes.length > 5000) return { dados: null, erro: "As observações podem ter até 5000 caracteres." };
  return { dados: { valor_total: valor, prazo_dias: prazo, validade_dias: validade, observacoes: campos.observacoes.trim() || null }, erro: "" };
}

export function mensagemErroFornecedor(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const detalhe = (erro as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
    const mensagens: Record<string, string> = {
      empresa_fornecedora_nao_encontrada: "A empresa do fornecedor não foi encontrada. Confira o cadastro da empresa.",
      empresa_nao_e_fornecedora: "A empresa deste acesso precisa estar cadastrada como fornecedor ou ambos.",
      solicitacao_nao_encontrada: "A solicitação não foi encontrada. Atualize a lista.",
      solicitacao_nao_esta_aberta: "Esta solicitação já foi encerrada. Atualize as oportunidades.",
      fornecedor_nao_compativel_com_a_solicitacao: "A capacidade da sua empresa não atende a esta solicitação. Confira processo, material, dimensões e tolerância.",
      cotacao_ja_cadastrada_para_este_fornecedor: "Sua empresa já enviou uma cotação para esta solicitação. Consulte Minhas Cotações.",
      solicitacao_ja_possui_cotacao_aceita: "O cliente já aceitou uma cotação para esta solicitação.",
      fornecedor_sem_acesso_a_solicitacao: "Sua empresa não possui acesso aos arquivos desta solicitação.",
      arquivo_tecnico_nao_encontrado: "O arquivo não está mais disponível. Atualize os arquivos.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize a tela e tente novamente.";
    if (Array.isArray(detalhe)) return "Os dados não foram aceitos. Confira valor, prazo, validade e observações.";
  }
  return "Não foi possível confirmar a operação. Confira a conexão e atualize a tela.";
}

export function formatarTamanhoArquivo(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "Tamanho indisponível";
  if (bytes < 1024) return `${bytes} B`;
  const unidade = bytes >= 1024 * 1024 ? "MB" : "KB";
  const valor = bytes / (unidade === "MB" ? 1024 * 1024 : 1024);
  return `${valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} ${unidade}`;
}
