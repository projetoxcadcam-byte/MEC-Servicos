from __future__ import annotations

import hashlib
import hmac
import json
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.contratacao import ContratacaoServico
from backend.app.models.contratacao_admin import EventoContratacaoAdmin
from backend.app.models.empresa import Empresa
from backend.app.models.intermediacao import CicloIntermediacao, EventoIntermediacao
from backend.app.models.material import Material
from backend.app.models.ordem_servico import OrdemServico
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.solicitacao import SolicitacaoServico
from backend.app.schemas.contratacao_admin import (
    ConfirmacaoContratacaoAdmin, ContratacaoAdministrativa, EventoContratacaoLeitura,
    PaginaContratacoesAdmin, PreparacaoContratacaoAdmin, ResultadoContratacaoAdmin,
)
from backend.app.services.comercial_admin import ServicoComercialAdmin, agora_utc, data_utc
from backend.app.services.documentacao_cotacao import travar_documentacao


class ServicoContratacaoAdmin:
    def __init__(self, banco: Session):
        self.banco = banco
        self.comercial = ServicoComercialAdmin(banco)

    @staticmethod
    def _consulta():
        cliente, fornecedor = aliased(Empresa), aliased(Empresa)
        return select(ContratacaoServico, cliente.razao_social, fornecedor.razao_social,
            SolicitacaoServico.quantidade, ProcessoFabricacao.nome, Material.nome, OrdemServico, CicloIntermediacao
        ).join(SolicitacaoServico, SolicitacaoServico.id == ContratacaoServico.solicitacao_id
        ).join(cliente, cliente.id == ContratacaoServico.empresa_cliente_id
        ).join(fornecedor, fornecedor.id == ContratacaoServico.empresa_fornecedora_id
        ).join(ProcessoFabricacao, ProcessoFabricacao.id == SolicitacaoServico.processo_id
        ).join(Material, Material.id == SolicitacaoServico.material_id
        ).outerjoin(OrdemServico, OrdemServico.contratacao_id == ContratacaoServico.id
        ).outerjoin(CicloIntermediacao, CicloIntermediacao.ordem_servico_id == OrdemServico.id)

    @staticmethod
    def _resumo(linha):
        c, cliente, fornecedor, quantidade, processo, material, ordem, ciclo = linha
        return ContratacaoAdministrativa(id=c.id, solicitacao_id=c.solicitacao_id, cotacao_id=c.cotacao_id,
            empresa_cliente_id=c.empresa_cliente_id, cliente=cliente, empresa_fornecedora_id=c.empresa_fornecedora_id,
            fornecedor=fornecedor, valor_total=c.valor_total, prazo_dias=c.prazo_dias, quantidade=quantidade,
            processo=processo, material=material, status=c.status, criada_em=data_utc(c.criada_em), observacoes=c.observacoes,
            ordem_servico_id=ordem.id if ordem else None, ordem_status=ordem.status if ordem else None,
            etapa_administrativa=ciclo.status if ciclo else None)

    def listar(self, *, ordens=False, solicitacao_id=None, contratacao_id=None, ordem_servico_id=None,
               status=None, deslocamento=0, limite=20):
        self.comercial._leitura_consistente()
        consulta = self._consulta()
        if ordens: consulta = consulta.where(OrdemServico.id.is_not(None))
        if solicitacao_id is not None: consulta = consulta.where(ContratacaoServico.solicitacao_id == solicitacao_id)
        if contratacao_id is not None: consulta = consulta.where(ContratacaoServico.id == contratacao_id)
        if ordem_servico_id is not None: consulta = consulta.where(OrdemServico.id == ordem_servico_id)
        if status is not None: consulta = consulta.where((OrdemServico.status if ordens else ContratacaoServico.status) == status)
        total = self.banco.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        ordem = OrdemServico.id if ordens else ContratacaoServico.id
        linhas = self.banco.execute(consulta.order_by(ordem.desc()).offset(deslocamento).limit(limite)).all()
        return PaginaContratacoesAdmin(itens=[self._resumo(linha) for linha in linhas], total=total,
            deslocamento=deslocamento, limite=limite)

    def _capturar(self, solicitacao_id, *, travar=False):
        s, cotacoes, contrato, base_versao = self.comercial._estado(solicitacao_id, travar=travar)
        consulta = select(OrdemServico).where(OrdemServico.contratacao_id == contrato.id) if contrato else None
        if travar and consulta is not None: consulta = consulta.with_for_update()
        ordem = self.banco.scalar(consulta.execution_options(populate_existing=True)) if consulta is not None else None
        ciclo = self.banco.scalar(select(CicloIntermediacao).where(CicloIntermediacao.ordem_servico_id == ordem.id)
            .execution_options(populate_existing=True)) if ordem else None
        d = self.comercial.detalhe(solicitacao_id)
        def campos(item): return {c.name: getattr(item, c.name) for c in item.__table__.columns} if item else None
        estado = {"comercial": base_versao, "ordem": campos(ordem), "ciclo": campos(ciclo),
            "arquivos": [a.model_dump(mode="json") for a in d.arquivos]}
        versao = hashlib.sha256(json.dumps(estado, default=str, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        aceitas = [q for q in cotacoes if q.status == "aceita"]
        q = next((q for q in cotacoes if q.id == contrato.cotacao_id), None) if contrato else aceitas[0] if len(aceitas) == 1 else None
        return s, q, contrato, ordem, d, versao

    def _impedimento(self, s, q, c, ordem, arquivos):
        if ordem: return "contratacao_ja_possui_ordem"
        if c and c.status != "ativa": return "contratacao_nao_esta_ativa"
        if not c and s.status != "aberta": return "solicitacao_nao_esta_aberta"
        if q is None or q.status != "aceita": return "solicitacao_sem_cotacao_aceita_unica"
        if not c and q.decidida_por_empresa_id != s.empresa_cliente_id: return "aceite_sem_vinculo_com_cliente"
        if c and (c.empresa_cliente_id != s.empresa_cliente_id or c.empresa_fornecedora_id != q.empresa_fornecedora_id):
            return "vinculos_da_contratacao_divergentes"
        if not any(a.liberado for a in arquivos): return "documentacao_para_contratacao_nao_disponivel"
        if not c:
            from backend.app.services.formacao_preco import exigir_aprovacao
            try:exigir_aprovacao(self.banco,q)
            except HTTPException as erro:return erro.detail
        return None

    def preparar(self, solicitacao_id):
        self.comercial._leitura_consistente()
        s, q, c, ordem, d, versao = self._capturar(solicitacao_id)
        motivo = self._impedimento(s, q, c, ordem, d.arquivos)
        linha = self.banco.execute(self._consulta().where(ContratacaoServico.id == c.id)).first() if c else None
        eventos = self.banco.scalars(select(EventoContratacaoAdmin).where(
            EventoContratacaoAdmin.solicitacao_id == solicitacao_id).order_by(EventoContratacaoAdmin.id.desc())).all()
        return PreparacaoContratacaoAdmin(solicitacao=d.solicitacao,
            cotacao=next((item for item in d.cotacoes if q and item.id == q.id), None),
            contratacao=self._resumo(linha) if linha else None, arquivos=d.arquivos, versao=versao,
            acao_disponivel=("abrir_os" if c else "contratar_e_abrir_os") if motivo is None else None,
            motivo_indisponivel=motivo, historico=[EventoContratacaoLeitura(id=e.id, acao=e.acao,
                contratacao_id=e.contratacao_id, ordem_servico_id=e.ordem_servico_id,
                administrador_nome=e.administrador_nome, registro_interno=e.registro_interno, criado_em=e.criado_em) for e in eventos])

    def obter_contratacao(self, contratacao_id):
        self.comercial._leitura_consistente()
        c = self.banco.get(ContratacaoServico, contratacao_id)
        if c is None: raise HTTPException(404, detail="contratacao_nao_encontrada")
        return self.preparar(c.solicitacao_id)

    @staticmethod
    def _repetir(e, solicitacao_id, dados, usuario, registro, observacoes):
        if (e.solicitacao_id, e.cotacao_id, e.acao, e.versao_anterior, e.usuario_admin_id,
            e.registro_interno, e.observacoes_execucao) != (solicitacao_id, dados.cotacao_id, dados.acao,
                dados.versao, usuario.usuario_id, registro, observacoes):
            raise HTTPException(409, detail="chave_operacao_reutilizada")
        return ResultadoContratacaoAdmin(**json.loads(e.resultado_json), evento_id=e.id)

    def confirmar(self, solicitacao_id, dados: ConfirmacaoContratacaoAdmin, usuario: UsuarioAcesso):
        if usuario.perfil != "admin" or usuario.usuario_id <= 0 or usuario.deve_alterar_senha:
            raise HTTPException(403, detail="acao_exclusiva_da_administracao")
        registro = dados.registro_interno.strip()
        if len(registro) < 3: raise HTTPException(422, detail="registro_interno_obrigatorio")
        observacoes = (dados.observacoes_execucao or "").strip() or None
        travar_documentacao(self.banco)
        chave = str(dados.chave_operacao)
        existente = self.banco.scalar(select(EventoContratacaoAdmin).where(EventoContratacaoAdmin.chave_operacao == chave))
        if existente: return self._repetir(existente, solicitacao_id, dados, usuario, registro, observacoes)
        s, q, contrato, ordem, d, versao = self._capturar(solicitacao_id, travar=True)
        if not hmac.compare_digest(versao, dados.versao): raise HTTPException(409, detail="preparacao_contratacao_alterada_atualize")
        motivo = self._impedimento(s, q, contrato, ordem, d.arquivos)
        if motivo: raise HTTPException(409, detail=motivo)
        acao = "abrir_os" if contrato else "contratar_e_abrir_os"
        if dados.acao != acao or dados.cotacao_id != q.id: raise HTTPException(409, detail="proposta_da_contratacao_divergente")
        if contrato and observacoes is not None: raise HTTPException(422, detail="abertura_os_preserva_instrucoes_contratadas")
        agora = agora_utc(); instante = data_utc(agora)
        try:
            if contrato is None:
                from backend.app.services.formacao_preco import valor_para_contratar, vincular_contrato
                contrato = ContratacaoServico(solicitacao_id=s.id, cotacao_id=q.id,
                    empresa_cliente_id=s.empresa_cliente_id, empresa_fornecedora_id=q.empresa_fornecedora_id,
                    valor_total=valor_para_contratar(self.banco,q), prazo_dias=q.prazo_dias, observacoes=observacoes,
                    status="ativa", criada_em=agora)
                self.banco.add(contrato); self.banco.flush()
                vincular_contrato(self.banco,q,contrato)
                s.status = "encerrada"
            ordem = OrdemServico(contratacao_id=contrato.id, solicitacao_id=s.id, cotacao_id=contrato.cotacao_id,
                empresa_cliente_id=contrato.empresa_cliente_id, empresa_fornecedora_id=contrato.empresa_fornecedora_id,
                processo_id=s.processo_id, material_id=s.material_id, quantidade=s.quantidade,
                valor_total=contrato.valor_total, prazo_dias=contrato.prazo_dias,
                observacoes=contrato.observacoes, status="aberta", criada_em=agora)
            self.banco.add(ordem); self.banco.flush()
            ciclo = CicloIntermediacao(ordem_servico_id=ordem.id, status="aguardando_material", versao=1,
                criado_em=instante, atualizado_em=instante)
            self.banco.add(ciclo); self.banco.flush()
            self.banco.add(EventoIntermediacao(ciclo_id=ciclo.id, versao=1, acao="iniciar_ciclo",
                status_anterior=None, status_resultante="aguardando_material", usuario_admin_id=usuario.usuario_id,
                administrador_nome=usuario.nome, registro_interno=registro, criado_em=instante))
            resultado = {"solicitacao_id": s.id, "cotacao_id": q.id, "contratacao_id": contrato.id,
                "ordem_servico_id": ordem.id, "contratacao_status": contrato.status, "ordem_status": "aberta",
                "etapa_administrativa": "aguardando_material", "administrador_nome": usuario.nome, "criado_em": instante}
            evento = EventoContratacaoAdmin(solicitacao_id=s.id, cotacao_id=q.id, contratacao_id=contrato.id,
                ordem_servico_id=ordem.id, acao=acao, usuario_admin_id=usuario.usuario_id,
                administrador_nome=usuario.nome, registro_interno=registro, observacoes_execucao=observacoes,
                versao_anterior=dados.versao, chave_operacao=chave,
                resultado_json=json.dumps(resultado, sort_keys=True, ensure_ascii=False), criado_em=instante)
            self.banco.add(evento); self.banco.flush()
            resposta = ResultadoContratacaoAdmin(**resultado, evento_id=evento.id)
            self.banco.commit()
            return resposta
        except IntegrityError:
            self.banco.rollback()
            existente = self.banco.scalar(select(EventoContratacaoAdmin).where(EventoContratacaoAdmin.chave_operacao == chave))
            if existente: return self._repetir(existente, solicitacao_id, dados, usuario, registro, observacoes)
            raise HTTPException(409, detail="preparacao_contratacao_alterada_atualize") from None
        except BaseException:
            self.banco.rollback(); raise
