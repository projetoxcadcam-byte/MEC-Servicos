"""Salva no Git o MEC-Serviços com a D66 FIX1 já validada pelo usuário.

Execute na raiz do projeto com o Python da .venv. Usa o Git e o acesso ao
GitHub já configurados. Confere a instalação, registra o checkpoint e inclui
um roteiro de teste completo; não executa operações de negócio.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import uuid

REVISION = "MEC-SERVICOS-GIT-TUTORIAL-VALIDADO-D66-FIX1-2026-10-15"
STEM = "MEC_SERVICOS_GIT_TUTORIAL_VALIDADO_RELATORIO"
MENSAGEM = "Checkpoint do MEC-Servicos com tutorial D66 FIX1 validado"
MARCADOR = "# MEC: arquivos locais fora do checkpoint Git FIX2"
PASTAS_LOCAIS = {
    ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", "data", "upload", "uploads", "_mec_backups", "_mec_videos",
}
EXTENSOES_LOCAIS = {
    ".db", ".db3", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".sqlite-wal",
    ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm", ".pyc", ".pyo", ".log", ".tmp",
    ".bak", ".wav", ".mp3", ".mp4", ".webm", ".avi", ".rar", ".zip", ".7z",
    ".pdf", ".step", ".stp", ".dwg", ".dxf", ".igs", ".iges", ".stl",
    ".pem", ".key", ".pfx", ".p12",
}
EXEMPLOS_ENV = {".env.example", ".env.exemplo", ".env.sample", ".env.template"}
REGRAS = [
    "**/.venv/", "**/venv/", "**/node_modules/", "**/__pycache__/", "**/.pytest_cache/",
    "**/.mypy_cache/", "**/.ruff_cache/", "**/data/", "**/upload/", "**/uploads/",
    "/_mec_backups/", "/_mec_videos/", "/frontend/dist/", "/.coverage", "/htmlcov/",
    ".env", ".env.*", "!.env.example", "!.env.exemplo", "!.env.sample", "!.env.template",
    "MEC*_RELATORIO*.json", "MEC*_RELATORIO*.txt", "*_RELATORIO.json", "*_RELATORIO.txt",
    "mec*_relatorio*.json", "mec*_relatorio*.txt", "*_relatorio.json", "*_relatorio.txt",
    "*CREDENCIAIS*.txt", "*CREDENCIAIS*.json", "*CREDENCIAIS*.csv", "*ACESSOS_INICIAIS*.txt",
    "*credenciais*.txt", "*credenciais*.json", "*credenciais*.csv", "*acessos_iniciais*.txt",
    "*SENHAS*.txt", "*SENHAS*.json", "*senhas*.txt", "*senhas*.json",
    *["*" + extensao for extensao in sorted(EXTENSOES_LOCAIS)],
    "!/data/", "/data/*", "!/data/.gitkeep",
]
SEGREDOS = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{50,}\b"),
]


REVISION_D66_FIX1 = "MEC-SERVICOS-V0.1-D66-FIX1-CAMINHOS-WINDOWS-2026-10-15"
RELATORIO_D66_FIX1 = "MEC_SERVICOS_V0_1_D66_FIX1_CAMINHOS_WINDOWS_RELATORIO.json"
ARQUIVOS_TUTORIAL = (
    "frontend/src/pages/tutorial/dadosTutorial.ts",
    "frontend/src/pages/tutorial/progressoTutorial.ts",
    "frontend/src/pages/tutorial/TutorialPage.tsx",
    "frontend/src/pages/tutorial/TutorialEntrada.tsx",
    "frontend/src/pages/tutorial/Tutorial.css",
    "frontend/src/App.tsx",
    "frontend/src/layouts/AdminLayout.tsx",
    "frontend/src/layouts/ClientLayout.tsx",
    "frontend/src/layouts/SupplierLayout.tsx",
)
ROTEIRO_NOME = "ROTEIRO_TESTE_COMPLETO_APOS_D66.txt"
ROTEIRO = """MEC-Serviços — Teste completo com os três perfis

