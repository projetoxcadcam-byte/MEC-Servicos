"""Avisos na mesma transação dos registros; sem copiar textos livres ou contatos.

Os eventos de inserção usam a conexão do próprio flush. Um rollback do negócio
também desfaz seus avisos. Leitura e instalação nunca percorrem eventos antigos.
"""
from __future__ import annotations

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import object_session

from backend.app.models.avaliacao import AvaliacaoOficina
from backend.app.models.avaliacao_perfil import AutoriaAvaliacaoCliente, AvaliacaoAdministrativa
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.documentacao_cotacao import EventoArquivoCotacao, LiberacaoArquivoCotacao
from backend.app.models.empresa import Empresa
from backend.app.models.etapa_producao import EtapaProducao
from backend.app.models.financeiro_administrativo import EventoFinanceiro
from backend.app.models.intermediacao import CicloIntermediacao, EventoIntermediacao
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.notificacao import NotificacaoPerfil
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.services.notificacoes import agora

ETAPAS = {"aguardando_material": "Aguardando material", "em_usinagem": "Em usinagem",
          "em_solda_dobra": "Em solda/dobra", "em_acabamento": "Em acabamento", "pronto_para_envio": "Pronto para coleta"}
LOGISTICA = {
    "receber_material": ("Material recebido", "A administração recebeu o material do serviço."),
    "encaminhar_material": ("Material encaminhado", "A administração encaminhou o material para produção."),
    "solicitar_coleta": ("Coleta solicitada", "A administração solicitou a coleta das peças."),
    "receber_pecas": ("Peças recolhidas e recebidas", "A administração recolheu e registrou o recebimento das peças."),
    "iniciar_avaliacao": ("Avaliação iniciada", "A administração iniciou a avaliação das peças."),
    "aprovar_pecas": ("Peças aprovadas", "A administração aprovou as peças para entrega ao cliente."),
    "solicitar_retrabalho": ("Retrabalho solicitado", "A administração solicitou retrabalho das peças."),
    "encaminhar_retrabalho": ("Peças encaminhadas para retrabalho", "A administração encaminhou as peças para retrabalho."),
    "entregar_cliente": ("Entrega concluída", "A administração concluiu a entrega ao cliente e a ordem de serviço."),
    "cancelar": ("Serviço cancelado", "A administração cancelou o ciclo e a ordem de serviço."),
}
FINANCEIRO = {
    "recebimento": ("Pagamento registrado", "A administração registrou um recebimento do cliente.", {"cliente"}),
    "estornar_recebimento": ("Recebimento estornado", "A administração estornou um recebimento do cliente.", {"cliente"}),
    "repasse": ("Repasse registrado", "A administração registrou um repasse ao fornecedor.", {"fornecedor"}),
    "estornar_repasse": ("Repasse estornado", "A administração estornou um repasse ao fornecedor.", {"fornecedor"}),
    "encerrar": ("Contratação encerrada", "A administração encerrou o financeiro e a contratação.", {"cliente", "fornecedor"}),
    "reabrir": ("Financeiro reaberto", "A administração reabriu o financeiro e a contratação.", {"cliente", "fornecedor"}),
}


def _usuario(alvo):
    sessao = object_session(alvo)
    usuario = sessao.info.get("mec_usuario_notificacoes") if sessao else None
    return usuario if usuario and usuario.usuario_id > 0 else None


def _linha(conexao, modelo, identificador):
    return conexao.execute(select(modelo.__table__).where(modelo.id == identificador)).mappings().first()


def _destinos(dados, perfis=("cliente", "fornecedor", "admin")):
    campos = {"cliente": "empresa_cliente_id", "fornecedor": "empresa_fornecedora_id"}
    return [(p, 0 if p == "admin" else dados[campos[p]]) for p in perfis]


def _endereco(perfil, modulo, dados):
    raiz = "/" + ("admin" if perfil == "admin" else perfil)
    if modulo in {"producao", "entregas", "ordens-servico"}:
        # A produção administrativa é acompanhada pelo ciclo, não pela página genérica antiga.
        if perfil == "admin" and modulo == "producao":
            modulo = "entregas"
        if perfil != "admin" and modulo == "ordens-servico":
            modulo = "producao"
        return f"{raiz}/{modulo}?ordem={dados['ordem_servico_id']}"
    if modulo in {"pagamentos", "avaliacoes"}:
        return f"{raiz}/{modulo}?contratacao={dados['contratacao_id']}"
    if modulo == "arquivos-tecnicos" and perfil != "admin":
        modulo = "cotacoes"
    return f"{raiz}/{modulo}?solicitacao={dados['solicitacao_id']}"


