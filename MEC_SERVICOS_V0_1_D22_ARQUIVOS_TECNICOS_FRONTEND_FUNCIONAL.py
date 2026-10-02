from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

REVISION = "MEC-SERVICOS-V0.1-D22-ARQUIVOS-TECNICOS-FRONTEND-FUNCIONAL-2026-10-02"
BACKUP_ROOT_NAME = "_mec_backups"
REPORT_NAME = "MEC_SERVICOS_V0_1_D22_ARQUIVOS_TECNICOS_FRONTEND_RELATORIO.txt"
JSON_NAME = "MEC_SERVICOS_V0_1_D22_ARQUIVOS_TECNICOS_FRONTEND.json"

APP_REL = Path("frontend/src/App.tsx")
PAGE_REL = Path("frontend/src/pages/client/ClientArquivosTecnicosPage.tsx")
CSS_REL = Path("frontend/src/pages/client/ClientArquivosTecnicosPage.css")
BACKEND_API_REL = Path("backend/app/api/rotas/arquivos_tecnicos.py")
BACKEND_SOL_REL = Path("backend/app/api/rotas/solicitacoes.py")

IMPORT_LINE = 'import ClientArquivosTecnicosPage from "./pages/client/ClientArquivosTecnicosPage";'
OLD_CLIENT_ROUTE = '''<Route
            path="arquivos-tecnicos"
            element={
              <ModulePage
                title="Arquivos Técnicos"
                description="Gerencie os arquivos técnicos das suas solicitações."
              />
            }
          />'''
NEW_CLIENT_ROUTE = '<Route path="arquivos-tecnicos" element={<ClientArquivosTecnicosPage />} />'

