import {camposResultado,type ValoresRelatorio} from "./dadosRelatorioResultado";
import {centavosAnalise,dinheiroCentavos} from "./dadosAnaliseResultado";
export type MesMeta={mes:string;nome:string;fase:"encerrado"|"em_andamento"|"futuro";total:number;liquidadas:number;totais:ValoresRelatorio;meta:string|null;diferenca:string|null;atingimento_percentual:string|null;situacao:"sem_meta"|"meta_zero"|"alcancada"|"abaixo"};
export type DadosMetas={contexto:string;ano:number;base_periodo:string;base_meta:string;consulta_em:string;hoje_utc:string;versao:string;total:number;liquidadas:number;totais:ValoresRelatorio;meses_com_meta:number;meta_total:string|null;realizado_com_meta:string;diferenca_total:string|null;atingimento_total_percentual:string|null;meses:MesMeta[]};
export type MetaAtual={valor:string;estado:"ativa"|"retirada";administrador_nome:string;atualizada_em:string};
export type EventoMeta={id:number;versao:number;acao:"definir"|"retirar";valor_anterior:string|null;valor_atual:string|null;administrador_nome:string;registro_interno:string;criado_em:string};
export type DetalheMeta={contexto:string;mes:string;versao:string;meta:MetaAtual|null;total_eventos:number;deslocamento:number;limite:number;historico:EventoMeta[]};
export const situacaoMeta={sem_meta:"Sem meta",meta_zero:"Meta zero",alcancada:"Meta alcançada",abaixo:"Abaixo da meta"};
export const faseMeta={encerrado:"Mês anterior",em_andamento:"Mês em andamento",futuro:"Mês futuro"};
export const percentualMeta=(v:string|null)=>v===null?"—":v.replace(".",",")+"%";
export function razaoMeta(realizado:bigint,meta:bigint|null){if(meta===null||meta===0n)return null;const n=realizado*10000n,abs=n<0n?-n:n;const arredondado=abs/meta+(abs%meta*2n>=meta?1n:0n);return dinheiroCentavos(n<0n?-arredondado:arredondado);}
const dinheiro=(v:unknown):v is string=>typeof v==="string"&&/^-?\d+\.\d{2}$/.test(v);
const qtd=(v:unknown):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>=0;
const instante=(v:unknown):v is string=>typeof v==="string"&&v.endsWith("Z")&&Number.isFinite(Date.parse(v));
export function validarMetas(r:DadosMetas,contexto:string,ano:number){
 const negar=()=>{throw new Error("resposta_metas_divergente");};
 if(!r||r.contexto!==contexto||r.ano!==ano||r.base_periodo!=="criacao_contratacao_utc"||r.base_meta!=="resultado_liquidado_apos_despesas"||!instante(r.consulta_em)||!/^\d{4}-\d{2}-\d{2}$/.test(r.hoje_utc)||!/^[a-f0-9]{64}$/.test(r.versao)||!Array.isArray(r.meses)||r.meses.length!==12||!qtd(r.total)||!qtd(r.liquidadas)||!r.totais)negar();
 const somas=new Map(camposResultado.map(([k])=>[k,0n]));let total=0,liquidadas=0,quantidade=0,metaTotal=0n,realizadoMeta=0n;
 for(let i=0;i<12;i++){const m=r.meses[i],chave=`${ano}-${String(i+1).padStart(2,"0")}`;
  if(!m||m.mes!==chave||m.nome!==String(i+1).padStart(2,"0")+"/"+ano||!qtd(m.total)||!qtd(m.liquidadas)||m.liquidadas>m.total||!m.totais||m.fase!==(chave<r.hoje_utc.slice(0,7)?"encerrado":chave===r.hoje_utc.slice(0,7)?"em_andamento":"futuro"))negar();
  total+=m.total;liquidadas+=m.liquidadas;for(const [k] of camposResultado){if(!dinheiro(m.totais[k]))negar();somas.set(k,somas.get(k)!+centavosAnalise(m.totais[k]));}
  if(centavosAnalise(m.totais.ganho_bruto_previsto)!==centavosAnalise(m.totais.venda_cliente)-centavosAnalise(m.totais.custo_fornecedor)||centavosAnalise(m.totais.resultado_previsto)!==centavosAnalise(m.totais.ganho_bruto_previsto)-centavosAnalise(m.totais.despesas_previstas)||centavosAnalise(m.totais.resultado_apos_despesas)!==centavosAnalise(m.totais.ganho_bruto_previsto)-centavosAnalise(m.totais.despesas_pagas))negar();
  const real=centavosAnalise(m.totais.resultado_liquidado_apos_despesas);
  if(m.meta===null){if(m.diferenca!==null||m.atingimento_percentual!==null||m.situacao!=="sem_meta")negar();}
  else{if(!dinheiro(m.meta)||centavosAnalise(m.meta)<0n||!dinheiro(m.diferenca)||centavosAnalise(m.diferenca)!==real-centavosAnalise(m.meta)||m.atingimento_percentual!==razaoMeta(real,centavosAnalise(m.meta))||m.situacao!==(centavosAnalise(m.meta)===0n?"meta_zero":real>=centavosAnalise(m.meta)?"alcancada":"abaixo"))negar();++quantidade;metaTotal+=centavosAnalise(m.meta);realizadoMeta+=real;}
 }
 for(const [k] of camposResultado)if(!dinheiro(r.totais[k])||centavosAnalise(r.totais[k])!==somas.get(k))negar();
 if(total!==r.total||liquidadas!==r.liquidadas||quantidade!==r.meses_com_meta||r.meta_total!==(quantidade?dinheiroCentavos(metaTotal):null)||r.realizado_com_meta!==dinheiroCentavos(realizadoMeta)||r.diferenca_total!==(quantidade?dinheiroCentavos(realizadoMeta-metaTotal):null)||r.atingimento_total_percentual!==razaoMeta(realizadoMeta,quantidade?metaTotal:null))negar();
}
export function validarDetalheMeta(r:DetalheMeta,contexto:string,mes:string,pagina:number){
 const negar=()=>{throw new Error("historico_meta_divergente");};
 if(!r||r.contexto!==contexto||r.mes!==mes||!/^[a-f0-9]{64}$/.test(r.versao)||!qtd(r.total_eventos)||r.deslocamento!==pagina*20||r.limite!==20||!Array.isArray(r.historico)||r.historico.length!==Math.min(20,Math.max(0,r.total_eventos-pagina*20)))negar();
 if(r.meta===null){if(r.total_eventos!==0)negar();}else if(!dinheiro(r.meta.valor)||centavosAnalise(r.meta.valor)<0n||!["ativa","retirada"].includes(r.meta.estado)||typeof r.meta.administrador_nome!=="string"||!instante(r.meta.atualizada_em))negar();
 const ids=new Set<number>();for(let i=0;i<r.historico.length;i++){const e=r.historico[i];if(!e||!qtd(e.id)||e.id===0||ids.has(e.id)||e.versao!==r.total_eventos-pagina*20-i||typeof e.administrador_nome!=="string"||typeof e.registro_interno!=="string"||!instante(e.criado_em)||(e.valor_anterior!==null&&(!dinheiro(e.valor_anterior)||centavosAnalise(e.valor_anterior)<0n))||(e.acao==="definir"?(!dinheiro(e.valor_atual)||centavosAnalise(e.valor_atual)<0n):e.acao!=="retirar"||e.valor_atual!==null))negar();ids.add(e.id);}
 if(pagina===0&&r.meta&&r.historico[0]){const e=r.historico[0];if(r.meta.estado==="ativa"?(e.acao!=="definir"||e.valor_atual!==r.meta.valor):e.acao!=="retirar")negar();}
}
