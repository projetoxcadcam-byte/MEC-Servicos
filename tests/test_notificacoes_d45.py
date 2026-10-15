"""D45: fluxo real entre perfis, privacidade, atomicidade e leitura individual."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_acesso_d30 import ambiente, modelo_acessos, entrar, BASE, SENHA
from test_comercial_administrativo_d43 import comercial, decidir, corpo as corpo_decisao
from test_contratacao_administrativa_d44 import contratacao_admin, confirmar
from test_documentacao_cotacao_d42 import upload, liberar
from test_financeiro_administrativo_d32 import contas_d32, ambiente_d32, entrar as entrar_fin, iniciar as iniciar_fin, corpo as corpo_fin, registrar as registrar_fin
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.notificacao import LeituraNotificacao, NotificacaoPerfil
from backend.app.models.ordem_servico import OrdemServico
from backend.app.services.notificacoes import ServicoNotificacoes

pytestmark = pytest.mark.acesso_real
NOT = BASE + "/notificacoes"
ADM = BASE + "/administracao/intermediacao/ordens/4"
PRIVADO = "INTERNO-D45 telefone 11999999999 interno@privado.local: controle da administração."


def avisos(http, **params):
    r = http.get(NOT, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def bruto(sessoes):
    with sessoes() as b:
        return [(n.chave_evento, n.perfil_destino, n.empresa_destino, n.assunto, n.mensagem)
                for n in b.scalars(select(NotificacaoPerfil).order_by(NotificacaoPerfil.id))]


def logistica(http, acao, **extras):
    d = http.get(ADM).json()
    r = http.post(ADM + "/eventos", json={"acao": acao, "versao": d["ordem"]["versao"], "registro_interno": PRIVADO, **extras})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def producao(ambiente):
    http, _, _, _ = ambiente
    entrar(http, "admin")
    r = http.post(ADM + "/iniciar", json={"registro_interno": PRIVADO})
    assert r.status_code == 201, r.text
    logistica(http, "receber_material")
    logistica(http, "encaminhar_material", referencia="COMPROVANTE-PRIVADO-D45")
    return ambiente


def etapa(http, valor="em_usinagem", ultima=0):
    entrar(http, "fornecedor")
    r = http.post(BASE + "/portal-fornecedor/producao/4/etapas", json={"empresa_fornecedora_id":4,
        "etapa": valor, "ultima_etapa_id": ultima, "observacoes": PRIVADO})
    assert r.status_code == 201, r.text
    return r.json()


def test_instalacao_e_leituras_nao_reproduzem_historico(ambiente):
    http, _, sessoes, _ = ambiente
    assert bruto(sessoes) == []
    for perfil in ("admin", "cliente", "fornecedor"):
        entrar(http, perfil)
        assert avisos(http)["itens"] == []
        assert http.get(NOT + "/resumo").json() == {"usuario_id": (1 if perfil=="admin" else 2 if perfil=="cliente" else 3), "perfil":perfil, "empresa_id": (None if perfil=="admin" else 2 if perfil=="cliente" else 4), "nao_lidas":0,"ultimo_id":0}
    assert bruto(sessoes) == []


def test_producao_notifica_cliente_e_admin_e_preserva_sigilo(producao):
    http, _, sessoes, _ = producao
    nova = etapa(http)
    alvo = [n for n in bruto(sessoes) if n[0] == f"producao:{nova['id']}"]
    assert {(n[1], n[2]) for n in alvo} == {("cliente",2),("admin",0)}
    for perfil in ("cliente", "admin"):
        entrar(http, perfil); d = avisos(http)
        aviso = next(n for n in d["itens"] if n["assunto"] == "Em usinagem")
        assert aviso["ordem_servico_id"] == 4 and aviso["lida_em"] is None
        assert aviso["destino"] == ("/cliente/producao?ordem=4" if perfil == "cliente" else "/admin/entregas?ordem=4")
        assert aviso["mensagem"].endswith("Em usinagem.")
        assert all(segredo not in str(d) for segredo in ("INTERNO-D45","11999999999","@privado", "Razao Privada", "chave_evento", "empresa_destino"))
    entrar(http, "fornecedor")
    assert not any(n["assunto"] == "Em usinagem" for n in avisos(http)["itens"])


def test_inicio_formal_notifica_uma_vez_e_repeticao_nao_duplica(producao):
    http, _, sessoes, _ = producao; entrar(http, "fornecedor")
    url = BASE + "/portal-fornecedor/ordens-servico/4/iniciar"
    r = http.post(url, json={"empresa_fornecedora_id":4}); assert r.status_code == 200, r.text
    assert r.json()["status"] == "em_execucao"
    assert len([n for n in bruto(sessoes) if n[0] == "os-iniciada:4"]) == 2
    antes = bruto(sessoes)
    assert http.post(url,json={"empresa_fornecedora_id":4}).status_code == 409
    assert bruto(sessoes) == antes


def test_logistica_completa_notifica_os_donos_com_mensagens_publicas(producao):
    http, _, sessoes, _ = producao
    etapa(http, "pronto_para_envio"); entrar(http, "admin")
    logistica(http,"solicitar_coleta")
    logistica(http,"receber_pecas",referencia="REF-COLETA-PRIVADA",quantidade_conferida=5)
    logistica(http,"iniciar_avaliacao")
    logistica(http,"aprovar_pecas",quantidade_conferida=5,parecer_tecnico="PARECER PRIVADO telefone 11999999999")
    logistica(http,"entregar_cliente",quantidade_conferida=5,referencia="REF-ENTREGA-PRIVADA")
    expected={"Coleta solicitada","Peças recolhidas e recebidas","Avaliação iniciada","Peças aprovadas","Entrega concluída"}
    for perfil in ("cliente","fornecedor"):
        entrar(http,perfil); d=avisos(http)
        assert expected.issubset({n["assunto"] for n in d["itens"]})
        assert all(n["ordem_servico_id"] == 4 for n in d["itens"])
        assert all(s not in str(d) for s in ("PRIVADO","PRIVADA","11999999999","@privado"))
        assert next(n for n in d["itens"] if n["assunto"] == "Entrega concluída")["destino"] == f"/{perfil}/entregas?ordem=4"
    entrar(http,"admin")
    assert not expected.intersection({n["assunto"] for n in avisos(http)["itens"]})
    with sessoes() as b: assert b.get(OrdemServico,4).status == "concluida"


def test_leitura_individual_idempotente_e_filtro_nao_lidas(producao):
    http, _, _, _ = producao; etapa(http); entrar(http,"cliente")
    d=avisos(http); n=d["itens"][0]; qtd=d["nao_lidas"]
    r=http.post(NOT+f"/{n['id']}/ler",json={}); assert r.status_code == 200, r.text
    instante=r.json()["lida_em"]; assert instante
    assert http.post(NOT+f"/{n['id']}/ler",json={}).json()["lida_em"] == instante
    assert http.get(NOT+"/resumo").json()["nao_lidas"] == qtd-1
    assert n["id"] not in {m["id"] for m in avisos(http,somente_nao_lidas=True)["itens"]}
    entrar(http,"admin"); assert next(a for a in avisos(http)["itens"] if a["assunto"] == "Em usinagem")["lida_em"] is None


def test_leitura_independente_para_duas_contas_da_mesma_empresa(producao):
    http, acesso, _, _ = producao; etapa(http)
    acesso.criar_usuario("Segundo cliente","cliente2@teste.local","cliente",2,SENHA,deve_alterar_senha=False)
    entrar(http,"cliente"); n=avisos(http)["itens"][0]
    assert http.post(NOT+f"/{n['id']}/ler",json={}).status_code == 200
    entrar(http,"cliente2"); assert next(a for a in avisos(http)["itens"] if a["id"]==n["id"])["lida_em"] is None


@pytest.mark.parametrize("perfil,empresa",[("cliente",6),("fornecedor",8)])
def test_outra_empresa_nao_lista_nem_marca_aviso(producao,perfil,empresa):
    http, acesso, _, _ = producao; etapa(http); entrar(http,"cliente"); n=avisos(http)["itens"][0]
    acesso.criar_usuario("Outra empresa", "outra@teste.local",perfil,empresa,SENHA,deve_alterar_senha=False)
    entrar(http,"outra"); assert avisos(http)["itens"] == []
    assert http.post(NOT+f"/{n['id']}/ler",json={}).status_code == 404
    assert http.post(NOT+"/ler-ate",json={"ate_id":n["id"]}).json()["nao_lidas"] == 0
    entrar(http,"cliente"); assert next(a for a in avisos(http)["itens"] if a["id"]==n["id"])["lida_em"] is None


def test_marcar_todas_preserva_avisos_que_chegaram_depois(producao):
    http, _, _, _ = producao
    n1=etapa(http); entrar(http,"cliente"); corte=avisos(http)["ultimo_id"]
    etapa(http,"em_acabamento",ultima=n1["id"]); entrar(http,"cliente")
    r=http.post(NOT+"/ler-ate",json={"ate_id":corte}); assert r.status_code==200,r.text
    pendentes=avisos(http,somente_nao_lidas=True)
    assert pendentes["nao_lidas"] == 1 and pendentes["itens"][0]["assunto"] == "Em acabamento"


def test_paginacao_sem_duplicar_ou_sumir_quando_chega_aviso(producao):
    http, _, _, _ = producao
    n=etapa(http); entrar(http,"cliente")
    p1=avisos(http,limite=1); antes=p1["proximo_antes_id"]; assert antes
    etapa(http,"em_acabamento",ultima=n["id"]); entrar(http,"cliente")
    ids=[p1["itens"][0]["id"]]
    while antes:
        p=avisos(http,limite=1,antes_id=antes); ids.extend(a["id"] for a in p["itens"]); antes=p["proximo_antes_id"]
    assert len(ids)==len(set(ids))==3
    assert avisos(http)["itens"][0]["id"] not in ids


def test_csrf_sessao_empresa_e_corpo_nao_escolhem_destinatario(producao):
    http, _, _, _ = producao; etapa(http); entrar(http,"cliente"); n=avisos(http)["itens"][0]
    assert http.post(NOT+f"/{n['id']}/ler",json={},headers={"X-MEC-CSRF":"falso"}).status_code==403
    assert http.post(NOT+"/ler-ate",json={"ate_id":n["id"],"usuario_id":1}).status_code==403
    assert http.get(NOT,params={"empresa_id":6}).status_code==403
    assert http.post(NOT+"/ler-ate",json={"ate_id":n["id"],"campo":"extra"}).status_code==422
    http.cookies.clear(); assert http.get(NOT).status_code==401
    assert http.post(NOT+f"/{n['id']}/ler",json={}).status_code==401


@pytest.mark.parametrize("parametros",[{"limite":0},{"limite":51},{"antes_id":0},{"somente_nao_lidas":"valor"}])
def test_validacao_filtros(ambiente,parametros):
    http, _, _, _ = ambiente; entrar(http,"cliente")
    assert http.get(NOT,params=parametros).status_code==422


def test_notificacoes_sobrevivem_a_logout_e_nova_sessao(producao):
    http, _, _, _ = producao; etapa(http); entrar(http,"cliente"); d=avisos(http)
    assert http.post(BASE+"/autenticacao/sair",json={}).status_code==200
    entrar(http,"cliente"); assert avisos(http)==d


def test_erro_de_notificacao_desfaz_producao_e_nenhum_aviso_parcial(producao):
    http, _, sessoes, _ = producao; entrar(http,"fornecedor")
    engine=sessoes.kw["bind"]; anterior=bruto(sessoes)
    def falhar(_,__,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO notificacoes_perfis"):
            raise RuntimeError("Falha de escrita simulada D45")
    event.listen(engine,"before_cursor_execute",falhar)
    try:
        with pytest.raises(RuntimeError,match="Falha de escrita"):
            http.post(BASE+"/portal-fornecedor/producao/4/etapas",json={"empresa_fornecedora_id":4,"etapa":"em_usinagem","ultima_etapa_id":0})
    finally: event.remove(engine,"before_cursor_execute",falhar)
    assert bruto(sessoes)==anterior
    with sessoes() as b: assert b.scalar(select(func.count()).select_from(EtapaProducao))==0


def test_flush_seguido_de_rollback_nao_envia_avisos(producao):
    _, _, sessoes, _ = producao; antes=bruto(sessoes)
    with sessoes() as b:
        b.info["mec_usuario_notificacoes"]=UsuarioAcesso(3,"Fornecedor","privado@local","fornecedor",4,False)
        b.add(EtapaProducao(ordem_servico_id=4,empresa_fornecedora_id=4,etapa="em_usinagem")); b.flush(); b.rollback()
    assert bruto(sessoes)==antes


def test_versao_antiga_e_acao_proibida_nao_notificam(producao):
    http, _, sessoes, _ = producao; etapa(http); anterior=bruto(sessoes)
    assert http.post(BASE+"/portal-fornecedor/producao/4/etapas",json={"empresa_fornecedora_id":4,"etapa":"em_acabamento","ultima_etapa_id":0}).status_code==409
    entrar(http,"cliente")
    assert http.post(ADM+"/eventos",json={"acao":"cancelar","versao":3,"registro_interno":PRIVADO}).status_code==403
    assert bruto(sessoes)==anterior


def test_leitura_concorrente_tem_uma_marca_por_usuario(producao):
    http, _, sessoes, _ = producao; etapa(http); entrar(http,"cliente"); n=avisos(http)["itens"][0]
    usuario=UsuarioAcesso(2,"Cliente","cliente@teste.local","cliente",2,False)
    def ler(_):
        with sessoes() as b: return ServicoNotificacoes(b,usuario).ler(n["id"]).lida_em
    with ThreadPoolExecutor(max_workers=2) as ex: resultados=list(ex.map(ler,range(2)))
    assert resultados[0]==resultados[1]
    with sessoes() as b: assert b.scalar(select(func.count()).select_from(LeituraNotificacao))==1


def test_nova_solicitacao_e_documento_avisam_admin_e_nao_fornecedor(comercial):
    http, _, _, _ = comercial
    entrar(http,"cliente")
    r=http.post(BASE+"/solicitacoes-servico",json={"empresa_cliente_id":2,"processo_id":1,"material_id":1,
        "dimensao_x_maxima_mm":"100","dimensao_y_maxima_mm":"100","dimensao_z_maxima_mm":"100",
        "tolerancia_requerida_mm":"0.02","quantidade":5,"observacoes":PRIVADO})
    assert r.status_code==201,r.text
    sid=r.json()["id"]
    upload(http,nome="CONTATO-PRIVADO-cliente@local.pdf",solicitacao=9)
    entrar(http,"admin"); d=avisos(http)
    assert any(n["assunto"]=="Documento aguardando revisão" and n["solicitacao_id"]==9 for n in d["itens"])
    assert any(n["assunto"]=="Nova solicitação" and n["solicitacao_id"]==sid for n in d["itens"])
    assert "CONTATO-PRIVADO" not in str(d) and "@local.pdf" not in str(d)
    entrar(http,"fornecedor"); assert not any(n["solicitacao_id"]==9 for n in avisos(http)["itens"])


def test_documentacao_e_decisao_comercial_avisam_somente_envolvidos(comercial):
    http, _, sessoes, _ = comercial
    arquivo=upload(http,nome="desenho.pdf",solicitacao=9); liberar(http,arquivo)
    entrar(http,"cliente"); assert any(n["assunto"]=="Documentação liberada" for n in avisos(http)["itens"])
    entrar(http,"admin"); r=decidir(http,corpo_decisao(http)); assert r.status_code==200,r.text
    antes=bruto(sessoes)
    entrar(http,"fornecedor"); assert any(n["assunto"]=="Cotação aceita" for n in avisos(http)["itens"])
    entrar(http,"cliente"); assert any(n["assunto"]=="Cotação aceita" for n in avisos(http)["itens"])
    assert bruto(sessoes)==antes


def test_contratacao_e_os_geram_avisos_uma_vez_sem_flood_de_aguardando(contratacao_admin):
    http, _, sessoes, _ = contratacao_admin
    from test_contratacao_administrativa_d44 import corpo
    dados=corpo(http); r=confirmar(http,dados); assert r.status_code==200,r.text
    res=r.json(); antes=bruto(sessoes)
    assert confirmar(http,dados).json()==res and bruto(sessoes)==antes
    alvo=[n for n in antes if n[0]==f"os-aberta:{res['ordem_servico_id']}"]
    assert {(n[1],n[2]) for n in alvo}=={("cliente",2),("fornecedor",4)}


def test_oportunidade_notifica_apenas_fornecedor_compativel_depois_da_liberacao(ambiente):
    http, _, sessoes, _ = ambiente; entrar(http,"cliente")
    arquivo=upload(http,nome="desenho.pdf",solicitacao=3)
    assert not any(n[1]=="fornecedor" for n in bruto(sessoes))
    entrar(http,"admin"); liberar(http,arquivo)
    alvo=[n for n in bruto(sessoes) if n[3]=="Documentação disponível para cotação"]
    assert len(alvo)==1 and alvo[0][1:3]==("fornecedor",4)
    entrar(http,"fornecedor")
    n=next(a for a in avisos(http)["itens"] if a["assunto"]=="Documentação disponível para cotação")
    assert n["destino"]=="/fornecedor/solicitacoes?solicitacao=3"
    r=http.get(BASE+"/portal-fornecedor/oportunidades",params={"empresa_fornecedora_id":4,"solicitacao_id":3})
    assert r.status_code==200,r.text
    assert [a["id"] for a in r.json()["itens"]]==[3]
    assert http.get(BASE+"/portal-fornecedor/oportunidades",params={"empresa_fornecedora_id":4,"solicitacao_id":2}).json()["itens"]==[]


def test_nova_cotacao_avisa_cliente_e_admin_sem_notificar_fornecedor(ambiente):
    http, _, sessoes, _ = ambiente; entrar(http,"cliente"); arquivo=upload(http,nome="desenho.pdf",solicitacao=3)
    entrar(http,"admin"); liberar(http,arquivo); entrar(http,"fornecedor")
    r=http.post(BASE+"/portal-fornecedor/solicitacoes/3/cotacoes",json={"empresa_fornecedora_id":4,"valor_total":"1500.00",
        "prazo_dias":7,"validade_dias":10,"observacoes":PRIVADO})
    assert r.status_code==201,r.text
    alvo=[n for n in bruto(sessoes) if n[0]==f"cotacao:{r.json()['id']}:enviada"]
    assert {(n[1],n[2]) for n in alvo}=={("cliente",2),("admin",0)}


def test_financeiro_direciona_recebimentos_repasses_estornos_e_fechamento(ambiente_d32):
    http, sessoes, _ = ambiente_d32; entrar_fin(http); iniciar_fin(http)
    passos=[("recebimento",1),("repasse",2),("estornar_repasse",3),("estornar_recebimento",4),
            ("recebimento",5),("repasse",6),("encerrar",7)]
    for acao,versao in passos:
        dados=corpo_fin(acao,versao); r=registrar_fin(http,dados)
        if acao=="recebimento" and versao==1:
            antes=bruto(sessoes); repetido=registrar_fin(http,dados)
            assert repetido.json()["recebimentos"][0]["id"]==r.json()["recebimentos"][0]["id"] and bruto(sessoes)==antes
    expected_cliente={"Pagamento registrado","Recebimento estornado","Contratação encerrada"}
    expected_fornecedor={"Repasse registrado","Repasse estornado","Contratação encerrada"}
    for perfil,expected,proibidos in (("cliente",expected_cliente,{"Repasse registrado","Repasse estornado"}),
                                     ("fornecedor",expected_fornecedor,{"Pagamento registrado","Recebimento estornado"})):
        entrar_fin(http,perfil); d=avisos(http)
        assert expected=={a["assunto"] for a in d["itens"]}
        assert not proibidos.intersection(a["assunto"] for a in d["itens"])
        assert all(a["destino"]==f"/{perfil}/pagamentos?contratacao=1" for a in d["itens"])
        assert all(s not in str(d) for s in ("interno@", "PROVA-", "ESTORNO-", "registro_interno"))
    entrar_fin(http,"admin"); assert avisos(http)["itens"]==[]


@pytest.mark.parametrize("metodo,caminho,corpo",[("GET","/resumo",None),("GET","",None),("POST","/ler-ate",{"ate_id":999999}),("POST","/1/ler",{})])
def test_aba_com_contexto_anterior_nao_lista_nem_marca_novas_contas(producao,metodo,caminho,corpo):
    http, _, sessoes, _ = producao; etapa(http); entrar(http,"fornecedor")
    with sessoes() as b: antes=b.scalar(select(func.count()).select_from(LeituraNotificacao))
    r=http.request(metodo,NOT+caminho,json=corpo,headers={"X-MEC-NOTIFICACOES-CONTEXTO":"2:cliente:2"})
    assert r.status_code==409 and r.json()=={"detail":"contexto_notificacoes_alterado"}
    with sessoes() as b: assert b.scalar(select(func.count()).select_from(LeituraNotificacao))==antes
