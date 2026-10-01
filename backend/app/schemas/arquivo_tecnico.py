from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArquivoTecnicoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitacao_id: int
    nome_original: str
    extensao: str
    content_type: str | None
    tamanho_bytes: int
    sha256: str
    criado_em: datetime
    ativo: bool
