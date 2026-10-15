import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import { consultar, dataNota, idValido, mensagem, motivos, raiz, type Detalhe, type Item, type Nota, type Operacao, type Pagina, type Perfil } from "./avaliacoesPortal";
import "./Avaliacoes.css";

function NotaRegistrada({ nota, origem }: { nota: Nota | null; origem: string }) {
  return <article className="mec-av-nota"><h3>{origem}</h3>{nota ? <>
    <p className="mec-av-valor" aria-label={`Nota ${nota.nota} de 5`}><span aria-hidden="true">★</span> {nota.nota}<small> / 5</small></p>
    <p className="mec-av-data">{dataNota(nota.criada_em)}{nota.historica && " · Histórico anterior"}</p>
    {nota.autor && <p>Registrada por {nota.autor.nome}</p>}
    {nota.comentario && <p className="mec-av-comentario">{nota.comentario}</p>}
  </> : <p className="mec-av-vazio">Ainda não registrada</p>}</article>;
}

export default function AvaliacoesPage({ perfil }: { perfil: Perfil }) {
  const { user } = useAuth();
  if (!user || user.role !== perfil) return <main className="mec-av"><p>Entre com o perfil correspondente para consultar as avaliações.</p></main>;
  const contexto = `${user.usuario_id}:${user.role}:${user.empresa_id ?? 0}`;
  return <Conteudo key={contexto} perfil={perfil} contexto={contexto} />;
}

