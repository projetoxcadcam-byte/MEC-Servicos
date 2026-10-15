from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def decodificar_texto(dados: bytes, nome: str) -> tuple[str, str]:
    """Leitura estrita de UTF-8 ou Windows-1252, respeitando BOMs Unicode."""
    if dados.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        codificacoes = ("utf-32",)
    elif dados.startswith((b"\xff\xfe", b"\xfe\xff")):
        codificacoes = ("utf-16",)
    elif dados.startswith(b"\xef\xbb\xbf"):
        codificacoes = ("utf-8-sig",)
    else:
        codificacoes = ("utf-8", "cp1252")
    for codificacao in codificacoes:
        try:
            texto = dados.decode(codificacao)
        except UnicodeDecodeError as erro:
            posicao = erro.start
            continue
        if "\x00" in texto:
            raise RuntimeError("Texto com bytes nulos em " + nome + "; arquivo preservado.")
        return texto, codificacao
    raise RuntimeError(
        "Codificação inválida em " + nome + " (posição " + str(posicao)
        + "); arquivo preservado. Não foram descartados bytes."
    )


def codificacao_env() -> str:
    arquivo = Path(".env")
    if not arquivo.is_file():
        return "utf-8"
    return decodificar_texto(arquivo.read_bytes(), ".env")[1]


class Configuracoes(BaseSettings):
    nome_aplicacao: str = "Plataforma de Serviços Mecânicos"
    versao_aplicacao: str = "0.1.0"
    ambiente: str = "desenvolvimento"
    prefixo_api: str = "/api/v1"
    modo_debug: bool = True
    url_banco_dados: str = "sqlite:///./data/mec_servicos.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding=codificacao_env(),
        env_prefix="MEC_",
        extra="ignore",
    )


configuracoes = Configuracoes()
