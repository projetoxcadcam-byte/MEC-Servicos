from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

REVISION = "MEC-SERVICOS-V0.1-D18-PORTAL-CLIENTE-SOLICITACOES-2026-10-01"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def backup(root: Path, backup_root: Path, relative: str) -> bool:
    source = root / relative
    if not source.exists():
        return False
    target = backup_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


BACKEND_SOLICITACOES = r"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.solicitacao import (
    FornecedorCompativelLeitura,
    SolicitacaoServicoCriacao,
    SolicitacaoServicoLeitura,
)
from backend.app.services.compatibilidade import (
    EmpresaNaoCliente,
    MaterialSolicitacaoNaoEncontrado,
    ProcessoSolicitacaoNaoEncontrado,
    ServicoCompatibilidade,
    SolicitacaoNaoEncontrada,
)

roteador = APIRouter(
    prefix="/solicitacoes-servico",
    tags=["solicitações de serviço"],
)
SessaoBanco = Annotated[Session, Depends(obter_banco)]


@roteador.post(
    "",
    response_model=SolicitacaoServicoLeitura,
    status_code=status.HTTP_201_CREATED,
)
def criar_solicitacao(
    dados: SolicitacaoServicoCriacao,
    banco: SessaoBanco,
) -> SolicitacaoServicoLeitura:
    try:
        solicitacao = ServicoCompatibilidade(banco).criar_solicitacao(dados)
    except EmpresaNaoCliente as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="empresa_nao_e_cliente",
        ) from exc
    except SolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa_cliente_nao_encontrada",
        ) from exc
    except ProcessoSolicitacaoNaoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="processo_nao_encontrado",
        ) from exc
    except MaterialSolicitacaoNaoEncontrado as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="material_nao_encontrado",
        ) from exc

    return SolicitacaoServicoLeitura.model_validate(solicitacao)


@roteador.get(
    "",
    response_model=list[SolicitacaoServicoLeitura],
)
def listar_solicitacoes(
    empresa_cliente_id: int,
    banco: SessaoBanco,
) -> list[SolicitacaoServicoLeitura]:
    empresa = banco.get(Empresa, empresa_cliente_id)

    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa_cliente_nao_encontrada",
        )

    if empresa.tipo_empresa != "cliente":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="empresa_nao_e_cliente",
        )

    itens = banco.scalars(
        select(SolicitacaoServico)
        .where(SolicitacaoServico.empresa_cliente_id == empresa_cliente_id)
        .order_by(
            SolicitacaoServico.criada_em.desc(),
            SolicitacaoServico.id.desc(),
        )
    ).all()

    return [
        SolicitacaoServicoLeitura.model_validate(item)
        for item in itens
    ]


@roteador.get(
    "/{solicitacao_id}",
    response_model=SolicitacaoServicoLeitura,
)
def obter_solicitacao(
    solicitacao_id: int,
    banco: SessaoBanco,
) -> SolicitacaoServicoLeitura:
    try:
        solicitacao = ServicoCompatibilidade(banco).obter_solicitacao(
            solicitacao_id
        )
    except SolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc

    return SolicitacaoServicoLeitura.model_validate(solicitacao)


@roteador.get(
    "/{solicitacao_id}/fornecedores-compativeis",
    response_model=list[FornecedorCompativelLeitura],
)
def listar_fornecedores_compativeis(
    solicitacao_id: int,
    banco: SessaoBanco,
) -> list[FornecedorCompativelLeitura]:
    try:
        itens = ServicoCompatibilidade(banco).listar_fornecedores_compativeis(
            solicitacao_id
        )
    except SolicitacaoNaoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        ) from exc

    solicitacao = banco.get(SolicitacaoServico, solicitacao_id)

    if solicitacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="solicitacao_nao_encontrada",
        )

    return [
        FornecedorCompativelLeitura(
            empresa_id=empresa.id,
            razao_social=empresa.razao_social,
            tipo_empresa=empresa.tipo_empresa,
            capacidade_id=capacidade.id,
            processo_id=capacidade.processo_id,
            material_id=solicitacao.material_id,
            dimensao_x_maxima_mm=capacidade.dimensao_x_maxima_mm,
            dimensao_y_maxima_mm=capacidade.dimensao_y_maxima_mm,
            dimensao_z_maxima_mm=capacidade.dimensao_z_maxima_mm,
            tolerancia_minima_mm=capacidade.tolerancia_minima_mm,
        )
        for empresa, capacidade in itens
    ]
