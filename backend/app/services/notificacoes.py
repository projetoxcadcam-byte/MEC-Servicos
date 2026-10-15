from __future__ import annotations

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import and_, func, insert, literal, select
from sqlalchemy.orm import Session

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.notificacao import LeituraNotificacao, NotificacaoPerfil
from backend.app.schemas.notificacao import NotificacaoLeitura, PaginaNotificacoes, ResumoNotificacoes


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ServicoNotificacoes:
    def __init__(self, banco: Session, usuario: UsuarioAcesso):
        self.banco = banco
        self.usuario = usuario
        self.empresa = usuario.empresa_id if usuario.perfil != "admin" else 0
        if usuario.usuario_id <= 0 or usuario.perfil not in {"admin", "cliente", "fornecedor"} or self.empresa is None:
            raise HTTPException(403, detail="notificacoes_exigem_acesso_real")

    def _destinatario(self):
        return and_(NotificacaoPerfil.perfil_destino == self.usuario.perfil,
                    NotificacaoPerfil.empresa_destino == self.empresa)

    def _leitura(self):
        return and_(LeituraNotificacao.notificacao_id == NotificacaoPerfil.id,
                    LeituraNotificacao.usuario_id == self.usuario.usuario_id,
                    LeituraNotificacao.perfil == self.usuario.perfil,
                    LeituraNotificacao.empresa_id == self.empresa)

    def resumo(self) -> ResumoNotificacoes:
        lida = select(LeituraNotificacao.notificacao_id).where(self._leitura()).correlate(NotificacaoPerfil).exists()
        qtd, ultimo = self.banco.execute(select(
            func.count().filter(~lida), func.coalesce(func.max(NotificacaoPerfil.id), 0)
        ).select_from(NotificacaoPerfil).where(self._destinatario())).one()
        return ResumoNotificacoes(usuario_id=self.usuario.usuario_id, perfil=self.usuario.perfil,
                                  empresa_id=self.usuario.empresa_id, nao_lidas=qtd, ultimo_id=ultimo)

    @staticmethod
    def _publica(item, lida_em) -> NotificacaoLeitura:
        return NotificacaoLeitura(**{nome: getattr(item, nome) for nome in (
            "id", "assunto", "mensagem", "destino", "perfil_origem", "solicitacao_id", "contratacao_id",
            "ordem_servico_id", "criada_em")}, lida_em=lida_em)

    def listar(self, antes_id: int | None, limite: int, somente_nao_lidas: bool) -> PaginaNotificacoes:
        resumo = self.resumo()
        consulta = select(NotificacaoPerfil, LeituraNotificacao.lida_em).outerjoin(LeituraNotificacao, self._leitura()).where(self._destinatario())
        if antes_id is not None:
            consulta = consulta.where(NotificacaoPerfil.id < antes_id)
        if somente_nao_lidas:
            consulta = consulta.where(LeituraNotificacao.notificacao_id.is_(None))
        linhas = self.banco.execute(consulta.order_by(NotificacaoPerfil.id.desc()).limit(limite + 1)).all()
        itens = linhas[:limite]
        return PaginaNotificacoes(**resumo.model_dump(), itens=[self._publica(*linha) for linha in itens],
                                  proximo_antes_id=itens[-1][0].id if len(linhas) > limite else None)

    def _gravar_leituras(self, consulta) -> None:
        tabela = LeituraNotificacao.__table__
        colunas = ["notificacao_id", "usuario_id", "perfil", "empresa_id", "lida_em"]
        dialecto = self.banco.get_bind().dialect.name
        if dialecto == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as inserir
        elif dialecto == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as inserir
        else:
            inserir = insert
        comando = inserir(tabela).from_select(colunas, consulta)
        if dialecto in {"sqlite", "postgresql"}:
            comando = comando.on_conflict_do_nothing(index_elements=list(tabela.primary_key.columns))
        self.banco.execute(comando)
        self.banco.commit()

    def _pendentes_ate(self, ate_id: int):
        lida = select(LeituraNotificacao.notificacao_id).where(self._leitura()).correlate(NotificacaoPerfil).exists()
        return select(NotificacaoPerfil.id, literal(self.usuario.usuario_id), literal(self.usuario.perfil),
                      literal(self.empresa), literal(agora())).where(self._destinatario(), NotificacaoPerfil.id <= ate_id, ~lida)

    def ler(self, notificacao_id: int) -> NotificacaoLeitura:
        item = self.banco.scalar(select(NotificacaoPerfil).where(self._destinatario(), NotificacaoPerfil.id == notificacao_id))
        if item is None:
            raise HTTPException(404, detail="notificacao_nao_encontrada")
        self._gravar_leituras(self._pendentes_ate(notificacao_id).where(NotificacaoPerfil.id == notificacao_id))
        lida_em = self.banco.scalar(select(LeituraNotificacao.lida_em).where(self._leitura(), NotificacaoPerfil.id == notificacao_id))
        return self._publica(item, lida_em)

    def ler_ate(self, ate_id: int) -> ResumoNotificacoes:
        # O limite veio da tela já carregada. Avisos que chegarem depois continuam não lidos.
        self._gravar_leituras(self._pendentes_ate(ate_id))
        return self.resumo()
