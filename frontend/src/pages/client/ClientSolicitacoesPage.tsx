
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../services/api";
import { useAuth } from "../../auth/AuthContext";
import "./ClientSolicitacoesPage.css";

type Processo = { id: number; codigo?: string; nome?: string };
type Material = { id: number; codigo?: string; nome?: string };

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

type Formulario = {
  empresa_cliente_id: string;
  processo_id: string;
  material_id: string;
  x: string;
  y: string;
  z: string;
  tolerancia: string;
  quantidade: string;
  observacoes: string;
};

const criarFormulario = (empresaId: number): Formulario => ({
  empresa_cliente_id: String(empresaId),
  processo_id: "",
  material_id: "",
  x: "",
  y: "",
  z: "",
  tolerancia: "",
  quantidade: "1",
  observacoes: "",
});

function nome(item: { nome?: string; codigo?: string; id: number }) {
  return item.nome || item.codigo || `Registro #${item.id}`;
}

function mensagemErro(error: unknown): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (
      error as { response?: { data?: { detail?: string } } }
    ).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return "Não foi possível concluir a operação. Verifique se o backend está em execução.";
}

function statusTexto(status: string) {
  if (status === "aberta") return "Aberta";
  if (status === "encerrada") return "Encerrada";
  if (status === "cancelada") return "Cancelada";
  return status;
}

