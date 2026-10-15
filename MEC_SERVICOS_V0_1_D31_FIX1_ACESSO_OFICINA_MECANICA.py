r"""MEC-Serviços D31 FIX1 — Acesso da oficina mecanica à OS #3.

Pare o backend com Ctrl+C, salve este arquivo na raiz MEC-Servicos e execute:
    .\.venv\Scripts\python.exe .\MEC_SERVICOS_V0_1_D31_FIX1_ACESSO_OFICINA_MECANICA.py

Confere a empresa #1, a OS #3, a contratação e os acessos existentes.
Se faltar uma conta ativa de fornecedor, cria oficina1@mec-servicos.local
pelo serviço D30, com senha aleatória local e troca inicial obrigatória.
Se já houver acesso, informa seu e-mail sem redefinir a senha.
Gera relatório TXT/JSON sem senhas. A senha fica somente no arquivo local
indicado em CREDENCIAIS_LOCAIS, em data, ignorado pelo Git.
Não altera fontes, vínculos de contas existentes nem o banco de negócio.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

REVISION = "MEC-SERVICOS-V0.1-D31-FIX1-ACESSO-OFICINA-MECANICA-2026-10-05"
STEM = "MEC_SERVICOS_V0_1_D31_FIX1_ACESSO_OFICINA_MECANICA_RELATORIO"
EMPRESA_ID = 1
ORDEM_ID = 3
EMAIL_NOVO = "oficina1@mec-servicos.local"
FONTE_ACESSO = "backend/app/core/armazenamento_acesso.py"
SHA_ACESSO = "4c20d1c3fb3bd51a00818cef881a2c9bd6f0129cf449b6b7fb82bc8f051a94ba"
D31_REVISION = "MEC-SERVICOS-V0.1-D31-INTERMEDIACAO-ADMIN-2026-10-05"


class Bloqueio(RuntimeError):
    """Interrupção com mensagem que não contém credenciais."""


def informar(chave, valor):
    print(str(chave) + "=" + str(valor), flush=True)


def localizar_raiz():
    for raiz in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        if (raiz / "backend/app/principal.py").is_file() and (raiz / "frontend/package.json").is_file():
            return raiz
    raise Bloqueio("Salve e execute o script na raiz C:\\Users\\Omega\\Desktop\\MEC-Servicos.")


def seguro(raiz, caminho):
    alvo = Path(caminho)
    if not alvo.is_absolute():
        alvo = raiz / alvo
    if alvo.is_symlink() or any(p.is_symlink() for p in alvo.parents if p == raiz or raiz in p.parents):
        raise Bloqueio("Foi encontrado um vínculo simbólico; execute no projeto local original.")
    resolvido = alvo.resolve()
    if not resolvido.is_relative_to(raiz):
        raise Bloqueio("O arquivo configurado precisa ficar dentro do projeto MEC-Servicos.")
    return resolvido


def executar_git(raiz, *argumentos):
    git = shutil.which("git")
    if not git:
        raise Bloqueio("Git não encontrado; use o terminal configurado para o projeto.")
    return subprocess.run([git, *argumentos], cwd=raiz, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=30)


def conferir_origem(raiz):
    retorno = executar_git(raiz, "remote", "get-url", "origin")
    if retorno.returncode:
        raise Bloqueio("Não foi possível confirmar o repositório MEC-Servicos.")
    url = retorno.stdout.strip()
    if url.startswith("git@github.com:"):
        caminho = url.split(":", 1)[1]
    else:
        partes = urlsplit(url)
        if partes.scheme not in {"https", "ssh"} or partes.hostname != "github.com":
            raise Bloqueio("A origem do projeto não corresponde ao MEC-Servicos conhecido.")
        if partes.scheme == "https" and (partes.username or partes.password):
            raise Bloqueio("Use a origem Git do projeto sem credenciais no endereço.")
        caminho = partes.path.lstrip("/")
    if caminho.lower().rstrip("/").removesuffix(".git") != "projetoxcadcam-byte/mec-servicos":
        raise Bloqueio("A origem do projeto não corresponde ao MEC-Servicos conhecido.")


def exigir_backend_parado():
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.5):
            pass
    except OSError:
        return
    raise Bloqueio("Pare o backend com Ctrl+C no terminal dele antes de executar este FIX1.")


def ignorado_pelo_git(raiz, arquivo):
    relativo = arquivo.relative_to(raiz).as_posix()
    retorno = executar_git(raiz, "check-ignore", "--quiet", "--no-index", "--", relativo)
    rastreado = executar_git(raiz, "ls-files", "--error-unmatch", "--", relativo)
    if retorno.returncode != 0 or rastreado.returncode == 0:
        raise Bloqueio("A pasta de acessos locais não está protegida pelas regras Git instaladas pelo D30.")


@contextmanager
def somente_leitura(banco):
    with closing(sqlite3.connect(banco.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)) as conexao:
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA query_only=ON")
        yield conexao


def identificar(nome):
    return '"' + nome.replace('"', '""') + '"'


def retrato(banco):
    """Dados usados apenas na comparação local; nunca vão para o relatório."""
    with somente_leitura(banco) as conexao:
        resultado = {}
        tabelas = conexao.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        for tabela in tabelas:
            nome = tabela[0]
            linhas = [list(l) for l in conexao.execute("SELECT * FROM " + identificar(nome))]
            resultado[nome] = sorted(linhas, key=lambda l: json.dumps(l, default=str, ensure_ascii=True))
        return resultado


def assinatura(dados):
    return hashlib.sha256(json.dumps(dados, sort_keys=True, default=str, ensure_ascii=True).encode("utf-8")).hexdigest()


def conferir_negocio(banco):
    with somente_leitura(banco) as conexao:
        empresa = conexao.execute("SELECT id,razao_social,tipo_empresa FROM empresas WHERE id=?", (EMPRESA_ID,)).fetchone()
        if empresa is None or empresa["tipo_empresa"] not in {"fornecedor", "ambos"}:
            raise Bloqueio("A empresa #1 não foi encontrada como fornecedor; envie o relatório para conferência.")
        nome = "".join(c for c in unicodedata.normalize("NFKD", empresa["razao_social"]) if not unicodedata.combining(c))
        if " ".join(nome.casefold().split()) != "oficina mecanica":
            raise Bloqueio("O nome da empresa #1 mudou; envie o relatório antes de cadastrar este acesso.")
        ordem = conexao.execute("SELECT id,contratacao_id,empresa_fornecedora_id,status,quantidade FROM ordens_servico WHERE id=?", (ORDEM_ID,)).fetchone()
        if ordem is None or ordem["empresa_fornecedora_id"] != EMPRESA_ID:
            raise Bloqueio("A OS #3 não está vinculada à oficina mecanica (#1); nenhum acesso foi criado.")
        if ordem["status"] not in {"aberta", "em_execucao"}:
            raise Bloqueio("A OS #3 precisa estar aberta ou em execução para continuar este teste.")
        contratacao = conexao.execute("SELECT empresa_fornecedora_id,status FROM contratacoes_servico WHERE id=?", (ordem["contratacao_id"],)).fetchone()
        if contratacao is None or contratacao["empresa_fornecedora_id"] != EMPRESA_ID or contratacao["status"] != "ativa":
            raise Bloqueio("Confira a contratação ativa da OS #3 e seu fornecedor; nenhum acesso foi criado.")
        ciclo = conexao.execute("SELECT status FROM ciclos_intermediacao WHERE ordem_servico_id=?", (ORDEM_ID,)).fetchone()
        if ciclo is None:
            raise Bloqueio("O ciclo administrativo da OS #3 não foi encontrado; nenhum acesso foi criado.")
        return dict(empresa), {**dict(ordem), "etapa_administrativa": ciclo["status"]}


def obter_contas(banco):
    with somente_leitura(banco) as conexao:
        campos = {r["name"] for r in conexao.execute("PRAGMA table_info(usuarios_acesso)")}
        if not {"id", "nome", "email", "perfil", "empresa_id", "ativo", "trocar_senha", "senha_hash"}.issubset(campos):
            raise Bloqueio("O banco de acesso não corresponde ao D30 instalado.")
        contas = [dict(l) for l in conexao.execute("SELECT * FROM usuarios_acesso ORDER BY id")]
        if not any(c["perfil"] == "admin" and c["ativo"] == 1 for c in contas):
            raise Bloqueio("Não foi encontrado administrador ativo no banco de acesso.")
        return contas


def copiar_banco(origem, destino):
    if destino.exists():
        raise Bloqueio("O arquivo de backup já existe; execute novamente para usar outro nome.")
    with destino.open("xb"):
        pass
    os.chmod(destino, 0o600)
    with somente_leitura(origem) as banco, closing(sqlite3.connect(destino)) as copia:
        banco.backup(copia)


def conferir_preservacao(antes, depois, conta_id):
    if set(antes) != set(depois):
        return False
    for tabela in antes:
        atual = depois[tabela]
        if tabela == "usuarios_acesso":
            atuais_antigos = [l for l in atual if l[0] != conta_id]
            if atuais_antigos != antes[tabela] or sum(l[0] == conta_id for l in atual) != 1:
                return False
        elif tabela == "auditoria_acesso":
            novas = [l for l in atual if l not in antes[tabela]]
            if any(l not in atual for l in antes[tabela]) or len(novas) != 1 or novas[0][2] != "criar_acesso_local_d31_fix1":
                return False
        elif antes[tabela] != atual:
            return False
    return True


def credencial_anterior(raiz, anterior, conta, verificar_senha):
    caminho = anterior.get("credenciais_locais")
    if not caminho:
        return None
    try:
        arquivo = seguro(raiz, caminho)
        if not arquivo.is_relative_to(raiz / "data") or not arquivo.is_file() or arquivo.stat().st_size > 16000:
            return None
        campos = dict(l.split("=", 1) for l in arquivo.read_text(encoding="utf-8-sig").splitlines() if "=" in l)
        if campos.get("EMAIL") == conta["email"] and campos.get("EMPRESA_ID") == str(EMPRESA_ID) and verificar_senha(campos.get("SENHA_INICIAL", ""), conta["senha_hash"]):
            return str(arquivo)
    except (OSError, ValueError, Bloqueio):
        pass
    return None


def preparar_acesso(raiz, negocio, acesso, empresa, ordem, armazenamento, verificar_senha, dados, anterior):
    negocio_antes = assinatura(retrato(negocio))
    contas = obter_contas(acesso)
    fornecedores = [c for c in contas if c["perfil"] == "fornecedor" and c["empresa_id"] == EMPRESA_ID]
    ativas = [c for c in fornecedores if c["ativo"] == 1]
    if ativas:
        conta = next((c for c in ativas if c["email"] == EMAIL_NOVO), ativas[0])
        if assinatura(retrato(negocio)) != negocio_antes:
            raise Bloqueio("O banco de negócio mudou durante a conferência; pare o backend e execute novamente.")
        dados.update(resultado="OK", situacao="acesso_existente", usuario_id=conta["id"], email=conta["email"],
                     conta_criada=False, trocar_senha=bool(conta["trocar_senha"]),
                     credenciais_locais=credencial_anterior(raiz, anterior, conta, verificar_senha),
                     contas_anteriores_preservadas=True, historico_negocio_preservado=assinatura(retrato(negocio)) == negocio_antes,
                     orientacao="Use o acesso existente. Se não souber a senha, o administrador pode redefini-la em /conta.")
        return
    if fornecedores:
        raise Bloqueio("Já existe acesso de fornecedor desativado para a empresa #1. Confira sua ativação como administrador em /conta.")
    if any(c["email"].casefold() == EMAIL_NOVO for c in contas):
        raise Bloqueio("O e-mail previsto já pertence a outra conta. Confira os vínculos em /conta; nenhum acesso foi criado.")

    antes = retrato(acesso)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + secrets.token_hex(4)
    backup = seguro(raiz, "data/mec_acessos_preparacao_D31_FIX1_BACKUP_" + carimbo + ".db")
    privado = seguro(raiz, "data/MEC_SERVICOS_D30_ACESSOS_INICIAIS_D31_FIX1_OFICINA_MECANICA_" + carimbo + ".txt")
    ignorado_pelo_git(raiz, backup)
    ignorado_pelo_git(raiz, privado)
    copiar_banco(acesso, backup)
    dados["backup_acessos"] = str(backup)
    if retrato(backup) != antes:
        raise Bloqueio("O banco de acesso mudou durante a preparação; pare o backend e execute novamente.")

    senha = secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="mec_d31_fix1_validacao_") as pasta:
        temporario = Path(pasta) / "acessos.db"
        copiar_banco(backup, temporario)
        teste = armazenamento(temporario)
        usuario = teste.criar_usuario(empresa["razao_social"], EMAIL_NOVO, "fornecedor", EMPRESA_ID, senha)
        teste.registrar_acao(0, "criar_acesso_local_d31_fix1", "usuario/" + str(usuario.usuario_id))
        if not conferir_preservacao(antes, retrato(temporario), usuario.usuario_id):
            raise Bloqueio("A validação temporária não confirmou a preservação das contas anteriores.")
        sessao, token = teste.entrar(EMAIL_NOVO, senha, "127.0.0.1")
        obtido = teste.obter_sessao(token)
        if sessao.empresa_id != EMPRESA_ID or obtido.perfil != "fornecedor" or not obtido.deve_alterar_senha:
            raise Bloqueio("O acesso temporário não confirmou o perfil, a empresa e a troca inicial de senha.")
    dados["login_validado_em_copia"] = True

    if retrato(acesso) != antes or assinatura(retrato(negocio)) != negocio_antes:
        raise Bloqueio("Os dados mudaram durante a preparação; pare o backend e execute novamente.")
    conteudo = ["MEC-Serviços D31 FIX1 — ACESSO LOCAL DA OFICINA MECANICA", "",
                "Use este acesso somente se o relatório da execução indicar RESULTADO=OK.",
                "Não envie este arquivo ao chat nem ao Git. A senha inicial exige troca em Minha conta.", "",
                "PERFIL=fornecedor", "EMAIL=" + EMAIL_NOVO, "SENHA_INICIAL=" + senha,
                "EMPRESA_ID=" + str(EMPRESA_ID), "ORDEM_REFERENCIA=" + str(ORDEM_ID), ""]
    descritor = os.open(privado, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("\n".join(conteudo) + "\n")
    os.chmod(privado, 0o600)
    dados["credenciais_locais"] = str(privado)
    servico = armazenamento(acesso)
    usuario = servico.criar_usuario(empresa["razao_social"], EMAIL_NOVO, "fornecedor", EMPRESA_ID, senha)
    dados.update(conta_criada=True, usuario_id=usuario.usuario_id, email=usuario.email, trocar_senha=True)
    servico.registrar_acao(0, "criar_acesso_local_d31_fix1", "usuario/" + str(usuario.usuario_id) + "/empresa/1/os/3")
    gravada = next((c for c in obter_contas(acesso) if c["id"] == usuario.usuario_id), None)
    if gravada is None or gravada["perfil"] != "fornecedor" or gravada["empresa_id"] != EMPRESA_ID or gravada["ativo"] != 1 or gravada["trocar_senha"] != 1 or not verificar_senha(senha, gravada["senha_hash"]):
        raise Bloqueio("O acesso foi criado, mas a verificação final ficou pendente; envie o relatório TXT/JSON.")
    dados["contas_anteriores_preservadas"] = conferir_preservacao(antes, retrato(acesso), usuario.usuario_id)
    dados["historico_negocio_preservado"] = assinatura(retrato(negocio)) == negocio_antes
    if not dados["contas_anteriores_preservadas"] or not dados["historico_negocio_preservado"]:
        raise Bloqueio("O acesso foi criado, mas a comparação final precisa ser conferida; envie o relatório TXT/JSON.")
    dados.update(resultado="OK", situacao="acesso_criado", orientacao="Reinicie o backend. Entre com o novo e-mail e a senha do arquivo local, troque a senha em Minha conta, entre novamente e abra Produção para a OS #3.")


def salvar_relatorios(raiz, dados):
    conteudo = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    for extensao in ("json", "txt"):
        arquivo = seguro(raiz, STEM + "." + extensao)
        arquivo.write_text(conteudo, encoding="utf-8")
        informar("JSON" if extensao == "json" else "RELATORIO", arquivo)


def main():
    print("MEC-Serviços D31 FIX1 — Acesso da oficina mecanica", flush=True)
    informar("REVISION", REVISION)
    dados = {"revision": REVISION, "resultado": "BLOQUEADO", "empresa_id": EMPRESA_ID,
             "ordem_id": ORDEM_ID, "conta_criada": False, "senhas_transmitidas": False,
             "fontes_alterados": False, "banco_negocio_somente_leitura": True}
    try:
        raiz = localizar_raiz()
    except Bloqueio as erro:
        informar("ERRO", erro)
        informar("RESULTADO", "BLOQUEADO")
        return 1
    try:
        informar("ROOT", raiz)
        conferir_origem(raiz)
        informar("ORIGIN_MEC_CONFIRMADO", True)
        fonte = seguro(raiz, FONTE_ACESSO)
        if not fonte.is_file() or hashlib.sha256(fonte.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != SHA_ACESSO:
            raise Bloqueio("O armazenamento de acesso mudou em relação ao D30; envie esse fonte antes de executar o FIX1.")
        instalacao = json.loads(seguro(raiz, "MEC_SERVICOS_V0_1_D31_INTERMEDIACAO_ADMIN_RELATORIO.json").read_text(encoding="utf-8-sig"))
        if instalacao.get("revision") != D31_REVISION or instalacao.get("resultado") != "OK":
            raise Bloqueio("O relatório D31 não confirma a instalação concluída.")
        exigir_backend_parado()
        os.chdir(raiz)
        sys.path.insert(0, str(raiz))
        from backend.app.core.configuracao import configuracoes
        from backend.app.core.armazenamento_acesso import ArmazenamentoAcesso, verificar_senha
        url = configuracoes.url_banco_dados
        if configuracoes.prefixo_api.rstrip("/") != "/api/v1" or not url.startswith("sqlite:///"):
            raise Bloqueio("Este FIX1 foi preparado para o banco SQLite local do MEC-Servicos com /api/v1.")
        negocio = seguro(raiz, url[len("sqlite:///"):])
        acesso = seguro(raiz, os.environ.get("MEC_ACESSOS_DB", "data/mec_acessos.db"))
        if negocio == acesso or not negocio.is_file() or not acesso.is_file():
            raise Bloqueio("Confira os bancos locais separados de negócio e acesso do D30.")
        empresa, ordem = conferir_negocio(negocio)
        dados.update(empresa_nome=empresa["razao_social"], ordem=ordem)
        informar("VINCULO_OS3_EMPRESA1_CONFIRMADO", True)
        anterior = {}
        relatorio_anterior = seguro(raiz, STEM + ".json")
        if relatorio_anterior.is_file():
            try:
                anterior = json.loads(relatorio_anterior.read_text(encoding="utf-8-sig"))
                if not isinstance(anterior, dict):
                    anterior = {}
            except (OSError, ValueError):
                pass
        preparar_acesso(raiz, negocio, acesso, empresa, ordem, ArmazenamentoAcesso, verificar_senha, dados, anterior)
        informar("CONTA_CRIADA", dados["conta_criada"])
        informar("EMAIL", dados["email"])
        informar("EMPRESA_ID", EMPRESA_ID)
        informar("CONTAS_ANTERIORES_PRESERVADAS", dados["contas_anteriores_preservadas"])
        informar("HISTORICO_NEGOCIO_PRESERVADO", dados["historico_negocio_preservado"])
        if dados.get("credenciais_locais"):
            informar("CREDENCIAIS_LOCAIS", dados["credenciais_locais"])
        print(dados["orientacao"], flush=True)
    except Exception as erro:
        dados["resultado"] = "ACESSO_CRIADO_VERIFICACAO_PENDENTE" if dados["conta_criada"] else "BLOQUEADO"
        dados["erro"] = str(erro) if isinstance(erro, Bloqueio) else "Não foi possível concluir esta execução (" + type(erro).__name__ + "). Envie os relatórios TXT/JSON sem o arquivo de senha."
        informar("ERRO", dados["erro"])
        if dados.get("credenciais_locais"):
            informar("CREDENCIAIS_LOCAIS", dados["credenciais_locais"])
    try:
        salvar_relatorios(raiz, dados)
    except (OSError, Bloqueio):
        informar("ERRO_RELATORIO", "Não foi possível salvar o relatório na raiz do projeto.")
        informar("RESULTADO", dados["resultado"])
        return 1
    informar("RESULTADO", dados["resultado"])
    return 0 if dados["resultado"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
