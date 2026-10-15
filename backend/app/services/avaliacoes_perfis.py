"""Notas por origem, vinculadas à sessão e à entrega; comentários privados."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.avaliacao_perfil import AutoriaAvaliacaoCliente, AvaliacaoAdministrativa
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.empresa import Empresa
from backend.app.models.intermediacao import CicloIntermediacao
from backend.app.models.ordem_servico import OrdemServico
from backend.app.services.documentacao_cotacao import travar_documentacao
from backend.app.services.notificacoes import agora


def resumo(valor) -> str:
    return hashlib.sha256(json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def instante(valor) -> str:
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=timezone.utc).isoformat() if valor.tzinfo is None else valor.astimezone(timezone.utc).isoformat()
    return valor


def normalizar_busca(valor: str) -> str:
    texto = unicodedata.normalize("NFD", " ".join(valor.split()).casefold())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def motivo_elegibilidade(contrato, ordem, ciclo) -> str | None:
    if contrato.status not in {"ativa", "encerrada"}:
        return "contratacao_cancelada"
    if ordem is None:
        return "ordem_servico_nao_encontrada"
    if (ordem.empresa_cliente_id != contrato.empresa_cliente_id or
            ordem.empresa_fornecedora_id != contrato.empresa_fornecedora_id or
            ordem.solicitacao_id != contrato.solicitacao_id or ordem.cotacao_id != contrato.cotacao_id):
        return "vinculos_da_ordem_inconsistentes"
    if ordem.status != "concluida":
        return "aguardando_conclusao_da_ordem"
    if ciclo is not None and ciclo.status != "entregue_cliente":
        return "aguardando_entrega_ao_cliente"
    if ciclo is None and contrato.status != "encerrada":
        return "aguardando_entrega_ao_cliente"
    return None


class ServicoAvaliacoesPerfis:
    def __init__(self, banco: Session, usuario: UsuarioAcesso):
        self.banco, self.usuario = banco, usuario
        if usuario.usuario_id <= 0 or usuario.perfil not in {"admin", "cliente", "fornecedor"}:
            raise HTTPException(403, detail="avaliacoes_exigem_acesso_real")

    def contexto(self) -> str:
        u = self.usuario
        return f"{u.usuario_id}:{u.perfil}:{u.empresa_id or 0}"

    def _leitura(self):
        # SQLite não abre uma transação para SELECT no modo legado do driver.
        # Uma transação explícita mantém contagens, página e médias coerentes.
        conexao = self.banco.connection()
        if conexao.dialect.name == "sqlite" and not conexao.connection.driver_connection.in_transaction:
            self.banco.execute(text("BEGIN"))

    def _escopo(self):
        if self.usuario.perfil == "cliente":
            return ContratacaoServico.empresa_cliente_id == self.usuario.empresa_id
        if self.usuario.perfil == "fornecedor":
            return ContratacaoServico.empresa_fornecedora_id == self.usuario.empresa_id
        return True

    def _consulta(self):
        return (select(ContratacaoServico, OrdemServico, CicloIntermediacao,
                       AvaliacaoOficina, AvaliacaoAdministrativa, AutoriaAvaliacaoCliente)
            .outerjoin(OrdemServico, OrdemServico.contratacao_id == ContratacaoServico.id)
            .outerjoin(CicloIntermediacao, CicloIntermediacao.ordem_servico_id == OrdemServico.id)
            .outerjoin(AvaliacaoOficina, AvaliacaoOficina.contratacao_id == ContratacaoServico.id)
            .outerjoin(AvaliacaoAdministrativa, AvaliacaoAdministrativa.contratacao_id == ContratacaoServico.id)
            .outerjoin(AutoriaAvaliacaoCliente, AutoriaAvaliacaoCliente.avaliacao_id == AvaliacaoOficina.id)
            .where(self._escopo()))

    def _linha(self, cid):
        linha = self.banco.execute(self._consulta().where(ContratacaoServico.id == cid)).first()
        if linha is None:
            raise HTTPException(404, detail="contratacao_nao_encontrada")
        return linha

    def _nota(self, nota, autor, origem):
        if nota is None:
            return None
        r = {"id": nota.id, "origem": origem, "nota": nota.nota, "criada_em": instante(nota.criada_em),
             "historica": origem == "cliente" and autor is None}
        # Nem outro usuário da mesma empresa recebe o comentário do autor.
        if self.usuario.perfil == "admin" or (origem == "cliente" and self.usuario.perfil == "cliente"
                and autor is not None and autor.usuario_id == self.usuario.usuario_id):
            r["comentario"] = nota.comentario
        if self.usuario.perfil == "admin":
            r["autor"] = None if autor is None else {"usuario_id": autor.usuario_id, "nome": autor.nome_autor}
        return r

    def _publicar(self, linha):
        c, o, ciclo, cliente, admin, autoria = linha
        propria = admin if self.usuario.perfil == "admin" else cliente if self.usuario.perfil == "cliente" else None
        motivo = motivo_elegibilidade(c, o, ciclo)
        if self.usuario.perfil == "fornecedor":
            motivo = "fornecedor_consulta_avaliacoes"
        elif propria is not None:
            motivo = "avaliacao_ja_registrada"
        estado = [c.id, c.status, c.empresa_cliente_id, c.empresa_fornecedora_id, c.solicitacao_id, c.cotacao_id,
                  None if o is None else [o.id, o.status, o.empresa_cliente_id, o.empresa_fornecedora_id, o.solicitacao_id, o.cotacao_id],
                  None if ciclo is None else [ciclo.id, ciclo.status, ciclo.versao],
                  self.usuario.perfil, propria.id if propria else None]
        return {"contratacao_id": c.id, "ordem_servico_id": o.id if o else None,
                "cliente_codigo": f"C-{c.empresa_cliente_id}", "fornecedor_codigo": f"F-{c.empresa_fornecedora_id}",
                "status_ordem": o.status if o else None, "status_entrega": ciclo.status if ciclo else None,
                "status_contratacao": c.status, "pode_avaliar": motivo is None, "motivo_disponibilidade": motivo,
                "versao": resumo(estado), "cliente": self._nota(cliente, autoria, "cliente"),
                "admin": self._nota(admin, admin, "admin")}

    def obter(self, cid):
        self._leitura()
        return {"contexto": self.contexto(), "item": self._publicar(self._linha(cid))}

    def listar(self, cid, ordem_id, situacao, inicio, limite):
        self._leitura()
        q = self._consulta()
        if cid is not None:
            q = q.where(ContratacaoServico.id == cid)
        if ordem_id is not None:
            q = q.where(OrdemServico.id == ordem_id)
        propria = AvaliacaoAdministrativa if self.usuario.perfil == "admin" else AvaliacaoOficina
        if situacao == "avaliadas":
            condicao = propria.id.is_not(None)
            if self.usuario.perfil == "fornecedor":
                condicao = AvaliacaoOficina.id.is_not(None) | AvaliacaoAdministrativa.id.is_not(None)
            q = q.where(condicao)
        if situacao == "disponiveis":
            if self.usuario.perfil == "fornecedor":
                q = q.where(False)
            else:
                q = q.where(propria.id.is_(None), ContratacaoServico.status.in_(("ativa", "encerrada")),
                    OrdemServico.status == "concluida", OrdemServico.empresa_cliente_id == ContratacaoServico.empresa_cliente_id,
                    OrdemServico.empresa_fornecedora_id == ContratacaoServico.empresa_fornecedora_id,
                    OrdemServico.solicitacao_id == ContratacaoServico.solicitacao_id, OrdemServico.cotacao_id == ContratacaoServico.cotacao_id,
                    ((CicloIntermediacao.id.is_(None) & (ContratacaoServico.status == "encerrada")) |
                     (CicloIntermediacao.status == "entregue_cliente")))
        total = self.banco.scalar(select(func.count()).select_from(q.subquery()))
        linhas = self.banco.execute(q.order_by(ContratacaoServico.id.desc()).offset(inicio).limit(limite)).all()
        return {"contexto": self.contexto(), "total": total, "inicio": inicio, "limite": limite,
                "itens": [self._publicar(linha) for linha in linhas]}

    def registrar(self, cid, dados):
        if self.usuario.perfil not in {"admin", "cliente"}:
            raise HTTPException(403, detail="fornecedor_consulta_avaliacoes")
        try:
            travar_documentacao(self.banco)
            # A trava da contratação serializa as gravações também em PostgreSQL.
            self.banco.scalar(select(ContratacaoServico.id).where(ContratacaoServico.id == cid, self._escopo()).with_for_update())
            linha = self._linha(cid)
            chave = str(dados.chave_operacao)
            hash_corpo = resumo({"contratacao": cid, "nota": dados.nota, "comentario": dados.comentario, "versao": dados.versao})
            modelo = AvaliacaoAdministrativa if self.usuario.perfil == "admin" else AutoriaAvaliacaoCliente
            anterior = self.banco.scalar(select(modelo).where(modelo.chave_operacao == chave))
            if anterior is not None:
                if anterior.usuario_id != self.usuario.usuario_id or anterior.resumo_operacao != hash_corpo:
                    raise HTTPException(409, detail="chave_operacao_ja_utilizada")
                # A mesma operação confirmada pode ser consultada após perda da resposta.
                return {"contexto": self.contexto(), "item": self._publicar(linha), "repetida": True}
            previa = self._publicar(linha)
            if not previa["pode_avaliar"]:
                raise HTTPException(409, detail=previa["motivo_disponibilidade"])
            if dados.versao != previa["versao"]:
                raise HTTPException(409, detail="avaliacao_contexto_alterado")
            c, o, *_ = linha
            campos = dict(contratacao_id=cid, ordem_servico_id=o.id, empresa_cliente_id=c.empresa_cliente_id,
                          empresa_fornecedora_id=c.empresa_fornecedora_id, nota=dados.nota, comentario=dados.comentario)
            auditoria = dict(usuario_id=self.usuario.usuario_id, nome_autor=self.usuario.nome,
                             chave_operacao=chave, resumo_operacao=hash_corpo)
            if self.usuario.perfil == "cliente":
                avaliacao = AvaliacaoOficina(**campos, criada_em=datetime.now(timezone.utc))
                self.banco.add(avaliacao); self.banco.flush()
                self.banco.add(AutoriaAvaliacaoCliente(avaliacao_id=avaliacao.id, **auditoria))
            else:
                self.banco.add(AvaliacaoAdministrativa(**campos, criada_em=agora(), **auditoria))
            self.banco.flush()
            publicado = self._publicar(self._linha(cid))
            self.banco.commit()
            return {"contexto": self.contexto(), "item": publicado, "repetida": False}
        except IntegrityError:
            self.banco.rollback()
            raise HTTPException(409, detail="avaliacao_ja_registrada") from None
        except Exception:
            self.banco.rollback()
            raise

    def ranking(self, origem, inicio, limite, busca=""):
        if self.usuario.perfil != "admin":
            raise HTTPException(403, detail="ranking_exclusivo_da_administracao")
        self._leitura()
        modelo = AvaliacaoOficina if origem == "cliente" else AvaliacaoAdministrativa
        agregado = select(modelo.empresa_fornecedora_id.label("empresa_id"), func.count().label("quantidade"),
            func.sum(modelo.nota).label("soma")).group_by(modelo.empresa_fornecedora_id).subquery()
        linhas = self.banco.execute(select(Empresa.id, Empresa.razao_social, agregado.c.quantidade, agregado.c.soma)
            .outerjoin(agregado, agregado.c.empresa_id == Empresa.id)
            .where(Empresa.tipo_empresa.in_(("fornecedor", "ambos")))).all()
        linhas.sort(key=lambda r: (r.soma is None, -Fraction(r.soma, r.quantidade) if r.quantidade else 0,
                                  -(r.quantidade or 0), r.razao_social.casefold(), r.id))
        itens = []
        for posicao, r in enumerate(linhas, 1):
            media = str((Decimal(r.soma) / Decimal(r.quantidade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if r.quantidade else None
            item = {"fornecedor_codigo": f"F-{r.id}", "quantidade": r.quantidade or 0, "media": media,
                    "posicao": posicao if r.quantidade else None}
            item["empresa_id"] = r.id
            item["razao_social"] = r.razao_social
            itens.append(item)
        filtro = normalizar_busca(busca)
        codigo = re.fullmatch(r"(?:f-)?([1-9]\d{0,12})", filtro)
        if codigo:
            itens = [i for i in itens if i["empresa_id"] == int(codigo.group(1))]
        elif filtro:
            itens = [i for i in itens if filtro in normalizar_busca(i["razao_social"])]
        return {"contexto": self.contexto(), "origem": origem, "total": len(itens),
                "total_fornecedores": len(linhas), "inicio": inicio, "limite": limite,
                "busca": " ".join(busca.split()), "itens": itens[inicio:inicio + limite]}

    def historico_fornecedor(self, empresa_id, inicio, limite):
        if self.usuario.perfil != "admin":
            raise HTTPException(403, detail="historico_fornecedor_exclusivo_administracao")
        if empresa_id <= 0 or inicio < 0 or inicio > 1_000_000 or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtros_historico_fornecedor_invalidos")
        self._leitura()
        empresa = self.banco.scalar(select(Empresa).where(Empresa.id == empresa_id,
            Empresa.tipo_empresa.in_(("fornecedor", "ambos"))))
        if empresa is None:
            raise HTTPException(404, detail="fornecedor_nao_encontrado")

        def notas(modelo):
            quantidade, soma = self.banco.execute(select(func.count(), func.sum(modelo.nota))
                .where(modelo.empresa_fornecedora_id == empresa_id)).one()
            media = str((Decimal(soma) / Decimal(quantidade)).quantize(Decimal("0.01"),
                rounding=ROUND_HALF_UP)) if quantidade else None
            return {"quantidade": quantidade, "media": media}

        fornecedor = {"empresa_id": empresa.id, "fornecedor_codigo": f"F-{empresa.id}",
            "razao_social": empresa.razao_social, "notas_cliente": notas(AvaliacaoOficina),
            "notas_admin": notas(AvaliacaoAdministrativa)}
        consulta = self._consulta().where(ContratacaoServico.empresa_fornecedora_id == empresa_id,
            AvaliacaoOficina.id.is_not(None) | AvaliacaoAdministrativa.id.is_not(None))
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery()))
        linhas = self.banco.execute(consulta.order_by(ContratacaoServico.id.desc()).offset(inicio).limit(limite)).all()
        return {"contexto": self.contexto(), "fornecedor": fornecedor, "total": total,
            "inicio": inicio, "limite": limite, "itens": [self._publicar(linha) for linha in linhas]}
