from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from fastapi import HTTPException
from sqlalchemy import and_, case, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.models.comercial_admin import EventoDecisaoCotacaoAdmin
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.cotacao import CotacaoFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.material import Material
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.comercial_admin import (
    CotacaoComercial, DecisaoComercial, DetalheSolicitacaoComercial, EventoDecisaoComercial,
    PaginaCotacoesComerciais, PaginaSolicitacoesComerciais, ResultadoDecisaoComercial, SolicitacaoComercial,
)
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao, travar_documentacao


def agora_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sem_fuso(valor: datetime) -> datetime:
    return valor if valor.tzinfo is None else valor.astimezone(timezone.utc).replace(tzinfo=None)


def data_utc(valor: datetime | None) -> str | None:
    return sem_fuso(valor).isoformat(timespec="microseconds") + "Z" if valor else None


def situacao(cotacao: CotacaoFornecedor, agora: datetime) -> str:
    if cotacao.status == "enviada" and agora >= sem_fuso(cotacao.criada_em) + timedelta(days=cotacao.validade_dias):
        return "expirada"
    return cotacao.status


class ServicoComercialAdmin:
    def __init__(self, banco: Session):
        self.banco = banco
        from backend.app.models.formacao_preco import ConfiguracaoPreco
        self.configuracao_preco=banco.get(ConfiguracaoPreco,1)

    def _leitura_consistente(self):
        conexao = self.banco.connection()
        if conexao.dialect.name == "sqlite" and not conexao.connection.driver_connection.in_transaction:
            self.banco.execute(text("BEGIN"))

    def _resumo(self, s: SolicitacaoServico, cliente: str, processo: str, material: str,
                total: int, aceitas: int, arquivos: int, contratacao_id: int | None) -> SolicitacaoComercial:
        return SolicitacaoComercial(id=s.id, empresa_cliente_id=s.empresa_cliente_id, cliente=cliente,
            processo=processo, material=material, dimensao_x_maxima_mm=s.dimensao_x_maxima_mm,
            dimensao_y_maxima_mm=s.dimensao_y_maxima_mm, dimensao_z_maxima_mm=s.dimensao_z_maxima_mm,
            tolerancia_requerida_mm=s.tolerancia_requerida_mm, quantidade=s.quantidade,
            observacoes=s.observacoes, status=s.status, criada_em=data_utc(s.criada_em),
            cotacoes_total=total, cotacoes_aceitas=aceitas, arquivos_ativos=arquivos, contratacao_id=contratacao_id)

    @staticmethod
    def _contrato_id():
        return select(ContratacaoServico.id).where(ContratacaoServico.solicitacao_id == SolicitacaoServico.id).correlate(SolicitacaoServico).scalar_subquery()

    def listar_solicitacoes(self, solicitacao_id: int | None, status: str | None, deslocamento: int, limite: int):
        self._leitura_consistente()
        filtros = []
        if solicitacao_id is not None: filtros.append(SolicitacaoServico.id == solicitacao_id)
        if status is not None: filtros.append(SolicitacaoServico.status == status)
        total = self.banco.scalar(select(func.count()).select_from(SolicitacaoServico).where(*filtros)) or 0
        contagem = select(func.count(CotacaoFornecedor.id)).where(CotacaoFornecedor.solicitacao_id == SolicitacaoServico.id).correlate(SolicitacaoServico)
        arquivos = select(func.count(ArquivoTecnico.id)).where(ArquivoTecnico.solicitacao_id == SolicitacaoServico.id, ArquivoTecnico.ativo.is_(True)).correlate(SolicitacaoServico)
        consulta = select(SolicitacaoServico, Empresa.razao_social, ProcessoFabricacao.nome, Material.nome,
            contagem.scalar_subquery(), contagem.where(CotacaoFornecedor.status == "aceita").scalar_subquery(),
            arquivos.scalar_subquery(), self._contrato_id()).join(Empresa, Empresa.id == SolicitacaoServico.empresa_cliente_id)
        consulta = consulta.join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id).join(Material, Material.id == SolicitacaoServico.material_id)
        linhas = self.banco.execute(consulta.where(*filtros).order_by(SolicitacaoServico.id.desc()).offset(deslocamento).limit(limite)).all()
        return PaginaSolicitacoesComerciais(itens=[self._resumo(*linha) for linha in linhas], total=total, deslocamento=deslocamento, limite=limite)

    def _cotacao(self, q, s, cliente, fornecedor, processo, material, contratacao_id, tem_aceita, agora):
        status = situacao(q, agora)
        from backend.app.models.formacao_preco import FormacaoPreco
        from backend.app.services.precos_portais import ativa
        p=self.banco.get(FormacaoPreco,q.id)
        permite=self.configuracao_preco is None or bool(p and p.estado=='aprovada_cliente')
        return CotacaoComercial(preco_cliente_estado=p.estado if p else None,pode_aceitar=permite,id=q.id, solicitacao_id=s.id, empresa_cliente_id=s.empresa_cliente_id,
            cliente=cliente, empresa_fornecedora_id=q.empresa_fornecedora_id, fornecedor=fornecedor,
            processo=processo, material=material, valor_total=q.valor_total, prazo_dias=q.prazo_dias,
            validade_dias=q.validade_dias, observacoes=q.observacoes, status=status, status_registrado=q.status,
            criada_em=data_utc(q.criada_em), vence_em=data_utc(sem_fuso(q.criada_em) + timedelta(days=q.validade_dias)),
            encerrada_em=data_utc(q.encerrada_em), contratacao_id=contratacao_id,
            pode_decidir=s.status == "aberta" and status == "enviada" and contratacao_id is None and not tem_aceita)

    def listar_cotacoes(self, solicitacao_id: int | None, cotacao_id: int | None, status: str | None, deslocamento: int, limite: int):
        self._leitura_consistente()
        agora = agora_utc()
        efetivo = case((and_(CotacaoFornecedor.status == "enviada",
            func.julianday(CotacaoFornecedor.criada_em) + CotacaoFornecedor.validade_dias <= func.julianday(agora.isoformat())), "expirada"), else_=CotacaoFornecedor.status)
        filtros = []
        if solicitacao_id is not None: filtros.append(CotacaoFornecedor.solicitacao_id == solicitacao_id)
        if cotacao_id is not None: filtros.append(CotacaoFornecedor.id == cotacao_id)
        if status is not None: filtros.append(efetivo == status)
        total = self.banco.scalar(select(func.count()).select_from(CotacaoFornecedor).where(*filtros)) or 0
        cliente, fornecedor = aliased(Empresa), aliased(Empresa)
        aceitas = select(func.count(CotacaoFornecedor.id)).where(CotacaoFornecedor.solicitacao_id == SolicitacaoServico.id, CotacaoFornecedor.status == "aceita").correlate(SolicitacaoServico).scalar_subquery()
        consulta = select(CotacaoFornecedor, SolicitacaoServico, cliente.razao_social, fornecedor.razao_social,
            ProcessoFabricacao.nome, Material.nome, self._contrato_id(), aceitas)
        consulta = consulta.join(SolicitacaoServico, SolicitacaoServico.id == CotacaoFornecedor.solicitacao_id).join(cliente, cliente.id == SolicitacaoServico.empresa_cliente_id)
        consulta = consulta.join(fornecedor, fornecedor.id == CotacaoFornecedor.empresa_fornecedora_id).join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id).join(Material, Material.id == SolicitacaoServico.material_id)
        linhas = self.banco.execute(consulta.where(*filtros).order_by(CotacaoFornecedor.id.desc()).offset(deslocamento).limit(limite)).all()
        from backend.app.models.formacao_preco import FormacaoPreco
        precos=self.banco.scalars(select(FormacaoPreco).where(FormacaoPreco.cotacao_id.in_([l[0].id for l in linhas]))).all()
        return PaginaCotacoesComerciais(itens=[self._cotacao(*linha, agora) for linha in linhas], total=total, deslocamento=deslocamento, limite=limite)

    def _estado(self, solicitacao_id: int, *, travar=False):
        consulta = select(SolicitacaoServico).where(SolicitacaoServico.id == solicitacao_id)
        if travar: consulta = consulta.with_for_update()
        s = self.banco.scalar(consulta.execution_options(populate_existing=True))
        if s is None: raise HTTPException(404, detail="solicitacao_nao_encontrada")
        consulta_q = select(CotacaoFornecedor).where(CotacaoFornecedor.solicitacao_id == solicitacao_id).order_by(CotacaoFornecedor.id)
        if travar: consulta_q = consulta_q.with_for_update()
        qs = self.banco.scalars(consulta_q.execution_options(populate_existing=True)).all()
        contrato = self.banco.scalar(select(ContratacaoServico).where(ContratacaoServico.solicitacao_id == solicitacao_id).execution_options(populate_existing=True))
        estado = {"solicitacao": {c.name: getattr(s, c.name) for c in s.__table__.columns},
            "cotacoes": [{c.name: getattr(q, c.name) for c in q.__table__.columns} for q in qs],
            "contratacao": {c.name: getattr(contrato, c.name) for c in contrato.__table__.columns} if contrato else None}
        from backend.app.models.formacao_preco import FormacaoPreco
        estado['precos']=[{c.name:getattr(p,c.name) for c in p.__table__.columns} for p in self.banco.scalars(
            select(FormacaoPreco).where(FormacaoPreco.solicitacao_id==solicitacao_id).order_by(FormacaoPreco.cotacao_id))]
        versao = hashlib.sha256(json.dumps(estado, default=str, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return s, qs, contrato, versao

    def detalhe(self, solicitacao_id: int):
        self._leitura_consistente()
        s, qs, contrato, versao = self._estado(solicitacao_id)
        cliente = self.banco.get(Empresa, s.empresa_cliente_id).razao_social
        processo = self.banco.get(ProcessoFabricacao, s.processo_id).nome
        material = self.banco.get(Material, s.material_id).nome
        arquivos = [ServicoDocumentacaoCotacao(self.banco).detalhe(a) for a in self.banco.scalars(select(ArquivoTecnico).where(ArquivoTecnico.solicitacao_id == s.id).order_by(ArquivoTecnico.id))]
        from backend.app.models.formacao_preco import FormacaoPreco
        precos=self.banco.scalars(select(FormacaoPreco).where(FormacaoPreco.solicitacao_id==s.id)).all()
        total_aceitas = sum(q.status == "aceita" for q in qs)
        contrato_id = contrato.id if contrato else None
        fornecedores = {e.id: e.razao_social for e in self.banco.scalars(select(Empresa).where(Empresa.id.in_({q.empresa_fornecedora_id for q in qs}))) }
        agora = agora_utc()
        eventos = self.banco.scalars(select(EventoDecisaoCotacaoAdmin).where(EventoDecisaoCotacaoAdmin.solicitacao_id == s.id).order_by(EventoDecisaoCotacaoAdmin.id.desc())).all()
        historico = []
        for evento in eventos:
            resultado = json.loads(evento.resultado_json)
            historico.append(EventoDecisaoComercial(id=evento.id, solicitacao_id=s.id, cotacao_id=evento.cotacao_id,
                acao=evento.acao, administrador_nome=evento.administrador_nome, registro_interno=evento.registro_interno,
                criado_em=evento.criado_em, cotacoes_recusadas=resultado["cotacoes_recusadas"], cotacoes_expiradas=resultado["cotacoes_expiradas"]))
        return DetalheSolicitacaoComercial(solicitacao=self._resumo(s, cliente, processo, material, len(qs), total_aceitas, sum(a.ativo for a in arquivos), contrato_id),
            cotacoes=[self._cotacao(q, s, cliente, fornecedores[q.empresa_fornecedora_id], processo, material, contrato_id, total_aceitas, agora) for q in qs],
            arquivos=arquivos, historico=historico, versao=versao)

    @staticmethod
    def _repeticao(evento, solicitacao_id, cotacao_id, dados, usuario, registro):
        if (evento.solicitacao_id, evento.cotacao_id, evento.acao, evento.versao_anterior, evento.usuario_admin_id, evento.registro_interno) != (
                solicitacao_id, cotacao_id, dados.acao, dados.versao, usuario.usuario_id, registro):
            raise HTTPException(409, detail="chave_operacao_reutilizada")
        return ResultadoDecisaoComercial(**json.loads(evento.resultado_json), evento_id=evento.id)

    def registrar(self, solicitacao_id: int, cotacao_id: int, dados: DecisaoComercial, usuario: UsuarioAcesso):
        if usuario.perfil != "admin" or usuario.usuario_id <= 0 or usuario.deve_alterar_senha:
            raise HTTPException(403, detail="acao_exclusiva_da_administracao")
        registro = dados.registro_interno.strip()
        if len(registro) < 3: raise HTTPException(422, detail="registro_interno_obrigatorio")
        travar_documentacao(self.banco)
        chave = str(dados.chave_operacao)
        evento = self.banco.scalar(select(EventoDecisaoCotacaoAdmin).where(EventoDecisaoCotacaoAdmin.chave_operacao == chave))
        if evento: return self._repeticao(evento, solicitacao_id, cotacao_id, dados, usuario, registro)
        s, qs, contrato, versao = self._estado(solicitacao_id, travar=True)
        if not hmac.compare_digest(versao, dados.versao): raise HTTPException(409, detail="analise_comercial_alterada_atualize")
        q = next((item for item in qs if item.id == cotacao_id), None)
        if q is None: raise HTTPException(404, detail="cotacao_nao_encontrada")
        if s.status != "aberta": raise HTTPException(409, detail="solicitacao_nao_esta_aberta")
        if contrato is not None: raise HTTPException(409, detail="solicitacao_ja_contratada")
        agora = agora_utc()
        if situacao(q, agora) == "expirada": raise HTTPException(409, detail="cotacao_expirada")
        if q.status != "enviada": raise HTTPException(409, detail="cotacao_nao_esta_pendente")
        if any(item.status == "aceita" for item in qs): raise HTTPException(409, detail="solicitacao_ja_possui_cotacao_aceita")
        if dados.acao=='aceitar':
            from backend.app.services.formacao_preco import exigir_aprovacao
            exigir_aprovacao(self.banco,q)
        recusadas, expiradas = [], []
        for outra in qs:
            if outra.status != "enviada" or outra.id == q.id: continue
            if situacao(outra, agora) == "expirada":
                outra.status = "expirada"; outra.encerrada_em = agora; outra.decidida_por_empresa_id = None; expiradas.append(outra.id)
            elif dados.acao == "aceitar":
                outra.status = "recusada"; outra.encerrada_em = agora; outra.decidida_por_empresa_id = s.empresa_cliente_id; recusadas.append(outra.id)
        q.status = "aceita" if dados.acao == "aceitar" else "recusada"
        q.encerrada_em = agora
        # Campo legado conserva o cliente representado; o operador real está no evento.
        q.decidida_por_empresa_id = s.empresa_cliente_id
        resultado = {"solicitacao_id": s.id, "cotacao_id": q.id, "status": q.status,
            "administrador_nome": usuario.nome, "criado_em": data_utc(agora),
            "cotacoes_recusadas": recusadas, "cotacoes_expiradas": expiradas}
        evento = EventoDecisaoCotacaoAdmin(solicitacao_id=s.id, cotacao_id=q.id, acao=dados.acao,
            usuario_admin_id=usuario.usuario_id, administrador_nome=usuario.nome, registro_interno=registro,
            versao_anterior=dados.versao, chave_operacao=chave, resultado_json=json.dumps(resultado, ensure_ascii=False, sort_keys=True), criado_em=data_utc(agora))
        self.banco.add(evento)
        try:
            self.banco.commit()
            self.banco.refresh(evento)
        except IntegrityError:
            self.banco.rollback()
            existente = self.banco.scalar(select(EventoDecisaoCotacaoAdmin).where(EventoDecisaoCotacaoAdmin.chave_operacao == chave))
            if existente: return self._repeticao(existente, solicitacao_id, cotacao_id, dados, usuario, registro)
            raise HTTPException(409, detail="analise_comercial_alterada_atualize") from None
        return ResultadoDecisaoComercial(**resultado, evento_id=evento.id)
