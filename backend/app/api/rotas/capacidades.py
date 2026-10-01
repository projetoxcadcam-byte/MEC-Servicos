from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database.sessao import obter_banco
from backend.app.schemas.capacidade import CapacidadeCriacao, CapacidadeLeitura, MaquinaCriacao, MaquinaLeitura, MaterialFornecedorCriacao, MaterialFornecedorLeitura
from backend.app.services.capacidade import (CapacidadeDuplicada, EmpresaNaoFornecedora, EmpresaTecnicaNaoEncontrada, MaterialFornecedorDuplicado, MaterialNaoEncontrado, MaquinaDuplicada, ProcessoNaoEncontrado, ServicoCapacidadeFornecedor)

roteador = APIRouter(prefix="/empresas/{empresa_id}", tags=["capacidade técnica"])
SessaoBanco = Annotated[Session, Depends(obter_banco)]

def _servico(banco: Session) -> ServicoCapacidadeFornecedor:
    return ServicoCapacidadeFornecedor(banco)

@roteador.post("/capacidades", response_model=CapacidadeLeitura, status_code=status.HTTP_201_CREATED)
def criar_capacidade(empresa_id: int, dados: CapacidadeCriacao, banco: SessaoBanco) -> CapacidadeLeitura:
    try: item = _servico(banco).criar_capacidade(empresa_id, dados)
    except EmpresaTecnicaNaoEncontrada as exc: raise HTTPException(status_code=404, detail="empresa_nao_encontrada") from exc
    except EmpresaNaoFornecedora as exc: raise HTTPException(status_code=409, detail="empresa_nao_e_fornecedora") from exc
    except ProcessoNaoEncontrado as exc: raise HTTPException(status_code=404, detail="processo_nao_encontrado") from exc
    except CapacidadeDuplicada as exc: raise HTTPException(status_code=409, detail="capacidade_para_processo_ja_cadastrada") from exc
    return CapacidadeLeitura.model_validate(item)

@roteador.get("/capacidades", response_model=list[CapacidadeLeitura])
def listar_capacidades(empresa_id: int, banco: SessaoBanco) -> list[CapacidadeLeitura]:
    return [CapacidadeLeitura.model_validate(x) for x in _servico(banco).listar_capacidades(empresa_id)]

@roteador.post("/maquinas", response_model=MaquinaLeitura, status_code=status.HTTP_201_CREATED)
def criar_maquina(empresa_id: int, dados: MaquinaCriacao, banco: SessaoBanco) -> MaquinaLeitura:
    try: item = _servico(banco).criar_maquina(empresa_id, dados)
    except EmpresaTecnicaNaoEncontrada as exc: raise HTTPException(status_code=404, detail="empresa_nao_encontrada") from exc
    except EmpresaNaoFornecedora as exc: raise HTTPException(status_code=409, detail="empresa_nao_e_fornecedora") from exc
    except ProcessoNaoEncontrado as exc: raise HTTPException(status_code=404, detail="processo_nao_encontrado") from exc
    except MaquinaDuplicada as exc: raise HTTPException(status_code=409, detail="maquina_ja_cadastrada") from exc
    return MaquinaLeitura.model_validate(item)

@roteador.get("/maquinas", response_model=list[MaquinaLeitura])
def listar_maquinas(empresa_id: int, banco: SessaoBanco) -> list[MaquinaLeitura]:
    return [MaquinaLeitura.model_validate(x) for x in _servico(banco).listar_maquinas(empresa_id)]

@roteador.post("/materiais", response_model=MaterialFornecedorLeitura, status_code=status.HTTP_201_CREATED)
def adicionar_material(empresa_id: int, dados: MaterialFornecedorCriacao, banco: SessaoBanco) -> MaterialFornecedorLeitura:
    try: item = _servico(banco).adicionar_material(empresa_id, dados)
    except EmpresaTecnicaNaoEncontrada as exc: raise HTTPException(status_code=404, detail="empresa_nao_encontrada") from exc
    except EmpresaNaoFornecedora as exc: raise HTTPException(status_code=409, detail="empresa_nao_e_fornecedora") from exc
    except MaterialNaoEncontrado as exc: raise HTTPException(status_code=404, detail="material_nao_encontrado") from exc
    except MaterialFornecedorDuplicado as exc: raise HTTPException(status_code=409, detail="material_ja_associado_ao_fornecedor") from exc
    return MaterialFornecedorLeitura.model_validate(item)

@roteador.get("/materiais", response_model=list[MaterialFornecedorLeitura])
def listar_materiais_fornecedor(empresa_id: int, banco: SessaoBanco) -> list[MaterialFornecedorLeitura]:
    return [MaterialFornecedorLeitura.model_validate(x) for x in _servico(banco).listar_materiais(empresa_id)]
