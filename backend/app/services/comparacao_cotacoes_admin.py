from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.avaliacao_perfil import AvaliacaoAdministrativa
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.schemas.comparacao_cotacoes_admin import (
    ComparacaoCotacoesAdmin, CotacaoComparacaoAdmin, EscopoComparacao,
    NotasFornecedorComparacao, OrdenacaoComparacao,
)
from backend.app.services.comercial_admin import ServicoComercialAdmin, agora_utc, data_utc, sem_fuso, situacao


class ServicoComparacaoCotacoesAdmin:
    def __init__(self, banco: Session, usuario: UsuarioAcesso):
        if usuario.perfil != "admin" or usuario.usuario_id <= 0 or usuario.deve_alterar_senha:
            raise HTTPException(403, detail="comparacao_exclusiva_da_administracao")
        self.banco = banco
        self.usuario = usuario

    def contexto(self):
        return f"{self.usuario.usuario_id}:{self.usuario.perfil}:{self.usuario.empresa_id or 0}"

    @staticmethod
    def _agregado(modelo):
        # Cada origem é somada antes de juntar as duas, para não multiplicar notas.
        return select(modelo.empresa_fornecedora_id.label("empresa_id"),
            func.count().label("quantidade"), func.sum(modelo.nota).label("soma")
        ).group_by(modelo.empresa_fornecedora_id).subquery()

    @staticmethod
    def _notas(quantidade, soma):
        media = str((Decimal(soma) / Decimal(quantidade)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)) if quantidade else None
        return NotasFornecedorComparacao(quantidade=quantidade or 0, media=media)

    def consultar(self, solicitacao_id: int, ordenacao: OrdenacaoComparacao,
                  escopo: EscopoComparacao, deslocamento: int, limite: int):
        if solicitacao_id <= 0 or deslocamento < 0 or not 1 <= limite <= 100:
            raise HTTPException(422, detail="filtros_comparacao_invalidos")
        if ordenacao not in ("valor", "prazo", "nota_cliente", "nota_admin") or escopo not in ("disponiveis", "todas"):
            raise HTTPException(422, detail="filtros_comparacao_invalidos")
        comercial = ServicoComercialAdmin(self.banco)
        comercial._leitura_consistente()
        solicitacao, cotacoes, contrato, versao = comercial._estado(solicitacao_id)
        cliente, admin = self._agregado(AvaliacaoOficina), self._agregado(AvaliacaoAdministrativa)
        participantes = select(CotacaoFornecedor.empresa_fornecedora_id).where(CotacaoFornecedor.solicitacao_id == solicitacao_id)
        consulta = select(Empresa.id, Empresa.razao_social, cliente.c.quantidade, cliente.c.soma,
            admin.c.quantidade, admin.c.soma).outerjoin(cliente, cliente.c.empresa_id == Empresa.id)
        consulta = consulta.outerjoin(admin, admin.c.empresa_id == Empresa.id).where(Empresa.id.in_(participantes))
        fornecedores = {linha.id: linha for linha in self.banco.execute(consulta)}
        agora = agora_utc()
        tem_aceita = any(q.status == "aceita" for q in cotacoes)
        todos = []
        exatas = {}
        for q in cotacoes:
            fornecedor = fornecedores[q.empresa_fornecedora_id]
            nc, sc, na, sa = fornecedor[2:]
            status = situacao(q, agora)
            item = CotacaoComparacaoAdmin(cotacao_id=q.id,
                empresa_fornecedora_id=q.empresa_fornecedora_id, fornecedor=fornecedor.razao_social,
                valor_total=q.valor_total, prazo_dias=q.prazo_dias,
                vence_em=data_utc(sem_fuso(q.criada_em) + timedelta(days=q.validade_dias)),
                status=status, pode_decidir=solicitacao.status == "aberta" and status == "enviada" and contrato is None and not tem_aceita,
                notas_cliente=self._notas(nc, sc), notas_admin=self._notas(na, sa))
            todos.append(item)
            exatas[q.id] = {"nota_cliente": (Fraction(sc, nc) if nc else None, nc or 0),
                            "nota_admin": (Fraction(sa, na) if na else None, na or 0)}
        disponiveis = [q for q in todos if q.pode_decidir]
        itens = list(disponiveis) if escopo == "disponiveis" else todos

        def chave(item):
            valor = (item.valor_total, item.prazo_dias, item.cotacao_id)
            if ordenacao == "valor": return valor
            if ordenacao == "prazo": return (item.prazo_dias, item.valor_total, item.cotacao_id)
            media, quantidade = exatas[item.cotacao_id][ordenacao]
            return (media is None, -media if media is not None else 0, -quantidade, *valor)

        itens.sort(key=chave)
        return ComparacaoCotacoesAdmin(contexto=self.contexto(), solicitacao_id=solicitacao_id,
            versao=versao, consultado_em=data_utc(agora), ordenacao=ordenacao, escopo=escopo,
            total=len(itens), cotacoes_total=len(todos), cotacoes_disponiveis=len(disponiveis),
            menor_valor_disponivel=min((q.valor_total for q in disponiveis), default=None),
            menor_prazo_disponivel=min((q.prazo_dias for q in disponiveis), default=None),
            deslocamento=deslocamento, limite=limite, itens=itens[deslocamento:deslocamento + limite])