function Conteudo({ perfil, contexto }: { perfil: Perfil; contexto: string }) {
  const [params, setParams] = useSearchParams();
  const cid = params.get("contratacao"); const oid = params.get("ordem");
  const situacao = params.get("situacao") ?? "todas";
  const valido = (!cid || idValido(cid)) && (!oid || idValido(oid)) && ["todas", "disponiveis", "avaliadas"].includes(situacao);
  const [filtroCid, setFiltroCid] = useState(cid ?? ""); const [filtroOid, setFiltroOid] = useState(oid ?? "");
  const [filtroSituacao, setFiltroSituacao] = useState(situacao);
  const [pagina, setPagina] = useState<Pagina | null>(null); const [item, setItem] = useState<Item | null>(null);
  const [inicio, setInicio] = useState(0); const [revisao, setRevisao] = useState(0);
  const [erro, setErro] = useState(""); const [erroDetalhe, setErroDetalhe] = useState("");
  const [erroOperacao, setErroOperacao] = useState(""); const [sucesso, setSucesso] = useState("");
  const [carregando, setCarregando] = useState(false); const [abrindo, setAbrindo] = useState(false);
  const [ocupado, setOcupado] = useState(false); const [nota, setNota] = useState(0); const [comentario, setComentario] = useState("");
  const [operacao, setOperacao] = useState<Operacao | null>(null);
  const controleOperacao = useRef<AbortController | null>(null); const trava = useRef(false);
  const detalheRef = useRef<HTMLElement>(null); const confirmacaoRef = useRef<HTMLElement>(null);
  useEffect(() => () => controleOperacao.current?.abort(), []);
  useEffect(() => {
    controleOperacao.current?.abort(); trava.current = false; setOcupado(false);
    setFiltroCid(cid ?? ""); setFiltroOid(oid ?? ""); setFiltroSituacao(situacao); setInicio(0);
    setOperacao(null); setNota(0); setComentario(""); setSucesso(""); setErroOperacao("");
  }, [cid, oid, situacao]);
  useEffect(() => {
    const controle = new AbortController(); setPagina(null); setErro("");
    if (!valido) { setErro("Informe uma contratação ou OS válida e confira a situação."); return; }
    setCarregando(true);
    void consultar<Pagina>(raiz(perfil), contexto, controle.signal, {
      ...(cid ? { contratacao_id: cid } : {}), ...(oid ? { ordem_servico_id: oid } : {}), situacao, inicio, limite: 20,
    }).then(data => { if (!controle.signal.aborted) setPagina(data); })
      .catch(e => { if (!controle.signal.aborted) setErro(mensagem(e)); })
      .finally(() => { if (!controle.signal.aborted) setCarregando(false); });
    return () => controle.abort();
  }, [perfil, contexto, cid, oid, situacao, inicio, revisao, valido]);
  useEffect(() => {
    const controle = new AbortController(); setItem(null); setErroDetalhe(""); setAbrindo(Boolean(cid && valido));
    if (!cid || !valido) return;
    void consultar<Detalhe>(raiz(perfil) + "/" + cid, contexto, controle.signal)
      .then(data => {
        if (controle.signal.aborted) return;
        if (oid && data.item.ordem_servico_id !== Number(oid)) { setErroDetalhe("A OS informada não pertence a esta contratação."); return; }
        setItem(data.item);
      })
      .catch(e => { if (!controle.signal.aborted) setErroDetalhe(mensagem(e)); })
      .finally(() => { if (!controle.signal.aborted) setAbrindo(false); });
    return () => controle.abort();
  }, [perfil, contexto, cid, oid, revisao, valido]);
  useEffect(() => { if (item) detalheRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [item?.contratacao_id]);
  useEffect(() => { if (operacao) confirmacaoRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [operacao]);

  function filtrar(e: React.FormEvent) {
    e.preventDefault(); setErro("");
    if ((filtroCid && !idValido(filtroCid)) || (filtroOid && !idValido(filtroOid))) { setErro("Use números inteiros positivos nos campos Contratação e OS."); return; }
    const novos = new URLSearchParams();
    if (filtroCid) novos.set("contratacao", filtroCid);
    if (filtroOid) novos.set("ordem", filtroOid);
    if (filtroSituacao !== "todas") novos.set("situacao", filtroSituacao);
    setInicio(0); setParams(novos); setRevisao(v => v + 1);
  }
  async function revisar(e: React.FormEvent) {
    e.preventDefault(); if (!item || !cid || trava.current) return;
    if (nota < 1 || nota > 5) { setErroOperacao("Escolha uma nota de 1 a 5."); return; }
    const controle = new AbortController(); controleOperacao.current = controle; trava.current = true; setOcupado(true); setErroOperacao("");
    try {
      const atual = await consultar<Detalhe>(raiz(perfil) + "/" + cid, contexto, controle.signal);
      if (controle.signal.aborted) return;
      setItem(atual.item);
      if (!atual.item.pode_avaliar) { setErroOperacao(motivos[atual.item.motivo_disponibilidade ?? ""] ?? "Atualize para conferir a situação do serviço."); return; }
      setOperacao({ nota, comentario: comentario.trim() || null, versao: atual.item.versao, chave_operacao: crypto.randomUUID() });
    } catch (e) { if (!controle.signal.aborted) setErroOperacao(mensagem(e)); }
    finally { if (!controle.signal.aborted) { trava.current = false; setOcupado(false); } }
  }
  async function confirmar() {
    if (!operacao || !item || !cid || trava.current) return;
    const controle = new AbortController(); controleOperacao.current = controle; trava.current = true; setOcupado(true); setErroOperacao("");
    try {
      const { data } = await api.post<Detalhe>(raiz(perfil) + "/" + cid, operacao,
        { signal: controle.signal, timeout: 30_000, headers: { "X-MEC-AVALIACOES-CONTEXTO": contexto } });
      if (controle.signal.aborted) return;
      if (data.contexto !== contexto || data.item.contratacao_id !== item.contratacao_id) throw new Error("Contexto de acesso alterado.");
      setItem(data.item); setOperacao(null); setComentario(""); setNota(0);
      setSucesso(data.repetida ? "Esta avaliação já havia sido confirmada. O registro foi consultado." : "Avaliação registrada. Os outros perfis receberam a notificação.");
      setRevisao(v => v + 1);
    } catch (e) {
      if (!controle.signal.aborted) {
        setErroOperacao(mensagem(e));
        if ((e as { response?: { status?: number } }).response?.status === 409) { setOperacao(null); setRevisao(v => v + 1); }
      }
    } finally { if (!controle.signal.aborted) { trava.current = false; setOcupado(false); } }
  }
  function abrir(id: number) { const novos = new URLSearchParams(); novos.set("contratacao", String(id)); setParams(novos); }
  const consulta = perfil === "fornecedor";
  return <main className="mec-av">
    <header className="mec-av-cabecalho"><div><p className="mec-av-sobre">{perfil === "admin" ? "Administração" : perfil === "cliente" ? "Cliente" : "Fornecedor"} · Qualidade do serviço</p>
      <h1>Avaliações do serviço</h1><p>{consulta ? "Acompanhe as notas recebidas do cliente e da administração." : "Avalie o serviço entregue com uma nota de 1 a 5. Cada origem mantém sua própria avaliação."}</p></div>
      {perfil === "admin" && <Link className="mec-av-link" to="/admin/ranking">Ver reputação e ranking</Link>}</header>
    <p className="mec-av-aviso">{perfil === "admin" ? "As notas do cliente e da administração têm médias separadas. " : "Consulte as notas de cada contratação. "}Comentários são visíveis ao autor e à administração.</p>
    <form className="mec-av-filtros" onSubmit={filtrar}>
      <label>Contratação<input inputMode="numeric" value={filtroCid} onChange={e => setFiltroCid(e.target.value)} placeholder="Número" disabled={ocupado} /></label>
      <label>OS<input inputMode="numeric" value={filtroOid} onChange={e => setFiltroOid(e.target.value)} placeholder="Número" disabled={ocupado} /></label>
      <label>Situação<select value={filtroSituacao} onChange={e => setFiltroSituacao(e.target.value)} disabled={ocupado}><option value="todas">Todas</option>{!consulta && <option value="disponiveis">Disponíveis para avaliar</option>}<option value="avaliadas">Com avaliação registrada</option></select></label>
      <button type="submit" disabled={ocupado}>Consultar</button><button type="button" className="mec-av-secundario" disabled={ocupado} onClick={() => { setOperacao(null); setRevisao(v => v + 1); }}>Atualizar</button>
    </form>
    {erro && <p role="alert" className="mec-av-erro">{erro}</p>}
    {carregando && <p role="status">Consultando avaliações…</p>}
    {pagina && <><p className="mec-av-contagem">{pagina.total} contratação(ões)</p>
      {pagina.itens.length ? <div className="mec-av-tabela"><table><thead><tr><th>Contratação / OS</th><th>Fornecedor</th><th>Nota do cliente</th><th>Nota da administração</th><th>Situação</th><th><span className="mec-av-sr">Abrir</span></th></tr></thead><tbody>
        {pagina.itens.map(i => <tr key={i.contratacao_id}><td>#{i.contratacao_id} / {i.ordem_servico_id ? `OS #${i.ordem_servico_id}` : "Sem OS"}</td><td>{i.fornecedor_codigo}</td><td>{i.cliente ? `${i.cliente.nota} / 5` : "—"}</td><td>{i.admin ? `${i.admin.nota} / 5` : "—"}</td><td>{i.pode_avaliar ? <span className="mec-av-disponivel">Disponível para avaliar</span> : motivos[i.motivo_disponibilidade ?? ""] ?? "Em acompanhamento"}</td><td><button type="button" className="mec-av-secundario" onClick={() => abrir(i.contratacao_id)} disabled={ocupado}>Ver contratação #{i.contratacao_id}</button></td></tr>)}
      </tbody></table></div> : <p className="mec-av-vazio">Nenhuma contratação encontrada para estes filtros.</p>}
      <nav className="mec-av-paginacao" aria-label="Páginas de avaliações"><button type="button" disabled={inicio === 0 || ocupado} onClick={() => setInicio(v => Math.max(0, v - 20))}>Anterior</button><span>{pagina.total ? `${inicio + 1}–${Math.min(inicio + 20, pagina.total)} de ${pagina.total}` : "0 resultados"}</span><button type="button" disabled={inicio + 20 >= pagina.total || ocupado} onClick={() => setInicio(v => v + 20)}>Próxima</button></nav>
    </>}
    {abrindo && <p role="status">Abrindo a contratação selecionada…</p>}
    {erroDetalhe && <p role="alert" className="mec-av-erro">{erroDetalhe}</p>}
    {item && <section className="mec-av-detalhe" ref={detalheRef} aria-label="Avaliação da contratação selecionada">
      <div className="mec-av-linha"><div><h2>Contratação #{item.contratacao_id} · {item.ordem_servico_id ? `OS #${item.ordem_servico_id}` : "Sem OS"}</h2><p>{item.fornecedor_codigo}{perfil === "admin" ? ` · ${item.cliente_codigo}` : ""}</p></div>
        <button type="button" className="mec-av-secundario" disabled={ocupado} onClick={() => setParams(new URLSearchParams())}>Ver todas</button></div>
      <div className="mec-av-notas"><NotaRegistrada nota={item.cliente} origem="Avaliação do cliente" /><NotaRegistrada nota={item.admin} origem="Avaliação da administração" /></div>
      {sucesso && <p role="status" className="mec-av-sucesso">{sucesso}</p>}
      {erroOperacao && <p role="alert" className="mec-av-erro">{erroOperacao}</p>}
      {!consulta && !item.pode_avaliar && <p className="mec-av-aviso">{motivos[item.motivo_disponibilidade ?? ""]}</p>}
      {!consulta && item.pode_avaliar && !operacao && <form className="mec-av-formulario" onSubmit={revisar}>
        <h3>{perfil === "admin" ? "Registrar avaliação da administração" : "Registrar minha avaliação"}</h3>
        <p>Considere a qualidade e o cumprimento do serviço entregue. A inspeção técnica das peças permanece na intermediação.</p>
        <fieldset disabled={ocupado}><legend>Nota do serviço</legend><div className="mec-av-estrelas">{[1,2,3,4,5].map(n => <label key={n} className={nota === n ? "selecionada" : ""}><input type="radio" name="nota" value={n} checked={nota === n} onChange={() => setNota(n)} required /><span aria-hidden="true">★</span><span>{n}</span><span className="mec-av-sr"> de 5</span></label>)}</div></fieldset>
        <label>Comentário opcional<textarea rows={4} maxLength={2000} value={comentario} onChange={e => setComentario(e.target.value)} disabled={ocupado} /></label>
        <small>{comentario.length}/2.000 · Restrito ao autor e à administração.</small>
        <button type="submit" disabled={ocupado || !nota}>{ocupado ? "Conferindo…" : "Revisar avaliação"}</button>
      </form>}
      {operacao && <section className="mec-av-confirmacao" ref={confirmacaoRef} aria-label="Conferir avaliação antes de registrar">
        <h3>Conferir antes de registrar</h3><p>{perfil === "admin" ? "Administração" : "Cliente"} · Contratação #{item.contratacao_id} · OS #{item.ordem_servico_id}</p>
        <p className="mec-av-valor">{operacao.nota} <small>/ 5</small></p>{operacao.comentario && <p className="mec-av-comentario">{operacao.comentario}</p>}
        <p>A nota será incluída na média desta origem. Após confirmar, a avaliação fica registrada no histórico.</p>
        <div className="mec-av-linha"><button type="button" disabled={ocupado} onClick={() => void confirmar()}>{ocupado ? "Registrando…" : "Confirmar avaliação"}</button><button type="button" className="mec-av-secundario" disabled={ocupado} onClick={() => { setOperacao(null); setErroOperacao(""); }}>Voltar para editar</button></div>
      </section>}
    </section>}
  </main>;
}
