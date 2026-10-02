import { type ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
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

const ACCEPT = ".step,.stp,.iges,.igs,.dxf,.dwg,.pdf,.zip,.rar";
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
            <span>Formatos aceitos: STEP, STP, IGES, IGS, DXF, DWG, PDF, ZIP e RAR.</span>
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
          Formatos aceitos: STEP, STP, IGES, IGS, DXF, DWG, PDF, ZIP e RAR. Limite de 100 MB por arquivo.
        </span>
      </section>
    </section>
  );
}
