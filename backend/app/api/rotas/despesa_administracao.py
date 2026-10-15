from datetime import date
from typing import Annotated, Literal
from fastapi import APIRouter,Depends,HTTPException,Path,Query,Request,Response
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.despesa_administracao import RegistroDespesa,EstornoDespesa
from backend.app.schemas.relatorio_resultado import RelatorioResultado
from backend.app.services.relatorio_resultado import ServicoRelatorioResultado
from backend.app.services.despesa_administracao import ServicoDespesasAdministracao
from backend.app.schemas.analise_resultado import AnaliseResultado
from backend.app.services.analise_resultado import ServicoAnaliseResultado
from backend.app.schemas.meta_resultado import OperacaoMeta, DetalheMeta, ComparacaoMetas
from backend.app.services.meta_resultado import ServicoMetasResultado
roteador=APIRouter(prefix='/administracao/despesas',tags=['despesas-reais-administracao'])
Banco=Annotated[Session,Depends(obter_banco)]
ID=Annotated[int,Path(gt=0,le=9_999_999_999_999)]
def servico(request,response,banco):
    s=ServicoDespesasAdministracao(banco,request.state.usuario_acesso)
    contexto=request.headers.get('x-mec-despesas-contexto')
    if contexto is not None and contexto!=s.contexto():raise HTTPException(409,detail='contexto_despesas_alterado')
    response.headers['Cache-Control']='no-store';return s
@roteador.get('/resultado')
def resultado(request:Request,response:Response,banco:Banco,inicio:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),fim:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),deslocamento:int=Query(0,ge=0,le=1_000_000),limite:int=Query(20,ge=1,le=100),pedidos_deslocamento:int=Query(0,ge=0,le=1_000_000),historico_deslocamento:int=Query(0,ge=0,le=1_000_000)):
    return servico(request,response,banco).resultado(inicio,fim,deslocamento,limite,pedidos_deslocamento,historico_deslocamento)
@roteador.get('/contratacoes/{contratacao_id}')
def obter(contratacao_id:ID,request:Request,response:Response,banco:Banco,deslocamento:int=Query(0,ge=0,le=1_000_000),limite:int=Query(20,ge=1,le=100)):
    return servico(request,response,banco).obter(contratacao_id,deslocamento,limite)
@roteador.post('/contratacoes/{contratacao_id}')
def registrar(contratacao_id:ID,dados:RegistroDespesa,request:Request,response:Response,banco:Banco):
    return servico(request,response,banco).registrar(contratacao_id,dados)
@roteador.post('/contratacoes/{contratacao_id}/despesas/{despesa_id}/estornar')
def estornar(contratacao_id:ID,despesa_id:ID,dados:EstornoDespesa,request:Request,response:Response,banco:Banco):
    return servico(request,response,banco).estornar(contratacao_id,despesa_id,dados)


def conferir_filtros_relatorio(request, csv=False):
    permitidos = {'inicio', 'fim'} | ({'versao'} if csv else set())
    if any(k not in permitidos or len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, detail='filtro_relatorio_resultado_invalido')

@roteador.get('/resultado/relatorio', response_model=RelatorioResultado)
def relatorio_resultado(request:Request,response:Response,banco:Banco,
        inicio:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),fim:date=Query(ge=date(1900,1,1),le=date(9999,12,30))):
    s = servico(request,response,banco)
    conferir_filtros_relatorio(request)
    return ServicoRelatorioResultado(s).obter(inicio,fim)

@roteador.get('/resultado/csv')
def csv_resultado(request:Request,response:Response,banco:Banco,
        inicio:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),fim:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),
        versao:str=Query(pattern=r'^[0-9a-f]{64}$')):
    s = servico(request,response,banco)
    conferir_filtros_relatorio(request,csv=True)
    conteudo, atual = ServicoRelatorioResultado(s).exportar(inicio,fim,versao)
    return Response(conteudo,media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="MEC_SERVICOS_RESULTADO_ADMIN_{inicio}_{fim}.csv"',
        'Cache-Control':'no-store','X-MEC-Despesas-Contexto':s.contexto(),'X-MEC-Relatorio-Versao':atual})


@roteador.get('/resultado/pdf')
def pdf_resultado(request:Request,response:Response,banco:Banco,
        inicio:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),fim:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),
        versao:str=Query(pattern=r'^[0-9a-f]{64}$')):
    from hmac import compare_digest
    from backend.app.services.pdf_resultado import gerar_pdf_resultado
    s = servico(request,response,banco)
    conferir_filtros_relatorio(request,csv=True)
    r = ServicoRelatorioResultado(s).obter(inicio,fim)
    if not compare_digest(versao,r['versao']):raise HTTPException(409,detail='relatorio_resultado_alterado_atualize')
    return Response(gerar_pdf_resultado(r),media_type='application/pdf',headers={
        'Content-Disposition':f'attachment; filename="MEC_SERVICOS_RESULTADO_ADMIN_{inicio}_{fim}.pdf"',
        'Cache-Control':'no-store','X-MEC-Despesas-Contexto':s.contexto(),'X-MEC-Relatorio-Versao':r['versao']})


