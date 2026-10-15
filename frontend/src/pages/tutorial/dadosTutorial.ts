export type PerfilTutorial = "admin" | "cliente" | "fornecedor";
export type EtapaTutorial = {
  id: string;
  categoria: string;
  titulo: string;
  resumo: string;
  onde: string;
  caminho: string;
  passos: string[];
  resultado: string;
  dica?: string;
};
export type GuiaTutorial = {
  nome: string;
  introducao: string;
  etapas: EtapaTutorial[];
  duvidas: { pergunta: string; resposta: string }[];
};

export const GUIAS: Record<PerfilTutorial, GuiaTutorial> = {
  cliente: {
    nome: "Cliente",
    introducao: "Aprenda a solicitar um serviço, analisar o orçamento e acompanhar suas peças até a entrega.",
    etapas: [
      {
        id: "inicio", categoria: "Primeiros passos", titulo: "Conheça seu painel",
        resumo: "Encontre as pendências e acompanhe os serviços da sua empresa.",
        onde: "Dashboard", caminho: "/cliente",
        passos: ["Confira o nome da sua conta no topo da página.", "Abra o Dashboard e consulte os indicadores e os atalhos disponíveis.", "Anote o número da solicitação, da contratação ou da OS para localizar o mesmo serviço nas outras telas."],
        resultado: "Você sabe onde encontrar seus pedidos e quais itens precisam de atenção.",
        dica: "Solicitação, cotação, contratação e OS têm números próprios. Use o número correspondente ao filtro de cada tela.",
      },
      {
        id: "solicitacao", categoria: "Solicitação e orçamento", titulo: "Crie uma solicitação de serviço",
        resumo: "Informe o que precisa ser fabricado ou executado.",
        onde: "Minhas Solicitações", caminho: "/cliente/solicitacoes",
        passos: ["Clique na opção de nova solicitação e selecione processo e material.", "Informe quantidade, dimensões e os requisitos técnicos pedidos no formulário.", "Descreva as operações necessárias e as informações relevantes em Observações. Confira os dados e salve a solicitação."],
        resultado: "A solicitação recebe um número e fica disponível para acompanhamento.",
        dica: "Descreva o escopo real: uma peça de desbaste pode ter requisitos diferentes de uma peça acabada. Informe somente as exigências do serviço.",
      },
      {
        id: "arquivos", categoria: "Solicitação e orçamento", titulo: "Envie o desenho e os arquivos técnicos",
        resumo: "Vincule a documentação correta à solicitação.",
        onde: "Arquivos Técnicos", caminho: "/cliente/arquivos-tecnicos",
        passos: ["Localize a solicitação pelo número recebido na etapa anterior.", "Selecione o arquivo técnico e envie-o para essa solicitação.", "Confira a identificação do arquivo e acompanhe a revisão pela administração. Se precisar substituir o documento, comunique a alteração e confira a versão enviada."],
        resultado: "A administração pode revisar a documentação e liberar o serviço para cotação.",
        dica: "O fornecedor precisa de documentação técnica válida e liberada. O envio do arquivo é seguido pela revisão administrativa.",
      },
      {
        id: "orcamento", categoria: "Solicitação e orçamento", titulo: "Analise o orçamento publicado",
        resumo: "Confira o preço final, o prazo e as condições apresentadas.",
        onde: "Cotações Recebidas", caminho: "/cliente/cotacoes",
        passos: ["Pesquise a solicitação e abra Ver detalhes na cotação publicada para sua empresa.", "Confira valor total, quantidade, processo, material, prazo e validade da proposta.", "Use as opções de análise disponíveis para aprovar, solicitar revisão ou recusar. Revise sua decisão antes de confirmar."],
        resultado: "Sua análise fica registrada para a administração dar continuidade ao pedido.",
        dica: "A aprovação do orçamento é seguida pela formalização da contratação e da OS pela administração.",
      },
      {
        id: "contratacao", categoria: "Execução e entrega", titulo: "Confira a contratação e a OS",
        resumo: "Consulte a formalização do serviço aprovado.",
        onde: "Minhas Contratações", caminho: "/cliente/contratacoes",
        passos: ["Localize a solicitação e abra a contratação correspondente.", "Confira valor, prazo, situação e instruções de execução.", "Consulte Ordens de Serviço no menu e identifique a OS vinculada ao mesmo pedido."],
        resultado: "Você identifica o serviço contratado e sua ordem de execução.",
      },
      {
        id: "producao", categoria: "Execução e entrega", titulo: "Acompanhe a produção",
        resumo: "Veja as etapas e as atualizações registradas pelo fornecedor.",
        onde: "Acompanhamento de Produção", caminho: "/cliente/producao",
        passos: ["Selecione a OS e abra Ver histórico.", "Confira a etapa atual e as datas das atualizações.", "Use Atualizar histórico para consultar uma alteração recente e acompanhe as notificações no topo do sistema."],
        resultado: "Você acompanha o andamento da fabricação e as informações liberadas para sua empresa.",
        dica: "Pronto para coleta indica uma etapa da produção. A coleta e a entrega ao cliente são acompanhadas pela administração.",
      },
      {
        id: "entrega", categoria: "Execução e entrega", titulo: "Consulte a entrega das peças",
        resumo: "Acompanhe a movimentação e o histórico da entrega.",
        onde: "Entregas e Aceite", caminho: "/cliente/entregas",
        passos: ["Localize a OS e clique em Ver histórico.", "Confira os registros de coleta, conferência e entrega disponíveis no seu portal.", "Comunique à administração qualquer divergência entre as peças recebidas e o serviço contratado."],
        resultado: "Você confere a situação da entrega e mantém o acompanhamento do pedido.",
      },
      {
        id: "pagamentos", categoria: "Financeiro e avaliação", titulo: "Acompanhe os pagamentos do serviço",
        resumo: "Confira os valores e os registros financeiros da contratação.",
        onde: "Pagamentos", caminho: "/cliente/pagamentos",
        passos: ["Localize a contratação correspondente ao serviço.", "Confira o valor previsto, os recebimentos registrados e o saldo apresentado.", "Se houver diferença em relação ao pagamento realizado, encaminhe o comprovante à administração para conferência."],
        resultado: "Você acompanha o saldo com base nos registros financeiros do serviço.",
        dica: "Os registros no portal representam o controle do serviço. Confirme com a administração o meio de pagamento combinado.",
      },
      {
        id: "avaliacao", categoria: "Financeiro e avaliação", titulo: "Avalie o serviço recebido",
        resumo: "Registre sua nota quando a avaliação estiver disponível.",
        onde: "Avaliações", caminho: "/cliente/avaliacoes",
        passos: ["Pesquise a contratação ou a OS e abra os detalhes.", "Quando a avaliação estiver habilitada, selecione uma nota de 1 a 5 e, se desejar, escreva um comentário.", "Clique em Revisar avaliação, confira as informações e confirme o registro."],
        resultado: "Sua avaliação fica vinculada ao serviço para acompanhamento da qualidade.",
      },
      {
        id: "conta", categoria: "Primeiros passos", titulo: "Use as notificações e sua conta",
        resumo: "Consulte novidades e mantenha seu acesso atualizado.",
        onde: "Minha conta, no topo do sistema", caminho: "/conta",
        passos: ["Consulte o centro de notificações no topo e abra os avisos relevantes para seus serviços.", "Use Minha conta para consultar seu acesso e alterar sua senha quando necessário.", "Ao voltar ao programa, use o menu Ajuda e tutorial para continuar esta leitura."],
        resultado: "Você sabe acompanhar os avisos e gerenciar seu próprio acesso.",
      },
    ],
    duvidas: [
      { pergunta: "Enviei a solicitação. Por que ainda não recebi orçamento?", resposta: "Confira o envio dos arquivos técnicos e a revisão da administração. Depois da liberação, o orçamento passa pelo fornecedor e pela preparação administrativa antes de ser publicado para sua análise." },
      { pergunta: "Aprovei o orçamento. Onde aparece a ordem de serviço?", resposta: "A administração formaliza a contratação e a abertura da OS. Acompanhe Minhas Contratações, Ordens de Serviço e as notificações." },
      { pergunta: "Por que uma informação recente ainda não aparece?", resposta: "Confira a conta e a empresa selecionadas, o número pesquisado e os filtros. Use Atualizar na tela correspondente para consultar o registro mais recente." },
    ],
  },
  fornecedor: {
    nome: "Fornecedor",
    introducao: "Aprenda a consultar oportunidades, enviar propostas e atualizar a execução dos serviços da sua empresa.",
    etapas: [
      {
        id: "inicio", categoria: "Primeiros passos", titulo: "Conheça o painel do fornecedor",
        resumo: "Consulte as oportunidades e as pendências da sua empresa.",
        onde: "Dashboard", caminho: "/fornecedor",
        passos: ["Confira a identificação da sua empresa no acesso ao portal.", "Consulte o Dashboard e os atalhos para oportunidades, contratos e ordens.", "Use o número da solicitação ou da OS para acompanhar o mesmo serviço nas diferentes telas."],
        resultado: "Você identifica as pendências da sua empresa e as telas de trabalho.",
      },
      {
        id: "oportunidades", categoria: "Oportunidades e propostas", titulo: "Consulte as oportunidades disponíveis",
        resumo: "Encontre os serviços liberados para cotação.",
        onde: "Solicitações Disponíveis", caminho: "/fornecedor/solicitacoes",
        passos: ["Abra Solicitações Disponíveis e consulte as oportunidades apresentadas ao seu perfil.", "Abra a solicitação e confira processo, material, quantidade, dimensões e observações.", "Verifique se a capacidade da sua empresa atende às exigências antes de preparar a proposta."],
        resultado: "Você identifica um serviço compatível com sua capacidade de execução.",
        dica: "A disponibilidade depende da situação da solicitação, da documentação liberada e das regras de compatibilidade do cadastro.",
      },
      {
        id: "arquivos", categoria: "Oportunidades e propostas", titulo: "Baixe e confira a documentação técnica",
        resumo: "Use os documentos liberados para elaborar o orçamento.",
        onde: "Arquivos Técnicos", caminho: "/fornecedor/arquivos-tecnicos",
        passos: ["Localize a solicitação ou o serviço apresentado ao seu portal.", "Baixe os arquivos disponibilizados pela administração.", "Confira desenho, material, operações, revisões e requisitos técnicos. Encaminhe eventuais dúvidas à administração antes de confirmar preço e prazo."],
        resultado: "Você tem a documentação liberada para conferir o escopo do orçamento.",
      },
      {
        id: "cotacao", categoria: "Oportunidades e propostas", titulo: "Envie sua cotação",
        resumo: "Informe o valor total e os prazos para executar o serviço.",
        onde: "Solicitações Disponíveis", caminho: "/fornecedor/solicitacoes",
        passos: ["Abra a oportunidade e o formulário de cotação disponível para ela.", "Informe valor total do serviço, prazo em dias, validade e observações necessárias.", "Revise os dados, confira especialmente os zeros e as casas decimais do valor e confirme o envio."],
        resultado: "Sua proposta fica registrada para análise da administração.",
        dica: "O envio da cotação é uma proposta. Aguarde a contratação e a liberação da execução para iniciar o serviço.",
      },
      {
        id: "minhas-cotacoes", categoria: "Oportunidades e propostas", titulo: "Acompanhe suas propostas",
        resumo: "Consulte a situação e os detalhes das cotações enviadas.",
        onde: "Minhas Cotações", caminho: "/fornecedor/cotacoes",
        passos: ["Pesquise a cotação ou a solicitação desejada.", "Confira valor, prazo, validade e situação atual.", "Acompanhe as notificações e as orientações da administração sobre a continuidade do serviço."],
        resultado: "Você identifica quais propostas estão em análise e quais deram origem a serviços contratados.",
      },
      {
        id: "contratacao", categoria: "Produção e coleta", titulo: "Confira a contratação e a ordem",
        resumo: "Revise o que foi contratado antes da execução.",
        onde: "Contratações", caminho: "/fornecedor/contratacoes",
        passos: ["Abra a contratação vinculada à sua proposta.", "Confira as condições e as instruções de execução liberadas para sua empresa.", "Consulte Ordens de Serviço e confirme a OS e as orientações da administração sobre material e início do trabalho."],
        resultado: "Você conhece as condições do serviço e a OS que receberá as atualizações.",
      },
      {
        id: "producao", categoria: "Produção e coleta", titulo: "Atualize o andamento da produção",
        resumo: "Registre a etapa real de execução das peças.",
        onde: "Produção", caminho: "/fornecedor/producao",
        passos: ["Selecione a OS correta e abra seu histórico.", "Escolha a etapa disponível que representa o andamento real e informe observações úteis.", "Revise a atualização e confirme. Confira o novo registro no histórico."],
        resultado: "A etapa da produção fica registrada e os perfis envolvidos podem acompanhar a atualização.",
        dica: "Registre o que realmente aconteceu. Em caso de retrabalho, siga as orientações administrativas e atualize novamente a produção.",
      },
      {
        id: "coleta", categoria: "Produção e coleta", titulo: "Informe quando estiver pronto para coleta",
        resumo: "Avise que o lote está preparado para a movimentação.",
        onde: "Produção", caminho: "/fornecedor/producao",
        passos: ["Confira se o lote da OS está pronto conforme o serviço combinado.", "Na atualização da produção, selecione Pronto para coleta quando essa etapa estiver disponível e confirme.", "Acompanhe o agendamento e os registros da administração na tela Entregas."],
        resultado: "A administração pode dar continuidade à coleta e à conferência das peças.",
      },
      {
        id: "pagamentos", categoria: "Financeiro e qualidade", titulo: "Acompanhe os repasses do serviço",
        resumo: "Confira os valores financeiros apresentados à sua empresa.",
        onde: "Pagamentos", caminho: "/fornecedor/pagamentos",
        passos: ["Localize a contratação correspondente à OS executada.", "Confira os repasses registrados e o saldo exibido para o serviço.", "Solicite à administração a conferência de qualquer diferença nos registros."],
        resultado: "Você acompanha o controle dos valores a receber pelo serviço.",
      },
      {
        id: "notas", categoria: "Financeiro e qualidade", titulo: "Consulte as notas dos seus serviços",
        resumo: "Veja as notas individuais disponibilizadas para sua empresa.",
        onde: "Avaliações", caminho: "/fornecedor/avaliacoes",
        passos: ["Pesquise a contratação ou a OS concluída.", "Abra o serviço para consultar as notas disponibilizadas ao seu perfil.", "Use o retorno recebido para revisar a execução e alinhar melhorias com a administração."],
        resultado: "Você consulta as notas dos seus próprios serviços.",
      },
      {
        id: "conta", categoria: "Primeiros passos", titulo: "Acompanhe notificações e gerencie sua conta",
        resumo: "Consulte os avisos e as opções do seu acesso.",
        onde: "Minha conta, no topo do sistema", caminho: "/conta",
        passos: ["Consulte o centro de notificações e abra os avisos dos serviços da sua empresa.", "Use Minha conta para consultar seu acesso e alterar sua senha.", "Retorne ao menu Ajuda e tutorial sempre que precisar rever uma orientação."],
        resultado: "Você sabe acompanhar as novidades e gerenciar seu acesso ao portal.",
      },
    ],
    duvidas: [
      { pergunta: "Por que uma solicitação ainda não aparece para minha empresa?", resposta: "A administração precisa liberar a documentação técnica e o serviço deve atender às condições de disponibilidade do portal. Confira também se as operações e capacidades da sua empresa estão atualizadas com a administração." },
      { pergunta: "Enviei o orçamento. Já posso começar a produção?", resposta: "Aguarde a confirmação da contratação, a abertura da OS e as orientações da administração sobre material e execução." },
      { pergunta: "As peças estão prontas. Como aviso a administração?", resposta: "Selecione a OS em Produção, registre a etapa Pronto para coleta e confirme a atualização. Depois acompanhe a movimentação em Entregas." },
    ],
  },
  admin: {
    nome: "Administração",
    introducao: "Aprenda a coordenar a documentação, os orçamentos, a execução, as entregas e o resultado dos serviços.",
    etapas: [
      {
        id: "inicio", categoria: "Preparação", titulo: "Organize o trabalho pelo painel",
        resumo: "Localize pendências e acompanhe as contratações.",
        onde: "Dashboard", caminho: "/admin",
        passos: ["Confira os indicadores do Dashboard e consulte os serviços em andamento.", "Pesquise pelo número da OS ou da contratação para conferir um serviço específico.", "Abra os atalhos de pendências e relatórios disponíveis no painel para organizar as próximas ações."],
        resultado: "Você identifica os serviços e as etapas que precisam de intervenção administrativa.",
      },
      {
        id: "empresas", categoria: "Preparação", titulo: "Cadastre empresas, operações e capacidades",
        resumo: "Mantenha o cadastro técnico dos clientes e fornecedores.",
        onde: "Empresas e operações", caminho: "/admin/empresas",
        passos: ["Pesquise a empresa ou abra a opção para cadastrar uma nova.", "Informe os dados solicitados e o tipo de empresa. Para fornecedores, selecione as operações executadas.", "Confira capacidades, dimensões, tolerâncias e materiais aceitos conforme os campos disponíveis. Revise e salve o cadastro."],
        resultado: "O cadastro representa as condições de atendimento da empresa.",
        dica: "O cadastro da empresa e o acesso do usuário são registros diferentes. Confira também a conta que ficará vinculada a cada perfil.",
      },
      {
        id: "solicitacoes", categoria: "Documentos e orçamento", titulo: "Analise a solicitação do cliente",
        resumo: "Confira os requisitos antes de encaminhar o serviço para cotação.",
        onde: "Solicitações", caminho: "/admin/solicitacoes",
        passos: ["Pesquise a solicitação e clique em Abrir solicitação.", "Confira cliente, processo, material, quantidade, dimensões e observações.", "Confirme se a documentação enviada atende ao escopo e encaminhe a revisão em Arquivos Técnicos."],
        resultado: "Você conhece o pedido e as informações necessárias para cotar o serviço.",
      },
      {
        id: "documentos", categoria: "Documentos e orçamento", titulo: "Revise e libere os arquivos para cotação",
        resumo: "Confira o documento que será disponibilizado ao fornecedor.",
        onde: "Arquivos Técnicos", caminho: "/admin/arquivos-tecnicos",
        passos: ["Pesquise a solicitação e use Baixar para revisar no documento correto.", "Quando necessário, abra Preparar PDF com nossa logo, configure as áreas e os dados técnicos e confira a prévia comparada ao original.", "Após a revisão, use Liberar para cotação, confira a identificação do cliente, descreva o registro interno e clique em Confirmar registro."],
        resultado: "A documentação aprovada fica disponível segundo as regras de acesso da solicitação.",
        dica: "Preserve cotas, escala, revisões e requisitos técnicos relevantes. A preparação do PDF exige conferência do resultado antes de sua publicação.",
      },
      {
        id: "cotacoes", categoria: "Documentos e orçamento", titulo: "Compare as cotações dos fornecedores",
        resumo: "Analise preço, prazo e condições das propostas recebidas.",
        onde: "Cotações", caminho: "/admin/cotacoes",
        passos: ["Pesquise a solicitação ou a cotação e abra Analisar cotação.", "Confira preço do fornecedor, prazo de execução, validade e observações.", "Consulte o histórico e as avaliações administrativas disponíveis para apoiar a escolha do fornecedor."],
        resultado: "Você reúne os dados para escolher a proposta e preparar o preço ao cliente.",
      },
      {
        id: "preco", categoria: "Documentos e orçamento", titulo: "Prepare e publique o preço para o cliente",
        resumo: "Defina o acréscimo em percentual ou em reais.",
        onde: "Cotações > Analisar cotação", caminho: "/admin/cotacoes",
        passos: ["Abra a cotação e clique em Preparar preço para o cliente.", "Escolha a modalidade de acréscimo, informe o percentual sobre o custo ou o valor fixo e confira o preço final calculado.", "Revise os dados e publique o orçamento para análise do cliente. Acompanhe a aprovação, a solicitação de revisão ou a recusa."],
        resultado: "O cliente pode analisar o preço final publicado para o serviço.",
        dica: "O percentual é um acréscimo sobre o custo do fornecedor. Despesas do serviço são acompanhadas separadamente no resultado da administração.",
      },
      {
        id: "contratacao", categoria: "Contratação e execução", titulo: "Formalize a contratação e abra a OS",
        resumo: "Dê continuidade ao orçamento aprovado pelo cliente.",
        onde: "Contratações", caminho: "/admin/contratacoes",
        passos: ["Confira a aprovação do orçamento pelo cliente e registre a decisão administrativa da cotação quando habilitada.", "Abra a solicitação em Contratações e confira fornecedor, valores, prazo e documentação.", "Informe as instruções de execução e o registro interno. Revise contratação e OS e confirme a operação."],
        resultado: "O serviço fica formalizado e a OS passa a identificar a execução.",
      },
      {
        id: "material", categoria: "Contratação e execução", titulo: "Inicie o ciclo e encaminhe o material",
        resumo: "Registre as movimentações administrativas do serviço.",
        onde: "Entregas e Aceite", caminho: "/admin/entregas",
        passos: ["Localize a OS, abra Ver ciclo e inicie o ciclo administrativo quando disponível.", "Selecione a ação permitida de encaminhamento do material na situação atual.", "Informe registro interno e comprovante quando solicitado, revise os dados e confirme o registro."],
        resultado: "O histórico do ciclo passa a acompanhar o encaminhamento do serviço.",
      },
      {
        id: "producao", categoria: "Contratação e execução", titulo: "Acompanhe a produção informada",
        resumo: "Consulte o avanço dos serviços nas empresas fornecedoras.",
        onde: "Acompanhamento de Produção", caminho: "/admin/producao",
        passos: ["Localize a OS pelo filtro ou pela lista de serviços.", "Confira a etapa atual, as datas e o histórico informado pelo fornecedor.", "Quando houver atraso ou divergência, alinhe o encaminhamento com os envolvidos e acompanhe as notificações."],
        resultado: "Você acompanha a execução para coordenar os próximos movimentos.",
      },
      {
        id: "coleta", categoria: "Conferência e entrega", titulo: "Registre a coleta e confira o lote",
        resumo: "Acompanhe as peças prontas até a avaliação administrativa.",
        onde: "Entregas e Aceite", caminho: "/admin/entregas",
        passos: ["Confira se o fornecedor informou Pronto para coleta em Produção.", "No ciclo da OS, registre a solicitação de coleta e o recebimento das peças conforme as ações disponíveis.", "Confira a quantidade do lote e registre o parecer técnico ao aprovar as peças ou solicitar retrabalho."],
        resultado: "A coleta e a conferência ficam registradas no histórico administrativo.",
        dica: "O ciclo controla o lote completo da OS. Confira a quantidade pedida no formulário de cada movimentação.",
      },
      {
        id: "entrega", categoria: "Conferência e entrega", titulo: "Conclua a entrega ao cliente",
        resumo: "Registre a entrega física do lote aprovado.",
        onde: "Entregas e Aceite", caminho: "/admin/entregas",
        passos: ["Confira se as peças foram aprovadas e se a ação de entrega está disponível.", "Registre a entrega ao cliente, a quantidade conferida, o comprovante e as informações solicitadas.", "Revise e confirme. Confira a conclusão da OS e o histórico do ciclo."],
        resultado: "A entrega e a conclusão da ordem ficam registradas para acompanhamento.",
      },
      {
        id: "financeiro", categoria: "Financeiro e resultado", titulo: "Registre recebimentos e repasses",
        resumo: "Controle os movimentos financeiros efetivamente realizados.",
        onde: "Pagamentos", caminho: "/admin/pagamentos",
        passos: ["Abra a contratação correta e confira os valores previstos para cliente e fornecedor.", "Registre o recebimento do cliente ou o repasse ao fornecedor com os dados e comprovantes solicitados.", "Confira saldos e histórico. Se precisar corrigir um registro, use o estorno disponível e descreva o motivo antes de lançar o movimento correto."],
        resultado: "O controle financeiro reflete os movimentos registrados para o serviço.",
        dica: "O sistema registra recebimentos e repasses. A transferência bancária deve ser realizada pelo meio combinado fora desse registro.",
      },
      {
        id: "resultado", categoria: "Financeiro e resultado", titulo: "Registre despesas e acompanhe o resultado",
        resumo: "Veja o efeito dos gastos no resultado da administração.",
        onde: "Pagamentos > Resultado da administração", caminho: "/admin/resultado-administracao",
        passos: ["Consulte o período desejado e localize a contratação para conferir suas despesas.", "Registre os gastos reais e sua situação conforme os campos disponíveis. Confira os registros e os estornos existentes.", "Compare resultado previsto, resultado após despesas pagas e resultado dos serviços liquidados; use os relatórios e as análises disponíveis para detalhar os valores."],
        resultado: "Você acompanha o resultado dos serviços com os custos e as despesas registrados.",
        dica: "Os indicadores usam critérios próprios. Confira a situação dos pagamentos e a explicação de cada valor antes de compará-los.",
      },
      {
        id: "metas", categoria: "Financeiro e resultado", titulo: "Defina metas e consulte os relatórios",
        resumo: "Compare o resultado liquidado com a meta de cada mês.",
        onde: "Resultado da administração > Abrir metas mensais", caminho: "/admin/resultado-administracao",
        passos: ["Abra metas mensais e selecione o ano da consulta.", "No seletor Mês para definir ou editar a meta, escolha o mês e abra a edição. Informe o valor e o motivo quando quiser registrar uma alteração.", "Confira tabela, gráfico, histórico e atingimento. Use Baixar CSV das metas ou Baixar PDF das metas para exportar a consulta."],
        resultado: "Você acompanha as metas mensais e os resultados calculados na consulta.",
        dica: "As metas são comparadas ao resultado dos serviços liquidados, agrupado pelo mês de criação da contratação. Mês sem meta e meta igual a zero têm tratamentos próprios no percentual.",
      },
      {
        id: "avaliacoes", categoria: "Qualidade", titulo: "Avalie os serviços e consulte o ranking",
        resumo: "Acompanhe a qualidade e o histórico de cada fornecedor.",
        onde: "Ranking de Fornecedores", caminho: "/admin/ranking",
        passos: ["Em Avaliações, localize o serviço apto e registre a nota administrativa após a revisão.", "Abra Ranking de Fornecedores e consulte gráfico, notas e histórico da empresa.", "Use a comparação como apoio à análise das próximas propostas, considerando também capacidade, preço e prazo."],
        resultado: "Você reúne as informações de qualidade para apoiar decisões administrativas.",
        dica: "O ranking é exclusivo da administração. O fornecedor consulta apenas as notas individuais disponibilizadas dos seus serviços.",
      },
      {
        id: "conta", categoria: "Preparação", titulo: "Consulte avisos e gerencie seu acesso",
        resumo: "Acompanhe as notificações relevantes para a administração.",
        onde: "Minha conta, no topo do sistema", caminho: "/conta",
        passos: ["Abra o centro de notificações para consultar alterações nos serviços.", "Use Minha conta para consultar seu acesso e alterar sua senha.", "Retorne ao menu Ajuda e tutorial para revisar o procedimento de cada etapa."],
        resultado: "Você sabe onde consultar avisos e administrar seu próprio acesso.",
      },
    ],
    duvidas: [
      { pergunta: "Por que o fornecedor ainda não vê uma solicitação?", resposta: "Confira os arquivos ativos e íntegros, o registro de liberação para cotação, a situação da solicitação e a compatibilidade com o cadastro do fornecedor. Depois atualize a consulta no portal correspondente." },
      { pergunta: "Onde preparo o valor que será apresentado ao cliente?", resposta: "Em Cotações, abra Analisar cotação e depois Preparar preço para o cliente. O acréscimo pode ser percentual sobre o custo ou um valor fixo em reais. Revise o preço final antes da publicação." },
      { pergunta: "Por que a ação de coleta ainda não está disponível?", resposta: "Confira o ciclo administrativo e peça ao fornecedor que registre Pronto para coleta em Produção. Depois de retrabalho é necessário um novo registro dessa etapa." },
      { pergunta: "Onde consulto o resultado e as metas da administração?", resposta: "Abra Pagamentos e Resultado da administração. Nessa área ficam despesas, análises e relatórios; use Abrir metas mensais para consultar as metas, o gráfico e as exportações." },
    ],
  },
};

export function normalizarBusca(valor: string): string {
  return valor.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR").trim();
}

export function filtrarEtapas(guia: GuiaTutorial, busca: string): EtapaTutorial[] {
  const termos = normalizarBusca(busca).split(/\s+/).filter(Boolean);
  return guia.etapas.filter(etapa => {
    const texto = normalizarBusca([etapa.categoria, etapa.titulo, etapa.resumo, etapa.onde,
      ...etapa.passos, etapa.resultado, etapa.dica ?? ""].join(" "));
    return termos.every(termo => texto.includes(termo));
  });
}
