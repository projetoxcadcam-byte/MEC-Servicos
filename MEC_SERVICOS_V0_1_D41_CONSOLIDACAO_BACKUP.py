"""MEC-Serviços D41 — Consolidação e recuperação de backup.
Pare o backend e execute na raiz do MEC com a .venv. Não restaura bancos em uso.
"""

from __future__ import annotations

import ast

from contextlib import closing

from datetime import datetime

import hashlib

import json

import os

from pathlib import Path

import queue

import shutil

import signal

import socket

import sqlite3

import subprocess

import sys

import tempfile

import threading

import time

from urllib.parse import urlsplit

import uuid

REVISION = 'MEC-SERVICOS-V0.1-D41-CONSOLIDACAO-BACKUP-2026-10-06'

D40_REVISION = 'MEC-SERVICOS-V0.1-D40-EXTRATO-FINANCEIRO-2026-10-06'

STEM = 'MEC_SERVICOS_V0_1_D41_CONSOLIDACAO_BACKUP_RELATORIO'

BASE_SHA256 = {'backend/app/principal.py': ['e711b8fa481a20283c8764c5df5f93393227b2cb58b65782aa0698ae8b94371b'], 'frontend/src/App.tsx': ['e76316d60183d23cc442dd4e6ccfd938b8da75e44bfca39d4d9754f8dfebd561'], 'frontend/src/pages/financeiro/FinanceiroPage.tsx': ['670a078eae983c565a4e49743a5567acb4645ad068b7d82262b804a6e1cbe34a'], 'backend/app/services/financeiro_administrativo.py': ['472578665256b9aa5422a734fc10a0091e95ef103ba654e8a5b581c4ffacf22a'], 'backend/app/models/financeiro_administrativo.py': ['74efa682efd815f778782fb35701783d3081eddc4e689d0329ff9424b253d7e7'], 'frontend/src/pages/financeiro/financeiroPortal.ts': ['703c3d478e1c9f372c7eb21b4bf17670dfbd420305d74595789ce2ef3f6b8eb9'], 'frontend/src/pages/intermediacao/AdminIntermediacaoPage.tsx': ['825a4319b7b5b24137f6446503e2f5b41fa88fef74af1cc1e076bd14496594f3'], 'backend/app/services/intermediacao.py': ['8764c2cc920f9af14edfbc17029cf4875b02bcc6484725657ac69a90c436edfd'], 'backend/app/models/intermediacao.py': ['f6ed06fa32b5aae0d9b5d0b50b6d33759f7d19e2770acdfd1b45e1e3e9293db9'], 'frontend/src/pages/intermediacao/intermediacaoPortal.ts': ['ffc934f799789f13eea2437b99c9b7134318a8b8585c39dd48e2913c6a4d43cd'], 'backend/app/core/permissoes_acesso.py': ['5534eb6eb28423fe7ccce86e93534e34408de2a92887d9664eb730e792861604', '5aedd2d4bdc9be7bb7b0d6a53c87b933c40f9a6f697ab6a586a87e1c3b8a3da6'], 'frontend/src/auth/AuthContext.tsx': ['838f03f499b1374014428e0587d19589058d512ebca0520355b2f28867a9a7a6', '12ae647f73a80e4b1c8c00a01fb2e8cccb7114767d8292a659efe7a90f096c06'], 'frontend/src/services/api.ts': ['e5db9ea929d076ce6e2411d3d89c195a33acc5610af6035f23761a96fe543db3'], 'frontend/src/services/acesso.ts': ['c4c799053bcb9338a55c649a95ae80df45f4b294754c9bb751b0c4e062697ee5', '3dbe6b9d31ca74ab59362bf64740cdc776a209aedd81eafa44c7bc191c215d45'], 'D33_CONTRATO_PAINEL_ADMIN.txt': ['3fdf7577b59dba860bdf7c1f25e05ec0a62762f689a7d11492adb4041532ae15'], 'tests/test_painel_administrativo_d33.py': ['90cf716dc34755ad8db367caca4e77e25210d37c07710242bcc882728e65afab'], 'frontend/src/pages/painel/PainelAdministrativoPage.tsx': ['51030b1bfef117461bc4bfcdd915cbaf3c9162afdee638baf0a9197db7947e39'], 'frontend/src/pages/painel/painelPortal.ts': ['d077a53088d4023edba366997d77ef97719d17e80faddb8852dab4a6871b7ecd'], 'frontend/src/pages/painel/PainelAdministrativo.css': ['eea184d9069e3382243b0be6aac09cafd9a4ed50cc2063c19acb4625bdac17e2'], 'backend/app/services/painel_administrativo.py': ['60bfec3afcb0ef726f2f833ae9a4771fe05e96f29f35234916eed4575227e338'], 'backend/app/schemas/painel_administrativo.py': ['0fbb493e8132fbc1e5b220685e501860533e2c819b78d10fc30543510e8ab9b4'], 'backend/app/api/rotas/painel_administrativo.py': ['69000275b72a35814298075be18f2e95f04cd74320b7be2ee3deaa8a3872e883'], 'D34_CONTRATO_RELATORIO_ADMIN.txt': ['48c3bf12e576ba0efc391ede4c89dc3760e2c2e1e2b3c7bcc50d93e17d7bb9b2'], 'tests/test_relatorio_administrativo_d34.py': ['26032d692db416035331bc50db0911ba90489e199ace78ebba5a50564709e5bf'], 'frontend/src/pages/relatorios/RelatorioAdministrativoPage.tsx': ['b623fd9adf6d5519f8a636551097f9f6ad90e990ce9190889be4c36a910aa813'], 'frontend/src/pages/relatorios/relatorioPortal.ts': ['4b54d5346f81b065887d1cb8585f132f2418187c8e786c1124a45a75d796963d'], 'frontend/src/pages/relatorios/RelatorioAdministrativo.css': ['8862a85b43d1b282e5a556c2f0a6c35d77f51e20993966fb32282d25714278cb'], 'backend/app/services/relatorio_administrativo.py': ['0fa0ac56e453c32744f04635f64db876433bc5eb448165a08e336935d360d0ff'], 'backend/app/schemas/relatorio_administrativo.py': ['1a4123973bd6a61d82470798c9772924f85bbaeaea0db281f4d198fcd5277a88'], 'backend/app/api/rotas/relatorio_administrativo.py': ['79cad524f2632341685a4ed602eab3b3ed2ec6630bb3e1fd9d322845c87775f7'], 'D35_CONTRATO_RELATORIO_PERIODO.txt': ['f1754e201943e59cfaeb9bf955baaeb36225c217cd6f9cc5f6a59d6d67c33ab1'], 'backend/app/api/rotas/relatorio_periodo.py': ['8d6d5a2015f99668bbfed01bc82d5d45f4009c11d8bd3a0b7f6c0710e74e06d6'], 'backend/app/schemas/relatorio_periodo.py': ['36e2a56bee8b9a6a547930d04e36c47157852feab2ebcbb8b208ac7a0186bce0'], 'backend/app/services/relatorio_periodo.py': ['fa0bf2374a2110aec49ff6e4caebb6848a0e47003ec096e9ae5ab38ed090ab54'], 'frontend/src/pages/periodo/RelatorioPeriodo.css': ['b26d7c98c78774d1d6d185d8770af84159fbc5bcca7ba7e13db5ec2b92a5fbf8'], 'frontend/src/pages/periodo/RelatorioPeriodoPage.tsx': ['1dc0223179de83b01626f91e095c384e7929a992af698f28c8ac50e03ace1fbb'], 'frontend/src/pages/periodo/periodoPortal.ts': ['3ff8c0077bf53414f06620e8d6a545a027d88587a5701132462ae2340b0619df'], 'tests/test_relatorio_periodo_d35.py': ['4d3e5a659815d121cdf466b23e26df322e21286db753257f1073de8061f0016d'], 'D36_CONTRATO_RELATORIO_EMPRESAS.txt': ['af900f57dd64409c244da20ea2417d39a9eb9d20992739fabf830503bc2f428d'], 'backend/app/api/rotas/relatorio_empresas.py': ['225efaa3e2fb99aaa89f4cfc053a6b29b03f4ea39a85c7b13477641b91cbad61'], 'backend/app/schemas/relatorio_empresas.py': ['4e76d3d6ef778ddf80a093e52f78209526e29c92c9dba60e74cbd7628b410df2'], 'backend/app/services/relatorio_empresas.py': ['ffa5df1f91dc6f8b6758e65aa49f41b17c732e9192eaabfa7e7853788833db66'], 'frontend/src/pages/empresas/RelatorioEmpresas.css': ['d86d463385bbb705da95755979e43a1b8db3c7efb71eaee2e7ec4bff28f03a57'], 'frontend/src/pages/empresas/RelatorioEmpresasPage.tsx': ['58785b939e6bb476c69934d2a5fece088224dd26ee18e259a5b2dfc3c2afafc0'], 'frontend/src/pages/empresas/empresasPortal.ts': ['697ab17c48bf729c96d7838e5ffb633aa8efea3c5da47c8e593d6be012f2ea0b'], 'tests/test_relatorio_empresas_d36.py': ['de7106423af5dceec98cdc4d9d84ab8e022191a4d655e0029e85fd4443e50140'], 'D37_CONTRATO_CENTRAL_PENDENCIAS.txt': ['a14a181f67b0df05bcd7e71f451170e6a74eb2041e913875f3342c6c90b53757'], 'backend/app/api/rotas/central_pendencias.py': ['78e947cb062b81cc6af4ba40d261d9bbaefb440fec11d01171d9e5ba09a12cc7'], 'backend/app/schemas/central_pendencias.py': ['7326f459a0a70cd54048620e464731ea53cb4a4a17cd03450a49a52e53e08711'], 'backend/app/services/central_pendencias.py': ['1865833db3b34606b869ef8eb9b1fe32ad0c52aa4337a8fc015734d256296963'], 'frontend/src/pages/pendencias/CentralPendencias.css': ['f7faf8ed21d8660e06a25921b8636824f7e4613f6382419a084c8b7712cace80'], 'frontend/src/pages/pendencias/CentralPendenciasPage.tsx': ['f72bb5826fd226903e7be0788d2dcfe91e4b62db109d366506e232b1d720867c'], 'frontend/src/pages/pendencias/pendenciasPortal.ts': ['93b74cc9d977c80f6b77bc237fa281c254f6e233d3b4bcec9e083d3a9b55cbe4'], 'tests/test_central_pendencias_d37.py': ['a476ed08c728ddd3fcc405f305e9a58c32e3559e8265a00ae55a0079500f5d47'], 'D38_CONTRATO_RESUMO_GERENCIAL.txt': ['346685fa01bd3721879f7aff20cdc51665c979a9e5aa3d4153b7c037d2536622'], 'backend/app/api/rotas/resumo_gerencial.py': ['66cd246932992d32fbd12f9e67ed5178d7f79c15f9e58464c53d6b72b24f7df2'], 'backend/app/schemas/resumo_gerencial.py': ['aa51ebaaae32057c7e3779616eafdf2187a4874ae9738c36cb95b19beb0c4108'], 'backend/app/services/resumo_gerencial.py': ['0bbae5c14ed90e6722975181615ccc8dea76240616f81f1d1827f967a68700ca'], 'frontend/src/pages/gerencial/ResumoGerencial.css': ['6f79a62aaa42ab830c8a4bc6bc9d31beea3f6c535660ddcf15b2f1fb1f35dfc4'], 'frontend/src/pages/gerencial/ResumoGerencialPage.tsx': ['ffee2d228632e804024fa109d20c39bf6dec6abee05ac2e2344415bdc4bb32db'], 'frontend/src/pages/gerencial/gerencialPortal.ts': ['fe6c0ec330f0382fb014b3844bf0402fb6edb8e1b973ce7a2d8d4614f3b8de5a'], 'tests/test_resumo_gerencial_d38.py': ['49b35f87181bcf9e244f716b8c477eeb94c2397cbf214f5644425b906748f22f'], 'D38_FIX1_VER_MES_VISIVEL.txt': ['2391ed33d03302cdfd92171d9475274137d7b4e395c1bf899e24f6c403d5a705'], 'D39_CONTRATO_COMPARATIVO_GERENCIAL.txt': ['6a11efb401c00060a517510397edd6d6573621c1a6c65232b32eb781cf052efd'], 'backend/app/api/rotas/comparativo_gerencial.py': ['e4d7059ba75fc9d7f2ccbe750409675387746d62d6bd1a660c704956e0a6a605'], 'backend/app/schemas/comparativo_gerencial.py': ['e0c13912101874f2dc33912dea785992fd5e0e3949e4847eeb058a695ed01851'], 'backend/app/services/comparativo_gerencial.py': ['924072496b95bfa6ad235791cdf20d34a6075a67e55f3e886ae391f795106001'], 'frontend/src/pages/comparativo/ComparativoGerencial.css': ['969607ede26920ab36a78a6f7b422fb3de3d7ecc5f655cccc2baafe7c8388229'], 'frontend/src/pages/comparativo/ComparativoGerencialPage.tsx': ['34f149d93ee48562d1a6f42f313db422aaf80c7a89fd0b21e06c1078626e6887'], 'frontend/src/pages/comparativo/comparativoPortal.ts': ['654292aef1729e1449a58d54e6a9d830ccf78aac3321798c6098fd3d2bb9aeda'], 'tests/test_comparativo_gerencial_d39.py': ['fb5d10189e887ddbcc6068d05583ea98f2b10aa883b51d6490dd9c6f5ad55764'], 'D40_CONTRATO_EXTRATO_FINANCEIRO.txt': ['be535b740022b1bbaee6cf2287681762ebdf942fe4645b2027c111e0f601496a'], 'backend/app/api/rotas/extrato_financeiro.py': ['48c15f895665057302c4770e2500ec16d0e3cec664f8ca66e67469ae214543ee'], 'backend/app/schemas/extrato_financeiro.py': ['b2728c060f3c95dd4c793b314bf0605fd3fd6a226a6cdb25d90237cb5c3b4e24'], 'backend/app/services/extrato_financeiro.py': ['1bd9476755156adbfcaa8606443fa0c8d8c3a3fc57775f74ffe5a427f5e3fdcf'], 'frontend/src/pages/extrato/ExtratoFinanceiro.css': ['0a0284f29ca75a05d60e60c73eafbbc59f0262ac311f1e915f4cb5d3a1419bd9'], 'frontend/src/pages/extrato/ExtratoFinanceiroPage.tsx': ['aefb8802f6db300c8ec328f02097b988559f387a13c596a1694acb9592e56480'], 'frontend/src/pages/extrato/extratoPortal.ts': ['fe04c26177109b4346c563db25be32c49c41dd020c3ca5c0703df682a52a3c86'], 'tests/test_extrato_financeiro_d40.py': ['c9fb8d4172c45c6772659c2e4af0cfe5e406d6d0d9cd02ac1bc87e3c8296576c']}