def _emitir(conexao, usuario, chave, assunto, mensagem, modulo, dados, destinos):
    instante = agora()
    linhas = []
    for perfil, empresa in set(destinos):
        # A finalidade é avisar o outro perfil; ações próprias não criam avisos para o autor.
        if perfil == usuario.perfil:
            continue
        linhas.append({"chave_evento": chave, "perfil_destino": perfil, "empresa_destino": empresa,
            "perfil_origem": usuario.perfil, "assunto": assunto, "mensagem": mensagem,
            "destino": _endereco(perfil, modulo, dados), "criada_em": instante,
            "solicitacao_id": dados.get("solicitacao_id"), "contratacao_id": dados.get("contratacao_id"),
            "ordem_servico_id": dados.get("ordem_servico_id")})
    if linhas:
        conexao.execute(NotificacaoPerfil.__table__.insert(), linhas)


def _dados_ordem(ordem):
    return {**ordem, "ordem_servico_id": ordem["id"]}


def notificar_inicio_ordem(banco, ordem_id: int) -> None:
    """O início do portal usa UPDATE condicional; participa da mesma transação."""
    usuario = banco.info.get("mec_usuario_notificacoes")
    if usuario is None or usuario.usuario_id <= 0:
        return
    conexao = banco.connection()
    ordem = _linha(conexao, OrdemServico, ordem_id)
    if ordem is not None:
        dados = _dados_ordem(ordem)
        _emitir(conexao, usuario, f"os-iniciada:{ordem_id}", "Serviço iniciado",
                f"O serviço da OS #{ordem_id} foi iniciado.", "ordens-servico", dados, _destinos(dados))


def _nova_etapa(_, conexao, alvo):
    usuario = _usuario(alvo)
    ordem = _linha(conexao, OrdemServico, alvo.ordem_servico_id) if usuario else None
    if ordem is None or alvo.etapa not in ETAPAS:
        return
    dados = _dados_ordem(ordem)
    _emitir(conexao, usuario, f"producao:{alvo.id}", ETAPAS[alvo.etapa],
            f"A produção da OS #{ordem['id']} foi atualizada para {ETAPAS[alvo.etapa]}.",
            "producao", dados, _destinos(dados))


def _nova_ordem(_, conexao, alvo):
    usuario = _usuario(alvo)
    if usuario is None:
        return
    dados = {nome: getattr(alvo, nome) for nome in ("solicitacao_id", "contratacao_id", "empresa_cliente_id", "empresa_fornecedora_id")}
    dados["ordem_servico_id"] = alvo.id
    _emitir(conexao, usuario, f"os-aberta:{alvo.id}", "Ordem de serviço aberta",
            f"A OS #{alvo.id} foi aberta para a contratação #{alvo.contratacao_id}.", "ordens-servico", dados, _destinos(dados))


def _ordem_alterada(_, conexao, alvo):
    if alvo.status == "em_execucao" and inspect(alvo).attrs.status.history.has_changes():
        banco = object_session(alvo)
        if banco:
            notificar_inicio_ordem(banco, alvo.id)


def _novo_ciclo_evento(_, conexao, alvo):
    usuario = _usuario(alvo)
    if usuario is None or alvo.acao not in LOGISTICA:
        return
    ciclo = _linha(conexao, CicloIntermediacao, alvo.ciclo_id)
    ordem = _linha(conexao, OrdemServico, ciclo["ordem_servico_id"]) if ciclo else None
    if ordem is None:
        return
    dados = _dados_ordem(ordem)
    assunto, texto = LOGISTICA[alvo.acao]
    _emitir(conexao, usuario, f"intermediacao:{alvo.id}", assunto,
            f"OS #{ordem['id']}: {texto}", "entregas", dados, _destinos(dados, ("cliente", "fornecedor")))


def _novo_financeiro(_, conexao, alvo):
    usuario = _usuario(alvo)
    if usuario is None or alvo.acao not in FINANCEIRO:
        return
    contrato = _linha(conexao, ContratacaoServico, alvo.contratacao_id)
    if contrato is None:
        return
    dados = {**contrato, "contratacao_id": contrato["id"]}
    ordem = conexao.execute(select(OrdemServico.id).where(OrdemServico.contratacao_id == contrato["id"])).scalar()
    dados["ordem_servico_id"] = ordem
    assunto, texto, perfis = FINANCEIRO[alvo.acao]
    _emitir(conexao, usuario, f"financeiro:{alvo.id}", assunto,
            f"Contratação #{contrato['id']}: {texto}", "pagamentos", dados, _destinos(dados, perfis))