PAGE_CONTENT = r'''import { type ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../services/api";
import { useAuth } from "../../auth/AuthContext";
import "./ClientArquivosTecnicosPage.css";

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
  status: string;
  criada_em: string;
};

type ArquivoTecnico = {
  id: number;
  solicitacao_id: number;
  nome_original: string;
  extensao: string;
  content_type: string | null;
  tamanho_bytes: number;
  sha256: string;
  criado_em: string;
  ativo: boolean;
};

const ACCEPT = ".step,.stp,.iges,.igs,.dxf,.dwg,.pdf";
const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024;

function mensagemErro(error: unknown): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (
      error as {
        response?: {
          data?: {
            detail?: unknown;
          };
        };
      }
    ).response;

    const detail = response?.data?.detail;

    if (typeof detail === "string") {
      const mensagens: Record<string, string> = {
        solicitacao_nao_encontrada: "A solicitação selecionada não foi encontrada.",
        empresa_cliente_nao_encontrada: "A empresa cliente não foi encontrada.",
        empresa_nao_e_cliente: "O registro selecionado não é uma empresa cliente.",
        arquivo_tecnico_nao_encontrado: "O arquivo técnico não foi encontrado.",
        arquivo_fisico_nao_encontrado: "O arquivo físico não está disponível.",
        extensao_arquivo_nao_permitida:
          "A extensão deste arquivo não é permitida.",
        arquivo_excede_limite_de_tamanho:
          "O arquivo ultrapassa o limite de 100 MB.",
        nome_arquivo_obrigatorio: "Informe um arquivo.",
        nome_arquivo_muito_longo: "O nome do arquivo é muito longo.",
      };

      return mensagens[detail] ?? detail;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Não foi possível concluir a operação. Verifique se o backend está em execução.";
}

function formatarBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;

  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;

  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;

  return `${(mb / 1024).toFixed(2)} GB`;
}

function formatarData(valor: string): string {
  return new Date(valor).toLocaleString("pt-BR");
}

function resumoSolicitacao(item: Solicitacao): string {
  return `#${item.id} — ${item.dimensao_x_maxima_mm} × ${item.dimensao_y_maxima_mm} × ${item.dimensao_z_maxima_mm} mm`;
}

export default function ClientArquivosTecnicosPage() {
  const { user } = useAuth();
  const empresaId = user?.id ?? 0;

  const [solicitacoes, setSolicitacoes] = useState<Solicitacao[]>([]);
  const [solicitacaoId, setSolicitacaoId] = useState("");
  const [arquivos, setArquivos] = useState<ArquivoTecnico[]>([]);

  const [carregandoSolicitacoes, setCarregandoSolicitacoes] = useState(true);
  const [carregandoArquivos, setCarregandoArquivos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [operandoId, setOperandoId] = useState<number | null>(null);

  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const inputRef = useRef<HTMLInputElement | null>(null);

  const carregarSolicitacoes = useCallback(async () => {
    if (!empresaId) {
      setErro("Usuário cliente sem empresa associada.");
      setCarregandoSolicitacoes(false);
      return;
    }

    setCarregandoSolicitacoes(true);
    setErro("");

    try {
      const resposta = await api.get<Solicitacao[]>("/solicitacoes-servico", {
        params: { empresa_cliente_id: empresaId },
      });

      setSolicitacoes(resposta.data);
      setSolicitacaoId((atual) => {
        if (atual && resposta.data.some((item) => String(item.id) === atual)) {
          return atual;
        }

        return resposta.data.length ? String(resposta.data[0].id) : "";
      });
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setCarregandoSolicitacoes(false);
    }
  }, [empresaId]);

  const carregarArquivos = useCallback(async (id: number) => {
    setCarregandoArquivos(true);
    setErro("");

    try {
      const resposta = await api.get<ArquivoTecnico[]>(
        `/solicitacoes-servico/${id}/arquivos-tecnicos`,
      );
      setArquivos(resposta.data);
    } catch (error) {
      setArquivos([]);
      setErro(mensagemErro(error));
    } finally {
      setCarregandoArquivos(false);
    }
  }, []);

  useEffect(() => {
    void carregarSolicitacoes();
  }, [carregarSolicitacoes]);

  useEffect(() => {
    if (!solicitacaoId) {
      setArquivos([]);
      return;
    }

    void carregarArquivos(Number(solicitacaoId));
  }, [solicitacaoId, carregarArquivos]);

  const solicitacaoSelecionada =
    solicitacoes.find((item) => String(item.id) === solicitacaoId) ?? null;

  function abrirSeletorArquivo() {
    setErro("");
    setSucesso("");

    if (!solicitacaoId) {
      setErro("Selecione uma solicitação antes de enviar um arquivo.");
      return;
    }

    inputRef.current?.click();
  }

  async function enviarArquivo(event: ChangeEvent<HTMLInputElement>) {
    const arquivo = event.target.files?.[0];

    if (!arquivo) {
      return;
    }

    event.target.value = "";
    setErro("");
    setSucesso("");

    if (!solicitacaoId) {
      setErro("Selecione uma solicitação antes de enviar um arquivo.");
      return;
    }

    if (arquivo.size > MAX_FILE_SIZE_BYTES) {
      setErro("O arquivo ultrapassa o limite de 100 MB.");
      return;
    }

    setEnviando(true);

    try {
      const dados = new FormData();
      dados.append("file", arquivo);

      await api.post(
        `/solicitacoes-servico/${solicitacaoId}/arquivos-tecnicos`,
        dados,
      );

      setSucesso(`Arquivo "${arquivo.name}" enviado com sucesso.`);
      await carregarArquivos(Number(solicitacaoId));
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setEnviando(false);
    }
  }

  async function baixarArquivo(arquivo: ArquivoTecnico) {
    setErro("");
    setSucesso("");
    setOperandoId(arquivo.id);

    try {
      const resposta = await api.get(
        `/arquivos-tecnicos/${arquivo.id}/download`,
        { responseType: "blob" },
      );

      const url = URL.createObjectURL(resposta.data);
      const link = document.createElement("a");
      link.href = url;
      link.download = arquivo.nome_original;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setOperandoId(null);
    }
  }

  async function desvincularArquivo(arquivo: ArquivoTecnico) {
    const confirmado = window.confirm(
      `Desvincular o arquivo "${arquivo.nome_original}" desta solicitação?`,
    );

    if (!confirmado) {
      return;
    }

    setErro("");
    setSucesso("");
    setOperandoId(arquivo.id);

    try {
      await api.delete(`/arquivos-tecnicos/${arquivo.id}`);
      setSucesso(`Arquivo "${arquivo.nome_original}" desvinculado.`);
      await carregarArquivos(Number(solicitacaoId));
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setOperandoId(null);
    }
  }

  return (
    <section className="cliente-arquivos">
      <header className="cliente-arquivos__header">
        <div>
          <span className="cliente-arquivos__eyebrow">MÓDULO MEC-SERVIÇOS</span>
          <h1>Arquivos Técnicos</h1>
          <p>
            Gerencie os arquivos técnicos das suas solicitações de fabricação.
          </p>
        </div>

        <button
          className="cliente-arquivos__primary"
          type="button"
          onClick={abrirSeletorArquivo}
          disabled={enviando || !solicitacaoId}
        >
          + Enviar arquivo
        </button>

        <input
          ref={inputRef}
          className="cliente-arquivos__file-input"
          type="file"
          accept={ACCEPT}
          onChange={enviarArquivo}
          disabled={enviando || !solicitacaoId}
        />
      </header>

      {sucesso && (
        <div className="cliente-arquivos__feedback cliente-arquivos__feedback--success">
          {sucesso}
        </div>
      )}

      {erro && (
        <div className="cliente-arquivos__feedback cliente-arquivos__feedback--error">
          {erro}
        </div>
      )}

      <section className="cliente-arquivos__panel cliente-arquivos__selector">
        <div>
          <span className="cliente-arquivos__eyebrow">SOLICITAÇÃO</span>
          <h2>Selecione a demanda</h2>
          <p>Os arquivos abaixo pertencem à solicitação selecionada.</p>
        </div>

        <div className="cliente-arquivos__selector-row">
          <select
            value={solicitacaoId}
            onChange={(event) => {
              setSolicitacaoId(event.target.value);
              setErro("");
              setSucesso("");
            }}
            disabled={carregandoSolicitacoes || !solicitacoes.length}
          >
            <option value="">
              {carregandoSolicitacoes
                ? "Carregando solicitações..."
                : "Selecione uma solicitação"}
            </option>

            {solicitacoes.map((item) => (
              <option key={item.id} value={item.id}>
                {resumoSolicitacao(item)}
              </option>
            ))}
          </select>

          <button
            className="cliente-arquivos__secondary"
            type="button"
            onClick={() => {
              setSucesso("");
              void carregarSolicitacoes();
            }}
            disabled={carregandoSolicitacoes}
          >
            Atualizar
          </button>
        </div>

        {solicitacaoSelecionada && (
          <div className="cliente-arquivos__request-summary">
            <strong>Solicitação #{solicitacaoSelecionada.id}</strong>
            <span>
              Quantidade {solicitacaoSelecionada.quantidade} · Tolerância {solicitacaoSelecionada.tolerancia_requerida_mm} mm
            </span>
            <span>
              Processo #{solicitacaoSelecionada.processo_id} · Material #{solicitacaoSelecionada.material_id}
            </span>
          </div>
        )}
      </section>

      <section className="cliente-arquivos__panel">
        <div className="cliente-arquivos__panel-header">
          <div>
            <span className="cliente-arquivos__eyebrow">ARQUIVOS</span>
            <h2>Documentos técnicos</h2>
          </div>

          {solicitacaoId && (
            <button
              className="cliente-arquivos__secondary"
              type="button"
              onClick={() => void carregarArquivos(Number(solicitacaoId))}
              disabled={carregandoArquivos}
            >
              Atualizar
            </button>
          )}
        </div>

        {!solicitacoes.length && !carregandoSolicitacoes ? (
          <div className="cliente-arquivos__empty">
            <div className="cliente-arquivos__empty-icon">+</div>
            <strong>Nenhuma solicitação cadastrada.</strong>
            <span>Crie uma solicitação antes de adicionar arquivos técnicos.</span>
            <Link
              to="/cliente/solicitacoes"
              className="cliente-arquivos__primary-link"
            >
              Ir para Minhas Solicitações
            </Link>
          </div>
        ) : carregandoArquivos ? (
          <div className="cliente-arquivos__empty">
            <strong>Carregando arquivos...</strong>
          </div>
        ) : !solicitacaoId ? (
          <div className="cliente-arquivos__empty">
            <strong>Selecione uma solicitação.</strong>
            <span>Depois disso, você poderá enviar e gerenciar os arquivos técnicos.</span>
          </div>
        ) : arquivos.length === 0 ? (
          <div className="cliente-arquivos__empty">
            <div className="cliente-arquivos__empty-icon">+</div>
            <strong>Nenhum arquivo técnico cadastrado.</strong>
            <span>Formatos aceitos: STEP, STP, IGES, IGS, DXF, DWG e PDF.</span>
            <button
              className="cliente-arquivos__primary-link"
              type="button"
              onClick={abrirSeletorArquivo}
              disabled={enviando}
            >
              {enviando ? "Enviando..." : "Selecionar primeiro arquivo"}
            </button>
          </div>
        ) : (
          <div className="cliente-arquivos__list">
            {arquivos.map((arquivo) => (
              <article className="cliente-arquivos__item" key={arquivo.id}>
                <div className="cliente-arquivos__item-icon">▤</div>

                <div className="cliente-arquivos__item-main">
                  <strong>{arquivo.nome_original}</strong>
                  <div className="cliente-arquivos__item-meta">
                    <span>{arquivo.extensao.toUpperCase()}</span>
                    <span>{formatarBytes(arquivo.tamanho_bytes)}</span>
                    <span>{formatarData(arquivo.criado_em)}</span>
                  </div>
                  <small title={arquivo.sha256}>
                    SHA-256: {arquivo.sha256.slice(0, 18)}…
                  </small>
                </div>

                <div className="cliente-arquivos__item-actions">
                  <button
                    className="cliente-arquivos__secondary"
                    type="button"
                    onClick={() => void baixarArquivo(arquivo)}
                    disabled={operandoId === arquivo.id}
                  >
                    Baixar
                  </button>

                  <button
                    className="cliente-arquivos__danger"
                    type="button"
                    onClick={() => void desvincularArquivo(arquivo)}
                    disabled={operandoId === arquivo.id}
                  >
                    Desvincular
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="cliente-arquivos__hint">
        <strong>Limite e formatos</strong>
        <span>
          O backend aceita arquivos STEP, STP, IGES, IGS, DXF, DWG e PDF, com limite de 100 MB por arquivo.
        </span>
      </section>
    </section>
  );
}
'''

