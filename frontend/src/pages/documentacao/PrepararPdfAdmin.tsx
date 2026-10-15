import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import CampoPdfComHistorico from "./CampoPdfComHistorico";
import OperacoesServicoPdf from "./OperacoesServicoPdf";
import { opcoesMaterialPdf, OPERACOES_PDF, type OperacaoPdf } from "./CatalogoCamposPdf";
import "./PreparacaoPdf.css";

type EscopoServico = "conforme_solicitacao" | "desbaste" | "acabamento" | "peca_completa";
export type CamposCarimbo = { descricao: string; codigo_tecnico: string; material: string; quantidade: number; dureza: string; tratamento_termico: string; revestimento: string; escala: string; unidade: string; revisao: string; tolerancias_gerais: string; escopo_servico?: EscopoServico; sobremetal?: string; observacoes_servico?: string; operacoes_servico?: OperacaoPdf[] };
export type AreaCarimbo = { pagina: number; x: number; y: number; largura: number; altura: number; campos: CamposCarimbo };
export type PreparacaoPdf = { id: number; arquivo_id: number; versao: number; criado_em: string; administrador_nome: string; registro_interno: string; paginas: AreaCarimbo[] };
type ArquivoPdf = { id: number; nome_original: string; sha256: string; versao: number; preparacao_pdf_publicada_id?: number | null };
type PaginaPdf = { pagina: number; largura: number; altura: number };
type Info = { arquivo_id: number; sha256: string; paginas: PaginaPdf[]; preparacoes: PreparacaoPdf[] };
type CampoHistorico = Exclude<keyof CamposCarimbo, "escopo_servico" | "operacoes_servico">;
type ValorHistorico = { campo: CampoHistorico; valor: string };
type Historico = Partial<Record<CampoHistorico, string[]>>;
const BASE = "/administracao/preparacao-pdf";
const ESCOPOS: Record<EscopoServico, string> = { conforme_solicitacao: "Conforme solicitação", desbaste: "Somente desbaste", acabamento: "Somente acabamento", peca_completa: "Peça completa" };
const CAMPOS: [Exclude<keyof CamposCarimbo, "escopo_servico" | "sobremetal" | "observacoes_servico" | "operacoes_servico">, string, number][] = [
  ["descricao", "Descrição da peça *", 80], ["codigo_tecnico", "Código técnico neutro", 30],
  ["material", "Material *", 50], ["quantidade", "Quantidade *", 1000000],
  ["dureza", "Dureza", 40], ["tratamento_termico", "Tratamento térmico", 60],
  ["revestimento", "Revestimento", 60], ["escala", "Escala *", 24],
  ["unidade", "Unidade *", 16], ["revisao", "Revisão", 16],
  ["tolerancias_gerais", "Tolerâncias gerais (quando aplicáveis)", 180],
];
export function erroPdf(erro: unknown) {
  const falha = erro as { response?: { status?: number; data?: { detail?: unknown } } };
  const detalhe = falha.response?.data?.detail;
  const mensagens: Record<string, string> = {
    pdf_invalido: "O conteúdo deste arquivo não é um PDF válido.",
    pdf_protegido_nao_editavel: "Este PDF está protegido. Solicite uma cópia sem proteção para preparar o carimbo.",
    pdf_formulario_ou_assinatura_nao_editavel: "Este PDF contém formulário ou assinatura. Solicite uma cópia simples do desenho.",
    pdf_anotado_nao_editavel: "Este PDF contém anotações. Solicite uma cópia simples do desenho.",
    pdf_rotacao_ou_recorte_nao_suportado: "Este PDF usa rotação ou recorte de página. Solicite uma cópia com as páginas orientadas normalmente.",
    pdf_numero_paginas_nao_suportado: "A preparação aceita de 1 a 50 páginas.",
    pdf_tamanho_pagina_nao_suportado: "O tamanho das páginas deste PDF não é suportado.",
    pdf_excede_limite_preparacao: "A preparação aceita PDFs de até 30 MB.",
    area_carimbo_muito_pequena: "A legenda precisa ter pelo menos 320 × 96 pontos para acomodar os campos. Mantenha a seleção dentro da legenda, preservando vistas, cotas e notas.",
    area_corta_texto_imagem_ou_formulario: "A área corta um texto, imagem ou bloco do PDF. Ajuste a seleção para incluir o carimbo inteiro, sem atingir o desenho. PDFs digitalizados podem exigir preparação externa.",
    area_corta_bloco_texto: "O PDF reúne textos de dentro e de fora da legenda em um mesmo bloco. Ajuste a seleção sem atingir cotas ou solicite um PDF com a legenda separada.",
    pdf_estrutura_nao_suportada: "A estrutura deste PDF não permite trocar a legenda com segurança. Solicite outra exportação do desenho.",
    pdf_divergencia_fora_legenda: "A comparação detectou uma alteração fora da legenda. A cópia foi recusada. Confira a seleção ou solicite outra exportação do desenho.",
    texto_nao_cabe_no_carimbo: "Um dos campos não cabe na área escolhida. Confira os dados e as observações do serviço sem omitir informações necessárias. Ajuste a área somente dentro da legenda, preservando o desenho.",
    pdf_nao_pode_ser_preparado: "Este PDF não pôde ser preparado. Confira o formato ou solicite outra cópia.",
    pdf_nao_pode_ser_renderizado: "Não foi possível exibir esta página do PDF.",
    documentacao_alterada_atualize: "O arquivo ou a liberação mudou. Feche a preparação, atualize a lista e revise novamente.",
    arquivo_tecnico_sem_conteudo_valido: "O original está indisponível, foi alterado ou desvinculado. Atualize a lista.",
    pdf_preparado_indisponivel: "Esta cópia está indisponível ou foi alterada. Gere e revise uma nova versão.",
    preparacao_pdf_diverge_do_original: "A versão escolhida não corresponde ao original atual. Atualize e revise novamente.",
    chave_operacao_reutilizada: "A operação mudou. Atualize antes de tentar novamente.",
  };
  if (typeof detalhe === "string" && mensagens[detalhe]) return mensagens[detalhe];
  if (falha.response?.status === 401) return "Sua sessão expirou. Entre novamente.";
  if (falha.response?.status === 403) return "Esta preparação exige acesso administrativo.";
  if (falha.response?.status === 422) return "Confira os campos obrigatórios, o número da página e os limites da seleção. Use símbolos comuns como ±, ° e Ø.";
  return "Não foi possível concluir a preparação. Confira a conexão e tente novamente.";
}

