"""Consulta de orçamentos publicados, sem expiração automática ou contratação."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from backend.app.models.formacao_preco import ConfiguracaoPreco, FormacaoPreco
from backend.app.services.precos_portais import visibilidade_cliente
from fastapi import HTTPException
from sqlalchemy import and_, case, func, select, text
from sqlalchemy.orm import Session
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico


def utc(valor):
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


class ServicoCotacoesCliente:
    def __init__(self, banco: Session, usuario: UsuarioAcesso):
        if usuario.perfil != 'cliente' or not usuario.empresa_id or usuario.usuario_id <= 0:
            raise HTTPException(403, detail='cotacoes_exigem_perfil_cliente')
        self.banco, self.usuario = banco, usuario
        self.configuracao=banco.get(ConfiguracaoPreco,1)

    def contexto(self):
        return f'{self.usuario.usuario_id}:cliente:{self.usuario.empresa_id}'

    def _leitura(self):
        conexao = self.banco.connection()
        if conexao.dialect.name == 'sqlite' and not conexao.connection.driver_connection.in_transaction:
            self.banco.execute(text('BEGIN'))
        return datetime.now(timezone.utc)

    def _status(self, agora):
        vencida = func.julianday(agora.replace(tzinfo=None)) >= func.julianday(CotacaoFornecedor.criada_em) + CotacaoFornecedor.validade_dias
        return case(((CotacaoFornecedor.status == 'enviada') & vencida, 'expirada'), else_=CotacaoFornecedor.status)

    def _escopo(self):
        return SolicitacaoServico.empresa_cliente_id == self.usuario.empresa_id

    def _consulta(self, status):
        return (select(CotacaoFornecedor, SolicitacaoServico,
            ProcessoFabricacao.nome, Material.nome, status, ContratacaoServico.id, OrdemServico.id, FormacaoPreco)
            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)
            .join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id)
            .join(Material, Material.id == SolicitacaoServico.material_id)
            .outerjoin(ContratacaoServico, and_(ContratacaoServico.cotacao_id == CotacaoFornecedor.id,
                ContratacaoServico.solicitacao_id == SolicitacaoServico.id,
                ContratacaoServico.empresa_cliente_id == SolicitacaoServico.empresa_cliente_id,
                ContratacaoServico.empresa_fornecedora_id == CotacaoFornecedor.empresa_fornecedora_id))
            .outerjoin(OrdemServico, and_(OrdemServico.contratacao_id == ContratacaoServico.id,
                OrdemServico.cotacao_id == CotacaoFornecedor.id, OrdemServico.solicitacao_id == SolicitacaoServico.id,
                OrdemServico.empresa_cliente_id == SolicitacaoServico.empresa_cliente_id,
                OrdemServico.empresa_fornecedora_id == CotacaoFornecedor.empresa_fornecedora_id))
            .outerjoin(FormacaoPreco, FormacaoPreco.cotacao_id==CotacaoFornecedor.id)
            .where(self._escopo(),visibilidade_cliente() if self.configuracao else True))

    @staticmethod
    def _item(linha):
        cotacao, pedido, processo, material, status, contrato, ordem, preco = linha
        criada = utc(cotacao.criada_em)
        return dict(id=cotacao.id, solicitacao_id=pedido.id, empresa_cliente_id=pedido.empresa_cliente_id,
            empresa_fornecedora_id=cotacao.empresa_fornecedora_id, status=status, valor_total=(Decimal(preco.preco_cliente_centavos)/100).quantize(Decimal("0.01")) if preco else cotacao.valor_total,
            analise_cliente=preco.estado if preco else None,pode_analisar=False,versao_preco=None,
            prazo_dias=cotacao.prazo_dias, validade_dias=cotacao.validade_dias, criada_em=criada,
            vencimento_em=criada+timedelta(days=cotacao.validade_dias), encerrada_em=utc(cotacao.encerrada_em) if cotacao.encerrada_em else None,
            solicitacao_status=pedido.status, processo_nome=processo, material_nome=material, quantidade=pedido.quantidade,
            contratacao_id=contrato, ordem_servico_id=ordem)

    def listar(self, solicitacao_id, cotacao_id, situacao, ordenacao, deslocamento, limite):
        agora = self._leitura(); status = self._status(agora)
        filtros = [self._escopo(),visibilidade_cliente() if self.configuracao else True]
        if solicitacao_id is not None:
            propria = self.banco.scalar(select(SolicitacaoServico.id).where(self._escopo(), SolicitacaoServico.id == solicitacao_id))
            if propria is None:
                raise HTTPException(404, detail='solicitacao_nao_encontrada')
            filtros.append(CotacaoFornecedor.solicitacao_id == solicitacao_id)
        if cotacao_id is not None:
            filtros.append(CotacaoFornecedor.id == cotacao_id)
        if situacao != 'todas':
            filtros.append(status == situacao)
        contagens = self.banco.execute(select(status, func.count()).select_from(CotacaoFornecedor)
            .join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id)
            .where(*filtros).group_by(status)).all()
        por_status = {s: n for s, n in contagens}; total = sum(por_status.values())
        valor=func.coalesce(select(FormacaoPreco.preco_cliente_centavos/100.0).where(FormacaoPreco.cotacao_id==CotacaoFornecedor.id).correlate(CotacaoFornecedor).scalar_subquery(),CotacaoFornecedor.valor_total)
        ordem = (valor, CotacaoFornecedor.id) if ordenacao == 'valor' else (
            (CotacaoFornecedor.prazo_dias, CotacaoFornecedor.id) if ordenacao == 'prazo' else (CotacaoFornecedor.id.desc(),))
        linhas = self.banco.execute(self._consulta(status).where(*filtros)
            .order_by(*ordem).offset(deslocamento).limit(limite)).all()
        return dict(contexto=self.contexto(), empresa_id=self.usuario.empresa_id, consultado_em=agora,
            total=total, por_status=por_status, deslocamento=deslocamento, limite=limite, itens=[self._item(l) for l in linhas])

    def obter(self, cotacao_id):
        agora = self._leitura()
        linha = self.banco.execute(self._consulta(self._status(agora)).where(CotacaoFornecedor.id == cotacao_id)).first()
        if linha is None:
            raise HTTPException(404, detail='cotacao_nao_encontrada')
        item=self._item(linha)
        if self.configuracao and linha[-1] and linha[-1].estado=='publicada':
            from backend.app.services.formacao_preco import ServicoFormacaoPreco, termos, vencida
            q,pedido,preco=linha[0],linha[1],linha[-1]
            _,_,_,contrato,versao=ServicoFormacaoPreco(self.banco,self.usuario)._estado(q.id)
            item['pode_analisar']=q.status in ('enviada','aceita') and (q.status=='aceita' or not vencida(q)) and pedido.status=='aberta' and contrato is None and preco.termos_sha256==termos(q,pedido,self.banco)
            item['versao_preco']=versao if item['pode_analisar'] else None
        return dict(contexto=self.contexto(), empresa_id=self.usuario.empresa_id, consultado_em=agora, item=item)

    def linhas_legadas(self,solicitacao_id):
        agora=self._leitura()
        return self.banco.execute(self._consulta(self._status(agora)).where(CotacaoFornecedor.solicitacao_id==solicitacao_id).order_by(CotacaoFornecedor.id)).all()
