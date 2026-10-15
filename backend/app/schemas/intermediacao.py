from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

AcaoIntermediacao = Literal["receber_material", "encaminhar_material", "solicitar_coleta", "receber_pecas",
    "iniciar_avaliacao", "aprovar_pecas", "solicitar_retrabalho", "encaminhar_retrabalho", "entregar_cliente", "cancelar"]


class InicioIntermediacao(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    registro_interno: str = Field(min_length=3, max_length=2000)


class RegistroIntermediacao(InicioIntermediacao):
    acao: AcaoIntermediacao
    versao: int = Field(strict=True, gt=0)
    referencia: str | None = Field(default=None, min_length=3, max_length=200)
    parecer_tecnico: str | None = Field(default=None, min_length=3, max_length=4000)
    quantidade_conferida: int | None = Field(default=None, strict=True, gt=0)


class OrdemIntermediacaoLeitura(BaseModel):
    ordem_servico_id: int
    solicitacao_id: int
    contratacao_id: int
    empresa_cliente_id: int
    empresa_fornecedora_id: int
    cliente: str
    fornecedor: str
    quantidade: int
    ordem_status: str
    contratacao_status: str
    producao_etapa: str | None
    ciclo_id: int | None
    status: str | None
    versao: int
    atualizado_em: str | None
    pode_iniciar: bool


class IntermediacaoPagina(BaseModel):
    itens: list[OrdemIntermediacaoLeitura]
    total: int
    deslocamento: int
    limite: int


class EventoAdministrativoLeitura(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    versao: int
    acao: str
    status_anterior: str | None
    status_resultante: str
    usuario_admin_id: int
    administrador_nome: str
    registro_interno: str
    referencia: str | None
    parecer_tecnico: str | None
    quantidade_conferida: int | None
    criado_em: str


class IntermediacaoDetalhe(BaseModel):
    ordem: OrdemIntermediacaoLeitura
    acoes_permitidas: list[str]
    historico: list[EventoAdministrativoLeitura]


class EventoPortalIntermediacao(BaseModel):
    acao: str
    status_resultante: str
    criado_em: str


class ConsultaPortalIntermediacao(BaseModel):
    ordem_servico_id: int
    status: str | None
    atualizado_em: str | None
    historico: list[EventoPortalIntermediacao]


class ContratacaoParaIntermediacao(BaseModel):
    id: int
    solicitacao_id: int
    cliente: str
    fornecedor: str
