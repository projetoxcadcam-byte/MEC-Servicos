"""Formação, conferência, publicação e análise do preço pela empresa cliente."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session
from backend.app.models.formacao_preco import ConfiguracaoPreco, EventoFormacaoPreco, FormacaoPreco
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.notificacao import NotificacaoPerfil
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao, travar_documentacao

REVISION='MEC-SERVICOS-V0.1-D60-FORMACAO-PRECO-2026-10-13'
MAX_CENTAVOS=99_999_999_999_999


def agora():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def sha(d):return hashlib.sha256(json.dumps(d,sort_keys=True,default=str,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def moeda(c):return format(Decimal(c)/100,'.2f')
def centavos(v):
    d=Decimal(str(v))*100
    if not d.is_finite() or d!=d.to_integral_value() or not 0<=d<=MAX_CENTAVOS:
        raise HTTPException(422,detail='valor_preco_invalido')
    return int(d)
def vencida(q):
    criada=q.criada_em.replace(tzinfo=timezone.utc) if q.criada_em.tzinfo is None else q.criada_em.astimezone(timezone.utc)
    return datetime.now(timezone.utc)>=criada+timedelta(days=q.validade_dias)
def termos(q,s,banco):
    from backend.app.models.arquivo_tecnico import ArquivoTecnico
    from backend.app.models.documentacao_cotacao import LiberacaoArquivoCotacao
    from backend.app.models.preparacao_pdf import PreparacaoPdfCotacao, PublicacaoPdfCotacao
    documentos=banco.execute(select(ArquivoTecnico.id,ArquivoTecnico.sha256,ArquivoTecnico.ativo,
        LiberacaoArquivoCotacao.versao,LiberacaoArquivoCotacao.disponivel,LiberacaoArquivoCotacao.sha256,
        PublicacaoPdfCotacao.preparacao_id,PreparacaoPdfCotacao.sha256)
        .outerjoin(LiberacaoArquivoCotacao,LiberacaoArquivoCotacao.arquivo_id==ArquivoTecnico.id)
        .outerjoin(PublicacaoPdfCotacao,and_(PublicacaoPdfCotacao.arquivo_id==ArquivoTecnico.id,
            PublicacaoPdfCotacao.versao_liberacao==LiberacaoArquivoCotacao.versao))
        .outerjoin(PreparacaoPdfCotacao,PreparacaoPdfCotacao.id==PublicacaoPdfCotacao.preparacao_id)
        .where(ArquivoTecnico.solicitacao_id==s.id).order_by(ArquivoTecnico.id)).all()
    return sha({'cotacao':[q.id,q.solicitacao_id,q.empresa_fornecedora_id,str(q.valor_total),q.prazo_dias,q.validade_dias,str(q.criada_em)],
        'documentos':[list(r) for r in documentos],
        'solicitacao':[s.id,s.empresa_cliente_id,s.processo_id,s.material_id,s.quantidade,str(s.dimensao_x_maxima_mm),
            str(s.dimensao_y_maxima_mm),str(s.dimensao_z_maxima_mm),str(s.tolerancia_requerida_mm)]})


class ServicoFormacaoPreco:
    def __init__(self,banco:Session,usuario):
        self.banco,self.usuario=banco,usuario
        if usuario.usuario_id<=0 or usuario.deve_alterar_senha or usuario.perfil not in {'admin','cliente'}:
            raise HTTPException(403,detail='perfil_nao_autorizado_precificacao')
        cfg=banco.get(ConfiguracaoPreco,1)
        if cfg is None or cfg.revision!=REVISION:
            raise HTTPException(503,detail='instalacao_d60_nao_concluida')
        try:
            self.segredo=bytes.fromhex(cfg.segredo_verificacao)
            if len(self.segredo)!=32:raise ValueError()
        except ValueError:raise HTTPException(503,detail='instalacao_d60_nao_concluida') from None

    def contexto(self):return f'{self.usuario.usuario_id}:{self.usuario.perfil}:{self.usuario.empresa_id or 0}'

    def _admin(self):
        if self.usuario.perfil!='admin':raise HTTPException(403,detail='acao_exclusiva_da_administracao')

    def _estado(self,cotacao_id):
        conexao=self.banco.connection()
        if conexao.dialect.name=='sqlite' and not conexao.connection.driver_connection.in_transaction:self.banco.execute(text('BEGIN'))
        q=self.banco.get(CotacaoFornecedor,cotacao_id,populate_existing=True)
        s=self.banco.get(SolicitacaoServico,q.solicitacao_id,populate_existing=True) if q else None
        if q is None or s is None or (self.usuario.perfil=='cliente' and s.empresa_cliente_id!=self.usuario.empresa_id):
            raise HTTPException(404,detail='cotacao_nao_encontrada')
        p=self.banco.get(FormacaoPreco,q.id,populate_existing=True)
        c=self.banco.scalar(select(ContratacaoServico).where(ContratacaoServico.solicitacao_id==s.id))
        estado=sha({'termos':termos(q,s,self.banco),'status_q':q.status,'status_s':s.status,'contrato':c.id if c else None,
            'preco':{col.name:getattr(p,col.name) for col in p.__table__.columns} if p else None})
        versao=hmac.new(self.segredo,estado.encode(),hashlib.sha256).hexdigest()
        return q,s,p,c,versao

    def _editavel(self,q,s,c):
        preco=self.banco.get(FormacaoPreco,q.id) if q.status=='aceita' else None
        aceita_revisavel=q.status=='aceita' and preco is not None and preco.contratacao_id is None
        if q.status!='enviada' and not aceita_revisavel:raise HTTPException(409,detail='cotacao_nao_esta_pendente')
        if q.status=='enviada' and vencida(q):raise HTTPException(409,detail='cotacao_expirada')
        if s.status!='aberta' or c is not None:raise HTTPException(409,detail='solicitacao_ja_contratada_ou_fechada')
        if self.banco.scalar(select(CotacaoFornecedor.id).where(CotacaoFornecedor.solicitacao_id==s.id,CotacaoFornecedor.id!=q.id,CotacaoFornecedor.status=='aceita').limit(1)):
            raise HTTPException(409,detail='solicitacao_ja_possui_cotacao_aceita')

    def obter(self,cotacao_id):
        self._admin();q,s,p,c,v=self._estado(cotacao_id)
        eventos=self.banco.scalars(select(EventoFormacaoPreco).where(EventoFormacaoPreco.cotacao_id==q.id).order_by(EventoFormacaoPreco.id.desc())).all()
        from backend.app.models.empresa import Empresa
        cliente=self.banco.get(Empresa,s.empresa_cliente_id);fornecedor=self.banco.get(Empresa,q.empresa_fornecedora_id)
        try:self._editavel(q,s,c);pode=True
        except HTTPException:pode=False
        return {'contexto':self.contexto(),'cotacao_id':q.id,'solicitacao_id':s.id,'versao':v,'custo_fornecedor':str(q.valor_total),
            'cliente':cliente.razao_social,'fornecedor':fornecedor.razao_social,'pode_editar':pode,
            'preco':self._publicar_admin(p) if p else None,
            'historico':[{'id':e.id,'versao':e.versao,'acao':e.acao,'perfil':e.perfil,'registro':e.registro,'criado_em':e.criado_em} for e in eventos]}

    @staticmethod
    def _publicar_admin(p):
        return {'modo':p.modo,'acrescimo_informado':p.acrescimo_informado,'custo_fornecedor':moeda(p.custo_centavos),
            'acrescimo':moeda(p.acrescimo_centavos),'preco_cliente':moeda(p.preco_cliente_centavos),
            'despesas_previstas':moeda(p.despesas_previstas_centavos),'resultado_previsto':moeda(p.acrescimo_centavos-p.despesas_previstas_centavos),
            'estado':p.estado,'numero_versao':p.versao,'contratacao_id':p.contratacao_id,'atualizado_em':p.atualizado_em}

    def conferir(self,cotacao_id,dados):
        self._admin();q,s,p,c,v=self._estado(cotacao_id);self._editavel(q,s,c)
        if not hmac.compare_digest(v,dados.versao):raise HTTPException(409,detail='preco_alterado_atualize')
        custo=centavos(q.valor_total)
        acrescimo=int((Decimal(custo)*dados.acrescimo/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if dados.modo=='percentual' else centavos(dados.acrescimo)
        preco=custo+acrescimo;despesas=centavos(dados.despesas_previstas)
        if preco>MAX_CENTAVOS:raise HTTPException(422,detail='preco_cliente_supera_limite')
        resultado={'custo_fornecedor':moeda(custo),'acrescimo':moeda(acrescimo),'preco_cliente':moeda(preco),
            'despesas_previstas':moeda(despesas),'resultado_previsto':moeda(acrescimo-despesas),'versao':v}
        resultado['conferencia']=sha({'usuario':self.usuario.usuario_id,'cotacao':q.id,'versao':v,'modo':dados.modo,
            'informado':str(dados.acrescimo),'resultado':resultado})
        return {'contexto':self.contexto(),**resultado}

    def _repeticao(self,chave,pedido):
        e=self.banco.scalar(select(EventoFormacaoPreco).where(EventoFormacaoPreco.chave_operacao==str(chave)))
        if e:
            if e.usuario_id!=self.usuario.usuario_id or e.pedido_sha256!=pedido:
                raise HTTPException(409,detail='chave_operacao_reutilizada')
            return json.loads(e.resultado_json)

    def _evento(self,p,acao,registro,chave,pedido):
        e=EventoFormacaoPreco(cotacao_id=p.cotacao_id,versao=p.versao,acao=acao,usuario_id=self.usuario.usuario_id,
            perfil=self.usuario.perfil,registro=registro,criado_em=p.atualizado_em,chave_operacao=str(chave),pedido_sha256=pedido,resultado_json='{}')
        self.banco.add(e);self.banco.flush()
        resultado={'contexto':self.contexto(),'cotacao_id':p.cotacao_id,'evento_id':e.id,'estado':p.estado,'numero_versao':p.versao}
        e.resultado_json=json.dumps(resultado,sort_keys=True);return e,resultado

    def _notificar(self,p,e,perfil,empresa,assunto,mensagem):
        destino=f'/cliente/cotacoes?cotacao={p.cotacao_id}' if perfil=='cliente' else f'/admin/cotacoes?solicitacao={p.solicitacao_id}&cotacao={p.cotacao_id}'
        self.banco.add(NotificacaoPerfil(chave_evento=f'preco-d60:{e.id}:{perfil}:{empresa}',perfil_destino=perfil,empresa_destino=empresa,
            perfil_origem=self.usuario.perfil,assunto=assunto,mensagem=mensagem,destino=destino,
            solicitacao_id=p.solicitacao_id,contratacao_id=p.contratacao_id,criada_em=p.atualizado_em))

    def registrar(self,cotacao_id,dados):
        self._admin();pedido=sha({'cotacao':cotacao_id,'usuario':self.usuario.usuario_id,'dados':dados.model_dump(mode='json')})
        travar_documentacao(self.banco)
        repetida=self._repeticao(dados.chave_operacao,pedido)
        if repetida:return repetida
        calculo=self.conferir(cotacao_id,dados)
        if not hmac.compare_digest(calculo['conferencia'],dados.conferencia):raise HTTPException(409,detail='conferencia_preco_divergente')
        q,s,p,c,v=self._estado(cotacao_id)
        registro=dados.registro_interno.strip()
        if len(registro)<3:raise HTTPException(422,detail='registro_interno_obrigatorio')
        if dados.acao=='publicar':
            ServicoDocumentacaoCotacao(self.banco).exigir_para_cotacao(s.id)
            outro=self.banco.scalar(select(FormacaoPreco.cotacao_id).join(CotacaoFornecedor,CotacaoFornecedor.id==FormacaoPreco.cotacao_id).where(CotacaoFornecedor.status=='enviada',func.julianday(CotacaoFornecedor.criada_em)+CotacaoFornecedor.validade_dias>func.julianday(agora()),FormacaoPreco.solicitacao_id==s.id,
                FormacaoPreco.cotacao_id!=q.id,FormacaoPreco.estado.in_(('publicada','aprovada_cliente'))).limit(1))
            if outro:raise HTTPException(409,detail='outra_proposta_publicada_retire_primeiro')
        assinatura_termos=termos(q,s,self.banco)
        if p is None:
            if dados.acao=='retirar':raise HTTPException(409,detail='preco_ainda_nao_registrado')
            p=FormacaoPreco(cotacao_id=q.id,solicitacao_id=s.id,empresa_cliente_id=s.empresa_cliente_id,versao=0)
            self.banco.add(p)
        p.custo_centavos=centavos(calculo['custo_fornecedor']);p.modo=dados.modo;p.acrescimo_informado=str(dados.acrescimo)
        p.acrescimo_centavos=centavos(calculo['acrescimo']);p.preco_cliente_centavos=centavos(calculo['preco_cliente'])
        p.despesas_previstas_centavos=centavos(calculo['despesas_previstas']);p.termos_sha256=assinatura_termos
        anterior=p.estado;p.estado={'salvar':'rascunho','publicar':'publicada','retirar':'retirada'}[dados.acao]
        p.versao+=1;p.atualizado_em=agora()
        e,resposta=self._evento(p,dados.acao,registro,dados.chave_operacao,pedido)
        if dados.acao=='publicar':self._notificar(p,e,'cliente',s.empresa_cliente_id,'Orçamento disponível para análise',f'A administração publicou o orçamento da solicitação #{s.id}. Confira o preço final em Cotações.')
        elif anterior in ('publicada','aprovada_cliente','revisao_cliente'):
            self._notificar(p,e,'cliente',s.empresa_cliente_id,'Orçamento em revisão',f'O orçamento da solicitação #{s.id} voltou para revisão administrativa.')
        self.banco.commit();return resposta

    def analisar(self,cotacao_id,dados):
        if self.usuario.perfil!='cliente' or dados.empresa_cliente_id!=self.usuario.empresa_id:
            raise HTTPException(403,detail='empresa_diverge_da_sessao')
        pedido=sha({'cotacao':cotacao_id,'usuario':self.usuario.usuario_id,'dados':dados.model_dump(mode='json')})
        travar_documentacao(self.banco);repetida=self._repeticao(dados.chave_operacao,pedido)
        if repetida:return repetida
        q,s,p,c,v=self._estado(cotacao_id)
        if p is None or p.estado!='publicada':raise HTTPException(409,detail='orcamento_nao_disponivel_para_analise')
        self._editavel(q,s,c)
        if not hmac.compare_digest(v,dados.versao) or not hmac.compare_digest(p.termos_sha256,termos(q,s,self.banco)):
            raise HTTPException(409,detail='preco_alterado_atualize')
        if dados.acao in ('revisar','recusar') and len(dados.observacao.strip())<3:
            raise HTTPException(422,detail='motivo_analise_obrigatorio')
        ServicoDocumentacaoCotacao(self.banco).exigir_para_cotacao(s.id)
        p.estado={'aprovar':'aprovada_cliente','revisar':'revisao_cliente','recusar':'recusada_cliente'}[dados.acao]
        p.versao+=1;p.atualizado_em=agora()
        e,resposta=self._evento(p,dados.acao,dados.observacao.strip() or 'Cliente aprovou o preço e as condições apresentados.',dados.chave_operacao,pedido)
        self._notificar(p,e,'admin',0,'Análise de orçamento pelo cliente',f'O cliente registrou {dados.acao} no orçamento da solicitação #{s.id}. Confira a análise antes de contratar.')
        self.banco.commit();return resposta


def exigir_aprovacao(banco,q):
    from backend.app.services.precos_portais import ativa
    if not ativa(banco):return None
    p=banco.get(FormacaoPreco,q.id);s=banco.get(SolicitacaoServico,q.solicitacao_id)
    cfg=banco.get(ConfiguracaoPreco,1)
    if p is None and q.status=='aceita':
        data_legada=q.encerrada_em or q.criada_em
        encerrada=data_legada.replace(tzinfo=timezone.utc) if data_legada.tzinfo is None else data_legada
        if encerrada<datetime.fromisoformat(cfg.ativada_em.replace('Z','+00:00')):return None
    if not p or p.estado!='aprovada_cliente' or not hmac.compare_digest(p.termos_sha256,termos(q,s,banco)):
        raise HTTPException(409,detail='orcamento_cliente_aguarda_aprovacao')
    ServicoDocumentacaoCotacao(banco).exigir_para_cotacao(s.id)
    return p


def valor_para_contratar(banco,q):
    p=exigir_aprovacao(banco,q)
    return Decimal(moeda(p.preco_cliente_centavos)) if p else q.valor_total


def vincular_contrato(banco,q,contrato):
    from backend.app.services.precos_portais import ativa
    if not ativa(banco):return
    p=exigir_aprovacao(banco,q)
    if p is None:return
    p.contratacao_id=contrato.id;p.estado='contratada';p.versao+=1;p.atualizado_em=agora()
    banco.add(EventoFormacaoPreco(cotacao_id=q.id,versao=p.versao,acao='contratar',usuario_id=banco.info['mec_usuario_notificacoes'].usuario_id,
        perfil='admin',registro=f'Preço final e custo vinculados à contratação #{contrato.id}.',criado_em=p.atualizado_em,
        chave_operacao=f'contrato-d60-{contrato.id}',pedido_sha256=sha({'contrato':contrato.id}),
        resultado_json=json.dumps({'contratacao_id':contrato.id,'preco_cliente':moeda(p.preco_cliente_centavos),'custo_fornecedor':moeda(p.custo_centavos)})))
