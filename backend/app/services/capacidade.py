from __future__ import annotations
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.models.empresa import Empresa
from backend.app.repositories.capacidade import RepositorioCapacidade
from backend.app.schemas.capacidade import CapacidadeCriacao, MaquinaCriacao, MaterialFornecedorCriacao
from backend.app.schemas.material import MaterialCriacao
from backend.app.schemas.processo import ProcessoCriacao

class ProcessoDuplicado(ValueError): pass
class MaterialDuplicado(ValueError): pass
class EmpresaTecnicaNaoEncontrada(LookupError): pass
class EmpresaNaoFornecedora(ValueError): pass
class ProcessoNaoEncontrado(LookupError): pass
class MaterialNaoEncontrado(LookupError): pass
class CapacidadeDuplicada(ValueError): pass
class MaquinaDuplicada(ValueError): pass
class MaterialFornecedorDuplicado(ValueError): pass

class ServicoCatalogoTecnico:
    def __init__(self, banco: Session) -> None: self.repositorio = RepositorioCapacidade(banco)
    def criar_processo(self, dados: ProcessoCriacao):
        codigo = dados.codigo.strip().lower()
        if self.repositorio.obter_processo_por_codigo(codigo): raise ProcessoDuplicado(dados.codigo)
        try: return self.repositorio.criar_processo(dados)
        except IntegrityError as exc:
            self.repositorio.banco.rollback(); raise ProcessoDuplicado(dados.codigo) from exc
    def listar_processos(self, deslocamento: int, limite: int): return self.repositorio.listar_processos(deslocamento, limite)
    def criar_material(self, dados: MaterialCriacao):
        codigo = dados.codigo.strip().lower()
        if self.repositorio.obter_material_por_codigo(codigo): raise MaterialDuplicado(dados.codigo)
        try: return self.repositorio.criar_material(dados)
        except IntegrityError as exc:
            self.repositorio.banco.rollback(); raise MaterialDuplicado(dados.codigo) from exc
    def listar_materiais(self, deslocamento: int, limite: int): return self.repositorio.listar_materiais_catalogo(deslocamento, limite)

class ServicoCapacidadeFornecedor:
    def __init__(self, banco: Session) -> None: self.repositorio = RepositorioCapacidade(banco)
    def _obter_fornecedor(self, empresa_id: int) -> Empresa:
        empresa = self.repositorio.obter_empresa(empresa_id)
        if empresa is None: raise EmpresaTecnicaNaoEncontrada(empresa_id)
        if empresa.tipo_empresa not in {"fornecedor", "ambos"}: raise EmpresaNaoFornecedora(empresa_id)
        return empresa
    def criar_capacidade(self, empresa_id: int, dados: CapacidadeCriacao):
        self._obter_fornecedor(empresa_id)
        if self.repositorio.obter_processo(dados.processo_id) is None: raise ProcessoNaoEncontrado(dados.processo_id)
        if self.repositorio.obter_capacidade(empresa_id, dados.processo_id) is not None: raise CapacidadeDuplicada(dados.processo_id)
        try: return self.repositorio.criar_capacidade(empresa_id, dados)
        except IntegrityError as exc:
            self.repositorio.banco.rollback(); raise CapacidadeDuplicada(dados.processo_id) from exc
    def listar_capacidades(self, empresa_id: int): self._obter_fornecedor(empresa_id); return self.repositorio.listar_capacidades(empresa_id)
    def criar_maquina(self, empresa_id: int, dados: MaquinaCriacao):
        self._obter_fornecedor(empresa_id)
        if self.repositorio.obter_processo(dados.processo_id) is None: raise ProcessoNaoEncontrado(dados.processo_id)
        if self.repositorio.obter_maquina_por_nome(empresa_id, dados.nome) is not None: raise MaquinaDuplicada(dados.nome)
        try: return self.repositorio.criar_maquina(empresa_id, dados)
        except IntegrityError as exc:
            self.repositorio.banco.rollback(); raise MaquinaDuplicada(dados.nome) from exc
    def listar_maquinas(self, empresa_id: int): self._obter_fornecedor(empresa_id); return self.repositorio.listar_maquinas(empresa_id)
    def adicionar_material(self, empresa_id: int, dados: MaterialFornecedorCriacao):
        self._obter_fornecedor(empresa_id)
        if self.repositorio.obter_material(dados.material_id) is None: raise MaterialNaoEncontrado(dados.material_id)
        if self.repositorio.obter_material_fornecedor(empresa_id, dados.material_id) is not None: raise MaterialFornecedorDuplicado(dados.material_id)
        try: return self.repositorio.adicionar_material(empresa_id, dados)
        except IntegrityError as exc:
            self.repositorio.banco.rollback(); raise MaterialFornecedorDuplicado(dados.material_id) from exc
    def listar_materiais(self, empresa_id: int): self._obter_fornecedor(empresa_id); return self.repositorio.listar_materiais(empresa_id)
