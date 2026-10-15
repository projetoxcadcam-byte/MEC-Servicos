import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import "./EmpresasOperacoes.css";

type TipoEmpresa = "cliente" | "fornecedor" | "ambos";
type Empresa = { id:number; razao_social:string; documento:string; tipo_empresa:TipoEmpresa; operacoes:string[] };
type Pagina = { itens:Empresa[]; total:number; deslocamento:number; limite:number };
type Opcao = { codigo:string; nome:string; processo_id:number|null; ativo:boolean };
type Capacidade = { dimensao_x_maxima_mm:string; dimensao_y_maxima_mm:string; dimensao_z_maxima_mm:string; tolerancia_minima_mm:string };
type Operacao = Opcao & { processo_id:number; capacidade:Capacidade|null };
type Material = { material_id:number|null; codigo:string; nome:string };
type Detalhe = { empresa:Empresa; operacoes:Operacao[]; materiais:{material_id:number;nome:string;ativo:boolean}[]; versao:string };
const BASE="/administracao/empresas";
const TIPOS:Record<TipoEmpresa,string>={cliente:"Cliente",fornecedor:"Fornecedor",ambos:"Cliente e fornecedor"};
const norm=(s:string)=>s.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
function mensagem(falha:unknown){
  const e=falha as {response?:{status?:number;data?:{detail?:unknown}}};const detalhe=e.response?.data?.detail;
  const textos:Record<string,string>={
    documento_da_empresa_ja_cadastrado:"Este CPF/CNPJ já está cadastrado. Localize a empresa na lista.",
    operacoes_empresa_alteradas_atualize:"O cadastro mudou em outra tela. Reabra a empresa e confira antes de salvar.",
    operacao_possui_capacidade_tecnica:"Esta operação já possui capacidade técnica e permanece no cadastro.",
    processo_inativo:"A operação foi desativada no catálogo. Reabra a empresa para conferir.",
    catalogo_operacoes_alterado_atualize:"O catálogo mudou. Recarregue as opções e confira novamente.",
    cadastro_alterado_atualize:"O cadastro mudou. Reabra a empresa para conferir o resultado.",
    operacao_nao_encontrada:"Uma operação não está disponível. Recarregue as opções.",
    capacidade_para_processo_ja_cadastrada:"A capacidade já está cadastrada. Reabra a empresa para conferir.",
    operacao_nao_declarada_pela_empresa:"Salve a seleção de operações antes de registrar a capacidade.",
    material_ja_associado_ao_fornecedor:"Este material já está vinculado à empresa.",
    material_inativo:"Este material foi desativado. Reabra a empresa e confira as opções atuais.",
    material_nao_encontrado:"Este material não está disponível. Recarregue as opções.",
    material_catalogo_nao_encontrado:"A opção de material não está disponível. Recarregue as opções.",
    material_catalogo_alterado_atualize:"O catálogo de materiais mudou. Reabra a empresa e confira as opções atuais.",
    material_nome_ambiguo_selecione_cadastrado:"Há mais de um cadastro com este nome. Selecione o material existente na lista.",
  };
  if(typeof detalhe==="string"&&textos[detalhe])return textos[detalhe];
  if(e.response?.status===401)return "Sua sessão expirou. Entre novamente.";
  if(e.response?.status===403)return "O cadastro de empresas exige acesso administrativo.";
  if(e.response?.status===422)return "Confira os dados informados, o nome do material e os valores positivos dos limites técnicos.";
  return "Não foi possível concluir. Confira a conexão e tente novamente.";
}

