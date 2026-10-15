"""D42: documentação liberada, sessão real, arquivos físicos e histórico."""
from pathlib import Path
from uuid import uuid4
import hashlib
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select

from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.documentacao_cotacao import EventoArquivoCotacao, LiberacaoArquivoCotacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.schemas.documentacao_cotacao import RegistroDocumentacao

pytestmark = pytest.mark.acesso_real
DOC = BASE + "/administracao/documentacao-cotacao"
PORTAL = BASE + "/portal-fornecedor"

def upload(http, nome="contato-cliente@privado.local.pdf", conteudo=b"%PDF-1.4\nDesenho neutro D42\n%%EOF", solicitacao=3):
    entrar(http,"cliente")
    r=http.post(BASE+f"/solicitacoes-servico/{solicitacao}/arquivos-tecnicos",files={"file":(nome,conteudo,"application/pdf")})
    assert r.status_code==201,r.text
    return r.json()

def corpo(a, acao="liberar", versao=0, **kw):
    return {"acao":acao,"versao":versao,"sha256":a["sha256"],"registro_interno":"Revisão manual concluída em teste isolado.",
            "revisado_sem_contatos":True,"chave_operacao":str(uuid4()),**kw}

def liberar(http,a,**kw):
    entrar(http,"admin")
    r=http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,**kw))
    assert r.status_code==200,r.text
    return r.json()

def oportunidades(http, **kw):
    entrar(http,"fornecedor")
    r=http.get(PORTAL+"/oportunidades",params={"empresa_fornecedora_id":4,**kw})
    assert r.status_code==200,r.text
    return r.json()

def cotar(http, solicitacao=3, legado=False):
    entrar(http,"admin" if legado else "fornecedor")
    url=BASE+f"/solicitacoes-servico/{solicitacao}/cotacoes" if legado else PORTAL+f"/solicitacoes/{solicitacao}/cotacoes"
    return http.post(url,json={"empresa_fornecedora_id":4,"valor_total":"1000.00","prazo_dias":5,"validade_dias":7})

def numero_eventos(sessoes):
    with sessoes() as b:return len(b.scalars(select(EventoArquivoCotacao)).all())

def test_sem_arquivo_e_arquivo_so_enviado_nao_publicam_nem_aceitam_cotacao(ambiente):
    http,_,sessoes,_=ambiente
    assert oportunidades(http)["total"]==0
    for legado in (False,True):
        r=cotar(http,legado=legado);assert r.status_code==409 and r.json()["detail"]=="solicitacao_sem_arquivo_liberado_para_cotacao"
    upload(http)
    assert oportunidades(http)["total"]==0
    assert cotar(http).status_code==409
    with sessoes() as b:assert b.scalar(select(CotacaoFornecedor.id).where(CotacaoFornecedor.solicitacao_id==3)) is None
    assert numero_eventos(sessoes)==0

def test_liberacao_publica_download_neutro_e_envio_real(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http)
    d=liberar(http,a);assert d["liberado"] and d["versao"]==1
    p=oportunidades(http);assert p["total"]==1 and p["itens"][0]["id"]==3
    assert p["itens"][0]["cliente_razao_social"]=="Cliente C-0002" and p["itens"][0]["observacoes"] is None
    r=http.get(PORTAL+"/solicitacoes/3/arquivos",params={"empresa_fornecedora_id":4})
    assert r.status_code==200 and len(r.json())==1
    assert r.json()[0]["nome_original"]==f'Arquivo tecnico {a["id"]}.pdf'
    assert "privado" not in r.text and "caminho" not in r.text and "registro_interno" not in r.text
    r=http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={"empresa_fornecedora_id":4})
    assert r.status_code==200 and r.content.startswith(b"%PDF")
    assert "privado" not in r.headers["content-disposition"] and r.headers["cache-control"]=="no-store"
    assert r.headers["x-content-type-options"]=="nosniff"
    r=cotar(http);assert r.status_code==201 and r.json()["valor_total"]=="1000.00"
    assert oportunidades(http)["total"]==0
    with sessoes() as b:assert len(b.scalars(select(CotacaoFornecedor).where(CotacaoFornecedor.solicitacao_id==3)).all())==1

