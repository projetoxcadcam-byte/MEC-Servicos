from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

ITERACOES_SENHA = 600_000
DURACAO_SESSAO = 8 * 60 * 60
JANELA_LOGIN = 15 * 60
COOKIE_SESSAO = "mec_sessao"


def validar_senha(senha: str) -> None:
    if not isinstance(senha, str) or not 12 <= len(senha) <= 128:
        raise HTTPException(422, detail="senha_deve_ter_12_a_128_caracteres")
    try:
        senha.encode("utf-8")
    except UnicodeError:
        raise HTTPException(422, detail="dados_de_acesso_invalidos") from None


def hash_senha(senha: str) -> str:
    validar_senha(senha)
    sal = secrets.token_bytes(16)
    valor = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES_SENHA)
    return "pbkdf2_sha256$" + str(ITERACOES_SENHA) + "$" + base64.urlsafe_b64encode(sal).decode() + "$" + base64.urlsafe_b64encode(valor).decode()


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        algoritmo, repeticoes, sal, esperado = armazenado.split("$")
        iteracoes = int(repeticoes)
        if algoritmo != "pbkdf2_sha256" or not 600_000 <= iteracoes <= 2_000_000 or len(senha) > 128:
            return False
        valor = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), base64.urlsafe_b64decode(sal), iteracoes)
        return hmac.compare_digest(valor, base64.urlsafe_b64decode(esperado))
    except (ValueError, TypeError, UnicodeError):
        return False


def normalizar_email(email: str) -> str:
    email = email.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, detail="email_invalido")
    return email


@dataclass(frozen=True)
class UsuarioAcesso:
    usuario_id: int
    nome: str
    email: str
    perfil: str
    empresa_id: int | None
    deve_alterar_senha: bool
    csrf: str = ""

    def publico(self) -> dict:
        # As telas D23-D28 usam id como empresa; usuario_id identifica o operador.
        return {"id": self.empresa_id if self.empresa_id is not None else self.usuario_id,
                "usuario_id": self.usuario_id, "empresa_id": self.empresa_id,
                "nome": self.nome, "email": self.email, "role": self.perfil,
                "deve_alterar_senha": self.deve_alterar_senha}