export default function PrepararPdfAdmin({ arquivo, onFechar, onLiberar }: { arquivo: ArquivoPdf; onFechar: () => void; onLiberar: (p: PreparacaoPdf) => void }) {
  const { user } = useAuth();
  const contexto = user?.role === "admin" ? String(user.usuario_id) : "";
  const vigente = useRef(contexto); vigente.current = contexto;
  const [info, setInfo] = useState<Info | null>(null); const [erro, setErro] = useState("");
  const [pagina, setPagina] = useState(1); const [areas, setAreas] = useState<AreaCarimbo[]>([]);
  const [registro, setRegistro] = useState(""); const [ocupado, setOcupado] = useState(false);
  const [escolhida, setEscolhida] = useState<PreparacaoPdf | null>(null); const [revisado, setRevisado] = useState(false);
  const [imagem, setImagem] = useState(""); const [carregandoImagem, setCarregandoImagem] = useState(false);
  const [carregando, setCarregando] = useState(true); const [mostrarCopia, setMostrarCopia] = useState(false);
  const [baixando, setBaixando] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [historico, setHistorico] = useState<Historico>({});
  const [erroHistorico, setErroHistorico] = useState(""); const [estadoHistorico, setEstadoHistorico] = useState("");
  const [tentativaHistorico, setTentativaHistorico] = useState(0);
  const editados = useRef(new Map<string, ValorHistorico>());
  const aceitos = useRef(new Set<string>()); const pendentes = useRef(new Set<string>());
  const filaHistorico = useRef<Promise<boolean>>(Promise.resolve(true));
  const ativa = useRef(true); const trava = useRef(false); const pedidos = useRef(new Set<AbortController>());
  const chave = useRef({ pedido: "", valor: "" }); const inicio = useRef<{ x: number; y: number } | null>(null);
  const area = areas.find(a => a.pagina === pagina); const tamanho = info?.paginas.find(p => p.pagina === pagina);
  useEffect(() => { ativa.current = true; return () => { ativa.current = false; for (const c of pedidos.current) c.abort(); }; }, []);
  useEffect(() => {
    const c = new AbortController(); pedidos.current.add(c); let atual = true;
    setInfo(null); setAreas([]); setEscolhida(null); setRevisado(false); setImagem(""); setErro(""); setCarregando(true);
    editados.current = new Map(); aceitos.current = new Set(); pendentes.current = new Set(); filaHistorico.current = Promise.resolve(true); setEstadoHistorico("");
    if (!contexto) { setCarregando(false); return; }
    void api.get<Info>(`${BASE}/arquivos/${arquivo.id}`, { signal: c.signal, timeout: 30_000 }).then(({ data }) => {
      if (atual && vigente.current === contexto) { setInfo(data); if (data.sha256 !== arquivo.sha256) setErro("O original mudou. Atualize a lista antes de preparar."); }
    }).catch(e => { if (atual && !c.signal.aborted) setErro(erroPdf(e)); }).finally(() => { if (atual) setCarregando(false); pedidos.current.delete(c); });
    return () => { atual = false; c.abort(); for (const outro of pedidos.current) outro.abort(); };
  }, [arquivo.id, arquivo.sha256, contexto]);
  useEffect(() => {
    const c = new AbortController(); pedidos.current.add(c); let atual = true;
    setHistorico({}); setErroHistorico("");
    if (!contexto) return () => { pedidos.current.delete(c); };
    void api.get<{ campos: Historico }>(`${BASE}/historico-campos`, { signal: c.signal, timeout: 15_000 }).then(({ data }) => {
      if (atual && vigente.current === contexto) setHistorico(h => {
        const resultado = { ...data.campos };
        for (const k of Object.keys(h) as CampoHistorico[]) resultado[k] = [...new Set([...(h[k] ?? []), ...(resultado[k] ?? [])])];
        return resultado;
      });
    }).catch(() => { if (atual && !c.signal.aborted && vigente.current === contexto) setErroHistorico("Não foi possível carregar o histórico. Tente carregar novamente."); })
      .finally(() => pedidos.current.delete(c));
    return () => { atual = false; c.abort(); };
  }, [arquivo.id, contexto, tentativaHistorico]);
  useEffect(() => {
    const c = new AbortController(); pedidos.current.add(c); let atual = true; let url = "";
    setImagem("");
    if (!info || !contexto) return () => { pedidos.current.delete(c); };
    setCarregandoImagem(true);
    const rota = mostrarCopia && escolhida ? `${BASE}/versoes/${escolhida.id}/paginas/${pagina}` : `${BASE}/arquivos/${arquivo.id}/paginas/${pagina}`;
    void api.get<Blob>(rota, { responseType: "blob", params: mostrarCopia && escolhida ? {} : { sha256: info.sha256 }, signal: c.signal, timeout: 45_000 }).then(({ data }) => {
      if (atual && vigente.current === contexto) { url = URL.createObjectURL(data); setImagem(url); }
    }).catch(e => { if (atual && !c.signal.aborted) setErro(erroPdf(e)); }).finally(() => { if (atual) setCarregandoImagem(false); pedidos.current.delete(c); });
    return () => { atual = false; c.abort(); if (url) URL.revokeObjectURL(url); };
  }, [arquivo.id, info, pagina, mostrarCopia, escolhida, contexto]);
  function incluir() {
    if (!tamanho || area) return;
    const largura = Math.min(.95, Math.max(.21, 330 / tamanho.largura)); const altura = Math.min(.9, Math.max(.09, 140 / tamanho.altura));
    setAreas(a => [...a, { pagina, x: 1 - largura - .01, y: 1 - altura - .01, largura, altura,
      campos: { descricao: "", codigo_tecnico: `ARQUIVO-${arquivo.id}`, material: "", quantidade: 1, dureza: "", tratamento_termico: "", revestimento: "", escala: "", unidade: "mm", revisao: "", tolerancias_gerais: "", escopo_servico: "conforme_solicitacao", sobremetal: "", observacoes_servico: "", operacoes_servico: [] } }]);
    setMostrarCopia(false);
  }
  function mudar(alteracao: Partial<AreaCarimbo>) {
    if (alteracao.campos && area) for (const k of Object.keys(alteracao.campos) as (keyof CamposCarimbo)[]) {
      if (k !== "escopo_servico" && k !== "operacoes_servico" && alteracao.campos[k] !== area.campos[k]) editados.current.set(`${pagina}:${k}`, { campo: k, valor: String(alteracao.campos[k] ?? "") });
    }
    setErro(""); setAreas(a => a.map(v => v.pagina === pagina ? { ...v, ...alteracao } : v));
  }
  function guardarValores(valores: ValorHistorico[]) {
    if (!contexto) return Promise.resolve(false);
    const ctx = contexto; const itens: ValorHistorico[] = []; const pendentesDesteContexto = pendentes.current; const aceitosDesteContexto = aceitos.current;
    for (const item of valores) {
      const valor = item.valor.trim(); const chave = `${item.campo}\n${valor}`;
      if (!valor || aceitosDesteContexto.has(chave) || pendentesDesteContexto.has(chave)) continue;
      pendentesDesteContexto.add(chave); itens.push({ ...item, valor });
    }
    if (!itens.length) return filaHistorico.current;
    const salvar = async () => {
      const chaves = itens.map(v => `${v.campo}\n${v.valor}`);
      if (!ativa.current || vigente.current !== ctx) { chaves.forEach(v => pendentesDesteContexto.delete(v)); return false; }
      const c = new AbortController(); pedidos.current.add(c); setEstadoHistorico("Guardando valores no histórico…");
      try {
        await api.post(`${BASE}/historico-campos`, { itens }, { signal: c.signal, timeout: 15_000 });
        if (!ativa.current || vigente.current !== ctx || c.signal.aborted) return false;
        chaves.forEach(v => aceitosDesteContexto.add(v));
        setHistorico(h => {
          const atualizado = { ...h };
          for (const { campo, valor } of itens) atualizado[campo] = [valor, ...(atualizado[campo] ?? []).filter(v => v.replace(/\s+/g, " ").toLowerCase() !== valor.replace(/\s+/g, " ").toLowerCase())];
          return atualizado;
        });
        setErroHistorico(""); setEstadoHistorico("Valores guardados no histórico."); return true;
      } catch {
        if (ativa.current && vigente.current === ctx && !c.signal.aborted) { setErroHistorico("Não foi possível guardar os valores no histórico. Confira os campos e tente guardar novamente."); setEstadoHistorico(""); }
        return false;
      } finally { chaves.forEach(v => pendentesDesteContexto.delete(v)); pedidos.current.delete(c); }
    };
    filaHistorico.current = filaHistorico.current.then(salvar, salvar);
    return filaHistorico.current;
  }
  function guardarCampo(campo: CampoHistorico, valor: string) {
    editados.current.set(`${pagina}:${campo}`, { campo, valor });
    return guardarValores([{ campo, valor }]);
  }
  function campoHistorico(k: CampoHistorico, label: string, limite: number, multiline = false, placeholder?: string) {
    if (!area) return null;
    return <CampoPdfComHistorico key={k} label={label} nome={label.replace(/\s*\*.*/, "").replace(/\s*\(.*/, "")}
      valor={area.campos[k] ?? ""} valores={k === "material" ? opcoesMaterialPdf(historico.material ?? []) : historico[k] ?? []} catalogo={k === "material"} limite={limite} multiline={multiline} numero={k === "quantidade"}
      placeholder={placeholder} disabled={ocupado} onMudar={valor => mudar({ campos: { ...area.campos, [k]: k === "quantidade" ? Number(valor) : valor } })}
      onGuardar={valor => { void guardarCampo(k, valor); }} />;
  }
  async function fechar() { await guardarValores([...editados.current.values()]); if (ativa.current && vigente.current === contexto) onFechar(); }
  function ponto(e: PointerEvent<SVGSVGElement>) {
    const b = e.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (e.clientX - b.left) / b.width)), y: Math.max(0, Math.min(1, (e.clientY - b.top) / b.height)) };
  }
  function arrastar(e: PointerEvent<SVGSVGElement>) {
    if (!inicio.current) return;
    const p = ponto(e); mudar({ x: Math.min(p.x, inicio.current.x), y: Math.min(p.y, inicio.current.y), largura: Math.max(.00001, Math.abs(p.x - inicio.current.x)), altura: Math.max(.00001, Math.abs(p.y - inicio.current.y)) });
  }
  const areaInsuficiente = areas.some(a => {
    const p = info?.paginas.find(p => p.pagina === a.pagina);
    return !p || a.largura * p.largura < 320 - 0.000001 || a.altura * p.altura < 96 - 0.000001;
  });
  const valido = !areaInsuficiente && areas.length > 0 && areas.every(a => a.campos.descricao.trim() && a.campos.material.trim() && a.campos.quantidade > 0 && a.campos.escala.trim() && a.campos.unidade.trim() && a.x + a.largura <= 1.00000001 && a.y + a.altura <= 1.00000001);
  async function gerar() {
    if (!info || !contexto || trava.current || !valido || registro.trim().length < 3 || info.sha256 !== arquivo.sha256) return;
    trava.current = true; setOcupado(true); setErro(""); const ctx = contexto;
    const c = new AbortController(); pedidos.current.add(c);
    const corpo = { sha256: info.sha256, versao_liberacao: arquivo.versao, paginas: areas, registro_interno: registro.trim() };
    const serializado = JSON.stringify(corpo);
    if (chave.current.pedido !== serializado) chave.current = { pedido: serializado, valor: crypto.randomUUID() };
    try {
      await guardarValores([...editados.current.values()]);
      if (!ativa.current || vigente.current !== ctx || c.signal.aborted) return;
      const { data } = await api.post<PreparacaoPdf>(`${BASE}/arquivos/${arquivo.id}`, { ...corpo, chave_operacao: chave.current.valor }, { signal: c.signal, timeout: 90_000 });
      if (ativa.current && vigente.current === ctx && !c.signal.aborted) {
        setInfo(i => i && { ...i, preparacoes: [data, ...i.preparacoes.filter(p => p.id !== data.id)] });
        setEscolhida(data); setMostrarCopia(true); setRevisado(false); setPagina(data.paginas[0].pagina);
      }
    } catch (e) { if (ativa.current && vigente.current === ctx && !c.signal.aborted) setErro(erroPdf(e)); }
    finally { trava.current = false; pedidos.current.delete(c); if (ativa.current && vigente.current === ctx) setOcupado(false); }
  }
  async function baixar() {
    if (!escolhida || baixando || !contexto) return; const p = escolhida; const ctx = contexto;
    const c = new AbortController(); pedidos.current.add(c); setBaixando(true); setErro("");
    try {
      const { data } = await api.get<Blob>(`${BASE}/versoes/${p.id}/download`, { responseType: "blob", signal: c.signal, timeout: 45_000 });
      if (!ativa.current || vigente.current !== ctx || c.signal.aborted) return;
      const url = URL.createObjectURL(data); const a = document.createElement("a"); a.href = url; a.download = `mec-arquivo-${arquivo.id}-versao-${p.versao}.pdf`; document.body.appendChild(a); a.click(); a.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (e) { if (ativa.current && vigente.current === ctx && !c.signal.aborted) setErro(erroPdf(e)); }
    finally { pedidos.current.delete(c); if (ativa.current && vigente.current === ctx) setBaixando(false); }
  }
  if (!contexto) return <p role="alert">A preparação de PDF exige acesso administrativo.</p>;
  return <section className="pdf48-panel" aria-label="Preparação do PDF para cotação">
    <div className="pdf48-topo"><div><h2>Preparar PDF com carimbo MEC-Serviços</h2><p>{arquivo.nome_original}</p></div><button disabled={ocupado} onClick={() => void fechar()}>Fechar preparação</button></div>
    <p className="doc42-alert">Selecione somente o carimbo e informe os dados necessários ao serviço contratado. Para desbaste, registre o sobremetal quando definido. Confira também as outras áreas e páginas: a preparação não identifica automaticamente todos os dados do cliente.</p>
    <p>Gerar uma cópia não altera a liberação atual. O fornecedor receberá a nova versão somente após a revisão e a liberação.</p>
    <p>Na setinha de Material, escolha uma opção pronta ou um material do seu histórico. Nos outros campos, selecione valores já usados ou digite um valor novo: ele será guardado ao sair do campo.</p>
    {estadoHistorico && <p role="status">{estadoHistorico}</p>}
    {erroHistorico && <div className="doc42-alert" role="alert"><p>{erroHistorico}</p><button disabled={ocupado} onClick={() => { setTentativaHistorico(v => v + 1); void guardarValores([...editados.current.values()]); }}>Tentar histórico novamente</button></div>}
    {erro && <p role="alert" className="doc42-alert doc42-erro">{erro}</p>}
    {carregando && <p role="status">Conferindo PDF…</p>}
    {info && <>
      <div className="pdf48-barra"><label>Página<select value={pagina} disabled={ocupado} onChange={e => { setPagina(Number(e.target.value)); setRevisado(false); }}>{info.paginas.map(p => <option key={p.pagina} value={p.pagina}>{p.pagina} de {info.paginas.length}{areas.some(a => a.pagina === p.pagina) ? " · carimbo configurado" : ""}</option>)}</select></label>
        <label>Ampliação<select value={zoom} onChange={e => setZoom(Number(e.target.value))}><option value={1}>100%</option><option value={2}>200%</option><option value={3}>300%</option></select></label>
        <button disabled={ocupado || !escolhida} onClick={() => setMostrarCopia(v => !v)}>{mostrarCopia ? "Ver original" : "Ver cópia preparada"}</button>
        {!mostrarCopia && <button disabled={ocupado} onClick={() => area ? setAreas(a => a.filter(v => v.pagina !== pagina)) : incluir()}>{area ? "Remover carimbo desta página" : "Incluir carimbo nesta página"}</button>}
      </div>
      {carregandoImagem && <p role="status">Carregando página…</p>}
      {imagem && tamanho && <div className="pdf48-rolagem"><div className="pdf48-pagina" style={{ width: `${zoom * 100}%`, aspectRatio: `${tamanho.largura} / ${tamanho.altura}` }}><img src={imagem} alt={`Página ${pagina} ${mostrarCopia ? "da cópia preparada" : "do original"}`} />
        {!mostrarCopia && area && <svg viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-label="Área do carimbo; arraste para selecionar" onPointerDown={e => { if (ocupado) return; e.currentTarget.setPointerCapture(e.pointerId); inicio.current = ponto(e); }} onPointerMove={arrastar} onPointerUp={e => { arrastar(e); inicio.current = null; e.currentTarget.releasePointerCapture(e.pointerId); }} onPointerCancel={() => { inicio.current = null; }}><rect x={area.x * 1000} y={area.y * 1000} width={area.largura * 1000} height={area.altura * 1000} /></svg>}
      </div></div>}
      {!mostrarCopia && area && <fieldset disabled={ocupado} className="pdf48-config"><legend>Carimbo da página {pagina}</legend><p>Arraste sobre a página ou ajuste os percentuais. Inclua a logo e a identificação antigas por inteiro; preserve cotas, vistas e notas fora do carimbo.</p>
        <div className="pdf48-coordenadas">{([["x", "Esquerda (%)"], ["y", "Topo (%)"], ["largura", "Largura (%)"], ["altura", "Altura (%)"]] as const).map(([k, label]) => <label key={k}>{label}<input type="number" min={0} max={100} step="0.001" value={Number((area[k] * 100).toFixed(3))} onChange={e => mudar({ [k]: Number(e.target.value) / 100 })} /></label>)}</div>
        {tamanho && <p>Área: {(area.largura * tamanho.largura).toFixed(1)} × {(area.altura * tamanho.altura).toFixed(1)} pontos. Mínimo: 320 × 96. O formato compacto é usado automaticamente em legendas com altura inferior a 132 pontos.</p>}
        {tamanho && (area.largura * tamanho.largura < 320 - 0.000001 || area.altura * tamanho.altura < 96 - 0.000001) && <p className="doc42-alert doc42-erro" role="alert">A área selecionada é pequena para o carimbo. Ajuste somente dentro da legenda; preserve as vistas, cotas e notas.</p>}
        <OperacoesServicoPdf key={pagina} valores={area.campos.operacoes_servico ?? []} disabled={ocupado} onMudar={valores => mudar({ campos: { ...area.campos, operacoes_servico: valores } })} />
        <p>Selecione até 8 operações para esta página. Se necessário, detalhe a sequência e os requisitos nas observações. Nenhuma operação é selecionada automaticamente.</p>
        <div className="pdf48-campos"><label>Escopo da usinagem<select value={area.campos.escopo_servico ?? "conforme_solicitacao"} onChange={e => mudar({ campos: { ...area.campos, escopo_servico: e.target.value as EscopoServico } })}>{Object.entries(ESCOPOS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
          {campoHistorico("sobremetal", "Sobremetal (quando definido)", 80, false, "Informe valor, unidade e superfícies.")}
          {campoHistorico("observacoes_servico", "Observações do serviço", 180, true, "Etapas e condições acordadas para esta peça.")}</div>
        <p>Confira a especificação completa do material, incluindo a condição de fornecimento quando necessária. Preencha dureza, tratamentos, revestimento e tolerâncias apenas quando fizerem parte do serviço. O escopo não altera as cotas e notas que já estão nas vistas do desenho.</p>
        <div className="pdf48-campos">{CAMPOS.map(([k, label, limite]) => campoHistorico(k, label, limite, k === "tolerancias_gerais"))}</div>
      </fieldset>}
      {!mostrarCopia && <div className="pdf48-gerar"><p>{areas.length} página(s) configurada(s). As outras páginas permanecem no documento.</p><label>Registro interno da preparação<textarea maxLength={2000} value={registro} disabled={ocupado} onChange={e => setRegistro(e.target.value)} placeholder="Especificações conferidas e área substituída." /></label><button disabled={ocupado || !valido || registro.trim().length < 3 || info.sha256 !== arquivo.sha256} onClick={() => void gerar()}>{ocupado ? "Preparando cópia…" : "Gerar cópia para revisão"}</button></div>}
      {!!info.preparacoes.length && <div className="pdf48-versoes"><h3>Cópias preparadas</h3><label>Versão para revisar<select value={escolhida?.id ?? ""} disabled={ocupado} onChange={e => { const p = info.preparacoes.find(v => v.id === Number(e.target.value)) ?? null; setEscolhida(p); setMostrarCopia(!!p); setRevisado(false); if (p) setPagina(p.paginas[0].pagina); }}><option value="">Selecione uma cópia</option>{info.preparacoes.map(p => <option key={p.id} value={p.id}>Versão {p.versao}{p.id === arquivo.preparacao_pdf_publicada_id ? " · liberada" : ""} · {p.administrador_nome}</option>)}</select></label>
        {escolhida && <><p>Versão {escolhida.versao} · {escolhida.criado_em}<br />{escolhida.registro_interno}</p>{escolhida.paginas.map(p => <p key={p.pagina}>Página {p.pagina}: {p.campos.operacoes_servico?.length ? <>{p.campos.operacoes_servico.map(c => OPERACOES_PDF.find(v => v.codigo === c)?.nome ?? c).join(", ")}{p.campos.escopo_servico && p.campos.escopo_servico !== "conforme_solicitacao" && <> · {ESCOPOS[p.campos.escopo_servico]}</>}</> : p.campos.escopo_servico && p.campos.escopo_servico !== "conforme_solicitacao" ? ESCOPOS[p.campos.escopo_servico] : p.campos.sobremetal || p.campos.observacoes_servico ? ESCOPOS.conforme_solicitacao : "Escopo não indicado nesta cópia"}{p.campos.sobremetal && <> · Sobremetal: {p.campos.sobremetal}</>}{p.campos.observacoes_servico && <> · {p.campos.observacoes_servico}</>}</p>)}<div className="doc42-acoes"><button disabled={baixando} onClick={() => void baixar()}>{baixando ? "Baixando…" : "Baixar cópia para revisar"}</button></div><label className="doc42-check"><input type="checkbox" checked={revisado} disabled={ocupado} onChange={e => setRevisado(e.target.checked)} />Conferi todas as páginas da cópia, as operações e o escopo do serviço, as especificações aplicáveis e a ausência de contatos ou identificação do cliente.</label><button disabled={ocupado || !revisado || escolhida.id === arquivo.preparacao_pdf_publicada_id} onClick={() => onLiberar(escolhida)}>Liberar esta versão para cotação</button></>}
      </div>}
    </>}
  </section>;
}
