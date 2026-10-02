from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D21_PORTAL_CLIENTE_SOLICITACOES_COMPLETO.py"
REVISION = "MEC-SERVICOS-V0.1-D21-PORTAL-CLIENTE-SOLICITACOES-COMPLETO-2026-10-01"
BACKUP_ROOT = "_mec_backups"


def norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_utf8(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(norm(content).rstrip("\n") + "\n", encoding="utf-8", newline="\n")


def find_root() -> Path:
    for root in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        if (root / "backend" / "app" / "principal.py").exists() and (root / "frontend" / "src" / "App.tsx").exists():
            return root
    raise RuntimeError("Não encontrei a raiz do MEC-Servicos. Execute o script na raiz do projeto ou em uma subpasta.")


def npm_cmd() -> str:
    import shutil as _shutil
    for value in (_shutil.which("npm.cmd"), _shutil.which("npm"), r"C:\Program Files\nodejs\npm.cmd"):
        if value and Path(value).exists():
            return value
    raise RuntimeError("npm.cmd não foi encontrado.")


def discover_openapi(root: Path) -> dict:
    sys.path.insert(0, str(root))
    from backend.app.principal import app
    return app.openapi()


def contracts(openapi: dict) -> tuple[str, str, str]:
    paths = openapi.get("paths", {})
    solicitation = None
    technical_path = None
    technical_field = None

    def resolve_ref(schema: object) -> dict:
        if not isinstance(schema, dict):
            return {}

        current = schema
        visited: set[str] = set()

        while isinstance(current, dict) and "$ref" in current:
            ref = current.get("$ref")

            if not isinstance(ref, str) or not ref.startswith("#/"):
                return {}

            if ref in visited:
                return {}

            visited.add(ref)
            node: object = openapi

            for part in ref[2:].split("/"):
                if not isinstance(node, dict):
                    return {}

                node = node.get(
                    part.replace("~1", "/").replace("~0", "~")
                )

            if not isinstance(node, dict):
                return {}

            current = node

        return current if isinstance(current, dict) else {}

    def collect_properties(schema: object) -> dict:
        resolved = resolve_ref(schema)
        properties = dict(resolved.get("properties") or {})

        for branch in resolved.get("allOf", []) or []:
            properties.update(collect_properties(branch))

        return properties

    def is_file_schema(name: str, schema: object) -> bool:
        resolved = resolve_ref(schema)

        if resolved.get("format") == "binary":
            return True

        if (
            resolved.get("type") == "string"
            and resolved.get("contentMediaType")
        ):
            return True

        return name.strip().lower() in {
            "file",
            "arquivo",
            "arquivo_tecnico",
            "arquivo-tecnico",
        }

    for path, item in paths.items():
        if not isinstance(item, dict):
            continue

        if (
            path.endswith("/solicitacoes-servico")
            and item.get("get")
            and item.get("post")
        ):
            names = {
                str(parameter.get("name"))
                for parameter in item["get"].get("parameters", [])
                if isinstance(parameter, dict)
            }

            if "empresa_cliente_id" in names:
                solicitation = path

        if "arquivos-tecnicos" in path and item.get("post"):
            multipart = (
                item["post"]
                .get("requestBody", {})
                .get("content", {})
                .get("multipart/form-data")
            )

            if not multipart:
                continue

            props = collect_properties(multipart.get("schema", {}))

            for name, field_schema in props.items():
                if is_file_schema(str(name), field_schema):
                    technical_path = path
                    technical_field = str(name)
                    break

    if not solicitation:
        raise RuntimeError(
            "OpenAPI nao expos GET+POST /solicitacoes-servico "
            "com filtro empresa_cliente_id."
        )

    if not technical_path or not technical_field:
        raise RuntimeError(
            "OpenAPI nao expos uma rota multipart de Arquivos Tecnicos."
        )

    return solicitation, technical_path, technical_field

def backup(root: Path, files: list[Path]) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = root / BACKUP_ROOT / f"V0_1_D21_PORTAL_CLIENTE_SOLICITACOES_{stamp}"
    for path in files:
        if path.exists():
            dest = target / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    return target


PAGE = r'''import {
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Eye,
  FileText,
  Factory,
  Paperclip,
  Package,
  Plus,
  RefreshCw,
  Ruler,
  Search,
  UploadCloud,
  XCircle,
} from "lucide-react";
import type { ChangeEvent, FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import "./ClientSolicitacoesPage.css";

type Option = { id: number; nome?: string; codigo?: string; familia?: string };
type Solicitacao = {
  id: number;
  empresa_cliente_id: number;
  processo_id: number;
  material_id: number;
  dimensao_x_maxima_mm: string | number;
  dimensao_y_maxima_mm: string | number;
  dimensao_z_maxima_mm: string | number;
  tolerancia_requerida_mm: string | number;
  quantidade: number;
  observacoes?: string | null;
  status?: string | null;
  criada_em?: string | null;
};
type FormState = {
  processo_id: string;
  material_id: string;
  dimensao_x_maxima_mm: string;
  dimensao_y_maxima_mm: string;
  dimensao_z_maxima_mm: string;
  tolerancia_requerida_mm: string;
  quantidade: string;
  observacoes: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const SOLICITACOES_PATH = "__SOLICITACOES_PATH__";
const TECNICO_PATH = "__TECNICO_PATH__";
const TECNICO_FIELD = "__TECNICO_FIELD__";
const INITIAL: FormState = { processo_id: "", material_id: "", dimensao_x_maxima_mm: "", dimensao_y_maxima_mm: "", dimensao_z_maxima_mm: "", tolerancia_requerida_mm: "", quantidade: "1", observacoes: "" };

const url = (path: string) => `${API_BASE}${path}`;
const optionLabel = (x: Option) => [x.codigo, x.nome].filter(Boolean).join(" — ") || `#${x.id}`;
const dateLabel = (x?: string | null) => {
  if (!x) return "—";
  const d = new Date(x);
  return Number.isNaN(d.getTime()) ? x : d.toLocaleDateString("pt-BR");
};
const statusLabel = (x?: string | null) => ({ aberta: "Aberta", publicada: "Publicada", em_cotacao: "Em cotação", contratada: "Contratada", em_producao: "Em produção", concluida: "Concluída", cancelada: "Cancelada" }[String(x ?? "aberta").toLowerCase()] ?? x ?? "Aberta");
const statusClass = (x?: string | null) => {
  const v = String(x ?? "aberta").toLowerCase();
  return v === "cancelada" ? "status-danger" : v === "concluida" ? "status-success" : ["contratada", "em_producao"].includes(v) ? "status-info" : "status-warning";
};

export default function ClientSolicitacoesPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<Solicitacao[]>([]);
  const [processos, setProcessos] = useState<Option[]>([]);
  const [materiais, setMateriais] = useState<Option[]>([]);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [selected, setSelected] = useState<Solicitacao | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const clientId = user?.id ?? 0;

  const load = useCallback(async () => {
    if (!clientId) return;
    setLoading(true); setError("");
    try {
      const [a, b, c] = await Promise.all([
        fetch(url(`${SOLICITACOES_PATH}?empresa_cliente_id=${encodeURIComponent(clientId)}`)),
        fetch(url("/processos-fabricacao")),
        fetch(url("/materiais")),
      ]);
      if (!a.ok) throw new Error("Não foi possível carregar suas solicitações.");
      const data = await a.json();
      setItems(Array.isArray(data) ? data : []);
      setProcessos(b.ok ? await b.json() : []);
      setMateriais(c.ok ? await c.json() : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar os dados.");
    } finally { setLoading(false); }
  }, [clientId]);

  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => [x.id, x.status, x.observacoes].join(" ").toLowerCase().includes(q));
  }, [items, search]);

  const stats = useMemo(() => ({
    total: items.length,
    active: items.filter((x) => !["cancelada", "concluida"].includes(String(x.status ?? "").toLowerCase())).length,
    quote: items.filter((x) => ["publicada", "em_cotacao"].includes(String(x.status ?? "").toLowerCase())).length,
    production: items.filter((x) => ["contratada", "em_producao"].includes(String(x.status ?? "").toLowerCase())).length,
  }), [items]);

  const setField = (name: keyof FormState, value: string) => setForm((old) => ({ ...old, [name]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSuccess("");
    try {
      const response = await fetch(url(SOLICITACOES_PATH), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          empresa_cliente_id: clientId,
          processo_id: Number(form.processo_id),
          material_id: Number(form.material_id),
          dimensao_x_maxima_mm: form.dimensao_x_maxima_mm,
          dimensao_y_maxima_mm: form.dimensao_y_maxima_mm,
          dimensao_z_maxima_mm: form.dimensao_z_maxima_mm,
          tolerancia_requerida_mm: form.tolerancia_requerida_mm,
          quantidade: Number(form.quantidade),
          observacoes: form.observacoes.trim() || null,
        }),
      });
      if (!response.ok) {
        let detail = "Não foi possível criar a solicitação.";
        try { const data = await response.json(); if (typeof data?.detail === "string") detail = data.detail; } catch { /* noop */ }
        throw new Error(detail);
      }
      const created = await response.json() as Solicitacao;
      setItems((old) => [created, ...old]); setForm(INITIAL); setNewOpen(false);
      setSuccess(`Solicitação #${created.id} criada com sucesso.`);
      if (files.length) setSelected(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao criar a solicitação.");
    } finally { setSaving(false); }
  }

  function selectFiles(event: ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(event.target.files ?? []);
    setFiles((old) => [...old, ...incoming.filter((f) => !old.some((x) => x.name === f.name && x.size === f.size))]);
    event.target.value = "";
  }

  async function uploadFiles(item: Solicitacao) {
    if (!files.length) return;
    setError(""); setSuccess("");
    try {
      for (const file of files) {
        const data = new FormData(); data.append(TECNICO_FIELD, file);
        const response = await fetch(url(TECNICO_PATH.replace("{solicitacao_id}", String(item.id))), { method: "POST", body: data });
        if (!response.ok) throw new Error(`Não foi possível anexar ${file.name}.`);
      }
      setSuccess(`Arquivo${files.length > 1 ? "s" : ""} enviado${files.length > 1 ? "s" : ""} para a solicitação #${item.id}.`);
      setFiles([]);
    } catch (e) { setError(e instanceof Error ? e.message : "Falha ao anexar arquivos."); }
  }

  if (!user || user.role !== "cliente") return <Navigate to="/login" replace />;

  return <div className="client-solicitacoes">
    <header className="client-solicitacoes-header">
      <div><div className="eyebrow"><FileText size={15} /> ÁREA DO CLIENTE</div><h1>Minhas Solicitações</h1><p>Crie solicitações técnicas e acompanhe o andamento dos seus serviços.</p></div>
      <div className="header-actions">
        <button className="secondary-button" type="button" onClick={() => void load()} disabled={loading}><RefreshCw size={17} /> Atualizar</button>
        <button className="primary-button" type="button" onClick={() => { setNewOpen(true); setError(""); setSuccess(""); }}><Plus size={18} /> Nova solicitação</button>
      </div>
    </header>

    {error && <div className="feedback feedback-error"><AlertCircle size={18} />{error}</div>}
    {success && <div className="feedback feedback-success"><CheckCircle2 size={18} />{success}</div>}

    <section className="metric-grid">
      <article className="metric-card"><span>Total de solicitações</span><strong>{stats.total}</strong><small>Histórico da empresa</small></article>
      <article className="metric-card"><span>Em andamento</span><strong>{stats.active}</strong><small>Solicitações ativas</small></article>
      <article className="metric-card"><span>Em cotação</span><strong>{stats.quote}</strong><small>Aguardando propostas</small></article>
      <article className="metric-card"><span>Produção</span><strong>{stats.production}</strong><small>Serviços contratados</small></article>
    </section>

    <section className="workspace-card">
      <div className="workspace-toolbar"><div><div className="eyebrow"><Search size={15} /> CONSULTA</div><h2>Solicitações da empresa</h2></div><label className="search-box"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar por número, status ou observação" /></label></div>
      {loading ? <div className="empty-state"><RefreshCw className="spin" size={25} /><strong>Carregando solicitações...</strong></div> : filtered.length === 0 ? <div className="empty-state"><FileText size={32} /><strong>Nenhuma solicitação encontrada</strong><span>Comece criando uma nova solicitação de serviço mecânico.</span><button className="primary-button" type="button" onClick={() => setNewOpen(true)}><Plus size={17} /> Criar solicitação</button></div> : <div className="request-list">
        {filtered.map((item) => <article className="request-row" key={item.id}>
          <div className="request-main"><div className="request-icon"><FileText size={21} /></div><div><strong>Solicitação #{item.id}</strong><span>Criada em {dateLabel(item.criada_em)} · Quantidade {item.quantidade}</span></div></div>
          <div className="request-dimensions"><span><Ruler size={15} /> {item.dimensao_x_maxima_mm} × {item.dimensao_y_maxima_mm} × {item.dimensao_z_maxima_mm} mm</span><span><Package size={15} /> Tol. {item.tolerancia_requerida_mm} mm</span></div>
          <span className={`status-badge ${statusClass(item.status)}`}><Clock3 size={14} /> {statusLabel(item.status)}</span>
          <button className="icon-button" type="button" title="Visualizar" onClick={() => setSelected(item)}><Eye size={18} /></button>
        </article>)}
      </div>}
    </section>

    {newOpen && <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setNewOpen(false); }}><section className="modal-card large-modal">
      <div className="modal-header"><div><div className="eyebrow"><Plus size={15} /> NOVA SOLICITAÇÃO</div><h2>Solicitar serviço mecânico</h2><p>Informe os requisitos técnicos para a cotação.</p></div><button className="icon-button" type="button" onClick={() => setNewOpen(false)}><XCircle size={20} /></button></div>
      <form className="request-form" onSubmit={submit}>
        <div className="form-section"><div className="section-title"><Factory size={18} /> Processo e material</div><div className="form-grid two-columns">
          <label>Processo de fabricação<select value={form.processo_id} onChange={(e) => setField("processo_id", e.target.value)} required><option value="">Selecione o processo</option>{processos.map((x) => <option key={x.id} value={x.id}>{optionLabel(x)}</option>)}</select></label>
          <label>Material<select value={form.material_id} onChange={(e) => setField("material_id", e.target.value)} required><option value="">Selecione o material</option>{materiais.map((x) => <option key={x.id} value={x.id}>{optionLabel(x)}</option>)}</select></label>
        </div></div>
        <div className="form-section"><div className="section-title"><Ruler size={18} /> Dimensões e tolerância</div><div className="form-grid four-columns">
          <label>X máximo (mm)<input type="number" min="0.001" step="0.001" value={form.dimensao_x_maxima_mm} onChange={(e) => setField("dimensao_x_maxima_mm", e.target.value)} required /></label>
          <label>Y máximo (mm)<input type="number" min="0.001" step="0.001" value={form.dimensao_y_maxima_mm} onChange={(e) => setField("dimensao_y_maxima_mm", e.target.value)} required /></label>
          <label>Z máximo (mm)<input type="number" min="0.001" step="0.001" value={form.dimensao_z_maxima_mm} onChange={(e) => setField("dimensao_z_maxima_mm", e.target.value)} required /></label>
          <label>Tolerância (mm)<input type="number" min="0.0001" step="0.0001" value={form.tolerancia_requerida_mm} onChange={(e) => setField("tolerancia_requerida_mm", e.target.value)} required /></label>
        </div></div>
        <div className="form-section"><div className="section-title"><Package size={18} /> Quantidade e observações</div><div className="form-grid two-columns">
          <label>Quantidade<input type="number" min="1" step="1" value={form.quantidade} onChange={(e) => setField("quantidade", e.target.value)} required /></label>
          <label>Observações técnicas<textarea rows={4} value={form.observacoes} onChange={(e) => setField("observacoes", e.target.value)} placeholder="Informações importantes para fabricação, inspeção ou cotação." /></label>
        </div></div>
        <div className="form-section"><div className="section-title"><Paperclip size={18} /> Arquivos técnicos</div><div className="upload-zone" onClick={() => fileInput.current?.click()}><UploadCloud size={30} /><strong>Adicionar arquivos técnicos</strong><span>STEP, STP, IGES, IGS, DXF, DWG ou PDF até 100 MB por arquivo.</span><input ref={fileInput} type="file" multiple accept=".step,.stp,.iges,.igs,.dxf,.dwg,.pdf" hidden onChange={selectFiles} /></div>{files.length > 0 && <div className="file-list">{files.map((f) => <div className="file-chip" key={`${f.name}:${f.size}`}><FileText size={16} /><span>{f.name}</span><small>{(f.size / 1024 / 1024).toFixed(2)} MB</small></div>)}</div>}</div>
        <div className="modal-footer"><button className="secondary-button" type="button" onClick={() => setNewOpen(false)}>Cancelar</button><button className="primary-button" type="submit" disabled={saving}>{saving ? <><RefreshCw className="spin" size={17} /> Criando...</> : <><Plus size={17} /> Criar solicitação</>}</button></div>
      </form>
    </section></div>}

    {selected && <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelected(null); }}><section className="modal-card">
      <div className="modal-header"><div><div className="eyebrow"><FileText size={15} /> DETALHES</div><h2>Solicitação #{selected.id}</h2><p>Resumo técnico e arquivos vinculados.</p></div><button className="icon-button" type="button" onClick={() => setSelected(null)}><XCircle size={20} /></button></div>
      <div className="detail-grid"><div><span>Status</span><strong className={`status-badge ${statusClass(selected.status)}`}>{statusLabel(selected.status)}</strong></div><div><span>Quantidade</span><strong>{selected.quantidade}</strong></div><div><span>Dimensões</span><strong>{selected.dimensao_x_maxima_mm} × {selected.dimensao_y_maxima_mm} × {selected.dimensao_z_maxima_mm} mm</strong></div><div><span>Tolerância</span><strong>{selected.tolerancia_requerida_mm} mm</strong></div><div><span>Criada em</span><strong><CalendarDays size={16} /> {dateLabel(selected.criada_em)}</strong></div></div>
      <div className="detail-observacoes"><span>Observações</span><p>{selected.observacoes || "Nenhuma observação registrada."}</p></div>
      {files.length > 0 && <div className="detail-files"><div className="section-title"><Paperclip size={18} /> Arquivos preparados</div>{files.map((f) => <div className="file-chip" key={`${f.name}:${f.size}`}><FileText size={16} /><span>{f.name}</span></div>)}<button className="primary-button" type="button" onClick={() => void uploadFiles(selected)}><UploadCloud size={17} /> Enviar arquivos para esta solicitação</button></div>}
    </section></div>}
  </div>;
}
'''

CSS = r'''.client-solicitacoes{display:flex;flex-direction:column;gap:20px}.client-solicitacoes-header{display:flex;justify-content:space-between;align-items:flex-start;gap:24px}.client-solicitacoes-header h1{margin:8px 0;font-size:34px}.client-solicitacoes-header p{margin:0;color:#8ea0bb;font-size:16px}.eyebrow{display:flex;align-items:center;gap:8px;color:#4e91ff;font-size:12px;font-weight:800;letter-spacing:1.6px}.header-actions{display:flex;gap:10px;flex-wrap:wrap}.primary-button,.secondary-button,.icon-button{border:1px solid transparent;border-radius:9px;min-height:40px;display:inline-flex;align-items:center;justify-content:center;gap:8px;font:inherit;font-weight:700;cursor:pointer;transition:160ms}.primary-button{padding:0 16px;background:#2864e6;color:#fff}.primary-button:hover{background:#3474f2}.primary-button:disabled,.secondary-button:disabled{opacity:.55;cursor:not-allowed}.secondary-button{padding:0 15px;background:#111923;border-color:#293648;color:#d7e2f3}.secondary-button:hover{border-color:#3e5573}.icon-button{width:40px;padding:0;background:#111923;border-color:#293648;color:#b8c9e0}.feedback{border:1px solid #293648;border-radius:10px;padding:12px 15px;display:flex;align-items:center;gap:10px;font-weight:600}.feedback-error{background:#25171a;border-color:#5d3037;color:#ffb6bd}.feedback-success{background:#14241d;border-color:#2c6147;color:#a6e6c3}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.metric-card,.workspace-card,.modal-card{background:#141c26;border:1px solid #273444;border-radius:12px}.metric-card{padding:20px}.metric-card span,.metric-card small{display:block;color:#8295b1}.metric-card strong{display:block;margin:8px 0 4px;font-size:29px;color:#f4f7fb}.workspace-card{padding:22px}.workspace-toolbar{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:18px}.workspace-toolbar h2{margin:7px 0 0;font-size:22px}.search-box{min-width:340px;display:flex;align-items:center;gap:9px;padding:0 12px;height:42px;background:#0d141d;border:1px solid #2a394c;border-radius:9px;color:#7489a6}.search-box input{width:100%;border:0;outline:0;background:transparent;color:#e7edf7;font:inherit}.request-list{display:flex;flex-direction:column;gap:8px}.request-row{display:grid;grid-template-columns:minmax(260px,1.4fr) minmax(260px,1fr) auto 40px;align-items:center;gap:16px;padding:14px;background:#0f161f;border:1px solid #263344;border-radius:10px}.request-main{display:flex;align-items:center;gap:12px;min-width:0}.request-main strong,.request-main span{display:block}.request-main strong{color:#f0f5fd}.request-main span{margin-top:4px;color:#7f92ad;font-size:13px}.request-icon{width:42px;height:42px;flex:0 0 42px;display:grid;place-items:center;border-radius:10px;background:#15253e;color:#5da0ff}.request-dimensions{display:flex;flex-direction:column;gap:6px;color:#9aabc1;font-size:13px}.request-dimensions span{display:flex;align-items:center;gap:6px}.status-badge{min-height:28px;padding:0 9px;display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:999px;font-size:12px;font-weight:800;white-space:nowrap}.status-warning{background:#302815;color:#f5ca67}.status-info{background:#142b45;color:#73b4ff}.status-success{background:#163326;color:#80d4a3}.status-danger{background:#351b21;color:#ff9ba8}.empty-state{min-height:260px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:9px;color:#7589a6;text-align:center}.empty-state strong{color:#e8eef7}.empty-state .primary-button{margin-top:8px}.modal-backdrop{position:fixed;inset:0;z-index:100;display:grid;place-items:center;padding:24px;background:rgba(2,6,12,.72);backdrop-filter:blur(5px)}.modal-card{width:min(760px,100%);max-height:calc(100vh - 48px);overflow:auto;padding:24px;box-shadow:0 24px 70px rgba(0,0,0,.38)}.large-modal{width:min(980px,100%)}.modal-header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:22px}.modal-header h2{margin:7px 0;font-size:25px}.modal-header p{margin:0;color:#8295b1}.request-form{display:flex;flex-direction:column;gap:20px}.form-section{padding:16px;border:1px solid #273444;border-radius:10px;background:#101720}.section-title{display:flex;align-items:center;gap:8px;color:#dbe6f5;font-weight:800;margin-bottom:14px}.form-grid{display:grid;gap:14px}.two-columns{grid-template-columns:repeat(2,minmax(0,1fr))}.four-columns{grid-template-columns:repeat(4,minmax(0,1fr))}.form-grid label{display:flex;flex-direction:column;gap:7px;color:#bdcce0;font-size:13px;font-weight:700}.form-grid input,.form-grid select,.form-grid textarea{width:100%;box-sizing:border-box;border:1px solid #2c3b4f;border-radius:8px;background:#0b121a;color:#edf3fb;padding:11px 12px;font:inherit;outline:0}.form-grid textarea{resize:vertical}.upload-zone{min-height:145px;border:1px dashed #3b5573;border-radius:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;color:#7590b2;cursor:pointer;background:#0d151e}.upload-zone strong{color:#dfe8f5}.file-list,.detail-files{display:flex;flex-direction:column;gap:8px;margin-top:12px}.file-chip{min-height:38px;padding:0 10px;display:flex;align-items:center;gap:8px;background:#0b121a;border:1px solid #29384b;border-radius:8px;color:#b8c8dc}.file-chip span{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-chip small{color:#70839e}.modal-footer{display:flex;justify-content:flex-end;gap:10px}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.detail-grid>div,.detail-observacoes{padding:14px;background:#101720;border:1px solid #273444;border-radius:9px}.detail-grid span,.detail-observacoes>span{display:block;color:#7589a6;font-size:12px;margin-bottom:6px}.detail-grid strong{color:#e8eef7;display:flex;align-items:center;gap:7px}.detail-observacoes{margin-top:12px}.detail-observacoes p{margin:0;color:#c5d2e4;white-space:pre-wrap;line-height:1.55}.detail-files .primary-button{align-self:flex-start;margin-top:5px}.spin{animation:d21spin .9s linear infinite}@keyframes d21spin{to{transform:rotate(360deg)}}@media(max-width:1100px){.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.request-row{grid-template-columns:1fr auto}.request-dimensions{grid-column:1/2}}@media(max-width:780px){.client-solicitacoes-header,.workspace-toolbar{flex-direction:column;align-items:stretch}.search-box{min-width:0}.metric-grid,.two-columns,.four-columns,.detail-grid{grid-template-columns:1fr}.request-row{grid-template-columns:1fr auto}.request-dimensions{grid-column:1/-1}}
'''

TEST = r'''from backend.app.principal import app


def test_d21_solicitacoes_cliente_contract():
    paths = app.openapi().get("paths", {})
    matches = []
    for path, item in paths.items():
        if not isinstance(item, dict) or not path.endswith("/solicitacoes-servico"):
            continue
        if not item.get("get") or not item.get("post"):
            continue
        names = {str(p.get("name")) for p in item["get"].get("parameters", []) if isinstance(p, dict)}
        if "empresa_cliente_id" in names:
            matches.append(path)
    assert matches


def test_d21_arquivos_tecnicos_multipart_contract():
    paths = app.openapi().get("paths", {})
    matches = []
    for path, item in paths.items():
        if "arquivos-tecnicos" not in path or not isinstance(item, dict):
            continue
        post = item.get("post")
        if not post:
            continue
        multipart = post.get("requestBody", {}).get("content", {}).get("multipart/form-data")
        if multipart:
            props = multipart.get("schema", {}).get("properties", {})
            if any(isinstance(v, dict) and v.get("format") == "binary" for v in props.values()):
                matches.append(path)
    assert matches
'''


def patch_app(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";' not in text:
        marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
        if marker not in text:
            raise RuntimeError("Não encontrei o import de ClientDashboard em App.tsx.")
        text = text.replace(marker, marker + '\nimport ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";', 1)

    pattern = re.compile(r'(<Route\s+path="solicitacoes"\s+element=\{\s*)<ModulePage[\s\S]*?title="Minhas Solicitações"[\s\S]*?description="Crie e acompanhe suas solicitações de serviços mecânicos\."[\s\S]*?/>\s*\}', re.M)
    text, count = pattern.subn(r'\1<ClientSolicitacoesPage />', text, count=1)
    if count != 1:
        raise RuntimeError("Não encontrei a rota cliente /solicitacoes que aponta para ModulePage. Nenhuma alteração de rota foi aplicada.")
    write_utf8(path, text)


def main() -> int:
    root = find_root()
    frontend = root / "frontend"
    src = frontend / "src"
    app = src / "App.tsx"
    page = src / "pages" / "client" / "ClientSolicitacoesPage.tsx"
    css = src / "pages" / "client" / "ClientSolicitacoesPage.css"
    test = root / "tests" / "test_portal_cliente_d21.py"

    print("MEC Serviços — D21 Portal do Cliente / Solicitações Completo")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    openapi = discover_openapi(root)
    solicitation_path, technical_path, technical_field = contracts(openapi)
    backup_dir = backup(root, [app, page, css, test])

    page_text = PAGE.replace("__SOLICITACOES_PATH__", solicitation_path).replace("__TECNICO_PATH__", technical_path).replace("__TECNICO_FIELD__", technical_field)
    patch_app(app)
    write_utf8(page, page_text)
    write_utf8(css, CSS)
    write_utf8(test, TEST)

    npm = npm_cmd()
    package = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    if "lucide-react" not in deps:
        subprocess.run([npm, "install", "lucide-react"], cwd=frontend, check=True)

    build = subprocess.run([npm, "run", "build"], cwd=frontend, text=True, check=False)
    pytest = subprocess.run([sys.executable, "-m", "pytest", str(test), "-q"], cwd=root, text=True, check=False)

    print(f"BACKUP_DIR= {backup_dir}")
    print(f"SOLICITACOES_PATH= {solicitation_path}")
    print(f"ARQUIVOS_TECNICOS_PATH= {technical_path}")
    print(f"ARQUIVOS_TECNICOS_FIELD= {technical_field}")
    print(f"FRONTEND_BUILD= {'OK' if build.returncode == 0 else 'FAILED'}")
    print(f"D21_TEST= {'OK' if pytest.returncode == 0 else 'FAILED'}")
    print("D21_CONFIGURADO= True")

    if build.returncode or pytest.returncode:
        return 40

    print("Próximos comandos:")
    print("cd .\\frontend")
    print("npm run dev")
    print("cd ..")
    print("pytest -q .\\tests --ignore=.\\tests\\mold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
