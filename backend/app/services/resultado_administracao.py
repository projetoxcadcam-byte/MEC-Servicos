"""Resultado previsto da intermediação e ganho bruto de serviços liquidados."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.formacao_preco import FormacaoPreco
from backend.app.services.formacao_preco import moeda
from backend.app.services.painel_administrativo import ServicoPainelAdministrativo
from backend.app.services.financeiro_administrativo import centavos


class ServicoResultadoAdministracao:
    def __init__(self,banco,usuario):
        if usuario.perfil!='admin' or usuario.usuario_id<=0:raise HTTPException(403,detail='acao_exclusiva_da_administracao')
        self.banco,self.usuario=banco,usuario

    def consultar(self,inicio,fim,deslocamento,limite,incluir_despesas=False,identificar_empresas=False):
        if inicio>fim:raise HTTPException(422,detail='periodo_invertido')
        if (fim-inicio).days>3660:raise HTTPException(422,detail='periodo_supera_dez_anos')
        from sqlalchemy import text
        cx=self.banco.connection()
        if cx.dialect.name=='sqlite' and not cx.connection.driver_connection.in_transaction:self.banco.execute(text('BEGIN'))
        consulta=ServicoPainelAdministrativo(self.banco)._consulta().add_columns(FormacaoPreco.despesas_previstas_centavos)
        consulta=consulta.where(ContratacaoServico.criada_em>=datetime.combine(inicio,datetime.min.time()),
            ContratacaoServico.criada_em<datetime.combine(fim+timedelta(days=1),datetime.min.time()),
            ContratacaoServico.status.in_(('ativa','encerrada')),FormacaoPreco.estado=='contratada')
        if incluir_despesas:
            from sqlalchemy import select,func
            from backend.app.models.despesa_administracao import DespesaAdministracao
            despesas_pagas=select(DespesaAdministracao.contratacao_id.label('cid'),func.sum(DespesaAdministracao.valor_centavos).label('pago')).where(DespesaAdministracao.status=='confirmada').group_by(DespesaAdministracao.contratacao_id).subquery()
            consulta=consulta.outerjoin(despesas_pagas,despesas_pagas.c.cid==ContratacaoServico.id).add_columns(func.coalesce(despesas_pagas.c.pago,0))
        totais={k:0 for k in ('venda_cliente','custo_fornecedor','ganho_bruto_previsto','despesas_previstas','resultado_previsto','ganho_bruto_confirmado')}
        if incluir_despesas:totais.update(despesas_pagas=0,resultado_apos_despesas=0,resultado_liquidado_apos_despesas=0)
        itens=[]
        for linha in self.banco.execute(consulta):
            c,o,ciclo,controle,cliente,fornecedor,pagos,repasses,etapa,custo,despesas=linha[:11]
            resumo=ServicoPainelAdministrativo._item(linha[:10])
            venda=centavos(c.valor_total);ganho=venda-custo;despesas=int(despesas or 0)
            liquidado=(resumo.entrega_concluida and centavos(resumo.total_recebido)==venda and centavos(resumo.total_repassado)==custo and resumo.situacao!='verificar')
            valores=dict(venda_cliente=venda,custo_fornecedor=custo,ganho_bruto_previsto=ganho,
                despesas_previstas=despesas,resultado_previsto=ganho-despesas,ganho_bruto_confirmado=ganho if liquidado else 0)
            if incluir_despesas:
                pagas=int(linha[11]);valores.update(despesas_pagas=pagas,resultado_apos_despesas=ganho-pagas,resultado_liquidado_apos_despesas=ganho-pagas if liquidado else 0)
            for k,v in valores.items():totais[k]+=v
            itens.append(dict(contratacao_id=c.id,ordem_servico_id=o.id if o else None,cliente=cliente,fornecedor=fornecedor,
                criada_em=c.criada_em.isoformat()+'Z',liquidado=liquidado,situacao=resumo.situacao,**{k:moeda(v) for k,v in valores.items()}))
            if identificar_empresas:
                itens[-1].update(empresa_cliente_id=c.empresa_cliente_id,empresa_fornecedora_id=c.empresa_fornecedora_id)
        return dict(contexto=f'{self.usuario.usuario_id}:admin:0',inicio=str(inicio),fim=str(fim),base_periodo='criacao_contratacao_utc',
            total=len(itens),deslocamento=deslocamento,limite=limite,totais={k:moeda(v) for k,v in totais.items()},itens=itens if limite is None else itens[deslocamento:deslocamento+limite])
