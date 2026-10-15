import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, Check, Search } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { GUIAS, filtrarEtapas, type PerfilTutorial } from "./dadosTutorial";
import { chaveTutorial, lerProgresso, salvarProgresso } from "./progressoTutorial";
import "./Tutorial.css";

function armazenamentoLocal(): Storage | undefined {
  try { return window.localStorage; } catch { return undefined; }
}

export default function TutorialPage({ perfil }: { perfil: PerfilTutorial }) {
  const { user } = useAuth();
  if (!user || user.role !== perfil || user.deve_alterar_senha) {
    return <section className="t66"><p role="alert">Entre com seu perfil e conclua a atualização do acesso para abrir o tutorial.</p></section>;
  }
  const chave = chaveTutorial(user.usuario_id, perfil, user.empresa_id);
  return <ConteudoTutorial key={chave} perfil={perfil} chave={chave} />;
}

function ConteudoTutorial({ perfil, chave }: { perfil: PerfilTutorial; chave: string }) {
  const guia = GUIAS[perfil];
  const [parametros, setParametros] = useSearchParams();
  const [progresso, setProgresso] = useState(() => lerProgresso(armazenamentoLocal(), chave, guia.etapas.map(etapa => etapa.id)));
  const [busca, setBusca] = useState("");
  const [salvo, setSalvo] = useState(true);
  const [aviso, setAviso] = useState("");
  const [reiniciando, setReiniciando] = useState(false);
  const titulo = useRef<HTMLHeadingElement>(null);
  const etapaUrl = parametros.get("etapa");
  const indiceUrl = guia.etapas.findIndex(etapa => etapa.id === etapaUrl);
  const indice = indiceUrl >= 0 ? indiceUrl : Math.max(0, guia.etapas.findIndex(etapa => etapa.id === progresso.ultima));
  const atual = guia.etapas[indice];
  const filtradas = filtrarEtapas(guia, busca);
  const lida = progresso.lidas.includes(atual.id);

  useEffect(() => {
    titulo.current?.focus({ preventScroll: true });
  }, [atual.id]);

  function guardar(valor: typeof progresso) {
    setProgresso(valor);
    setSalvo(salvarProgresso(armazenamentoLocal(), chave, valor));
  }
  function selecionar(id: string) {
    if (!guia.etapas.some(etapa => etapa.id === id)) return;
    setAviso(""); setReiniciando(false);
    guardar({ ...progresso, ultima: id });
    setParametros({ etapa: id });
    titulo.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }
  function alternarLeitura() {
    guardar({ ...progresso, ultima: atual.id, lidas: lida ? progresso.lidas.filter(id => id !== atual.id) : [...progresso.lidas, atual.id] });
    setAviso(lida ? "Etapa marcada para reler." : "Leitura desta etapa concluída.");
  }
  function reiniciar() {
    guardar({ versao: 1, lidas: [], ultima: guia.etapas[0].id });
    setBusca(""); setParametros({ etapa: guia.etapas[0].id });
    setReiniciando(false); setAviso("Progresso de leitura reiniciado.");
  }

  return <section className="t66" aria-label={`Tutorial do perfil ${guia.nome}`}>
    <header className="t66-cabecalho">
      <div><p className="t66-perfil"><BookOpen size={17} aria-hidden="true" /> GUIA DO PERFIL · {guia.nome}</p>
        <h1>Ajuda e tutorial</h1><p className="t66-introducao">{guia.introducao}</p></div>
      <Link className="t66-botao t66-secundario" to={perfil === "admin" ? "/admin" : `/${perfil}`}>Ir ao Dashboard <ArrowRight size={16} aria-hidden="true" /></Link>
    </header>

    <div className="t66-progresso">
      <div><strong>{progresso.lidas.length} de {guia.etapas.length} etapas lidas</strong>
        <span>{salvo ? "Sua leitura fica salva neste navegador para esta conta." : "Você pode continuar. A leitura ficará marcada enquanto esta página estiver aberta."}</span></div>
      <progress value={progresso.lidas.length} max={guia.etapas.length} aria-label="Progresso de leitura do tutorial" />
      <button className="t66-botao t66-secundario" type="button" onClick={() => setReiniciando(valor => !valor)} aria-expanded={reiniciando} aria-controls="t66-reiniciar">Reiniciar leitura</button>
    </div>
    {reiniciando && <div className="t66-confirmacao" id="t66-reiniciar"><p>Deseja limpar as marcações de leitura deste tutorial para sua conta neste navegador?</p>
      <div className="t66-acoes"><button className="t66-botao" type="button" onClick={reiniciar}>Confirmar reinício da leitura</button>
        <button className="t66-botao t66-secundario" type="button" onClick={() => setReiniciando(false)}>Continuar como está</button></div></div>}
    <p className="t66-aviso" role="status" aria-live="polite">{aviso}</p>

    <div className="t66-corpo">
      <aside className="t66-indice" aria-label="Índice do tutorial">
        <label className="t66-busca"><span><Search size={16} aria-hidden="true" /> Buscar no tutorial</span>
          <input type="search" value={busca} maxLength={120} onChange={evento => setBusca(evento.target.value)} placeholder="Ex.: orçamento, produção…" /></label>
        <p className="t66-resultado-busca" aria-live="polite">{busca.trim() ? `${filtradas.length} etapa(s) encontrada(s)` : "Escolha uma etapa ou siga a sequência."}</p>
        <nav aria-label="Etapas do tutorial"><ol>{filtradas.map(etapa => <li key={etapa.id}>
          <button type="button" className={`t66-item ${etapa.id === atual.id ? "t66-ativo" : ""}`} aria-current={etapa.id === atual.id ? "step" : undefined} onClick={() => selecionar(etapa.id)}>
            <span className="t66-numero" aria-hidden="true">{progresso.lidas.includes(etapa.id) ? <Check size={16} /> : guia.etapas.indexOf(etapa) + 1}</span>
            <span><small>{etapa.categoria}</small><strong>{etapa.titulo}</strong>{progresso.lidas.includes(etapa.id) && <span className="t66-lida">Leitura concluída</span>}</span>
          </button>
        </li>)}</ol></nav>
        {!filtradas.length && <div className="t66-sem-resultado"><p>Nenhuma etapa corresponde à busca.</p><button className="t66-botao t66-secundario" type="button" onClick={() => setBusca("")}>Limpar busca</button></div>}
      </aside>

      <article className="t66-etapa" aria-labelledby="t66-titulo-etapa">
        <p className="t66-etiqueta">Etapa {indice + 1} de {guia.etapas.length} · {atual.categoria}</p>
        <h2 id="t66-titulo-etapa" ref={titulo} tabIndex={-1}>{atual.titulo}</h2>
        <p className="t66-resumo">{atual.resumo}</p>
        <div className="t66-onde"><div><small>ONDE FAZER</small><strong>{atual.onde}</strong></div>
          <Link className="t66-botao" to={atual.caminho}>Abrir esta tela <ArrowRight size={16} aria-hidden="true" /></Link></div>
        <h3>Passo a passo</h3><ol className="t66-passos">{atual.passos.map((passo, numero) => <li key={numero}><span aria-hidden="true">{numero + 1}</span><p>{passo}</p></li>)}</ol>
        <div className="t66-esperado"><h3>O que esperar</h3><p>{atual.resultado}</p></div>
        {atual.dica && <div className="t66-dica"><h3>Para conferir</h3><p>{atual.dica}</p></div>}
        <div className="t66-acoes"><button className={`t66-botao ${lida ? "t66-secundario" : ""}`} type="button" aria-pressed={lida} onClick={alternarLeitura}><Check size={16} aria-hidden="true" />{lida ? "Marcar para reler" : "Concluir leitura desta etapa"}</button></div>
        <p className="t66-leitura">A marcação acompanha sua leitura. Para executar o procedimento, abra a tela e confira os dados do serviço.</p>
        <nav className="t66-sequencia" aria-label="Avançar no tutorial">
          <button className="t66-botao t66-secundario" type="button" disabled={indice === 0} onClick={() => selecionar(guia.etapas[indice - 1].id)}><ArrowLeft size={16} aria-hidden="true" /> Etapa anterior</button>
          <button className="t66-botao" type="button" disabled={indice === guia.etapas.length - 1} onClick={() => selecionar(guia.etapas[indice + 1].id)}>Próxima etapa <ArrowRight size={16} aria-hidden="true" /></button>
        </nav>
        <p className="t66-retorno">Depois de usar a tela, escolha <strong>Ajuda e tutorial</strong> no menu para voltar ao guia.</p>
      </article>
    </div>

    <section className="t66-duvidas" aria-labelledby="t66-duvidas"><h2 id="t66-duvidas">Dúvidas frequentes</h2>
      {guia.duvidas.map(duvida => <details key={duvida.pergunta}><summary>{duvida.pergunta}</summary><p>{duvida.resposta}</p></details>)}
    </section>
  </section>;
}
