# Plataforma de Serviços Mecânicos

Projeto independente para conectar clientes e fornecedores de serviços mecânicos.

## Regra de idioma

A aplicação é desenvolvida em português: interface, documentação, mensagens,
validações, nomes do domínio e módulos específicos da aplicação.

Nomes de tecnologias externas, como Python, FastAPI, SQLAlchemy, SQLite e Uvicorn,
permanecem com seus nomes oficiais.

## Estado

**V0.1 D8 — Contratação**

Nesta etapa foram estruturados:

- criação de uma contratação a partir de uma cotação aceita;
- validação de que a empresa é a cliente da solicitação;
- validação de que a cotação pertence à solicitação;
- validação de que a cotação está `aceita`;
- registro do fornecedor, valor e prazo contratados;
- uma única contratação por solicitação;
- encerramento comercial da solicitação após a contratação;
- consulta da contratação;
- cancelamento da contratação pelo cliente proprietário.

A contratação mantém o projeto independente do CGX Platform.

## Contratação

Uma contratação pode estar em:

- `ativa`
- `cancelada`
- `encerrada`

A contratação é criada somente a partir da cotação aceita correspondente à solicitação.

## O que ainda não faz parte do D8

- autenticação de usuários;
- negociação de preço;
- contraproposta;
- ordem de produção;
- pagamento;
- avaliação;
- ranking de fornecedores.
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
- ordem de produção;
- pagamento;
- avaliação;
- ranking de fornecedores.

## Endpoints de contratação

- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/contratacao`
- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/contratacao/cancelar`

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

## V0.1 D9 — Ordem de Serviço

A contratação ativa pode gerar uma ordem de serviço única, com ciclo `aberta`, `em_execucao`, `concluida` ou `cancelada`.

## D12 — Pagamentos

Nesta etapa foi criado o núcleo financeiro da contratação:

- registro de pagamentos parciais ou integrais;
- cálculo de total pago e saldo;
- status financeiro `pendente`, `parcial`, `pago` e `cancelado`;
- formas de pagamento controladas;
- bloqueio de pagamento acima do saldo;
- bloqueio de pagamento para contratação cancelada;
- cancelamento de lançamento preservando o histórico;
- consulta do histórico de pagamentos;
- resumo financeiro por contratação.

O D12 registra o **livro financeiro interno da contratação**. Não integra gateway, banco ou adquirente externo nesta etapa.

## D13 — Integração de Pagamentos

Nesta etapa foi criada a camada de integração de pagamentos, mantendo o D12 como livro financeiro interno:

- intenção de pagamento vinculada à contratação;
- gateway abstrato com implementação `fake` para testes;
- chave de idempotência para evitar duplicação de cobranças;
- `external_payment_id` do provedor;
- webhook assinado;
- processamento idempotente de eventos;
- evento `payment.succeeded` convertendo a intenção em lançamento D12;
- eventos `payment.failed` e `payment.cancelled`;
- separação entre intenção de pagamento, evento do gateway e lançamento financeiro.

A integração externa real permanece desacoplada do domínio e poderá ser adicionada posteriormente por um adaptador de provedor.
