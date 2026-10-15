import {useEffect,useRef,useState} from "react";
import {useAuth} from "../../auth/AuthContext";
import {api} from "../../services/api";
import type {CotacaoConsulta} from "../cotacoes-cliente/consultaCotacoes";
import {brl,erroPreco,rotuloAnalise} from "./preco";
import "./FormacaoPreco.css";
export default function AnaliseOrcamentoCliente({cotacao,aoRegistrar}:{cotacao:CotacaoConsulta;aoRegistrar:()=>void}){
 const {user}=useAuth();const empresa=user?.role==='cliente'?user.empresa_id:0,contexto=user&&empresa?`${user.usuario_id}:cliente:${empresa}`:"";
 const [acao,setAcao]=useState<"aprovar"|"revisar"|"recusar"|null>(null),[observacao,setObservacao]=useState(""),[erro,setErro]=useState(""),[ocupado,setOcupado]=useState(false);
 const chave=useRef(crypto.randomUUID()),trava=useRef(false),montada=useRef(true),controle=useRef<AbortController|null>(null);
 useEffect(()=>{montada.current=true;return()=>{montada.current=false;controle.current?.abort();};},[]);
 async function confirmar(){
  if(!acao||!empresa||cotacao.empresa_cliente_id!==empresa||!cotacao.pode_analisar||!cotacao.versao_preco||trava.current)return;
  if(acao!=='aprovar'&&observacao.trim().length<3){setErro("Informe o motivo da revisão ou da recusa.");return;}
  trava.current=true;setOcupado(true);setErro("");const c=new AbortController();controle.current=c;
  try{const {data:r}=await api.post<{contexto:string;cotacao_id:number}>(`/portal-cliente/cotacoes/${cotacao.id}/analise`,{empresa_cliente_id:empresa,acao,versao:cotacao.versao_preco,observacao:observacao.trim(),chave_operacao:chave.current},{params:{empresa_cliente_id:empresa},headers:{"X-MEC-Preco-Contexto":contexto},signal:c.signal,timeout:30000});
   if(!montada.current||c.signal.aborted)return;
   if(r.contexto!==contexto||r.cotacao_id!==cotacao.id)throw new Error("resposta_divergente");
   setAcao(null);aoRegistrar();
  }catch(e){if(montada.current&&!c.signal.aborted)setErro(erroPreco(e));}finally{trava.current=false;if(montada.current)setOcupado(false);}
 }
 if(!contexto||cotacao.empresa_cliente_id!==empresa||!cotacao.analise_cliente)return null;
 return <section className="p60" aria-label="Análise do orçamento"><h3>Análise do orçamento</h3><p>{rotuloAnalise[cotacao.analise_cliente]??"Consulte a administração."}</p>
  {cotacao.analise_cliente==='publicada'&&!cotacao.pode_analisar&&<p>A validade ou as condições deste orçamento mudaram. Aguarde a conferência da administração.</p>}
  {erro&&<p role="alert">{erro}</p>}{cotacao.pode_analisar&&cotacao.versao_preco&&<><p>Preço final: <strong>{brl(cotacao.valor_total)}</strong> · {cotacao.prazo_dias} dias de execução. A administração confirma a contratação após a sua aprovação.</p>
   {!acao?<div className="p60-acoes">{(['aprovar','revisar','recusar'] as const).map(a=><button key={a} disabled={ocupado} onClick={()=>{setAcao(a);setObservacao("");setErro("");chave.current=crypto.randomUUID();}}>{a==='aprovar'?"Aprovar orçamento":a==='revisar'?"Pedir revisão":"Recusar orçamento"}</button>)}</div>:<div className="p60-conferencia"><h4>{acao==='aprovar'?"Confirmar aprovação":acao==='revisar'?"Solicitar revisão":"Confirmar recusa"}</h4>
    <label>{acao==='aprovar'?"Observação para a administração (opcional)":"Motivo para a administração"}<textarea maxLength={2000} value={observacao} disabled={ocupado} onChange={e=>{setObservacao(e.target.value);chave.current=crypto.randomUUID();}}/></label>
    <div className="p60-acoes"><button disabled={ocupado||(acao!=='aprovar'&&observacao.trim().length<3)} onClick={()=>void confirmar()}>{ocupado?"Registrando…":acao==='aprovar'?"Confirmar aprovação":acao==='revisar'?"Confirmar pedido de revisão":"Confirmar recusa"}</button><button disabled={ocupado} onClick={()=>setAcao(null)}>Voltar</button></div></div>}
  </>}
 </section>;
}
