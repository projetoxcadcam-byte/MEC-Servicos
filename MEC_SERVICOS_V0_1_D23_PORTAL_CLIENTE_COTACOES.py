r"""MEC-Serviços D23 — Portal do Cliente / Cotações Recebidas.

Na raiz do projeto, com a .venv ativa, execute:
    python .\MEC_SERVICOS_V0_1_D23_PORTAL_CLIENTE_COTACOES.py

Confere o OpenAPI local sem iniciar o servidor nem criar registros no banco.
Aplica a tela de cotações somente à rota /cliente/cotacoes. Faz backup dos
fontes e do dist anterior, executa a suíte MEC e npm run build. Em caso de
falha, restaura os arquivos alterados. Não instala dependências nem altera
o backend, o login, os arquivos técnicos ou as referências do Git.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


REVISION = "MEC-SERVICOS-V0.1-D23-PORTAL-CLIENTE-COTACOES-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D23_PORTAL_CLIENTE_COTACOES_RELATORIO"
APP_REL = Path("frontend/src/App.tsx")
PAGE_REL = Path("frontend/src/pages/client/ClientCotacoesPage.tsx")
CSS_REL = Path("frontend/src/pages/client/ClientCotacoesPage.css")
HELPER_REL = Path("frontend/src/pages/client/cotacoesCliente.ts")
DIST_REL = Path("frontend/dist")
ALVOS = (APP_REL, PAGE_REL, CSS_REL, HELPER_REL)
IMPORT_LINE = 'import ClientCotacoesPage from "./pages/client/ClientCotacoesPage";'
NEW_ROUTE = '<Route path="cotacoes" element={<ClientCotacoesPage />} />'


PAGE_CONTENT = r'''import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CheckCircle2, Clock3, FileText, RefreshCw, Search, XCircle } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { api } from "../../services/api";
import {
  formatarInstanteCotacao, formatarValorCotacao, instanteUtc, mensagemErroCotacao,
  ordenarCotacoes, podeDecidirCotacao, rotuloStatusCotacao, statusCotacao, vencimentoCotacao,
  type AcaoCotacao, type CotacaoCliente, type OrdenacaoCotacoes, type SolicitacaoCliente,
} from "./cotacoesCliente";
import "./ClientCotacoesPage.css";

type GrupoCotacoes = {
  empresaId: number;
  solicitacaoId: number;
  itens: CotacaoCliente[];
  fornecedores: Record<number, string>;
};
type ModalCotacao = {
  empresaId: number;
  solicitacaoId: number;
  cotacaoId: number;
  acao: AcaoCotacao | "detalhes";
};
type EmpresaFornecedor = { id: number; razao_social: string };

function resumoSolicitacao(item: SolicitacaoCliente): string {
  return `Solicitação #${item.id} · ${item.quantidade} un. · ${item.dimensao_x_maxima_mm} × ${item.dimensao_y_maxima_mm} × ${item.dimensao_z_maxima_mm} mm`;
}

export default function ClientCotacoesPage() {
  const { user } = useAuth();
  const empresaId = user?.id ?? 0;
  const [parametros, setParametros] = useSearchParams();
  const [solicitacoes, setSolicitacoes] = useState<SolicitacaoCliente[]>([]);
  const [grupo, setGrupo] = useState<GrupoCotacoes | null>(null);
  const [carregandoSolicitacoes, setCarregandoSolicitacoes] = useState(true);
  const [carregandoCotacoes, setCarregandoCotacoes] = useState(false);
  const [erroSolicitacoes, setErroSolicitacoes] = useState("");
  const [erroCotacoes, setErroCotacoes] = useState("");
  const [erroDecisao, setErroDecisao] = useState("");
  const [avisoFornecedores, setAvisoFornecedores] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [revisaoSolicitacoes, setRevisaoSolicitacoes] = useState(0);
  const [revisaoCotacoes, setRevisaoCotacoes] = useState(0);
  const [ordenacao, setOrdenacao] = useState<OrdenacaoCotacoes>("valor");
  const [filtro, setFiltro] = useState("todas");
  const [busca, setBusca] = useState("");
  const [agora, setAgora] = useState(Date.now);
  const [modal, setModal] = useState<ModalCotacao | null>(null);
  const [decidindo, setDecidindo] = useState(false);
  const dialogoRef = useRef<HTMLDialogElement | null>(null);
  const envioRef = useRef(false);
  const montadaRef = useRef(true);

  const minhasSolicitacoes = useMemo(() => solicitacoes.filter((item) => item.empresa_cliente_id === empresaId), [solicitacoes, empresaId]);
  const idPedido = Number(parametros.get("solicitacao"));
  const solicitacaoId = minhasSolicitacoes.some((item) => item.id === idPedido) ? idPedido : minhasSolicitacoes[0]?.id ?? 0;
  const solicitacao = minhasSolicitacoes.find((item) => item.id === solicitacaoId);
  const visaoRef = useRef({ empresaId, solicitacaoId });
  visaoRef.current = { empresaId, solicitacaoId };
  const grupoAtual = grupo?.empresaId === empresaId && grupo.solicitacaoId === solicitacaoId ? grupo : null;
  const cotacoes = grupoAtual?.itens ?? [];
  const fornecedores = grupoAtual?.fornecedores ?? {};
  const possuiAceita = cotacoes.some((item) => item.status === "aceita");
  const modalAtual = modal?.empresaId === empresaId && modal.solicitacaoId === solicitacaoId ? modal : null;
  const cotacaoModal = modalAtual ? cotacoes.find((item) => item.id === modalAtual.cotacaoId) : undefined;
  const nomeFornecedor = (id: number) => fornecedores[id] ?? `Fornecedor #${id}`;

  useEffect(() => {
    montadaRef.current = true;
    const intervalo = window.setInterval(() => setAgora(Date.now()), 30_000);
    return () => { montadaRef.current = false; window.clearInterval(intervalo); };
  }, []);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setCarregandoSolicitacoes(true);
    setErroSolicitacoes("");
    if (!empresaId) {
      setSolicitacoes([]);
      setErroSolicitacoes("Entre com uma conta cliente associada a uma empresa.");
      setCarregandoSolicitacoes(false);
      return () => controlador.abort();
    }
    void (async () => {
      try {
        const resposta = await api.get<SolicitacaoCliente[]>("/solicitacoes-servico", {
          params: { empresa_cliente_id: empresaId }, signal: controlador.signal,
        });
        if (!Array.isArray(resposta.data)) throw new Error("Resposta de solicitações inválida.");
        if (vigente) setSolicitacoes(resposta.data.filter((item) => item.empresa_cliente_id === empresaId).sort((a, b) => b.id - a.id));
      } catch (erro) {
        if (vigente && !controlador.signal.aborted) { setErroSolicitacoes(mensagemErroCotacao(erro)); setSolicitacoes([]); }
      } finally {
        if (vigente) setCarregandoSolicitacoes(false);
      }
    })();
    return () => { vigente = false; controlador.abort(); };
  }, [empresaId, revisaoSolicitacoes]);

  useEffect(() => {
    const controlador = new AbortController();
    let vigente = true;
    setErroCotacoes("");
    setAvisoFornecedores("");
    setGrupo(null);
    if (!empresaId || !solicitacaoId) { setCarregandoCotacoes(false); return () => controlador.abort(); }
    setCarregandoCotacoes(true);
    void (async () => {
      try {
        const resposta = await api.get<CotacaoCliente[]>(`/solicitacoes-servico/${solicitacaoId}/cotacoes`, { signal: controlador.signal });
        if (!Array.isArray(resposta.data) || resposta.data.some((item) => item.solicitacao_id !== solicitacaoId)) throw new Error("Resposta de cotações inválida.");
        if (!vigente) return;
        const itens = resposta.data;
        const nomes: Record<number, string> = {};
        setGrupo({ empresaId, solicitacaoId, itens, fornecedores: nomes });
        setCarregandoCotacoes(false);
        const ids = [...new Set(itens.map((item) => item.empresa_fornecedora_id))];
        let falhas = 0;
        for (let inicio = 0; inicio < ids.length && vigente; inicio += 8) {
          const resultados = await Promise.allSettled(ids.slice(inicio, inicio + 8).map(async (id) => {
            const empresa = await api.get<EmpresaFornecedor>(`/empresas/${id}`, { signal: controlador.signal });
            if (empresa.data.id !== id || !empresa.data.razao_social) throw new Error("Fornecedor indisponível.");
            return empresa.data;
          }));
          if (!vigente) return;
          for (const resultado of resultados) {
            if (resultado.status === "fulfilled") nomes[resultado.value.id] = resultado.value.razao_social;
            else falhas += 1;
          }
          setGrupo({ empresaId, solicitacaoId, itens, fornecedores: { ...nomes } });
        }
        if (vigente && falhas) setAvisoFornecedores("Alguns nomes de fornecedores estão indisponíveis. As propostas continuam identificadas pelo número da empresa.");
      } catch (erro) {
        if (vigente && !controlador.signal.aborted) setErroCotacoes(mensagemErroCotacao(erro));
      } finally {
        if (vigente) setCarregandoCotacoes(false);
      }
    })();
    return () => { vigente = false; controlador.abort(); };
  }, [empresaId, solicitacaoId, revisaoCotacoes]);

  useEffect(() => {
    setModal(null); setSucesso(""); setErroDecisao(""); setFiltro("todas"); setBusca("");
  }, [empresaId, solicitacaoId]);

  useEffect(() => {
    const dialogo = dialogoRef.current;
    if (!dialogo) return;
    if (modalAtual && cotacaoModal && !dialogo.open) dialogo.showModal();
    else if ((!modalAtual || !cotacaoModal) && dialogo.open) dialogo.close();
  }, [modalAtual, cotacaoModal]);

  const disponiveis = cotacoes.filter((item) => podeDecidirCotacao(item, possuiAceita, agora));
  const menorValor = disponiveis.length ? Math.min(...disponiveis.map((item) => Number(item.valor_total))) : null;
  const menorPrazo = disponiveis.length ? Math.min(...disponiveis.map((item) => item.prazo_dias)) : null;
  const textoBusca = busca.trim().toLocaleLowerCase("pt-BR");
  const exibidas = ordenarCotacoes(cotacoes, ordenacao).filter((item) =>
    (filtro === "todas" || statusCotacao(item, agora) === filtro)
    && (!textoBusca || `${item.id} ${item.empresa_fornecedora_id} ${nomeFornecedor(item.empresa_fornecedora_id)}`.toLocaleLowerCase("pt-BR").includes(textoBusca)),
  );

  function abrirModal(item: CotacaoCliente, acao: ModalCotacao["acao"]) {
    if (envioRef.current || carregandoCotacoes) return;
    if (acao !== "detalhes" && !podeDecidirCotacao(item, possuiAceita, Date.now())) {
      setErroDecisao("Esta proposta não está disponível para decisão. Atualize as cotações.");
      return;
    }
    setErroDecisao("");
    setModal({ empresaId, solicitacaoId, cotacaoId: item.id, acao });
  }

  async function confirmarDecisao() {
    if (!modalAtual || !cotacaoModal || modalAtual.acao === "detalhes" || envioRef.current) return;
    const item = cotacaoModal;
    const acao = modalAtual.acao;
    const contexto = { empresaId, solicitacaoId };
    if (!podeDecidirCotacao(item, possuiAceita, Date.now())) {
      setModal(null); setErroDecisao("Esta proposta não está disponível para decisão. Atualize as cotações.");
      setRevisaoCotacoes((valor) => valor + 1);
      return;
    }
    envioRef.current = true;
    setDecidindo(true); setErroDecisao(""); setSucesso("");
    const mesmaVisao = () => montadaRef.current && visaoRef.current.empresaId === contexto.empresaId && visaoRef.current.solicitacaoId === contexto.solicitacaoId;
    try {
      const resposta = await api.post<CotacaoCliente>(`/solicitacoes-servico/${contexto.solicitacaoId}/cotacoes/${item.id}/${acao}`, { empresa_cliente_id: contexto.empresaId });
      if (resposta.data.id !== item.id || resposta.data.solicitacao_id !== contexto.solicitacaoId || resposta.data.status !== (acao === "aceitar" ? "aceita" : "recusada")) throw new Error("Não foi possível confirmar o resultado.");
      if (mesmaVisao()) {
        setModal(null);
        setSucesso(acao === "aceitar" ? `Cotação #${item.id} aceita. As demais propostas pendentes desta solicitação foram recusadas.` : `Cotação #${item.id} recusada.`);
        setRevisaoCotacoes((valor) => valor + 1);
      }
    } catch (erro) {
      if (mesmaVisao()) {
        setModal(null); setErroDecisao(mensagemErroCotacao(erro));
        setRevisaoCotacoes((valor) => valor + 1);
      }
    } finally {
      envioRef.current = false;
      if (montadaRef.current) setDecidindo(false);
    }
  }

  function atualizar() {
    if (envioRef.current) return;
    setErroDecisao(""); setSucesso("");
    setRevisaoSolicitacoes((valor) => valor + 1);
    setRevisaoCotacoes((valor) => valor + 1);
  }

  return <div className="c23-page">
    <header className="c23-header">
      <div><div className="c23-eyebrow"><FileText size={16} /> PORTAL DO CLIENTE</div><h1>Cotações Recebidas</h1><p>Compare as propostas e escolha a mais adequada ao seu serviço.</p></div>
      <button type="button" className="c23-button" onClick={atualizar} disabled={carregandoSolicitacoes || carregandoCotacoes || decidindo}><RefreshCw size={16} className={carregandoSolicitacoes || carregandoCotacoes ? "c23-spin" : ""} /> Atualizar</button>
    </header>

    {erroSolicitacoes && <div className="c23-alert c23-alert-error" role="alert">{erroSolicitacoes}</div>}
    {erroDecisao && <div className="c23-alert c23-alert-error" role="alert">{erroDecisao}</div>}
    {sucesso && <div className="c23-alert c23-alert-success" role="status"><CheckCircle2 size={18} /> {sucesso}</div>}

    <section className="c23-panel c23-selector" aria-label="Selecionar solicitação">
      <label htmlFor="c23-solicitacao">Solicitação de serviço</label>
      <div className="c23-selector-row"><select id="c23-solicitacao" value={solicitacaoId || ""} disabled={carregandoSolicitacoes || decidindo || !minhasSolicitacoes.length} onChange={(evento) => {
        const proximos = new URLSearchParams(parametros); proximos.set("solicitacao", evento.target.value); setParametros(proximos);
      }}>
        {!minhasSolicitacoes.length && <option value="">{carregandoSolicitacoes ? "Carregando solicitações..." : "Nenhuma solicitação disponível"}</option>}
        {minhasSolicitacoes.map((item) => <option key={item.id} value={item.id}>{resumoSolicitacao(item)}</option>)}
      </select><Link className="c23-link" to="/cliente/solicitacoes">Minhas solicitações</Link><Link className="c23-link" to="/cliente/arquivos-tecnicos">Arquivos técnicos</Link></div>
      {solicitacao?.observacoes && <p className="c23-request-note">{solicitacao.observacoes}</p>}
    </section>

    <div className="c23-metrics" aria-label="Resumo das propostas da solicitação">
      <article><span>Propostas recebidas</span><strong>{carregandoCotacoes ? "—" : cotacoes.length}</strong><small>Nesta solicitação</small></article>
      <article><span>Aguardando decisão</span><strong>{carregandoCotacoes ? "—" : disponiveis.length}</strong><small>Dentro da validade</small></article>
      <article><span>Menor valor disponível</span><strong className="c23-metric-value">{menorValor === null ? "—" : formatarValorCotacao(menorValor)}</strong><small>Entre as propostas válidas</small></article>
      <article><span>Menor prazo disponível</span><strong>{menorPrazo === null ? "—" : `${menorPrazo} dias`}</strong><small>Entre as propostas válidas</small></article>
    </div>

    {possuiAceita && <div className="c23-alert c23-alert-success"><CheckCircle2 size={18} /> Esta solicitação já possui uma cotação aceita. Consulte os detalhes abaixo.</div>}
    {avisoFornecedores && <div className="c23-alert" role="status">{avisoFornecedores}</div>}

    <section className="c23-panel" aria-label="Comparação de cotações" aria-busy={carregandoCotacoes}>
      <div className="c23-toolbar"><div><h2>Propostas dos fornecedores</h2><p>Valores totais, prazo de execução e validade da oferta.</p></div>
        <div className="c23-filters"><label className="c23-search"><Search size={16} /><span className="c23-sr">Buscar fornecedor ou cotação</span><input type="search" value={busca} placeholder="Fornecedor ou cotação" onChange={(evento) => setBusca(evento.target.value)} /></label>
          <label><span className="c23-sr">Filtrar por situação</span><select value={filtro} onChange={(evento) => setFiltro(evento.target.value)}><option value="todas">Todas as situações</option><option value="enviada">Aguardando decisão</option><option value="aceita">Aceitas</option><option value="recusada">Recusadas</option><option value="expirada">Expiradas</option><option value="cancelada">Canceladas</option></select></label>
          <label><span className="c23-sr">Ordenar propostas</span><select value={ordenacao} onChange={(evento) => setOrdenacao(evento.target.value as OrdenacaoCotacoes)}><option value="valor">Menor valor</option><option value="prazo">Menor prazo</option><option value="recentes">Mais recentes</option></select></label>
        </div>
      </div>
      {erroCotacoes ? <div className="c23-empty" role="alert"><XCircle size={32} /><strong>Não foi possível carregar as propostas</strong><p>{erroCotacoes}</p><button type="button" className="c23-button" onClick={() => setRevisaoCotacoes((valor) => valor + 1)}>Tentar novamente</button></div>
        : carregandoSolicitacoes || carregandoCotacoes ? <div className="c23-empty" role="status"><RefreshCw className="c23-spin" size={30} /><strong>Carregando cotações...</strong></div>
          : !minhasSolicitacoes.length ? <div className="c23-empty"><FileText size={32} /><strong>Comece por uma solicitação</strong><p>Cadastre seu serviço para receber propostas dos fornecedores.</p><Link className="c23-button c23-primary" to="/cliente/solicitacoes">Ir para solicitações</Link></div>
            : !cotacoes.length ? <div className="c23-empty"><Clock3 size={32} /><strong>Nenhuma cotação recebida nesta solicitação</strong><p>As propostas aparecerão aqui quando os fornecedores enviarem suas cotações.</p></div>
              : !exibidas.length ? <div className="c23-empty"><Search size={32} /><strong>Nenhuma proposta corresponde aos filtros</strong><button type="button" className="c23-button" onClick={() => { setFiltro("todas"); setBusca(""); }}>Limpar filtros</button></div>
                : <div className="c23-table-scroll"><table><caption className="c23-sr">Cotações da solicitação #{solicitacaoId}</caption><thead><tr><th scope="col">Fornecedor / cotação</th><th scope="col">Valor total</th><th scope="col">Prazo</th><th scope="col">Validade até</th><th scope="col">Situação</th><th scope="col">Ações</th></tr></thead><tbody>
                  {exibidas.map((item) => {
                    const status = statusCotacao(item, agora);
                    const podeDecidir = podeDecidirCotacao(item, possuiAceita, agora) && !decidindo;
                    return <tr key={item.id}><td><strong>{nomeFornecedor(item.empresa_fornecedora_id)}</strong><small>Cotação #{item.id} · Empresa #{item.empresa_fornecedora_id}</small></td>
                      <td><strong className="c23-price">{formatarValorCotacao(item.valor_total)}</strong>{podeDecidir && Number(item.valor_total) === menorValor && <small className="c23-highlight">Menor valor</small>}</td>
                      <td><strong>{item.prazo_dias} dias</strong>{podeDecidir && item.prazo_dias === menorPrazo && <small className="c23-highlight">Menor prazo</small>}</td>
                      <td>{formatarInstanteCotacao(vencimentoCotacao(item))}</td><td><span className={`c23-badge c23-status-${status === "aceita" ? "success" : status === "enviada" ? "pending" : "closed"}`}>{rotuloStatusCotacao(status)}</span></td>
                      <td><div className="c23-actions"><button type="button" className="c23-button c23-small" onClick={() => abrirModal(item, "detalhes")} disabled={decidindo}>Detalhes</button>
                        {podeDecidir && <><button type="button" className="c23-button c23-primary c23-small" onClick={() => abrirModal(item, "aceitar")}>Aceitar</button><button type="button" className="c23-button c23-small c23-danger-text" onClick={() => abrirModal(item, "recusar")}>Recusar</button></>}
                      </div></td></tr>;
                  })}
                </tbody></table></div>}
    </section>

    <p className="c23-footnote">As propostas são comparadas dentro da mesma solicitação. Uma oferta expirada não pode ser aceita ou recusada.</p>

    <dialog ref={dialogoRef} className="c23-dialog" aria-labelledby="c23-dialog-title" onCancel={(evento) => { if (envioRef.current) evento.preventDefault(); else setModal(null); }} onClose={() => { if (!envioRef.current) setModal(null); }}>
      {modalAtual && cotacaoModal && <><div className="c23-dialog-head"><div><div className="c23-eyebrow">COTAÇÃO #{cotacaoModal.id}</div><h2 id="c23-dialog-title">{modalAtual.acao === "detalhes" ? "Detalhes da proposta" : modalAtual.acao === "aceitar" ? "Aceitar esta cotação?" : "Recusar esta cotação?"}</h2></div><button type="button" className="c23-icon-button" aria-label="Fechar" disabled={decidindo} onClick={() => setModal(null)}><XCircle size={22} /></button></div>
        <div className="c23-detail-grid"><div><span>Fornecedor</span><strong>{nomeFornecedor(cotacaoModal.empresa_fornecedora_id)}</strong></div><div><span>Solicitação</span><strong>#{cotacaoModal.solicitacao_id}</strong></div><div><span>Valor total</span><strong>{formatarValorCotacao(cotacaoModal.valor_total)}</strong></div><div><span>Prazo de execução</span><strong>{cotacaoModal.prazo_dias} dias</strong></div><div><span>Validade até</span><strong>{formatarInstanteCotacao(vencimentoCotacao(cotacaoModal))}</strong></div><div><span>Situação</span><strong>{rotuloStatusCotacao(statusCotacao(cotacaoModal, agora))}</strong></div></div>
        {modalAtual.acao === "detalhes" ? <><div className="c23-observacoes"><span>Observações do fornecedor</span><p>{cotacaoModal.observacoes?.trim() || "Nenhuma observação informada."}</p></div><p className="c23-dates">Enviada em {formatarInstanteCotacao(instanteUtc(cotacaoModal.criada_em))}{cotacaoModal.encerrada_em ? ` · Encerrada em ${formatarInstanteCotacao(instanteUtc(cotacaoModal.encerrada_em))}` : ""}</p></>
          : <div className={`c23-alert ${modalAtual.acao === "aceitar" ? "" : "c23-alert-warning"}`}>{modalAtual.acao === "aceitar" ? "Ao confirmar, esta será a cotação escolhida e as demais propostas pendentes desta solicitação serão recusadas automaticamente." : "Ao confirmar, esta proposta será recusada. As outras cotações da solicitação continuarão disponíveis."}</div>}
        <div className="c23-dialog-actions"><button type="button" className="c23-button" disabled={decidindo} onClick={() => setModal(null)}>{modalAtual.acao === "detalhes" ? "Fechar" : "Voltar"}</button>
          {modalAtual.acao === "detalhes" ? podeDecidirCotacao(cotacaoModal, possuiAceita, agora) && <><button type="button" className="c23-button c23-danger-text" onClick={() => abrirModal(cotacaoModal, "recusar")}>Recusar</button><button type="button" className="c23-button c23-primary" onClick={() => abrirModal(cotacaoModal, "aceitar")}>Aceitar</button></>
            : <button type="button" className={`c23-button ${modalAtual.acao === "aceitar" ? "c23-primary" : "c23-danger"}`} disabled={decidindo || !podeDecidirCotacao(cotacaoModal, possuiAceita, agora)} onClick={() => { void confirmarDecisao(); }}>{decidindo ? <><RefreshCw className="c23-spin" size={16} /> Registrando...</> : modalAtual.acao === "aceitar" ? "Confirmar aceite" : "Confirmar recusa"}</button>}
        </div></>}
    </dialog>
  </div>;
}
'''

CSS_CONTENT = r'''.c23-page { display: flex; flex-direction: column; gap: 20px; color: #e8eef7; }
.c23-page *, .c23-dialog * { box-sizing: border-box; }
.c23-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.c23-eyebrow { display: flex; align-items: center; gap: 8px; color: #69a8ff; font-size: 11px; letter-spacing: 1.5px; font-weight: 800; }
.c23-header h1 { margin: 8px 0; font-size: clamp(26px, 3vw, 34px); letter-spacing: -.7px; }
.c23-header p, .c23-toolbar p { margin: 0; color: #8da1bd; line-height: 1.5; }
.c23-button, .c23-link { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 40px; padding: 9px 14px; border: 1px solid #33465e; border-radius: 8px; background: #162233; color: #e4edf9; font: inherit; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; }
.c23-button:hover:not(:disabled), .c23-link:hover { border-color: #659bed; background: #1c2c43; }
.c23-button:disabled { opacity: .5; cursor: default; }
.c23-primary { background: #2563eb; border-color: #3475f8; color: white; }
.c23-primary:hover:not(:disabled) { background: #3475f8; }
.c23-danger { background: #a72f45; border-color: #cc4f66; color: white; }
.c23-danger-text { color: #ffabba; }
.c23-small { min-height: 34px; padding: 6px 10px; font-size: 12px; }
.c23-panel { border: 1px solid #28384d; border-radius: 12px; background: #111b29; overflow: hidden; }
.c23-selector { padding: 20px; }
.c23-selector > label { display: block; color: #c5d3e6; font-size: 13px; font-weight: 700; margin-bottom: 9px; }
.c23-selector-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.c23-selector-row > select { flex: 1; min-width: 240px; }
.c23-page select, .c23-page input { min-height: 40px; border: 1px solid #33465e; border-radius: 8px; background: #0c1521; color: #e7eef9; font: inherit; font-size: 13px; padding: 9px 11px; }
.c23-page select:disabled { opacity: .65; }
.c23-request-note { margin: 14px 0 0; max-height: 90px; overflow: auto; color: #98adc8; font-size: 13px; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
.c23-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.c23-metrics article { display: flex; flex-direction: column; gap: 9px; padding: 20px; border: 1px solid #28384d; border-radius: 12px; background: linear-gradient(135deg, #152237, #101a29); }
.c23-metrics span { color: #99aecb; font-size: 12px; font-weight: 600; }
.c23-metrics strong { color: #f1f6ff; font-size: 27px; line-height: 1.2; }
.c23-metrics .c23-metric-value { font-size: clamp(17px, 1.7vw, 24px); overflow-wrap: anywhere; }
.c23-metrics small { color: #6e85a5; font-size: 11px; }
.c23-alert { display: flex; align-items: center; gap: 9px; padding: 14px 16px; border: 1px solid #375273; border-radius: 9px; background: #14243a; color: #b9d6ff; font-size: 13px; line-height: 1.6; }
.c23-alert svg { flex: 0 0 auto; }
.c23-alert-error { background: #321c29; border-color: #75374a; color: #ffb4c0; }
.c23-alert-success { background: #122e27; border-color: #285b47; color: #a1dfbe; }
.c23-alert-warning { background: #302817; border-color: #66562e; color: #f2d18b; }
.c23-toolbar { padding: 20px; display: flex; justify-content: space-between; gap: 18px; align-items: center; flex-wrap: wrap; border-bottom: 1px solid #28384d; }
.c23-toolbar h2 { margin: 0 0 5px; font-size: 18px; }
.c23-toolbar p { font-size: 12px; }
.c23-filters { display: flex; gap: 9px; flex-wrap: wrap; }
.c23-search { display: flex; align-items: center; gap: 7px; padding: 0 10px; border: 1px solid #33465e; border-radius: 8px; background: #0c1521; color: #7c93b2; }
.c23-search input { border: 0; background: transparent; width: 175px; padding-left: 0; }
.c23-table-scroll { overflow-x: auto; }
.c23-page table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
.c23-page th { background: #0e1826; color: #8298b6; font-size: 11px; font-weight: 700; padding: 13px 16px; white-space: nowrap; }
.c23-page td { border-top: 1px solid #253449; padding: 18px 16px; vertical-align: middle; line-height: 1.5; }
.c23-page td:first-child { min-width: 220px; max-width: 310px; overflow-wrap: anywhere; }
.c23-page td > strong { display: block; color: #e7eefb; }
.c23-page td > small { display: block; margin-top: 5px; color: #7d93b1; font-size: 11px; }
.c23-page td .c23-highlight { color: #81b2ff; }
.c23-page td .c23-price { white-space: nowrap; font-size: 15px; }
.c23-page tbody tr:hover { background: #142238; }
.c23-badge { display: inline-flex; padding: 5px 9px; border-radius: 99px; font-size: 11px; font-weight: 800; white-space: nowrap; }
.c23-status-success { background: #183c2d; color: #9ce0b7; }
.c23-status-pending { background: #373018; color: #efd48b; }
.c23-status-closed { background: #283143; color: #a7b4c9; }
.c23-actions { display: flex; flex-wrap: nowrap; gap: 6px; }
.c23-empty { display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 245px; padding: 35px 20px; gap: 12px; text-align: center; color: #8298b8; }
.c23-empty > svg { color: #5d97ef; }
.c23-empty strong { color: #dce8fa; font-size: 17px; }
.c23-empty p { max-width: 550px; margin: 0; line-height: 1.6; font-size: 13px; }
.c23-footnote { margin: 0; color: #7890af; font-size: 12px; line-height: 1.6; }
.c23-dialog { width: min(660px, calc(100vw - 32px)); max-height: calc(100vh - 40px); overflow-y: auto; border: 1px solid #3b5372; border-radius: 14px; background: #111d2d; color: #e8eef7; padding: 24px; box-shadow: 0 24px 90px #0008; font: inherit; }
.c23-dialog::backdrop { background: #020712bd; backdrop-filter: blur(4px); }
.c23-dialog-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; margin-bottom: 20px; }
.c23-dialog-head h2 { margin: 7px 0 0; font-size: 24px; }
.c23-icon-button { padding: 4px; border: 0; background: transparent; color: #8ba3c2; cursor: pointer; }
.c23-icon-button:disabled { opacity: .5; cursor: default; }
.c23-detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; margin-bottom: 16px; }
.c23-detail-grid > div, .c23-observacoes { padding: 13px; border: 1px solid #293d55; border-radius: 8px; background: #0e1724; overflow-wrap: anywhere; }
.c23-detail-grid span, .c23-observacoes > span { display: block; margin-bottom: 7px; color: #8198b7; font-size: 11px; }
.c23-detail-grid strong { font-size: 14px; }
.c23-observacoes p { margin: 0; color: #bfd0e8; white-space: pre-wrap; line-height: 1.6; font-size: 13px; }
.c23-dates { color: #8298b8; font-size: 11px; line-height: 1.6; }
.c23-dialog-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 9px; margin-top: 20px; }
.c23-button:focus-visible, .c23-link:focus-visible, .c23-icon-button:focus-visible, .c23-page input:focus-visible, .c23-page select:focus-visible { outline: 2px solid #8dbaff; outline-offset: 3px; }
.c23-sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.c23-spin { animation: c23spin 1s linear infinite; }
@keyframes c23spin { to { transform: rotate(360deg); } }
@media (max-width: 1150px) { .c23-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .c23-toolbar { align-items: flex-start; flex-direction: column; } }
@media (max-width: 680px) { .c23-header { flex-direction: column; } .c23-selector-row, .c23-filters { align-items: stretch; flex-direction: column; width: 100%; } .c23-selector-row > select { min-width: 0; width: 100%; } .c23-filters select, .c23-search input { width: 100%; } .c23-search { width: 100%; } .c23-detail-grid { grid-template-columns: 1fr; } .c23-dialog { padding: 18px; } .c23-dialog-actions { flex-direction: column-reverse; } }
@media (prefers-reduced-motion: reduce) { .c23-spin { animation: none; } .c23-dialog::backdrop { backdrop-filter: none; } }
'''

HELPER_CONTENT = r'''export type SolicitacaoCliente = {
  id: number;
  empresa_cliente_id: number;
  quantidade: number;
  dimensao_x_maxima_mm: string | number;
  dimensao_y_maxima_mm: string | number;
  dimensao_z_maxima_mm: string | number;
  observacoes?: string | null;
  status: string;
};

export type CotacaoCliente = {
  id: number;
  solicitacao_id: number;
  empresa_fornecedora_id: number;
  valor_total: string | number;
  prazo_dias: number;
  validade_dias: number;
  observacoes: string | null;
  status: string;
  criada_em: string;
  encerrada_em: string | null;
  decidida_por_empresa_id: number | null;
};

export type OrdenacaoCotacoes = "valor" | "prazo" | "recentes";
export type AcaoCotacao = "aceitar" | "recusar";

export function instanteUtc(valor: string | null): number | null {
  if (!valor) return null;
  // O backend considera UTC as datas sem indicação de fuso.
  const texto = valor.trim().replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  const comFuso = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(texto);
  const instante = Date.parse(comFuso ? texto : `${texto}Z`);
  return Number.isFinite(instante) ? instante : null;
}

export function vencimentoCotacao(cotacao: CotacaoCliente): number | null {
  const criada = instanteUtc(cotacao.criada_em);
  if (criada === null || !Number.isInteger(cotacao.validade_dias) || cotacao.validade_dias <= 0) return null;
  return criada + cotacao.validade_dias * 86_400_000;
}

export function statusCotacao(cotacao: CotacaoCliente, agora = Date.now()): string {
  const vencimento = vencimentoCotacao(cotacao);
  if (cotacao.status === "enviada" && vencimento !== null && agora >= vencimento) return "expirada";
  return cotacao.status;
}

export function podeDecidirCotacao(cotacao: CotacaoCliente, possuiAceita: boolean, agora = Date.now()): boolean {
  const vencimento = vencimentoCotacao(cotacao);
  return !possuiAceita && cotacao.status === "enviada" && vencimento !== null && agora < vencimento;
}

export function rotuloStatusCotacao(status: string): string {
  const rotulos: Record<string, string> = {
    enviada: "Aguardando decisão", aceita: "Aceita", recusada: "Recusada", expirada: "Expirada", cancelada: "Cancelada",
  };
  return rotulos[status] ?? "Situação indisponível";
}

export function formatarValorCotacao(valor: string | number): string {
  const numero = Number(valor);
  return Number.isFinite(numero) && numero > 0
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numero)
    : "Valor indisponível";
}

export function formatarInstanteCotacao(instante: number | null): string {
  return instante === null ? "Data indisponível" : new Date(instante).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function ordenarCotacoes(itens: CotacaoCliente[], ordenacao: OrdenacaoCotacoes): CotacaoCliente[] {
  return [...itens].sort((a, b) => {
    const diferenca = ordenacao === "prazo" ? a.prazo_dias - b.prazo_dias
      : ordenacao === "recentes" ? (instanteUtc(b.criada_em) ?? 0) - (instanteUtc(a.criada_em) ?? 0)
      : Number(a.valor_total) - Number(b.valor_total);
    return diferenca || a.id - b.id;
  });
}

export function mensagemErroCotacao(erro: unknown): string {
  if (typeof erro === "object" && erro !== null && "response" in erro) {
    const resposta = (erro as { response?: { data?: { detail?: unknown } } }).response;
    const detalhe = resposta?.data?.detail;
    const mensagens: Record<string, string> = {
      solicitacao_nao_encontrada: "A solicitação não foi encontrada. Atualize a lista.",
      cotacao_nao_encontrada: "A cotação não foi encontrada. Atualize as propostas.",
      empresa_nao_e_cliente_da_solicitacao: "Esta solicitação pertence a outro cliente.",
      cotacao_expirada: "A validade desta cotação terminou. Atualize as propostas.",
      cotacao_nao_esta_pendente: "Esta cotação já foi encerrada. Atualize as propostas.",
      solicitacao_ja_possui_cotacao_aceita: "Esta solicitação já possui uma cotação aceita.",
      empresa_cliente_nao_encontrada: "A empresa cliente não foi encontrada.",
      empresa_nao_e_cliente: "A empresa selecionada não é uma empresa cliente.",
    };
    if (typeof detalhe === "string") return mensagens[detalhe] ?? "Não foi possível concluir a operação. Atualize as cotações e tente novamente.";
    if (Array.isArray(detalhe)) return "Os dados enviados não foram aceitos. Atualize a página e tente novamente.";
  }
  return "Não foi possível confirmar a operação. Verifique a conexão e atualize as cotações antes de tentar novamente.";
}
'''

VALIDACAO_CONTRATO = r'''
from backend.app.principal import app

documento = app.openapi()
paths = documento.get("paths", {})

def schema(valor):
    vistos = set()
    while "$ref" in valor:
        referencia = valor["$ref"]
        if referencia in vistos or not referencia.startswith("#/"):
            raise RuntimeError("Referência OpenAPI inesperada.")
        vistos.add(referencia)
        valor = documento
        for parte in referencia[2:].split("/"):
            valor = valor[parte.replace("~1", "/").replace("~0", "~")]
    return valor

def operacao(caminho, metodo):
    valor = paths.get(caminho, {}).get(metodo)
    if not isinstance(valor, dict):
        raise RuntimeError(f"Contrato ausente: {metodo.upper()} {caminho}")
    return valor

def resposta(op):
    return schema(op["responses"]["200"]["content"]["application/json"]["schema"])

def campos(valor, esperados, nome):
    propriedades = schema(valor).get("properties", {})
    ausentes = set(esperados) - set(propriedades)
    if ausentes:
        raise RuntimeError(nome + ": faltam " + ", ".join(sorted(ausentes)))

base = "/api/v1/solicitacoes-servico"
solicitacoes = operacao(base, "get")
parametros = {p.get("name"): p for p in solicitacoes.get("parameters", [])}
if parametros.get("empresa_cliente_id", {}).get("in") != "query":
    raise RuntimeError("Listagem de solicitações sem filtro por empresa cliente.")
lista = resposta(solicitacoes)
if lista.get("type") != "array":
    raise RuntimeError("A listagem de solicitações não retorna uma lista.")
campos(lista["items"], ("id", "empresa_cliente_id", "quantidade", "dimensao_x_maxima_mm", "dimensao_y_maxima_mm", "dimensao_z_maxima_mm", "status"), "Solicitação")

cotacoes = operacao(base + "/{solicitacao_id}/cotacoes", "get")
lista = resposta(cotacoes)
if lista.get("type") != "array":
    raise RuntimeError("A listagem de cotações não retorna uma lista.")
esperados = ("id", "solicitacao_id", "empresa_fornecedora_id", "valor_total", "prazo_dias", "validade_dias", "observacoes", "status", "criada_em", "encerrada_em", "decidida_por_empresa_id")
campos(lista["items"], esperados, "Cotação")
for acao in ("aceitar", "recusar"):
    op = operacao(base + "/{solicitacao_id}/cotacoes/{cotacao_id}/" + acao, "post")
    dados = schema(op["requestBody"]["content"]["application/json"]["schema"])
    if set(dados.get("required", [])) != {"empresa_cliente_id"}:
        raise RuntimeError("O corpo da decisão difere do contrato D7.")
    campos(dados, ("empresa_cliente_id",), "Decisão")
    campos(resposta(op), esperados, "Resposta da decisão")
fornecedor = operacao("/api/v1/empresas/{empresa_id}", "get")
campos(resposta(fornecedor), ("id", "razao_social"), "Fornecedor")
print("LISTAGEM_SOLICITACOES_CLIENTE_OK=True")
print("LISTAGEM_COTACOES_POR_SOLICITACAO_OK=True")
print("ACEITE_RECUSA_EMPRESA_CLIENTE_OK=True")
print("NOMES_FORNECEDORES_OK=True")
print("CONTRATO_COTACOES_OK=True")
'''


def ler_texto(caminho: Path) -> str:
    return caminho.read_bytes().decode("utf-8-sig")


def localizar_raiz() -> Path:
    raiz = Path.cwd().resolve()
    obrigatorios = (
        "backend/app/principal.py", "backend/app/api/rotas/cotacoes.py",
        "frontend/src/App.tsx", "frontend/package.json", "frontend/src/auth/AuthContext.tsx",
        "frontend/src/services/api.ts", "frontend/src/pages/client/ClientArquivosTecnicosPage.tsx",
        "tests/test_cotacoes.py",
    )
    if not all((raiz / nome).is_file() for nome in obrigatorios):
        raise RuntimeError("Execute este script na raiz do projeto MEC-Servicos já atualizado até o D22.")
    return raiz


def fim_tag(texto: str, inicio: int) -> int:
    """Encontra o fim da tag Route sem confundir JSX dentro de element={...}."""
    pos = inicio
    nivel = 0
    aspas = ""
    while pos < len(texto):
        caractere = texto[pos]
        if aspas:
            if caractere == "\\":
                pos += 2
                continue
            if caractere == aspas:
                aspas = ""
        elif caractere in "\"'`":
            aspas = caractere
        elif texto.startswith("/*", pos):
            fim = texto.find("*/", pos + 2)
            if fim < 0:
                break
            pos = fim + 2
            continue
        elif texto.startswith("//", pos):
            fim = texto.find("\n", pos + 2)
            if fim < 0:
                break
            pos = fim + 1
            continue
        elif caractere == "{":
            nivel += 1
        elif caractere == "}":
            nivel -= 1
            if nivel < 0:
                break
        elif caractere == ">" and nivel == 0:
            return pos + 1
        pos += 1
    raise RuntimeError("Uma tag Route de App.tsx não pôde ser interpretada com segurança.")


def localizar_rotas(texto: str) -> list[dict]:
    rotas = []
    pilha = []
    pos = 0
    token = re.compile(r"</?Route\b")
    padrao_path = re.compile(r'''\bpath\s*=\s*(?:(["'])(.*?)\1|\{\s*(["'])(.*?)\3\s*\})''', re.S)
    while correspondencia := token.search(texto, pos):
        inicio = correspondencia.start()
        fim = fim_tag(texto, inicio)
        abertura = texto[inicio:fim]
        if abertura.startswith("</"):
            if not pilha:
                raise RuntimeError("Fechamento Route sem abertura correspondente em App.tsx.")
            pilha.pop()["fim"] = fim
        else:
            caminho = padrao_path.search(abertura)
            registro = {
                "inicio": inicio, "fim_abertura": fim, "fim": fim,
                "path": (caminho.group(2) if caminho.group(1) else caminho.group(4)) if caminho else None,
                "auto_fecha": abertura.rstrip().endswith("/>"),
            }
            rotas.append(registro)
            if not registro["auto_fecha"]:
                pilha.append(registro)
        pos = fim
    if pilha:
        raise RuntimeError("Há um grupo Route sem fechamento em App.tsx.")
    return rotas


def atualizar_app(texto: str) -> str:
    rotas = localizar_rotas(texto)
    grupos = [item for item in rotas if item["path"] == "/cliente" and not item["auto_fecha"]]
    if len(grupos) != 1:
        raise RuntimeError("Não encontrei um único grupo /cliente em App.tsx. Nenhum fonte foi alterado.")
    grupo = grupos[0]
    candidatas = [item for item in rotas if grupo["fim_abertura"] <= item["inicio"] < item["fim"] <= grupo["fim"] and item["path"] == "cotacoes"]
    if len(candidatas) != 1 or not candidatas[0]["auto_fecha"]:
        raise RuntimeError("Não encontrei uma única rota cliente cotacoes sem subrotas. Nenhum fonte foi alterado.")
    rota = candidatas[0]
    anterior = texto[rota["inicio"]:rota["fim"]]
    if re.search(r"<ClientCotacoesPage\b", anterior):
        atualizado = texto
    elif re.search(r"<ModulePage\b", anterior):
        atualizado = texto[:rota["inicio"]] + NEW_ROUTE + texto[rota["fim"]:]
    else:
        raise RuntimeError("A rota cliente de cotações já usa uma tela diferente. Ela foi preservada.")
    existente = re.search(r'''import\s+ClientCotacoesPage\s+from\s*["']\./pages/client/ClientCotacoesPage["']\s*;?''', atualizado)
    if not existente:
        if "./pages/client/ClientCotacoesPage" in atualizado:
            raise RuntimeError("O import existente da tela de cotações usa outro formato. Nenhum fonte foi alterado.")
        quebra = "\r\n" if "\r\n" in atualizado else "\n"
        atualizado = IMPORT_LINE + quebra + atualizado
    return atualizado


def codificar(texto: str, original: bytes | None) -> bytes:
    marcador = b"\xef\xbb\xbf" if original and original.startswith(b"\xef\xbb\xbf") else b""
    return marcador + texto.encode("utf-8")


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d23_", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def executar_etapa(nome: str, comando: list[str], pasta: Path, relatorio: dict) -> None:
    print(f"Executando {nome}...", flush=True)
    ambiente = os.environ.copy()
    ambiente["PYTHONIOENCODING"] = "utf-8"
    processo = subprocess.run(
        comando, cwd=pasta, env=ambiente, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=600,
    )
    saida = (processo.stdout or "") + (processo.stderr or "")
    relatorio["etapas"].append({"nome": nome, "returncode": processo.returncode, "saida": saida})
    if saida:
        print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
    print(f"{nome.upper().replace(' ', '_')}_RETURN_CODE={processo.returncode}", flush=True)
    if processo.returncode:
        raise RuntimeError(f"A etapa {nome} falhou. Confira a saída e o relatório.")


def salvar_relatorios(raiz: Path, relatorio: dict) -> None:
    json_path = raiz / (RELATORIO_NOME + ".json")
    txt_path = raiz / (RELATORIO_NOME + ".txt")
    linhas = [
        "MEC-Serviços D23 — Portal do Cliente / Cotações Recebidas",
        f"REVISION={REVISION}", f"ROOT={raiz}", f"RESULTADO={relatorio['resultado']}",
        f"BACKUP_DIR={relatorio.get('backup_dir', '')}",
    ]
    if relatorio.get("erro"):
        linhas.append("ERRO=" + relatorio["erro"])
    if "restaurado" in relatorio:
        linhas.append(f"RESTAURADO={relatorio['restaurado']}")
    for etapa in relatorio["etapas"]:
        linhas.extend(["", etapa["nome"], f"RETURN_CODE={etapa['returncode']}", etapa["saida"].rstrip()])
    gravar_atomico(json_path, (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    gravar_atomico(txt_path, ("\n".join(linhas).rstrip() + "\n").encode("utf-8"))
    print(f"RELATORIO={txt_path}", flush=True)
    print(f"JSON={json_path}", flush=True)


def main() -> int:
    print("MEC-Serviços D23 — Portal do Cliente / Cotações Recebidas", flush=True)
    print(f"REVISION={REVISION}", flush=True)
    raiz = None
    backup = None
    originais: dict[Path, bytes | None] = {}
    alterados: list[Path] = []
    dist_alteravel = False
    dist_existia = False
    relatorio_salvo = False
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapas": []}
    try:
        raiz = localizar_raiz()
        print(f"ROOT={raiz}", flush=True)
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm não encontrado no PATH. Nenhum fonte foi alterado.")
        pacote = json.loads(ler_texto(raiz / "frontend/package.json"))
        dependencias = {**pacote.get("dependencies", {}), **pacote.get("devDependencies", {})}
        if not pacote.get("scripts", {}).get("build") or not all(nome in dependencias for nome in ("react", "react-router-dom", "lucide-react", "axios")):
            raise RuntimeError("As dependências e o comando de build do frontend não correspondem ao D22.")
        if not re.search(r'''\bbaseURL\s*:\s*["']/api/v1/?["']''', ler_texto(raiz / "frontend/src/services/api.ts")):
            raise RuntimeError("O endereço base do cliente API difere de /api/v1. Nenhum fonte foi alterado.")
        for alvo in (*ALVOS, DIST_REL):
            caminho = raiz / alvo
            if caminho.is_symlink() or not caminho.resolve().is_relative_to(raiz):
                raise RuntimeError("Um destino da atualização aponta para fora do projeto: " + str(alvo))
            if alvo == DIST_REL and caminho.exists() and not caminho.is_dir():
                raise RuntimeError("frontend/dist existe, mas não é uma pasta. Nenhum fonte foi alterado.")
        originais = {alvo: (raiz / alvo).read_bytes() if (raiz / alvo).exists() else None for alvo in ALVOS}
        app_atualizado = atualizar_app(originais[APP_REL].decode("utf-8-sig"))
        conteudos = {APP_REL: app_atualizado, PAGE_REL: PAGE_CONTENT, CSS_REL: CSS_CONTENT, HELPER_REL: HELPER_CONTENT}
        planejados = {alvo: codificar(texto, originais[alvo]) for alvo, texto in conteudos.items()}
        executar_etapa("validacao contrato", [sys.executable, "-c", VALIDACAO_CONTRATO], raiz, relatorio)
        carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = raiz / "_mec_backups" / ("D23_COTACOES_CLIENTE_" + carimbo)
        backup.mkdir(parents=True, exist_ok=False)
        relatorio["backup_dir"] = str(backup)
        for alvo, original in originais.items():
            if original is not None:
                destino = backup / alvo
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(original)
        dist = raiz / DIST_REL
        dist_existia = dist.is_dir()
        if dist_existia:
            shutil.copytree(dist, backup / DIST_REL)
        print(f"BACKUP_DIR={backup}", flush=True)
        for alvo, dados in planejados.items():
            if dados != originais[alvo]:
                alterados.append(alvo)
                gravar_atomico(raiz / alvo, dados)
        relatorio["arquivos_atualizados"] = [str(alvo) for alvo in alterados]
        print("COTACOES_TELA_E_ROTA_CLIENTE_OK=True", flush=True)
        print("PYTEST_COMANDO=python -m pytest tests -q --ignore=tests/mold", flush=True)
        executar_etapa("pytest", [sys.executable, "-m", "pytest", "tests", "-q", "--ignore=tests/mold"], raiz, relatorio)
        dist_alteravel = True
        executar_etapa("npm build", [npm, "run", "build"], raiz / "frontend", relatorio)
        relatorio["resultado"] = "OK"
        salvar_relatorios(raiz, relatorio)
        relatorio_salvo = True
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["resultado"] = "ERRO"
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ERRO=" + relatorio["erro"], flush=True)
        falhas = []
        if raiz is not None and backup is not None:
            for alvo in reversed(alterados):
                try:
                    original = originais[alvo]
                    if original is None:
                        (raiz / alvo).unlink(missing_ok=True)
                    else:
                        gravar_atomico(raiz / alvo, original)
                except Exception as falha:
                    falhas.append(str(alvo) + ": " + str(falha))
            if dist_alteravel:
                try:
                    dist = raiz / DIST_REL
                    if dist.exists():
                        shutil.rmtree(dist)
                    if dist_existia:
                        shutil.copytree(backup / DIST_REL, dist)
                except Exception as falha:
                    falhas.append("frontend/dist: " + str(falha))
            if alterados or dist_alteravel:
                relatorio["restaurado"] = not falhas
                print(f"RESTAURADO={not falhas}", flush=True)
            if falhas:
                relatorio["falhas_restauracao"] = falhas
                for falha in falhas:
                    print("ERRO_RESTAURACAO=" + falha, flush=True)
    if raiz is not None and not relatorio_salvo:
        try:
            salvar_relatorios(raiz, relatorio)
        except Exception as erro:
            print(f"ERRO_RELATORIO={erro}", flush=True)
            relatorio["resultado"] = "ERRO"
    print("RESULTADO=" + relatorio["resultado"], flush=True)
    if relatorio["resultado"] != "OK":
        return 1
    print("Atualize /cliente/cotacoes com Ctrl+F5.", flush=True)
    print("Confira a seleção da solicitação, os detalhes e a comparação das propostas.", flush=True)
    print("Teste as decisões em cotações de teste, observando o aviso de confirmação.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
