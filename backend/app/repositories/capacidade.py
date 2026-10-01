from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.models.capacidade import CapacidadeFornecedor
from backend.app.models.empresa import Empresa
from backend.app.models.maquina import Maquina
from backend.app.models.material import Material
from backend.app.models.material_fornecedor import MaterialFornecedor
from backend.app.models.processo import ProcessoFabricacao
from backend.app.schemas.capacidade import CapacidadeCriacao, MaquinaCriacao, MaterialFornecedorCriacao
from backend.app.schemas.material import MaterialCriacao
from backend.app.schemas.processo import ProcessoCriacao

class RepositorioCapacidade:
    def __init__(self, banco: Session) -> None: self.banco = banco
    def obter_empresa(self, empresa_id: int) -> Empresa | None: return self.banco.get(Empresa, empresa_id)
    def obter_processo(self, processo_id: int) -> ProcessoFabricacao | None: return self.banco.get(ProcessoFabricacao, processo_id)
    def obter_material(self, material_id: int) -> Material | None: return self.banco.get(Material, material_id)
    def obter_capacidade(self, empresa_id: int, processo_id: int) -> CapacidadeFornecedor | None:
        return self.banco.scalar(select(CapacidadeFornecedor).where(CapacidadeFornecedor.empresa_id == empresa_id, CapacidadeFornecedor.processo_id == processo_id))
    def listar_capacidades(self, empresa_id: int) -> list[CapacidadeFornecedor]:
        return list(self.banco.scalars(select(CapacidadeFornecedor).where(CapacidadeFornecedor.empresa_id == empresa_id).order_by(CapacidadeFornecedor.id)).all())
    def criar_capacidade(self, empresa_id: int, dados: CapacidadeCriacao) -> CapacidadeFornecedor:
        item = CapacidadeFornecedor(empresa_id=empresa_id, processo_id=dados.processo_id, dimensao_x_maxima_mm=dados.dimensao_x_maxima_mm, dimensao_y_maxima_mm=dados.dimensao_y_maxima_mm, dimensao_z_maxima_mm=dados.dimensao_z_maxima_mm, tolerancia_minima_mm=dados.tolerancia_minima_mm, observacoes=dados.observacoes)
        self.banco.add(item); self.banco.commit(); self.banco.refresh(item); return item
    def obter_maquina_por_nome(self, empresa_id: int, nome: str) -> Maquina | None:
        return self.banco.scalar(select(Maquina).where(Maquina.empresa_id == empresa_id, Maquina.nome == nome))
    def listar_maquinas(self, empresa_id: int) -> list[Maquina]:
        return list(self.banco.scalars(select(Maquina).where(Maquina.empresa_id == empresa_id).order_by(Maquina.id)).all())
    def criar_maquina(self, empresa_id: int, dados: MaquinaCriacao) -> Maquina:
        item = Maquina(empresa_id=empresa_id, processo_id=dados.processo_id, nome=dados.nome, fabricante=dados.fabricante, modelo=dados.modelo, dimensao_x_maxima_mm=dados.dimensao_x_maxima_mm, dimensao_y_maxima_mm=dados.dimensao_y_maxima_mm, dimensao_z_maxima_mm=dados.dimensao_z_maxima_mm, tolerancia_minima_mm=dados.tolerancia_minima_mm)
        self.banco.add(item); self.banco.commit(); self.banco.refresh(item); return item
    def obter_material_fornecedor(self, empresa_id: int, material_id: int) -> MaterialFornecedor | None:
        return self.banco.scalar(select(MaterialFornecedor).where(MaterialFornecedor.empresa_id == empresa_id, MaterialFornecedor.material_id == material_id))
    def listar_materiais(self, empresa_id: int) -> list[MaterialFornecedor]:
        return list(self.banco.scalars(select(MaterialFornecedor).where(MaterialFornecedor.empresa_id == empresa_id).order_by(MaterialFornecedor.id)).all())
    def adicionar_material(self, empresa_id: int, dados: MaterialFornecedorCriacao) -> MaterialFornecedor:
        item = MaterialFornecedor(empresa_id=empresa_id, material_id=dados.material_id, observacoes=dados.observacoes)
        self.banco.add(item); self.banco.commit(); self.banco.refresh(item); return item
    def obter_processo_por_codigo(self, codigo: str) -> ProcessoFabricacao | None:
        return self.banco.scalar(select(ProcessoFabricacao).where(ProcessoFabricacao.codigo == codigo))
    def obter_material_por_codigo(self, codigo: str) -> Material | None:
        return self.banco.scalar(select(Material).where(Material.codigo == codigo))
    def listar_processos(self, deslocamento: int, limite: int) -> list[ProcessoFabricacao]:
        return list(self.banco.scalars(select(ProcessoFabricacao).order_by(ProcessoFabricacao.id).offset(deslocamento).limit(limite)).all())
    def listar_materiais_catalogo(self, deslocamento: int, limite: int) -> list[Material]:
        return list(self.banco.scalars(select(Material).order_by(Material.id).offset(deslocamento).limit(limite)).all())
    def criar_processo(self, dados: ProcessoCriacao) -> ProcessoFabricacao:
        item = ProcessoFabricacao(codigo=dados.codigo.strip().lower(), nome=" ".join(dados.nome.split()), descricao=dados.descricao)
        self.banco.add(item); self.banco.commit(); self.banco.refresh(item); return item
    def criar_material(self, dados: MaterialCriacao) -> Material:
        item = Material(codigo=dados.codigo.strip().lower(), nome=" ".join(dados.nome.split()), familia=dados.familia, especificacao=dados.especificacao)
        self.banco.add(item); self.banco.commit(); self.banco.refresh(item); return item
