"""Registro exato e auditado de despesas efetivamente pagas por contratação."""
import hashlib, hmac, json
from fastapi import HTTPException
from sqlalchemy import func, select, text
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.despesa_administracao import ConfiguracaoDespesas, DespesaAdministracao, EventoDespesaAdministracao
from backend.app.models.formacao_preco import FormacaoPreco
from backend.app.models.empresa import Empresa
from backend.app.services.formacao_preco import ServicoFormacaoPreco, agora, centavos, moeda, sha
from backend.app.services.documentacao_cotacao import travar_documentacao

REVISION='MEC-SERVICOS-V0.1-D61-DESPESAS-REAIS-ADMINISTRACAO-2026-10-13'

class ServicoDespesasAdministracao:
    def __init__(self,banco,usuario):
        if usuario.perfil!='admin' or usuario.usuario_id<=0 or usuario.deve_alterar_senha:
            raise HTTPException(403,detail='acao_exclusiva_da_administracao')
        cfg=banco.get(ConfiguracaoDespesas,1)
        if cfg is None or cfg.revision!=REVISION:raise HTTPException(503,detail='instalacao_d61_nao_concluida')
        self.banco,self.usuario=banco,usuario
        self.segredo=ServicoFormacaoPreco(banco,usuario).segredo
    def contexto(self):return f'{self.usuario.usuario_id}:admin:0'
    def _estado(self,cid):
        cx=self.banco.connection()
        if cx.dialect.name=='sqlite' and not cx.connection.driver_connection.in_transaction:self.banco.execute(text('BEGIN'))
        c=self.banco.get(ContratacaoServico,cid,populate_existing=True)
        if c is None:raise HTTPException(404,detail='contratacao_nao_encontrada')
        p=self.banco.scalar(select(FormacaoPreco).where(FormacaoPreco.contratacao_id==cid,FormacaoPreco.estado=='contratada').execution_options(populate_existing=True))
        if p is None:raise HTTPException(409,detail='despesa_exige_contratacao_precificada')
        seq=int(self.banco.scalar(select(func.coalesce(func.max(EventoDespesaAdministracao.versao),0)).where(EventoDespesaAdministracao.contratacao_id==cid)))
        raw=sha({'contratacao':cid,'status':c.status,'preco':[p.cotacao_id,p.preco_cliente_centavos,p.custo_centavos,p.versao],'eventos':seq})
        return c,p,seq,hmac.new(self.segredo,raw.encode(),hashlib.sha256).hexdigest()
    def obter(self,cid,deslocamento=0,limite=20):
        c,p,seq,v=self._estado(cid)
        filtro=DespesaAdministracao.contratacao_id==cid
        total=self.banco.scalar(select(func.count()).select_from(DespesaAdministracao).where(filtro))
        paga=int(self.banco.scalar(select(func.coalesce(func.sum(DespesaAdministracao.valor_centavos),0)).where(filtro,DespesaAdministracao.status=='confirmada')))
        itens=self.banco.scalars(select(DespesaAdministracao).where(filtro).order_by(DespesaAdministracao.paga_em.desc(),DespesaAdministracao.id.desc()).offset(deslocamento).limit(limite)).all()
        eventos=self.banco.scalars(select(EventoDespesaAdministracao).where(EventoDespesaAdministracao.contratacao_id==cid).order_by(EventoDespesaAdministracao.id.desc()).limit(20)).all()
        cliente=self.banco.get(Empresa,c.empresa_cliente_id);fornecedor=self.banco.get(Empresa,c.empresa_fornecedora_id)
        return {'contexto':self.contexto(),'contratacao_id':cid,'versao':v,'cliente':cliente.razao_social,'fornecedor':fornecedor.razao_social,'contratacao_status':c.status,
                'pode_registrar':c.status in ('ativa','encerrada'),'despesas_confirmadas':moeda(paga),'despesas_previstas':moeda(p.despesas_previstas_centavos),
                'ganho_bruto_previsto':moeda(p.acrescimo_centavos),'resultado_apos_despesas':moeda(p.acrescimo_centavos-paga),
                'total':total,'deslocamento':deslocamento,'limite':limite,'total_eventos':seq,
                'itens':[{'id':d.id,'categoria':d.categoria,'descricao':d.descricao,'valor':moeda(d.valor_centavos),'paga_em':d.paga_em,'referencia':d.referencia,
                    'status':d.status,'criada_em':d.criada_em,'estornada_em':d.estornada_em,'administrador_nome':d.administrador_nome,'registro_interno':d.registro_interno} for d in itens],
                'historico':[{'id':e.id,'despesa_id':e.despesa_id,'acao':e.acao,'administrador_nome':e.administrador_nome,'registro_interno':e.registro_interno,'referencia':e.referencia,'criado_em':e.criado_em} for e in eventos]}
    def resultado(self,inicio,fim,deslocamento,limite,pedidos_deslocamento=0,historico_deslocamento=0):
        from backend.app.services.resultado_administracao import ServicoResultadoAdministracao
        r=ServicoResultadoAdministracao(self.banco,self.usuario).consultar(inicio,fim,deslocamento,limite,incluir_despesas=True)
        r['acompanhamento']=self._acompanhamento(inicio,fim,pedidos_deslocamento,historico_deslocamento,limite)
        return r
    def _acompanhamento(self,inicio,fim,pedidos_deslocamento,historico_deslocamento,limite):
        from datetime import datetime,timedelta
        from sqlalchemy import and_
        from sqlalchemy.orm import aliased
        from backend.app.models.solicitacao import SolicitacaoServico
        from backend.app.models.cotacao import CotacaoFornecedor
        from backend.app.models.ordem_servico import OrdemServico
        from backend.app.services.formacao_preco import vencida
        comeco=datetime.combine(inicio,datetime.min.time());final=datetime.combine(fim+timedelta(days=1),datetime.min.time())
        cliente,fornecedor=aliased(Empresa),aliased(Empresa)
        consulta=select(SolicitacaoServico,CotacaoFornecedor,FormacaoPreco,cliente.razao_social,fornecedor.razao_social).join(cliente,cliente.id==SolicitacaoServico.empresa_cliente_id).outerjoin(
            CotacaoFornecedor,and_(CotacaoFornecedor.solicitacao_id==SolicitacaoServico.id,CotacaoFornecedor.status.in_(('enviada','aceita')))).outerjoin(
            fornecedor,fornecedor.id==CotacaoFornecedor.empresa_fornecedora_id).outerjoin(FormacaoPreco,FormacaoPreco.cotacao_id==CotacaoFornecedor.id).where(
            SolicitacaoServico.status=='aberta',SolicitacaoServico.criada_em>=comeco,SolicitacaoServico.criada_em<final,
            ~select(ContratacaoServico.id).where(ContratacaoServico.solicitacao_id==SolicitacaoServico.id).exists()).order_by(SolicitacaoServico.id.desc(),CotacaoFornecedor.id.desc())
        pedidos=[]
        for s,q,p,cn,fn in self.banco.execute(consulta):
            etapa='sem_proposta' if q is None else 'expirada' if q.status=='enviada' and vencida(q) else p.estado if p else 'preparar_preco'
            pedidos.append({'solicitacao_id':s.id,'cotacao_id':q.id if q else None,'cliente':cn,'fornecedor':fn,'etapa':etapa,
                'valor_cliente':moeda(p.preco_cliente_centavos) if p else None,'cotacao_status':q.status if q else None})
        consulta=select(ContratacaoServico,OrdemServico.id,cliente.razao_social,fornecedor.razao_social).join(cliente,cliente.id==ContratacaoServico.empresa_cliente_id).join(
            fornecedor,fornecedor.id==ContratacaoServico.empresa_fornecedora_id).outerjoin(OrdemServico,OrdemServico.contratacao_id==ContratacaoServico.id).where(
            ContratacaoServico.criada_em>=comeco,ContratacaoServico.criada_em<final,
            ~select(FormacaoPreco.cotacao_id).where(FormacaoPreco.contratacao_id==ContratacaoServico.id,FormacaoPreco.estado=='contratada').exists()).order_by(ContratacaoServico.id.desc())
        historico=[{'contratacao_id':c.id,'ordem_servico_id':oid,'solicitacao_id':c.solicitacao_id,'cliente':cn,'fornecedor':fn,'valor_contratado':str(c.valor_total),'status':c.status} for c,oid,cn,fn in self.banco.execute(consulta)]
        return {'pedidos':{'base_periodo':'criacao_solicitacao_utc','total':len(pedidos),'total_solicitacoes':len({p['solicitacao_id'] for p in pedidos}),
                    'deslocamento':pedidos_deslocamento,'limite':limite,'itens':pedidos[pedidos_deslocamento:pedidos_deslocamento+limite]},
                'historico_anterior':{'base_periodo':'criacao_contratacao_utc','total':len(historico),'deslocamento':historico_deslocamento,'limite':limite,'itens':historico[historico_deslocamento:historico_deslocamento+limite]}}
    def _repetida(self,chave,pedido):
        e=self.banco.scalar(select(EventoDespesaAdministracao).where(EventoDespesaAdministracao.chave_operacao==str(chave)))
        if e:
            if e.usuario_admin_id!=self.usuario.usuario_id or not hmac.compare_digest(e.pedido_sha256,pedido):raise HTTPException(409,detail='chave_operacao_reutilizada')
            return json.loads(e.resultado_json)
    def registrar(self,cid,dados):return self._operar(cid,dados,None)
    def estornar(self,cid,did,dados):return self._operar(cid,dados,did)
    def _operar(self,cid,dados,did):
        acao='estornar' if did is not None else 'registrar'
        pedido=sha({'acao':acao,'contratacao':cid,'despesa':did,'usuario':self.usuario.usuario_id,'dados':dados.model_dump(mode='json')})
        travar_documentacao(self.banco)
        repetida=self._repetida(dados.chave_operacao,pedido)
        if repetida:return repetida
        c,p,seq,v=self._estado(cid)
        if not hmac.compare_digest(v,dados.versao):raise HTTPException(409,detail='despesas_alteradas_atualize')
        momento=agora()
        if acao=='registrar':
            if c.status not in ('ativa','encerrada'):raise HTTPException(409,detail='contratacao_nao_permite_despesa')
            d=DespesaAdministracao(contratacao_id=cid,categoria=dados.categoria,descricao=dados.descricao,valor_centavos=centavos(dados.valor),paga_em=str(dados.paga_em),
                referencia=dados.referencia,status='confirmada',usuario_admin_id=self.usuario.usuario_id,administrador_nome=self.usuario.nome,
                registro_interno=dados.registro_interno,criada_em=momento)
            self.banco.add(d);self.banco.flush()
        else:
            d=self.banco.get(DespesaAdministracao,did,populate_existing=True)
            if d is None or d.contratacao_id!=cid:raise HTTPException(404,detail='despesa_nao_encontrada')
            if d.status!='confirmada':raise HTTPException(409,detail='despesa_ja_estornada')
            d.status='estornada';d.estornada_em=momento
        e=EventoDespesaAdministracao(contratacao_id=cid,despesa_id=d.id,versao=seq+1,acao=acao,usuario_admin_id=self.usuario.usuario_id,administrador_nome=self.usuario.nome,
            registro_interno=dados.registro_interno,referencia=dados.referencia,criado_em=momento,chave_operacao=str(dados.chave_operacao),pedido_sha256=pedido,resultado_json='{}')
        self.banco.add(e);self.banco.flush()
        r={'contexto':self.contexto(),'contratacao_id':cid,'despesa_id':d.id,'evento_id':e.id,'status':d.status}
        e.resultado_json=json.dumps(r,sort_keys=True);self.banco.commit();return r
