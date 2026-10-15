export type UsuarioServidor = {
  id: number; usuario_id: number; empresa_id: number | null; nome: string; email: string;
  role: "admin" | "cliente" | "fornecedor"; deve_alterar_senha: boolean; teste_local?: boolean;
};
export type SessaoServidor = { usuario: UsuarioServidor; csrf: string };
const EVENTO_EXPIRACAO = "mec-acesso-expirou";
let csrfAtual = "";
let transporteInstalado = false;

export function definirCsrf(valor: string) { csrfAtual = valor; }
export function obterCsrf() { return csrfAtual; }
export function limparAcessoLocal() {
  csrfAtual = "";
  window.dispatchEvent(new Event(EVENTO_EXPIRACAO));
}
export function observarExpiracao(funcao: () => void) {
  window.addEventListener(EVENTO_EXPIRACAO, funcao);
  return () => window.removeEventListener(EVENTO_EXPIRACAO, funcao);
}

export function instalarTransporteAcesso() {
  if (transporteInstalado) return;
  transporteInstalado = true;
  const original = window.fetch.bind(window);
  window.fetch = async (entrada: RequestInfo | URL, opcoes?: RequestInit) => {
    const endereco = entrada instanceof Request ? entrada.url : String(entrada);
    const url = new URL(endereco, window.location.href);
    if (url.origin !== window.location.origin || !/^\/api\/v1(?:\/|$)/.test(url.pathname)) return original(entrada, opcoes);
    const metodo = (opcoes?.method ?? (entrada instanceof Request ? entrada.method : "GET")).toUpperCase();
    const cabecalhos = new Headers(entrada instanceof Request ? entrada.headers : undefined);
    new Headers(opcoes?.headers).forEach((valor, chave) => cabecalhos.set(chave, valor));
    if (!["GET", "HEAD", "OPTIONS"].includes(metodo) && csrfAtual) cabecalhos.set("X-MEC-CSRF", csrfAtual);
    const resposta = await original(entrada, { ...opcoes, headers: cabecalhos, credentials: "same-origin" });
    if (resposta.status === 401 && !url.pathname.startsWith("/api/v1/autenticacao/")) limparAcessoLocal();
    return resposta;
  };
}

export class ErroAcesso extends Error {
  status: number; detalhe: string;
  constructor(status: number, detalhe: string) { super(mensagemAcesso(detalhe)); this.status = status; this.detalhe = detalhe; }
}
export function mensagemAcesso(detalhe: string): string {
  const mensagens: Record<string, string> = {
    modo_teste_local_indisponivel: "Inicie o backend pelo comando de teste local para usar este acesso.",
    entrada_teste_local_nao_confirmada: "Atualize a página e escolha a conta de teste novamente.",
    conta_teste_local_indisponivel: "Essa conta não está ativa para o teste local.",
    sessao_teste_local_encerrada: "O modo de teste local foi encerrado. Entre novamente.",
    email_ou_senha_invalidos: "E-mail ou senha inválidos.",
    muitas_tentativas_aguarde: "Foram feitas várias tentativas. Aguarde 15 minutos para tentar novamente.",
    acesso_servidor_nao_configurado: "As contas de acesso ainda não foram configuradas no servidor.",
    sessao_nao_autenticada: "Entre para acessar a plataforma.",
    sessao_expirada_entre_novamente: "Sua sessão expirou. Entre novamente.",
    sessao_alterada_entre_novamente: "A sessão foi alterada em outra aba. Entre novamente antes de repetir a operação.",
    troca_senha_inicial_obrigatoria: "Altere sua senha inicial em Minha conta para continuar.",
    senha_atual_invalida: "A senha atual está incorreta.",
    senha_deve_ter_12_a_128_caracteres: "Use uma senha com 12 a 128 caracteres.",
    nova_senha_deve_ser_diferente: "A nova senha deve ser diferente da senha atual.",
    acao_exclusiva_da_administracao: "Esta operação é realizada pela administração.",
    arquivo_aguarda_liberacao_administrativa: "O arquivo técnico será encaminhado pela administração após revisão.",
    empresa_diverge_da_sessao: "A empresa informada não corresponde à conta autenticada.",
    vinculo_empresa_nao_autorizado: "O vínculo da sua conta com a empresa precisa ser conferido pela administração.",
    vinculo_empresa_invalido: "Informe uma empresa válida para o perfil da conta.",
    email_ja_cadastrado: "Já existe uma conta com esse e-mail.",
    dados_de_acesso_invalidos: "Confira os campos informados. A senha deve ter entre 12 e 128 caracteres.",
    origem_nao_autorizada: "O endereço usado para acessar o portal precisa ser autorizado pela administração.",
    ultimo_administrador_nao_pode_ser_desativado: "Mantenha pelo menos uma conta administrativa ativa.",
  };
  return mensagens[detalhe] ?? "Não foi possível concluir a operação de acesso. Confira os dados e tente novamente.";
}

export async function requisitarAcesso<T>(caminho: string, dados?: unknown, metodo = dados === undefined ? "GET" : "POST", cabecalhos: Record<string, string> = {}): Promise<T> {
  instalarTransporteAcesso();
  let resposta: Response;
  try {
    resposta = await window.fetch(`/api/v1/autenticacao${caminho}`, {
      method: metodo, headers: { ...(dados === undefined ? {} : { "Content-Type": "application/json" }), ...cabecalhos },
      body: dados === undefined ? undefined : JSON.stringify(dados), cache: "no-store",
    });
  } catch {
    throw new Error("Não foi possível conectar ao servidor. Confira se o backend está em execução.");
  }
  const corpo = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new ErroAcesso(resposta.status, typeof corpo.detail === "string" ? corpo.detail : "dados_de_acesso_invalidos");
  return corpo as T;
}

export function validarSessao(dados: SessaoServidor): SessaoServidor {
  const usuario = dados?.usuario;
  if (!usuario || !["admin", "cliente", "fornecedor"].includes(usuario.role) || !Number.isInteger(usuario.usuario_id) || usuario.usuario_id <= 0
      || typeof dados.csrf !== "string" || !dados.csrf || !Number.isInteger(usuario.id)
      || (usuario.teste_local !== undefined && typeof usuario.teste_local !== "boolean") || typeof usuario.deve_alterar_senha !== "boolean" || typeof usuario.nome !== "string" || typeof usuario.email !== "string"
      || (usuario.role === "admin" ? usuario.empresa_id !== null || usuario.id !== usuario.usuario_id : usuario.id !== usuario.empresa_id || usuario.id <= 0)) throw new Error("O servidor retornou uma sessão inválida.");
  return dados;
}
