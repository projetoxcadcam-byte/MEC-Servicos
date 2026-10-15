export const camposResultado = [
 ["venda_cliente", "Venda aos clientes"], ["custo_fornecedor", "Custo dos fornecedores"],
 ["ganho_bruto_previsto", "Ganho bruto previsto"], ["despesas_previstas", "Despesas previstas"],
 ["resultado_previsto", "Resultado previsto"], ["ganho_bruto_confirmado", "Ganho bruto confirmado"],
 ["despesas_pagas", "Despesas pagas confirmadas"], ["resultado_apos_despesas", "Resultado após despesas pagas"],
 ["resultado_liquidado_apos_despesas", "Resultado dos serviços liquidados após despesas"],
] as const;
export type ValoresRelatorio = Record<(typeof camposResultado)[number][0], string>;
export type ContratoRelatorio = ValoresRelatorio & {contratacao_id:number;ordem_servico_id:number|null;cliente:string;fornecedor:string;criada_em:string;liquidado:boolean;situacao:string};
export type DespesaRelatorio = {id:number;contratacao_id:number;categoria:string;descricao:string;valor:string;paga_em:string;status:"confirmada"|"estornada";referencia:string;registro_interno:string;administrador_nome:string;criada_em:string;estornada_em:string|null;motivo_estorno:string|null;referencia_estorno:string|null};
export type RelatorioResultado = {contexto:string;inicio:string;fim:string;base_periodo:string;gerado_em:string;versao:string;total:number;liquidadas:number;totais:ValoresRelatorio;itens:ContratoRelatorio[];despesas:DespesaRelatorio[];despesas_confirmadas:number;despesas_estornadas:number;valor_estornado:string};
export const categoriasDespesa:Record<string,string> = {coleta:"Coleta",transporte:"Transporte",frete:"Frete",embalagem:"Embalagem",inspecao:"Inspeção",outros:"Outros"};
const dinheiro = (v:unknown):v is string => typeof v === "string" && /^-?\d+\.\d{2}$/.test(v);
const centavos = (v:string) => BigInt(v.replace(".", ""));
const id = (v:unknown):v is number => typeof v === "number" && Number.isSafeInteger(v) && v>0;
const instante = (v:unknown):v is string => typeof v === "string" && Number.isFinite(Date.parse(v));
export const dataRelatorio = (v:string) => v.split("-").reverse().join("/");
export const instanteRelatorio = (v:string) => new Date(v).toLocaleString("pt-BR", {timeZone:"UTC"}) + " UTC";
export function moedaRelatorio(v:string) {
 const [inteiro, fracao] = v.replace(/^-/, "").split(".");
 return `${v.startsWith("-")?"-":""}R$ ${BigInt(inteiro).toLocaleString("pt-BR")},${fracao}`;
}
export function validarRelatorio(r:RelatorioResultado, contexto:string, inicio:string, fim:string) {
 const recusar = () => {throw new Error("resposta_relatorio_divergente");};
 if(!r || r.contexto!==contexto || r.inicio!==inicio || r.fim!==fim || r.base_periodo!=="criacao_contratacao_utc" || !instante(r.gerado_em) || !/^[0-9a-f]{64}$/.test(r.versao) || !Array.isArray(r.itens) || !Array.isArray(r.despesas) || r.total!==r.itens.length || !r.totais)recusar();
 const contratos=new Map<number,ContratoRelatorio>(), soma=new Map<string,bigint>();
 for(const [k] of camposResultado){if(!dinheiro(r.totais[k]))recusar();soma.set(k,0n);}
 for(const c of r.itens){
  if(!c || !id(c.contratacao_id) || contratos.has(c.contratacao_id) || (c.ordem_servico_id!==null&&!id(c.ordem_servico_id)) || typeof c.cliente!=="string" || typeof c.fornecedor!=="string" || typeof c.liquidado!=="boolean" || !instante(c.criada_em))recusar();
  contratos.set(c.contratacao_id,c);
  for(const [k] of camposResultado){if(!dinheiro(c[k]))recusar();soma.set(k,soma.get(k)!+centavos(c[k]));}
  const ganho=centavos(c.venda_cliente)-centavos(c.custo_fornecedor), resultado=ganho-centavos(c.despesas_pagas);
  if(centavos(c.ganho_bruto_previsto)!==ganho || centavos(c.resultado_previsto)!==ganho-centavos(c.despesas_previstas) || centavos(c.resultado_apos_despesas)!==resultado || centavos(c.ganho_bruto_confirmado)!==(c.liquidado?ganho:0n) || centavos(c.resultado_liquidado_apos_despesas)!==(c.liquidado?resultado:0n))recusar();
 }
 for(const [k] of camposResultado)if(soma.get(k)!==centavos(r.totais[k]))recusar();
 const despesas=new Set<number>(), pagas=new Map<number,bigint>();let confirmadas=0,estornadas=0,estornado=0n;
 for(const d of r.despesas){
  if(!d || !id(d.id) || despesas.has(d.id) || !contratos.has(d.contratacao_id) || !categoriasDespesa[d.categoria] || !dinheiro(d.valor) || centavos(d.valor)<=0n || !/^\d{4}-\d{2}-\d{2}$/.test(d.paga_em) || !instante(d.criada_em) || ![d.descricao,d.referencia,d.registro_interno,d.administrador_nome].every(v=>typeof v==="string"))recusar();
  despesas.add(d.id);
  if(d.status==="confirmada"){
   if(d.estornada_em!==null || d.motivo_estorno!==null || d.referencia_estorno!==null)recusar();
   ++confirmadas;pagas.set(d.contratacao_id,(pagas.get(d.contratacao_id)??0n)+centavos(d.valor));
  } else if(d.status==="estornada"){
   if(!instante(d.estornada_em) || (d.motivo_estorno!==null&&typeof d.motivo_estorno!=="string") || (d.referencia_estorno!==null&&typeof d.referencia_estorno!=="string"))recusar();
   ++estornadas;estornado+=centavos(d.valor);
  } else recusar();
 }
 for(const c of r.itens)if((pagas.get(c.contratacao_id)??0n)!==centavos(c.despesas_pagas))recusar();
 if(r.liquidadas!==r.itens.filter(c=>c.liquidado).length || r.despesas_confirmadas!==confirmadas || r.despesas_estornadas!==estornadas || !dinheiro(r.valor_estornado) || centavos(r.valor_estornado)!==estornado)recusar();
}
