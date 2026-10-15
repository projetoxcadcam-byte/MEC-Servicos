from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.comercial_admin import CotacaoComercial, SolicitacaoComercial
from backend.app.schemas.documentacao_cotacao import ArquivoDocumentacao


class ContratacaoAdministrativa(BaseModel):
    id: int
    solicitacao_id: int
    cotacao_id: int
    empresa_cliente_id: int
    cliente: str
    empresa_fornecedora_id: int
    fornecedor: str
    valor_total: Decimal
    prazo_dias: int
    quantidade: int
    processo: str
    material: str
    status: str
    criada_em: str
    observacoes: str | None
    ordem_servico_id: int | None
    ordem_status: str | None
    etapa_administrativa: str | None


class PaginaContratacoesAdmin(BaseModel):
    itens: list[ContratacaoAdministrativa]
    total: int
    deslocamento: int
    limite: int


class EventoContratacaoLeitura(BaseModel):
    id: int
    acao: str
    contratacao_id: int
    ordem_servico_id: int
    administrador_nome: str
    registro_interno: str
    criado_em: str


class PreparacaoContratacaoAdmin(BaseModel):
    solicitacao: SolicitacaoComercial
    cotacao: CotacaoComercial | None
    contratacao: ContratacaoAdministrativa | None
    arquivos: list[ArquivoDocumentacao]
    historico: list[EventoContratacaoLeitura]
    versao: str
    acao_disponivel: Literal["contratar_e_abrir_os", "abrir_os"] | None
    motivo_indisponivel: str | None


class ConfirmacaoContratacaoAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acao: Literal["contratar_e_abrir_os", "abrir_os"]
    cotacao_id: int = Field(gt=0)
    versao: str = Field(pattern=r"^[0-9a-f]{64}$")
    registro_interno: str = Field(min_length=3, max_length=2000)
    observacoes_execucao: str | None = Field(default=None, max_length=4000)
    chave_operacao: UUID


class ResultadoContratacaoAdmin(BaseModel):
    evento_id: int
    solicitacao_id: int
    cotacao_id: int
    contratacao_id: int
    ordem_servico_id: int
    contratacao_status: str
    ordem_status: str
    etapa_administrativa: str
    administrador_nome: str
    criado_em: str