CSS_CONTENT = r'''.cliente-arquivos {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.cliente-arquivos__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.cliente-arquivos__eyebrow {
  display: block;
  margin-bottom: 8px;
  color: #4d96ff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.cliente-arquivos__header h1 {
  margin: 0;
  color: #f4f7fb;
  font-size: clamp(32px, 4vw, 46px);
  line-height: 1.05;
}

.cliente-arquivos__header p {
  margin: 14px 0 0;
  color: #8fa5c4;
  font-size: 17px;
}

.cliente-arquivos__primary,
.cliente-arquivos__primary-link,
.cliente-arquivos__secondary,
.cliente-arquivos__danger {
  border: 1px solid transparent;
  border-radius: 10px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease, opacity 0.15s ease;
}

.cliente-arquivos__primary:hover,
.cliente-arquivos__primary-link:hover,
.cliente-arquivos__secondary:hover,
.cliente-arquivos__danger:hover {
  transform: translateY(-1px);
}

.cliente-arquivos__primary:disabled,
.cliente-arquivos__primary-link:disabled,
.cliente-arquivos__secondary:disabled,
.cliente-arquivos__danger:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

.cliente-arquivos__primary {
  min-width: 170px;
  padding: 14px 20px;
  background: #286ff0;
  border-color: #286ff0;
  color: #ffffff;
  box-shadow: 0 10px 26px rgba(40, 111, 240, 0.22);
}

.cliente-arquivos__secondary {
  padding: 11px 16px;
  background: #111923;
  border-color: #29384d;
  color: #dce8f7;
}

.cliente-arquivos__danger {
  padding: 11px 16px;
  background: #251619;
  border-color: #63343a;
  color: #ffb7bd;
}

.cliente-arquivos__primary-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  padding: 11px 16px;
  background: #286ff0;
  border-color: #286ff0;
  color: #ffffff;
  text-decoration: none;
}

.cliente-arquivos__file-input {
  display: none;
}

.cliente-arquivos__feedback {
  border-radius: 10px;
  padding: 13px 16px;
  font-weight: 600;
}

.cliente-arquivos__feedback--success {
  border: 1px solid #245b43;
  background: #10241c;
  color: #8be0b5;
}

.cliente-arquivos__feedback--error {
  border: 1px solid #67363c;
  background: #291619;
  color: #ff9fa8;
}

.cliente-arquivos__panel {
  overflow: hidden;
  border: 1px solid #27364a;
  border-radius: 12px;
  background: #131b25;
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.12);
}

.cliente-arquivos__selector {
  padding: 24px;
}

.cliente-arquivos__selector h2,
.cliente-arquivos__panel-header h2 {
  margin: 0;
  color: #f1f5fb;
  font-size: 23px;
}

.cliente-arquivos__selector p {
  margin: 8px 0 0;
  color: #8197b4;
}

.cliente-arquivos__selector-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  margin-top: 20px;
}

.cliente-arquivos select {
  width: 100%;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid #304057;
  border-radius: 9px;
  outline: none;
  background: #0c131c;
  color: #eef4fb;
  font: inherit;
}

.cliente-arquivos select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
}

.cliente-arquivos__request-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-top: 16px;
  padding: 14px 16px;
  border-left: 3px solid #3b82f6;
  background: #0e1722;
  color: #8fa5c4;
}

.cliente-arquivos__request-summary strong {
  color: #eef4fb;
}

.cliente-arquivos__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 24px;
  border-bottom: 1px solid #243247;
}

.cliente-arquivos__list {
  display: flex;
  flex-direction: column;
}

.cliente-arquivos__item {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 18px 24px;
  border-bottom: 1px solid #243247;
}

.cliente-arquivos__item:last-child {
  border-bottom: 0;
}

.cliente-arquivos__item-icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border: 1px solid #2d5ea7;
  border-radius: 10px;
  background: #102344;
  color: #66a4ff;
  font-size: 21px;
}

.cliente-arquivos__item-main {
  min-width: 0;
}

.cliente-arquivos__item-main strong {
  display: block;
  overflow: hidden;
  color: #f2f6fb;
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cliente-arquivos__item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 18px;
  margin-top: 7px;
  color: #7f96b3;
  font-size: 13px;
}

.cliente-arquivos__item-main small {
  display: block;
  margin-top: 6px;
  overflow: hidden;
  color: #5f7693;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cliente-arquivos__item-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.cliente-arquivos__empty {
  display: flex;
  min-height: 260px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 24px;
  text-align: center;
  color: #8096b3;
  flex-direction: column;
}

.cliente-arquivos__empty strong {
  color: #edf3fb;
  font-size: 18px;
}

.cliente-arquivos__empty-icon {
  display: grid;
  width: 52px;
  height: 52px;
  margin-bottom: 4px;
  place-items: center;
  border: 1px solid #2e64b3;
  border-radius: 50%;
  color: #66a4ff;
  font-size: 28px;
}

.cliente-arquivos__hint {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid #27364a;
  border-radius: 10px;
  background: #0f1721;
}

.cliente-arquivos__hint strong {
  color: #eaf1f9;
}

.cliente-arquivos__hint span {
  color: #7f96b3;
  font-size: 14px;
}

@media (max-width: 900px) {
  .cliente-arquivos__header {
    flex-direction: column;
  }

  .cliente-arquivos__primary {
    width: 100%;
  }

  .cliente-arquivos__item {
    grid-template-columns: 42px minmax(0, 1fr);
  }

  .cliente-arquivos__item-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .cliente-arquivos__selector-row {
    grid-template-columns: 1fr;
  }

  .cliente-arquivos__panel-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .cliente-arquivos__item {
    padding: 16px;
  }

  .cliente-arquivos__selector,
  .cliente-arquivos__panel-header {
    padding: 18px;
  }
}
'''


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: Path) -> str:
    return normalize(path.read_text(encoding="utf-8-sig"))


