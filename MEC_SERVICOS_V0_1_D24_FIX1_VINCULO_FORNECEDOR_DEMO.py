r"""MEC-Serviços D24 FIX1 — Vínculo do acesso de fornecedor de demonstração.

Na raiz do projeto, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D24_FIX1_VINCULO_FORNECEDOR_DEMO.py

Consulta o SQLite existente em modo somente leitura. Se o fornecedor do login
de demonstração não tem cadastro técnico, procura uma única empresa já
configurada com oportunidades disponíveis. Corrige somente o ID desse acesso
em AuthContext.tsx. Não modifica o banco, capacidades, materiais ou cotações.

Se houver mais de uma opção, informa os IDs e termina sem alterar os fontes.
Uma empresa pode ser indicada com --empresa-id ID. --somente-conferir exibe o
resultado da seleção sem aplicar a mudança. Faz backup do AuthContext.tsx e
do dist anterior; testa e compila; restaura ambos se alguma etapa falhar.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

REVISION = "MEC-SERVICOS-V0.1-D24-FIX1-VINCULO-FORNECEDOR-DEMO-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D24_FIX1_VINCULO_FORNECEDOR_DEMO_RELATORIO"
AUTH_REL = Path("frontend/src/auth/AuthContext.tsx")
DIST_REL = Path("frontend/dist")
EMAIL_DEMO = "fornecedor@mec-servicos.local"


def pular_trivia(texto: str, pos: int) -> int:
    while pos < len(texto):
        if texto[pos].isspace():
            pos += 1
        elif texto.startswith("//", pos):
            fim = texto.find("\n", pos + 2)
            pos = len(texto) if fim < 0 else fim + 1
        elif texto.startswith("/*", pos):
            fim = texto.find("*/", pos + 2)
            if fim < 0:
                raise RuntimeError("Comentário sem fechamento no cadastro de demonstração.")
            pos = fim + 2
        else:
            break
    return pos


def fim_string(texto: str, inicio: int) -> int:
    aspas = texto[inicio]
    pos = inicio + 1
    while pos < len(texto):
        if texto[pos] == "\\":
            pos += 2
        elif texto[pos] == aspas:
            return pos + 1
        else:
            pos += 1
    raise RuntimeError("Texto sem fechamento no cadastro de demonstração.")


def fim_bloco(texto: str, inicio: int) -> int:
    pares = {"{": "}", "[": "]", "(": ")"}
    pilha = []
    pos = inicio
    while pos < len(texto):
        depois = pular_trivia(texto, pos)
        if depois != pos:
            pos = depois
            continue
        caractere = texto[pos]
        if caractere in "\"'`":
            pos = fim_string(texto, pos)
            continue
        if caractere in pares:
            pilha.append(pares[caractere])
        elif caractere in "}])":
            if not pilha or pilha.pop() != caractere:
                raise RuntimeError("Cadastro de demonstração com delimitadores inesperados.")
            if not pilha:
                return pos + 1
        pos += 1
    raise RuntimeError("Cadastro de demonstração sem fechamento.")


def campos_objeto(texto: str, inicio: int, fim: int) -> dict:
    campos = {}
    pos = inicio + 1
    while pos < fim - 1:
        pos = pular_trivia(texto, pos)
        if pos >= fim - 1:
            break
        chave = re.match(r"[A-Za-z_$][\w$]*", texto[pos:])
        if not chave:
            raise RuntimeError("O cadastro de demonstração usa propriedades calculadas ou outro formato. Nenhum fonte foi alterado.")
        nome = chave.group()
        pos = pular_trivia(texto, pos + len(nome))
        if texto[pos] != ":":
            raise RuntimeError("Propriedade do cadastro de demonstração sem valor literal.")
        pos = pular_trivia(texto, pos + 1)
        inicio_valor = pos
        if texto[pos] in "\"'":
            pos = fim_string(texto, pos)
            try:
                valor = ast.literal_eval(texto[inicio_valor:pos])
            except (SyntaxError, ValueError) as erro:
                raise RuntimeError("Valor de demonstração não reconhecido.") from erro
        else:
            numero = re.match(r"\d+", texto[pos:])
            if not numero:
                raise RuntimeError("O cadastro de demonstração usa valores dinâmicos. Nenhum fonte foi alterado.")
            pos += len(numero.group())
            valor = int(numero.group())
        if nome in campos:
            raise RuntimeError("Há propriedades duplicadas no cadastro de demonstração.")
        campos[nome] = {"valor": valor, "inicio": inicio_valor, "fim": pos}
        pos = pular_trivia(texto, pos)
        if pos < fim - 1:
            if texto[pos] != ",":
                raise RuntimeError("Cadastro de demonstração com uma expressão inesperada.")
            pos += 1
    return campos


def localizar_fornecedor_demo(texto: str) -> dict:
    declaracoes = list(re.finditer(r"\bconst\s+USUARIOS\b[^=]*=\s*\[", texto))
    if len(declaracoes) != 1:
        raise RuntimeError("Não encontrei um único cadastro const USUARIOS em AuthContext.tsx. Nenhum fonte foi alterado.")
    inicio = declaracoes[0].end() - 1
    fim = fim_bloco(texto, inicio)
    pos = inicio + 1
    encontrados = []
    while pos < fim - 1:
        pos = pular_trivia(texto, pos)
        if pos >= fim - 1:
            break
        if texto[pos] != "{":
            raise RuntimeError("O cadastro de demonstração usa entradas dinâmicas. Nenhum fonte foi alterado.")
        final = fim_bloco(texto, pos)
        campos = campos_objeto(texto, pos, final)
        email = campos.get("email", {}).get("valor")
        papel = campos.get("role", {}).get("valor")
        if isinstance(email, str) and email.lower() == EMAIL_DEMO and papel == "fornecedor":
            identificador = campos.get("id", {})
            if not isinstance(identificador.get("valor"), int) or identificador["valor"] <= 0:
                raise RuntimeError("O ID do fornecedor de demonstração não é válido.")
            encontrados.append(identificador)
        pos = pular_trivia(texto, final)
        if pos < fim - 1:
            if texto[pos] != ",":
                raise RuntimeError("Formato inesperado entre os acessos de demonstração.")
            pos += 1
    if len(encontrados) != 1:
        raise RuntimeError("Não encontrei um único acesso fornecedor@mec-servicos.local com perfil fornecedor. Nenhum fonte foi alterado.")
    return encontrados[0]


def atualizar_id_demo(texto: str, novo_id: int) -> str:
    if novo_id <= 0:
        raise RuntimeError("O novo ID precisa ser positivo.")
    campo = localizar_fornecedor_demo(texto)
    atualizado = texto[:campo["inicio"]] + str(novo_id) + texto[campo["fim"]:]
    if localizar_fornecedor_demo(atualizado)["valor"] != novo_id:
        raise RuntimeError("Não foi possível validar o vínculo atualizado.")
    return atualizado


def consultar_fornecedores(raiz: Path) -> dict:
    from sqlalchemy import create_engine, event, func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from backend.app.core.configuracao import configuracoes
    from backend.app.models.capacidade import CapacidadeFornecedor
    from backend.app.models.empresa import Empresa
    from backend.app.models.material_fornecedor import MaterialFornecedor
    from backend.app.services.portal_fornecedor import ServicoPortalFornecedor

    url = make_url(configuracoes.url_banco_dados)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:" or url.database.startswith("file:"):
        raise RuntimeError("Esta correção requer o arquivo SQLite existente do MEC-Serviços.")
    caminho = Path(url.database)
    if not caminho.is_absolute():
        caminho = raiz / caminho
    caminho = caminho.resolve()
    if not caminho.is_file():
        raise RuntimeError("O banco configurado não existe. Nenhum banco foi criado.")
    engine = create_engine("sqlite+pysqlite://", creator=lambda: sqlite3.connect(caminho.as_uri() + "?mode=ro", uri=True, timeout=10))

    @event.listens_for(engine, "connect")
    def leitura(conexao, _):
        conexao.execute("PRAGMA query_only=ON")

    try:
        with Session(engine, autoflush=False) as banco:
            empresas = banco.scalars(select(Empresa).where(Empresa.tipo_empresa.in_(("fornecedor", "ambos"))).order_by(Empresa.id)).all()
            fornecedores = []
            for empresa in empresas:
                capacidades = banco.scalar(select(func.count()).select_from(CapacidadeFornecedor).where(CapacidadeFornecedor.empresa_id == empresa.id)) or 0
                materiais = banco.scalar(select(func.count()).select_from(MaterialFornecedor).where(MaterialFornecedor.empresa_id == empresa.id)) or 0
                pagina = ServicoPortalFornecedor(banco).listar_oportunidades(empresa.id, 0, 100)
                fornecedores.append({"id": empresa.id, "razao_social": empresa.razao_social, "tipo_empresa": empresa.tipo_empresa, "capacidades": capacidades, "materiais": materiais, "oportunidades": pagina.total, "solicitacoes_disponiveis": [item.id for item in pagina.itens]})
            return {"banco": str(caminho), "somente_leitura": True, "fornecedores": fornecedores}
    finally:
        engine.dispose()


def selecionar_destino(dados: dict, atual_id: int, destino_id: int | None) -> dict:
    fornecedores = dados["fornecedores"]
    atual = next((item for item in fornecedores if item["id"] == atual_id), None)
    if destino_id is not None:
        destino = next((item for item in fornecedores if item["id"] == destino_id), None)
        if destino is None:
            raise RuntimeError("O ID indicado não pertence a uma empresa fornecedora cadastrada.")
        if not destino["capacidades"] or not destino["materiais"]:
            raise RuntimeError("O fornecedor indicado ainda não tem capacidades e materiais cadastrados.")
        return destino
    if atual is not None and atual["capacidades"] and atual["materiais"]:
        return atual
    candidatas = [item for item in fornecedores if item["capacidades"] and item["materiais"] and item["oportunidades"] > 0]
    if len(candidatas) != 1:
        if candidatas:
            ids = ", ".join(str(item["id"]) for item in candidatas)
            raise RuntimeError("Há mais de um fornecedor configurado com oportunidades (IDs " + ids + "). Confira a lista e execute novamente com --empresa-id ID. Nenhum fonte foi alterado.")
        raise RuntimeError("Não há fornecedor configurado com oportunidades disponíveis para o vínculo automático. Confira a lista de fornecedores. Nenhum fonte foi alterado.")
    return candidatas[0]


def gravar_atomico(caminho: Path, dados: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=caminho.parent, prefix=".mec_d24_vinculo_", delete=False) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(dados)
        os.replace(temporario, caminho)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def executar_etapa(nome: str, comando: list[str], pasta: Path, relatorio: dict) -> None:
    print("Executando " + nome + "...", flush=True)
    ambiente = os.environ.copy()
    ambiente["PYTHONIOENCODING"] = "utf-8"
    processo = subprocess.run(comando, cwd=pasta, env=ambiente, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
    saida = (processo.stdout or "") + (processo.stderr or "")
    relatorio["etapas"].append({"nome": nome, "returncode": processo.returncode, "saida": saida})
    if saida:
        print(saida, end="" if saida.endswith("\n") else "\n", flush=True)
    print(nome.upper().replace(" ", "_") + "_RETURN_CODE=" + str(processo.returncode), flush=True)
    if processo.returncode:
        raise RuntimeError("A etapa " + nome + " falhou. Confira a saída e o relatório.")


def salvar_relatorios(raiz: Path, relatorio: dict) -> None:
    linhas = ["MEC-Serviços D24 FIX1 — Vínculo do Fornecedor Demo", "REVISION=" + REVISION, "RESULTADO=" + relatorio["resultado"], "BANCO_ALTERADO=False"]
    for chave in ("empresa_anterior_id", "empresa_destino_id", "empresa_destino_nome", "solicitacoes_disponiveis", "backup_dir", "restaurado", "erro"):
        if chave in relatorio:
            linhas.append(chave.upper() + "=" + str(relatorio[chave]))
    for etapa in relatorio["etapas"]:
        linhas.extend(["", etapa["nome"], "RETURN_CODE=" + str(etapa["returncode"]), etapa["saida"].rstrip()])
    j = raiz / (RELATORIO_NOME + ".json")
    t = raiz / (RELATORIO_NOME + ".txt")
    gravar_atomico(j, (json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    gravar_atomico(t, ("\n".join(linhas).rstrip() + "\n").encode("utf-8"))
    print("RELATORIO=" + str(t), flush=True)
    print("JSON=" + str(j), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Corrige o ID do fornecedor de demonstração usando cadastros já existentes.")
    parser.add_argument("--empresa-id", type=int, help="Empresa fornecedora escolhida explicitamente.")
    parser.add_argument("--somente-conferir", action="store_true", help="Consulta e seleciona, sem alterar os fontes.")
    args = parser.parse_args()
    raiz = Path.cwd().resolve()
    print("MEC-Serviços D24 FIX1 — Vínculo do Fornecedor Demo", flush=True)
    print("REVISION=" + REVISION, flush=True)
    print("ROOT=" + str(raiz), flush=True)
    relatorio = {"revision": REVISION, "resultado": "ERRO", "banco_alterado": False, "etapas": []}
    marcadores = ("backend/app/core/configuracao.py", "backend/app/services/portal_fornecedor.py", str(AUTH_REL), "frontend/package.json")
    if not all((raiz / nome).is_file() for nome in marcadores):
        print("ERRO=Execute na raiz do MEC-Servicos com o D24 instalado. Nenhum arquivo foi alterado.")
        return 1
    auth = raiz / AUTH_REL
    dist = raiz / DIST_REL
    original = None
    backup = None
    auth_alterado = False
    dist_alteravel = False
    dist_existia = False
    try:
        if args.empresa_id is not None and args.empresa_id <= 0:
            raise RuntimeError("O ID indicado precisa ser positivo.")
        for alvo in (auth, dist):
            if alvo.is_symlink() or not alvo.resolve().is_relative_to(raiz):
                raise RuntimeError("Um destino aponta para fora do projeto. Nenhum fonte foi alterado.")
        if dist.exists() and not dist.is_dir():
            raise RuntimeError("frontend/dist existe, mas não é uma pasta.")
        original = auth.read_bytes()
        texto = original.decode("utf-8-sig")
        atual_id = localizar_fornecedor_demo(texto)["valor"]
        relatorio["empresa_anterior_id"] = atual_id
        sys.path.insert(0, str(raiz))
        dados = consultar_fornecedores(raiz)
        relatorio["consulta"] = dados
        print("BANCO_SOMENTE_LEITURA=True", flush=True)
        print("FORNECEDOR_DEMO_ID_ATUAL=" + str(atual_id), flush=True)
        for item in dados["fornecedores"]:
            print(f"FORNECEDOR=ID {item['id']} | {item['razao_social']} | capacidades={item['capacidades']} | materiais={item['materiais']} | oportunidades={item['oportunidades']} | solicitacoes={item['solicitacoes_disponiveis']}", flush=True)
        destino = selecionar_destino(dados, atual_id, args.empresa_id)
        novo_id = destino["id"]
        relatorio.update({"empresa_destino_id": novo_id, "empresa_destino_nome": destino["razao_social"], "solicitacoes_disponiveis": destino["solicitacoes_disponiveis"]})
        print(f"DESTINO=ID {novo_id} | {destino['razao_social']}", flush=True)
        if args.somente_conferir or atual_id == novo_id:
            relatorio["resultado"] = "OK"
            relatorio["fontes_alterados"] = False
            relatorio["somente_conferir"] = args.somente_conferir
            print("FONTES_ALTERADOS=False", flush=True)
            if not destino["oportunidades"]:
                print("AVISO=O vínculo já aponta para um fornecedor com cadastro técnico. Confira a compatibilidade e as cotações anteriores para explicar a ausência de oportunidades.", flush=True)
        else:
            npm = shutil.which("npm.cmd") or shutil.which("npm")
            if not npm:
                raise RuntimeError("npm não encontrado no PATH. Nenhum fonte foi alterado.")
            pacote = json.loads((raiz / "frontend/package.json").read_bytes().decode("utf-8-sig"))
            if not pacote.get("scripts", {}).get("build"):
                raise RuntimeError("O frontend não possui comando de build. Nenhum fonte foi alterado.")
            novo_texto = atualizar_id_demo(texto, novo_id)
            marcador = b"\xef\xbb\xbf" if original.startswith(b"\xef\xbb\xbf") else b""
            novo = marcador + novo_texto.encode("utf-8")
            backup = raiz / "_mec_backups" / ("D24_FIX1_VINCULO_FORNECEDOR_DEMO_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
            backup.mkdir(parents=True, exist_ok=False)
            relatorio["backup_dir"] = str(backup)
            destino_backup = backup / AUTH_REL
            destino_backup.parent.mkdir(parents=True, exist_ok=True)
            destino_backup.write_bytes(original)
            dist_existia = dist.is_dir()
            if dist_existia:
                shutil.copytree(dist, backup / DIST_REL)
            if auth.read_bytes() != original:
                raise RuntimeError("AuthContext.tsx mudou durante a verificação. A edição atual foi preservada.")
            print("BACKUP_DIR=" + str(backup), flush=True)
            auth_alterado = True
            gravar_atomico(auth, novo)
            relatorio["fontes_alterados"] = True
            print(f"VINCULO_FORNECEDOR_DEMO_ATUALIZADO={atual_id}->{novo_id}", flush=True)
            executar_etapa("pytest", [sys.executable, "-m", "pytest", "tests", "-q", "--ignore=tests/mold"], raiz, relatorio)
            dist_alteravel = True
            executar_etapa("npm build", [npm, "run", "build"], raiz / "frontend", relatorio)
            relatorio["resultado"] = "OK"
        salvar_relatorios(raiz, relatorio)
    except (Exception, KeyboardInterrupt) as erro:
        relatorio["resultado"] = "ERRO"
        relatorio["erro"] = str(erro) or "Operação interrompida."
        print("ERRO=" + relatorio["erro"], flush=True)
        falhas = []
        if auth_alterado:
            try:
                gravar_atomico(auth, original)
            except Exception as falha:
                falhas.append("AuthContext.tsx: " + str(falha))
        if dist_alteravel:
            try:
                if dist.exists():
                    shutil.rmtree(dist)
                if dist_existia:
                    shutil.copytree(backup / DIST_REL, dist)
            except Exception as falha:
                falhas.append("frontend/dist: " + str(falha))
        if auth_alterado or dist_alteravel:
            relatorio["restaurado"] = not falhas
            print("RESTAURADO=" + str(not falhas), flush=True)
        if falhas:
            relatorio["falhas_restauracao"] = falhas
        try:
            salvar_relatorios(raiz, relatorio)
        except Exception as falha:
            print("ERRO_RELATORIO=" + str(falha), flush=True)
    print("RESULTADO=" + relatorio["resultado"], flush=True)
    if relatorio["resultado"] != "OK":
        return 1
    if not args.somente_conferir:
        print("Na aplicação, clique em Sair; atualize com Ctrl+F5; entre novamente como fornecedor.", flush=True)
        print("Abra /fornecedor/solicitacoes e use uma das solicitações disponíveis indicadas acima.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