@pytest.mark.parametrize("perfil",["cliente","fornecedor"])
def test_revisao_e_historico_exclusivos_da_administracao(ambiente,perfil):
    http,_,sessoes,_=ambiente;a=upload(http);entrar(http,perfil)
    assert http.get(DOC).status_code==403
    assert http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a)).status_code==403
    assert numero_eventos(sessoes)==0

@pytest.mark.parametrize("alteracao",[{"revisado_sem_contatos":False},{"registro_interno":"   "},{"usuario_admin_id":999},{"acao":"inventada"},{"sha256":"errado"},{"versao":-1}])
def test_validacao_da_revisao_nao_grava(ambiente,alteracao):
    http,_,sessoes,_=ambiente;a=upload(http);entrar(http,"admin")
    assert http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,**alteracao)).status_code==422
    assert numero_eventos(sessoes)==0 and oportunidades(http)["total"]==0

def test_csrf_e_versao_sha_impedem_revisao_antiga(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http);entrar(http,"admin")
    r=http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a),headers={"X-MEC-CSRF":"falso"})
    assert r.status_code==403 and numero_eventos(sessoes)==0
    liberar(http,a)
    entrar(http,"admin")
    assert http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,acao="bloquear")).status_code==409
    assert http.post(DOC+f'/arquivos/{a["id"]}/eventos',json=corpo(a,acao="bloquear",versao=1,sha256="f"*64)).status_code==409
    assert numero_eventos(sessoes)==1

def test_idempotencia_e_bloqueio_preservam_eventos(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http);entrar(http,"admin")
    dados=corpo(a);url=DOC+f'/arquivos/{a["id"]}/eventos'
    assert http.post(url,json=dados).status_code==200
    assert http.post(url,json=dados).status_code==200 and numero_eventos(sessoes)==1
    assert http.post(url,json={**dados,"registro_interno":"outro registro"}).status_code==409
    bloqueio=http.post(url,json=corpo(a,acao="bloquear",versao=1));assert bloqueio.status_code==200 and not bloqueio.json()["liberado"]
    assert http.post(url,json=dados).status_code==200 and numero_eventos(sessoes)==2
    assert oportunidades(http)["total"]==0
    assert cotar(http).status_code==409

def test_desvincular_ultimo_arquivo_retira_oportunidade_e_recusa_envio_antigo(ambiente):
    http,_,_,_=ambiente;a=upload(http);liberar(http,a);assert oportunidades(http)["total"]==1
    entrar(http,"cliente");assert http.delete(BASE+f'/arquivos-tecnicos/{a["id"]}').status_code==204
    assert oportunidades(http)["total"]==0 and cotar(http).status_code==409
    assert http.get(PORTAL+f'/arquivos/{a["id"]}/download',params={"empresa_fornecedora_id":4}).status_code==403

def test_dois_arquivos_nao_multiplicam_oportunidade_e_so_liberados_sao_visiveis(ambiente):
    http,_,_,_=ambiente;a=upload(http);b=upload(http,nome="segunda-versao.pdf");liberar(http,a)
    assert oportunidades(http)["total"]==1
    lista=http.get(PORTAL+"/solicitacoes/3/arquivos",params={"empresa_fornecedora_id":4}).json()
    assert [i["id"] for i in lista]==[a["id"]]
    assert http.get(PORTAL+f'/arquivos/{b["id"]}/download',params={"empresa_fornecedora_id":4}).status_code==403
    liberar(http,b);assert oportunidades(http)["total"]==1
    liberar(http,a,acao="bloquear",versao=1);assert oportunidades(http)["total"]==1
    liberar(http,b,acao="bloquear",versao=1);assert oportunidades(http)["total"]==0

@pytest.mark.parametrize("dano",["ausente","bytes","tamanho","fora","vazio"])
def test_arquivo_integro_e_obrigatorio_tambem_apos_revisao(ambiente,tmp_path,dano):
    http,_,sessoes,_=ambiente;a=upload(http);liberar(http,a)
    with sessoes() as b:
        item=b.get(ArquivoTecnico,a["id"]);p=Path(item.caminho_arquivo)
        if dano=="ausente":p.unlink()
        elif dano=="bytes":p.write_bytes(b"X"*item.tamanho_bytes)
        elif dano=="tamanho":p.write_bytes(b"corto")
        elif dano=="fora":
            externo=tmp_path/"externo.pdf";externo.write_bytes(p.read_bytes());item.caminho_arquivo=str(externo)
        else:
            p.write_bytes(b"");item.tamanho_bytes=0;item.sha256=hashlib.sha256(b"").hexdigest()
        b.commit()
    assert oportunidades(http)["total"]==0 and cotar(http).status_code==409
    entrar(http,"admin")
    d=http.get(DOC,params={"solicitacao_id":3}).json()["itens"][0]["arquivos"][0]
    assert not d["liberado"] and not d["conteudo_valido"]

