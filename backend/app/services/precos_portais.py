"""Consultas auxiliares para valor contratado e sigilo dos preços internos."""
from decimal import Decimal
from sqlalchemy import and_, func, select
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.formacao_preco import ConfiguracaoPreco, FormacaoPreco

ESTADOS_VISIVEIS = ('publicada','aprovada_cliente','revisao_cliente','recusada_cliente','contratada')


def ativa(banco):
    return banco.get(ConfiguracaoPreco, 1) is not None


def visibilidade_cliente():
    publicado = select(FormacaoPreco.cotacao_id).where(FormacaoPreco.cotacao_id == CotacaoFornecedor.id,
        FormacaoPreco.estado.in_(ESTADOS_VISIVEIS)).correlate(CotacaoFornecedor).exists()
    # Apenas decisões anteriores à ativação conservam a consulta histórica.
    sem_preco = ~select(FormacaoPreco.cotacao_id).where(FormacaoPreco.cotacao_id == CotacaoFornecedor.id).correlate(CotacaoFornecedor).exists()
    data_ativacao = select(ConfiguracaoPreco.ativada_em).where(ConfiguracaoPreco.id == 1).scalar_subquery()
    historica = and_(sem_preco, CotacaoFornecedor.status.in_(('aceita','recusada','cancelada')),
        ((CotacaoFornecedor.encerrada_em.is_not(None)) & (func.julianday(CotacaoFornecedor.encerrada_em) < func.julianday(data_ativacao))) |
        ((CotacaoFornecedor.encerrada_em.is_(None)) & (func.julianday(CotacaoFornecedor.criada_em) < func.julianday(data_ativacao))))
    return publicado | historica


def preco_contratacao(banco, contrato):
    p = banco.get(FormacaoPreco, contrato.cotacao_id)
    return p if p and p.contratacao_id == contrato.id and p.estado == 'contratada' else None


def custo_contratacao(banco, contrato):
    p = preco_contratacao(banco, contrato)
    return (Decimal(p.custo_centavos)/100).quantize(Decimal('0.01')) if p else contrato.valor_total


def mapa_portal(banco, usuario):
    if usuario.perfil != 'fornecedor':
        return {}
    linhas = banco.execute(select(FormacaoPreco.contratacao_id,FormacaoPreco.custo_centavos)
        .join(CotacaoFornecedor,CotacaoFornecedor.id == FormacaoPreco.cotacao_id)
        .where(FormacaoPreco.estado == 'contratada',FormacaoPreco.contratacao_id.is_not(None),
               CotacaoFornecedor.empresa_fornecedora_id == usuario.empresa_id)).all()
    return {cid:format(Decimal(c)/100,'.2f') for cid,c in linhas}


def reservar_valores(valor, custos):
    if isinstance(valor,list):return [reservar_valores(v,custos) for v in valor]
    if not isinstance(valor,dict):return valor
    retorno={k:reservar_valores(v,custos) for k,v in valor.items()}
    cid=valor.get('contratacao_id')
    if cid is None and 'cotacao_id' in valor and 'empresa_cliente_id' in valor and 'solicitacao_id' in valor:
        cid=valor.get('id')
    if cid in custos:
        if 'valor_total' in retorno:retorno['valor_total']=custos[cid]
        if 'valor_contratado' in retorno:retorno['valor_contratado']=custos[cid]
    return retorno
