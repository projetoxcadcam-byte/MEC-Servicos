# Correção de sessão do frontend MEC-Serviços

Esta correção troca a autenticação de `localStorage` para `sessionStorage`.

Comportamento:
- recarregar a página: permanece logado;
- navegar entre rotas: permanece logado;
- fechar a aba/janela: a sessão termina;
- abrir novamente: volta ao login;
- a chave antiga `mec-servicos-auth` do localStorage é removida automaticamente.

## Aplicação

No PowerShell:

```powershell
cd C:\Users\Omega\Desktop\MEC-Servicos\frontend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\CORRIGIR_SESSAO_FRONTEND_MEC_SERVICOS.ps1
npm run build
npm run dev
```

O script cria backups dos dois arquivos de autenticação antes de substituir.
