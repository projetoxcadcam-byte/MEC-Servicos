import {useEffect,useRef,useState,type FormEvent} from 'react';
import {useAuth} from '../../auth/AuthContext';
import {api} from '../../services/api';
import {brl,numeroPreco} from './preco';
import './DespesasAdministracao.css';
const CATEGORIAS={coleta:'Coleta',transporte:'Transporte',frete:'Frete',embalagem:'Embalagem',inspecao:'Inspeção',outros:'Outros'};
type Categoria=keyof typeof CATEGORIAS;
type Item={id:number;categoria:Categoria;descricao:string;valor:string;paga_em:string;referencia:string;status:'confirmada'|'estornada';administrador_nome:string;registro_interno:string;criada_em:string;estornada_em:string|null};
type Detalhe={contexto:string;contratacao_id:number;versao:string;cliente:string;fornecedor:string;pode_registrar:boolean;contratacao_status:string;despesas_confirmadas:string;despesas_previstas:string;ganho_bruto_previsto:string;resultado_apos_despesas:string;total:number;deslocamento:number;limite:number;total_eventos:number;itens:Item[];historico:{id:number;despesa_id:number;acao:string;administrador_nome:string;registro_interno:string;referencia:string;criado_em:string}[]};
type Registro={categoria:Categoria;descricao:string;valor:string;paga_em:string;referencia:string;registro_interno:string;versao:string;chave_operacao:string};
type Confirmacao={contexto:string;contratacao:number;despesa:Item|null;corpo:Partial<Registro>&{versao:string;chave_operacao:string;referencia:string;registro_interno:string}};
const data=(t:string)=>/^\d{4}-\d{2}-\d{2}$/.test(t)?t.split('-').reverse().join('/'):new Date(t).toLocaleString('pt-BR');
function erroDespesa(e:unknown){
 const f=e as {response?:{status?:number;data?:{detail?:unknown}}};const d=f.response?.data?.detail;
 const nomes:Record<string,string>={despesas_alteradas_atualize:'As despesas ou a contratação mudaram. Atualize e confira os dados antes de confirmar novamente.',contexto_despesas_alterado:'O acesso mudou. Entre novamente no perfil administrativo.',despesa_exige_contratacao_precificada:'Esta contratação não tem formação do preço D60. Seu financeiro anterior continua disponível em Pagamentos.',contratacao_nao_permite_despesa:'Novas despesas exigem contratação ativa ou encerrada.',despesa_ja_estornada:'Esta despesa já foi estornada. Atualize o histórico.',despesa_nao_encontrada:'A despesa não pertence a esta contratação.',chave_operacao_reutilizada:'A operação mudou. Atualize e confira o histórico.',instalacao_d61_nao_concluida:'Conclua a instalação D61 antes de registrar despesas.'};
 if(typeof d==='string'&&nomes[d])return nomes[d];
 if(f.response?.status===401)return 'Sua sessão expirou. Entre novamente.';
 if(f.response?.status===403)return 'Esta janela exige acesso administrativo.';
 if(f.response?.status===422)return 'Confira descrição, valor positivo com até duas casas decimais, data já ocorrida, referência e registro interno.';
 return 'A operação não pôde ser confirmada. Atualize a consulta e confira o histórico antes de tentar novamente.';
}
export default function DespesasAdministracao({contratacaoId,aoRegistrar,onFechar}:{contratacaoId:number;aoRegistrar:()=>void;onFechar:()=>void}){
 const {user}=useAuth(),contexto=user?.role==='admin'?`${user.usuario_id}:admin:0`:'';
 const [resposta,setResposta]=useState<{chave:string;dados:Detalhe}|null>(null),[falha,setFalha]=useState<{chave:string;texto:string}|null>(null),[pagina,setPagina]=useState(0),[revisao,setRevisao]=useState(0);
 const [categoria,setCategoria]=useState<Categoria>('coleta'),[descricao,setDescricao]=useState(''),[valor,setValor]=useState(''),[dia,setDia]=useState(new Date().toISOString().slice(0,10)),[referencia,setReferencia]=useState(''),[registro,setRegistro]=useState('');
 const [alvo,setAlvo]=useState<Item|null>(null),[confirmacao,setConfirmacao]=useState<Confirmacao|null>(null),[erro,setErro]=useState(''),[aviso,setAviso]=useState(''),[ocupado,setOcupado]=useState(false);
 const area=useRef<HTMLElement|null>(null),formulario=useRef<HTMLFormElement|null>(null);
 const trava=useRef(false),controle=useRef<AbortController|null>(null),montada=useRef(true),chaveOperacao=useRef(crypto.randomUUID());
 const chave=JSON.stringify([contexto,contratacaoId,pagina,revisao]),dados=resposta?.chave===chave?resposta.dados:null,erroConsulta=falha?.chave===chave?falha.texto:'',carregando=!!contexto&&!dados&&!erroConsulta;
 useEffect(()=>{montada.current=true;return()=>{montada.current=false;controle.current?.abort();};},[]);
 useEffect(()=>{
  const c=new AbortController();setResposta(null);setFalha(null);setConfirmacao(null);setAlvo(null);setErro('');
  if(contexto)void api.get<Detalhe>(`/administracao/despesas/contratacoes/${contratacaoId}`,{params:{deslocamento:pagina*20,limite:20},headers:{'X-MEC-Despesas-Contexto':contexto},signal:c.signal,timeout:20000}).then(({data:d})=>{
   if(c.signal.aborted)return;
   if(d.contexto!==contexto||d.contratacao_id!==contratacaoId||d.deslocamento!==pagina*20||d.limite!==20||!/^[a-f0-9]{64}$/.test(d.versao)||!Number.isSafeInteger(d.total)||d.total<0||!Array.isArray(d.itens)||!Array.isArray(d.historico))throw new Error('resposta_divergente');
   if(d.total>0&&pagina*20>=d.total){setPagina(0);return;}setResposta({chave,dados:d});chaveOperacao.current=crypto.randomUUID();
  }).catch(e=>{if(!c.signal.aborted)setFalha({chave,texto:erroDespesa(e)});});return()=>c.abort();
 },[contexto,chave,contratacaoId,pagina]);
 useEffect(()=>{area.current?.scrollIntoView({behavior:"smooth",block:"start"});area.current?.focus({preventScroll:true});},[contratacaoId,contexto]);
 useEffect(()=>{if(alvo){formulario.current?.scrollIntoView({behavior:"smooth",block:"start"});formulario.current?.focus({preventScroll:true});}},[alvo]);
 function conferir(e:FormEvent){
  e.preventDefault();if(!dados||ocupado)return;setErro('');setAviso('');
  if(referencia.trim().length<3||registro.trim().length<3){setErro('Informe referência e registro interno com ao menos três caracteres.');return;}
  const base={versao:dados.versao,chave_operacao:chaveOperacao.current,referencia:referencia.trim(),registro_interno:registro.trim()};
  if(alvo){setConfirmacao({contexto,contratacao:contratacaoId,despesa:alvo,corpo:base});return;}
  const quantia=numeroPreco(valor);const hoje=new Date().toISOString().slice(0,10);
  if(!dados.pode_registrar||!quantia||Number(quantia)<=0||descricao.trim().length<3||!/^\d{4}-\d{2}-\d{2}$/.test(dia)||dia>hoje||dia<'1900-01-01'){
   setErro('Informe descrição, valor pago positivo e data do pagamento sem data futura. Use até duas casas decimais.');return;
  }
  setConfirmacao({contexto,contratacao:contratacaoId,despesa:null,corpo:{...base,categoria,descricao:descricao.trim(),valor:quantia,paga_em:dia}});
 }
 async function confirmar(){
  const c=confirmacao;if(!c||!dados||c.contexto!==contexto||c.contratacao!==contratacaoId||trava.current)return;
  trava.current=true;setOcupado(true);setErro('');const a=new AbortController();controle.current=a;
  try{
   const url=`/administracao/despesas/contratacoes/${contratacaoId}`+(c.despesa?`/despesas/${c.despesa.id}/estornar`:'');
   const {data:r}=await api.post<{contexto:string;contratacao_id:number;despesa_id:number}>(url,c.corpo,{headers:{'X-MEC-Despesas-Contexto':contexto},signal:a.signal,timeout:30000});
   if(!montada.current||a.signal.aborted)return;
   if(r.contexto!==contexto||r.contratacao_id!==contratacaoId||!Number.isSafeInteger(r.despesa_id)||(c.despesa&&r.despesa_id!==c.despesa.id))throw new Error('resposta_divergente');
   setConfirmacao(null);setAlvo(null);setDescricao('');setValor('');setReferencia('');setRegistro('');setAviso(c.despesa?'Despesa estornada. O original permanece no histórico.':'Despesa paga registrada. Confira o resultado atualizado.');setRevisao(v=>v+1);aoRegistrar();
  }catch(e){if(montada.current&&!a.signal.aborted){setErro(erroDespesa(e));setConfirmacao(null);}}
  finally{trava.current=false;if(montada.current)setOcupado(false);}
 }
 if(!contexto)return null;
 return <section ref={area} tabIndex={-1} className="p60 desp61" aria-label={`Despesas da contratação #${contratacaoId}`}>
  <header><div><h2>Despesas reais · contratação #{contratacaoId}</h2><p>Registre gastos já pagos vinculados a este serviço. A confirmação não efetua pagamentos.</p></div><div className="p60-acoes"><button disabled={ocupado} onClick={()=>{setAviso('');setRevisao(v=>v+1);}}>Atualizar despesas</button><button disabled={ocupado} onClick={onFechar}>Fechar despesas</button></div></header>
  {(erroConsulta||erro)&&<p role="alert">{erroConsulta||erro}</p>}{aviso&&<p role="status">{aviso}</p>}{carregando&&<p role="status">Consultando despesas…</p>}
  {dados&&<><p>{dados.cliente} · {dados.fornecedor} · Contratação {dados.contratacao_status}</p><dl className="p60-resumo"><div><dt>Despesas previstas</dt><dd>{brl(dados.despesas_previstas)}</dd></div><div><dt>Despesas pagas confirmadas</dt><dd>{brl(dados.despesas_confirmadas)}</dd></div><div><dt>Ganho bruto previsto</dt><dd>{brl(dados.ganho_bruto_previsto)}</dd></div><div><dt>Resultado após despesas pagas</dt><dd>{brl(dados.resultado_apos_despesas)}</dd></div></dl>
   <p>A previsão permanece separada. O resultado considera apenas as despesas confirmadas registradas; novos gastos podem alterá-lo.</p>
   {!confirmacao&&(dados.pode_registrar||alvo)&&<form ref={formulario} tabIndex={-1} onSubmit={conferir}><h3>{alvo?`Estornar despesa #${alvo.id}`:'Registrar despesa paga'}</h3>{alvo?<p>{alvo.descricao} · {brl(alvo.valor)} · {data(alvo.paga_em)}. O original ficará no histórico.</p>:<div className="desp61-campos">
    <label>Categoria<select disabled={ocupado} value={categoria} onChange={e=>setCategoria(e.target.value as Categoria)}>{Object.entries(CATEGORIAS).map(([k,n])=><option key={k} value={k}>{n}</option>)}</select></label>
    <label>Descrição da despesa<input disabled={ocupado} value={descricao} maxLength={300} minLength={3} required onChange={e=>setDescricao(e.target.value)}/></label>
    <label>Valor pago (R$)<input disabled={ocupado} value={valor} inputMode="decimal" required onChange={e=>setValor(e.target.value)} placeholder="Ex.: 50,00"/></label>
    <label>Data do pagamento<input disabled={ocupado} type="date" min="1900-01-01" max={new Date().toISOString().slice(0,10)} value={dia} required onChange={e=>setDia(e.target.value)}/></label></div>}
    <label>Referência do comprovante<input disabled={ocupado} value={referencia} maxLength={200} minLength={3} required onChange={e=>setReferencia(e.target.value)}/></label>
    <label>Registro interno<textarea disabled={ocupado} value={registro} maxLength={2000} minLength={3} required onChange={e=>setRegistro(e.target.value)}/></label>
    <div className="p60-acoes"><button disabled={ocupado} type="submit">{alvo?'Conferir estorno':'Conferir despesa'}</button>{alvo&&<button disabled={ocupado} type="button" onClick={()=>{setAlvo(null);setReferencia('');setRegistro('');}}>Cancelar estorno</button>}</div></form>}
   {confirmacao&&<div className="p60-conferencia" aria-label="Conferência da despesa"><h3>{confirmacao.despesa?'Confirmar estorno da despesa':'Confira o gasto já pago'}</h3><p>Contratação #{contratacaoId} · {confirmacao.despesa?.descricao??confirmacao.corpo.descricao}</p><p><strong>{brl(confirmacao.despesa?.valor??confirmacao.corpo.valor??'0')}</strong> · {confirmacao.corpo.paga_em?data(confirmacao.corpo.paga_em):`Despesa #${confirmacao.despesa?.id}`}</p><p>Referência: {confirmacao.corpo.referencia}</p><p>{confirmacao.corpo.registro_interno}</p><div className="p60-acoes"><button disabled={ocupado} onClick={()=>void confirmar()}>{ocupado?'Registrando…':confirmacao.despesa?'Confirmar estorno':'Confirmar despesa'}</button><button disabled={ocupado} onClick={()=>{setConfirmacao(null);chaveOperacao.current=crypto.randomUUID();}}>Voltar à conferência</button></div></div>}
   <h3>{dados.total} despesas registradas</h3>{!dados.total?<p>Nenhuma despesa registrada para esta contratação.</p>:<div className="fin-scroll"><table><thead><tr><th>Despesa / categoria</th><th>Pagamento</th><th>Valor</th><th>Situação</th><th>Conferência</th></tr></thead><tbody>{dados.itens.map(d=><tr key={d.id}><td>#{d.id} · {CATEGORIAS[d.categoria]}<small>{d.descricao}</small></td><td>{data(d.paga_em)}<small>{d.referencia}</small></td><td>{brl(d.valor)}</td><td>{d.status==='confirmada'?'Confirmada':'Estornada'}{d.estornada_em&&<small>{data(d.estornada_em)}</small>}</td><td>{d.status==='confirmada'&&<button disabled={ocupado||!!confirmacao} onClick={()=>{setAlvo(d);setReferencia('');setRegistro('');setErro('');setAviso('');chaveOperacao.current=crypto.randomUUID();}}>Estornar despesa #{d.id}</button>}<details><summary>Registro interno</summary><p>{d.administrador_nome} · {data(d.criada_em)}</p><p>{d.registro_interno}</p></details></td></tr>)}</tbody></table></div>}
   <div className="p60-acoes"><button disabled={ocupado||pagina===0} onClick={()=>setPagina(v=>v-1)}>Anterior</button><span>{dados.total?pagina*20+1:0}–{pagina*20+dados.itens.length} de {dados.total}</span><button disabled={ocupado||(pagina+1)*20>=dados.total} onClick={()=>setPagina(v=>v+1)}>Próxima</button></div>
   <details><summary>Histórico administrativo · {dados.total_eventos} eventos</summary><p>Até 20 eventos mais recentes. Os registros originais permanecem disponíveis nas páginas de despesas.</p>{dados.historico.map(e=><article key={e.id}><strong>{e.acao==='registrar'?'Despesa registrada':'Despesa estornada'} #{e.despesa_id} · {e.administrador_nome} · {data(e.criado_em)}</strong><p>{e.referencia} · {e.registro_interno}</p></article>)}</details>
  </>}
 </section>;
}
