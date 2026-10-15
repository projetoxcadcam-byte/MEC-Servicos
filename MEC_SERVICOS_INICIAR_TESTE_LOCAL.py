r"""Iniciar o backend MEC em modo de teste no próprio computador.

    .\.venv\Scripts\python.exe .\MEC_SERVICOS_INICIAR_TESTE_LOCAL.py

O login normal volta ao iniciar diretamente o Uvicorn sem este comando.
"""
from pathlib import Path
import os
import subprocess
import sys


def main():
    raiz = Path(__file__).resolve().parent
    if not (raiz / "backend/app/core/modo_teste_local.py").is_file():
        print("ERRO=Instale primeiro o D31 FIX2 — Modo de teste local.")
        return 1
    ambiente = os.environ.copy()
    ambiente["MEC_MODO_TESTE_LOCAL"] = "1"
    ambiente["MEC_AMBIENTE"] = "desenvolvimento"
    print("MEC-Serviços — Modo de teste local", flush=True)
    print("Abra o frontend e escolha a conta na tela de acesso.", flush=True)
    print("O backend atende somente em 127.0.0.1:8000. Use Ctrl+C para parar.", flush=True)
    try:
        return subprocess.call([sys.executable, "-m", "uvicorn", "backend.app.principal:app", "--host", "127.0.0.1", "--port", "8000", "--reload"], cwd=raiz, env=ambiente)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