export default function EmpresasOperacoesPage(){
  const {user}=useAuth();const ctx=user?.role==="admin"?String(user.usuario_id):"";const contexto=useRef(ctx);contexto.current=ctx;
  const viva=useRef(true);const controles=useRef(new Set<AbortController>());const trava=useRef(false);const operacaoPendente=useRef(0);const pedidoDetalhe=useRef(0);
  const [dados,setDados]=useState<Pagina|null>(null);const [opcoes,setOpcoes]=useState<Opcao[]|null>(null);
  const [carregando,setCarregando]=useState(false);const [erroLista,setErroLista]=useState("");const [erroCatalogo,setErroCatalogo]=useState("");
  const [texto,setTexto]=useState("");const [busca,setBusca]=useState("");const [tipoFiltro,setTipoFiltro]=useState("");
  const [pagina,setPagina]=useState(0);const [revisao,setRevisao]=useState(0);const [revisaoCatalogo,setRevisaoCatalogo]=useState(0);
  const [novo,setNovo]=useState(false);const [detalhe,setDetalhe]=useState<Detalhe|null>(null);const [abrindo,setAbrindo]=useState(false);
  const [razao,setRazao]=useState("");const [documento,setDocumento]=useState("");const [tipo,setTipo]=useState<TipoEmpresa>("fornecedor");
  const [selecionadas,setSelecionadas]=useState<string[]>([]);const [buscaOperacao,setBuscaOperacao]=useState("");
  const [ocupado,setOcupado]=useState(false);const [erro,setErro]=useState("");const [aviso,setAviso]=useState("");
  const [qualificar,setQualificar]=useState<Operacao|null>(null);const [limites,setLimites]=useState({x:"",y:"",z:"",tolerancia:""});
  const [materiais,setMateriais]=useState<Material[]|null>(null);const [carregandoMateriais,setCarregandoMateriais]=useState(false);const [material,setMaterial]=useState("");
  const [buscaMaterial,setBuscaMaterial]=useState("");const [criarMaterial,setCriarMaterial]=useState(false);const [nomeMaterial,setNomeMaterial]=useState("");
  useEffect(()=>{viva.current=true;return()=>{viva.current=false;for(const c of controles.current)c.abort();};},[]);
  useEffect(()=>{++pedidoDetalhe.current;++operacaoPendente.current;trava.current=false;setOcupado(false);setAbrindo(false);setCarregandoMateriais(false);setNovo(false);setDetalhe(null);setSelecionadas([]);setErro("");setAviso("");setQualificar(null);setMateriais(null);setMaterial("");setBuscaMaterial("");setCriarMaterial(false);setNomeMaterial("");for(const c of controles.current)c.abort();},[ctx]);
  useEffect(()=>{
    let atual=true;const c=new AbortController();controles.current.add(c);setDados(null);setErroLista("");
    if(!ctx)return()=>{controles.current.delete(c);};setCarregando(true);
    void api.get<Pagina>(BASE,{params:{busca,tipo:tipoFiltro||undefined,deslocamento:pagina*20,limite:20},signal:c.signal,timeout:20_000}).then(({data})=>{
      if(!atual||contexto.current!==ctx)return;
      if(data.total&&pagina*20>=data.total){setPagina(Math.floor((data.total-1)/20));return;}setDados(data);
    }).catch(e=>{if(atual&&!c.signal.aborted&&contexto.current===ctx)setErroLista(mensagem(e));}).finally(()=>{controles.current.delete(c);if(atual&&contexto.current===ctx)setCarregando(false);});
    return()=>{atual=false;c.abort();};
  },[ctx,busca,tipoFiltro,pagina,revisao]);
  useEffect(()=>{
    let atual=true;const c=new AbortController();controles.current.add(c);setOpcoes(null);setErroCatalogo("");
    if(!ctx)return()=>{controles.current.delete(c);};
    void api.get<{itens:Opcao[]}>(BASE+"/catalogo-operacoes",{signal:c.signal,timeout:20_000}).then(({data})=>{if(atual&&contexto.current===ctx)setOpcoes(data.itens);})
      .catch(e=>{if(atual&&!c.signal.aborted&&contexto.current===ctx)setErroCatalogo(mensagem(e));}).finally(()=>controles.current.delete(c));
    return()=>{atual=false;c.abort();};
  },[ctx,revisaoCatalogo]);
  function aplicar(d:Detalhe){setDetalhe(d);setNovo(false);setRazao(d.empresa.razao_social);setDocumento(d.empresa.documento);setTipo(d.empresa.tipo_empresa);setSelecionadas(d.operacoes.map(v=>v.codigo));setBuscaOperacao("");setQualificar(null);setMateriais(null);setMaterial("");setBuscaMaterial("");setCriarMaterial(false);setNomeMaterial("");}
  async function abrir(id:number){
    if(ocupado||!ctx)return;const ctxPedido=ctx;const numero=++pedidoDetalhe.current;const c=new AbortController();controles.current.add(c);setAbrindo(true);setCarregandoMateriais(false);setErro("");setAviso("");setNovo(false);setDetalhe(null);
    try{const {data}=await api.get<Detalhe>(BASE+"/"+id,{signal:c.signal,timeout:20_000});if(viva.current&&contexto.current===ctxPedido&&numero===pedidoDetalhe.current)aplicar(data);}
    catch(e){if(viva.current&&!c.signal.aborted&&contexto.current===ctxPedido&&numero===pedidoDetalhe.current)setErro(mensagem(e));}
    finally{controles.current.delete(c);if(viva.current&&contexto.current===ctxPedido&&numero===pedidoDetalhe.current)setAbrindo(false);}
  }
  function nova(){++pedidoDetalhe.current;setNovo(true);setDetalhe(null);setAbrindo(false);setCarregandoMateriais(false);setRazao("");setDocumento("");setTipo("fornecedor");setSelecionadas([]);setBuscaOperacao("");setErro("");setAviso("");setQualificar(null);setMateriais(null);setMaterial("");setBuscaMaterial("");setCriarMaterial(false);setNomeMaterial("");}
  async function executar(acao:(signal:AbortSignal)=>Promise<void>){
    if(trava.current||!ctx)return;trava.current=true;const numero=++operacaoPendente.current;setOcupado(true);setErro("");setAviso("");const contextoPedido=ctx;const c=new AbortController();controles.current.add(c);
    try{await acao(c.signal);}catch(e){if(viva.current&&contexto.current===contextoPedido&&!c.signal.aborted)setErro(mensagem(e));}
    finally{if(operacaoPendente.current===numero)trava.current=false;controles.current.delete(c);if(viva.current&&contexto.current===contextoPedido&&operacaoPendente.current===numero)setOcupado(false);}
  }
  function atualizarTela(d:Detalhe,textoAviso:string,contextoPedido:string){if(!viva.current||contexto.current!==contextoPedido)return;aplicar(d);setAviso(textoAviso);setRevisao(v=>v+1);setRevisaoCatalogo(v=>v+1);}
  function salvar(e:FormEvent){e.preventDefault();const contextoPedido=ctx;const d=detalhe;const novos=novo;const operacoes=[...selecionadas];
    void executar(async signal=>{const {data}=novos?await api.post<Detalhe>(BASE,{razao_social:razao,documento,tipo_empresa:tipo,operacoes},{signal,timeout:20_000}):await api.put<Detalhe>(BASE+"/"+d!.empresa.id+"/operacoes",{operacoes,versao:d!.versao},{signal,timeout:20_000});atualizarTela(data,novos?"Empresa e operações cadastradas.":"Operações da empresa atualizadas.",contextoPedido);});
  }
  function salvarCapacidade(e:FormEvent){e.preventDefault();if(!detalhe||!qualificar)return;const contextoPedido=ctx;const d=detalhe;const processo=qualificar.processo_id;
    void executar(async signal=>{const {data}=await api.post<Detalhe>(BASE+"/"+d.empresa.id+"/capacidade",{versao:d.versao,processo_id:processo,dimensao_x_maxima_mm:limites.x.replace(",","."),dimensao_y_maxima_mm:limites.y.replace(",","."),dimensao_z_maxima_mm:limites.z.replace(",","."),tolerancia_minima_mm:limites.tolerancia.replace(",",".")},{signal,timeout:20_000});atualizarTela(data,"Capacidade técnica registrada.",contextoPedido);});
  }
  async function carregarMateriais(){
    if(!detalhe||carregandoMateriais)return;const id=detalhe.empresa.id;const contextoPedido=ctx;const c=new AbortController();controles.current.add(c);setCarregandoMateriais(true);setErro("");
    try{const lista:Material[]=[];for(let inicio=0;;inicio+=200){const {data}=await api.get<{itens:Material[]}>(BASE+"/catalogo-materiais",{params:{deslocamento:inicio,limite:200},signal:c.signal,timeout:20_000});lista.push(...data.itens);if(data.itens.length<200)break;}
      if(viva.current&&contexto.current===contextoPedido&&pedidoDetalhe.current===idPedido&&id===detalhe.empresa.id)setMateriais(lista);
    }catch(e){if(viva.current&&!c.signal.aborted&&contexto.current===contextoPedido&&pedidoDetalhe.current===idPedido)setErro(mensagem(e));}
    finally{controles.current.delete(c);if(viva.current&&contexto.current===contextoPedido&&pedidoDetalhe.current===idPedido)setCarregandoMateriais(false);}
  }
  // Cada abertura identifica a empresa; respostas antigas não mudam outro cadastro.
  const idPedido=pedidoDetalhe.current;
  function adicionarMaterial(e:FormEvent){e.preventDefault();if(!detalhe||!material)return;const d=detalhe;const contextoPedido=ctx;
    const opcao=materiais?.find(v=>(v.material_id===null?"catalogo:"+v.codigo:String(v.material_id))===material);if(!opcao)return;
    const escolha=opcao.material_id===null?{codigo_catalogo:opcao.codigo}:{material_id:opcao.material_id};
    void executar(async signal=>{const {data}=await api.post<Detalhe>(BASE+"/"+d.empresa.id+"/materiais",{versao:d.versao,...escolha},{signal,timeout:20_000});atualizarTela(data,"Material vinculado à empresa.",contextoPedido);});
  }
  function cadastrarMaterial(e:FormEvent){e.preventDefault();if(!detalhe||nomeMaterial.trim().length<2)return;const d=detalhe;const contextoPedido=ctx;const nome=nomeMaterial.trim();
    void executar(async signal=>{const {data}=await api.post<Detalhe>(BASE+"/"+d.empresa.id+"/materiais",{versao:d.versao,novo_material:nome},{signal,timeout:20_000});atualizarTela(data,"Material vinculado à empresa.",contextoPedido);});
  }
  if(!ctx)return <p role="alert">O cadastro de empresas está disponível somente para a administração.</p>;
  const capacidades=new Set(detalhe?.operacoes.filter(v=>v.capacidade).map(v=>v.codigo)??[]);
  const opcoesVisiveis=(opcoes??[]).filter(v=>norm(v.nome+" "+v.codigo).includes(norm(buscaOperacao)));
  const fornecedor=tipo!=="cliente";const exibir=novo||!!detalhe;
  const alteradas=detalhe&&([...selecionadas].sort().join("\n")!==detalhe.operacoes.map(v=>v.codigo).sort().join("\n"));
  const materiaisDisponiveis=(materiais??[]).filter(v=>v.material_id===null||!detalhe?.materiais.some(m=>m.material_id===v.material_id));
  const materiaisVisiveis=materiaisDisponiveis.filter(v=>norm(v.nome+" "+v.codigo).includes(norm(buscaMaterial)));
  return <main className="empresa52"><header><div><p>ADMINISTRAÇÃO</p><h1>Empresas e operações</h1><p>Cadastre quais serviços cada empresa executa e confira sua capacidade técnica.</p></div><Link to="/admin">Voltar ao Dashboard</Link></header>
    <div className="empresa52-barra"><button disabled={ocupado} onClick={nova}>Cadastrar empresa</button><button disabled={ocupado||carregando} onClick={()=>setRevisao(v=>v+1)}>Atualizar lista</button></div>
    {aviso&&<p className="empresa52-aviso" role="status">{aviso}</p>}{erro&&<p className="empresa52-erro" role="alert">{erro}</p>}
    {abrindo&&<p role="status">Abrindo cadastro da empresa…</p>}
    {exibir&&<section aria-label="Cadastro da empresa"><h2>{novo?"Nova empresa":`${detalhe!.empresa.razao_social} · Empresa #${detalhe!.empresa.id}`}</h2>
      <form onSubmit={salvar}><fieldset disabled={ocupado}><div className="empresa52-dados"><label>Razão social<input value={razao} readOnly={!novo} required minLength={2} maxLength={200} onChange={e=>setRazao(e.target.value)} /></label>
        <label>CPF/CNPJ<input value={documento} readOnly={!novo} required maxLength={32} onChange={e=>setDocumento(e.target.value)} /></label>
        <label>Tipo de empresa<select value={tipo} disabled={!novo} onChange={e=>{const t=e.target.value as TipoEmpresa;setTipo(t);if(t==="cliente")setSelecionadas([]);}}><option value="fornecedor">Fornecedor</option><option value="cliente">Cliente</option><option value="ambos">Cliente e fornecedor</option></select></label></div>
        {fornecedor?<><h3>Operações que esta empresa executa</h3><p>Marque todas as operações oferecidas. As operações com capacidade técnica já cadastrada permanecem selecionadas.</p>
          {erroCatalogo&&<p className="empresa52-erro" role="alert">{erroCatalogo}</p>}{!opcoes&&!erroCatalogo&&<p role="status">Carregando operações…</p>}
          <button type="button" onClick={()=>setRevisaoCatalogo(v=>v+1)}>Recarregar opções</button><label>Buscar operação<input type="search" value={buscaOperacao} onChange={e=>setBuscaOperacao(e.target.value)} placeholder="Usinagem, dobra, solda, pintura…" /></label>
          <div className="empresa52-operacoes">{opcoesVisiveis.map(v=><label key={v.codigo}><input type="checkbox" data-operacao={v.codigo} checked={selecionadas.includes(v.codigo)} disabled={capacidades.has(v.codigo)||!v.ativo} onChange={e=>setSelecionadas(s=>e.target.checked?[...s,v.codigo]:s.filter(c=>c!==v.codigo))} /><span>{v.nome}{capacidades.has(v.codigo)&&<small>Capacidade técnica cadastrada</small>}{!v.ativo&&<small>Processo inativo</small>}</span></label>)}</div>
          {!!opcoes&&!opcoesVisiveis.length&&<p>Nenhuma operação corresponde à busca.</p>}<p>{selecionadas.length} operação(ões) selecionada(s).</p>
        </>:<p>Empresas do tipo Cliente solicitam serviços. Para oferecer serviços também, cadastre como Cliente e fornecedor.</p>}
        <div className="empresa52-barra"><button type="submit" disabled={ocupado||(!opcoes&&fornecedor)||(novo&&fornecedor&&!selecionadas.length)}>{ocupado?"Salvando…":novo?"Cadastrar empresa e operações":"Salvar operações"}</button><button type="button" onClick={()=>{++pedidoDetalhe.current;setNovo(false);setDetalhe(null);setQualificar(null);setErro("");}}>Fechar cadastro</button></div>
      </fieldset></form>
      {detalhe&&fornecedor&&<><h3>Capacidades técnicas por operação</h3><p>As oportunidades continuam considerando processo, material, dimensões, tolerância e documentação liberada. Informe somente os limites que a empresa realmente atende.</p>
        {alteradas&&<p className="empresa52-aviso">Salve as operações antes de completar a capacidade técnica ou adicionar materiais.</p>}
        <div className="empresa52-capacidades">{detalhe.operacoes.map(v=><article key={v.codigo}><h4>{v.nome}</h4>{v.capacidade?<p>X: {v.capacidade.dimensao_x_maxima_mm} mm · Y: {v.capacidade.dimensao_y_maxima_mm} mm · Z: {v.capacidade.dimensao_z_maxima_mm} mm<br />Tolerância mínima: {v.capacidade.tolerancia_minima_mm} mm</p>:<><p>Limites técnicos ainda não informados.</p><button disabled={ocupado||!!alteradas||!v.ativo} onClick={()=>{setQualificar(v);setLimites({x:"",y:"",z:"",tolerancia:""});setErro("");}}>Completar capacidade de {v.nome}</button></>}</article>)}</div>
        {qualificar&&<form className="empresa52-qualificar" onSubmit={salvarCapacidade}><fieldset disabled={ocupado||!!alteradas}><legend>Capacidade de {qualificar.nome}</legend><div className="empresa52-dados">{([ ["x","Dimensão máxima X (mm)"],["y","Dimensão máxima Y (mm)"],["z","Dimensão máxima Z (mm)"],["tolerancia","Tolerância mínima atendida (mm)"] ] as const).map(([k,nome])=><label key={k}>{nome}<input inputMode="decimal" required value={limites[k]} onChange={e=>setLimites(s=>({...s,[k]:e.target.value}))} placeholder="Informe o limite real" /></label>)}</div><button type="submit">Registrar capacidade técnica</button><button type="button" onClick={()=>setQualificar(null)}>Cancelar capacidade</button></fieldset></form>}
        <h3>Materiais aceitos pela empresa</h3><p>{detalhe.materiais.length?detalhe.materiais.map(v=>v.nome+(v.ativo?"":" (inativo)")).join(", "):"Nenhum material vinculado."}</p>
        {!materiais?<button disabled={ocupado||!!alteradas||carregandoMateriais} onClick={()=>void carregarMateriais()}>{carregandoMateriais?"Carregando materiais…":"Adicionar material aceito"}</button>:<><p>Escolha somente os materiais que esta empresa aceita.</p>
          <form onSubmit={adicionarMaterial}><fieldset disabled={ocupado||!!alteradas}><label>Buscar material<input type="search" value={buscaMaterial} onChange={e=>{setBuscaMaterial(e.target.value);setMaterial("");}} placeholder="1045, inox, alumínio, nylon…" /></label>
            <label>Material aceito<select required value={material} onChange={e=>setMaterial(e.target.value)}><option value="">Selecione um material</option>{materiaisVisiveis.map(v=>{const chave=v.material_id===null?"catalogo:"+v.codigo:String(v.material_id);return <option key={chave} value={chave}>{v.nome}</option>;})}</select></label>
            {!materiaisVisiveis.length&&<p role="status">{materiaisDisponiveis.length?"Nenhum material corresponde à busca. Limpe a busca ou cadastre outro material.":"Todos os materiais disponíveis já estão vinculados. Você pode cadastrar outro material."}</p>}
            <button type="submit" disabled={!material}>Vincular material</button></fieldset></form>
          <button type="button" disabled={ocupado||!!alteradas} onClick={()=>setCriarMaterial(v=>!v)}>{criarMaterial?"Fechar novo material":"Cadastrar outro material"}</button>
          {criarMaterial&&<form onSubmit={cadastrarMaterial}><fieldset disabled={ocupado||!!alteradas}><label>Nome do novo material<input value={nomeMaterial} onChange={e=>setNomeMaterial(e.target.value)} required minLength={2} maxLength={160} placeholder="Informe a especificação do material" /></label><button type="submit" disabled={nomeMaterial.trim().length<2}>Cadastrar e vincular material</button></fieldset></form>}
        </>}
        <p>Para criar o acesso desta empresa, use o ID #{detalhe.empresa.id} em <Link to="/conta">Minha conta &gt; Criar acesso</Link>.</p>
      </>}
    </section>}
    <section aria-label="Empresas cadastradas"><h2>Empresas cadastradas</h2><form className="empresa52-filtros" onSubmit={e=>{e.preventDefault();setBusca(texto.trim());setPagina(0);setRevisao(v=>v+1);}}><label>Buscar empresa<input value={texto} maxLength={120} onChange={e=>setTexto(e.target.value)} placeholder="Nome, CPF/CNPJ ou ID" /></label><label>Exibir<select value={tipoFiltro} onChange={e=>{setTipoFiltro(e.target.value);setPagina(0);}}><option value="">Todos os tipos</option>{Object.entries(TIPOS).map(([c,n])=><option key={c} value={c}>{n}</option>)}</select></label><button>Buscar</button></form>
      {erroLista&&<p className="empresa52-erro" role="alert">{erroLista}</p>}{carregando&&<p role="status">Carregando empresas…</p>}
      {dados&&<><p>{dados.total} empresa(s) encontrada(s).</p><div className="empresa52-tabela"><table><thead><tr><th>Empresa</th><th>Tipo</th><th>Operações</th><th>Ações</th></tr></thead><tbody>{dados.itens.map(v=><tr key={v.id}><td>{v.razao_social}<small>Empresa #{v.id} · {v.documento}</small></td><td>{TIPOS[v.tipo_empresa]}</td><td>{v.operacoes.join(", ")||(v.tipo_empresa==="cliente"?"Cliente":"Operações ainda não informadas")}</td><td><button disabled={ocupado} onClick={()=>void abrir(v.id)}>Editar empresa #{v.id}</button></td></tr>)}</tbody></table></div>
        {!dados.total&&<p>Nenhuma empresa corresponde aos filtros.</p>}<nav className="empresa52-barra" aria-label="Paginação de empresas"><button disabled={!pagina||carregando} onClick={()=>setPagina(v=>v-1)}>Anterior</button><span>Página {pagina+1}</span><button disabled={carregando||(pagina+1)*20>=dados.total} onClick={()=>setPagina(v=>v+1)}>Próxima</button></nav></>}
    </section>
  </main>;
}