def find_root() -> Path:
    current = Path.cwd().resolve()
    candidates = [current, *current.parents]
    for root in candidates:
        if (
            (root / "backend" / "app" / "principal.py").exists()
            and (root / APP_REL).exists()
        ):
            return root
    raise RuntimeError(
        "Nao encontrei a raiz do MEC-Servicos. Execute o script dentro do projeto."
    )


def backup_file(root: Path, relative: Path, backup_dir: Path) -> bool:
    source = root / relative
    if not source.exists():
        return False
    destination = backup_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def restore_file(root: Path, relative: Path, backup_dir: Path) -> None:
    source = backup_dir / relative
    destination = root / relative
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    elif destination.exists():
        destination.unlink()


def validate_backend_contract(root: Path) -> dict[str, bool]:
    api = read_text(root / BACKEND_API_REL)
    service = read_text(root / "backend/app/services/arquivo_tecnico.py")
    schema = read_text(root / "backend/app/schemas/arquivo_tecnico.py")

    checks = {
        "upload_endpoint": '"/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos"' in api,
        "upload_field_file": "file: UploadFile = File(...)" in api,
        "list_endpoint": '"/solicitacoes-servico/{solicitacao_id}/arquivos-tecnicos"' in api,
        "download_endpoint": '"/arquivos-tecnicos/{arquivo_id}/download"' in api,
        "delete_endpoint": '"/arquivos-tecnicos/{arquivo_id}"' in api and "@roteador.delete" in api,
        "allowed_extensions": all(
            token in service
            for token in ['".step"', '".stp"', '".iges"', '".igs"', '".dxf"', '".dwg"', '".pdf"']
        ),
        "max_100mb": "MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024" in service,
        "sha256": "hashlib.sha256" in service and "sha256" in schema,
        "active_soft_unlink": "item.ativo = False" in service,
    }

    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        raise RuntimeError(
            "Contrato D22 do backend nao confere. Faltantes: " + ", ".join(missing)
        )

    return checks