"""


TEST_PORTAL = r"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database.base import Base
from backend.app.database.sessao import obter_banco
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.principal import app


@pytest.fixture()
def ambiente() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessaoTeste = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)

    def substituir_banco() -> Generator[Session, None, None]:
        banco = SessaoTeste()
        try:
            yield banco
        finally:
            banco.close()

    app.dependency_overrides[obter_banco] = substituir_banco

    try:
        with TestClient(app) as test_client:
            yield test_client, SessaoTeste
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def preparar_base(SessaoTeste: sessionmaker) -> tuple[int, int, int, int]:
    banco = SessaoTeste()

    cliente = Empresa(
        razao_social="Cliente Portal D18",
        documento="D18-CLIENTE-001",
        tipo_empresa="cliente",
    )
    outro_cliente = Empresa(
        razao_social="Outro Cliente Portal D18",
        documento="D18-CLIENTE-002",
        tipo_empresa="cliente",
    )
    processo = ProcessoFabricacao(
        codigo="usinagem_cnc_d18",
        nome="Usinagem CNC D18",
        descricao="Processo de teste do portal D18.",
    )
    material = Material(
        codigo="aluminio_6061_d18",
        nome="Aluminio 6061 D18",
        familia="Aluminio",
        especificacao="Liga de teste D18.",
    )

    banco.add_all([cliente, outro_cliente, processo, material])
    banco.commit()

    ids = (cliente.id, outro_cliente.id, processo.id, material.id)
    banco.close()
    return ids


def test_listar_solicitacoes_por_cliente(ambiente):
    cliente_http, SessaoTeste = ambiente
    cliente_id, outro_cliente_id, processo_id, material_id = preparar_base(
        SessaoTeste
    )

    primeira = cliente_http.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "100.000",
            "dimensao_y_maxima_mm": "80.000",
            "dimensao_z_maxima_mm": "50.000",
            "tolerancia_requerida_mm": "0.0200",
            "quantidade": 10,
            "observacoes": "Solicitacao D18 do cliente principal.",
        },
    )
    assert primeira.status_code == 201

    segunda = cliente_http.post(
        "/api/v1/solicitacoes-servico",
        json={
            "empresa_cliente_id": outro_cliente_id,
            "processo_id": processo_id,
            "material_id": material_id,
            "dimensao_x_maxima_mm": "50.000",
            "dimensao_y_maxima_mm": "50.000",
            "dimensao_z_maxima_mm": "20.000",
            "tolerancia_requerida_mm": "0.0500",
            "quantidade": 2,
        },
    )
    assert segunda.status_code == 201

    resposta = cliente_http.get(
        "/api/v1/solicitacoes-servico",
        params={"empresa_cliente_id": cliente_id},
    )

    assert resposta.status_code == 200
    itens = resposta.json()

    assert len(itens) == 1
    assert itens[0]["empresa_cliente_id"] == cliente_id
    assert itens[0]["quantidade"] == 10
    assert itens[0]["status"] == "aberta"


def test_listar_solicitacoes_rejeita_empresa_inexistente(ambiente):
    cliente_http, _ = ambiente

    resposta = cliente_http.get(
        "/api/v1/solicitacoes-servico",
        params={"empresa_cliente_id": 999999},
    )

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "empresa_cliente_nao_encontrada"


def test_listar_solicitacoes_rejeita_fornecedor(ambiente):
    cliente_http, SessaoTeste = ambiente

    banco = SessaoTeste()
    fornecedor = Empresa(
        razao_social="Fornecedor Portal D18",
        documento="D18-FORNECEDOR-001",
        tipo_empresa="fornecedor",
    )
    banco.add(fornecedor)
    banco.commit()
    fornecedor_id = fornecedor.id
    banco.close()

    resposta = cliente_http.get(
        "/api/v1/solicitacoes-servico",
        params={"empresa_cliente_id": fornecedor_id},
    )

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "empresa_nao_e_cliente"
"""


API_TS = r"""
import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});
"""


CLIENT_PAGE = r"""
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
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
"""


