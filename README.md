# Plataforma de Serviços Mecânicos

Projeto independente para conectar clientes e fornecedores de serviços mecânicos.

## Regra de idioma

A aplicação é desenvolvida em português: interface, documentação, mensagens,
validações, nomes do domínio e módulos específicos da aplicação.

Nomes de tecnologias externas, como Python, FastAPI, SQLAlchemy, SQLite e Uvicorn,
permanecem com seus nomes oficiais.

## Estado

**V0.1 D7 — Decisão Comercial das Cotações**

Nesta etapa foram estruturados:

- ciclo de vida da cotação;
- aceite de uma cotação pelo cliente da solicitação;
- recusa de uma cotação pelo cliente da solicitação;
- registro da data de encerramento;
- registro da empresa que tomou a decisão;
- rejeição automática das demais cotações pendentes quando uma é aceita;
- bloqueio de novas cotações depois que uma solicitação já possui cotação aceita;
- expiração automática das cotações vencidas durante consultas ou decisões;
- preservação do histórico das cotações.

O projeto continua independente do CGX Platform.

## Ciclo da cotação

Uma cotação pode estar em:

- `enviada`
- `aceita`
- `recusada`
- `expirada`
- `cancelada`

Somente uma cotação por solicitação pode ficar `aceita`.

Quando uma cotação é aceita, as demais que ainda estiverem `enviada`
são marcadas como `recusada`.

## Autorização comercial

Como ainda não existe autenticação de usuários, as rotas de decisão recebem
explicitamente `empresa_cliente_id`.

O sistema verifica se essa empresa é a empresa cliente da solicitação.

Isso é uma validação de domínio e **não substitui autenticação**.

## Regra técnica

A criação da cotação continua dependente da compatibilidade técnica do D5.

O D7 não altera o motor de compatibilidade.

## O que ainda não faz parte do D7

- autenticação de usuários;
- negociação de preço;
- contraproposta;
- contratação;
- ordem de produção;
- pagamento;
- avaliação;
- ranking de fornecedores.

## Executar

```powershell
python -m pytest
python -m uvicorn backend.app.principal:app --reload
```

## Endpoints principais

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/api/v1/saude`
- `http://127.0.0.1:8000/api/v1/banco-dados/saude`
- `http://127.0.0.1:8000/api/v1/empresas`
- `http://127.0.0.1:8000/api/v1/processos-fabricacao`
- `http://127.0.0.1:8000/api/v1/materiais`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/aceitar`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/cotacoes/{cotacao_id}/recusar`
- `http://127.0.0.1:8000/docs`
