from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    nome_aplicacao: str = "Plataforma de Serviços Mecânicos"
    versao_aplicacao: str = "0.1.0"
    ambiente: str = "desenvolvimento"
    prefixo_api: str = "/api/v1"
    modo_debug: bool = True
    url_banco_dados: str = "sqlite:///./data/mec_servicos.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MEC_",
        extra="ignore",
    )


configuracoes = Configuracoes()