ROTEIRO = 'MEC-Serviços D41 — Consolidação e recuperação de backup\n\nEXECUÇÃO:\n1. Salve MEC_SERVICOS_V0_1_D41_CONSOLIDACAO_BACKUP.py na raiz do MEC.\n2. Pare o backend com Ctrl+C. Execute o script com a .venv do MEC.\n3. Aguarde RESULTADO=OK. A saída mostra o diretório do pacote recuperável,\n   a integridade, a recuperação isolada e a preservação dos dois bancos.\n4. Reinicie MEC_SERVICOS_INICIAR_TESTE_LOCAL.py e atualize com Ctrl+F5.\n\nO D41 não altera fontes do backend/frontend nem registra operações de negócio.\nConfere a instalação D40 e as evidências de pytest/build dessa instalação.\nNão repete a suíte inteira quando os fontes não mudaram. Executa um ensaio\nnovo em uma cópia: recupera arquivos e bancos, inicia a aplicação com\nTestClient e verifica leituras e permissões administrativas e dos portais.\nAs contas temporárias do ensaio existem apenas na cópia descartável. Contas,\nsenhas, sessões, modo de teste e histórico dos bancos originais permanecem.\n\nPACOTE:\n- Bancos de negócio e acesso copiados pela API de backup SQLite.\n- Backend, frontend/src, frontend/public, build frontend/dist, configurações do frontend,\n  dependências declaradas, documentos e scripts/relatórios MEC da raiz.\n- Arquivos físicos de storage/arquivos_tecnicos, inclusive os já existentes.\n- MANIFESTO.json com caminho relativo, tamanho e SHA-256 de cada arquivo,\n  estrutura completa, quantidades e impressões digitais lógicas dos bancos.\n- LEIA_RECUPERACAO.txt com a abrangência e as condições de recuperação.\n- O pacote só recebe validado=true após passar pelas verificações e pelo\n  ensaio. Falha/interrupção deixa um pacote incompleto, que não é aprovado.\n- Pastas anteriores são preservadas; cada execução cria um pacote novo.\n- A pasta .venv, node_modules e o histórico Git não integram o pacote.\n  As dependências devem ser reinstaladas a partir das declarações incluídas.\n- A aplicação e os dois bancos devem ser recuperados juntos. Caminhos\n  originais são registrados; referências de arquivos técnicos podem ser\n  absolutas e exigem a mesma raiz original em uma recuperação real.\n\nVERIFICAR UM PACOTE NOVAMENTE:\nExecute o mesmo script com --verificar-backup e o caminho completo da pasta\ndo pacote. Essa opção verifica arquivos, integridade e conteúdo lógico dos\nbancos e recupera uma cópia temporária para comparação, sem depender dos\nbancos originais. Não sobrescreve a aplicação nem restaura os bancos em uso.\nUma recuperação real deve ser feita com o backend parado e preservando\nprimeiro a instalação atual. Este script ensaia a recuperação isoladamente.\n\nHOMOLOGAÇÃO MANUAL DA PRIMEIRA VERSÃO — registrar OK/pendência e evidência:\n1. Acesso: administrador, cliente e fornecedor; login normal, troca de senha,\n   troca de perfil local e vínculo da empresa corretos.\n2. Novo serviço: solicitação com arquivo técnico, oportunidade do fornecedor,\n   envio/aceite de cotação e contratação sem duplicidade.\n3. Execução: criação da OS, recebimento/encaminhamento de material, etapas de\n   produção, coleta, recebimento, avaliação e entrega ao cliente.\n4. Retrabalho: reprovação, encaminhamento, nova produção/coleta e nova\n   conferência antes de concluir. Histórico anterior permanece disponível.\n5. Financeiro manual: recebimento parcial, correção por estorno, recebimento\n   restante, repasse após entrega, encerramento e reabertura justificada.\n6. Cancelamento e permissões: ações fora da etapa devem ser recusadas;\n   cliente/fornecedor consultam apenas os próprios recursos.\n7. Consultas: Dashboard, relatórios D34-D36, pendências, Ver mês, comparativo\n   A/B, extrato D40, CSV e impressão coerentes com os registros existentes.\n8. Mais de uma empresa/serviço: confirmar que os dados e saldos não se misturam\n   e que paginação não limita os totais/CSV.\n\nCONTROLE EXISTENTE:\nA contratação #1 / OS #3 foi conferida nas telas como concluída e com financeiro\nencerrado. Extrato: bruto recebido R$ 13.750,00; estorno R$ 1.250,00; líquido\nrecebido R$ 12.500,00; líquido repassado R$ 12.500,00; resultado R$ 0,00.\nEssa referência é para conferência. D41 não exige esses IDs/valores em outra\nbase, não cria demonstrações e não modifica registros para atingir um total.\n\nCONCLUSÃO:\nA estimativa anterior de aproximadamente 80% refere-se à versão funcional\nlocal. RESULTADO=OK do D41 comprova as verificações técnicas descritas acima;\nnão substitui a homologação manual de todos os fluxos nem a preparação de\npublicação, configuração e acompanhamento em produção. MEC e CGX seguem\ntotalmente independentes. Integração bancária automática não integra o D41.\n'

