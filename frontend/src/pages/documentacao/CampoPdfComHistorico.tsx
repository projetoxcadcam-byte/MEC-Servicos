import { useEffect, useId, useRef, useState } from "react";

type Props = { label: string; nome: string; valor: string | number; valores: string[];
  limite: number; numero?: boolean; multiline?: boolean; placeholder?: string; catalogo?: boolean; disabled: boolean;
  onMudar: (valor: string) => void; onGuardar: (valor: string) => void };

export default function CampoPdfComHistorico({ label, nome, valor, valores, limite, numero,
  multiline, placeholder, catalogo, disabled, onMudar, onGuardar }: Props) {
  const id = useId(); const raiz = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);
  const [aberto, setAberto] = useState(false); const [busca, setBusca] = useState("");
  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: globalThis.PointerEvent) => { if (!raiz.current?.contains(e.target as Node)) setAberto(false); };
    document.addEventListener("pointerdown", fechar);
    return () => document.removeEventListener("pointerdown", fechar);
  }, [aberto]);
  useEffect(() => { if (disabled) setAberto(false); }, [disabled]);
  const texto = (v: string) => v.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const opcoes = valores.filter(v => texto(v).includes(texto(busca)));
  const atributos = { id, value: valor, disabled, placeholder,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onMudar(e.currentTarget.value),
    onBlur: (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => onGuardar(e.currentTarget.value),
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      if (e.key === "ArrowDown" && !disabled) { e.preventDefault(); setBusca(""); setAberto(true); }
      if (e.key === "Escape") setAberto(false);
    } };
  return <div className="pdf50-campo" ref={raiz} onKeyDown={e => { if (e.key === "Escape") { setAberto(false); campo.current?.focus(); } }}>
    <label htmlFor={id}>{label}<span className="pdf50-controle">
      {multiline ? <textarea {...atributos} maxLength={limite} ref={el => { campo.current = el; }} /> :
        <input {...atributos} type={numero ? "number" : "text"} {...(numero ? { min:1, max:limite } : { maxLength:limite })} ref={el => { campo.current = el; }} />}
      <button className="pdf50-seta" type="button" disabled={disabled} aria-label={`Selecionar ${nome}${catalogo ? "" : " do histórico"}`} title={catalogo ? `Selecionar ${nome} nas opções e no histórico` : `Selecionar ${nome} do histórico`}
        aria-haspopup="listbox" aria-expanded={aberto} aria-controls={`${id}-opcoes`} onMouseDown={e => e.preventDefault()}
        onClick={() => { setBusca(""); setAberto(v => !v); }}>▾</button>
    </span></label>
    {aberto && <div className="pdf50-menu" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setAberto(false); }}>
      <input type="search" aria-label={`Buscar ${nome}${catalogo ? "" : " no histórico"}`} placeholder={catalogo ? "Buscar nas opções e no histórico…" : "Buscar no histórico…"} value={busca} onChange={e => setBusca(e.target.value)} />
      <div id={`${id}-opcoes`} role="listbox" aria-label={`${catalogo ? "Opções" : "Histórico"} de ${nome}`}>
        {opcoes.map(v => <button type="button" role="option" aria-selected={String(valor) === v} key={v} onClick={() => {
          onMudar(v); onGuardar(v); setAberto(false); campo.current?.focus();
        }}>{v}</button>)}
        {!opcoes.length && <p>{valores.length ? "Nenhum valor encontrado." : "Nenhum valor salvo. Digite um valor para começar."}</p>}
      </div>
    </div>}
  </div>;
}
