import {useEffect,useRef,useState} from "react";
import {useAuth} from "../../auth/AuthContext";
import {api} from "../../services/api";
import {categoriasDespesa,camposResultado,dataRelatorio,instanteRelatorio,moedaRelatorio,validarRelatorio,type RelatorioResultado as Dados} from "./dadosRelatorioResultado";
import "./RelatorioResultado.css";

const endpoint="/administracao/despesas/resultado";
function erroRelatorio(e:unknown) {
 const r=(e as {response?:{status?:number;data?:unknown}}).response;
 if(r?.status===401||r?.status===403)return "Entre novamente com o perfil da administração para consultar este relatório.";
 if(r?.status===409)return "Os dados ou o acesso mudaram. Atualize o relatório antes de exportar.";
 if(r?.status===422)return "Confira o período: informe as datas em ordem e um intervalo de até dez anos.";
 return "Não foi possível conferir o relatório. Atualize e tente novamente.";
}
function Conteudo({r}:{r:Dados}) {
 return <article className="rel62-conteudo">
  <header><div><p className="rel62-marca">MEC-Serviços · Administração</p><h2>Relatório do resultado da administração</h2><p>{dataRelatorio(r.inicio)} a {dataRelatorio(r.fim)} · {r.total} contratações · {r.liquidadas} liquidadas</p><p>Consulta: {instanteRelatorio(r.gerado_em)}</p></div><span className="rel62-reservado">Uso exclusivo do ADM</span></header>
  <div className="rel62-totais">{camposResultado.map(([k,t])=><div key={k}><span>{t}</span><strong className={r.totais[k].startsWith("-")?"rel62-negativo":""}>{moedaRelatorio(r.totais[k])}</strong></div>)}</div>
  <section><h3>Critérios da consulta</h3><p>O período considera a criação da contratação em UTC. As despesas vinculadas a essas contratações entram em todas as datas de pagamento, inclusive quando registradas depois do período. Esta consulta acompanha o resultado dos serviços; o período não filtra o fluxo de caixa.</p><p>Somente contratações ativas ou encerradas com preço formado pela administração entram nos totais. Pedidos ainda sem contratação, contratações canceladas e o histórico anterior continuam nas suas telas de acompanhamento.</p><p>Despesas previstas são o orçamento interno. Despesas pagas somam os gastos confirmados. A liquidação exige entrega concluída, recebimento integral do cliente e repasse integral do custo ao fornecedor, sem divergência. O resultado pode mudar com novos gastos ou estornos e considera somente despesas registradas.</p></section>
  <section><h3>Formação do resultado por contratação</h3>{!r.total?<p>Nenhuma contratação com preço formado neste período.</p>:<div className="rel62-scroll"><table><thead><tr><th>Contratação / OS</th><th>Cliente / fornecedor</th><th>Venda ao cliente</th><th>Custo do fornecedor</th><th>Ganho bruto previsto</th><th>Despesas previstas</th><th>Resultado previsto</th></tr></thead><tbody>{r.itens.map(c=><tr key={c.contratacao_id}><th scope="row">#{c.contratacao_id}<small>{c.ordem_servico_id?`OS #${c.ordem_servico_id}`:"Sem OS"}</small><small>Criação: {instanteRelatorio(c.criada_em)}</small></th><td>{c.cliente}<small>{c.fornecedor}</small></td>{(["venda_cliente","custo_fornecedor","ganho_bruto_previsto","despesas_previstas","resultado_previsto"] as const).map(k=><td key={k}>{moedaRelatorio(c[k])}</td>)}</tr>)}</tbody></table></div>}</section>
  {!!r.total&&<section><h3>Despesas e liquidação por contratação</h3><div className="rel62-scroll"><table><thead><tr><th>Contratação / OS</th><th>Despesas pagas</th><th>Resultado após despesas pagas</th><th>Ganho bruto confirmado</th><th>Resultado liquidado após despesas</th><th>Liquidação</th></tr></thead><tbody>{r.itens.map(c=><tr key={c.contratacao_id}><th scope="row">#{c.contratacao_id}<small>{c.ordem_servico_id?`OS #${c.ordem_servico_id}`:"Sem OS"}</small></th>{(["despesas_pagas","resultado_apos_despesas","ganho_bruto_confirmado","resultado_liquidado_apos_despesas"] as const).map(k=><td key={k} className={c[k].startsWith("-")?"rel62-negativo":""}>{moedaRelatorio(c[k])}</td>)}<td>{c.liquidado?"Liquidada":c.situacao==="verificar"?"Conferir valores e entrega":"Aguardando liquidação"}</td></tr>)}</tbody></table></div></section>}
  <section><h3>Despesas registradas nos serviços do período</h3><p>{r.despesas_confirmadas} confirmadas · {r.despesas_estornadas} estornadas. Valor dos estornos: {moedaRelatorio(r.valor_estornado)}. Os registros estornados ficam no histórico e não compõem as despesas pagas.</p>
   {!r.despesas.length?<p>Nenhuma despesa registrada nessas contratações.</p>:<div className="rel62-scroll"><table><thead><tr><th>Contratação / despesa</th><th>Pagamento / categoria</th><th>Descrição</th><th>Valor</th><th>Estado</th><th>Referência e registro interno</th></tr></thead><tbody>{r.despesas.map(d=><tr key={d.id}><th scope="row">Contratação #{d.contratacao_id}<small>Despesa #{d.id}</small></th><td>{dataRelatorio(d.paga_em)}<small>{categoriasDespesa[d.categoria]}</small></td><td>{d.descricao}</td><td>{moedaRelatorio(d.valor)}</td><td>{d.status==="confirmada"?"Confirmada":"Estornada"}{d.estornada_em&&<small>{instanteRelatorio(d.estornada_em)}</small>}</td><td><p>Comprovante: {d.referencia}</p><p>Registro: {d.registro_interno}</p><small>Registrada por {d.administrador_nome} · {instanteRelatorio(d.criada_em)}</small>{d.status==="estornada"&&<><p>Motivo do estorno: {d.motivo_estorno??"Consultar histórico da despesa"}</p><small>Referência do estorno: {d.referencia_estorno??"Consultar histórico"}</small></>}</td></tr>)}</tbody></table></div>}
  </section><footer>Resultado reservado à administração. O relatório não substitui a apuração contábil nem inclui gastos ainda não registrados.</footer>
 </article>;
}
export default function RelatorioResultado({contexto,inicio,fim,onFechar}:{contexto:string;inicio:string;fim:string;onFechar:()=>void}) {
 const {user}=useAuth(), atual=user?.role==="admin"?`${user.usuario_id}:admin:0`:"", autorizado=!!atual&&atual===contexto;
 const [dados,setDados]=useState<Dados|null>(null),[erro,setErro]=useState(""),[aviso,setAviso]=useState(""),[revisao,setRevisao]=useState(0),[operacao,setOperacao]=useState<""|"csv"|"pdf"|"imprimir">("");
 const baixando=operacao!=="",janelas=useRef(new Set<Window>());
 const painel=useRef<HTMLElement>(null),download=useRef<AbortController|null>(null),urls=useRef(new Set<string>());
 useEffect(()=>{
  const controle=new AbortController();setDados(null);setErro("");setAviso("");
  if(autorizado)void api.get<Dados>(endpoint+"/relatorio",{params:{inicio,fim},headers:{"X-MEC-Despesas-Contexto":contexto},signal:controle.signal,timeout:30000}).then(({data})=>{
   if(controle.signal.aborted)return;validarRelatorio(data,contexto,inicio,fim);setDados(data);
  }).catch(e=>{if(!controle.signal.aborted)setErro(erroRelatorio(e));});
  return()=>controle.abort();
 },[autorizado,contexto,inicio,fim,revisao]);
 useEffect(()=>()=>{download.current?.abort();for(const janela of janelas.current)janela.close();janelas.current.clear();for(const url of urls.current)URL.revokeObjectURL(url);urls.current.clear();},[]);
 useEffect(()=>{painel.current?.scrollIntoView({behavior:"smooth",block:"start"});painel.current?.focus({preventScroll:true});},[]);
 useEffect(()=>{if(!dados){for(const janela of janelas.current)janela.close();janelas.current.clear();}},[dados]);
 async function exportar(formato:"csv"|"pdf"="csv", visualizar=false) {
  if(!dados||baixando||!autorizado)return;
  const janela=visualizar?window.open("about:blank","_blank"):null;
  if(janela){janela.opener=null;janela.document.title="MEC-Serviços - Preparando PDF";janela.document.body.textContent="Preparando o PDF em A4 horizontal…";janelas.current.add(janela);}
  const controle=new AbortController();download.current=controle;setOperacao(visualizar?"imprimir":formato);setErro("");setAviso("");
  try {
   const r=await api.get<Blob>(endpoint+"/"+formato,{params:{inicio,fim,versao:dados.versao},headers:{"X-MEC-Despesas-Contexto":contexto},responseType:"blob",signal:controle.signal,timeout:30000});
   if(controle.signal.aborted)return;
   const tipo=formato==="pdf"?"application/pdf":"text/csv";
   if(r.headers["x-mec-despesas-contexto"]!==contexto || r.headers["x-mec-relatorio-versao"]!==dados.versao || !(r.data instanceof Blob) || !r.data.type.startsWith(tipo))throw new Error("exportacao_divergente");
   if(formato==="pdf"&&(await r.data.slice(0,5).text())!=="%PDF-")throw new Error("pdf_invalido");
   if(controle.signal.aborted)return;
   const url=URL.createObjectURL(r.data);urls.current.add(url);
   if(janela&&!janela.closed){janela.location.replace(url);setAviso("PDF aberto em A4 horizontal. Use Imprimir na visualização do PDF.");}
   else {
    const link=document.createElement("a");link.href=url;link.download=`MEC_SERVICOS_RESULTADO_ADMIN_${inicio}_${fim}.${formato}`;document.body.append(link);link.click();link.remove();
    setTimeout(()=>{URL.revokeObjectURL(url);urls.current.delete(url);},1000);
    setAviso(formato==="csv"?"CSV gerado com todas as contratações e despesas deste relatório.":visualizar?"PDF baixado. Abra o arquivo para imprimir; a visualização foi bloqueada ou fechada.":"PDF gerado em A4 horizontal, com todas as contratações e despesas do relatório.");
   }
  } catch(e) {
   janela?.close();if(janela)janelas.current.delete(janela);
   if(!controle.signal.aborted){setDados(null);setErro(erroRelatorio(e));}
  } finally {if(!controle.signal.aborted)setOperacao("");}
 }
 if(!autorizado)return null;
 const carregando=!dados&&!erro;
 return <section className="fin-card rel62" aria-label="Relatório do resultado" ref={painel} tabIndex={-1}>
  <div className="fin-header-acoes rel62-acoes"><button disabled={carregando||baixando} onClick={()=>setRevisao(v=>v+1)}>Atualizar relatório</button><button disabled={!dados||baixando} onClick={()=>void exportar()}>{operacao==="csv"?"Gerando CSV…":"Baixar CSV"}</button><button disabled={!dados||baixando} onClick={()=>void exportar("pdf")}>{operacao==="pdf"?"Gerando PDF…":"Baixar PDF"}</button><button disabled={!dados||baixando} onClick={()=>void exportar("pdf",true)}>{operacao==="imprimir"?"Preparando impressão…":"Imprimir / salvar PDF"}</button><button onClick={onFechar}>Fechar relatório</button></div>
  {carregando&&<p role="status">Conferindo todas as contratações e despesas do período…</p>}{erro&&<p role="alert">{erro}</p>}{aviso&&<p role="status">{aviso}</p>}
  {dados&&<><p className="rel62-pdf-ajuda">O PDF é gerado em A4 horizontal, com escala e margens próprias. Baixe o arquivo ou abra a visualização para imprimir.</p><Conteudo r={dados}/></>}
 </section>;
}