def test_cotacao_anterior_sem_documentacao_permanece_no_historico(ambiente):
    http,_,sessoes,_=ambiente
    with sessoes() as b:
        b.add(CotacaoFornecedor(id=7,solicitacao_id=3,empresa_fornecedora_id=4,valor_total="1000.00",prazo_dias=5,validade_dias=7,status="enviada"));b.commit()
    p=oportunidades(http);assert p["total"]==0
    r=http.get(PORTAL+"/cotacoes",params={"empresa_fornecedora_id":4})
    assert any(c["id"]==7 and c["valor_total"]=="1000.00" and c["status"]=="enviada" for c in r.json()["itens"])
    a=upload(http);liberar(http,a);assert oportunidades(http)["total"]==0
    assert cotar(http).status_code==409

def test_vinculo_empresa_e_compatibilidade_no_download(ambiente):
    http,acesso,sessoes,_=ambiente;a=upload(http);liberar(http,a);entrar(http,"fornecedor")
    url=PORTAL+f'/arquivos/{a["id"]}/download'
    for params in ({},{"empresa_fornecedora_id":8},[("empresa_fornecedora_id",4),("empresa_fornecedora_id",4)]):
        assert http.get(url,params=params).status_code==403
    acesso.criar_usuario("Outro fornecedor","outro@d42.local","fornecedor",8,"Senha-teste-valida-D42!",deve_alterar_senha=False)
    r=http.post(BASE+"/autenticacao/entrar",json={"email":"outro@d42.local","senha":"Senha-teste-valida-D42!"});assert r.status_code==200
    assert http.get(url,params={"empresa_fornecedora_id":8}).status_code==403
    assert numero_eventos(sessoes)==1

def test_paginacao_total_nao_depende_de_arquivos_duplicados(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http);liberar(http,a)
    with sessoes() as b:
        original=b.get(SolicitacaoServico,3);arquivo=b.get(ArquivoTecnico,a["id"])
        campos={n:getattr(original,n) for n in ("empresa_cliente_id","processo_id","material_id","dimensao_x_maxima_mm","dimensao_y_maxima_mm","dimensao_z_maxima_mm","tolerancia_requerida_mm","quantidade")}
        for n in range(10,35):
            b.add(SolicitacaoServico(id=n,**campos));b.flush()
            f=ArquivoTecnico(solicitacao_id=n,nome_original="neutro.pdf",extensao=".pdf",tamanho_bytes=arquivo.tamanho_bytes,sha256=arquivo.sha256,caminho_arquivo=arquivo.caminho_arquivo,ativo=True)
            b.add(f);b.flush()
            ServicoDocumentacaoCotacao(b).registrar(f.id,RegistroDocumentacao(**corpo({"sha256":f.sha256})),UsuarioAcesso(1,"Administrador QA","admin@qa.local","admin",None,False))
    p=oportunidades(http,limite=20);q=oportunidades(http,limite=20,deslocamento=20)
    assert p["total"]==q["total"]==26 and len(p["itens"])==20 and len(q["itens"])==6
    assert set(i["id"] for i in p["itens"]).isdisjoint(i["id"] for i in q["itens"])
    entrar(http,"admin");p=http.get(DOC,params={"limite":1}).json();assert p["total"]==29 and len(p["itens"])==1

def test_duas_revisoes_concorrentes_nao_duplicam_evento(ambiente):
    http,_,sessoes,_=ambiente;a=upload(http)
    def revisar(_):
        with sessoes() as b:
            try:
                ServicoDocumentacaoCotacao(b).registrar(a["id"],RegistroDocumentacao(**corpo(a)),UsuarioAcesso(1,"Administrador QA","admin@qa.local","admin",None,False))
                return 200
            except Exception as e:
                assert getattr(e,"status_code",None)==409,str(e)
                return 409
    with ThreadPoolExecutor(max_workers=2) as pool:resultados=list(pool.map(revisar,range(2)))
    assert sorted(resultados)==[200,409] and numero_eventos(sessoes)==1
