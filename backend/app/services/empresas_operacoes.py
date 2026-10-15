from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.models.empresa import Empresa
from backend.app.models.processo import ProcessoFabricacao
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.operacao_empresa import OperacaoEmpresa
from backend.app.schemas.empresa import EmpresaLeitura
from backend.app.schemas.capacidade import CapacidadeLeitura
from backend.app.schemas.empresas_operacoes import EmpresaComOperacoesCriacao, OperacoesEmpresaAtualizacao, CapacidadeEmpresaRegistro, MaterialEmpresaVinculo
from backend.app.services.documentacao_cotacao import travar_documentacao
from backend.app.services.catalogo_operacoes_empresa import OPERACOES_PADRAO
from backend.app.services.catalogo_materiais_empresa import MATERIAIS_PADRAO


class ServicoEmpresasOperacoes:
    def __init__(self, banco: Session, usuario):
        if usuario.perfil != "admin" or usuario.usuario_id <= 0:
            raise HTTPException(403, detail="acao_exclusiva_da_administracao")
        self.banco, self.usuario = banco, usuario

    def _leitura(self):
        c=self.banco.connection()
        if c.dialect.name == "sqlite" and not c.connection.driver_connection.in_transaction:
            self.banco.execute(text("BEGIN"))

    def _empresa(self, empresa_id):
        empresa=self.banco.get(Empresa, empresa_id)
        if empresa is None: raise HTTPException(404, detail="empresa_nao_encontrada")
        return empresa

    def _registros(self, empresa_id):
        declaradas=list(self.banco.scalars(select(OperacaoEmpresa).where(OperacaoEmpresa.empresa_id==empresa_id).order_by(OperacaoEmpresa.processo_id)))
        capacidades=list(self.banco.scalars(select(CapacidadeFornecedor).where(CapacidadeFornecedor.empresa_id==empresa_id).order_by(CapacidadeFornecedor.processo_id)))
        return declaradas, capacidades

    def _versao(self, empresa, declaradas, capacidades):
        materiais=list(self.banco.execute(select(MaterialFornecedor.id,MaterialFornecedor.material_id).where(
            MaterialFornecedor.empresa_id==empresa.id).order_by(MaterialFornecedor.id)))
        dados=[empresa.id,empresa.tipo_empresa,
            [(v.processo_id,v.ativo,v.atualizado_em) for v in declaradas],
            [(v.id,v.processo_id,str(v.dimensao_x_maxima_mm),str(v.dimensao_y_maxima_mm),str(v.dimensao_z_maxima_mm),str(v.tolerancia_minima_mm)) for v in capacidades],
            [tuple(v) for v in materiais]]
        return hashlib.sha256(json.dumps(dados,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

    def catalogo(self):
        self._leitura()
        processos=list(self.banco.scalars(select(ProcessoFabricacao).order_by(ProcessoFabricacao.id)))
        opcoes=[dict(codigo=p.codigo,nome=p.nome,processo_id=p.id,ativo=p.ativo) for p in processos]
        codigos={p.codigo for p in processos};nomes={p.nome.casefold() for p in processos}
        for codigo,nome in OPERACOES_PADRAO.items():
            if codigo not in codigos and nome.casefold() not in nomes:
                opcoes.append(dict(codigo=codigo,nome=nome,processo_id=None,ativo=True))
        return {"itens":sorted(opcoes,key=lambda v:(v["nome"].casefold(),v["codigo"]))}

    @staticmethod
    def _nome_material(nome):
        return " ".join(nome.split()).casefold()

    def catalogo_materiais(self,deslocamento,limite):
        self._leitura()
        materiais=list(self.banco.scalars(select(Material).order_by(Material.id)))
        nomes={self._nome_material(m.nome) for m in materiais};codigos={m.codigo for m in materiais}
        opcoes=[dict(material_id=m.id,codigo=m.codigo,nome=m.nome) for m in materiais if m.ativo]
        opcoes.extend(dict(material_id=None,codigo=codigo,nome=nome) for codigo,nome in MATERIAIS_PADRAO.items()
            if codigo not in codigos and self._nome_material(nome) not in nomes)
        opcoes.sort(key=lambda v:(v["nome"].casefold(),v["codigo"]))
        return dict(itens=opcoes[deslocamento:deslocamento+limite],total=len(opcoes),deslocamento=deslocamento,limite=limite)

    def vincular_material(self,empresa_id,dados:MaterialEmpresaVinculo):
        try:
            travar_documentacao(self.banco);empresa=self._empresa(empresa_id);declaradas,capacidades=self._registros(empresa_id)
            if dados.versao!=self._versao(empresa,declaradas,capacidades):
                raise HTTPException(409,detail="operacoes_empresa_alteradas_atualize")
            if empresa.tipo_empresa not in {"fornecedor","ambos"}:
                raise HTTPException(409,detail="empresa_nao_e_fornecedora")
            if dados.material_id is not None:
                material=self.banco.get(Material,dados.material_id)
                if material is None:raise HTTPException(404,detail="material_nao_encontrado")
            else:
                if dados.codigo_catalogo is not None:
                    nome=MATERIAIS_PADRAO.get(dados.codigo_catalogo)
                    if nome is None:raise HTTPException(422,detail="material_catalogo_nao_encontrado")
                    codigo=dados.codigo_catalogo
                else:
                    nome=dados.novo_material
                    codigo="mec_material_"+hashlib.sha256(self._nome_material(nome).encode()).hexdigest()[:32]
                # Mesmo nome, mesmo cadastro: não assume equivalência entre ligas ou marcas.
                existentes=list(self.banco.scalars(select(Material).order_by(Material.id)))
                iguais=[m for m in existentes if self._nome_material(m.nome)==self._nome_material(nome)]
                if len(iguais)>1:raise HTTPException(409,detail="material_nome_ambiguo_selecione_cadastrado")
                material=iguais[0] if iguais else None
                if material is None:
                    if any(m.codigo==codigo for m in existentes):
                        raise HTTPException(409,detail="material_catalogo_alterado_atualize")
                    material=Material(codigo=codigo,nome=nome)
                    self.banco.add(material);self.banco.flush()
            if not material.ativo:raise HTTPException(409,detail="material_inativo")
            if self.banco.scalar(select(MaterialFornecedor.id).where(MaterialFornecedor.empresa_id==empresa_id,
                MaterialFornecedor.material_id==material.id)):
                raise HTTPException(409,detail="material_ja_associado_ao_fornecedor")
            self.banco.add(MaterialFornecedor(empresa_id=empresa_id,material_id=material.id))
            self.banco.commit();return self.detalhe(empresa_id)
        except IntegrityError:
            self.banco.rollback();raise HTTPException(409,detail="material_catalogo_alterado_atualize") from None
        except BaseException:self.banco.rollback();raise

    def detalhe(self, empresa_id):
        self._leitura(); empresa=self._empresa(empresa_id);declaradas,capacidades=self._registros(empresa_id)
        ids={v.processo_id for v in declaradas if v.ativo}|{v.processo_id for v in capacidades}
        processos={p.id:p for p in self.banco.scalars(select(ProcessoFabricacao).where(ProcessoFabricacao.id.in_(ids)))} if ids else {}
        caps={c.processo_id:c for c in capacidades}
        operacoes=[dict(codigo=processos[i].codigo,nome=processos[i].nome,processo_id=i,ativo=processos[i].ativo,
            capacidade=CapacidadeLeitura.model_validate(caps[i]).model_dump(mode="json") if i in caps else None)
            for i in sorted(ids) if i in processos]
        materiais=[dict(material_id=m.id,nome=m.nome,ativo=m.ativo) for m in self.banco.scalars(select(Material).join(MaterialFornecedor,MaterialFornecedor.material_id==Material.id).where(MaterialFornecedor.empresa_id==empresa_id).order_by(Material.nome))]
        return dict(empresa=EmpresaLeitura.model_validate(empresa).model_dump(mode="json"),operacoes=operacoes,
            materiais=materiais,versao=self._versao(empresa,declaradas,capacidades))

    def listar(self,busca,tipo,deslocamento,limite):
        self._leitura(); filtros=[]
        if busca:
            padrao="%"+busca.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
            filtros.append(or_(Empresa.razao_social.ilike(padrao,escape="\\"),Empresa.documento.ilike(padrao,escape="\\"),Empresa.id==int(busca) if busca.isascii() and busca.isdigit() and len(busca)<13 else False))
        if tipo: filtros.append(Empresa.tipo_empresa==tipo)
        total=self.banco.scalar(select(func.count()).select_from(Empresa).where(*filtros)) or 0
        empresas=list(self.banco.scalars(select(Empresa).where(*filtros).order_by(Empresa.id.desc()).offset(deslocamento).limit(limite)))
        ids=[e.id for e in empresas]; por_empresa={i:{} for i in ids}
        if ids:
            for modelo,condicoes in ((OperacaoEmpresa,[OperacaoEmpresa.ativo.is_(True)]),(CapacidadeFornecedor,[])):
                linhas=self.banco.execute(select(modelo.empresa_id,ProcessoFabricacao.id,ProcessoFabricacao.nome).join(ProcessoFabricacao,ProcessoFabricacao.id==modelo.processo_id).where(modelo.empresa_id.in_(ids),*condicoes))
                for empresa_id,pid,nome in linhas: por_empresa[empresa_id][pid]=nome
        itens=[dict(**EmpresaLeitura.model_validate(e).model_dump(mode="json"),operacoes=list(por_empresa[e.id].values())) for e in empresas]
        return dict(itens=itens,total=total,deslocamento=deslocamento,limite=limite)

    def _processos(self,codigos):
        processos=[]
        for codigo in codigos:
            processo=self.banco.scalar(select(ProcessoFabricacao).where(ProcessoFabricacao.codigo==codigo))
            if processo:
                if not processo.ativo: raise HTTPException(409,detail="processo_inativo")
            elif codigo in OPERACOES_PADRAO:
                nome=OPERACOES_PADRAO[codigo]
                if self.banco.scalar(select(ProcessoFabricacao.id).where(func.lower(ProcessoFabricacao.nome)==nome.lower())):
                    raise HTTPException(409,detail="catalogo_operacoes_alterado_atualize")
                processo=ProcessoFabricacao(codigo=codigo,nome=nome)
                self.banco.add(processo);self.banco.flush()
            else: raise HTTPException(422,detail="operacao_nao_encontrada")
            processos.append(processo)
        return processos

    def _guardar(self,empresa,processos,declaradas):
        alvo={p.id for p in processos}; antigas={v.processo_id:v for v in declaradas}
        agora=datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")
        for pid in alvo|set(antigas):
            registro=antigas.get(pid);ativo=pid in alvo
            if registro is None:
                self.banco.add(OperacaoEmpresa(empresa_id=empresa.id,processo_id=pid,ativo=True,usuario_admin_id=self.usuario.usuario_id,atualizado_em=agora))
            elif registro.ativo!=ativo:
                registro.ativo=ativo;registro.usuario_admin_id=self.usuario.usuario_id;registro.atualizado_em=agora

    def criar(self,dados:EmpresaComOperacoesCriacao):
        try:
            travar_documentacao(self.banco)
            if self.banco.scalar(select(Empresa.id).where(Empresa.documento==dados.documento)):
                raise HTTPException(409,detail="documento_da_empresa_ja_cadastrado")
            processos=self._processos(dados.operacoes)
            empresa=Empresa(razao_social=dados.razao_social,documento=dados.documento,tipo_empresa=dados.tipo_empresa.value)
            self.banco.add(empresa);self.banco.flush();self._guardar(empresa,processos,[])
            self.banco.commit();return self.detalhe(empresa.id)
        except IntegrityError:
            self.banco.rollback();raise HTTPException(409,detail="cadastro_alterado_atualize") from None
        except BaseException:self.banco.rollback();raise

    def atualizar(self,empresa_id,dados:OperacoesEmpresaAtualizacao):
        try:
            travar_documentacao(self.banco);empresa=self._empresa(empresa_id);declaradas,capacidades=self._registros(empresa_id)
            if dados.versao!=self._versao(empresa,declaradas,capacidades):raise HTTPException(409,detail="operacoes_empresa_alteradas_atualize")
            if empresa.tipo_empresa not in {"fornecedor","ambos"} and dados.operacoes:raise HTTPException(409,detail="empresa_nao_e_fornecedora")
            # Capacidade técnica existente continua no cadastro e na compatibilidade.
            existentes={p.id:p for p in self.banco.scalars(select(ProcessoFabricacao).where(ProcessoFabricacao.id.in_([c.processo_id for c in capacidades])))}
            obrigatorios={p.codigo for p in existentes.values()}
            if not obrigatorios.issubset(set(dados.operacoes)):raise HTTPException(409,detail="operacao_possui_capacidade_tecnica")
            normais=[codigo for codigo in dados.operacoes if codigo not in obrigatorios]
            processos=self._processos(normais)+list(existentes.values())
            self._guardar(empresa,processos,declaradas);self.banco.commit();return self.detalhe(empresa_id)
        except IntegrityError:
            self.banco.rollback();raise HTTPException(409,detail="cadastro_alterado_atualize") from None
        except BaseException:self.banco.rollback();raise

    def registrar_capacidade(self,empresa_id,dados:CapacidadeEmpresaRegistro):
        try:
            travar_documentacao(self.banco);empresa=self._empresa(empresa_id);declaradas,capacidades=self._registros(empresa_id)
            if dados.versao!=self._versao(empresa,declaradas,capacidades):raise HTTPException(409,detail="operacoes_empresa_alteradas_atualize")
            if empresa.tipo_empresa not in {"fornecedor","ambos"}:raise HTTPException(409,detail="empresa_nao_e_fornecedora")
            if dados.processo_id in {c.processo_id for c in capacidades}:raise HTTPException(409,detail="capacidade_para_processo_ja_cadastrada")
            if dados.processo_id not in {v.processo_id for v in declaradas if v.ativo}:raise HTTPException(409,detail="operacao_nao_declarada_pela_empresa")
            processo=self.banco.get(ProcessoFabricacao,dados.processo_id)
            if processo is None or not processo.ativo:raise HTTPException(409,detail="processo_inativo")
            self.banco.add(CapacidadeFornecedor(empresa_id=empresa_id,**dados.model_dump(exclude={"versao"})))
            self.banco.commit();return self.detalhe(empresa_id)
        except IntegrityError:
            self.banco.rollback();raise HTTPException(409,detail="capacidade_para_processo_ja_cadastrada") from None
        except BaseException:self.banco.rollback();raise
