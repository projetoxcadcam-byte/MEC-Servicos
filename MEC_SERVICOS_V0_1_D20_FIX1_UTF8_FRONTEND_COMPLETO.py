from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


REVISION = "MEC-SERVICOS-V0.1-D20-FIX1-UTF8-FRONTEND-COMPLETO-2026-10-01"


def localizar_raiz() -> Path:
    candidatos = [Path.cwd(), Path(__file__).resolve().parent]

    for base in candidatos:
        for p in [base, *base.parents]:
            if (p / "frontend" / "package.json").is_file() and (p / "backend").is_dir():
                return p

    raise RuntimeError(
        "Não encontrei a raiz do MEC-Servicos. "
        "Execute este script a partir de C:\\Users\\Omega\\Desktop\\MEC-Servicos."
    )


def ler_utf8(path: Path) -> str:
    data = path.read_bytes()

    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass

    # Fallback somente para arquivos antigos em Windows.
    return data.decode("cp1252")


def gravar_utf8(path: Path, text: str) -> None:
    # UTF-8 sem BOM, compatível com Vite/TypeScript.
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def score_mojibake(text: str) -> int:
    markers = (
        "Ã", "Â", "â", "ð", "�",
        "Ã§", "Ã£", "Ã©", "Ãª", "Ã¡", "Ã³", "Ãµ",
        "Ãº", "Ã­", "Ã´", "Ã‰", "Ã‡", "Ãƒ",
    )
    return sum(text.count(marker) for marker in markers)


def reparar_texto(text: str) -> str:
    atual = text

    # Corrige cadeias UTF-8 interpretadas como Latin-1/Windows-1252.
    # Repetimos no máximo 3 vezes para casos de dupla/tripla conversão.
    for _ in range(3):
        melhor = atual
        melhor_score = score_mojibake(atual)

        for encoding in ("latin1", "cp1252"):
            try:
                candidato = atual.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

            score = score_mojibake(candidato)

            # Só aceita a conversão quando ela realmente reduz os sinais
            # de mojibake e não introduz o caractere de substituição.
            if "�" not in candidato and score < melhor_score:
                melhor = candidato
                melhor_score = score

        if melhor == atual:
            break

        atual = melhor

    return atual


def backup(path: Path, backup_root: Path) -> Path:
    destino = backup_root / path.relative_to(backup_root.parents[1])
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(path.read_bytes())
    return destino


def encontrar_npm() -> str:
    candidatos = [
        Path(r"C:\Program Files\nodejs\npm.cmd"),
        Path(r"C:\Program Files (x86)\nodejs\npm.cmd"),
    ]

    for candidato in candidatos:
        if candidato.is_file():
            return str(candidato)

    # Também tenta PATH.
    try:
        resultado = subprocess.run(
            ["where.exe", "npm.cmd"],
            capture_output=True,
            text=True,
            check=False,
        )
        for linha in resultado.stdout.splitlines():
            linha = linha.strip()
            if linha:
                return linha
    except OSError:
        pass

    raise RuntimeError("npm.cmd não foi encontrado.")


def main() -> int:
    root = localizar_raiz()
    frontend = root / "frontend"
    src = frontend / "src"

    print("MEC Serviços — D20 FIX1 UTF-8 Frontend Completo")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")
    print(f"FRONTEND= {frontend}")

    if not src.is_dir():
        raise RuntimeError(f"Pasta não encontrada: {src}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / "_mec_backups" / f"D20_FIX1_UTF8_FRONTEND_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    extensoes = {".ts", ".tsx", ".css", ".html", ".json"}
    arquivos = [
        p for p in src.rglob("*")
        if p.is_file() and p.suffix.lower() in extensoes
    ]

    # index.html fica fora de src e também precisa permanecer explicitamente UTF-8.
    index_html = frontend / "index.html"
    if index_html.is_file():
        arquivos.append(index_html)

    alterados: list[Path] = []
    backed_up: list[Path] = []

    for path in arquivos:
        original = ler_utf8(path)
        corrigido = reparar_texto(original)

        # Normaliza apenas a codificação dos arquivos que realmente possuem
        # mojibake. Não reescreve arquivos já corretos.
        if corrigido != original:
            destino_backup = backup(path, backup_root)
            backed_up.append(destino_backup)
            gravar_utf8(path, corrigido)
            alterados.append(path)

    # Garante charset explícito no index.html.
    if index_html.is_file():
        original = ler_utf8(index_html)
        corrigido = original

        if "<meta charset=" not in corrigido.lower():
            corrigido = corrigido.replace(
                "<head>",
                '<head>\n    <meta charset="UTF-8" />',
                1,
            )

        if corrigido != original:
            if index_html not in alterados:
                destino_backup = backup(index_html, backup_root)
                backed_up.append(destino_backup)
            gravar_utf8(index_html, corrigido)
            if index_html not in alterados:
                alterados.append(index_html)

    # Relatório da correção.
    relatorio = root / f"MEC_SERVICOS_V0_1_D20_FIX1_UTF8_RELATORIO_{timestamp}.txt"
    linhas = [
        "MEC Serviços — D20 FIX1 UTF-8 Frontend Completo",
        f"REVISION={REVISION}",
        f"ROOT={root}",
        f"FRONTEND={frontend}",
        f"BACKUP_DIR={backup_root}",
        f"SCANNED_FILES={len(arquivos)}",
        f"CHANGED_FILES={len(alterados)}",
        f"BACKED_UP_FILES={len(backed_up)}",
        "",
        "ARQUIVOS ALTERADOS:",
        *[str(p.relative_to(root)) for p in alterados],
        "",
        "RESULTADO=OK",
    ]
    relatorio.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print(f"SCANNED_FILES= {len(arquivos)}")
    print(f"CHANGED_FILES= {len(alterados)}")
    print(f"BACKUP_DIR= {backup_root}")
    print(f"REPORT= {relatorio}")

    if alterados:
        print("\nArquivos corrigidos:")
        for path in alterados:
            print(f"  - {path.relative_to(root)}")
    else:
        print("\nNenhum arquivo apresentou mojibake detectável.")
        print("A página pode estar sendo servida por um processo Vite antigo/cache.")

    # Build completo.
    npm = encontrar_npm()
    print(f"\nNPM= {npm}")
    print("Executando npm run build...")

    result = subprocess.run(
        [npm, "run", "build"],
        cwd=str(frontend),
        check=False,
    )

    if result.returncode != 0:
        print(f"\nBUILD= FALHOU ({result.returncode})")
        return result.returncode

    print("\nBUILD= OK")
    print("\nPróximos comandos:")
    print("cd .\\frontend")
    print("npm run dev")
    print("Depois abra/atualize: http://localhost:5173/")
    print("\nIMPORTANTE: se o Vite já estiver rodando em outro PowerShell,")
    print("encerre com Ctrl+C e execute novamente 'npm run dev'.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERRO: {exc}")
        raise SystemExit(1)
