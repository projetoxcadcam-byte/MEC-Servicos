r"""MEC-Serviços D29 — Contrato e diagnóstico da intermediação administrativa.

Execute na raiz do MEC-Servicos:
    python .\MEC_SERVICOS_V0_1_D29_DIAGNOSTICO_INTERMEDIACAO_ADMIN.py

Usa apenas a biblioteca padrão. Lê os fontes e, quando presente, abre o banco
SQLite em modo somente leitura. Gera o contrato do fluxo pretendido e relatórios.
Não instala autenticação, não altera as telas, não muda registros do banco e não
envia nada ao GitHub. RESULTADO=OK significa que o diagnóstico foi concluído.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

REVISION = "MEC-SERVICOS-V0.1-D29-DIAGNOSTICO-INTERMEDIACAO-ADMIN-2026-10-05"
BASE = "MEC_SERVICOS_V0_1_D29_DIAGNOSTICO_INTERMEDIACAO_ADMIN"
CONTRATO_BASE = "MEC_SERVICOS_V0_1_D29_CONTRATO_INTERMEDIACAO_ADMIN"
REPOSITORIO = "projetoxcadcam-byte/mec-servicos"

CONTRATO = {
    "revision": REVISION,
    "situacao": "contrato_do_fluxo_alvo; ainda_nao_implantado",
    "projeto": "MEC-Serviços",
    "contato_direto_cliente_fornecedor": False,
    "intermediario": "administração",
    "identificacao_contraparte": {
        "padrao": "codigo_publico",
        "premissa": "Adotado para evitar contato direto; confirmar se forem desejados nomes visíveis.",
        "regra": "Cada empresa vê seus próprios dados. A outra parte aparece por código público, sem nome, documento, endereço ou contato.",
        "administracao": "Acessa as identidades e os contatos necessários à operação.",
    },
    "responsabilidades": {
        "cliente": [
            "Solicitar o serviço e disponibilizar requisitos técnicos à administração.",
            "Responder à proposta apresentada pela administração.",
            "Informar a disponibilidade do material e combinar seu encaminhamento com a administração.",
            "Acompanhar o andamento e a entrega final pela plataforma.",
            "Confirmar o recebimento final ou comunicar uma ocorrência à administração.",
        ],
        "fornecedor": [
            "Receber oportunidades técnicas encaminhadas pela administração, sem identificar o cliente.",
            "Apresentar proposta à administração e receber a autorização de execução.",
            "Receber material encaminhado pela administração e informar o andamento da produção.",
            "Sinalizar peças prontas para coleta; essa sinalização não representa entrega ao cliente.",
            "Executar eventual retrabalho solicitado pela administração.",
        ],
        "administracao": [
            "Intermediar solicitações, propostas, contratos e comunicação entre as partes.",
            "Agendar, registrar, conferir e encaminhar o material ao fornecedor.",
            "Agendar e registrar o recolhimento das peças prontas.",
            "Avaliar as peças e registrar aprovação ou reprovação fundamentada.",
            "Coordenar devolução para retrabalho e nova coleta, quando necessário.",
            "Agendar e registrar a entrega das peças aprovadas ao cliente.",
            "Encerrar a OS e a contratação somente após a entrega final registrada.",
        ],
    },
    "etapas_logisticas": [
        {"codigo": "material_agendado", "responsavel": "administracao"},
        {"codigo": "material_recebido", "responsavel": "administracao"},
        {"codigo": "material_conferido", "responsavel": "administracao"},
        {"codigo": "material_encaminhado_ao_fornecedor", "responsavel": "administracao"},
        {"codigo": "em_producao", "responsavel": "fornecedor", "observacao": "Reutiliza o acompanhamento de produção existente."},
        {"codigo": "pronto_para_coleta", "responsavel": "fornecedor"},
        {"codigo": "pecas_recolhidas", "responsavel": "administracao"},
        {"codigo": "em_avaliacao", "responsavel": "administracao"},
        {"codigo": "avaliacao_aprovada", "responsavel": "administracao"},
        {"codigo": "avaliacao_reprovada", "responsavel": "administracao", "observacao": "Exige motivo e segue para retrabalho; não encerra a OS."},
        {"codigo": "retrabalho_solicitado", "responsavel": "administracao"},
        {"codigo": "entrega_final_agendada", "responsavel": "administracao"},
        {"codigo": "entregue_ao_cliente", "responsavel": "administracao"},
        {"codigo": "encerrado", "responsavel": "administracao"},
    ],
    "regras_de_avaliacao": [
        "A administração realiza a avaliação técnica antes de liberar a entrega ao cliente.",
        "Aprovação técnica, recebimento final e avaliação de satisfação são eventos distintos.",
        "Reprovação exige motivo; registrar quantidade afetada e evidências quando disponíveis.",
        "Peças reprovadas voltam ao fornecedor por intermédio da administração e recebem nova avaliação.",
        "O cliente não aprova diretamente uma entrega do fornecedor.",
        "O fornecedor não entrega peças diretamente ao cliente.",
    ],
    "regras_de_acesso": [
        "Autenticar o usuário no servidor e vincular a conta à empresa e ao perfil autorizado.",
        "IDs recebidos do navegador e o perfil no localStorage não comprovam identidade ou autorização.",
        "Cliente e fornecedor acessam apenas seus próprios pedidos e os dados liberados pela administração.",
        "Verificar permissões nas rotas novas e nas rotas legadas; esconder botões não impede chamadas diretas à API.",
        "A conta administrativa é uma conta de operador; não utilizar a empresa cliente como identidade administrativa.",
        "Respostas da API para as empresas omitem identidade, contato e endereço da outra parte.",
        "Observações, nomes de arquivos, anexos e comprovantes destinados à outra parte passam por revisão administrativa.",
        "Comunicação é cliente-administração ou fornecedor-administração; não criar chat direto entre as empresas.",
    ],
    "rastreabilidade": [
        "Registrar OS, lote, etapa, data, operador, quantidades, motivo e evidências pertinentes.",
        "Preservar histórico; não substituir uma ocorrência anterior por uma nova situação.",
        "Impedir duplicação de eventos por duplo clique, repetição de requisição ou concorrência.",
        "Não declarar coleta, inspeção ou entrega final a partir de uma simples mudança de status de produção.",
    ],
    "preservacao_d28": [
        "Manter o checkpoint v0.1.0-d28 e preservar OS, contratações e entregas já concluídas.",
        "Tratar dados antigos como histórico do fluxo anterior, sem inventar etapas administrativas retroativas.",
        "Revisar operações pendentes antes de enquadrá-las no novo fluxo.",
        "Manter CGX e MEC-Serviços independentes.",
    ],
    "ordem_de_implantacao": [
        "Conferir o diagnóstico do projeto real e implementar autenticação e autorização no servidor.",
        "Restringir as rotas legadas e separar as respostas dos portais para ocultar a contraparte.",
        "Aplicar o painel administrativo de material, coleta e avaliação, com histórico persistente.",
        "Substituir entrega direta e aceite do cliente pelo fluxo administrativo e entrega final.",
        "Validar acesso entre perfis, preservação do histórico e o ciclo completo com dados de teste.",
    ],
}

PADRAO_AUTH = re.compile(r"autentic|authenticate|auth_|oauth|jwt|bearer|security|seguranca|verificar_token|usuario_atual|usuario_autenticado|current_user|exigir_perfil|require_role|require_admin", re.I)
CAMPOS = {"razao_social", "cliente_razao_social", "fornecedor_razao_social", "nome_cliente", "nome_fornecedor",
          "telefone", "celular", "whatsapp", "email", "e_mail", "endereco", "documento"}
REGRAS_FRONT = {
    "identificacao_empresa": re.compile(r"\b(?:cliente_razao_social|fornecedor_razao_social|razao_social|nome_cliente|nome_fornecedor)\b"),
    "contato_ou_endereco": re.compile(r"\b(?:telefone|celular|whatsapp|email|e_mail|endereco|documento)\b|mailto:|tel:", re.I),
    "acoes_de_entrega": re.compile(r"\b(?:aceitarEntrega|recusarEntrega|registrarEntrega)\b|/(?:aceitar|recusar|registrar)(?:[`\"'/]|$)"),
    "sessao_no_navegador": re.compile(r"localStorage|sessionStorage"),
    "login_demo": re.compile(r"\b(?:DEMO_USERS|USUARIOS_DEMO|usuariosDemo|demoUsers)\b|mec-servicos\.local|createContext.*\{\s*user:\s*\{", re.I),
}


def nome_expr(no) -> str:
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        anterior = nome_expr(no.value)
        return (anterior + "." if anterior else "") + no.attr
    return ""


def literal_texto(no) -> str | None:
    return no.value if isinstance(no, ast.Constant) and isinstance(no.value, str) else None


def ler_fonte(caminho: Path) -> str:
    if caminho.is_symlink() or caminho.stat().st_size > 3_000_000:
        raise ValueError("Fonte simbólico ou maior que o limite de leitura do diagnóstico.")
    return caminho.read_text(encoding="utf-8-sig")


def origem_mec(url: str) -> bool:
    if url.lower().startswith("git@github.com:"):
        caminho = url.split(":", 1)[1]
    else:
        partes = urlsplit(url)
        if partes.scheme not in {"https", "ssh"} or partes.hostname != "github.com":
            return False
        caminho = partes.path.lstrip("/")
    return caminho.lower().rstrip("/").removesuffix(".git") == REPOSITORIO


def git_leitura(raiz: Path, *argumentos: str) -> subprocess.CompletedProcess:
    executavel = shutil.which("git")
    if not executavel:
        raise RuntimeError("Git não encontrado para conferir o projeto.")
    return subprocess.run([executavel, "-c", "core.quotepath=false", *argumentos], cwd=raiz,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, check=False)


def conferir_projeto(raiz: Path) -> dict:
    necessarios = ("backend/app/principal.py", "backend/app/api/roteador.py", "frontend/src/App.tsx",
                   "frontend/src/auth/AuthContext.tsx", "frontend/src/layouts/AdminLayout.tsx")
    faltam = [item for item in necessarios if not (raiz / item).is_file()]
    if faltam:
        raise RuntimeError("Execute na raiz do MEC-Servicos. Fontes ausentes: " + ", ".join(faltam))
    if not (raiz / ".git").exists():
        return {"conferido": False, "observacao": "Ambiente sem Git; somente a estrutura MEC foi conferida."}
    top = git_leitura(raiz, "rev-parse", "--show-toplevel")
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != raiz:
        raise RuntimeError("A pasta informada difere da raiz Git do projeto.")
    for argumentos in (("remote", "get-url", "--all", "origin"), ("remote", "get-url", "--push", "--all", "origin")):
        resposta = git_leitura(raiz, *argumentos)
        urls = resposta.stdout.splitlines()
        if resposta.returncode != 0 or not urls or not all(origem_mec(url.strip()) for url in urls):
            raise RuntimeError("O origin não corresponde ao repositório GitHub MEC-Servicos esperado.")
    branch = git_leitura(raiz, "branch", "--show-current").stdout.strip()
    commit = git_leitura(raiz, "rev-parse", "HEAD").stdout.strip()
    tag = git_leitura(raiz, "rev-parse", "--verify", "refs/tags/v0.1.0-d28^{commit}")
    return {"conferido": True, "branch": branch, "commit": commit,
            "checkpoint_d28": tag.stdout.strip() if tag.returncode == 0 else None}


def inventariar_backend(raiz: Path) -> dict:
    rotas, sinais, campos, erros, hashes = [], [], [], [], {}
    for arquivo in sorted((raiz / "backend/app").rglob("*.py")):
        relativo = arquivo.relative_to(raiz).as_posix()
        if "__pycache__" in arquivo.parts:
            continue
        try:
            texto = ler_fonte(arquivo)
            hashes[relativo] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
            arvore = ast.parse(texto)
        except (OSError, UnicodeError, SyntaxError, ValueError) as erro:
            erros.append({"arquivo": relativo, "tipo": type(erro).__name__, "linha": getattr(erro, "lineno", None)})
            continue
        prefixos, dependencias_modulo = {}, set()
        for no in ast.walk(arvore):
            identificador = nome_expr(no) if isinstance(no, (ast.Name, ast.Attribute)) else ""
            if identificador and PADRAO_AUTH.search(identificador):
                sinais.append({"arquivo": relativo, "linha": no.lineno, "identificador": identificador})
            campo = None
            if isinstance(no, ast.Attribute) and no.attr in CAMPOS:
                campo = no.attr
            elif isinstance(no, ast.keyword) and no.arg in CAMPOS:
                campo = no.arg
            elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name) and no.target.id in CAMPOS:
                campo = no.target.id
            if campo:
                campos.append({"arquivo": relativo, "linha": no.lineno, "campo": campo})
            if isinstance(no, ast.Call) and nome_expr(no.func).split(".")[-1] in {"Depends", "Security"} and no.args:
                dep = nome_expr(no.args[0])
                if dep:
                    dependencias_modulo.add(dep)
            if isinstance(no, ast.Assign) and isinstance(no.value, ast.Call) and nome_expr(no.value.func).split(".")[-1] == "APIRouter":
                prefixo = next((literal_texto(k.value) for k in no.value.keywords if k.arg == "prefix"), "")
                for alvo in no.targets:
                    if isinstance(alvo, ast.Name):
                        prefixos[alvo.id] = prefixo
        for no in ast.walk(arvore):
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorador in no.decorator_list:
                if not isinstance(decorador, ast.Call) or not isinstance(decorador.func, ast.Attribute):
                    continue
                metodo = decorador.func.attr.lower()
                if metodo not in {"get", "post", "put", "patch", "delete", "api_route"}:
                    continue
                caminho = literal_texto(decorador.args[0]) if decorador.args else next(
                    (literal_texto(k.value) for k in decorador.keywords if k.arg == "path"), None)
                roteador = nome_expr(decorador.func.value)
                prefixo = prefixos.get(roteador, "")
                completo = ((prefixo or "") + caminho) if caminho is not None and prefixo is not None else "<caminho dinâmico>"
                rotas.append({"arquivo": relativo, "linha": no.lineno, "funcao": no.name,
                    "metodo": metodo.upper(), "caminho_relativo": completo,
                    "dependencias_encontradas_no_modulo": sorted(dependencias_modulo),
                    "sinal_de_dependencia_auth_no_modulo": any(PADRAO_AUTH.search(dep) for dep in dependencias_modulo)})
    # As evidências são locais ao módulo. Dependências globais, proxy e execução
    # precisam ser verificados antes de concluir que uma rota está protegida.
    vistos = set(); sinais_unicos = []
    for sinal in sinais:
        chave = (sinal["arquivo"], sinal["linha"], sinal["identificador"])
        if chave not in vistos:
            vistos.add(chave); sinais_unicos.append(sinal)
    return {"rotas": rotas, "indicios_autenticacao": sinais_unicos, "campos_identificacao_contato": campos,
            "fontes_nao_analisados": erros, "sha256_fontes": hashes,
            "limite": "Inventário estático; não comprova proteção em execução e não analisa proxies ou extensões externas."}


def inventariar_frontend(raiz: Path) -> dict:
    encontrados, hashes, erros = [], {}, []
    pasta = raiz / "frontend/src"
    for arquivo in sorted(pasta.rglob("*")):
        if arquivo.suffix not in {".ts", ".tsx"} or not arquivo.is_file():
            continue
        relativo = arquivo.relative_to(raiz).as_posix()
        try:
            texto = ler_fonte(arquivo)
            hashes[relativo] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        except (OSError, UnicodeError, ValueError) as erro:
            erros.append({"arquivo": relativo, "tipo": type(erro).__name__}); continue
        for numero, linha in enumerate(texto.splitlines(), 1):
            for categoria, padrao in REGRAS_FRONT.items():
                if padrao.search(linha):
                    encontrados.append({"arquivo": relativo, "linha": numero, "categoria": categoria})
    return {"ocorrencias": encontrados, "sha256_fontes": hashes, "fontes_nao_analisados": erros,
            "limite": "Ocorrências indicam pontos para revisão. Dados da própria empresa e campos de login não são vazamento por si só. Valores e fontes completos não são copiados."}


def consultar_banco(raiz: Path) -> dict:
    arquivo = raiz / "data/mec_servicos.db"
    if not arquivo.is_file() or arquivo.is_symlink():
        return {"consultado": False, "observacao": "Banco SQLite padrão ausente ou simbólico; nenhum banco foi criado."}
    resultado = {"consultado": False, "somente_leitura": True, "tabelas": {}}
    try:
        conexao = sqlite3.connect(arquivo.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            conexao.execute("PRAGMA query_only = ON")
            conexao.execute("BEGIN")
            existentes = {linha[0] for linha in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for tabela in ("ordens_servico", "contratacoes_servico", "entregas_servico", "etapas_producao"):
                if tabela not in existentes:
                    continue
                # Nomes fixos do domínio, sem interpolação de entrada do usuário.
                colunas = {linha[1] for linha in conexao.execute(f'PRAGMA table_info("{tabela}")')}
                total = conexao.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
                resumo = {"total": total}
                if "status" in colunas:
                    resumo["por_status"] = {str(status): quantidade for status, quantidade in conexao.execute(
                        f'SELECT status, COUNT(*) FROM "{tabela}" GROUP BY status')}
                resultado["tabelas"][tabela] = resumo
            resultado["consultado"] = True
        finally:
            conexao.close()
    except sqlite3.Error as erro:
        resultado["erro"] = type(erro).__name__
        resultado["observacao"] = "Não foi possível consultar o banco. Nenhum registro foi alterado."
    return resultado


def pontos_de_ajuste(backend: dict, frontend: dict) -> list[dict]:
    rotas = backend["rotas"]
    decisoes = [r for r in rotas if "/portal-cliente/entregas/" in r["caminho_relativo"]
                and r["caminho_relativo"].endswith(("/aceitar", "/recusar"))]
    empresas = [r for r in rotas if r["caminho_relativo"].startswith("/empresas")]
    legado = [r for r in rotas if r["arquivo"].endswith("/rotas/entregas.py") and r["metodo"] != "GET"]
    return [
        {"codigo": "autenticacao_servidor", "prioridade": "alta",
         "situacao": "indicios_a_conferir" if backend["indicios_autenticacao"] else "nao_identificada_estaticamente",
         "acao": "Conferir proteção global e autenticar perfil/empresa no servidor antes de liberar o novo painel administrativo."},
        {"codigo": "aceite_cliente_d28", "prioridade": "alta", "rotas": decisoes,
         "acao": "Substituir o aceite/recusa direta do cliente pela avaliação administrativa e pelo registro da entrega final."},
        {"codigo": "rotas_entrega_legadas", "prioridade": "alta", "rotas": legado,
         "acao": "Restringir também os caminhos legados; não deixar alternativas à regra administrativa."},
        {"codigo": "consulta_empresas", "prioridade": "alta", "rotas": empresas,
         "acao": "Restringir cadastro/listagem completa à administração e autorizar a consulta dos próprios dados quando necessária."},
        {"codigo": "identidades_e_comunicacao", "prioridade": "alta",
         "ocorrencias_backend": len(backend["campos_identificacao_contato"]),
         "ocorrencias_frontend": sum(o["categoria"] in {"identificacao_empresa", "contato_ou_endereco"} for o in frontend["ocorrencias"]),
         "acao": "Separar as respostas dos portais; revisar campos, observações e anexos antes de repassá-los à outra parte."},
        {"codigo": "material_coleta_qualidade_entrega", "prioridade": "alta",
         "acao": "Registrar o novo ciclo administrativo separado das etapas de produção e do histórico D28 já concluído."},
    ]


def texto_contrato() -> str:
    linhas = ["MEC-Serviços D29 — Contrato do fluxo administrativo", "REVISION=" + REVISION,
        "SITUACAO=FLUXO_ALVO_AINDA_NAO_IMPLANTADO", "",
        "REGRA PRINCIPAL", "Cliente e fornecedor não mantêm contato direto. A administração intermedeia toda a operação.",
        "Identificação da outra empresa por código público: premissa adotada para implementar a regra de ausência de contato.", "",
        "RESPONSABILIDADES"]
    for perfil, regras in CONTRATO["responsabilidades"].items():
        linhas.extend([perfil.upper(), *["- " + regra for regra in regras], ""])
    linhas.append("ETAPAS")
    for etapa in CONTRATO["etapas_logisticas"]:
        linhas.append("- " + etapa["codigo"] + " | responsável=" + etapa["responsavel"]
                      + (" | " + etapa["observacao"] if etapa.get("observacao") else ""))
    for chave, titulo in (("regras_de_avaliacao", "AVALIAÇÃO"), ("regras_de_acesso", "ACESSO E COMUNICAÇÃO"),
                          ("rastreabilidade", "RASTREABILIDADE"), ("preservacao_d28", "HISTÓRICO D28"),
                          ("ordem_de_implantacao", "ORDEM DE IMPLANTAÇÃO")):
        linhas.extend(["", titulo, *["- " + regra for regra in CONTRATO[chave]]])
    return "\n".join(linhas) + "\n"


def gravar_resultados(raiz: Path, arquivos: dict[str, bytes]) -> None:
    # Preserva qualquer contrato que o usuário já tenha editado.
    for nome, conteudo in arquivos.items():
        caminho = raiz / nome
        if caminho.is_symlink():
            raise RuntimeError("Destino simbólico não permitido: " + nome)
        if nome.startswith(CONTRATO_BASE) and caminho.exists() and caminho.read_bytes() != conteudo:
            raise RuntimeError("O contrato existente difere deste diagnóstico e foi preservado: " + nome)
    anteriores = {nome: (raiz / nome).read_bytes() if (raiz / nome).exists() else None for nome in arquivos}
    alterados = {nome: conteudo for nome, conteudo in arquivos.items() if anteriores[nome] != conteudo}
    existentes = [nome for nome in alterados if anteriores[nome] is not None]
    if existentes:
        backup = raiz / "_mec_backups" / ("D29_DIAGNOSTICO_ADMIN_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        backup.mkdir(parents=True, exist_ok=False)
        for nome in existentes:
            (backup / nome).write_bytes(anteriores[nome])
        print("BACKUP_RELATORIOS=" + str(backup), flush=True)
    gravados = []
    try:
        for nome, conteudo in alterados.items():
            temporario = None
            try:
                with tempfile.NamedTemporaryFile(dir=raiz, prefix="mec_d29_diag_", delete=False) as arquivo:
                    temporario = Path(arquivo.name); arquivo.write(conteudo)
                if ((raiz / nome).read_bytes() if (raiz / nome).exists() else None) != anteriores[nome]:
                    raise RuntimeError("O destino mudou durante a gravação: " + nome)
                os.replace(temporario, raiz / nome)
                gravados.append(nome)
            finally:
                if temporario is not None:
                    temporario.unlink(missing_ok=True)
    except (Exception, KeyboardInterrupt):
        for nome in reversed(gravados):
            if anteriores[nome] is None:
                (raiz / nome).unlink(missing_ok=True)
            else:
                (raiz / nome).write_bytes(anteriores[nome])
        raise


def main(argumentos=None) -> int:
    parser = argparse.ArgumentParser(description="Contrato e diagnóstico da intermediação administrativa MEC.")
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="Raiz do MEC-Servicos; por padrão, a pasta atual.")
    args = parser.parse_args(argumentos)
    raiz = args.raiz.resolve()
    print("MEC-Serviços D29 — Diagnóstico da Intermediação Administrativa", flush=True)
    print("REVISION=" + REVISION, flush=True)
    try:
        estado_git = conferir_projeto(raiz)
        backend = inventariar_backend(raiz)
        frontend = inventariar_frontend(raiz)
        banco = consultar_banco(raiz)
        ajustes = pontos_de_ajuste(backend, frontend)
        linhas = ["MEC-Serviços D29 — Diagnóstico da Intermediação Administrativa", "REVISION=" + REVISION,
            "ROOT=" + str(raiz), "VERIFICACAO_ESTATICA=True",
            "ORIGIN_MEC_CONFIRMADO=" + str(estado_git["conferido"]),
            "CONTRATO_CONTATO_DIRETO_PERMITIDO=False", "CONTRAPARTE_POR_CODIGO=PREMISSA_ADOTADA",
            "ROTAS_INVENTARIADAS=" + str(len(backend["rotas"])),
            "AUTENTICACAO_SERVIDOR=" + ajustes[0]["situacao"].upper(),
            "ROTAS_ACEITE_RECUSA_CLIENTE=" + str(len(ajustes[1]["rotas"])),
            "ROTAS_ENTREGA_LEGADAS_MUTACAO=" + str(len(ajustes[2]["rotas"])),
            "OCORRENCIAS_LOGIN_DEMO=" + str(sum(o["categoria"] == "login_demo" for o in frontend["ocorrencias"])),
            "FONTES_NAO_ANALISADOS=" + str(len(backend["fontes_nao_analisados"]) + len(frontend["fontes_nao_analisados"])),
            "BANCO_CONSULTADO=" + str(banco["consultado"]), "BANCO_SOMENTE_LEITURA=True",
            "CODIGO_APLICACAO_ALTERADO=False", "REGISTROS_BANCO_ALTERADOS=False", "INTERMEDIACAO_IMPLANTADA=False", ""]
        for tabela, resumo in banco.get("tabelas", {}).items():
            linhas.append("BANCO_RESUMO=" + tabela + " | " + json.dumps(resumo, ensure_ascii=False, sort_keys=True))
        if banco.get("observacao"):
            linhas.append("BANCO_OBSERVACAO=" + banco["observacao"])
        linhas.extend(["", "PONTOS PARA APLICAÇÃO DO NOVO FLUXO"])
        for ajuste in ajustes:
            linhas.append("AJUSTE=" + ajuste["codigo"] + " | " + ajuste["acao"])
            for rota in ajuste.get("rotas", []):
                linhas.append("ROTA=" + rota["metodo"] + " " + rota["caminho_relativo"]
                              + " | " + rota["arquivo"] + ":" + str(rota["linha"]))
        linhas.extend(["", "LIMITES=" + backend["limite"],
            "PROXIMO=Conferir o relatório e aplicar autenticação, restrição das rotas e o painel administrativo na sequência.",
            "RESULTADO=OK"])
        relatorio = {"revision": REVISION, "gerado_em": datetime.now().astimezone().isoformat(),
            "resultado": "OK", "raiz": str(raiz), "estado_git": estado_git,
            "intermediacao_implantada": False, "codigo_aplicacao_alterado": False, "registros_banco_alterados": False,
            "contrato": CONTRATO, "backend": backend, "frontend": frontend, "banco": banco, "ajustes": ajustes}
        # Confere que os fontes examinados não mudaram durante a análise.
        for relativo, esperado in {**backend["sha256_fontes"], **frontend["sha256_fontes"]}.items():
            if hashlib.sha256((raiz / relativo).read_bytes()).hexdigest() != esperado:
                raise RuntimeError("Um fonte mudou durante a análise. Execute novamente: " + relativo)
        gravar_resultados(raiz, {
            CONTRATO_BASE + ".json": (json.dumps(CONTRATO, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            CONTRATO_BASE + ".txt": texto_contrato().encode("utf-8"),
            BASE + "_RELATORIO.json": (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            BASE + "_RELATORIO.txt": ("\n".join(linhas) + "\n").encode("utf-8"),
        })
        for linha in linhas[2:-1]:
            print(linha, flush=True)
        print("CONTRATO=" + str(raiz / (CONTRATO_BASE + ".txt")), flush=True)
        print("RELATORIO=" + str(raiz / (BASE + "_RELATORIO.txt")), flush=True)
        print("JSON=" + str(raiz / (BASE + "_RELATORIO.json")), flush=True)
        print("RESULTADO=OK", flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as erro:
        print("ERRO=" + (str(erro) or "Diagnóstico interrompido pelo usuário."), flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
