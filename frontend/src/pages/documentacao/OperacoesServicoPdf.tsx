import { useEffect, useId, useRef, useState } from "react";
import { GRUPOS_OPERACOES_PDF, OPERACOES_PDF, MAX_OPERACOES_PDF, type OperacaoPdf } from "./CatalogoCamposPdf";

export default function OperacoesServicoPdf({ valores, disabled, onMudar }: {
  valores: OperacaoPdf[]; disabled: boolean; onMudar: (valores: OperacaoPdf[]) => void;
}) {
  const id = useId(); const raiz = useRef<HTMLDivElement>(null); const botao = useRef<HTMLButtonElement>(null);
  const [aberto, setAberto] = useState(false); const [busca, setBusca] = useState("");
  const normal = (valor: string) => valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const grupos = GRUPOS_OPERACOES_PDF.map(g => ({ nome: g.nome, opcoes: g.opcoes.filter(([, nome]) => normal(nome).includes(normal(busca))) })).filter(g => g.opcoes.length);
  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: globalThis.PointerEvent) => { if (!raiz.current?.contains(e.target as Node)) setAberto(false); };
    document.addEventListener("pointerdown", fechar);
    return () => document.removeEventListener("pointerdown", fechar);
  }, [aberto]);
  useEffect(() => { if (disabled) setAberto(false); }, [disabled]);
  function alternar(codigo: OperacaoPdf) {
    if (disabled || (!valores.includes(codigo) && valores.length >= MAX_OPERACOES_PDF)) return;
    const proximas = valores.includes(codigo) ? valores.filter(v => v !== codigo) : [...valores, codigo];
    onMudar(OPERACOES_PDF.map(v => v.codigo).filter(v => proximas.includes(v)));
  }
  return <div className="pdf51-operacoes" ref={raiz} onKeyDown={e => { if (e.key === "Escape") { e.stopPropagation(); setAberto(false); botao.current?.focus(); } }}>
    <span id={`${id}-label`}>Operações do serviço</span>
    <button type="button" className="pdf51-seletor" ref={botao} disabled={disabled} aria-label="Selecionar operações do serviço"
      aria-haspopup="dialog" aria-expanded={aberto} aria-controls={`${id}-menu`} onClick={() => { setBusca(""); setAberto(v => !v); }}>
      <span>{valores.length ? `${valores.length} operação(ões) selecionada(s)` : "Selecione uma ou mais operações"}</span><span aria-hidden="true">▾</span>
    </button>
    {!!valores.length && <div className="pdf51-selecionadas" aria-label="Operações selecionadas">{OPERACOES_PDF.filter(v => valores.includes(v.codigo)).map(v =>
      <button key={v.codigo} type="button" disabled={disabled} aria-label={`Remover ${v.nome}`} onClick={() => alternar(v.codigo)}>{v.nome} <span aria-hidden="true">×</span></button>)}</div>}
    {aberto && <div id={`${id}-menu`} className="pdf50-menu pdf51-menu" role="dialog" aria-labelledby={`${id}-label`}
      onBlur={e => { if (!raiz.current?.contains(e.relatedTarget as Node)) setAberto(false); }}>
      <input type="search" aria-label="Buscar operação do serviço" placeholder="Buscar usinagem, dobra, solda, pintura…" value={busca} onChange={e => setBusca(e.target.value)} />
      <p>{valores.length} de {MAX_OPERACOES_PDF} selecionadas</p>
      <div className="pdf51-lista">{grupos.map(g => <fieldset key={g.nome}><legend>{g.nome}</legend>{g.opcoes.map(([codigo, nome]) =>
        <label key={codigo}><input type="checkbox" checked={valores.includes(codigo)} disabled={disabled || (!valores.includes(codigo) && valores.length >= MAX_OPERACOES_PDF)} onChange={() => alternar(codigo)} />{nome}</label>)}</fieldset>)}
        {!grupos.length && <p>Nenhuma operação encontrada. Use as observações para detalhar serviços adicionais.</p>}
      </div>
      <button type="button" className="pdf51-concluir" onClick={() => { setAberto(false); botao.current?.focus(); }}>Concluir seleção</button>
    </div>}
  </div>;
}
