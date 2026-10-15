"""Recuperação local de contas MEC. Execute somente no computador do servidor."""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sys


def main() -> int:
    raiz = Path(__file__).resolve().parent
    sys.path.insert(0, str(raiz))
    from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso
    from fastapi import HTTPException
    parser = argparse.ArgumentParser(description="Listar ou recuperar contas de acesso no servidor MEC.")
    parser.add_argument("acao", choices=("listar", "redefinir-senha"))
    parser.add_argument("--usuario-id", type=int)
    argumentos = parser.parse_args()
    servico = ArmazenamentoAcesso(raiz / "data/mec_acessos.db")
    try:
        if argumentos.acao == "listar":
            for conta in servico.listar_usuarios():
                print(f"USUARIO={conta['usuario_id']} | {conta['nome']} | {conta['email']} | perfil={conta['role']} | empresa={conta['empresa_id']} | ativo={conta['ativo']}")
            return 0
        if not argumentos.usuario_id or argumentos.usuario_id <= 0:
            parser.error("Informe --usuario-id com um ID positivo.")
        senha = getpass.getpass("Nova senha inicial (12 a 128 caracteres): ")
        confirmar = getpass.getpass("Confirme a senha: ")
        if senha != confirmar:
            print("ERRO=As senhas não conferem."); return 1
        servico.redefinir_senha(argumentos.usuario_id, senha)
        servico.registrar_acao(0, "recuperar_senha_local", "usuario/" + str(argumentos.usuario_id))
        print("RESULTADO=OK\nSessões encerradas. O titular deverá alterar a senha inicial no próximo acesso.")
        return 0
    except HTTPException as erro:
        print("ERRO=" + str(erro.detail)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