OBJETIVO
Conferir um novo pedido da solicitação ao encerramento, usando dados fictícios.
O tutorial já foi validado pelo usuário. Este roteiro confere o fluxo de negócio.
O script de checkpoint não executa as ações abaixo nem altera bancos de dados.

PREPARAÇÃO
1. Mantenha backend e frontend iniciados e abra http://localhost:5173.
2. Use contas de teste de Cliente, Fornecedor e Administração. Alterne pelo
   seletor de contas disponível no modo de teste local, conferindo o perfil.
3. Identifique o novo pedido como TESTE COMPLETO D66. Anote os números gerados
   da solicitação, cotação, contratação e OS; não use números de pedidos antigos.
4. A empresa fornecedora deve ter operações, materiais e capacidade compatíveis
   com o pedido. Use um arquivo técnico de teste válido e valores fictícios.

ETAPA 1 — CLIENTE CRIA A SOLICITAÇÃO
Crie uma solicitação com descrição, operação, material, quantidade, dimensões
e prazo. Anexe o documento técnico de teste e envie para análise.
Conferir: a solicitação fica registrada para o cliente e pode ser vista pelo ADM.
Uma nova oportunidade não deve ser liberada sem documentação aprovada.

ETAPA 2 — ADM REVISA E LIBERA A DOCUMENTAÇÃO
Em Arquivos Técnicos, localize a solicitação, baixe e revise o documento.
Se usar a preparação do PDF com a logo, confira medidas, escala e informações
relevantes antes da liberação. Registre a liberação pelo fluxo da tela.
Conferir: o fornecedor compatível passa a visualizar a oportunidade e os
arquivos liberados; a versão original permanece disponível à administração.

ETAPA 3 — FORNECEDOR ENVIA A COTAÇÃO
Abra a oportunidade, confira o documento liberado e envie preço, prazo e
observações da proposta para análise administrativa.
Conferir: a proposta aparece para o ADM antes de ser publicada ao cliente.

ETAPA 4 — ADM PREPARA O PREÇO PARA O CLIENTE
Em Cotações, abra a proposta e use Preparar preço para o cliente. Confira
o custo do fornecedor, aplique percentual ou valor fixo e publique o preço.
Exemplo fictício para conferir a conta: custo R$ 1.000,00 mais acréscimo de
20% sobre o custo resulta em R$ 1.200,00 para o cliente e R$ 200,00 de acréscimo.
Conferir: o cliente vê o preço publicado; custo, acréscimo e resultado da ADM
permanecem restritos à administração. Esse acréscimo não é o lucro líquido.

ETAPA 5 — CLIENTE ANALISA; ADM FORMALIZA
Como cliente, analise e aprove o orçamento publicado. Como ADM, confira
a decisão e formalize a contratação e a ordem de serviço pelo fluxo da tela.
Conferir: contratação e OS vinculadas à solicitação correta, sem duplicidade.

ETAPA 6 — MATERIAL E INÍCIO DA PRODUÇÃO
Como ADM, registre as etapas aplicáveis de disponibilização e entrega de
material. Como fornecedor, confira a OS e registre o início da produção.
Conferir: o cliente visualiza a atualização e recebe a notificação relevante.

ETAPA 7 — PRODUÇÃO, COLETA E INSPEÇÃO
Como fornecedor, atualize o andamento e registre a conclusão ou disponibilidade
para coleta conforme as ações da tela. Como ADM, registre o recolhimento e
a conferência. Registre retrabalho apenas se aplicável a este ensaio.
Conferir: histórico coerente, situação atual correta e notificação ao cliente
quando a administração registrar o recolhimento das peças.

ETAPA 8 — ENTREGA E ACEITE
Como ADM, registre a entrega final pelo fluxo da OS. Como cliente, confira
a entrega e registre o aceite quando a ação estiver disponível.
Conferir: a OS termina na situação esperada e o histórico mostra as etapas.

