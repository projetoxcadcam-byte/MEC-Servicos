import {camposResultado,type ContratoRelatorio,type ValoresRelatorio} from "./dadosRelatorioResultado";
export type IndicadorAnalise=keyof ValoresRelatorio;
export type FiltrosAnalise={empresa_cliente_id:number|null;empresa_fornecedora_id:number|null;liquidacao:"todas"|"liquidadas"|"aguardando"};
export type EmpresaAnalise={id:number;nome:string};
export type GrupoAnalise={chave:string;empresa_id:number|null;nome:string;total:number;liquidadas:number;totais:ValoresRelatorio};
export type ContratoAnalise=ContratoRelatorio&{empresa_cliente_id:number;empresa_fornecedora_id:number};
export type DadosAnalise={contexto:string;inicio:string;fim:string;base_periodo:string;gerado_em:string;versao:string;filtros:FiltrosAnalise;opcoes_clientes:EmpresaAnalise[];opcoes_fornecedores:EmpresaAnalise[];total_periodo:number;total:number;liquidadas:number;totais:ValoresRelatorio;meses:GrupoAnalise[];clientes:GrupoAnalise[];fornecedores:GrupoAnalise[];itens:ContratoAnalise[]};
export const centavosAnalise=(v:string)=>BigInt(v.replace(".",""));
export function dinheiroCentavos(v:bigint){const abs=v<0n?-v:v;return `${v<0n?"-":""}${abs/100n}.${String(abs%100n).padStart(2,"0")}`;}
const dinheiro=(v:unknown):v is string=>typeof v==="string"&&/^-?\d+\.\d{2}$/.test(v);
const id=(v:unknown):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>0&&v<=9999999999999;
const quantidade=(v:unknown):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=0;
const instante=(v:unknown):v is string=>typeof v==="string"&&v.endsWith("Z")&&Number.isFinite(Date.parse(v));
type Acumulado={total:number;liquidadas:number;valores:Map<IndicadorAnalise,bigint>};
const vazio=():Acumulado=>({total:0,liquidadas:0,valores:new Map(camposResultado.map(([k])=>[k,0n]))});
function somar(a:Acumulado,c:ContratoAnalise){++a.total;a.liquidadas+=Number(c.liquidado);for(const [k] of camposResultado)a.valores.set(k,a.valores.get(k)!+centavosAnalise(c[k]));}
export function validarAnalise(r:DadosAnalise,contexto:string,inicio:string,fim:string,filtros:FiltrosAnalise){
 const recusar=()=>{throw new Error("analise_resultado_divergente");};
 if(!r||r.contexto!==contexto||r.inicio!==inicio||r.fim!==fim||r.base_periodo!=="criacao_contratacao_utc"||!instante(r.gerado_em)||!/^[0-9a-f]{64}$/.test(r.versao)||!r.filtros||Object.keys(filtros).some(k=>r.filtros[k as keyof FiltrosAnalise]!==filtros[k as keyof FiltrosAnalise])||!Array.isArray(r.itens)||!quantidade(r.total_periodo)||r.total_periodo<r.total||r.total!==r.itens.length||!r.totais)recusar();
 function opcoes(lista:EmpresaAnalise[]){if(!Array.isArray(lista))recusar();const mapa=new Map<number,string>();for(const e of lista){if(!e||!id(e.id)||typeof e.nome!=="string"||mapa.has(e.id))recusar();mapa.set(e.id,e.nome);}return mapa;}
 const clientes=opcoes(r.opcoes_clientes),fornecedores=opcoes(r.opcoes_fornecedores);
 if((filtros.empresa_cliente_id!==null&&!clientes.has(filtros.empresa_cliente_id))||(filtros.empresa_fornecedora_id!==null&&!fornecedores.has(filtros.empresa_fornecedora_id)))recusar();
 const meses=new Map<string,Acumulado>(),gc=new Map<string,Acumulado>(),gf=new Map<string,Acumulado>(),total=vazio(),ids=new Set<number>();
 let [ano,mes]=inicio.split("-").map(Number);const [ultimoAno,ultimoMes]=fim.split("-").map(Number);
 while(ano<ultimoAno||ano===ultimoAno&&mes<=ultimoMes){meses.set(`${String(ano).padStart(4,"0")}-${String(mes).padStart(2,"0")}`,vazio());if(++mes===13){mes=1;++ano;}}
 for(const c of r.itens){
  if(!c||!id(c.contratacao_id)||ids.has(c.contratacao_id)||(c.ordem_servico_id!==null&&!id(c.ordem_servico_id))||!id(c.empresa_cliente_id)||!id(c.empresa_fornecedora_id)||clientes.get(c.empresa_cliente_id)!==c.cliente||fornecedores.get(c.empresa_fornecedora_id)!==c.fornecedor||typeof c.liquidado!=="boolean"||typeof c.situacao!=="string"||!instante(c.criada_em)||c.criada_em.slice(0,10)<inicio||c.criada_em.slice(0,10)>fim||!meses.has(c.criada_em.slice(0,7)))recusar();
  if((filtros.empresa_cliente_id!==null&&c.empresa_cliente_id!==filtros.empresa_cliente_id)||(filtros.empresa_fornecedora_id!==null&&c.empresa_fornecedora_id!==filtros.empresa_fornecedora_id)||(filtros.liquidacao!=="todas"&&c.liquidado!==(filtros.liquidacao==="liquidadas")))recusar();
  ids.add(c.contratacao_id);for(const [k] of camposResultado)if(!dinheiro(c[k]))recusar();
  const ganho=centavosAnalise(c.venda_cliente)-centavosAnalise(c.custo_fornecedor),apos=ganho-centavosAnalise(c.despesas_pagas);
  if(centavosAnalise(c.ganho_bruto_previsto)!==ganho||centavosAnalise(c.resultado_previsto)!==ganho-centavosAnalise(c.despesas_previstas)||centavosAnalise(c.resultado_apos_despesas)!==apos||centavosAnalise(c.ganho_bruto_confirmado)!==(c.liquidado?ganho:0n)||centavosAnalise(c.resultado_liquidado_apos_despesas)!==(c.liquidado?apos:0n))recusar();
  somar(total,c);somar(meses.get(c.criada_em.slice(0,7))!,c);
  for(const [mapa,eid] of [[gc,c.empresa_cliente_id],[gf,c.empresa_fornecedora_id]] as const){const chave=String(eid);if(!mapa.has(chave))mapa.set(chave,vazio());somar(mapa.get(chave)!,c);}
 }
 function conferir(valores:ValoresRelatorio,a:Acumulado){if(!valores)recusar();for(const [k] of camposResultado)if(!dinheiro(valores[k])||centavosAnalise(valores[k])!==a.valores.get(k))recusar();}
 conferir(r.totais,total);if(r.liquidadas!==total.liquidadas)recusar();
 function grupos(lista:GrupoAnalise[],esperados:Map<string,Acumulado>,nomes:Map<number,string>|null){
  if(!Array.isArray(lista)||lista.length!==esperados.size)recusar();const vistos=new Set<string>();
  for(const g of lista){const a=g&&esperados.get(g.chave);if(!g||!a||vistos.has(g.chave)||g.total!==a.total||g.liquidadas!==a.liquidadas||typeof g.nome!=="string")recusar();
   if(nomes?(g.empresa_id===null||String(g.empresa_id)!==g.chave||nomes.get(g.empresa_id)!==g.nome):(g.empresa_id!==null||g.nome!==g.chave.slice(5)+"/"+g.chave.slice(0,4)))recusar();
   vistos.add(g.chave);conferir(g.totais,a!);
  }
 }
 grupos(r.meses,meses,null);grupos(r.clientes,gc,clientes);grupos(r.fornecedores,gf,fornecedores);
 if(r.meses.some((g,i)=>g.chave!==[...meses.keys()][i]))recusar();
}