CLIENT_CSS = r"""
.cliente-solicitacoes {
  max-width: 1380px;
  margin: 0 auto;
  padding: 32px 34px 48px;
  color: #e8edf5;
}

.cliente-solicitacoes__header,
.cliente-panel__header,
.cliente-request__top,
.cliente-form-footer,
.cliente-request__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.cliente-solicitacoes__header { margin-bottom: 24px; }

.cliente-solicitacoes h1 {
  margin: 6px 0 8px;
  font-size: 34px;
  color: #f7f9fc;
}

.cliente-solicitacoes h2 {
  margin: 5px 0 7px;
  color: #f2f5fa;
}

.cliente-solicitacoes p {
  color: #8f9caf;
  line-height: 1.55;
}

.cliente-eyebrow {
  color: #4f98ff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.7px;
}

.cliente-primary,
.cliente-secondary {
  border-radius: 9px;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  padding: 11px 16px;
}

.cliente-primary {
  border: 1px solid #2d6fe7;
  background: #2563eb;
  color: #fff;
}

.cliente-primary:disabled { cursor: wait; opacity: .65; }

.cliente-secondary {
  border: 1px solid #2a3544;
  background: #101720;
  color: #c8d2e1;
}

.cliente-feedback {
  border: 1px solid #2b3747;
  border-radius: 9px;
  margin-bottom: 16px;
  padding: 12px 14px;
}

.cliente-success {
  background: rgba(22, 163, 74, .1);
  border-color: rgba(34, 197, 94, .3);
  color: #86efac;
}

.cliente-error {
  background: rgba(220, 38, 38, .1);
  border-color: rgba(248, 113, 113, .3);
  color: #fca5a5;
}

.cliente-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

.cliente-stats article,
.cliente-panel {
  border: 1px solid #273242;
  border-radius: 12px;
  background: #141b24;
}

.cliente-stats article { padding: 18px; }

.cliente-stats span { color: #8290a4; font-size: 13px; }

.cliente-stats strong {
  display: block;
  margin-top: 7px;
  font-size: 29px;
}

.cliente-panel {
  margin-bottom: 18px;
  padding: 22px;
}

.cliente-panel__header { align-items: flex-start; }

.cliente-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 22px;
}

.cliente-form-grid label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: #acb9cc;
  font-size: 13px;
  font-weight: 700;
}

.cliente-form-grid input,
.cliente-form-grid select,
.cliente-form-grid textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #2b394b;
  border-radius: 8px;
  outline: none;
  background: #0d131b;
  color: #e8edf5;
  font: inherit;
  padding: 11px 12px;
}

.cliente-form-grid input:focus,
.cliente-form-grid select:focus,
.cliente-form-grid textarea:focus {
  border-color: #3b82f6;
}

.cliente-form-grid small {
  color: #6f7d91;
  font-weight: 400;
  line-height: 1.4;
}

.cliente-form-grid textarea { resize: vertical; }
.cliente-full { grid-column: 1 / -1; }

.cliente-form-footer {
  margin-top: 22px;
  padding-top: 17px;
  border-top: 1px solid #273242;
  color: #718097;
  font-size: 12px;
}

.cliente-request-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.cliente-request {
  border: 1px solid #273242;
  border-radius: 10px;
  background: #0f151d;
  padding: 17px;
}

.cliente-request__top > div > span {
  color: #5c9cff;
  font-size: 12px;
  font-weight: 800;
}

.cliente-request h3 {
  margin: 6px 0;
  color: #f4f7fb;
  font-size: 18px;
}

.cliente-request p { margin: 0; }

.cliente-status {
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 12px;
}

.cliente-status--aberta {
  background: rgba(37, 99, 235, .16);
  color: #80b1ff;
}

.cliente-status--encerrada {
  background: rgba(22, 163, 74, .15);
  color: #86efac;
}

.cliente-status--cancelada {
  background: rgba(220, 38, 38, .15);
  color: #fca5a5;
}

.cliente-request__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 14px;
  padding-top: 13px;
  border-top: 1px solid #202b39;
  color: #6f7d91;
  font-size: 12px;
}

.cliente-request__notes {
  margin-top: 14px !important;
  padding: 10px 12px;
  border-left: 3px solid #3b82f6;
  background: #121a24;
}

.cliente-request__footer {
  justify-content: flex-start;
  margin-top: 13px;
  font-size: 12px;
}

.cliente-request__footer a {
  color: #65a3ff;
  font-weight: 700;
  text-decoration: none;
}

.cliente-request__footer span { color: #68778c; }

.cliente-empty {
  min-height: 210px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 9px;
  color: #7e8b9e;
  text-align: center;
}

.cliente-empty strong { color: #dbe3ef; }

@media (max-width: 900px) {
  .cliente-solicitacoes { padding: 22px 17px 34px; }
  .cliente-stats { grid-template-columns: repeat(2, 1fr); }
  .cliente-form-grid { grid-template-columns: 1fr; }
  .cliente-full { grid-column: auto; }

  .cliente-solicitacoes__header,
  .cliente-panel__header,
  .cliente-form-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
"""


API_VITE = r"""
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
"""