ETAPA 9 — FINANCEIRO E RESULTADO ADMINISTRATIVO
Como ADM, use os registros fictícios deste pedido para conferir recebimentos,
repasses ao fornecedor e despesas aplicáveis. Compare com o preço publicado.
Conferir: saldos do pedido e resultado administrativo coerentes, sem registrar
o mesmo movimento duas vezes. O sistema registra o controle; não executa
transferências bancárias. O lucro depende também das despesas registradas.

ETAPA 10 — AVALIAÇÃO, PRIVACIDADE E RELATÓRIOS
Como cliente, faça a avaliação quando o fluxo permitir. Como fornecedor,
confira somente a nota própria disponibilizada. Como ADM, confira avaliação,
gráfico de ranking e relatórios da contratação, inclusive CSV e impressão.
Conferir: ranking e comparação entre empresas exclusivos da administração;
cliente e fornecedor não devem acessar o ranking nem o resultado da ADM.

CONFERÊNCIA FINAL
Para cada etapa, registre OK ou a mensagem exata do erro, junto com o perfil
e os números da solicitação/OS. Se uma etapa bloquear, mantenha o registro
para análise antes de repetir a operação. O teste completo só fica aprovado
depois de todas as etapas aplicáveis serem conferidas pelo usuário.
"""


class ErroCheckpoint(RuntimeError):
    pass


class Git:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.executavel = shutil.which("git")
        if not self.executavel:
            raise ErroCheckpoint("Git não encontrado neste computador.")

    def executar_bytes(self, *argumentos: str, limite: int = 30) -> bytes:
        ambiente = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            retorno = subprocess.run([self.executavel, "--literal-pathspecs", "-C", str(self.raiz), *argumentos],
                capture_output=True, env=ambiente, timeout=limite)
        except subprocess.TimeoutExpired:
            raise ErroCheckpoint("O comando Git demorou além do limite. Confira a conexão e execute novamente; os arquivos locais permanecem disponíveis.") from None
        if retorno.returncode:
            detalhe = retorno.stderr.decode("utf-8", errors="replace").strip()
            raise ErroCheckpoint("Git não concluiu " + argumentos[0] + ": " + detalhe[-4000:])
        return retorno.stdout

    def executar(self, *argumentos: str, limite: int = 30) -> str:
        return self.executar_bytes(*argumentos, limite=limite).decode("utf-8", errors="replace")

    def lista(self, *argumentos: str) -> list[str]:
        return [nome for nome in self.executar(*argumentos).split("\0") if nome]


def localizar_raiz() -> Path:
    for raiz in dict.fromkeys([Path.cwd().resolve(), Path(__file__).resolve().parent]):
        if (raiz / "backend/app/principal.py").is_file() and (raiz / "frontend/package.json").is_file():
            return raiz
    raise ErroCheckpoint("Salve e execute este arquivo na pasta C:\\Users\\Omega\\Desktop\\MEC-Servicos.")


def caminho_seguro(raiz: Path, relativo: str) -> Path:
    p = Path(relativo)
    if p.is_absolute() or ".." in p.parts:
        raise ErroCheckpoint("Caminho fora do projeto: " + relativo)
    alvo = raiz / p
    for componente in [alvo, *alvo.parents]:
        if componente == raiz:
            break
        if componente.is_symlink() or getattr(componente, "is_junction", lambda: False)():
            raise ErroCheckpoint("Arquivo com redirecionamento local precisa de conferência: " + relativo)
    if not alvo.resolve().is_relative_to(raiz):
        raise ErroCheckpoint("Caminho fora do projeto: " + relativo)
    return alvo


def arquivo_local(nome: str) -> bool:
    valor = nome.replace("\\", "/").casefold()
    if valor == "data/.gitkeep":
        return False
    partes = valor.split("/")
    base = partes[-1]
    if any(p in PASTAS_LOCAIS for p in partes[:-1]):
        return True
    if valor.startswith(("frontend/dist/", "htmlcov/")) or base in {".coverage", ".credentials", "credentials.json"}:
        return True
    if base.startswith(".env") and base not in EXEMPLOS_ENV:
        return True
    if any(base.endswith(extensao) for extensao in EXTENSOES_LOCAIS):
        return True
    if base.endswith((".txt", ".json", ".csv")):
        if any(p in base for p in ["credenciais", "senhas", "acessos_iniciais"]):
            return True
        if (base.startswith("mec") and "_relatorio" in base) or re.search(r"_relatorio\.(?:txt|json)$", base):
            return True
    return False


def relatorio_gerado(nome: str) -> bool:
    base = nome.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return base.endswith((".json", ".txt")) and (
        (base.startswith("mec") and "_relatorio" in base)
        or bool(re.search(r"_relatorio\.(?:txt|json)$", base))
    )


def conferir_conteudo(nome: str, dados: bytes) -> None:
    if len(dados) > 25 * 1024 * 1024:
        raise ErroCheckpoint("Arquivo maior que 25 MB precisa de conferência antes do envio: " + nome)
    if any(padrao.search(dados) for padrao in SEGREDOS):
        raise ErroCheckpoint("Possível chave privada ou token encontrado; conteúdo não exibido e envio interrompido: " + nome)


def conferir_origem(git: Git) -> None:
    def origem_mec(url: str) -> bool:
        if url.startswith("git@github.com:"):
            caminho = url.split(":", 1)[1]
        else:
            valor = urlsplit(url)
            if valor.scheme not in {"https", "ssh"} or valor.hostname != "github.com":
                return False
            if valor.scheme == "https" and (valor.username or valor.password):
                return False
            caminho = valor.path.lstrip("/")
        return caminho.rstrip("/").casefold().removesuffix(".git") == "projetoxcadcam-byte/mec-servicos"
    for argumentos in [("remote", "get-url", "--all", "origin"), ("remote", "get-url", "--push", "--all", "origin")]:
        urls = git.executar(*argumentos).strip().splitlines()
        if not urls or not all(origem_mec(url) for url in urls):
            raise ErroCheckpoint("Origin não corresponde ao repositório MEC-Servicos no GitHub.")


def conferir_repositorio(git: Git) -> None:
    raiz_git = Path(git.executar("rev-parse", "--show-toplevel").strip()).resolve()
    if raiz_git != git.raiz:
        raise ErroCheckpoint("A pasta MEC-Servicos precisa ser a raiz do próprio repositório Git.")
    if git.executar("branch", "--show-current").strip() != "main":
        raise ErroCheckpoint("O checkpoint espera a branch main. Sua branch atual foi preservada.")
    if git.lista("ls-files", "--unmerged", "-z"):
        raise ErroCheckpoint("Há conflitos no índice do Git. Resolva-os antes de criar o checkpoint.")
    for marcador in ["MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "index.lock"]:
        nome = Path(git.executar("rev-parse", "--git-path", marcador).strip())
        nome = nome if nome.is_absolute() else git.raiz / nome
        if nome.exists():
            raise ErroCheckpoint("Há outra operação Git em andamento: " + marcador + ". Conclua-a antes do checkpoint.")
    for campo in ["user.name", "user.email"]:
        if not git.executar("config", "--get", campo).strip():
            raise ErroCheckpoint("Configure seu nome e e-mail no Git antes de criar o checkpoint.")


def preparar_gitignore(raiz: Path) -> None:
    alvo = caminho_seguro(raiz, ".gitignore")
    antes = alvo.read_bytes() if alvo.exists() else b""
    # Preserva integralmente os bytes já existentes, inclusive comentários em
    # ANSI/Windows-1252. O marcador e as regras novas usam somente ASCII.
    if MARCADOR.encode("ascii") in antes:
        return
    quebra = b"\r\n" if b"\r\n" in antes else b"\n"
    bloco = (MARCADOR + "\n" + "\n".join(REGRAS) + "\n").encode("ascii").replace(b"\n", quebra)
    if antes and not antes.endswith(b"\n"):
        antes += quebra
    gravar_atomico(alvo, antes + quebra + bloco)


def gravar_atomico(alvo: Path, dados: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=alvo.parent, prefix="mec_git_", delete=False) as arquivo:
        arquivo.write(dados)
        temporario = Path(arquivo.name)
    try:
        os.replace(temporario, alvo)
    finally:
        temporario.unlink(missing_ok=True)


def conferir_commits_pendentes(git: Git, commits: list[str]) -> None:
    # Inspeciona também commits locais anteriores: arquivos removidos depois
    # ainda poderiam estar presentes no histórico que seria enviado.
    for commit in commits:
        nomes = git.lista("diff-tree", "--root", "--no-commit-id", "--name-only", "--diff-filter=AM", "-m", "-r", "-z", commit)
        for nome in nomes:
            if arquivo_local(nome):
                raise ErroCheckpoint("Um commit local ainda não enviado contém arquivo de uso local; histórico preservado para conferência: " + nome)
            conferir_conteudo(nome, git.executar_bytes("show", commit + ":" + nome))


def adicionar_arquivos(git: Git, nomes: list[str]) -> None:
    lote: list[str] = []
    tamanho = 0
    for nome in nomes:
        if lote and tamanho + len(nome) + 3 > 12000:
            git.executar("add", "-A", "--", *lote, limite=120)
            lote = []
            tamanho = 0
        lote.append(nome)
        tamanho += len(nome) + 3
    if lote:
        git.executar("add", "-A", "--", *lote, limite=120)


def preservar_e_desversionar_relatorios(git: Git, nomes: list[str], relatorio: dict) -> None:
    if not nomes:
        relatorio.update(relatorios_retirados_do_git=0, relatorios_locais_preservados=True)
        return
    backup = caminho_seguro(git.raiz, "_mec_backups/GIT_RELATORIOS_TUTORIAL_VALIDADO_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, exist_ok=False)
    manifesto = {}
    for nome in nomes:
        alvo = caminho_seguro(git.raiz, nome)
        dados = alvo.read_bytes() if alvo.is_file() else None
        if alvo.exists() and dados is None:
            raise ErroCheckpoint("Relatório não é um arquivo regular; preservado para conferência: " + nome)
        if dados is not None:
            copia = caminho_seguro(backup, "locais/" + nome)
            copia.parent.mkdir(parents=True, exist_ok=True)
            copia.write_bytes(dados)
            if copia.read_bytes() != dados:
                raise ErroCheckpoint("Não foi possível validar o backup local do relatório: " + nome)
        indice = git.executar_bytes("show", ":" + nome)
        copia_indice = caminho_seguro(backup, "indice/" + nome)
        copia_indice.parent.mkdir(parents=True, exist_ok=True)
        copia_indice.write_bytes(indice)
        manifesto[nome] = {
            "existia_localmente": dados is not None,
            "sha256_local": hashlib.sha256(dados).hexdigest() if dados is not None else None,
            "sha256_indice": hashlib.sha256(indice).hexdigest(),
        }
    (backup / "MANIFESTO.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    relatorio.update(backup_relatorios=str(backup), relatorios_retirados_do_git=0, relatorios_locais_preservados=False)
    print("BACKUP_RELATORIOS=" + str(backup), flush=True)
    # --cached retira somente do índice. O backup contém tanto o arquivo local
    # quanto uma eventual versão diferente que já estava preparada no índice.
    lote = []
    tamanho = 0
    for nome in nomes:
        if lote and tamanho + len(nome) + 3 > 12000:
            git.executar("rm", "--cached", "-f", "--ignore-unmatch", "--", *lote, limite=120)
            lote = []
            tamanho = 0
        lote.append(nome)
        tamanho += len(nome) + 3
    if lote:
        git.executar("rm", "--cached", "-f", "--ignore-unmatch", "--", *lote, limite=120)
    restantes = set(git.lista("ls-files", "-z"))
    for nome, registro in manifesto.items():
        if nome in restantes:
            raise ErroCheckpoint("O relatório ainda consta no índice: " + nome)
        alvo = caminho_seguro(git.raiz, nome)
        atual = hashlib.sha256(alvo.read_bytes()).hexdigest() if alvo.is_file() else None
        if atual != registro["sha256_local"]:
            raise ErroCheckpoint("O relatório local mudou durante a conferência; a alteração posterior foi preservada: " + nome)
    relatorio.update(relatorios_retirados_do_git=len(nomes), relatorios_locais_preservados=True)
    print("RELATORIOS_RETIRADOS_DO_GIT=" + str(len(nomes)), flush=True)
    print("RELATORIOS_LOCAIS_PRESERVADOS=True", flush=True)
    print("HISTORICO_ANTERIOR_GIT_PRESERVADO=True", flush=True)



def conferir_tutorial(raiz: Path, relatorio: dict) -> None:
    caminho = caminho_seguro(raiz, RELATORIO_D66_FIX1)
    if not caminho.is_file():
        raise ErroCheckpoint("Relatório da D66 FIX1 não encontrado. Conclua a instalação antes deste checkpoint.")
    try:
        registro = json.loads(caminho.read_text(encoding="utf-8-sig"))
    except (UnicodeError, ValueError):
        raise ErroCheckpoint("Relatório da D66 FIX1 ilegível; arquivo preservado.") from None
    if not isinstance(registro, dict) or registro.get("resultado") != "OK" or registro.get("revision") != REVISION_D66_FIX1:
        raise ErroCheckpoint("A instalação D66 FIX1 precisa estar concluída com RESULTADO=OK.")
    hashes = {}
    for nome in ARQUIVOS_TUTORIAL:
        alvo = caminho_seguro(raiz, nome)
        if not alvo.is_file() or not alvo.stat().st_size:
            raise ErroCheckpoint("Arquivo do tutorial ausente ou vazio; checkpoint interrompido: " + nome)
        hashes[nome] = hashlib.sha256(alvo.read_bytes()).hexdigest()
    app = caminho_seguro(raiz, "frontend/src/App.tsx").read_text(encoding="utf-8-sig")
    if "./pages/tutorial/TutorialEntrada" not in app:
        raise ErroCheckpoint("A entrada do tutorial não está integrada ao App.tsx.")
    for perfil, layout in [("admin", "Admin"), ("cliente", "Client"), ("fornecedor", "Supplier")]:
        padrao = r'<Route\s+path=[\"\']ajuda[\"\']\s+element=\{<TutorialPage\s+perfil=[\"\']' + perfil + r'[\"\']'
        menu = caminho_seguro(raiz, "frontend/src/layouts/" + layout + "Layout.tsx").read_text(encoding="utf-8-sig")
        if not re.search(padrao, app) or "Ajuda e tutorial" not in menu or "/" + perfil + "/ajuda" not in menu:
            raise ErroCheckpoint("Rota ou menu de ajuda não encontrado para o perfil " + perfil + ".")
    antes = relatorio.get("sha256_tutorial")
    if antes is not None and antes != hashes:
        raise ErroCheckpoint("Um arquivo do tutorial mudou durante o checkpoint; alteração local preservada.")
    relatorio.update(d66_fix1_confirmada=True, sha256_tutorial=hashes)


def conferir_tutorial_no_commit(git: Git, commit: str, relatorio: dict) -> None:
    for nome, esperado in relatorio["sha256_tutorial"].items():
        # O Git pode normalizar CRLF para LF. A comparação textual ignora
        # somente essa normalização, mantendo o conteúdo do arquivo conferido.
        local = caminho_seguro(git.raiz, nome).read_bytes()
        if hashlib.sha256(local).hexdigest() != esperado:
            raise ErroCheckpoint("Um arquivo do tutorial mudou durante o checkpoint; alteração local preservada: " + nome)
        salvo = git.executar_bytes("show", commit + ":" + nome)
        if salvo.replace(b"\r\n", b"\n") != local.replace(b"\r\n", b"\n"):
            raise ErroCheckpoint("O commit não contém a versão conferida do tutorial: " + nome)
    relatorio["tutorial_incluido_no_commit"] = True


def preparar_roteiro(raiz: Path, relatorio: dict) -> None:
    alvo = caminho_seguro(raiz, ROTEIRO_NOME)
    if alvo.exists():
        if not alvo.is_file():
            raise ErroCheckpoint("O destino do roteiro não é um arquivo: " + ROTEIRO_NOME)
        # Preserva inclusive eventuais anotações feitas pelo usuário.
        relatorio["roteiro_existente_preservado"] = True
    else:
        gravar_atomico(alvo, ROTEIRO.encode("utf-8"))
    relatorio["roteiro_teste_completo"] = ROTEIRO_NOME
    print("ROTEIRO=" + ROTEIRO_NOME, flush=True)


def salvar_relatorio(raiz: Path, relatorio: dict) -> None:
    conteudo = (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    for extensao in ["json", "txt"]:
        alvo = caminho_seguro(raiz, STEM + "." + extensao)
        gravar_atomico(alvo, conteudo)
        print(extensao.upper() + "=" + str(alvo), flush=True)


def main() -> int:
    print("MEC-Serviços — Git com tutorial D66 FIX1 validado", flush=True)
    print("REVISION=" + REVISION, flush=True)
    raiz = None
    relatorio = {"revision": REVISION, "resultado": "ERRO", "etapa": "inicio",
                 "commit_criado": False, "push_confirmado": False,
                 "validacao_manual_informada_pelo_usuario": True,
                 "testes_automaticos_executados": False, "operacoes_negocio_executadas": False}
    try:
        raiz = localizar_raiz()
        git = Git(raiz)
        print("ROOT=" + str(raiz), flush=True)
        conferir_repositorio(git)
        conferir_origem(git)
        print("ORIGIN_MEC_CONFIRMADO=True", flush=True)
        print("BRANCH=main", flush=True)
        relatorio["etapa"] = "conferir_d66_fix1"
        conferir_tutorial(raiz, relatorio)
        print("D66_FIX1_CONFIRMADA=True", flush=True)
        relatorio["etapa"] = "conferir_arquivos_locais"
        rastreados = git.lista("ls-files", "-z")
        relatorios_rastreados = [nome for nome in rastreados if relatorio_gerado(nome)]
        indevidos = [nome for nome in rastreados if arquivo_local(nome) and not relatorio_gerado(nome)]
        if indevidos:
            raise ErroCheckpoint("Estes arquivos de uso local já estão rastreados no Git. O checkpoint parou antes do envio; os arquivos foram preservados: " + "; ".join(indevidos[:15]))
        relatorio["etapa"] = "conferir_remoto"
        print("Conferindo origin/main no GitHub...", flush=True)
        git.executar("fetch", "--no-tags", "origin", "refs/heads/main:refs/remotes/origin/main", limite=180)
        atras = int(git.executar("rev-list", "--count", "HEAD..refs/remotes/origin/main").strip())
        if atras:
            raise ErroCheckpoint("Origin/main tem alterações que ainda não estão neste computador. O checkpoint parou para integrar essas alterações; nenhum merge ou descarte foi executado.")
        commits_pendentes = git.executar("rev-list", "refs/remotes/origin/main..HEAD").splitlines()
        conferir_commits_pendentes(git, commits_pendentes)
        relatorio["etapa"] = "preparar_checkpoint"
        preparar_gitignore(raiz)
        preparar_roteiro(raiz, relatorio)
        candidatos = sorted(set(git.lista("ls-files", "--cached", "--others", "--exclude-standard", "-z")))
        nomes = [nome for nome in candidatos if not arquivo_local(nome)]
        for nome in nomes:
            alvo = caminho_seguro(raiz, nome)
            if alvo.is_file():
                conferir_conteudo(nome, alvo.read_bytes())
            elif alvo.exists():
                raise ErroCheckpoint("Destino rastreado precisa de conferência: " + nome)
        print("ARQUIVOS_CONFERIDOS=" + str(len(nomes)), flush=True)
        relatorio["etapa"] = "preservar_relatorios"
        preservar_e_desversionar_relatorios(git, relatorios_rastreados, relatorio)
        relatorio["etapa"] = "preparar_commit"
        adicionar_arquivos(git, nomes)
        staged = git.lista("diff", "--cached", "--name-only", "-z")
        novas_versoes = git.lista("diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z")
        if any(arquivo_local(nome) for nome in novas_versoes):
            raise ErroCheckpoint("O índice contém arquivo de uso local; commit e envio interrompidos.")
        if staged:
            relatorio["etapa"] = "commit"
            print("Criando commit do checkpoint...", flush=True)
            git.executar("commit", "-m", MENSAGEM, limite=180)
            relatorio["commit_criado"] = True
        else:
            print("SEM_ALTERACOES_NOVAS=True; será identificado o commit atual.", flush=True)
        commit = git.executar("rev-parse", "HEAD").strip()
        conferir_commits_pendentes(git, [c for c in git.executar("rev-list", "refs/remotes/origin/main..HEAD").splitlines() if c not in commits_pendentes])
        tag = "checkpoint-tutorial-d66-validado-" + datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        relatorio.update(commit=commit, tag=tag, branch="main", arquivos_no_commit=len(staged))
        relatorio["etapa"] = "tag"
        git.executar("tag", "-a", tag, "-m", "MEC-Servicos com tutorial D66 FIX1 validado pelo usuario", commit)
        tag_objeto = git.executar("rev-parse", "refs/tags/" + tag).strip()
        print("COMMIT=" + commit, flush=True)
        print("TAG=" + tag, flush=True)
        relatorio["etapa"] = "conferir_tutorial_no_commit"
        conferir_tutorial(raiz, relatorio)
        conferir_tutorial_no_commit(git, commit, relatorio)
        relatorio["etapa"] = "push"
        print("Enviando main e a tag ao GitHub...", flush=True)
        git.executar("push", "--atomic", "--set-upstream", "origin", "HEAD:refs/heads/main", "refs/tags/" + tag + ":refs/tags/" + tag, limite=180)
        relatorio["etapa"] = "confirmar_envio"
        refs = {}
        for linha in git.executar("ls-remote", "origin", "refs/heads/main", "refs/tags/" + tag, limite=120).splitlines():
            valor, referencia = linha.split("\t", 1)
            refs[referencia] = valor
        if refs.get("refs/heads/main") != commit or refs.get("refs/tags/" + tag) != tag_objeto:
            raise ErroCheckpoint("O envio precisa de conferência: as referências remotas não correspondem ao checkpoint local.")
        conferir_tutorial_no_commit(git, commit, relatorio)
        relatorio.update(resultado="OK", etapa="concluido", push_confirmado=True)
        print("PUSH_MAIN_CONFIRMADO=True", flush=True)
        print("PUSH_TAG_CONFIRMADO=True", flush=True)
        salvar_relatorio(raiz, relatorio)
        print("RESULTADO=OK", flush=True)
        print("TUTORIAL_INCLUIDO_NO_COMMIT=True", flush=True)
        print("Checkpoint com o tutorial confirmado no GitHub.", flush=True)
        print("Próxima conferência: " + ROTEIRO_NOME, flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ETAPA=" + relatorio["etapa"], flush=True)
        print("ERRO=" + relatorio["erro"], flush=True)
        if relatorio.get("commit"):
            print("CHECKPOINT_LOCAL=" + relatorio["commit"], flush=True)
        if raiz:
            try:
                salvar_relatorio(raiz, relatorio)
            except OSError:
                print("RELATORIO_NAO_GRAVADO=True; preserve a saída do terminal.", flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