def conferir_filtros_analise(request, exportacao=False):
    permitidos = {'inicio', 'fim', 'empresa_cliente_id', 'empresa_fornecedora_id', 'liquidacao'} | ({'versao'} if exportacao else set())
    if any(k not in permitidos or len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        raise HTTPException(422, detail='filtro_analise_resultado_invalido')

@roteador.get('/resultado/analise', response_model=AnaliseResultado)
def analise_resultado(request:Request,response:Response,banco:Banco,
        inicio:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),fim:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),
        empresa_cliente_id:int|None=Query(None,gt=0,le=9_999_999_999_999),
        empresa_fornecedora_id:int|None=Query(None,gt=0,le=9_999_999_999_999),
        liquidacao:Literal['todas','liquidadas','aguardando']=Query('todas')):
    s = servico(request,response,banco)
    conferir_filtros_analise(request)
    response.headers['X-MEC-Despesas-Contexto'] = s.contexto()
    return ServicoAnaliseResultado(s).obter(inicio,fim,empresa_cliente_id,empresa_fornecedora_id,liquidacao)

@roteador.get('/resultado/analise/csv')
def csv_analise_resultado(request:Request,response:Response,banco:Banco,
        inicio:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),fim:date=Query(ge=date(1900,1,1),le=date(9999,12,30)),
        empresa_cliente_id:int|None=Query(None,gt=0,le=9_999_999_999_999),
        empresa_fornecedora_id:int|None=Query(None,gt=0,le=9_999_999_999_999),
        liquidacao:Literal['todas','liquidadas','aguardando']=Query('todas'),versao:str=Query(pattern=r'^[0-9a-f]{64}$')):
    s = servico(request,response,banco)
    conferir_filtros_analise(request,exportacao=True)
    conteudo, atual = ServicoAnaliseResultado(s).exportar(inicio,fim,versao,
        empresa_cliente_id=empresa_cliente_id,empresa_fornecedora_id=empresa_fornecedora_id,liquidacao=liquidacao)
    return Response(conteudo,media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="MEC_SERVICOS_ANALISE_RESULTADO_{inicio}_{fim}.csv"',
        'Cache-Control':'no-store','X-MEC-Despesas-Contexto':s.contexto(),'X-MEC-Relatorio-Versao':atual})


MES=Annotated[str,Path(pattern=r'^(?:19\d{2}|[2-9]\d{3})-(?:0[1-9]|1[0-2])$')]

def metas_servico(request,response,banco):
    s=servico(request,response,banco)
    response.headers['X-MEC-Despesas-Contexto']=s.contexto()
    return ServicoMetasResultado(s)

def filtros_metas(request,permitidos):
    if any(k not in permitidos or len(request.query_params.getlist(k))!=1 for k in request.query_params):
        raise HTTPException(422,detail='filtro_metas_resultado_invalido')

def conferir_mes(mes):
    if int(mes[:4])>9998:raise HTTPException(422,detail='ano_da_meta_invalido')

@roteador.get('/metas',response_model=ComparacaoMetas)
def comparar_metas(request:Request,response:Response,banco:Banco,ano:int=Query(ge=1900,le=9998)):
    s=metas_servico(request,response,banco)
    filtros_metas(request,{'ano'})
    return s.comparar(ano)

@roteador.get('/metas/csv')
def csv_metas(request:Request,response:Response,banco:Banco,ano:int=Query(ge=1900,le=9998),versao:str=Query(pattern=r'^[0-9a-f]{64}$')):
    s=metas_servico(request,response,banco)
    filtros_metas(request,{'ano','versao'})
    conteudo,atual=s.exportar(ano,versao)
    return Response(conteudo,media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="MEC_SERVICOS_METAS_RESULTADO_{ano}.csv"',
        'Cache-Control':'no-store','X-MEC-Despesas-Contexto':s.despesas.contexto(),'X-MEC-Relatorio-Versao':atual})

@roteador.get('/metas/pdf')
def pdf_metas(request:Request,response:Response,banco:Banco,ano:int=Query(ge=1900,le=9998),versao:str=Query(pattern=r'^[0-9a-f]{64}$')):
    from hmac import compare_digest
    from backend.app.services.pdf_metas_resultado import gerar_pdf_metas
    s=metas_servico(request,response,banco)
    filtros_metas(request,{'ano','versao'})
    r=s.comparar(ano)
    if not compare_digest(versao,r['versao']):raise HTTPException(409,detail='metas_ou_resultado_alterados_atualize')
    return Response(gerar_pdf_metas(r),media_type='application/pdf',headers={
        'Content-Disposition':f'attachment; filename="MEC_SERVICOS_METAS_RESULTADO_{ano}.pdf"',
        'Cache-Control':'no-store','X-MEC-Despesas-Contexto':s.despesas.contexto(),'X-MEC-Relatorio-Versao':r['versao']})

@roteador.get('/metas/{mes}',response_model=DetalheMeta)
def detalhe_meta(mes:MES,request:Request,response:Response,banco:Banco,deslocamento:int=Query(0,ge=0,le=1_000_000),limite:int=Query(20,ge=1,le=100)):
    s=metas_servico(request,response,banco);conferir_mes(mes)
    filtros_metas(request,{'deslocamento','limite'})
    return s.obter(mes,deslocamento,limite)

@roteador.post('/metas/{mes}')
def registrar_meta(mes:MES,dados:OperacaoMeta,request:Request,response:Response,banco:Banco):
    s=metas_servico(request,response,banco);conferir_mes(mes)
    filtros_metas(request,set())
    return s.operar(mes,dados)