ENSAIO = '"""Executado somente dentro da cópia recuperada D41."""\nimport json\nimport os\nfrom pathlib import Path\nimport secrets\nimport sqlite3\nimport sys\nfrom contextlib import closing\n\norigem = Path.cwd().resolve()\nraiz = Path(sys.argv[1]).resolve()\nassert raiz != origem and raiz.is_dir(), "Ensaio deve usar uma cópia diferente da instalação original."\nnegocio, acesso = raiz / "bancos/negocio.db", raiz / "bancos/acessos.db"\nassert negocio.is_file() and acesso.is_file()\nos.chdir(raiz / "aplicacao")\nsys.path[:] = [str(Path.cwd()), *[p for p in sys.path if p and Path(p).resolve() != origem]]\nos.environ.update(MEC_URL_BANCO_DADOS="sqlite:///" + negocio.as_posix(), MEC_ACESSOS_DB=str(acesso),\n    MEC_MODO_TESTE_LOCAL="0", MEC_AMBIENTE="teste", MEC_COOKIE_SEGURO="0")\nfrom backend.app.core import configuracao\nfrom backend.app.database.sessao import engine\nfrom backend.app.core.armazenamento_acesso import ArmazenamentoAcesso\nfrom backend.app.principal import criar_aplicacao\nfrom fastapi.testclient import TestClient\n\nassert Path(configuracao.__file__).resolve().is_relative_to(Path.cwd())\nassert Path(engine.url.database).resolve() == negocio\nassert Path(os.environ["MEC_ACESSOS_DB"]).resolve() == acesso\nsenha = secrets.token_urlsafe(24)\noperadores = ArmazenamentoAcesso(acesso)\nwith closing(sqlite3.connect(negocio)) as banco:\n    clientes = [r[0] for r in banco.execute("SELECT id FROM empresas WHERE tipo_empresa IN (\'cliente\',\'ambos\') ORDER BY id LIMIT 1")]\n    fornecedores = [r[0] for r in banco.execute("SELECT id FROM empresas WHERE tipo_empresa IN (\'fornecedor\',\'ambos\') ORDER BY id LIMIT 1")]\n    antes = banco.iterdump(); negocio_antes = list(antes)\nperfis = [("admin", None)] + ([("cliente", clientes[0])] if clientes else []) + ([("fornecedor", fornecedores[0])] if fornecedores else [])\ncontas = {}\nfor perfil, empresa in perfis:\n    email = "ensaio-" + secrets.token_hex(10) + "@d41.local"\n    operadores.criar_usuario("Ensaio isolado D41", email, perfil, empresa, senha, deve_alterar_senha=False)\n    contas[perfil] = (email, empresa)\n\nrotas = ["/administracao/painel", "/administracao/financeiro/contratacoes", "/administracao/relatorios/periodo",\n    "/administracao/relatorios/empresas", "/administracao/pendencias", "/administracao/relatorios/gerencial",\n    "/administracao/relatorios/comparativo", "/administracao/financeiro/extrato"]\nverificacoes, avisos = [], []\nwith TestClient(criar_aplicacao()) as http:\n    def conferir(nome, rota, esperado, params=None):\n        r = http.get("/api/v1" + rota, params=params or {})\n        if r.status_code != esperado:\n            raise RuntimeError(nome + ": HTTP " + str(r.status_code) + ", esperado " + str(esperado))\n        verificacoes.append({"verificacao": nome, "http": r.status_code})\n        print("ENSAIO_OK=" + nome + " HTTP=" + str(r.status_code), flush=True)\n    conferir("Saúde da aplicação recuperada", "/saude", 200)\n    conferir("Saúde do banco recuperado", "/banco-dados/saude", 200)\n    for rota in rotas:\n        conferir("Sessão ausente recusada " + rota, rota, 401)\n    for perfil, (email, empresa) in contas.items():\n        http.cookies.clear()\n        r = http.post("/api/v1/autenticacao/entrar", json={"email": email, "senha": senha})\n        assert r.status_code == 200, "Acesso real da cópia não funcionou: " + perfil\n        verificacoes.append({"verificacao": "Acesso real da cópia " + perfil, "http": 200})\n        print("ENSAIO_OK=Acesso real " + perfil, flush=True)\n        for rota in rotas:\n            params = {"data_inicial": "", "data_final": ""} if rota.endswith("extrato") else {}\n            conferir(perfil + " " + rota, rota, 200 if perfil == "admin" else 403, params)\n        if perfil != "admin":\n            campo = "empresa_cliente_id" if perfil == "cliente" else "empresa_fornecedora_id"\n            prefixo = "/portal-" + perfil\n            for recurso in ("contratacoes", "financeiro"):\n                conferir(perfil + " próprio " + recurso, prefixo + "/" + recurso, 200, {campo: empresa})\n            conferir(perfil + " empresa divergente recusada", prefixo + "/financeiro", 403, {campo: empresa + 1000000})\n    if not clientes:\n        avisos.append("Sem empresa cliente: ensaio desse perfil pendente.")\n    if not fornecedores:\n        avisos.append("Sem empresa fornecedora: ensaio desse perfil pendente.")\nwith closing(sqlite3.connect(negocio)) as banco:\n    assert list(banco.iterdump()) == negocio_antes, "Leituras alteraram o banco de negócio da cópia."\nengine.dispose()\nresultado = {"resultado": "OK", "verificacoes": verificacoes, "avisos": avisos,\n    "perfis_verificados": list(contas), "operacoes_negocio_executadas": False, "contas_temporarias_somente_na_copia": True}\n(raiz / "ENSAIO_API.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")\nprint("ENSAIO_API_ISOLADO_OK=True", flush=True)\n'

