"""Metas do ADM: centavos exatos, leitura coerente e gravações auditadas."""
import csv
import hmac
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fastapi import HTTPException
from sqlalchemy import func, select, text
from backend.app.models.meta_resultado import ConfiguracaoMetas, MetaResultado, EventoMetaResultado
from backend.app.services.analise_resultado import ServicoAnaliseResultado, centavos_exatos
from backend.app.services.formacao_preco import agora, centavos, moeda, sha
from backend.app.services.documentacao_cotacao import travar_documentacao
from backend.app.services.relatorio_administrativo import celula_csv
from backend.app.services.relatorio_resultado import CAMPOS

REVISION='MEC-SERVICOS-V0.1-D64-METAS-RESULTADO-2026-10-14'

def percentual(realizado,meta):
    if meta is None or meta==0:return None
    with localcontext() as ctx:
        ctx.prec=50
        return format((Decimal(realizado)*100/Decimal(meta)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f')

class ServicoMetasResultado:
    def __init__(self,despesas):
        self.despesas=despesas;self.banco=despesas.banco;self.usuario=despesas.usuario
        cfg=self.banco.get(ConfiguracaoMetas,1)
        if cfg is None or cfg.revision!=REVISION:raise HTTPException(503,detail='instalacao_d64_nao_concluida')

    def _leitura(self):
        cx=self.banco.connection()
        if cx.dialect.name=='sqlite' and not cx.connection.driver_connection.in_transaction:self.banco.execute(text('BEGIN'))

    def _estado(self,mes):
        self._leitura()
        meta=self.banco.get(MetaResultado,mes,populate_existing=True)
        dados={'mes':mes,'usuario':self.usuario.usuario_id,'meta':None if meta is None else [meta.estado,meta.valor_centavos,meta.versao,meta.atualizada_em]}
        return meta,hmac.new(self.despesas.segredo,sha(dados).encode(),'sha256').hexdigest()

    def obter(self,mes,deslocamento=0,limite=20):
        meta,versao=self._estado(mes)
        total=int(self.banco.scalar(select(func.count()).select_from(EventoMetaResultado).where(EventoMetaResultado.mes==mes)))
        eventos=self.banco.scalars(select(EventoMetaResultado).where(EventoMetaResultado.mes==mes).order_by(EventoMetaResultado.versao.desc()).offset(deslocamento).limit(limite)).all()
        return dict(contexto=self.despesas.contexto(),mes=mes,versao=versao,
            meta=None if meta is None else dict(valor=moeda(meta.valor_centavos),estado=meta.estado,administrador_nome=meta.administrador_nome,atualizada_em=meta.atualizada_em),
            total_eventos=total,deslocamento=deslocamento,limite=limite,historico=[dict(id=e.id,versao=e.versao,acao=e.acao,
                valor_anterior=None if e.valor_anterior_centavos is None else moeda(e.valor_anterior_centavos),
                valor_atual=None if e.valor_atual_centavos is None else moeda(e.valor_atual_centavos),
                administrador_nome=e.administrador_nome,registro_interno=e.registro_interno,criado_em=e.criado_em) for e in eventos])

    def operar(self,mes,dados):
        pedido=sha({'mes':mes,'usuario':self.usuario.usuario_id,'dados':dados.model_dump(mode='json')})
        travar_documentacao(self.banco)
        e=self.banco.scalar(select(EventoMetaResultado).where(EventoMetaResultado.chave_operacao==str(dados.chave_operacao)))
        if e:
            if e.usuario_admin_id!=self.usuario.usuario_id or not hmac.compare_digest(e.pedido_sha256,pedido):raise HTTPException(409,detail='chave_operacao_reutilizada')
            return json.loads(e.resultado_json)
        meta,versao=self._estado(mes)
        if not hmac.compare_digest(versao,dados.versao):raise HTTPException(409,detail='meta_alterada_atualize')
        anterior=meta.valor_centavos if meta and meta.estado=='ativa' else None
        if dados.acao=='retirar' and anterior is None:raise HTTPException(409,detail='mes_sem_meta_ativa')
        valor=centavos(dados.valor) if dados.acao=='definir' else None
        if dados.acao=='definir' and anterior==valor:raise HTTPException(409,detail='meta_igual_a_atual')
        momento=agora();seq=meta.versao+1 if meta else 1
        if meta is None:
            meta=MetaResultado(mes=mes);self.banco.add(meta)
        if valor is not None:meta.valor_centavos=valor
        meta.estado='ativa' if dados.acao=='definir' else 'retirada';meta.versao=seq
        meta.usuario_admin_id=self.usuario.usuario_id;meta.administrador_nome=self.usuario.nome;meta.atualizada_em=momento
        self.banco.flush()
        e=EventoMetaResultado(mes=mes,versao=seq,acao=dados.acao,valor_anterior_centavos=anterior,valor_atual_centavos=valor,
            usuario_admin_id=self.usuario.usuario_id,administrador_nome=self.usuario.nome,registro_interno=dados.registro_interno,
            criado_em=momento,chave_operacao=str(dados.chave_operacao),pedido_sha256=pedido,resultado_json='{}')
        self.banco.add(e);self.banco.flush()
        r=dict(contexto=self.despesas.contexto(),mes=mes,evento_id=e.id,estado=meta.estado,valor=None if valor is None else moeda(valor))
        e.resultado_json=json.dumps(r,sort_keys=True);self.banco.commit();return r

    def comparar(self,ano):
        r=ServicoAnaliseResultado(self.despesas).obter(date(ano,1,1),date(ano,12,31))
        metas={m.mes:m for m in self.banco.scalars(select(MetaResultado).where(MetaResultado.mes>=f'{ano:04d}-01',MetaResultado.mes<=f'{ano:04d}-12')).all()}
        hoje=datetime.now(timezone.utc).date();mes_atual=hoje.strftime('%Y-%m')
        meses=[];meta_total=realizado_com_meta=quantidade=0
        for g in r['meses']:
            m=metas.get(g['chave']);valor=m.valor_centavos if m and m.estado=='ativa' else None
            realizado=centavos_exatos(g['totais']['resultado_liquidado_apos_despesas'])
            if valor is not None:quantidade+=1;meta_total+=valor;realizado_com_meta+=realizado
            meses.append(dict(mes=g['chave'],nome=g['nome'],fase='encerrado' if g['chave']<mes_atual else 'em_andamento' if g['chave']==mes_atual else 'futuro',
                total=g['total'],liquidadas=g['liquidadas'],totais=g['totais'],meta=None if valor is None else moeda(valor),
                diferenca=None if valor is None else moeda(realizado-valor),atingimento_percentual=percentual(realizado,valor),
                situacao='sem_meta' if valor is None else 'meta_zero' if valor==0 else 'alcancada' if realizado>=valor else 'abaixo'))
        comp=dict(contexto=r['contexto'],ano=ano,base_periodo=r['base_periodo'],base_meta='resultado_liquidado_apos_despesas',
            hoje_utc=str(hoje),total=r['total'],liquidadas=r['liquidadas'],totais=r['totais'],meses_com_meta=quantidade,
            meta_total=moeda(meta_total) if quantidade else None,realizado_com_meta=moeda(realizado_com_meta),
            diferenca_total=moeda(realizado_com_meta-meta_total) if quantidade else None,
            atingimento_total_percentual=percentual(realizado_com_meta,meta_total) if quantidade else None,meses=meses)
        # Vínculo também às revisões das metas: mudar e voltar ao mesmo valor
        # ainda exige atualizar uma exportação aberta antes das alterações.
        assinatura=sha({'comparacao':comp,'revisoes':[(k,m.versao,m.estado) for k,m in sorted(metas.items())]})
        comp['versao']=hmac.new(self.despesas.segredo,assinatura.encode(),'sha256').hexdigest()
        comp['consulta_em']=agora();return comp

    def exportar(self,ano,versao):
        r=self.comparar(ano)
        if not hmac.compare_digest(versao,r['versao']):raise HTTPException(409,detail='metas_ou_resultado_alterados_atualize')
        titulos=[t for _,t in CAMPOS]
        cols=['Tipo de registro','Ano','Mês de criação dos serviços UTC','Consulta em UTC','Fase do mês','Contratações','Liquidadas',
            'Meses com meta','Meta (R$)','Realizado nos meses com meta (R$)','Diferença da meta (R$)','Atingimento (%)','Situação',*titulos]
        monetarias=set(titulos)|{'Meta (R$)','Realizado nos meses com meta (R$)','Diferença da meta (R$)','Atingimento (%)'}
        s=io.StringIO();w=csv.writer(s,delimiter=';',lineterminator='\r\n');w.writerow(cols)
        def escrever(tipo,valores,dados):
            row={'Tipo de registro':tipo,'Ano':r['ano'],'Consulta em UTC':r['consulta_em'],**dados,**{t:valores[k] for k,t in CAMPOS}}
            w.writerow([('' if row.get(c) is None else str(row[c]).replace('.',',')) if c in monetarias else celula_csv(row.get(c)) for c in cols])
        escrever('Resumo do ano',r['totais'],{'Contratações':r['total'],'Liquidadas':r['liquidadas'],'Meses com meta':r['meses_com_meta'],
            'Meta (R$)':r['meta_total'],'Realizado nos meses com meta (R$)':r['realizado_com_meta'],'Diferença da meta (R$)':r['diferenca_total'],'Atingimento (%)':r['atingimento_total_percentual']})
        nomes={'sem_meta':'Sem meta','meta_zero':'Meta zero; percentual não calculado','alcancada':'Meta alcançada','abaixo':'Abaixo da meta'}
        for m in r['meses']:
            escrever('Mês',m['totais'],{'Mês de criação dos serviços UTC':m['mes'],'Fase do mês':{'encerrado':'Mês anterior','em_andamento':'Mês em andamento','futuro':'Mês futuro'}[m['fase']],
                'Contratações':m['total'],'Liquidadas':m['liquidadas'],'Meses com meta':int(m['meta'] is not None),
                'Meta (R$)':m['meta'],'Realizado nos meses com meta (R$)':m['totais']['resultado_liquidado_apos_despesas'] if m['meta'] is not None else '',
                'Diferença da meta (R$)':m['diferenca'],'Atingimento (%)':m['atingimento_percentual'],'Situação':nomes[m['situacao']]})
        return '\ufeff'+s.getvalue(),r['versao']