export default function ClientSolicitacoesPage() {
  const { user } = useAuth();
  const empresaId = user?.id ?? 0;

  const [processos, setProcessos] = useState<Processo[]>([]);
  const [materiais, setMateriais] = useState<Material[]>([]);
  const [solicitacoes, setSolicitacoes] = useState<Solicitacao[]>([]);
  const [formulario, setFormulario] = useState(() => criarFormulario(empresaId));
  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const carregar = useCallback(async () => {
    if (!empresaId) {
      setErro("Usuário cliente sem empresa associada.");
      setCarregando(false);
      return;
    }

    setCarregando(true);
    setErro("");

    try {
      const [processosResposta, materiaisResposta, solicitacoesResposta] =
        await Promise.all([
          api.get<Processo[]>("/processos-fabricacao"),
          api.get<Material[]>("/materiais"),
          api.get<Solicitacao[]>("/solicitacoes-servico", {
            params: { empresa_cliente_id: empresaId },
          }),
        ]);

      setProcessos(processosResposta.data);
      setMateriais(materiaisResposta.data);
      setSolicitacoes(solicitacoesResposta.data);
      setFormulario((atual) => ({
        ...atual,
        empresa_cliente_id: String(empresaId),
      }));
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setCarregando(false);
    }
  }, [empresaId]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const indicadores = useMemo(
    () => ({
      total: solicitacoes.length,
      abertas: solicitacoes.filter((item) => item.status === "aberta").length,
      encerradas: solicitacoes.filter((item) => item.status === "encerrada").length,
      canceladas: solicitacoes.filter((item) => item.status === "cancelada").length,
    }),
    [solicitacoes],
  );

  function alterar(campo: keyof Formulario, valor: string) {
    setFormulario((atual) => ({ ...atual, [campo]: valor }));
  }

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSalvando(true);
    setErro("");
    setSucesso("");

    try {
      await api.post("/solicitacoes-servico", {
        empresa_cliente_id: Number(formulario.empresa_cliente_id),
        processo_id: Number(formulario.processo_id),
        material_id: Number(formulario.material_id),
        dimensao_x_maxima_mm: formulario.x,
        dimensao_y_maxima_mm: formulario.y,
        dimensao_z_maxima_mm: formulario.z,
        tolerancia_requerida_mm: formulario.tolerancia,
        quantidade: Number(formulario.quantidade),
        observacoes: formulario.observacoes.trim() || null,
      });

      setFormulario(criarFormulario(empresaId));
      setMostrarFormulario(false);
      setSucesso("Solicitação criada com sucesso.");
      await carregar();
    } catch (error) {
      setErro(mensagemErro(error));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <section className="cliente-solicitacoes">
      <header className="cliente-solicitacoes__header">
        <div>
          <span className="cliente-eyebrow">ÁREA DO CLIENTE</span>
          <h1>Minhas Solicitações</h1>
          <p>
            Crie demandas de fabricação e acompanhe as solicitações enviadas
            aos fornecedores.
          </p>
        </div>
        <button
          className="cliente-primary"
          type="button"
          onClick={() => {
            setMostrarFormulario(true);
            setErro("");
            setSucesso("");
          }}
        >
          + Nova solicitação
        </button>
      </header>

      {sucesso && <div className="cliente-feedback cliente-success">{sucesso}</div>}
      {erro && <div className="cliente-feedback cliente-error">{erro}</div>}

      <div className="cliente-stats">
        <article><span>Total</span><strong>{indicadores.total}</strong></article>
        <article><span>Abertas</span><strong>{indicadores.abertas}</strong></article>
        <article><span>Encerradas</span><strong>{indicadores.encerradas}</strong></article>
        <article><span>Canceladas</span><strong>{indicadores.canceladas}</strong></article>
      </div>

      {mostrarFormulario && (
        <form className="cliente-panel" onSubmit={enviar}>
          <div className="cliente-panel__header">
            <div>
              <span className="cliente-eyebrow">NOVA DEMANDA</span>
              <h2>Dados técnicos</h2>
              <p>Informe os requisitos básicos para solicitar a fabricação.</p>
            </div>
            <button
              className="cliente-secondary"
              type="button"
              onClick={() => setMostrarFormulario(false)}
            >
              Cancelar
            </button>
          </div>

          <div className="cliente-form-grid">
            <label>
              Empresa cliente
              <input
                type="number"
                min="1"
                value={formulario.empresa_cliente_id}
                onChange={(event) =>
                  alterar("empresa_cliente_id", event.target.value)
                }
                required
              />
              <small>
                Na autenticação de demonstração, este ID acompanha o usuário
                cliente.
              </small>
            </label>

            <label>
              Processo de fabricação
              <select
                value={formulario.processo_id}
                onChange={(event) => alterar("processo_id", event.target.value)}
                required
              >
                <option value="">Selecione</option>
                {processos.map((item) => (
                  <option key={item.id} value={item.id}>{nome(item)}</option>
                ))}
              </select>
            </label>

            <label>
              Material
              <select
                value={formulario.material_id}
                onChange={(event) => alterar("material_id", event.target.value)}
                required
              >
                <option value="">Selecione</option>
                {materiais.map((item) => (
                  <option key={item.id} value={item.id}>{nome(item)}</option>
                ))}
              </select>
            </label>

            <label>
              Quantidade
              <input
                type="number"
                min="1"
                value={formulario.quantidade}
                onChange={(event) => alterar("quantidade", event.target.value)}
                required
              />
            </label>

            <label>
              Dimensão X máxima (mm)
              <input
                type="number"
                min="0.001"
                step="0.001"
                value={formulario.x}
                onChange={(event) => alterar("x", event.target.value)}
                required
              />
            </label>

            <label>
              Dimensão Y máxima (mm)
              <input
                type="number"
                min="0.001"
                step="0.001"
                value={formulario.y}
                onChange={(event) => alterar("y", event.target.value)}
                required
              />
            </label>

            <label>
              Dimensão Z máxima (mm)
              <input
                type="number"
                min="0.001"
                step="0.001"
                value={formulario.z}
                onChange={(event) => alterar("z", event.target.value)}
                required
              />
            </label>

            <label>
              Tolerância requerida (mm)
              <input
                type="number"
                min="0.0001"
                step="0.0001"
                value={formulario.tolerancia}
                onChange={(event) => alterar("tolerancia", event.target.value)}
                required
              />
            </label>

            <label className="cliente-full">
              Observações
              <textarea
                rows={5}
                maxLength={5000}
                value={formulario.observacoes}
                onChange={(event) => alterar("observacoes", event.target.value)}
                placeholder="Especificações, acabamento, prazo desejado ou outras informações."
              />
            </label>
          </div>

          <div className="cliente-form-footer">
            <span>
              O vínculo de arquivos técnicos será integrado ao fluxo da
              solicitação na próxima etapa.
            </span>
            <button className="cliente-primary" type="submit" disabled={salvando}>
              {salvando ? "Enviando..." : "Enviar solicitação"}
            </button>
          </div>
        </form>
      )}

      <section className="cliente-panel">
        <div className="cliente-panel__header">
          <div>
            <span className="cliente-eyebrow">HISTÓRICO</span>
            <h2>Solicitações cadastradas</h2>
          </div>
          <button
            className="cliente-secondary"
            type="button"
            onClick={() => void carregar()}
          >
            Atualizar
          </button>
        </div>

        {carregando ? (
          <div className="cliente-empty">Carregando suas solicitações...</div>
        ) : solicitacoes.length === 0 ? (
          <div className="cliente-empty">
            <strong>Nenhuma solicitação cadastrada.</strong>
            <span>Crie sua primeira demanda de fabricação.</span>
            <button
              className="cliente-primary"
              type="button"
              onClick={() => setMostrarFormulario(true)}
            >
              Criar primeira solicitação
            </button>
          </div>
        ) : (
          <div className="cliente-request-list">
            {solicitacoes.map((item) => (
              <article className="cliente-request" key={item.id}>
                <div className="cliente-request__top">
                  <div>
                    <span>Solicitação #{item.id}</span>
                    <h3>
                      {item.dimensao_x_maxima_mm} × {item.dimensao_y_maxima_mm} ×{" "}
                      {item.dimensao_z_maxima_mm} mm
                    </h3>
                    <p>
                      Quantidade {item.quantidade} · Tolerância{" "}
                      {item.tolerancia_requerida_mm} mm
                    </p>
                  </div>
                  <strong className={`cliente-status cliente-status--${item.status}`}>
                    {statusTexto(item.status)}
                  </strong>
                </div>

                <div className="cliente-request__meta">
                  <span>Processo #{item.processo_id}</span>
                  <span>Material #{item.material_id}</span>
                  <span>{new Date(item.criada_em).toLocaleString("pt-BR")}</span>
                </div>

                {item.observacoes && (
                  <p className="cliente-request__notes">{item.observacoes}</p>
                )}

                <div className="cliente-request__footer">
                  <Link to="/cliente/arquivos-tecnicos">
                    Arquivos técnicos
                  </Link>
                  <span>Próxima etapa: cotações.</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