class ArmazenamentoAcesso:
    def __init__(self, caminho: Path) -> None:
        bruto = Path(caminho)
        if bruto.is_symlink():
            raise RuntimeError("O banco de acesso não pode ser um vínculo simbólico.")
        self.caminho = bruto.resolve()

    @contextmanager
    def _conexao(self):
        if not self.caminho.is_file():
            raise HTTPException(503, detail="acesso_servidor_nao_configurado")
        banco = sqlite3.connect(self.caminho.as_uri() + "?mode=rw", uri=True, timeout=10)
        banco.row_factory = sqlite3.Row
        banco.execute("PRAGMA foreign_keys=ON")
        try:
            with banco:
                yield banco
        finally:
            banco.close()

    def inicializar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        if self.caminho.is_symlink():
            raise RuntimeError("O banco de acesso não pode ser um vínculo simbólico.")
        with closing(sqlite3.connect(self.caminho, timeout=10)) as banco:
            tabelas = {r[0] for r in banco.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tabelas and "usuarios_acesso" not in tabelas:
                raise RuntimeError("O destino já contém um banco diferente do banco de acesso MEC.")
            banco.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS usuarios_acesso(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                    perfil TEXT NOT NULL CHECK(perfil IN ('admin','cliente','fornecedor')),
                    empresa_id INTEGER, senha_hash TEXT NOT NULL,
                    ativo INTEGER NOT NULL DEFAULT 1, trocar_senha INTEGER NOT NULL DEFAULT 1,
                    criado_em REAL NOT NULL,
                    CHECK((perfil='admin' AND empresa_id IS NULL) OR (perfil!='admin' AND empresa_id>0))
                );
                CREATE TABLE IF NOT EXISTS sessoes_acesso(
                    token_hash TEXT PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios_acesso(id),
                    csrf TEXT NOT NULL, expira_em REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tentativas_acesso(
                    email_hash TEXT NOT NULL, endereco_hash TEXT NOT NULL, instante REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_tentativas_tempo ON tentativas_acesso(instante);
                CREATE TABLE IF NOT EXISTS auditoria_acesso(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER NOT NULL,
                    acao TEXT NOT NULL, recurso TEXT NOT NULL, instante REAL NOT NULL
                );
            """)

    @staticmethod
    def _usuario(linha, csrf: str = "") -> UsuarioAcesso:
        return UsuarioAcesso(linha["id"], linha["nome"], linha["email"], linha["perfil"],
                             linha["empresa_id"], bool(linha["trocar_senha"]), csrf)

    @staticmethod
    def _hash(valor: str) -> str:
        return hashlib.sha256(valor.encode("utf-8", errors="replace")).hexdigest()

    def criar_usuario(self, nome: str, email: str, perfil: str, empresa_id: int | None,
                      senha: str, deve_alterar_senha: bool = True) -> UsuarioAcesso:
        email = normalizar_email(email)
        if not nome.strip() or len(nome.strip()) > 120 or perfil not in {"admin", "cliente", "fornecedor"}:
            raise HTTPException(422, detail="dados_usuario_invalidos")
        if (perfil == "admin" and empresa_id is not None) or (perfil != "admin" and (type(empresa_id) is not int or empresa_id <= 0)):
            raise HTTPException(422, detail="vinculo_empresa_invalido")
        senha_hash = hash_senha(senha)
        with self._conexao() as banco:
            try:
                cursor = banco.execute("INSERT INTO usuarios_acesso(nome,email,perfil,empresa_id,senha_hash,trocar_senha,criado_em) VALUES(?,?,?,?,?,?,?)",
                    (nome.strip(), email, perfil, empresa_id, senha_hash, int(deve_alterar_senha), time.time()))
            except sqlite3.IntegrityError:
                raise HTTPException(409, detail="email_ja_cadastrado") from None
            linha = banco.execute("SELECT * FROM usuarios_acesso WHERE id=?", (cursor.lastrowid,)).fetchone()
            return self._usuario(linha)

    def listar_usuarios(self) -> list[dict]:
        with self._conexao() as banco:
            return [{**self._usuario(r).publico(), "ativo": bool(r["ativo"])} for r in banco.execute("SELECT * FROM usuarios_acesso ORDER BY id")]

    def entrar(self, email: str, senha: str, endereco: str, token_anterior: str | None = None):
        try:
            email = normalizar_email(email)
        except HTTPException:
            email = email.strip().casefold()[:254]
        agora = time.time(); email_hash = self._hash(email); endereco_hash = self._hash(endereco)
        with self._conexao() as banco:
            banco.execute("BEGIN IMMEDIATE")
            banco.execute("DELETE FROM tentativas_acesso WHERE instante<?", (agora - JANELA_LOGIN,))
            falhas_email = banco.execute("SELECT COUNT(*) FROM tentativas_acesso WHERE email_hash=?", (email_hash,)).fetchone()[0]
            falhas_endereco = banco.execute("SELECT COUNT(*) FROM tentativas_acesso WHERE endereco_hash=?", (endereco_hash,)).fetchone()[0]
            if falhas_email >= 5 or falhas_endereco >= 30:
                raise HTTPException(429, detail="muitas_tentativas_aguarde", headers={"Retry-After": str(JANELA_LOGIN)})
            linha = banco.execute("SELECT * FROM usuarios_acesso WHERE email=?", (email,)).fetchone()
            if linha:
                correta = verificar_senha(senha, linha["senha_hash"])
            else:
                # Mesmo custo do cálculo da senha para contas não encontradas.
                hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8", errors="replace")[:512], b"MEC-D30-SAL-NAO-CADASTRADO", ITERACOES_SENHA)
                correta = False
            if not correta or not linha["ativo"]:
                banco.execute("INSERT INTO tentativas_acesso VALUES(?,?,?)", (email_hash, endereco_hash, agora))
                banco.commit()
                raise HTTPException(401, detail="email_ou_senha_invalidos")
            banco.execute("DELETE FROM tentativas_acesso WHERE email_hash=?", (email_hash,))
            banco.execute("DELETE FROM sessoes_acesso WHERE expira_em<=?", (agora,))
            if token_anterior:
                banco.execute("DELETE FROM sessoes_acesso WHERE token_hash=?", (self._hash(token_anterior),))
            token = secrets.token_urlsafe(32); csrf = secrets.token_urlsafe(32)
            banco.execute("INSERT INTO sessoes_acesso VALUES(?,?,?,?)", (self._hash(token), linha["id"], csrf, agora + DURACAO_SESSAO))
            banco.execute("INSERT INTO auditoria_acesso(usuario_id,acao,recurso,instante) VALUES(?,?,?,?)", (linha["id"], "entrar", "sessao", agora))
            return self._usuario(linha, csrf), token

    def obter_sessao(self, token: str | None) -> UsuarioAcesso:
        if not token or len(token) > 200:
            raise HTTPException(401, detail="sessao_nao_autenticada")
        with self._conexao() as banco:
            linha = banco.execute("SELECT u.*,s.csrf FROM sessoes_acesso s JOIN usuarios_acesso u ON u.id=s.usuario_id WHERE s.token_hash=? AND s.expira_em>? AND u.ativo=1",
                                  (self._hash(token), time.time())).fetchone()
            if linha is None:
                raise HTTPException(401, detail="sessao_expirada_entre_novamente")
            return self._usuario(linha, linha["csrf"])

    def sair(self, token: str | None) -> None:
        if token:
            with self._conexao() as banco:
                banco.execute("DELETE FROM sessoes_acesso WHERE token_hash=?", (self._hash(token),))

    def alterar_senha(self, usuario_id: int, atual: str, nova: str) -> None:
        nova_hash = hash_senha(nova)
        with self._conexao() as banco:
            banco.execute("BEGIN IMMEDIATE")
            linha = banco.execute("SELECT * FROM usuarios_acesso WHERE id=? AND ativo=1", (usuario_id,)).fetchone()
            if linha is None or not verificar_senha(atual, linha["senha_hash"]):
                raise HTTPException(401, detail="senha_atual_invalida")
            if verificar_senha(nova, linha["senha_hash"]):
                raise HTTPException(422, detail="nova_senha_deve_ser_diferente")
            banco.execute("UPDATE usuarios_acesso SET senha_hash=?,trocar_senha=0 WHERE id=?", (nova_hash, usuario_id))
            banco.execute("DELETE FROM sessoes_acesso WHERE usuario_id=?", (usuario_id,))
            banco.execute("INSERT INTO auditoria_acesso(usuario_id,acao,recurso,instante) VALUES(?,?,?,?)", (usuario_id, "alterar_senha", "propria_conta", time.time()))

    def redefinir_senha(self, usuario_id: int, nova: str) -> None:
        nova_hash = hash_senha(nova)
        with self._conexao() as banco:
            cursor = banco.execute("UPDATE usuarios_acesso SET senha_hash=?,trocar_senha=1 WHERE id=?", (nova_hash, usuario_id))
            if cursor.rowcount != 1:
                raise HTTPException(404, detail="usuario_nao_encontrado")
            banco.execute("DELETE FROM sessoes_acesso WHERE usuario_id=?", (usuario_id,))

    def definir_ativo(self, usuario_id: int, ativo: bool) -> None:
        with self._conexao() as banco:
            banco.execute("BEGIN IMMEDIATE")
            alvo = banco.execute("SELECT * FROM usuarios_acesso WHERE id=?", (usuario_id,)).fetchone()
            if alvo is None:
                raise HTTPException(404, detail="usuario_nao_encontrado")
            if not ativo and alvo["perfil"] == "admin" and alvo["ativo"]:
                quantidade = banco.execute("SELECT COUNT(*) FROM usuarios_acesso WHERE perfil='admin' AND ativo=1").fetchone()[0]
                if quantidade <= 1:
                    raise HTTPException(409, detail="ultimo_administrador_nao_pode_ser_desativado")
            banco.execute("UPDATE usuarios_acesso SET ativo=? WHERE id=?", (int(ativo), usuario_id))
            if not ativo:
                banco.execute("DELETE FROM sessoes_acesso WHERE usuario_id=?", (usuario_id,))

    def registrar_acao(self, usuario_id: int, acao: str, recurso: str) -> None:
        with self._conexao() as banco:
            banco.execute("INSERT INTO auditoria_acesso(usuario_id,acao,recurso,instante) VALUES(?,?,?,?)", (usuario_id, acao[:100], recurso[:250], time.time()))