def main() -> None:
    root = Path.cwd()

    if not (root / "backend" / "app").is_dir():
        raise SystemExit("ERRO: execute este script na raiz do MEC-Servicos.")

    if not (root / "frontend" / "package.json").exists():
        raise SystemExit("ERRO: frontend não encontrado.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / "_mec_backups" / f"V0_1_D18_PORTAL_CLIENTE_{stamp}"

    targets = [
        "backend/app/api/rotas/solicitacoes.py",
        "tests/test_portal_cliente_solicitacoes.py",
        "frontend/src/App.tsx",
        "frontend/src/services/api.ts",
        "frontend/src/pages/client/ClientSolicitacoesPage.tsx",
        "frontend/src/pages/client/ClientSolicitacoesPage.css",
        "frontend/vite.config.ts",
    ]

    backed_up = sum(
        int(backup(root, backup_root, relative))
        for relative in targets
    )

    write_file(
        root / "backend/app/api/rotas/solicitacoes.py",
        BACKEND_SOLICITACOES,
    )
    write_file(
        root / "tests/test_portal_cliente_solicitacoes.py",
        TEST_PORTAL,
    )

    frontend = root / "frontend"
    write_file(frontend / "src/services/api.ts", API_TS)
    write_file(
        frontend / "src/pages/client/ClientSolicitacoesPage.tsx",
        CLIENT_PAGE,
    )
    write_file(
        frontend / "src/pages/client/ClientSolicitacoesPage.css",
        CLIENT_CSS,
    )
    write_file(frontend / "vite.config.ts", API_VITE)

    app_path = frontend / "src/App.tsx"
    app_text = app_path.read_text(encoding="utf-8")

    import_marker = 'import ClientDashboard from "./pages/client/ClientDashboard";'
    import_new = 'import ClientSolicitacoesPage from "./pages/client/ClientSolicitacoesPage";'

    if import_new not in app_text:
        if import_marker not in app_text:
            raise SystemExit("ERRO: import de ClientDashboard não encontrado em App.tsx.")
        app_text = app_text.replace(
            import_marker,
            import_marker + "\n" + import_new,
            1,
        )

    old_route = """
          <Route
            path="solicitacoes"
            element={
              <ModulePage
                title="Minhas Solicitações"
                description="Crie e acompanhe suas solicitações de serviços mecânicos."
              />
            }
          />"""

    new_route = """
          <Route
            path="solicitacoes"
            element={<ClientSolicitacoesPage />}
          />"""

    if old_route in app_text:
        app_text = app_text.replace(old_route, new_route, 1)
    elif "path=\"solicitacoes\"" not in app_text:
        raise SystemExit("ERRO: rota de solicitações do cliente não encontrada em App.tsx.")

    write_file(app_path, app_text)

    report = {
        "revision": REVISION,
        "backend_list_endpoint": True,
        "frontend_client_request_page": True,
        "frontend_api_proxy": True,
        "tests_created": True,
        "database_migration_required": False,
        "backup_dir": str(backup_root),
        "backed_up_files": backed_up,
        "scope": [
            "listar solicitações por empresa cliente",
            "criar solicitação",
            "carregar processos",
            "carregar materiais",
            "indicadores do cliente",
            "histórico de solicitações",
        ],
        "not_in_scope": [
            "autenticação real no backend",
            "vínculo de arquivo técnico",
            "cotações",
        ],
    }

    (root / "MEC_SERVICOS_V0_1_D18_PORTAL_CLIENTE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (root / "MEC_SERVICOS_V0_1_D18_PORTAL_CLIENTE_RELATORIO.txt").write_text(
        "\n".join(
            [
                "Plataforma de Serviços Mecânicos — D18 Portal do Cliente",
                f"REVISION= {REVISION}",
                f"ROOT= {root}",
                "BACKEND_LIST_ENDPOINT= True",
                "FRONTEND_CLIENT_REQUEST_PAGE= True",
                "FRONTEND_API_PROXY= True",
                "TESTS_CREATED= True",
                "DATABASE_MIGRATION_REQUIRED= False",
                f"BACKED_UP= {backed_up}",
                f"BACKUP_DIR= {backup_root}",
            ]
        ) + "\n",
        encoding="utf-8",
    )

    print("Plataforma de Serviços Mecânicos — D18 Portal do Cliente")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")
    print("BACKEND_LIST_ENDPOINT= True")
    print("FRONTEND_CLIENT_REQUEST_PAGE= True")
    print("FRONTEND_API_PROXY= True")
    print("TESTS_CREATED= True")
    print("DATABASE_MIGRATION_REQUIRED= False")
    print(f"BACKED_UP= {backed_up}")
    print(f"BACKUP_DIR= {backup_root}")
    print("D18_CONFIGURADO= True")
    print("")
    print("Próximos comandos:")
    print("pytest .\\tests\\test_portal_cliente_solicitacoes.py -q")
    print("cd .\\frontend")
    print("npm run build")
    print("cd ..")
    print("pytest -q .\\tests --ignore= .\\tests\\mold".replace("--ignore= ", "--ignore="))


if __name__ == "__main__":
    main()
