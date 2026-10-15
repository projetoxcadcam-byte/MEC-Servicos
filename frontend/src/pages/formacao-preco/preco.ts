export const rotuloAnalise: Record<string,string> = {
  rascunho:"Rascunho administrativo",publicada:"Aguardando análise do cliente",aprovada_cliente:"Cliente aprovou · aguardando contratação pelo ADM",
  revisao_cliente:"Cliente pediu revisão",recusada_cliente:"Cliente recusou o orçamento",retirada:"Orçamento em revisão administrativa",contratada:"Contratação registrada",
};
export const brl=(v:string)=>Number(v).toLocaleString("pt-BR",{style:"currency",currency:"BRL"});
export function numeroPreco(v:string,casas=2) {
  const t=v.trim();
  if (!new RegExp(`^(?:0|[1-9]\\d{0,11})(?:[,.]\\d{1,${casas}})?$`).test(t)) return null;
  return t.replace(",",".");
}
export function erroPreco(e:unknown) {
  const r=(e as {response?:{status?:number;data?:{detail?:unknown}}}).response;
  const mensagens:Record<string,string>={
    preco_alterado_atualize:"O preço ou as condições mudaram. Atualize e confira novamente.",
    conferencia_preco_divergente:"A conferência mudou. Confira o preço novamente antes de registrar.",
    outra_proposta_publicada_retire_primeiro:"Já há outro orçamento publicado nesta solicitação. Retire o anterior antes de publicar este.",
    cotacao_expirada:"A cotação venceu. Solicite uma nova proposta ao fornecedor.",
    documentacao_para_cotacao_obrigatoria:"Revise e libere um documento técnico antes de publicar.",
    orcamento_nao_disponivel_para_analise:"Este orçamento não está mais disponível para análise. Atualize os detalhes.",
    orcamento_cliente_aguarda_aprovacao:"Publique o preço final e aguarde a aprovação do cliente antes de aceitar a cotação.",
    contexto_precificacao_alterado:"O acesso mudou. Entre novamente antes de continuar.",
    cotacao_nao_esta_pendente:"Esta cotação já recebeu uma decisão. Atualize para conferir.",
  };
  if(r?.status===401||r?.status===403)return "Entre novamente com o perfil autorizado para esta ação.";
  if(typeof r?.data?.detail==='string' && mensagens[r.data.detail])return mensagens[r.data.detail];
  return r?.status===422?"Confira os valores, o percentual e os campos obrigatórios.":r?.status===409?"Os dados mudaram ou esta ação não está disponível. Atualize e confira novamente.":"Não foi possível concluir. Confira a conexão e tente novamente.";
}
