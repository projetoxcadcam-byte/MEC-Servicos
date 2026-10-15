"""Gera as narrações localmente, com a voz Maria já instalada no Windows.

Não usa serviços externos nem instala pacotes. Cria WAVs por perfil, trechos
por cena, legendas e um ZIP para a edição dos vídeos. Não grava a tela.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
import uuid
import wave
import zipfile

REVISION = "MEC-SERVICOS-NARRACOES-GRATUITAS-MARIA-2026-10-14"
ROTEIROS = [{'perfil': 'CLIENTE', 'nome': 'Cliente', 'cenas': [{'etapa': 'Apresentação', 'titulo': 'Cliente', 'texto': 'Bem-vindo ao guia do perfil cliente. Do pedido à avaliação do serviço. Vamos acompanhar o fluxo principal do sistema, passo a passo. Os dados e valores usados neste treinamento são exemplos.', 'duracao_minima': 8}, {'etapa': 'Entrar e conferir o painel', 'titulo': 'Acesso do cliente', 'texto': 'Entre com a conta da sua empresa. Se for o primeiro acesso, altere a senha em Minha conta e entre novamente.', 'duracao_minima': 7}, {'etapa': 'Entrar e conferir o painel', 'titulo': 'Dashboard da sua empresa', 'texto': 'Confira seus pedidos e use os atalhos do Dashboard. O sino reúne os avisos que precisam da sua atenção.', 'duracao_minima': 7}, {'etapa': 'Criar uma solicitação', 'titulo': 'Nova solicitação', 'texto': 'Abra Solicitações e clique Nova solicitação. Escolha o processo e o material realmente necessários ao serviço.', 'duracao_minima': 7}, {'etapa': 'Criar uma solicitação', 'titulo': 'Conferir o escopo do pedido', 'texto': 'Informe tolerância, quantidade e observações técnicas. Se o serviço for somente desbaste, descreva esse escopo antes de criar a solicitação.', 'duracao_minima': 7}, {'etapa': 'Enviar os arquivos técnicos', 'titulo': 'Arquivos Técnicos', 'texto': 'Selecione a solicitação correta e use + Enviar arquivo para escolher o desenho. Confira o número do pedido antes do envio.', 'duracao_minima': 7}, {'etapa': 'Enviar os arquivos técnicos', 'titulo': 'Documento vinculado ao pedido', 'texto': 'Confira a confirmação e baixe o arquivo para verificar. O ADM revisará a documentação antes de liberar a oportunidade ao fornecedor.', 'duracao_minima': 7}, {'etapa': 'Analisar o orçamento', 'titulo': 'Orçamento publicado pelo ADM', 'texto': 'Em Cotações, abra Ver detalhes. Confira o preço final, o prazo, a validade e os requisitos técnicos da versão publicada.', 'duracao_minima': 7}, {'etapa': 'Analisar o orçamento', 'titulo': 'Análise do orçamento', 'texto': 'Escolha Aprovar orçamento, Pedir revisão ou Recusar orçamento. Revisão e recusa exigem um motivo para a administração.', 'duracao_minima': 7}, {'etapa': 'Analisar o orçamento', 'titulo': 'Conferir a sua resposta', 'texto': 'Revise sua decisão e clique Confirmar aprovação. A contratação e a abertura da OS serão confirmadas depois pela administração.', 'duracao_minima': 7}, {'etapa': 'Acompanhar a produção', 'titulo': 'Contratação e OS confirmadas', 'texto': 'Quando o ADM concluir a contratação, consulte Contratações e Ordens de Serviço. Use sempre o número da OS para acompanhar o trabalho.', 'duracao_minima': 7}, {'etapa': 'Acompanhar a produção', 'titulo': 'Acompanhamento de Produção', 'texto': 'Abra Produção, selecione a OS e clique Ver histórico. O fornecedor registra as etapas; use Atualizar histórico para conferir mudanças.', 'duracao_minima': 7}, {'etapa': 'Consultar as notificações', 'titulo': 'Avisos da sua conta', 'texto': 'Clique no sino e confira o número do serviço. Abra o aviso para consultar a atualização na tela correspondente.', 'duracao_minima': 7}, {'etapa': 'Consultar as notificações', 'titulo': 'Conferir e marcar a leitura', 'texto': 'Depois de ler, use Marcar como lida. Abrir somente o sino não marca todos os avisos; a leitura é individual por conta.', 'duracao_minima': 7}, {'etapa': 'Conferir entrega e saldo', 'titulo': 'Entregas · OS #401', 'texto': 'Em Entregas, clique Ver histórico. Acompanhe coleta, avaliação e entrega final registrada pelo ADM para o lote completo.', 'duracao_minima': 7}, {'etapa': 'Conferir entrega e saldo', 'titulo': 'Pagamentos e saldo', 'texto': 'Abra Pagamentos e clique Abrir na contratação. Confira valor contratado, recebimentos confirmados e saldo a pagar.', 'duracao_minima': 7}, {'etapa': 'Conferir entrega e saldo', 'titulo': 'Saldo atualizado pelo ADM', 'texto': 'Após um pagamento realizado, aguarde a conferência do ADM e atualize a tela. O saldo considera os recebimentos válidos registrados.', 'duracao_minima': 7}, {'etapa': 'Avaliar o serviço entregue', 'titulo': 'Registrar minha avaliação', 'texto': 'Depois da entrega e da OS concluída, abra Avaliações e Ver contratação. Quando disponível, escolha uma nota de 1 a 5.', 'duracao_minima': 7}, {'etapa': 'Avaliar o serviço entregue', 'titulo': 'Confirmar avaliação', 'texto': 'Revise a nota e o comentário e clique Confirmar avaliação. A avaliação confirmada fica no histórico e não pode ser editada pela interface.', 'duracao_minima': 7}, {'etapa': 'Rotina de conferência', 'titulo': 'Encerramento', 'texto': 'Confira, confirme e acompanhe o histórico. Na dúvida, informe a janela e o número do serviço. Consulte também o manual do seu perfil para os detalhes de cada procedimento.', 'duracao_minima': 8}]}, {'perfil': 'FORNECEDOR', 'nome': 'Fornecedor', 'cenas': [{'etapa': 'Apresentação', 'titulo': 'Fornecedor', 'texto': 'Bem-vindo ao guia do perfil fornecedor. Da oportunidade à produção e ao repasse. Vamos acompanhar o fluxo principal do sistema, passo a passo. Os dados e valores usados neste treinamento são exemplos.', 'duracao_minima': 8}, {'etapa': 'Entrar e conferir os avisos', 'titulo': 'Acesso do fornecedor', 'texto': 'Entre com a conta da sua empresa. No primeiro acesso, altere a senha em Minha conta, quando solicitado, e entre novamente.', 'duracao_minima': 7}, {'etapa': 'Entrar e conferir os avisos', 'titulo': 'Dashboard do fornecedor', 'texto': 'Confira oportunidades, propostas e serviços. No sino, leia os avisos de documentos, decisões, material encaminhado, repasses e avaliações.', 'duracao_minima': 7}, {'etapa': 'Conferir a oportunidade', 'titulo': 'Solicitações Compatíveis', 'texto': 'Abra Solicitações e Ver detalhes. O pedido precisa estar aberto, ser compatível com sua capacidade e ter documentação liberada pelo ADM.', 'duracao_minima': 7}, {'etapa': 'Conferir a oportunidade', 'titulo': 'Arquivos técnicos liberados', 'texto': 'Baixe os documentos antes de calcular a proposta. Confira revisão, material, dimensões, tolerância e escopo, inclusive quando o pedido for somente desbaste.', 'duracao_minima': 7}, {'etapa': 'Preparar a proposta', 'titulo': 'Sua proposta', 'texto': 'Informe o valor total de todas as peças, o prazo e a validade. As observações devem descrever as condições relevantes para a análise administrativa.', 'duracao_minima': 7}, {'etapa': 'Preparar a proposta', 'titulo': 'Revisão da proposta', 'texto': 'Confira solicitação, valor total, prazo e validade. Clique Confirmar envio e verifique o registro em Minhas Cotações.', 'duracao_minima': 7}, {'etapa': 'Aguardar contratação e material', 'titulo': 'Minhas Cotações', 'texto': 'Depois de enviar, acompanhe a proposta em Minhas Cotações. O pedido pode sair das oportunidades porque sua empresa já apresentou uma proposta.', 'duracao_minima': 7}, {'etapa': 'Aguardar contratação e material', 'titulo': 'Serviço autorizado', 'texto': 'Confira a contratação, a OS e o encaminhamento do material pelo ADM. Só inicie a execução quando essas condições estiverem atendidas.', 'duracao_minima': 7}, {'etapa': 'Registrar o andamento real', 'titulo': 'Acompanhamento de Produção', 'texto': 'Abra Produção e Ver histórico na OS correta. Selecione a etapa que representa o andamento real e acrescente observações quando necessário.', 'duracao_minima': 7}, {'etapa': 'Registrar o andamento real', 'titulo': 'Confirmar atualização de produção', 'texto': 'Revise a OS, a nova etapa e a observação. Clique Confirmar atualização. Cliente e ADM recebem os avisos relevantes do andamento.', 'duracao_minima': 7}, {'etapa': 'Registrar o andamento real', 'titulo': 'Histórico atualizado', 'texto': 'Confira a mensagem de sucesso e a nova linha no histórico. Cada atualização deve corresponder ao que realmente aconteceu no serviço.', 'duracao_minima': 7}, {'etapa': 'Informar disponibilidade para coleta', 'titulo': 'Lote pronto para coleta', 'texto': 'Ao terminar o serviço contratado, registre Pronto para coleta em Produção. Revise e confirme, seguindo a mesma sequência da atualização anterior.', 'duracao_minima': 7}, {'etapa': 'Informar disponibilidade para coleta', 'titulo': 'Entregas · histórico da OS', 'texto': 'Acompanhe coleta e avaliação em Entregas. Se houver retrabalho, aguarde o encaminhamento, atualize a produção e informe novamente Pronto para coleta ao concluir.', 'duracao_minima': 7}, {'etapa': 'Consultar repasses e saldo', 'titulo': 'Repasses e saldo', 'texto': 'Em Pagamentos, clique Abrir na contratação. Confira o valor contratado com sua empresa, os repasses confirmados e o saldo a receber.', 'duracao_minima': 7}, {'etapa': 'Consultar repasses e saldo', 'titulo': 'Repasse conferido pelo ADM', 'texto': 'Após o repasse realizado e registrado pelo ADM, use Atualizar. Confira a linha do histórico e o saldo. A tela não executa transferências bancárias.', 'duracao_minima': 7}, {'etapa': 'Consultar as próprias notas', 'titulo': 'Notas do serviço', 'texto': 'Abra Avaliações, filtre pela OS ou contratação e clique Ver contratação. Consulte as notas individuais registradas pelo cliente e pelo ADM, quando disponíveis.', 'duracao_minima': 7}, {'etapa': 'Consultar as próprias notas', 'titulo': 'O que fica disponível', 'texto': 'O fornecedor consulta suas próprias notas individuais, sem comentários ou nomes dos autores. Ranking, médias e posições são exclusivos da administração.', 'duracao_minima': 7}, {'etapa': 'Rotina de conferência', 'titulo': 'Encerramento', 'texto': 'Confira, confirme e acompanhe o histórico. Na dúvida, informe a janela e o número do serviço. Consulte também o manual do seu perfil para os detalhes de cada procedimento.', 'duracao_minima': 8}]}, {'perfil': 'ADMINISTRADOR', 'nome': 'Administrador', 'cenas': [{'etapa': 'Apresentação', 'titulo': 'Administrador', 'texto': 'Bem-vindo ao guia do perfil administrador. Da documentação ao resultado da intermediação. Vamos acompanhar o fluxo principal do sistema, passo a passo. Os dados e valores usados neste treinamento são exemplos.', 'duracao_minima': 8}, {'etapa': 'Começar pelo painel', 'titulo': 'Rotina de início do dia', 'texto': 'Entre com a conta ADM. No Dashboard, confira os pedidos e a Central de pendências; no sino, abra os avisos que exigem sua conferência.', 'duracao_minima': 7}, {'etapa': 'Começar pelo painel', 'titulo': 'Empresas, operações e materiais', 'texto': 'Mantenha o cadastro técnico dos fornecedores atualizado: operações, materiais aceitos, dimensões e tolerância. Essas informações determinam a compatibilidade das oportunidades.', 'duracao_minima': 7}, {'etapa': 'Revisar os documentos', 'titulo': 'Arquivos para cotação', 'texto': 'Pesquise a Solicitação #101 e clique Baixar para revisar. Confira integridade, revisão, legibilidade e informações necessárias à execução.', 'duracao_minima': 7}, {'etapa': 'Revisar os documentos', 'titulo': 'Preparar PDF com nossa logo', 'texto': 'Se necessário, prepare uma cópia neutra do PDF. Preserve cotas, tolerâncias, material e notas técnicas relevantes; revise o resultado antes de liberar.', 'duracao_minima': 7}, {'etapa': 'Revisar os documentos', 'titulo': 'Liberar arquivo para cotação', 'texto': 'Após revisar o conteúdo, use Liberar para cotação. Confirme a revisão, preencha o registro interno e clique Confirmar registro.', 'duracao_minima': 7}, {'etapa': 'Comparar as propostas', 'titulo': 'Análise administrativa', 'texto': 'Em Cotações, localize a proposta e clique Analisar cotação. Use Comparar propostas para conferir preço, prazo e histórico dos fornecedores.', 'duracao_minima': 7}, {'etapa': 'Comparar as propostas', 'titulo': 'Abrir a formação do preço', 'texto': 'No detalhe, role até Cotações desta solicitação. Na proposta pendente, clique Preparar preço para o cliente.', 'duracao_minima': 7}, {'etapa': 'Preparar e publicar o preço', 'titulo': 'Preço ao cliente · cotação #201', 'texto': 'Escolha percentual sobre o custo ou valor fixo. Neste exemplo, 20% sobre R$ 1.000,00 equivalem a R$ 200,00 de acréscimo.', 'duracao_minima': 7}, {'etapa': 'Preparar e publicar o preço', 'titulo': 'Conferência antes de publicar', 'texto': 'Confira preço final e resultado previsto. Preencha Registro interno e use Publicar ao cliente. Salvar rascunho guarda a preparação sem liberar a análise.', 'duracao_minima': 7}, {'etapa': 'Confirmar contratação e OS', 'titulo': 'Aguardar a análise do cliente', 'texto': 'Confira a aprovação vigente do cliente, a validade e os documentos. Após essa conferência, use Aceitar cotação, registre o motivo e confirme o aceite.', 'duracao_minima': 7}, {'etapa': 'Confirmar contratação e OS', 'titulo': 'Preparar contratação e abertura da OS', 'texto': 'Abra Preparar contratação e abertura da OS. Confira as partes, valores, prazo, quantidade e documentos; preencha o registro e use Revisar contratação e OS.', 'duracao_minima': 7}, {'etapa': 'Confirmar contratação e OS', 'titulo': 'Confirmar contratação e OS', 'texto': 'Revise o resumo e confirme. Anote os números exibidos e confira contratação ativa, OS aberta e ciclo administrativo em Aguardando material.', 'duracao_minima': 7}, {'etapa': 'Encaminhar o material', 'titulo': 'Ciclo da OS #401', 'texto': 'Abra Ver ciclo. Quando o material chegar, escolha Registrar recebimento do material e preencha registro, referência e quantidade total solicitados.', 'duracao_minima': 7}, {'etapa': 'Encaminhar o material', 'titulo': 'Material encaminhado ao fornecedor', 'texto': 'Revise e confirme o recebimento. Depois do encaminhamento real, registre Registrar encaminhamento do material, revise e confirme. A oficina poderá atualizar a produção.', 'duracao_minima': 7}, {'etapa': 'Acompanhar produção e coleta', 'titulo': 'Produção administrativa', 'texto': 'Em Produção, localize a OS e abra Ver produção da OS. Acompanhe a etapa informada pelo fornecedor e o histórico das atualizações.', 'duracao_minima': 7}, {'etapa': 'Acompanhar produção e coleta', 'titulo': 'Coletar e receber as peças', 'texto': 'Após Pronto para coleta, registre Solicitar coleta das peças. Quando chegarem, registre o recebimento das peças, com lote completo, referência e registro interno.', 'duracao_minima': 7}, {'etapa': 'Inspecionar e concluir a entrega', 'titulo': 'Avaliação administrativa das peças', 'texto': 'Use Iniciar avaliação das peças. Registre o parecer técnico e escolha Aprovar peças para entrega ou Solicitar retrabalho, conforme a inspeção.', 'duracao_minima': 7}, {'etapa': 'Inspecionar e concluir a entrega', 'titulo': 'Concluir entrega ao cliente e OS', 'texto': 'Após entregar o lote aprovado, registre Concluir entrega ao cliente e OS. Confira quantidade e comprovante, revise e confirme; verifique a OS concluída.', 'duracao_minima': 7}, {'etapa': 'Registrar o financeiro real', 'titulo': 'Financeiro administrativo', 'texto': 'Abra a contratação em Pagamentos e inicie o controle, se necessário. Para um valor já recebido, selecione Registrar recebimento do cliente e confira os dados.', 'duracao_minima': 7}, {'etapa': 'Registrar o financeiro real', 'titulo': 'Registrar repasse ao fornecedor', 'texto': 'Revise e use Confirmar registro. Após a entrega e com cobertura pelos recebimentos, registre o repasse efetivamente realizado ao fornecedor, seguindo a mesma conferência.', 'duracao_minima': 7}, {'etapa': 'Registrar o financeiro real', 'titulo': 'Conferir saldos e encerrar', 'texto': 'Confira entrega e OS concluídas e os dois saldos zerados. Use Encerrar financeiro e contratação, registre o motivo, confira e confirme.', 'duracao_minima': 7}, {'etapa': 'Registrar despesas e analisar', 'titulo': 'Despesas reais · contratação #301', 'texto': 'Em Resultado da administração, consulte as despesas da contratação. Para um gasto já pago, informe categoria, descrição, valor, data, referência e registro interno.', 'duracao_minima': 7}, {'etapa': 'Registrar despesas e analisar', 'titulo': 'Resultado do exemplo liquidado', 'texto': 'Compare previsão e despesa paga: R$ 200,00 de ganho bruto menos R$ 40,00 pagos resultam em R$ 160,00 após despesas. A previsão permanece separada.', 'duracao_minima': 7}, {'etapa': 'Consultar metas e relatórios', 'titulo': 'Metas mensais do resultado', 'texto': 'Use Abrir metas mensais e consulte o ano. Escolha o mês em Mês para definir ou editar a meta e clique Abrir edição da meta.', 'duracao_minima': 7}, {'etapa': 'Consultar metas e relatórios', 'titulo': 'Conferir e exportar as metas', 'texto': 'Compare a meta ao resultado dos serviços liquidados. Use Baixar PDF das metas ou Baixar CSV das metas; a impressão abre o PDF em A4 horizontal.', 'duracao_minima': 7}, {'etapa': 'Avaliar e consultar o ranking', 'titulo': 'Avaliação da administração', 'texto': 'Após a entrega, abra Avaliações, confira a contratação, escolha nota e comentário e use Revisar avaliação. Revise antes de Confirmar avaliação.', 'duracao_minima': 7}, {'etapa': 'Avaliar e consultar o ranking', 'titulo': 'Ranking exclusivo do ADM', 'texto': 'Abra Ranking para consultar notas, médias e posições. Escolha a origem Cliente ou ADM e confira o histórico; as duas origens não formam uma nota combinada.', 'duracao_minima': 7}, {'etapa': 'Rotina de conferência', 'titulo': 'Encerramento', 'texto': 'Confira, confirme e acompanhe o histórico. Na dúvida, informe a janela e o número do serviço. Consulte também o manual do seu perfil para os detalhes de cada procedimento.', 'duracao_minima': 8}]}]

# Código fixo. Textos e caminhos chegam como JSON pela entrada padrão.
POWERSHELL = r'''
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$sintese = $null
try {
    $pedido = [Console]::In.ReadToEnd() | ConvertFrom-Json
    Add-Type -AssemblyName System.Speech
    $sintese = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $disponiveis = @($sintese.GetInstalledVoices() | Where-Object { $_.Enabled })
    $escolhida = $disponiveis | Where-Object {
        $_.VoiceInfo.Name -eq $pedido.voz -and $_.VoiceInfo.Culture.Name -eq 'pt-BR'
    } | Select-Object -First 1
    if ($null -eq $escolhida) {
        throw 'A voz solicitada não está habilitada em português do Brasil. Confira as vozes instaladas no Windows.'
    }
    $sintese.SelectVoice($escolhida.VoiceInfo.Name)
    $sintese.Rate = [int]$pedido.velocidade
    $sintese.Volume = 100
    Write-Output ('VOZ=' + $sintese.Voice.Name)
    Write-Output ('IDIOMA=' + $sintese.Voice.Culture.Name)
    $itens = @($pedido.itens)
    for ($i = 0; $i -lt $itens.Count; $i++) {
        $item = $itens[$i]
        $alvo = [IO.Path]::GetFullPath([string]$item.arquivo)
        if ([IO.File]::Exists($alvo)) { throw ('Arquivo já existente; preservado: ' + $alvo) }
        $sintese.SetOutputToWaveFile($alvo)
        $sintese.SpeakSsml([string]$item.ssml)
        $sintese.SetOutputToNull()
        Write-Output ('AUDIO_GERADO=' + ($i + 1) + '/' + $itens.Count + ' ' + [string]$item.identificador)
    }
    Write-Output 'SINTESE_LOCAL_CONCLUIDA=True'
} catch {
    Write-Output ('ERRO_VOZ=' + $_.Exception.Message)
    exit 1
} finally {
    if ($null -ne $sintese) { $sintese.Dispose() }
}
'''


def texto_falado(texto: str) -> str:
    valores = {
        "R$ 1.200,00": "mil e duzentos reais",
        "R$ 1.000,00": "mil reais",
        "R$ 200,00": "duzentos reais",
        "R$ 160,00": "cento e sessenta reais",
        "R$ 150,00": "cento e cinquenta reais",
        "R$ 50,00": "cinquenta reais",
        "R$ 40,00": "quarenta reais",
    }
    for original, falado in valores.items():
        texto = texto.replace(original, falado)
    texto = texto.replace("20%", "vinte por cento")
    texto = re.sub(r"\bconta ADM\b", "conta de administrador", texto)
    texto = re.sub(r"\bADM\b", "administrador", texto)
    texto = re.sub(r"\bOS\b", "ordem de serviço", texto)
    texto = re.sub(r"\bPDF\b", "pê dê éfe", texto)
    texto = re.sub(r"\bCSV\b", "cê ésse vê", texto)
    texto = re.sub(r"#\s*(\d+)", r"número \1", texto)
    texto = texto.replace("+ Enviar arquivo", "Enviar arquivo")
    return texto


def ssml(texto: str) -> str:
    seguro = html.escape(texto_falado(texto), quote=True)
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            'xml:lang="pt-BR"><p>' + seguro + '</p><break time="180ms"/></speak>')


def localizar_powershell() -> Path:
    if os.name != "nt":
        raise RuntimeError("Execute este arquivo no seu computador Windows, onde a voz Microsoft Maria Desktop está instalada.")
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    candidatos = [
        windows / "Sysnative/WindowsPowerShell/v1.0/powershell.exe",
        windows / "System32/WindowsPowerShell/v1.0/powershell.exe",
    ]
    localizado = shutil.which("powershell.exe")
    if localizado:
        candidatos.append(Path(localizado))
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    raise RuntimeError("Windows PowerShell não encontrado.")


def montar_pedido(roteiros: list[dict], pasta: Path, voz: str, velocidade: int) -> dict:
    itens = []
    for perfil in roteiros:
        destino = pasta / perfil["perfil"] / "trechos"
        destino.mkdir(parents=True, exist_ok=True)
        for i, cena in enumerate(perfil["cenas"], 1):
            nome = f"{i:03}.wav"
            itens.append({
                "identificador": perfil["perfil"] + "/" + nome,
                "arquivo": str(destino / nome),
                "ssml": ssml(cena["texto"]),
            })
    return {"voz": voz, "velocidade": velocidade, "itens": itens}


def sintetizar(executavel: Path, pedido: dict, limite_segundos: int = 900) -> None:
    comando_codificado = base64.b64encode(POWERSHELL.encode("utf-16-le")).decode("ascii")
    comando = [str(executavel), "-NoProfile", "-NonInteractive", "-Sta", "-EncodedCommand", comando_codificado]
    processo = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    eventos: queue.Queue = queue.Queue()

    def alimentar():
        try:
            processo.stdin.write(json.dumps(pedido, ensure_ascii=False))
            processo.stdin.close()
        except (OSError, ValueError) as erro:
            eventos.put(("erro_entrada", str(erro)))

    def receber():
        try:
            for linha in processo.stdout:
                eventos.put(("saida", linha.rstrip()))
        finally:
            eventos.put(("fim_saida", None))

    threading.Thread(target=alimentar, daemon=True).start()
    threading.Thread(target=receber, daemon=True).start()
    inicio = time.monotonic()
    ultima_mensagem = inicio
    concluiu_sintese = False
    try:
        while True:
            agora = time.monotonic()
            if agora - inicio > limite_segundos:
                raise RuntimeError("A geração de voz excedeu 15 minutos. Os trechos já criados ficam na pasta indicada.")
            try:
                tipo, valor = eventos.get(timeout=0.3)
            except queue.Empty:
                if agora - ultima_mensagem >= 15:
                    print("Gerando narração local; aguarde…", flush=True)
                    ultima_mensagem = agora
                continue
            if tipo == "saida":
                print(valor, flush=True)
                ultima_mensagem = agora
                concluiu_sintese |= valor == "SINTESE_LOCAL_CONCLUIDA=True"
            elif tipo == "erro_entrada":
                raise RuntimeError("Não foi possível enviar o roteiro à voz do Windows: " + valor)
            else:
                break
        retorno = processo.wait(timeout=10)
        if retorno != 0 or not concluiu_sintese:
            raise RuntimeError("A síntese de voz não foi concluída. Confira ERRO_VOZ na saída acima.")
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)
        processo.stdout.close()


def instante_legenda(amostras: int, frequencia: int) -> str:
    milissegundos = round(amostras * 1000 / frequencia)
    horas, restante = divmod(milissegundos, 3_600_000)
    minutos, restante = divmod(restante, 60_000)
    segundos, milesimos = divmod(restante, 1000)
    return f"{horas:02}:{minutos:02}:{segundos:02},{milesimos:03}"


def montar_audio(perfil: dict, pasta: Path) -> dict:
    chave = perfil["perfil"]
    final = pasta / f"MEC_SERVICOS_NARRACAO_{chave}.wav"
    parcial = final.with_suffix(".wav.part")
    if final.exists():
        raise RuntimeError("Áudio já existente; preservado: " + str(final))
    # Confere todos os trechos antes de criar o áudio final.
    parametros = None
    detalhes = []
    for i, cena in enumerate(perfil["cenas"], 1):
        arquivo = pasta / chave / "trechos" / f"{i:03}.wav"
        try:
            with wave.open(str(arquivo), "rb") as audio:
                p = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype())
                if p[3] != "NONE" or p[0] not in (1, 2) or p[1] not in (1, 2, 3, 4):
                    raise RuntimeError("Formato de áudio não compatível: " + str(arquivo))
                if audio.getnframes() < audio.getframerate() * .1:
                    raise RuntimeError("Trecho vazio ou curto demais: " + str(arquivo))
                if parametros is not None and p != parametros:
                    raise RuntimeError("Os trechos foram gerados com formatos diferentes.")
                parametros = p
                detalhes.append((arquivo, cena, audio.getnframes()))
        except (OSError, EOFError, wave.Error) as erro:
            raise RuntimeError("Trecho de áudio inválido ou ausente: " + str(arquivo)) from erro
    if not detalhes:
        raise RuntimeError("O roteiro não contém cenas.")
    canais, largura, frequencia, _ = parametros
    amostras_acumuladas = 0
    cenas = []
    legendas = []
    try:
        with wave.open(str(parcial), "wb") as destino:
            destino.setnchannels(canais)
            destino.setsampwidth(largura)
            destino.setframerate(frequencia)
            for i, (arquivo, cena, faladas) in enumerate(detalhes, 1):
                inicio = amostras_acumuladas
                alvo = max(round(cena["duracao_minima"] * frequencia), faladas + round(.75 * frequencia))
                with wave.open(str(arquivo), "rb") as origem:
                    lidas = 0
                    while True:
                        trecho = origem.readframes(16384)
                        if not trecho:
                            break
                        if len(trecho) % (canais * largura):
                            raise RuntimeError("Trecho PCM incompleto: " + str(arquivo))
                        lidas += len(trecho) // (canais * largura)
                        destino.writeframesraw(trecho)
                    if lidas != faladas:
                        raise RuntimeError("Trecho PCM truncado: " + str(arquivo))
                restante = alvo - faladas
                # PCM de 8 bits usa 128 para representar silêncio; os demais usam zero.
                silencio = (b"\x80" if largura == 1 else b"\x00" * largura) * canais
                while restante:
                    bloco = min(restante, 16384)
                    destino.writeframesraw(silencio * bloco)
                    restante -= bloco
                amostras_acumuladas += alvo
                cenas.append({
                    "indice": i, "etapa": cena["etapa"], "titulo": cena["titulo"],
                    "texto_legenda": cena["texto"], "texto_falado": texto_falado(cena["texto"]),
                    "trecho": arquivo.relative_to(pasta).as_posix(),
                    "inicio_segundos": round(inicio / frequencia, 6),
                    "fala_segundos": round(faladas / frequencia, 6),
                    "duracao_segundos": round(alvo / frequencia, 6),
                    "fim_segundos": round(amostras_acumuladas / frequencia, 6),
                })
                legendas.append(f"{i}\n{instante_legenda(inicio, frequencia)} --> {instante_legenda(amostras_acumuladas, frequencia)}\n" + "\n".join(textwrap.wrap(cena["texto"], 78)) + "\n")
        with wave.open(str(parcial), "rb") as conferir:
            if conferir.getnframes() != amostras_acumuladas:
                raise RuntimeError("Duração final divergente.")
        parcial.replace(final)
    finally:
        parcial.unlink(missing_ok=True)
    final.with_suffix(".srt").write_text("\n".join(legendas), encoding="utf-8")
    roteiro = ["MEC-Serviços — Narração do perfil " + perfil["nome"],
               "Voz local do Windows. Dados e valores dos exemplos são fictícios.", ""]
    for cena in cenas:
        roteiro.extend([cena["etapa"] + " / " + cena["titulo"], cena["texto_legenda"], ""])
    final.with_suffix(".txt").write_text("\n".join(roteiro), encoding="utf-8")
    return {"perfil": chave, "audio": final.name, "canais": canais,
            "bits": largura * 8, "frequencia_hz": frequencia,
            "duracao_segundos": round(amostras_acumuladas / frequencia, 6), "cenas": cenas}


def empacotar(pasta: Path, perfis: list[dict], voz: str, velocidade: int) -> Path:
    manifesto = {
        "revision": REVISION, "voz": voz, "velocidade": velocidade,
        "idioma": "pt-BR", "servico_pago_utilizado": False,
        "gravacao_de_tela_incluida": False,
        "perfis": perfis,
    }
    (pasta / "MEC_NARRACOES_MANIFESTO.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "LEIA_ME.txt").write_text(
        "MEC-Serviços — Narrações gratuitas\n\n"
        "Abra os WAVs da raiz para ouvir cada perfil. Os áudios foram gerados pela voz local do Windows.\n"
        "Os subdiretórios contêm a fala separada por cena. O manifesto e as legendas indicam os tempos para edição.\n"
        "Os números, empresas, documentos e valores do roteiro são exemplos para treinamento.\n"
        "Este pacote contém somente áudio, legendas e roteiro: não contém gravações de tela.\n"
        "Não basta colocar o WAV sobre o vídeo ilustrativo anterior: é preciso ajustar cada cena aos tempos da narração.\n"
        "Envie o ZIP de áudios no chat para a montagem. Para usar telas reais, envie também o ZIP dos fontes atuais gerado pelo coletor.\n",
        encoding="utf-8")
    final = pasta / ("MEC_SERVICOS_NARRACOES_GRATUITAS_" + pasta.name + ".zip")
    parcial = final.with_suffix(".zip.part")
    arquivos = sorted(p for p in pasta.rglob("*") if p.is_file() and p not in (final, parcial))
    try:
        with zipfile.ZipFile(parcial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as pacote:
            for arquivo in arquivos:
                pacote.write(arquivo, arquivo.relative_to(pasta).as_posix())
        with zipfile.ZipFile(parcial) as pacote:
            if pacote.testzip() is not None:
                raise RuntimeError("O ZIP de narrações não passou na conferência.")
        parcial.replace(final)
    finally:
        parcial.unlink(missing_ok=True)
    return final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", choices=["CLIENTE", "FORNECEDOR", "ADMINISTRADOR"], help="Sem esta opção, gera os três perfis.")
    parser.add_argument("--voz", default="Microsoft Maria Desktop")
    parser.add_argument("--velocidade", type=int, choices=range(-10, 11), default=-1)
    parser.add_argument("--pasta", help="Pasta base para os resultados; padrão: pasta deste script.")
    args = parser.parse_args(argv)
    print("MEC-Serviços — Narração gratuita com Microsoft Maria", flush=True)
    print("REVISION=" + REVISION, flush=True)
    pasta = None
    try:
        powershell = localizar_powershell()
        base = Path(args.pasta).expanduser().resolve() if args.pasta else Path(__file__).resolve().parent
        marca = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        pasta = base / "_mec_videos" / "narracoes" / marca
        pasta.mkdir(parents=True, exist_ok=False)
        print("PASTA=" + str(pasta), flush=True)
        roteiros = [p for p in ROTEIROS if not args.perfil or p["perfil"] == args.perfil]
        pedido = montar_pedido(roteiros, pasta, args.voz, args.velocidade)
        print("Gerando os áudios. Não é necessário abrir o programa ou fornecer senhas.", flush=True)
        sintetizar(powershell, pedido)
        perfis = []
        for roteiro in roteiros:
            dados = montar_audio(roteiro, pasta)
            perfis.append(dados)
            print("AUDIO_" + roteiro["perfil"] + "=" + str(pasta / dados["audio"]), flush=True)
            print("DURACAO_" + roteiro["perfil"] + "=" + str(dados["duracao_segundos"]) + " segundos", flush=True)
        arquivo = empacotar(pasta, perfis, args.voz, args.velocidade)
        print("SERVICO_PAGO_UTILIZADO=False", flush=True)
        print("GRAVACAO_DE_TELA_INCLUIDA=False", flush=True)
        print("ZIP=" + str(arquivo), flush=True)
        print("RESULTADO=OK", flush=True)
        print("Ouça os três WAVs e envie o ZIP indicado no chat para a montagem dos vídeos.", flush=True)
        return 0
    except KeyboardInterrupt:
        print("ERRO=Geração interrompida. As fontes do programa foram preservadas.", flush=True)
    except Exception as erro:
        print("ERRO=" + str(erro), flush=True)
    if pasta is not None:
        print("PASTA_PARCIAL=" + str(pasta), flush=True)
    print("RESULTADO=ERRO", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
