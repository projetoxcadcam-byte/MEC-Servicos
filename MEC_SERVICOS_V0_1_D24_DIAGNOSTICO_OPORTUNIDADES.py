r"""MEC-Serviços D24 — Diagnóstico das solicitações disponíveis ao fornecedor.

Execute na raiz do MEC-Servicos, com a .venv ativa:
    python .\MEC_SERVICOS_V0_1_D24_DIAGNOSTICO_OPORTUNIDADES.py

Usa o ID do fornecedor no AuthContext.tsx. Para consultar outra empresa:
    python .\MEC_SERVICOS_V0_1_D24_DIAGNOSTICO_OPORTUNIDADES.py --empresa-id 3

Consulta o cadastro e explica a exclusão de cada solicitação. Não cadastra
capacidades, não envia cotações e não altera os fontes. Em SQLite abre o banco
existente em modo somente leitura. Grava apenas os relatórios TXT e JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

REVISION = "MEC-SERVICOS-V0.1-D24-DIAGNOSTICO-OPORTUNIDADES-2026-10-02"
RELATORIO_NOME = "MEC_SERVICOS_V0_1_D24_DIAGNOSTICO_OPORTUNIDADES_RELATORIO"


def fornecedor_do_frontend(raiz: Path) -> int:
    texto = (raiz / "frontend/src/auth/AuthContext.tsx").read_bytes().decode("utf-8-sig")
    ids = set()
    for item in re.finditer(r'''\{([^{}]*?\brole\s*:\s*["']fornecedor["'][^{}]*?)\}''', texto, re.S):
        numero = re.search(r"\bid\s*:\s*(\d+)\b", item.group(1))
        if numero:
            ids.add(int(numero.group(1)))
    if len(ids) != 1:
        raise RuntimeError("Não identifiquei um único fornecedor no AuthContext.tsx. Execute com --empresa-id seguido do ID da empresa do seu acesso.")
    return ids.pop()


def abrir_engine_leitura(raiz: Path, url_banco: str):
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import make_url

    url = make_url(url_banco)
    if url.get_backend_name() != "sqlite":
        raise RuntimeError("Este diagnóstico foi preparado para o banco SQLite do MEC-Serviços. Nenhum banco foi alterado.")
    if not url.database or url.database == ":memory:" or url.database.startswith("file:"):
        raise RuntimeError("O diagnóstico precisa de um caminho SQLite existente, conforme a configuração do projeto.")
    caminho = Path(url.database)
    if not caminho.is_absolute():
        caminho = raiz / caminho
    caminho = caminho.resolve()
    if not caminho.is_file():
        raise RuntimeError("O banco configurado não foi encontrado: " + str(caminho) + ". Não foi criado um banco novo.")
    uri = caminho.as_uri() + "?mode=ro"
    engine = create_engine("sqlite+pysqlite://", creator=lambda: sqlite3.connect(uri, uri=True, timeout=10))

    @event.listens_for(engine, "connect")
    def somente_leitura(conexao, _):
        conexao.execute("PRAGMA query_only=ON")

    return engine, caminho


def analisar_solicitacao(item, capacidades, materiais, propria_cotacao, possui_aceita, empresa_valida, processo_nome, material_nome):
    motivos = []
    if not empresa_valida:
        motivos.append("A empresa não está cadastrada como fornecedor ou ambos.")
    if item.status != "aberta":
        motivos.append(f"A solicitação está {item.status}; precisa estar aberta.")
    if propria_cotacao is not None:
        motivos.append(f"Esta empresa já possui a cotação #{propria_cotacao['id']} ({propria_cotacao['status']}) para o pedido. Uma segunda proposta não é permitida.")
    if possui_aceita:
        motivos.append("O cliente já aceitou uma cotação para este pedido.")
    if item.material_id not in materiais:
        motivos.append(f"O material {material_nome} (ID {item.material_id}) não está vinculado ao fornecedor.")

    candidatas = [cap for cap in capacidades if cap.processo_id == item.processo_id]
    checagens = []
    capacidade_id = None
    if not candidatas:
        motivos.append(f"O fornecedor não possui capacidade cadastrada para {processo_nome} (ID {item.processo_id}).")
    else:
        alternativas = []
        for capacidade in candidatas:
            falhas = []
            verificacoes = []
            for eixo in ("x", "y", "z"):
                campo = f"dimensao_{eixo}_maxima_mm"
                limite = getattr(capacidade, campo)
                requerida = getattr(item, campo)
                atende = limite >= requerida
                verificacoes.append({"criterio": "dimensao_" + eixo, "capacidade_mm": str(limite), "requisito_mm": str(requerida), "atende": atende})
                if not atende:
                    falhas.append(f"Eixo {eixo.upper()}: o pedido exige {requerida} mm, mas a capacidade cadastrada é {limite} mm.")
            tolerancia_ok = capacidade.tolerancia_minima_mm <= item.tolerancia_requerida_mm
            verificacoes.append({"criterio": "tolerancia", "capacidade_mm": str(capacidade.tolerancia_minima_mm), "requisito_mm": str(item.tolerancia_requerida_mm), "atende": tolerancia_ok})
            if not tolerancia_ok:
                falhas.append(f"Tolerância: o pedido exige {item.tolerancia_requerida_mm} mm, mas o mínimo cadastrado do fornecedor é {capacidade.tolerancia_minima_mm} mm.")
            alternativas.append((capacidade.id, falhas, verificacoes))
        capacidade_id, falhas, checagens = min(alternativas, key=lambda alternativa: len(alternativa[1]))
        motivos.extend(falhas)

    return {
        "solicitacao_id": item.id,
        "empresa_cliente_id": item.empresa_cliente_id,
        "status": item.status,
        "processo_id": item.processo_id, "processo_nome": processo_nome,
        "material_id": item.material_id, "material_nome": material_nome,
        "dimensoes_mm": [str(getattr(item, f"dimensao_{eixo}_maxima_mm")) for eixo in ("x", "y", "z")],
        "tolerancia_requerida_mm": str(item.tolerancia_requerida_mm),
        "quantidade": item.quantidade,
        "capacidade_comparada_id": capacidade_id,
        "checagens": checagens,
        "disponivel_para_cotar": not motivos,
        "motivos": motivos,
    }


def consultar(raiz: Path, empresa_id: int, limite: int) -> dict:
    from sqlalchemy import func, inspect, select
    from sqlalchemy.orm import Session

    from backend.app.core.configuracao import configuracoes
    from backend.app.models.capacidade import CapacidadeFornecedor
    from backend.app.models.cotacao import CotacaoFornecedor
    from backend.app.models.empresa import Empresa
    from backend.app.models.material import Material
    from backend.app.models.material_fornecedor import MaterialFornecedor
    from backend.app.models.processo import ProcessoFabricacao
    from backend.app.models.solicitacao import SolicitacaoServico
    from backend.app.services.portal_fornecedor import ServicoPortalFornecedor

    engine, caminho = abrir_engine_leitura(raiz, configuracoes.url_banco_dados)
    try:
        tabelas = set(inspect(engine).get_table_names())
        obrigatorias = {modelo.__tablename__ for modelo in (Empresa, CapacidadeFornecedor, MaterialFornecedor, SolicitacaoServico, CotacaoFornecedor, Material, ProcessoFabricacao)}
        if ausentes := obrigatorias - tabelas:
            raise RuntimeError("Tabelas ausentes no banco configurado: " + ", ".join(sorted(ausentes)))
        with Session(engine, autoflush=False) as banco:
            empresa = banco.get(Empresa, empresa_id)
            if empresa is None:
                raise RuntimeError(f"A empresa ID {empresa_id} não existe no banco configurado. Confira o ID da empresa do acesso de fornecedor.")
            capacidades = banco.scalars(select(CapacidadeFornecedor).where(CapacidadeFornecedor.empresa_id == empresa_id)).all()
            materiais = set(banco.scalars(select(MaterialFornecedor.material_id).where(MaterialFornecedor.empresa_id == empresa_id)).all())
            processos_nomes = dict(banco.execute(select(ProcessoFabricacao.id, ProcessoFabricacao.nome)).all())
            materiais_nomes = dict(banco.execute(select(Material.id, Material.nome)).all())
            total_solicitacoes = banco.scalar(select(func.count()).select_from(SolicitacaoServico)) or 0
            pedidos = banco.scalars(select(SolicitacaoServico).order_by(SolicitacaoServico.id.desc()).limit(limite)).all()
            cotacoes = defaultdict(list)
            if pedidos:
                consulta = select(CotacaoFornecedor.id, CotacaoFornecedor.solicitacao_id, CotacaoFornecedor.empresa_fornecedora_id, CotacaoFornecedor.status).where(CotacaoFornecedor.solicitacao_id.in_([pedido.id for pedido in pedidos]))
                for id_cotacao, id_pedido, id_empresa, status in banco.execute(consulta):
                    cotacoes[id_pedido].append({"id": id_cotacao, "empresa_id": id_empresa, "status": status})
            empresa_valida = empresa.tipo_empresa in {"fornecedor", "ambos"}
            itens = [analisar_solicitacao(
                pedido, capacidades, materiais,
                next((cotacao for cotacao in cotacoes[pedido.id] if cotacao["empresa_id"] == empresa_id), None),
                any(cotacao["status"] == "aceita" for cotacao in cotacoes[pedido.id]),
                empresa_valida,
                processos_nomes.get(pedido.processo_id, f"Processo #{pedido.processo_id} não encontrado"),
                materiais_nomes.get(pedido.material_id, f"Material #{pedido.material_id} não encontrado"),
            ) for pedido in pedidos]
            total_portal = ServicoPortalFornecedor(banco).listar_oportunidades(empresa_id, 0, 100).total if empresa_valida else 0
            return {
                "banco": str(caminho), "banco_somente_leitura": True,
                "empresa": {"id": empresa.id, "razao_social": empresa.razao_social, "tipo_empresa": empresa.tipo_empresa},
                "capacidades": [{"id": cap.id, "processo_id": cap.processo_id, "processo_nome": processos_nomes.get(cap.processo_id, "Não encontrado"), "dimensoes_maximas_mm": [str(getattr(cap, f"dimensao_{eixo}_maxima_mm")) for eixo in ("x", "y", "z")], "tolerancia_minima_mm": str(cap.tolerancia_minima_mm)} for cap in capacidades],
                "materiais": [{"id": id_material, "nome": materiais_nomes.get(id_material, "Não encontrado")} for id_material in sorted(materiais)],
                "total_solicitacoes_no_banco": total_solicitacoes,
                "total_oportunidades_portal_d24": total_portal,
                "limite_analisado": limite,
                "solicitacoes": itens,
                "alteracoes_no_banco": False,
            }
    finally:
        engine.dispose()


def salvar_relatorios(raiz: Path, relatorio: dict, linhas: list[str]) -> None:
    json_path = raiz / (RELATORIO_NOME + ".json")
    txt_path = raiz / (RELATORIO_NOME + ".txt")
    json_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    txt_path.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8", newline="\n")
    print("RELATORIO=" + str(txt_path))
    print("JSON=" + str(json_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Explica as oportunidades do fornecedor sem alterar banco ou fontes.")
    parser.add_argument("--empresa-id", type=int, help="ID da empresa do acesso de fornecedor; padrão: cadastro no AuthContext.tsx.")
    parser.add_argument("--limite", type=int, default=100, help="Máximo de solicitações recentes analisadas; padrão 100.")
    args = parser.parse_args()
    raiz = Path.cwd().resolve()
    linhas = ["MEC-Serviços D24 — Diagnóstico de Oportunidades", "REVISION=" + REVISION, "ROOT=" + str(raiz)]
    for linha in linhas:
        print(linha, flush=True)
    relatorio = {"revision": REVISION, "gerado_em_utc": datetime.now(timezone.utc).isoformat(), "resultado": "ERRO", "alteracoes_no_banco": False}
    marcadores = ("backend/app/core/configuracao.py", "backend/app/services/portal_fornecedor.py", "frontend/src/auth/AuthContext.tsx")
    if not all((raiz / nome).is_file() for nome in marcadores):
        print("ERRO=Execute na raiz do MEC-Servicos com o D24 instalado. Nenhum arquivo foi alterado.")
        return 1
    try:
        if args.empresa_id is not None and args.empresa_id <= 0:
            raise RuntimeError("O ID da empresa precisa ser positivo.")
        if not 1 <= args.limite <= 10_000:
            raise RuntimeError("O limite precisa estar entre 1 e 10000.")
        empresa_id = args.empresa_id if args.empresa_id is not None else fornecedor_do_frontend(raiz)
        origem = "informado no comando" if args.empresa_id is not None else "cadastro de fornecedor no AuthContext.tsx"
        sys.path.insert(0, str(raiz))
        relatorio.update(consultar(raiz, empresa_id, args.limite))
        relatorio["resultado"] = "OK"
        empresa = relatorio["empresa"]
        linhas.extend([
            f"EMPRESA_ID={empresa_id} ({origem})",
            f"EMPRESA={empresa['razao_social']} | tipo={empresa['tipo_empresa']}",
            "BANCO=" + relatorio["banco"], "BANCO_SOMENTE_LEITURA=True",
            f"CAPACIDADES_CADASTRADAS={len(relatorio['capacidades'])}",
        ])
        for capacidade in relatorio["capacidades"]:
            linhas.append(f"CAPACIDADE=#{capacidade['id']} | processo={capacidade['processo_nome']} (ID {capacidade['processo_id']}) | X/Y/Z={' x '.join(capacidade['dimensoes_maximas_mm'])} mm | tolerancia minima={capacidade['tolerancia_minima_mm']} mm")
        linhas.append("MATERIAIS_ACEITOS=" + (", ".join(f"{material['nome']} (ID {material['id']})" for material in relatorio["materiais"]) or "Nenhum material vinculado"))
        linhas.append(f"SOLICITACOES_NO_BANCO={relatorio['total_solicitacoes_no_banco']}")
        linhas.append(f"OPORTUNIDADES_NO_PORTAL_D24={relatorio['total_oportunidades_portal_d24']}")
        linhas.append("EIXOS=Comparados na ordem X/Y/Z cadastrada; não há rotação automática.")
        if len(relatorio["solicitacoes"]) < relatorio["total_solicitacoes_no_banco"]:
            linhas.append(f"AMOSTRA=As {len(relatorio['solicitacoes'])} solicitações mais recentes. Use --limite para ampliar.")
        for pedido in relatorio["solicitacoes"]:
            linhas.extend(["", f"SOLICITACAO=#{pedido['solicitacao_id']} | status={pedido['status']} | processo={pedido['processo_nome']} | material={pedido['material_nome']}", f"REQUISITOS=X/Y/Z={' x '.join(pedido['dimensoes_mm'])} mm | tolerancia={pedido['tolerancia_requerida_mm']} mm | quantidade={pedido['quantidade']}", f"DISPONIVEL_PARA_COTAR={pedido['disponivel_para_cotar']}"])
            for motivo in pedido["motivos"]:
                linhas.append("MOTIVO=" + motivo)
        if not relatorio["solicitacoes"]:
            linhas.append("MOTIVO=Não há solicitações no banco configurado. Crie uma solicitação de teste no Portal do Cliente.")
        if relatorio["total_oportunidades_portal_d24"]:
            linhas.append("PROXIMO=Se a tela continuar vazia, compare o ID da empresa do acesso com EMPRESA_ID e confirme que o backend usa este mesmo banco.")
        else:
            linhas.append("PROXIMO=Confira os motivos antes de cadastrar ou alterar capacidades. Cadastre valores que representem a capacidade real do fornecedor.")
    except Exception as erro:
        relatorio["erro"] = str(erro)
        linhas.append("ERRO=" + str(erro))
    for linha in linhas[3:]:
        print(linha, flush=True)
    linhas.append("RESULTADO=" + relatorio["resultado"])
    try:
        salvar_relatorios(raiz, relatorio, linhas)
    except Exception as erro:
        print("ERRO_RELATORIO=" + str(erro), flush=True)
        print("RESULTADO=ERRO", flush=True)
        return 1
    print("RESULTADO=" + relatorio["resultado"], flush=True)
    return 0 if relatorio["resultado"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
