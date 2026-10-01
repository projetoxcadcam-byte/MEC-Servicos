# Documentação

Documentação técnica e funcional da Plataforma de Serviços Mecânicos.

Todo o conteúdo voltado ao usuário e ao domínio da aplicação deve ser mantido em português.

O projeto permanece independente do CGX Platform.

## D8 — Contratação

A contratação nasce de uma cotação aceita. O cliente proprietário da solicitação é validado, a cotação precisa pertencer à solicitação e estar no estado `aceita`. A criação registra fornecedor, valor e prazo da contratação e encerra comercialmente a solicitação. O contrato pode ser consultado e cancelado pelo cliente proprietário.

## D9 — Ordem de Serviço

O D9 cria a ordem a partir da contratação ativa e prepara o acompanhamento da execução.
Próxima evolução: marcos de produção como matéria-prima, usinagem/corte, tratamento e envio.

## D12 — Pagamentos

O módulo financeiro trabalha sobre a contratação existente e registra lançamentos confirmados ou cancelados. O saldo é derivado do valor contratado menos a soma dos pagamentos confirmados. O sistema impede valor acima do saldo e não permite novos pagamentos para contratação cancelada.

Nesta etapa não existe integração com PSP/gateway externo; o objetivo é estabelecer o domínio financeiro interno antes da integração de meios de pagamento reais.

## D13 — Integração de Pagamentos

O D13 adiciona uma camada de intenção de pagamento e um contrato de gateway. O provedor `fake` é usado exclusivamente para testes. O webhook exige assinatura HMAC e possui idempotência por `(provedor, evento_id)`.

Quando `payment.succeeded` é recebido, o serviço cria o lançamento confirmado no livro financeiro do D12 e associa seu identificador à intenção. Eventos duplicados não criam um segundo lançamento.