def _cotacao(_, conexao, alvo, nova=False):
    usuario = _usuario(alvo)
    if usuario is None or (not nova and not inspect(alvo).attrs.status.history.has_changes()):
        return
    estados = {"enviada": ("Nova cotação recebida", "Uma nova cotação foi enviada para esta solicitação."),
               "aceita": ("Cotação aceita", "A administração aceitou a cotação."),
               "recusada": ("Cotação recusada", "A administração recusou a cotação."),
               "expirada": ("Cotação expirada", "A validade da cotação foi encerrada."),
               "cancelada": ("Cotação cancelada", "A cotação foi cancelada.")}
    if alvo.status not in estados:
        return
    solicitacao = _linha(conexao, SolicitacaoServico, alvo.solicitacao_id)
    if solicitacao is None:
        return
    dados = {**solicitacao, "solicitacao_id": alvo.solicitacao_id, "empresa_fornecedora_id": alvo.empresa_fornecedora_id}
    assunto, texto = estados[alvo.status]
    from backend.app.models.formacao_preco import ConfiguracaoPreco, FormacaoPreco
    destinos=_destinos(dados)
    if conexao.execute(select(ConfiguracaoPreco.id).where(ConfiguracaoPreco.id==1)).first():
        publicada=conexao.execute(select(FormacaoPreco.cotacao_id).where(FormacaoPreco.cotacao_id==alvo.id,
            FormacaoPreco.estado.in_(('publicada','aprovada_cliente','revisao_cliente','recusada_cliente','contratada')))).first()
        if not publicada:destinos=[d for d in destinos if d[0]!='cliente']
    # Cada estado só pode ocorrer uma vez na cotação atual. A cotação não é reaberta pelas rotas existentes.
    _emitir(conexao, usuario, f"cotacao:{alvo.id}:{alvo.status}", assunto,
            f"Solicitação #{alvo.solicitacao_id}, cotação #{alvo.id}: {texto}", "cotacoes", dados, destinos)


def _nova_cotacao(mapper, conexao, alvo):
    _cotacao(mapper, conexao, alvo, nova=True)


def _nova_solicitacao(_, conexao, alvo):
    usuario = _usuario(alvo)
    if usuario:
        dados = {"solicitacao_id": alvo.id}
        _emitir(conexao, usuario, f"solicitacao:{alvo.id}", "Nova solicitação",
                f"A solicitação #{alvo.id} foi registrada e aguarda acompanhamento administrativo.", "solicitacoes", dados, [("admin", 0)])


def _novo_arquivo(_, conexao, alvo):
    usuario = _usuario(alvo)
    if usuario:
        _emitir(conexao, usuario, f"arquivo-enviado:{alvo.id}", "Documento aguardando revisão",
                f"Um documento técnico da solicitação #{alvo.solicitacao_id} foi enviado para revisão administrativa.",
                "arquivos-tecnicos", {"solicitacao_id": alvo.solicitacao_id}, [("admin", 0)])


