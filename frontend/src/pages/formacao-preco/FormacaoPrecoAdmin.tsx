import {useEffect,useRef,useState} from "react";
import {useAuth} from "../../auth/AuthContext";
import {api} from "../../services/api";
import {brl,erroPreco,numeroPreco,rotuloAnalise} from "./preco";
import "./FormacaoPreco.css";
type Valores={modo:"percentual"|"valor";acrescimo_informado:string;custo_fornecedor:string;acrescimo:string;preco_cliente:string;despesas_previstas:string;resultado_previsto:string;estado:string;numero_versao:number;contratacao_id:number|null;atualizado_em:string};
type Preco={contexto:string;cotacao_id:number;solicitacao_id:number;versao:string;custo_fornecedor:string;pode_editar:boolean;preco:Valores|null;historico:{id:number;acao:string;perfil:string;registro:string;criado_em:string}[]};
type Conferencia={contexto:string;versao:string;conferencia:string;custo_fornecedor:string;acrescimo:string;preco_cliente:string;despesas_previstas:string;resultado_previsto:string};
export default function FormacaoPrecoAdmin({cotacaoId,solicitacaoId,aoRegistrar}:{cotacaoId:number;solicitacaoId:number;aoRegistrar:()=>void}) {
 const {user}=useAuth();const contexto=user?.role==='admin'?`${user.usuario_id}:admin:0`:"";
 const [preco,setPreco]=useState<Preco|null>(null),[erro,setErro]=useState(""),[ocupado,setOcupado]=useState(false),[revisao,setRevisao]=useState(0);
 const [modo,setModo]=useState<"percentual"|"valor">("percentual"),[valor,setValor]=useState(""),[despesas,setDespesas]=useState("0"),[registro,setRegistro]=useState("");
 const [conferencia,setConferencia]=useState<{entrada:string;dados:Conferencia}|null>(null);
 const trava=useRef(false),controle=useRef<AbortController|null>(null),montada=useRef(true),chave=useRef(crypto.randomUUID());
 const entrada=JSON.stringify([contexto,cotacaoId,preco?.versao,modo,valor,despesas]);
 const atual=conferencia?.entrada===entrada?conferencia.dados:null;
 useEffect(()=>{montada.current=true;return()=>{montada.current=false;controle.current?.abort();};},[]);
 useEffect(()=>{
  const c=new AbortController();setPreco(null);setConferencia(null);setErro("");
  if(contexto)void api.get<Preco>(`/administracao/formacao-preco/cotacoes/${cotacaoId}`,{signal:c.signal,timeout:20000,headers:{"X-MEC-Preco-Contexto":contexto}}).then(({data:d})=>{
   if(c.signal.aborted)return;
   if(d.contexto!==contexto||d.cotacao_id!==cotacaoId||d.solicitacao_id!==solicitacaoId||!/^[a-f0-9]{64}$/.test(d.versao))throw new Error("resposta_divergente");
   setPreco(d);setModo(d.preco?.modo??"percentual");setValor(d.preco?.acrescimo_informado.replace('.',',')??"");setDespesas(d.preco?.despesas_previstas.replace('.',',')??"0");setRegistro("");chave.current=crypto.randomUUID();
  }).catch(e=>{if(!c.signal.aborted)setErro(erroPreco(e));});
  return()=>c.abort();
 },[cotacaoId,solicitacaoId,contexto,revisao]);
 function dados(){
  const acrescimo=numeroPreco(valor,modo==='percentual'?4:2),despesas_previstas=numeroPreco(despesas);
  if(!acrescimo||!despesas_previstas||!preco||preco.contexto!==contexto)return null;
  return {modo,acrescimo,despesas_previstas,versao:preco.versao};
 }
 async function conferir(){
  const d=dados();if(trava.current||!d)return;trava.current=true;setOcupado(true);setErro("");setConferencia(null);
  const c=new AbortController();controle.current=c;
  try{const {data:r}=await api.post<Conferencia>(`/administracao/formacao-preco/cotacoes/${cotacaoId}/conferir`,d,{signal:c.signal,timeout:20000,headers:{"X-MEC-Preco-Contexto":contexto}});
   if(!montada.current||c.signal.aborted)return;
   if(r.contexto!==contexto||r.versao!==d.versao||!/^[a-f0-9]{64}$/.test(r.conferencia)||!/^\d+\.\d{2}$/.test(r.preco_cliente))throw new Error("resposta_divergente");
   setConferencia({entrada,dados:r});chave.current=crypto.randomUUID();
  }catch(e){if(montada.current&&!c.signal.aborted)setErro(erroPreco(e));}finally{trava.current=false;if(montada.current)setOcupado(false);}
 }
 async function registrar(acao:"salvar"|"publicar"|"retirar"){
  const d=dados();if(trava.current||!d||!atual||registro.trim().length<3)return;trava.current=true;setOcupado(true);setErro("");
  const c=new AbortController();controle.current=c;
  try{const {data:r}=await api.post<{contexto:string;cotacao_id:number}>(`/administracao/formacao-preco/cotacoes/${cotacaoId}/registrar`,{...d,acao,conferencia:atual.conferencia,registro_interno:registro.trim(),chave_operacao:chave.current},{signal:c.signal,timeout:30000,headers:{"X-MEC-Preco-Contexto":contexto}});
   if(!montada.current||c.signal.aborted)return;
   if(r.contexto!==contexto||r.cotacao_id!==cotacaoId)throw new Error("resposta_divergente");
   setConferencia(null);setRevisao(v=>v+1);aoRegistrar();
  }catch(e){if(montada.current&&!c.signal.aborted)setErro(erroPreco(e));}finally{trava.current=false;if(montada.current)setOcupado(false);}
 }
 if(!contexto)return null;
 return <section className="p60" aria-label={`Formação do preço da cotação #${cotacaoId}`}>
  <header><h3>Preço ao cliente · cotação #{cotacaoId}</h3><button disabled={ocupado} onClick={()=>setRevisao(v=>v+1)}>Atualizar preço</button></header>
  {erro&&<p role="alert">{erro}</p>}{!preco&&!erro&&<p role="status">Consultando formação do preço…</p>}
  {preco&&<><p>Custo do fornecedor: <strong>{brl(preco.custo_fornecedor)}</strong>. O percentual é um acréscimo sobre esse custo.</p>
   <p>{preco.preco?rotuloAnalise[preco.preco.estado]:"Ainda não publicado ao cliente."}</p>
   {preco.preco&&<dl className="p60-resumo"><div><dt>Preço final registrado</dt><dd>{brl(preco.preco.preco_cliente)}</dd></div><div><dt>Ganho bruto previsto</dt><dd>{brl(preco.preco.acrescimo)}</dd></div><div><dt>Despesas previstas</dt><dd>{brl(preco.preco.despesas_previstas)}</dd></div><div><dt>Resultado previsto</dt><dd>{brl(preco.preco.resultado_previsto)}</dd></div></dl>}
   {preco.pode_editar?<><div className="p60-campos"><label>Forma de acréscimo<select value={modo} disabled={ocupado} onChange={e=>{setModo(e.target.value as typeof modo);setValor("");setConferencia(null);}}><option value="percentual">Percentual sobre o custo (%)</option><option value="valor">Valor fixo em reais (R$)</option></select></label>
    <label>{modo==='percentual'?"Acréscimo (%)":"Acréscimo (R$)"}<input inputMode="decimal" value={valor} disabled={ocupado} onChange={e=>{setValor(e.target.value);setConferencia(null);}} placeholder={modo==='percentual'?"Ex.: 20":"Ex.: 300,00"}/></label>
    <label>Despesas previstas do ADM (R$)<input inputMode="decimal" value={despesas} disabled={ocupado} onChange={e=>{setDespesas(e.target.value);setConferencia(null);}}/></label></div>
    <p className="p60-nota">As despesas são uma previsão para análise interna. Os valores e o ganho do ADM ficam reservados à administração.</p>
    <button disabled={ocupado||!dados()} onClick={()=>void conferir()}>{ocupado?"Aguarde…":"Conferir preço"}</button>
    {atual&&<div className="p60-conferencia" aria-label="Conferência do preço"><h4>Confira antes de publicar</h4><dl className="p60-resumo"><div><dt>Fornecedor</dt><dd>{brl(atual.custo_fornecedor)}</dd></div><div><dt>Acréscimo</dt><dd>{brl(atual.acrescimo)}</dd></div><div><dt>Preço final ao cliente</dt><dd>{brl(atual.preco_cliente)}</dd></div><div><dt>Resultado previsto após despesas</dt><dd>{brl(atual.resultado_previsto)}</dd></div></dl>
     <label>Registro interno<textarea value={registro} maxLength={2000} disabled={ocupado} onChange={e=>{setRegistro(e.target.value);chave.current=crypto.randomUUID();}} placeholder="Registre a conferência e o motivo da formação do preço."/></label>
     <div className="p60-acoes"><button disabled={ocupado||registro.trim().length<3} onClick={()=>void registrar('salvar')}>Salvar rascunho</button><button disabled={ocupado||registro.trim().length<3} onClick={()=>void registrar('publicar')}>Publicar ao cliente</button>{preco.preco&&<button disabled={ocupado||registro.trim().length<3} onClick={()=>void registrar('retirar')}>Retirar da análise do cliente</button>}</div>
     <p>Publicar envia o preço final para o cliente analisar. Alterar o preço exige uma nova aprovação.</p></div>}
   </>:<p>Esta cotação está disponível apenas para consulta. A formação do preço é feita antes da contratação.</p>}
   <details><summary>Histórico do preço e da análise do cliente ({preco.historico.length})</summary>{preco.historico.map(h=><article key={h.id}><strong>{h.acao} · {h.perfil} · {new Date(h.criado_em).toLocaleString('pt-BR')}</strong><p>{h.registro}</p></article>)}</details>
  </>}
 </section>;
}