def validate_solicitacoes_contract(root: Path) -> dict[str, bool]:
    path = root / BACKEND_SOL_REL
    text = read_text(path)
    checks = {
        "prefix": 'prefix="/solicitacoes-servico"' in text,
        "list_route": '@roteador.get(\n    ""' in text or '@roteador.get(""' in text,
        "empresa_cliente_id": "empresa_cliente_id: int" in text,
        "filters_company": "SolicitacaoServico.empresa_cliente_id == empresa_cliente_id" in text,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        raise RuntimeError(
            "Contrato de listagem de solicitacoes nao confere. Faltantes: "
            + ", ".join(missing)
        )
    return checks


def patch_app(root: Path) -> dict[str, bool]:
    target = root / APP_REL
    source = read_text(target)

    if IMPORT_LINE not in source:
        marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
        if marker not in source:
            raise RuntimeError("Nao encontrei o import de ClientDashboard em App.tsx.")
        source = source.replace(marker, marker + "\n" + IMPORT_LINE, 1)
        import_added = True
    else:
        import_added = False

    if NEW_CLIENT_ROUTE in source:
        return {
            "import_added": import_added,
            "client_route_replaced": False,
            "already_patched": True,
        }

    occurrences = source.count(OLD_CLIENT_ROUTE)
    if occurrences != 1:
        raise RuntimeError(
            "A rota cliente de Arquivos Tecnicos nao foi encontrada de forma exata "
            f"(ocorrencias={occurrences}). Nenhuma alteracao sera aplicada."
        )

    source = source.replace(OLD_CLIENT_ROUTE, NEW_CLIENT_ROUTE, 1)
    target.write_text(source.rstrip("\n") + "\n", encoding="utf-8", newline="\n")

    return {
        "import_added": import_added,
        "client_route_replaced": True,
        "already_patched": False,
    }


def validate_frontend(root: Path) -> dict[str, bool]:
    app = read_text(root / APP_REL)
    page = read_text(root / PAGE_REL)
    css = read_text(root / CSS_REL)

    checks = {
        "page_exists": (root / PAGE_REL).exists(),
        "css_exists": (root / CSS_REL).exists(),
        "route_import": IMPORT_LINE in app,
        "client_route": NEW_CLIENT_ROUTE in app,
        "admin_route_untouched": 'path="arquivos-tecnicos"' in app and app.count(NEW_CLIENT_ROUTE) == 1,
        "api_import": 'from "../../services/api"' in page,
        "auth_import": 'from "../../auth/AuthContext"' in page,
        "list_solicitations": 'api.get<Solicitacao[]>("/solicitacoes-servico"' in page,
        "company_filter": 'empresa_cliente_id: empresaId' in page,
        "multipart_file_field": 'dados.append("file", arquivo)' in page,
        "upload_endpoint": '/arquivos-tecnicos`' in page,
        "download_endpoint": '`/arquivos-tecnicos/${arquivo.id}/download`' in page,
        "delete_endpoint": 'api.delete(`/arquivos-tecnicos/${arquivo.id}`)' in page,
        "client_limit": "100 * 1024 * 1024" in page,
        "accepted_extensions": all(ext in page for ext in [".step", ".stp", ".iges", ".igs", ".dxf", ".dwg", ".pdf"]),
        "css_selector": ".cliente-arquivos" in css,
    }

    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        raise RuntimeError(
            "Validacao do frontend D22 falhou. Faltantes: " + ", ".join(missing)
        )
    return checks


def run_npm_build(root: Path) -> tuple[int, str]:
    frontend = root / "frontend"
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm nao encontrado no PATH.")

    result = subprocess.run(
        [npm, "run", "build"],
        cwd=frontend,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def main() -> int:
    print("MEC Servicos - D22 Arquivos Tecnicos Frontend Funcional")
    print(f"REVISION={REVISION}")

    root = find_root()
    print(f"ROOT={root}")

    backup_dir = root / BACKUP_ROOT_NAME / (
        "D22_ARQUIVOS_TECNICOS_FRONTEND_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"BACKUP_DIR={backup_dir}")

    targets = [APP_REL, PAGE_REL, CSS_REL]
    backed_up = []
    for rel in targets:
        if backup_file(root, rel, backup_dir):
            backed_up.append(str(rel))

    report: dict[str, object] = {
        "revision": REVISION,
        "root": str(root),
        "backup_dir": str(backup_dir),
        "backed_up": backed_up,
        "backend_contract": {},
        "solicitacoes_contract": {},
        "frontend_checks": {},
        "patch": {},
        "npm_build_returncode": None,
        "npm_build_output_tail": "",
        "result": "ERRO",
        "restored": False,
    }

    report_txt = root / REPORT_NAME
    report_json = root / JSON_NAME

    try:
        backend_checks = validate_backend_contract(root)
        solicitacoes_checks = validate_solicitacoes_contract(root)
        report["backend_contract"] = backend_checks
        report["solicitacoes_contract"] = solicitacoes_checks
        print(f"BACKEND_CONTRACT_OK=True")
        print(f"SOLICITACOES_CONTRACT_OK=True")

        write_page = root / PAGE_REL
        write_css = root / CSS_REL
        write_page.parent.mkdir(parents=True, exist_ok=True)
        write_css.parent.mkdir(parents=True, exist_ok=True)
        write_page.write_text(PAGE_CONTENT.rstrip() + "\n", encoding="utf-8", newline="\n")
        write_css.write_text(CSS_CONTENT.rstrip() + "\n", encoding="utf-8", newline="\n")

        patch_info = patch_app(root)
        report["patch"] = patch_info
        print(f"PATCH_INFO={patch_info}")

        frontend_checks = validate_frontend(root)
        report["frontend_checks"] = frontend_checks
        print("FRONTEND_VALIDATION_OK=True")

        returncode, build_output = run_npm_build(root)
        report["npm_build_returncode"] = returncode
        report["npm_build_output_tail"] = build_output[-12000:]
        print(f"NPM_BUILD_RETURN_CODE={returncode}")

        if returncode != 0:
            raise RuntimeError("npm run build falhou. Os arquivos serao restaurados.")

        report["result"] = "OK"
        report["restored"] = False

        report_txt.write_text(
            "\n".join(
                [
                    "MEC Servicos — D22 Arquivos Tecnicos Frontend Funcional",
                    f"REVISION={REVISION}",
                    f"ROOT={root}",
                    f"BACKUP_DIR={backup_dir}",
                    f"BACKED_UP={backed_up}",
                    f"PATCH={patch_info}",
                    f"BACKEND_CONTRACT={backend_checks}",
                    f"SOLICITACOES_CONTRACT={solicitacoes_checks}",
                    f"FRONTEND_CHECKS={frontend_checks}",
                    "NPM_BUILD=OK",
                    "BACKEND_CHANGED=False",
                    "RESULTADO=OK",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        print(f"REPORT={report_txt}")
        print(f"JSON={report_json}")
        print("BACKEND_CHANGED=False")
        print("RESULTADO=OK")
        print()
        print("Proximo passo:")
        print("  1. cd .\\frontend")
        print("  2. npm run dev")
        print("  3. abrir /cliente/arquivos-tecnicos")
        return 0

    except Exception as exc:
        report["result"] = "ERRO"
        report["error"] = f"{type(exc).__name__}: {exc}"
        print(f"ERRO={type(exc).__name__}: {exc}")
        print("RESTAURANDO_ARQUIVOS=True")
        for rel in targets:
            restore_file(root, rel, backup_dir)
        report["restored"] = True

        report_txt.write_text(
            "\n".join(
                [
                    "MEC Servicos — D22 Arquivos Tecnicos Frontend Funcional",
                    f"REVISION={REVISION}",
                    f"ROOT={root}",
                    f"BACKUP_DIR={backup_dir}",
                    f"ERROR={type(exc).__name__}: {exc}",
                    "RESTORED=True",
                    "RESULTADO=ERRO",
                ]
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        report_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"REPORT={report_txt}")
        print(f"JSON={report_json}")
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