def _documento(_, conexao, alvo):
    usuario = _usuario(alvo)
    arquivo = _linha(conexao, ArquivoTecnico, alvo.arquivo_id) if usuario else None
    solicitacao = _linha(conexao, SolicitacaoServico, arquivo["solicitacao_id"]) if arquivo else None
    if solicitacao is None:
        return
    dados = {**solicitacao, "solicitacao_id": solicitacao["id"]}
    fornecedores = conexao.execute(select(CotacaoFornecedor.empresa_fornecedora_id).where(
        CotacaoFornecedor.solicitacao_id == solicitacao["id"], CotacaoFornecedor.status.in_(("enviada", "aceita")))).scalars().all()
    destinos = [("cliente", solicitacao["empresa_cliente_id"])] + [("fornecedor", i) for i in fornecedores]
    liberado = alvo.acao == "liberar"
    texto = "liberado para cotação" if liberado else "bloqueado para revisão"
    _emitir(conexao, usuario, f"documentacao:{alvo.id}", "Documentação liberada" if liberado else "Documentação em revisão",
            f"Um documento técnico da solicitação #{solicitacao['id']} foi {texto} pela administração.",
            "arquivos-tecnicos", dados, destinos)
    if not liberado or solicitacao["status"] != "aberta":
        return
    aceita = conexao.execute(select(CotacaoFornecedor.id).where(
        CotacaoFornecedor.solicitacao_id == solicitacao["id"], CotacaoFornecedor.status == "aceita")).first()
    # O evento e o estado documental podem ser inseridos em ordens diferentes no flush.
    # A ação liberar já passou por revisão, integridade e trava documental no serviço.
    # Usamos o evento confirmado; ambos serão desfeitos se a transação falhar.
    disponivel = arquivo["ativo"] and arquivo["sha256"] == alvo.sha256
    if aceita or not disponivel:
        return
    ja_cotou = select(CotacaoFornecedor.id).where(CotacaoFornecedor.solicitacao_id == solicitacao["id"],
        CotacaoFornecedor.empresa_fornecedora_id == Empresa.id).correlate(Empresa).exists()
    compativel = select(CapacidadeFornecedor.id).join(MaterialFornecedor,
        MaterialFornecedor.empresa_id == CapacidadeFornecedor.empresa_id).where(
        CapacidadeFornecedor.empresa_id == Empresa.id, CapacidadeFornecedor.processo_id == solicitacao["processo_id"],
        MaterialFornecedor.material_id == solicitacao["material_id"],
        CapacidadeFornecedor.dimensao_x_maxima_mm >= solicitacao["dimensao_x_maxima_mm"],
        CapacidadeFornecedor.dimensao_y_maxima_mm >= solicitacao["dimensao_y_maxima_mm"],
        CapacidadeFornecedor.dimensao_z_maxima_mm >= solicitacao["dimensao_z_maxima_mm"],
        CapacidadeFornecedor.tolerancia_minima_mm <= solicitacao["tolerancia_requerida_mm"]
    ).correlate(Empresa).exists()
    elegiveis = conexao.execute(select(Empresa.id).where(Empresa.tipo_empresa.in_(("fornecedor", "ambos")),
        compativel, ~ja_cotou)).scalars().all()
    _emitir(conexao, usuario, f"documentacao:{alvo.id}", "Documentação disponível para cotação",
            f"A solicitação #{solicitacao['id']} tem documentação liberada e requisitos compatíveis com sua capacidade cadastrada.",
            "solicitacoes", dados, [("fornecedor", i) for i in elegiveis])


def _notificar_avaliacao(conexao, usuario, avaliacao, origem):
    contrato = _linha(conexao, ContratacaoServico, avaliacao["contratacao_id"])
    if contrato is None:
        return
    dados = {**contrato, "contratacao_id": contrato["id"], "ordem_servico_id": avaliacao["ordem_servico_id"]}
    fonte = "cliente" if origem == "cliente" else "administração"
    _emitir(conexao, usuario, f"avaliacao-{origem}:{avaliacao['id']}", "Nova avaliação do serviço",
        f"A {fonte} registrou uma avaliação na contratação #{contrato['id']}, OS #{avaliacao['ordem_servico_id']}.",
        "avaliacoes", dados, _destinos(dados))


def _avaliacao_cliente(_, conexao, alvo):
    usuario = _usuario(alvo)
    avaliacao = _linha(conexao, AvaliacaoOficina, alvo.avaliacao_id) if usuario else None
    if avaliacao is not None:
        _notificar_avaliacao(conexao, usuario, avaliacao, "cliente")


def _avaliacao_admin(_, conexao, alvo):
    usuario = _usuario(alvo)
    if usuario:
        _notificar_avaliacao(conexao, usuario, {"id": alvo.id, "contratacao_id": alvo.contratacao_id,
                            "ordem_servico_id": alvo.ordem_servico_id}, "admin")


def instalar_captura() -> None:
    registros = [(EtapaProducao, "after_insert", _nova_etapa), (OrdemServico, "after_insert", _nova_ordem),
        (OrdemServico, "after_update", _ordem_alterada), (EventoIntermediacao, "after_insert", _novo_ciclo_evento),
        (EventoFinanceiro, "after_insert", _novo_financeiro), (CotacaoFornecedor, "after_insert", _nova_cotacao),
        (CotacaoFornecedor, "after_update", _cotacao), (SolicitacaoServico, "after_insert", _nova_solicitacao),
        (ArquivoTecnico, "after_insert", _novo_arquivo), (EventoArquivoCotacao, "after_insert", _documento),
        (AutoriaAvaliacaoCliente, "after_insert", _avaliacao_cliente), (AvaliacaoAdministrativa, "after_insert", _avaliacao_admin)]
    for modelo, nome, funcao in registros:
        if not event.contains(modelo, nome, funcao):
            event.listen(modelo, nome, funcao)