TABELAS_D31 = ('ciclos_intermediacao', 'eventos_intermediacao')

DDL_TABELAS = {'ciclos_intermediacao': "CREATE TABLE ciclos_intermediacao (\n\tid INTEGER NOT NULL, \n\tordem_servico_id INTEGER NOT NULL, \n\tstatus VARCHAR(40) NOT NULL, \n\tversao INTEGER NOT NULL, \n\tultima_etapa_coleta_id INTEGER NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tatualizado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_ciclo_intermediacao_ordem UNIQUE (ordem_servico_id), \n\tCONSTRAINT ck_ciclo_intermediacao_versao CHECK (versao > 0), \n\tCONSTRAINT ck_ciclo_intermediacao_status CHECK (status IN ('aguardando_material','material_recebido','material_encaminhado','coleta_solicitada','pecas_recebidas','em_avaliacao','retrabalho','retrabalho_encaminhado','aprovado_para_entrega','entregue_cliente','cancelado')), \n\tFOREIGN KEY(ordem_servico_id) REFERENCES ordens_servico (id) ON DELETE RESTRICT\n)", 'eventos_intermediacao': 'CREATE TABLE eventos_intermediacao (\n\tid INTEGER NOT NULL, \n\tciclo_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(40) NOT NULL, \n\tstatus_anterior VARCHAR(40), \n\tstatus_resultante VARCHAR(40) NOT NULL, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\treferencia VARCHAR(200), \n\tparecer_tecnico TEXT, \n\tquantidade_conferida INTEGER, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_evento_intermediacao_versao UNIQUE (ciclo_id, versao), \n\tFOREIGN KEY(ciclo_id) REFERENCES ciclos_intermediacao (id) ON DELETE RESTRICT\n)'}

SCHEMA_D31 = {'ciclos_intermediacao': [('id', 'INTEGER', True, True), ('ordem_servico_id', 'INTEGER', True, False), ('status', 'VARCHAR(40)', True, False), ('versao', 'INTEGER', True, False), ('ultima_etapa_coleta_id', 'INTEGER', True, False), ('criado_em', 'VARCHAR(40)', True, False), ('atualizado_em', 'VARCHAR(40)', True, False)], 'eventos_intermediacao': [('id', 'INTEGER', True, True), ('ciclo_id', 'INTEGER', True, False), ('versao', 'INTEGER', True, False), ('acao', 'VARCHAR(40)', True, False), ('status_anterior', 'VARCHAR(40)', False, False), ('status_resultante', 'VARCHAR(40)', True, False), ('usuario_admin_id', 'INTEGER', True, False), ('administrador_nome', 'VARCHAR(120)', True, False), ('registro_interno', 'TEXT', True, False), ('referencia', 'VARCHAR(200)', False, False), ('parecer_tecnico', 'TEXT', False, False), ('quantidade_conferida', 'INTEGER', False, False), ('criado_em', 'VARCHAR(40)', True, False)]}

DDL_D32 = {'controles_financeiros_admin': "CREATE TABLE controles_financeiros_admin (\n\tcontratacao_id INTEGER NOT NULL, \n\tvalor_contratado_centavos INTEGER NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tversao INTEGER NOT NULL, \n\tcriado_em VARCHAR(40) NOT NULL, \n\tatualizado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (contratacao_id), \n\tCONSTRAINT ck_financeiro_valor CHECK (valor_contratado_centavos > 0), \n\tCONSTRAINT ck_financeiro_versao CHECK (versao > 0), \n\tCONSTRAINT ck_financeiro_status CHECK (status IN ('aberto','encerrado')), \n\tFOREIGN KEY(contratacao_id) REFERENCES contratacoes_servico (id) ON DELETE RESTRICT\n)", 'repasses_administrativos': "CREATE TABLE repasses_administrativos (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tvalor_centavos INTEGER NOT NULL, \n\tforma_pagamento VARCHAR(20) NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\tregistrado_em VARCHAR(40) NOT NULL, \n\testornado_em VARCHAR(40), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_repasse_valor CHECK (valor_centavos > 0), \n\tCONSTRAINT ck_repasse_status CHECK (status IN ('confirmado','estornado')), \n\tFOREIGN KEY(contratacao_id) REFERENCES controles_financeiros_admin (contratacao_id) ON DELETE RESTRICT\n)", 'eventos_financeiros_admin': 'CREATE TABLE eventos_financeiros_admin (\n\tid INTEGER NOT NULL, \n\tcontratacao_id INTEGER NOT NULL, \n\tversao INTEGER NOT NULL, \n\tacao VARCHAR(32) NOT NULL, \n\tchave_operacao VARCHAR(36), \n\tresumo_operacao VARCHAR(64), \n\tpagamento_id INTEGER, \n\trepasse_id INTEGER, \n\tvalor_centavos INTEGER, \n\tusuario_admin_id INTEGER NOT NULL, \n\tadministrador_nome VARCHAR(120) NOT NULL, \n\tregistro_interno TEXT NOT NULL, \n\treferencia VARCHAR(200), \n\tcriado_em VARCHAR(40) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_financeiro_evento_versao UNIQUE (contratacao_id, versao), \n\tCONSTRAINT uq_financeiro_chave UNIQUE (contratacao_id, chave_operacao), \n\tCONSTRAINT uq_financeiro_referencia UNIQUE (contratacao_id, referencia), \n\tFOREIGN KEY(contratacao_id) REFERENCES controles_financeiros_admin (contratacao_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(pagamento_id) REFERENCES pagamentos_contratacao (id) ON DELETE RESTRICT, \n\tFOREIGN KEY(repasse_id) REFERENCES repasses_administrativos (id) ON DELETE RESTRICT\n)'}

INDICES_D32 = {'ix_repasses_administrativos_contratacao_id': 'CREATE INDEX ix_repasses_administrativos_contratacao_id ON repasses_administrativos (contratacao_id)', 'ix_eventos_financeiros_admin_contratacao_id': 'CREATE INDEX ix_eventos_financeiros_admin_contratacao_id ON eventos_financeiros_admin (contratacao_id)'}

SCHEMA_D32 = {'controles_financeiros_admin': [('contratacao_id', 'INTEGER', True, True), ('valor_contratado_centavos', 'INTEGER', True, False), ('status', 'VARCHAR(16)', True, False), ('versao', 'INTEGER', True, False), ('criado_em', 'VARCHAR(40)', True, False), ('atualizado_em', 'VARCHAR(40)', True, False)], 'repasses_administrativos': [('id', 'INTEGER', True, True), ('contratacao_id', 'INTEGER', True, False), ('valor_centavos', 'INTEGER', True, False), ('forma_pagamento', 'VARCHAR(20)', True, False), ('status', 'VARCHAR(16)', True, False), ('registrado_em', 'VARCHAR(40)', True, False), ('estornado_em', 'VARCHAR(40)', False, False)], 'eventos_financeiros_admin': [('id', 'INTEGER', True, True), ('contratacao_id', 'INTEGER', True, False), ('versao', 'INTEGER', True, False), ('acao', 'VARCHAR(32)', True, False), ('chave_operacao', 'VARCHAR(36)', False, False), ('resumo_operacao', 'VARCHAR(64)', False, False), ('pagamento_id', 'INTEGER', False, False), ('repasse_id', 'INTEGER', False, False), ('valor_centavos', 'INTEGER', False, False), ('usuario_admin_id', 'INTEGER', True, False), ('administrador_nome', 'VARCHAR(120)', True, False), ('registro_interno', 'TEXT', True, False), ('referencia', 'VARCHAR(200)', False, False), ('criado_em', 'VARCHAR(40)', True, False)]}

def sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()

def localizar_raiz() -> Path:
    for raiz in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        if (raiz / "backend/app/principal.py").is_file() and (raiz / "frontend/package.json").is_file():
            return raiz
    raise RuntimeError("Salve e execute este arquivo na raiz C:\\Users\\Omega\\Desktop\\MEC-Servicos.")

def seguro(raiz: Path, relativo: str) -> Path:
    alvo = raiz / relativo
    if alvo.is_symlink() or any(p.is_symlink() for p in alvo.parents if p != raiz and raiz in p.parents):
        raise RuntimeError("Destino simbólico preservado: " + relativo)
    if not alvo.resolve().is_relative_to(raiz): raise RuntimeError("Destino fora do projeto.")
    return alvo

def executar_git(raiz: Path, *args: str) -> str:
    git = shutil.which("git")
    if not git: raise RuntimeError("Git não encontrado.")
    r = subprocess.run([git, *args], cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if r.returncode: raise RuntimeError("Não foi possível conferir o projeto com Git.")
    return r.stdout.strip()

def origem_mec(url: str) -> bool:
    if url.startswith("git@github.com:"): caminho = url.split(":", 1)[1]
    else:
        p = urlsplit(url)
        if p.scheme not in {"https", "ssh"} or p.hostname != "github.com" or (p.scheme == "https" and (p.username or p.password)):
            return False
        caminho = p.path.lstrip("/")
    return caminho.lower().rstrip("/").removesuffix(".git") == "projetoxcadcam-byte/mec-servicos"

def fonte_confere(dados: bytes, esperado: str) -> bool:
    normal = dados.replace(b"\r\n", b"\n")
    return esperado in {sha(dados), sha(normal), sha(normal.replace(b"\n", b"\r\n"))}

def exigir_backend_parado() -> None:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
            pass
    except OSError:
        return
    raise RuntimeError("A porta 8000 está em uso. Pare o backend com Ctrl+C no terminal dele antes de executar o D41.")

def configuracao_bancos(raiz: Path):
    sys.path.insert(0, str(raiz))
    from backend.app.core.configuracao import configuracoes
    if configuracoes.prefixo_api.rstrip("/") != "/api/v1": raise RuntimeError("Confira o prefixo /api/v1.")
    url = configuracoes.url_banco_dados
    if not url.startswith("sqlite:///"): raise RuntimeError("O D41 foi preparado para o banco SQLite local.")
    banco = conferir_banco_local(raiz, Path(url[len("sqlite:///"):]))
    if not banco.is_file() or not banco.is_relative_to(raiz): raise RuntimeError("Banco de negócio local não encontrado.")
    acesso = Path(os.environ.get("MEC_ACESSOS_DB", str(raiz / "data/mec_acessos.db")))
    acesso = conferir_banco_local(raiz, acesso)
    if not acesso.is_file() or not acesso.is_relative_to(raiz): raise RuntimeError("Banco de acesso D30 local não encontrado.")
    if acesso == banco: raise RuntimeError("O banco de acesso deve ser separado do banco de negócio.")
    with closing(sqlite3.connect(acesso.as_uri() + "?mode=ro", uri=True)) as c:
        c.execute("PRAGMA query_only=ON")
        if not c.execute("SELECT COUNT(*) FROM usuarios_acesso WHERE perfil='admin' AND ativo=1").fetchone()[0]:
            raise RuntimeError("Não foi encontrado administrador ativo no banco de acesso.")
    return banco, acesso

def identidade_sql(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'

def conferir_schema(conexao):
    existem = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    presentes = existem.intersection(TABELAS_D31)
    if presentes and presentes != set(TABELAS_D31): raise RuntimeError("Estrutura D31 parcial encontrada; banco preservado.")
    if not presentes: return False
    for nome, esperado in SCHEMA_D31.items():
        atual = [(l[1], l[2].upper(), bool(l[3]), bool(l[5])) for l in conexao.execute("PRAGMA table_info(" + identidade_sql(nome) + ")")]
        if atual != [tuple(l) for l in esperado]: raise RuntimeError("Estrutura D31 divergente; banco preservado: " + nome)
        sql = conexao.execute("SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (nome,)).fetchone()[0]
        if "".join(sql.split()).lower() != "".join(DDL_TABELAS[nome].strip().split()).lower():
            raise RuntimeError("Restrições D31 divergentes; banco preservado: " + nome)
    return True

def salvar_relatorio(raiz: Path, relatorio):
    conteudo = json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n"
    for extensao in ("json", "txt"):
        alvo = seguro(raiz, STEM + "." + extensao)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=raiz, delete=False, prefix="mec_d41_relatorio_") as temp:
            temp.write(conteudo); caminho = Path(temp.name)
        try: os.replace(caminho, alvo)
        finally: caminho.unlink(missing_ok=True)
        print(("JSON=" if extensao == "json" else "RELATORIO=") + str(alvo), flush=True)

def gravar_atomico(alvo: Path, conteudo: bytes) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=alvo.parent, delete=False, prefix="mec_d41_") as temp:
        temp.write(conteudo)
        caminho = Path(temp.name)
    try:
        os.replace(caminho, alvo)
    finally:
        caminho.unlink(missing_ok=True)

def conferir_schema_d32(conexao):
    tabelas = {n for (n,) in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    presentes = tabelas.intersection(DDL_D32)
    if presentes and presentes != set(DDL_D32):
        raise RuntimeError("Estrutura D32 parcial; banco preservado.")
    if not presentes: return False
    def normal(sql): return "".join(sql.split()).lower()
    for nome, ddl in DDL_D32.items():
        atual = [(l[1],l[2].upper(),bool(l[3]),bool(l[5])) for l in conexao.execute("PRAGMA table_info("+identidade_sql(nome)+")")]
        if atual != [tuple(l) for l in SCHEMA_D32[nome]]:
            raise RuntimeError("Colunas D32 divergentes; banco preservado: " + nome)
        sql = conexao.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(nome,)).fetchone()[0]
        if normal(sql) != normal(ddl): raise RuntimeError("Restrições D32 divergentes; banco preservado: " + nome)
    for nome, ddl in INDICES_D32.items():
        row = conexao.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?",(nome,)).fetchone()
        if not row or not row[0] or normal(row[0]) != normal(ddl):
            raise RuntimeError("Índice D32 divergente; banco preservado: " + nome)
    return True

def encerrar_processo(processo):
    # Somente a árvore iniciada por esta etapa; nunca todos os processos Python.
    if os.name == "nt":
        if processo.poll() is None:
            fim = subprocess.run(["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                capture_output=True, timeout=10)
            if fim.returncode and processo.poll() is None:
                raise RuntimeError("Não foi possível encerrar a etapa. Pare o processo PID " + str(processo.pid) + ".")
    else:
        try: os.killpg(processo.pid, signal.SIGTERM)
        except ProcessLookupError: pass
    try: processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt": processo.kill()
        else:
            try: os.killpg(processo.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        processo.wait(timeout=5)

def executar(raiz, rotulo, comando, ambiente, relatorio, *, limite_segundos=None, intervalo_aviso=30):
    relatorio["etapa"] = rotulo
    limite = limite_segundos if limite_segundos is not None else (1800 if rotulo == "pytest" else 600)
    print("Executando " + rotulo + "... (saída ao vivo)", flush=True)
    ambiente = {**ambiente, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    opcoes = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    log = seguro(raiz, STEM + "_" + rotulo + ".log")
    saida = []; fila = queue.Queue(); inicio = ultimo_aviso = time.monotonic(); processo = None; leitor = None
    def recolher():
        try:
            for linha in processo.stdout: fila.put(linha)
        finally: fila.put(None)
    with log.open("w", encoding="utf-8", buffering=1) as arquivo:
        def mostrar(linha):
            saida.append(linha); arquivo.write(linha); print(linha, end="", flush=True)
        try:
            processo = subprocess.Popen(comando, cwd=raiz, env=ambiente, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, **opcoes)
            leitor = threading.Thread(target=recolher, daemon=True); leitor.start()
            terminou_saida = False
            while not terminou_saida or processo.poll() is None:
                agora = time.monotonic()
                if agora - inicio >= limite:
                    raise RuntimeError("A etapa " + rotulo + " excedeu o limite de " + str(limite) + " segundos.")
                try:
                    linha = fila.get(timeout=min(1, max(.01, intervalo_aviso), max(.01, limite - (agora - inicio))))
                    if linha is None: terminou_saida = True
                    else: mostrar(linha); ultimo_aviso = time.monotonic()
                except queue.Empty:
                    agora = time.monotonic()
                    if agora - ultimo_aviso >= intervalo_aviso:
                        mostrar("[" + rotulo + "] Em execução há " + str(int(agora - inicio)) + " segundos.\n")
                        ultimo_aviso = agora
            codigo = processo.wait()
            relatorio[rotulo] = {"return_code": codigo, "saida": "".join(saida), "log": str(log),
                "duracao_segundos": round(time.monotonic() - inicio, 2)}
            print(rotulo.upper() + "_RETURN_CODE=" + str(codigo), flush=True)
            if codigo: raise RuntimeError("A etapa " + rotulo + " falhou; confira o relatório.")
        except (Exception, KeyboardInterrupt) as erro:
            if processo is not None: encerrar_processo(processo)
            if leitor is not None: leitor.join(timeout=2)
            while not fila.empty():
                linha = fila.get_nowait()
                if linha is not None: mostrar(linha)
            relatorio[rotulo] = {"return_code": processo.poll() if processo is not None else None,
                "saida": "".join(saida), "log": str(log), "erro": str(erro) or "Operação interrompida.",
                "duracao_segundos": round(time.monotonic() - inicio, 2)}
            raise
        finally:
            if processo is not None and processo.stdout is not None: processo.stdout.close()

"""Rotinas D41. Somente a pasta de backup, o roteiro e os relatórios recebem gravações."""

NOME_SCRIPT = "MEC_SERVICOS_V0_1_D41_CONSOLIDACAO_BACKUP.py"
NOME_ROTEIRO = "D41_ROTEIRO_HOMOLOGACAO.txt"
PASTAS = ("backend", "frontend/src", "frontend/public", "frontend/dist", "tests", "storage/arquivos_tecnicos")
IGNORAR = {"__pycache__", ".pytest_cache", "node_modules", ".git"}


def vinculo(p):
    if p.is_symlink() or bool(getattr(p, "is_junction", lambda: False)()): return True
    if os.name == "nt":
        try: return getattr(p.lstat(), "st_reparse_tag", 0) == 0xA0000003
        except FileNotFoundError: return False
    return False


def caminho_pacote(raiz, nome):
    if (not isinstance(nome, str) or not nome or "\\" in nome or ":" in nome or "\x00" in nome
            or nome.startswith("/") or any(p in {"", ".", ".."} for p in nome.split("/"))):
        raise RuntimeError("Caminho inválido no pacote de recuperação.")
    alvo = seguro(raiz, nome)
    for pasta in (alvo, *alvo.parents):
        if pasta == raiz: break
        if vinculo(pasta): raise RuntimeError("Vínculo preservado no pacote: " + nome)
    return alvo


def conferir_banco_local(raiz, bruto):
    p = bruto if bruto.is_absolute() else raiz / bruto
    try: nome = p.relative_to(raiz).as_posix()
    except ValueError: raise RuntimeError("Banco configurado fora do projeto; preservado.") from None
    p = caminho_pacote(raiz, nome)
    if not p.is_file(): raise RuntimeError("Banco local configurado não encontrado.")
    return p.resolve()


def sha_arquivo(p):
    digest = hashlib.sha256()
    with p.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def fotografia(banco):
    with closing(sqlite3.connect(banco.as_uri() + "?mode=ro", uri=True, timeout=10)) as c:
        c.execute("PRAGMA query_only=ON"); c.execute("BEGIN")
        if list(c.execute("PRAGMA integrity_check")) != [("ok",)]:
            raise RuntimeError("Integridade SQLite não confirmada: " + banco.name)
        if c.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("Vínculos SQLite não confirmados: " + banco.name)
        estrutura = list(c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
        tabelas, ultimo = {}, time.monotonic()
        def valor(v):
            if isinstance(v, bytes): return {"binario": v.hex()}
            if isinstance(v, float): return {"real": v.hex()}
            return v
        for tipo, nome, _, sql in estrutura:
            if tipo != "table": continue
            linhas = [json.dumps([valor(v) for v in l], ensure_ascii=False, separators=(",", ":"))
                      for l in c.execute("SELECT * FROM " + identidade_sql(nome))]
            tabelas[nome] = {"quantidade": len(linhas), "sha256": sha(json.dumps([sql, sorted(linhas)], ensure_ascii=False).encode())}
            if time.monotonic() - ultimo >= 30:
                print("[conferência] Tabelas verificadas: " + str(len(tabelas)), flush=True); ultimo = time.monotonic()
        return {"estrutura_sha256": sha(json.dumps(estrutura, ensure_ascii=False).encode()), "tabelas": tabelas}


def conferir_fontes(raiz):
    for nome, hashes in BASE_SHA256.items():
        p = caminho_pacote(raiz, nome)
        if not p.is_file() or not any(fonte_confere(p.read_bytes(), h) for h in hashes):
            raise RuntimeError("Fonte diferente da base D40 conhecida; preservado: " + nome)
    rel = caminho_pacote(raiz, "MEC_SERVICOS_V0_1_D40_EXTRATO_FINANCEIRO_RELATORIO.json")
    if not rel.is_file(): raise RuntimeError("Relatório D40 não encontrado; conclua o D40 antes do D41.")
    dados = json.loads(rel.read_text(encoding="utf-8-sig"))
    if (dados.get("revision") != D40_REVISION or dados.get("resultado") != "OK"
            or dados.get("validacao_backend_e_frontend") is not True
            or any(type(dados.get(n, {}).get("return_code")) is not int or dados[n]["return_code"] != 0 for n in ("pytest", "npm_build"))):
        raise RuntimeError("Evidências de testes/build do D40 não confirmadas.")
    return {"revision": dados["revision"], "resultado": "OK", "pytest_return_code": 0, "npm_build_return_code": 0}


def conferir_contas(negocio, acesso):
    with closing(sqlite3.connect(negocio.as_uri() + "?mode=ro", uri=True)) as c:
        empresas = dict(c.execute("SELECT id,tipo_empresa FROM empresas"))
    with closing(sqlite3.connect(acesso.as_uri() + "?mode=ro", uri=True)) as c:
        contas = list(c.execute("SELECT id,perfil,empresa_id,ativo,trocar_senha FROM usuarios_acesso"))
    ativos = {"admin": 0, "cliente": 0, "fornecedor": 0}
    for uid, perfil, empresa, ativo, trocar in contas:
        if perfil not in ativos or ativo not in {0, 1} or trocar not in {0, 1}:
            raise RuntimeError("Conta com dados inconsistentes; preservada: usuário #" + str(uid))
        if not ativo: continue
        if (perfil == "admin" and empresa is not None) or (perfil != "admin" and empresas.get(empresa) not in {perfil, "ambos"}):
            raise RuntimeError("Vínculo de empresa de conta ativa não confirmado: usuário #" + str(uid))
        ativos[perfil] += 1
    if not ativos["admin"]: raise RuntimeError("Administrador ativo não encontrado.")
    return {"total": len(contas), "ativos_por_perfil": ativos, "vinculos_ativos_confirmados": True}


def conferir_arquivos_tecnicos(raiz, negocio):
    with closing(sqlite3.connect(negocio.as_uri() + "?mode=ro", uri=True)) as c:
        arquivos = list(c.execute("SELECT id,caminho_arquivo,sha256,tamanho_bytes FROM arquivos_tecnicos WHERE ativo=1 ORDER BY id"))
    resumo = []
    for aid, caminho, esperado, tamanho in arquivos:
        bruto = Path(caminho)
        bruto = bruto if bruto.is_absolute() else raiz / bruto
        if not bruto.resolve().is_relative_to(raiz / "storage/arquivos_tecnicos"):
            raise RuntimeError("Caminho de arquivo técnico ativo não confirmado: #" + str(aid))
        nome = bruto.relative_to(raiz).as_posix()
        p = caminho_pacote(raiz, nome)
        if not p.is_file() or p.stat().st_size != tamanho or sha_arquivo(p) != esperado:
            raise RuntimeError("Arquivo físico técnico ativo ausente ou divergente: #" + str(aid))
        resumo.append({"id": aid, "arquivo": "aplicacao/" + nome, "sha256": esperado, "bytes": tamanho})
    return resumo


def catalogo(raiz, bancos):
    nomes = set()
    excluidos = set(bancos) | {Path(str(b) + fim) for b in bancos for fim in ("-wal", "-shm", "-journal")}
    def incluir(p):
        if p in excluidos: return
        n = p.relative_to(raiz).as_posix()
        p = caminho_pacote(raiz, n)
        if p.is_file(): nomes.add(n)
    for pasta in PASTAS:
        inicio = caminho_pacote(raiz, pasta)
        if not inicio.exists(): continue
        for diretorio, subpastas, arquivos in os.walk(inicio, followlinks=False):
            base = Path(diretorio)
            for n in subpastas + arquivos:
                if vinculo(base / n): raise RuntimeError("Vínculo de arquivo/pasta preservado: " + (base / n).relative_to(raiz).as_posix())
            subpastas[:] = [n for n in subpastas if n not in IGNORAR]
            for n in arquivos:
                if not n.endswith((".pyc", ".pyo")): incluir(base / n)
    for p in raiz.iterdir():
        if ((p.name.startswith("MEC_SERVICOS") and p.suffix in {".py", ".json", ".txt"} and not p.name.startswith(STEM))
                or p.name.startswith("D") and p.suffix == ".txt"
                or p.name in {"requirements.txt", "pyproject.toml", ".env", ".env.example", "README.md"}): incluir(p)
    frontend = caminho_pacote(raiz, "frontend")
    for p in frontend.iterdir():
        if p.name in {"package.json", "package-lock.json", "index.html", ".env", ".env.local", ".env.production"} or p.name.startswith(("tsconfig", "vite.config")):
            incluir(p)
    obrigatorios = ["backend/app/principal.py", "frontend/src/App.tsx", "frontend/package.json", "frontend/dist/index.html",
        "requirements.txt", "MEC_SERVICOS_INICIAR_TESTE_LOCAL.py", NOME_SCRIPT, NOME_ROTEIRO,
        "MEC_SERVICOS_V0_1_D40_EXTRATO_FINANCEIRO_RELATORIO.json"]
    for n in obrigatorios:
        if n not in nomes: raise RuntimeError("Arquivo necessário ao pacote não encontrado: " + n)
    return {n: {"sha256": sha_arquivo(raiz / n), "bytes": (raiz / n).stat().st_size} for n in sorted(nomes)}


def conferir_build(raiz):
    from html.parser import HTMLParser
    from urllib.parse import urlsplit, unquote
    ativos = []
    class Leitor(HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "script" and a.get("src"): ativos.append(a["src"])
            if tag == "link" and a.get("rel") == "stylesheet" and a.get("href"): ativos.append(a["href"])
    p = caminho_pacote(raiz, "frontend/dist/index.html")
    if not p.is_file(): raise RuntimeError("Build frontend/dist/index.html não encontrado.")
    Leitor().feed(p.read_text(encoding="utf-8-sig"))
    if not ativos: raise RuntimeError("Build sem scripts/estilos declarados.")
    for nome in ativos:
        u = urlsplit(nome)
        if u.scheme or u.netloc: raise RuntimeError("Recurso externo no build; confira a abrangência do pacote.")
        relativo = unquote(u.path).lstrip("/")
        if not caminho_pacote(raiz, "frontend/dist/" + relativo).is_file():
            raise RuntimeError("Recurso do build ausente: " + relativo)
    return len(ativos)


def copiar_sqlite(origem, destino):
    destino.parent.mkdir(parents=True, exist_ok=True); inicio = time.monotonic()
    def progresso(status, restantes, total):
        if time.monotonic() - inicio > 120: raise RuntimeError("Backup SQLite excedeu 120 segundos.")
    with closing(sqlite3.connect(origem.as_uri() + "?mode=ro", uri=True, timeout=10)) as banco:
        with closing(sqlite3.connect(destino)) as copia: banco.backup(copia, pages=256, progress=progresso, sleep=.05)


def manifesto_valido(pacote, exigir_validado=True):
    m = json.loads(caminho_pacote(pacote, "MANIFESTO.json").read_text(encoding="utf-8"))
    if m.get("revision") != REVISION or m.get("formato") != 1 or (exigir_validado and m.get("validado") is not True):
        raise RuntimeError("Pacote D41 incompleto ou não validado.")
    arquivos = m.get("arquivos")
    if not isinstance(arquivos, dict) or not arquivos: raise RuntimeError("Lista de arquivos do pacote inválida.")
    vistos = set()
    for diretorio, subpastas, nomes in os.walk(pacote, followlinks=False):
        base = Path(diretorio)
        for n in subpastas + nomes:
            if vinculo(base / n): raise RuntimeError("Vínculo no pacote de recuperação; preservado.")
        for n in nomes:
            relativo = (base / n).relative_to(pacote).as_posix()
            if relativo != "MANIFESTO.json": vistos.add(relativo)
    if vistos != set(arquivos): raise RuntimeError("Arquivo ausente ou extra no pacote de recuperação.")
    for n, dados in arquivos.items():
        p = caminho_pacote(pacote, n)
        if not p.is_file() or p.stat().st_size != dados["bytes"] or sha_arquivo(p) != dados["sha256"]:
            raise RuntimeError("Arquivo de backup divergente: " + n)
    for nome in ("negocio", "acessos"):
        b = m["bancos"][nome]
        if b["arquivo"] != "bancos/" + nome + ".db" or fotografia(caminho_pacote(pacote, b["arquivo"])) != b["fotografia"]:
            raise RuntimeError("Conteúdo do banco recuperável não confirmado: " + nome)
    for tecnico in m["arquivos_tecnicos_ativos"]:
        p = caminho_pacote(pacote, tecnico["arquivo"])
        if p.stat().st_size != tecnico["bytes"] or sha_arquivo(p) != tecnico["sha256"]:
            raise RuntimeError("Arquivo técnico recuperável não confirmado.")
    return m


def recuperar_copia(pacote, destino, m):
    for n in m["arquivos"]:
        alvo = caminho_pacote(destino, n); alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(caminho_pacote(pacote, n), alvo)
        if sha_arquivo(alvo) != m["arquivos"][n]["sha256"]: raise RuntimeError("Recuperação de arquivo não confirmada: " + n)
    for nome in ("negocio", "acessos"):
        if fotografia(destino / "bancos" / (nome + ".db")) != m["bancos"][nome]["fotografia"]:
            raise RuntimeError("Recuperação do banco não confirmada: " + nome)


def main():
    import argparse
    argumentos = argparse.ArgumentParser(description="MEC D41: conferir, copiar e ensaiar recuperação isolada.")
    argumentos.add_argument("--verificar-backup", metavar="PASTA", help="Verifica um pacote existente e recupera somente uma cópia temporária.")
    opcoes = argumentos.parse_args()
    print("MEC-Serviços D41 — Consolidação e recuperação de backup", flush=True)
    print("REVISION=" + REVISION, flush=True)
    raiz, pacote = None, None
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapa": "inicio", "operacoes_negocio_executadas": False,
        "restauracao_na_instalacao_original": False, "tabelas_criadas_na_instalacao_original": 0}
    try:
        if sys.version_info < (3, 11): raise RuntimeError("Use a .venv do MEC com Python 3.11 ou mais recente.")
        if opcoes.verificar_backup:
            pacote = Path(opcoes.verificar_backup).absolute()
            if vinculo(pacote) or not pacote.is_dir(): raise RuntimeError("Pasta do pacote não encontrada ou simbólica.")
            pacote = pacote.resolve(); print("VERIFICANDO_BACKUP=" + str(pacote), flush=True)
            m = manifesto_valido(pacote)
            with tempfile.TemporaryDirectory(prefix="mec_d41_rever_") as pasta:
                recuperar_copia(pacote, Path(pasta), m)
            print("ARQUIVOS_E_BANCOS_DO_BACKUP_CONFERIDOS=True", flush=True)
            print("RECUPERACAO_TEMPORARIA_CONFIRMADA=True", flush=True)
            print("RESULTADO=OK", flush=True); return 0
        raiz = localizar_raiz(); print("ROOT=" + str(raiz), flush=True)
        urls = executar_git(raiz, "remote", "get-url", "--all", "origin").splitlines()
        if not urls or not all(origem_mec(u) for u in urls): raise RuntimeError("Origin não corresponde ao MEC-Servicos.")
        exigir_backend_parado(); relatorio["etapa"] = "conferir_instalacao"
        relatorio["base_d40"] = conferir_fontes(raiz)
        print("BASE_D40_CONFIRMADA=True", flush=True)
        os.chdir(raiz); negocio, acesso = configuracao_bancos(raiz)
        for p in (negocio, acesso): caminho_pacote(raiz, p.relative_to(raiz).as_posix())
        with closing(sqlite3.connect(negocio.as_uri() + "?mode=ro", uri=True)) as c:
            if not conferir_schema(c) or not conferir_schema_d32(c): raise RuntimeError("Schema D31/D32 não confirmado.")
        print("Conferindo os dois bancos e seus vínculos…", flush=True)
        anteriores = {"negocio": fotografia(negocio), "acessos": fotografia(acesso)}
        relatorio["contas"] = conferir_contas(negocio, acesso)
        tecnicos = conferir_arquivos_tecnicos(raiz, negocio)
        relatorio["arquivos_tecnicos_ativos"] = len(tecnicos)
        relatorio["recursos_build"] = conferir_build(raiz)
        roteiro = caminho_pacote(raiz, NOME_ROTEIRO)
        if roteiro.exists() and not fonte_confere(roteiro.read_bytes(), sha(ROTEIRO.encode())):
            raise RuntimeError("Roteiro D41 já existe com outro conteúdo; preservado.")
        if not roteiro.exists(): gravar_atomico(roteiro, ROTEIRO.encode())
        origem = catalogo(raiz, {negocio, acesso})
        relatorio["etapa"] = "copiar_pacote"
        pacote = caminho_pacote(raiz, "_mec_backups/D41_CONSOLIDACAO_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8])
        pacote.mkdir(parents=True, mode=0o700); relatorio["backup_dir"] = str(pacote)
        print("BACKUP_DIR=" + str(pacote), flush=True)
        arquivos = {}
        for n, dados in origem.items():
            destino = caminho_pacote(pacote, "aplicacao/" + n); destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raiz / n, destino)
            if sha_arquivo(destino) != dados["sha256"]: raise RuntimeError("Fonte mudou durante a cópia; original preservado: " + n)
            arquivos["aplicacao/" + n] = dados
        bancos = {}
        for nome, p in (("negocio", negocio), ("acessos", acesso)):
            n = "bancos/" + nome + ".db"; destino = caminho_pacote(pacote, n)
            copiar_sqlite(p, destino)
            if fotografia(destino) != anteriores[nome]: raise RuntimeError("Banco mudou durante o backup; registros externos preservados.")
            bancos[nome] = {"arquivo": n, "origem_relativa": p.relative_to(raiz).as_posix(), "fotografia": anteriores[nome]}
            arquivos[n] = {"bytes": destino.stat().st_size, "sha256": sha_arquivo(destino)}
        leitura = ("Pacote MEC D41. Aplicação e os dois bancos devem ser recuperados juntos.\n"
            "Raiz original: " + str(raiz) + "\nO manifesto registra os destinos relativos originais.\n"
            "Arquivos técnicos podem referenciar a raiz original; recuperar no mesmo caminho.\n"
            "Dependências (.venv/node_modules) e histórico Git não incluídos.\n"
            "Verifique MANIFESTO.json: validado deve ser true. Nunca sobrescreva uma instalação em execução.\n"
            "O script --verificar-backup verifica este pacote e recupera apenas uma cópia temporária.\n")
        (pacote / "LEIA_RECUPERACAO.txt").write_text(leitura, encoding="utf-8")
        arquivos["LEIA_RECUPERACAO.txt"] = {"bytes": (pacote / "LEIA_RECUPERACAO.txt").stat().st_size, "sha256": sha_arquivo(pacote / "LEIA_RECUPERACAO.txt")}
        m = {"revision": REVISION, "formato": 1, "validado": False, "raiz_original": str(raiz), "base_d40": relatorio["base_d40"],
            "arquivos": arquivos, "bancos": bancos, "arquivos_tecnicos_ativos": tecnicos}
        gravar_atomico(pacote / "MANIFESTO.json", (json.dumps(m, ensure_ascii=False, indent=2) + "\n").encode())
        relatorio["etapa"] = "conferir_recuperacao"
        manifesto_valido(pacote, exigir_validado=False)
        with tempfile.TemporaryDirectory(prefix="mec_d41_recuperado_") as pasta:
            copia = Path(pasta); recuperar_copia(pacote, copia, m)
            ambiente = dict(os.environ)
            ambiente.update(MEC_MODO_TESTE_LOCAL="0", MEC_AMBIENTE="teste", MEC_COOKIE_SEGURO="0",
                MEC_URL_BANCO_DADOS="sqlite:///" + (copia / "bancos/negocio.db").as_posix(), MEC_ACESSOS_DB=str(copia / "bancos/acessos.db"))
            executar(raiz, "ensaio_api_isolado", [sys.executable, "-u", "-c", ENSAIO, str(copia)], ambiente, relatorio, limite_segundos=300)
            ensaio = json.loads((copia / "ENSAIO_API.json").read_text(encoding="utf-8"))
            if ensaio.get("resultado") != "OK": raise RuntimeError("Ensaio da aplicação recuperada não confirmado.")
        relatorio["etapa"] = "conferir_preservacao"
        if fotografia(negocio) != anteriores["negocio"] or fotografia(acesso) != anteriores["acessos"]:
            raise RuntimeError("Um banco original mudou durante a validação; registros externos preservados.")
        if catalogo(raiz, {negocio, acesso}) != origem:
            raise RuntimeError("Arquivo original mudou durante a validação; alterações externas preservadas.")
        if manifesto_valido(pacote, exigir_validado=False) != m:
            raise RuntimeError("Manifesto mudou durante a validação; alteração externa preservada.")
        m.update(validado=True, ensaio_api=ensaio)
        gravar_atomico(pacote / "MANIFESTO.json", (json.dumps(m, ensure_ascii=False, indent=2) + "\n").encode())
        relatorio.update(resultado="OK", etapa="concluido", fontes_backend_frontend_preservados=True,
            historico_negocio_preservado=True, contas_senhas_sessoes_preservadas=True, backup_validado=True,
            recuperacao_isolada_confirmada=True, quantidade_arquivos=len(arquivos), ensaio_api=ensaio,
            homologacao_manual_pendente=True, publicacao_pendente=True)
        print("INTEGRIDADE_DOS_DOIS_BANCOS_CONFIRMADA=True", flush=True)
        print("ARQUIVOS_NO_PACOTE=" + str(len(arquivos)), flush=True)
        print("ARQUIVOS_TECNICOS_ATIVOS_CONFERIDOS=" + str(len(tecnicos)), flush=True)
        print("RECUPERACAO_ISOLADA_CONFIRMADA=True", flush=True)
        print("HISTORICO_NEGOCIO_PRESERVADO=True", flush=True)
        print("CONTAS_SENHAS_SESSOES_PRESERVADAS=True", flush=True)
        print("FONTES_BACKEND_FRONTEND_PRESERVADOS=True", flush=True)
        salvar_relatorio(raiz, relatorio)
        print("RESULTADO=OK", flush=True)
        print("Reinicie o teste local. Próxima conferência: D41_ROTEIRO_HOMOLOGACAO.txt", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["resultado"] = "ERRO"
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ETAPA=" + relatorio["etapa"], flush=True); print("ERRO=" + relatorio["erro"], flush=True)
        if pacote is not None:
            rotulo = "BACKUP_VALIDADO_RELATORIO_FALHOU=" if relatorio.get("backup_validado") is True else "PACOTE_NAO_APROVADO="
            print(rotulo + str(pacote), flush=True)
        if raiz is not None:
            try: salvar_relatorio(raiz, relatorio)
            except OSError: print("RELATORIO_NAO_GRAVADO=True", flush=True)
        print("RESULTADO=ERRO", flush=True); return 1


if __name__ == "__main__":
    raise SystemExit(main())
