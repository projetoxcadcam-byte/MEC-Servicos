from __future__ import annotations
import ast
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = "MEC_SERVICOS_V0_1_D5_REQUISITOS_COMPATIBILIDADE.py"
REVISION = "MEC-SERVICOS-V0.1-D5-REQUISITOS-COMPATIBILIDADE-2026-10-01"
PROJECT_LABEL = "Plataforma de Serviços Mecânicos"
REPORT_TXT = "MEC_SERVICOS_V0_1_D5_REQUISITOS_COMPATIBILIDADE_RELATORIO.txt"
REPORT_JSON = "MEC_SERVICOS_V0_1_D5_REQUISITOS_COMPATIBILIDADE.json"
BACKUP_ROOT = "_mec_backups"

EXPECTED_D4_HASHES = {'.env.example': '87eee5ce36ba1ae7bc1a51a07094e24b3bf8b4ee5d41b66f8cd1200bdad6981d',
 '.gitignore': 'a1144fdc91958b636c070731d3a43dffb86b3eff72c962ec04c235568d5f9d08',
 'README.md': '7a7679b605a3ba827f4c7c09380fce1916cda70c43fbd7622d1046cf884060ef',
 'backend/__init__.py': '690ba32252f50de29c041a17bd248e084cfaec2aad44ed8e2feca911fb71f0f7',
 'backend/app/__init__.py': '2ddf04ce230d37abf359b2abd8d1677209e06b54dcfaf256148aecb551b7d46c',
 'backend/app/api/__init__.py': 'f2bb21446686add00526d449012aea5f0b2c313166124fa756965721d7655500',
 'backend/app/api/rotas/__init__.py': 'adcf1b9f47338f24a6bc9471aa5382e447dafa5e37bbe8e837bc3c22d2150f27',
 'backend/app/api/rotas/banco_dados.py': '4ede4c00d97ffeb6a6a07773b5cc965112420ec50151f71f1a741c5a1d1948a7',
 'backend/app/api/rotas/capacidades.py': 'f6618b2615afe1f982243add5c746f6e203688a97cf824d310f6a30adbf7cebd',
 'backend/app/api/rotas/empresas.py': '8b053288b7c0db67afa6947feb21e4f8029a2daafed91ef7f62a0a87fbe9fb09',
 'backend/app/api/rotas/materiais.py': 'f30f27e3f85685efdf554f6e9bc6d9438cce2df70090bad21989d7e0a8b2d80d',
 'backend/app/api/rotas/processos.py': '09b41103270590f34cae7c04accfe5f035cfc3fe6bb948dc84d8ce5d00bd009e',
 'backend/app/api/rotas/saude.py': '71762976f56f1286a4caf30edbc699573fb2f859a6e89e78cc85791973a4ea39',
 'backend/app/api/roteador.py': '1fa945aeb5807d888a4ba4da3d4caf5ee1d74da31e4672b03d58530a3ae86dd8',
 'backend/app/auth/__init__.py': '3201b3408ec5bc94f9f1921146643b6aba1195cf93fcb44891c6535640b86d29',
 'backend/app/core/__init__.py': 'e6d29562bddb2c0bd00adee7a6dbe81028949a848e4d767de324b6bcd43c773a',
 'backend/app/core/configuracao.py': '3c09980767ca8fdec98d3e6d83847ddefe93fe62636f59f478f2123360360823',
 'backend/app/database/__init__.py': 'db6d80c314e9b104c7ce5fa3a8cbc688620f948263b55f89bdb799655931e5ca',
 'backend/app/database/base.py': '169ee7e047f140ec73aa6df8f83fab632bbad0ff3c7995087b008134ffc8b9ce',
 'backend/app/database/inicializacao.py': 'ae713833fc5ffc79e2f79642d972cda0e4c640ac33d58efd69294429c9a1abf7',
 'backend/app/database/sessao.py': '0eb809448955331d1ce4b65e06153882bd5f523e839f6736f66ca323c54c658a',
 'backend/app/models/__init__.py': '977a06e5df578834d79361a70288f3980fe9b06f2165480096f05e9aee94eb52',
 'backend/app/models/capacidade.py': '3e52b82bf88d8636acb5b93de24f6c12fd78c08fd465b5cc37c58348aa8934b7',
 'backend/app/models/empresa.py': '56f2bdbc9930627574ee50b1a19624a903e43ddb330a75dc1c5355b8f5e78730',
 'backend/app/models/maquina.py': '87e05f3563524822d31bff9cfa2bc24aeba2667baecb3f43b87fa5972d37a617',
 'backend/app/models/material.py': 'bc424157fc9141d35c4275d54655d331fa6b2e5d51eca4d35a23fb4e0e1eb313',
 'backend/app/models/material_fornecedor.py': '30372d3a583069625bb54120793351b5da16b037b79fd1bb34f0424d002213ae',
 'backend/app/models/processo.py': '84ddea465d90af57c729973e1b80697d70ebaf8cf328453f6c4436d73e50b51b',
 'backend/app/principal.py': '7a4a04cbaae7e0b99e2acae3a4c7c031d494e108184c699e35ab431c4898db48',
 'backend/app/repositories/__init__.py': '1c34878befe52911e8dd3c67b64ed745d826a017bc92c6abc140fddd4a6a2892',
 'backend/app/repositories/capacidade.py': 'ebeabad5e367cbf6fd56c30cdcc8ada786cef963c80172f1b192e437ebe0be38',
 'backend/app/repositories/empresa.py': 'be9cc6fd0caef93e475f585cf349642d86744f2efee9bd2d4df894857070080a',
 'backend/app/schemas/__init__.py': 'c94b5333d8067e2e8689e848e749241a690baf6cc24f12c01be12a11c36b2a70',
 'backend/app/schemas/capacidade.py': '39e765fc34fcaf55a1b3775cef4b5a10e53fedac123586f95fcd73e59f210609',
 'backend/app/schemas/empresa.py': 'c45daf2aa640d50576d113b5917466e4feff44015ef1cd07715297e145f561ba',
 'backend/app/schemas/material.py': '51a7360a94223cda59ead93d285fb898fcc3441161a4a2752cc579ea57b91f9e',
 'backend/app/schemas/processo.py': '43ee83979a70faae06e2f33977ebff5db9c1b0684645b5558cf54dd0a0f0bc2b',
 'backend/app/services/__init__.py': '0a1ee226f5b792028404f5726d3c8560c7451a4a9d8e483ca53d7d176bc6da95',
 'backend/app/services/capacidade.py': 'f052d3448f05be622df4eb65e9f16f9a5e26c7cf1f9b0f6e304432f9dda1505d',
 'backend/app/services/empresa.py': '239e4f78f66a583493cb1c45b0ca818270910deb992e93673e68bef5416a563e',
 'docs/README.md': 'd57eafc62261a9b07b2c6083391725678cb14331d3b6c4ef318ac4ea7c477cfb',
 'pyproject.toml': '804119239108047d4248590388e74779e241f3c0050d3e8c81c92dd4f249ce33',
 'tests/test_banco_dados.py': 'a3c73d8f22483993efaba3a3e1803e5c28ef5f6d94e484368a5082fad33199d2',
 'tests/test_capacidade_tecnica.py': '096492868933fa0b9899c265bbe31937de6f82fe8edc581cc3d92f85e5de470b',
 'tests/test_empresas_api.py': 'ead6248db13f010d8a528aec745c614779d77786261fb3a1529cd8fb4cf70365',
 'tests/test_saude.py': 'b301583b26b6d3d5ebec124594e02dcc9ca6a9ea675e78563f32bddd5a02afa5'}
UPDATED_FILES = {'README.md': '# Plataforma de Serviços Mecânicos\n'
              '\n'
              'Projeto independente para conectar clientes e fornecedores de serviços mecânicos.\n'
              '\n'
              '## Regra de idioma\n'
              '\n'
              'A aplicação é desenvolvida em português: interface, documentação, mensagens,\n'
              'validações, nomes do domínio e módulos específicos da aplicação.\n'
              '\n'
              'Nomes de tecnologias externas, como Python, FastAPI, SQLAlchemy, SQLite e Uvicorn,\n'
              'permanecem com seus nomes oficiais.\n'
              '\n'
              '## Estado\n'
              '\n'
              '**V0.1 D5 — Requisitos Técnicos e Compatibilidade de Fornecedores**\n'
              '\n'
              'Nesta etapa foram estruturados:\n'
              '\n'
              '- solicitação de serviço técnico;\n'
              '- processo de fabricação requerido;\n'
              '- material requerido;\n'
              '- dimensões máximas da peça em milímetros;\n'
              '- tolerância requerida em milímetros;\n'
              '- quantidade;\n'
              '- validação de empresa cliente;\n'
              '- consulta de fornecedores tecnicamente compatíveis;\n'
              '- compatibilidade por processo, material, dimensões e tolerância.\n'
              '\n'
              'O projeto continua independente do CGX Platform.\n'
              '\n'
              '## Regra dimensional do D5\n'
              '\n'
              'A compatibilidade inicial usa correspondência direta dos eixos:\n'
              '\n'
              '- X requerido <= X máximo do fornecedor;\n'
              '- Y requerido <= Y máximo do fornecedor;\n'
              '- Z requerido <= Z máximo do fornecedor;\n'
              '- tolerância mínima do fornecedor <= tolerância requerida.\n'
              '\n'
              'A rotação automática da peça entre eixos ainda não faz parte desta etapa.\n'
              '\n'
              '## Executar\n'
              '\n'
              '```powershell\n'
              'python -m pytest\n'
              'python -m uvicorn backend.app.principal:app --reload\n'
              '```\n'
              '\n'
              '## Endpoints principais\n'
              '\n'
              '- `http://127.0.0.1:8000/`\n'
              '- `http://127.0.0.1:8000/api/v1/saude`\n'
              '- `http://127.0.0.1:8000/api/v1/banco-dados/saude`\n'
              '- `http://127.0.0.1:8000/api/v1/empresas`\n'
              '- `http://127.0.0.1:8000/api/v1/processos-fabricacao`\n'
              '- `http://127.0.0.1:8000/api/v1/materiais`\n'
              '- `http://127.0.0.1:8000/api/v1/solicitacoes-servico`\n'
              '- `http://127.0.0.1:8000/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis`\n'
              '- `http://127.0.0.1:8000/docs`\n',
 'backend/app/api/roteador.py': 'from fastapi import APIRouter\n'
                                '\n'
                                'from backend.app.api.rotas.banco_dados import roteador as roteador_banco\n'
                                'from backend.app.api.rotas.empresas import roteador as roteador_empresas\n'
                                'from backend.app.api.rotas.saude import roteador as roteador_saude\n'
                                'from backend.app.api.rotas.processos import roteador as roteador_processos\n'
                                'from backend.app.api.rotas.materiais import roteador as roteador_materiais\n'
                                'from backend.app.api.rotas.capacidades import roteador as roteador_capacidades\n'
                                'from backend.app.api.rotas.solicitacoes import roteador as roteador_solicitacoes\n'
                                '\n'
                                'roteador_api = APIRouter()\n'
                                'roteador_api.include_router(roteador_saude)\n'
                                'roteador_api.include_router(roteador_banco)\n'
                                'roteador_api.include_router(roteador_empresas)\n'
                                'roteador_api.include_router(roteador_processos)\n'
                                'roteador_api.include_router(roteador_materiais)\n'
                                'roteador_api.include_router(roteador_capacidades)\n'
                                'roteador_api.include_router(roteador_solicitacoes)\n',
 'backend/app/models/__init__.py': 'from backend.app.models.empresa import Empresa\n'
                                   'from backend.app.models.processo import ProcessoFabricacao\n'
                                   'from backend.app.models.material import Material\n'
                                   'from backend.app.models.capacidade import CapacidadeFornecedor\n'
                                   'from backend.app.models.maquina import Maquina\n'
                                   'from backend.app.models.material_fornecedor import MaterialFornecedor\n'
                                   'from backend.app.models.solicitacao import SolicitacaoServico\n'
                                   '\n'
                                   '__all__ = [\n'
                                   '    "Empresa",\n'
                                   '    "ProcessoFabricacao",\n'
                                   '    "Material",\n'
                                   '    "CapacidadeFornecedor",\n'
                                   '    "Maquina",\n'
                                   '    "MaterialFornecedor",\n'
                                   '    "SolicitacaoServico",\n'
                                   ']\n',
 'backend/app/schemas/__init__.py': 'from backend.app.schemas.empresa import EmpresaCriacao, EmpresaLeitura, '
                                    'TipoEmpresa\n'
                                    'from backend.app.schemas.processo import ProcessoCriacao, ProcessoLeitura\n'
                                    'from backend.app.schemas.material import MaterialCriacao, MaterialLeitura\n'
                                    'from backend.app.schemas.capacidade import (\n'
                                    '    CapacidadeCriacao,\n'
                                    '    CapacidadeLeitura,\n'
                                    '    MaquinaCriacao,\n'
                                    '    MaquinaLeitura,\n'
                                    '    MaterialFornecedorCriacao,\n'
                                    '    MaterialFornecedorLeitura,\n'
                                    ')\n'
                                    'from backend.app.schemas.solicitacao import (\n'
                                    '    SolicitacaoServicoCriacao,\n'
                                    '    SolicitacaoServicoLeitura,\n'
                                    '    FornecedorCompativelLeitura,\n'
                                    ')\n'
                                    '\n'
                                    '__all__ = [\n'
                                    '    "EmpresaCriacao",\n'
                                    '    "EmpresaLeitura",\n'
                                    '    "TipoEmpresa",\n'
                                    '    "ProcessoCriacao",\n'
                                    '    "ProcessoLeitura",\n'
                                    '    "MaterialCriacao",\n'
                                    '    "MaterialLeitura",\n'
                                    '    "CapacidadeCriacao",\n'
                                    '    "CapacidadeLeitura",\n'
                                    '    "MaquinaCriacao",\n'
                                    '    "MaquinaLeitura",\n'
                                    '    "MaterialFornecedorCriacao",\n'
                                    '    "MaterialFornecedorLeitura",\n'
                                    '    "SolicitacaoServicoCriacao",\n'
                                    '    "SolicitacaoServicoLeitura",\n'
                                    '    "FornecedorCompativelLeitura",\n'
                                    ']\n'}
NEW_FILES = {'backend/app/api/rotas/solicitacoes.py': 'from __future__ import annotations\n'
                                          '\n'
                                          'from typing import Annotated\n'
                                          '\n'
                                          'from fastapi import APIRouter, Depends, HTTPException, status\n'
                                          'from sqlalchemy.orm import Session\n'
                                          '\n'
                                          'from backend.app.database.sessao import obter_banco\n'
                                          'from backend.app.models.solicitacao import SolicitacaoServico\n'
                                          'from backend.app.schemas.solicitacao import (\n'
                                          '    FornecedorCompativelLeitura,\n'
                                          '    SolicitacaoServicoCriacao,\n'
                                          '    SolicitacaoServicoLeitura,\n'
                                          ')\n'
                                          'from backend.app.services.compatibilidade import (\n'
                                          '    EmpresaNaoCliente,\n'
                                          '    MaterialSolicitacaoNaoEncontrado,\n'
                                          '    ProcessoSolicitacaoNaoEncontrado,\n'
                                          '    ServicoCompatibilidade,\n'
                                          '    SolicitacaoNaoEncontrada,\n'
                                          ')\n'
                                          '\n'
                                          'roteador = APIRouter(\n'
                                          '    prefix="/solicitacoes-servico",\n'
                                          '    tags=["solicitações de serviço"],\n'
                                          ')\n'
                                          'SessaoBanco = Annotated[Session, Depends(obter_banco)]\n'
                                          '\n'
                                          '\n'
                                          '@roteador.post(\n'
                                          '    "",\n'
                                          '    response_model=SolicitacaoServicoLeitura,\n'
                                          '    status_code=status.HTTP_201_CREATED,\n'
                                          ')\n'
                                          'def criar_solicitacao(\n'
                                          '    dados: SolicitacaoServicoCriacao,\n'
                                          '    banco: SessaoBanco,\n'
                                          ') -> SolicitacaoServicoLeitura:\n'
                                          '    try:\n'
                                          '        solicitacao = '
                                          'ServicoCompatibilidade(banco).criar_solicitacao(dados)\n'
                                          '    except EmpresaNaoCliente as exc:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_409_CONFLICT,\n'
                                          '            detail="empresa_nao_e_cliente",\n'
                                          '        ) from exc\n'
                                          '    except SolicitacaoNaoEncontrada as exc:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                          '            detail="empresa_cliente_nao_encontrada",\n'
                                          '        ) from exc\n'
                                          '    except ProcessoSolicitacaoNaoEncontrado as exc:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                          '            detail="processo_nao_encontrado",\n'
                                          '        ) from exc\n'
                                          '    except MaterialSolicitacaoNaoEncontrado as exc:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                          '            detail="material_nao_encontrado",\n'
                                          '        ) from exc\n'
                                          '\n'
                                          '    return SolicitacaoServicoLeitura.model_validate(solicitacao)\n'
                                          '\n'
                                          '\n'
                                          '@roteador.get(\n'
                                          '    "/{solicitacao_id}",\n'
                                          '    response_model=SolicitacaoServicoLeitura,\n'
                                          ')\n'
                                          'def obter_solicitacao(\n'
                                          '    solicitacao_id: int,\n'
                                          '    banco: SessaoBanco,\n'
                                          ') -> SolicitacaoServicoLeitura:\n'
                                          '    try:\n'
                                          '        solicitacao = ServicoCompatibilidade(banco).obter_solicitacao(\n'
                                          '            solicitacao_id\n'
                                          '        )\n'
                                          '    except SolicitacaoNaoEncontrada as exc:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                          '            detail="solicitacao_nao_encontrada",\n'
                                          '        ) from exc\n'
                                          '\n'
                                          '    return SolicitacaoServicoLeitura.model_validate(solicitacao)\n'
                                          '\n'
                                          '\n'
                                          '@roteador.get(\n'
                                          '    "/{solicitacao_id}/fornecedores-compativeis",\n'
                                          '    response_model=list[FornecedorCompativelLeitura],\n'
                                          ')\n'
                                          'def listar_fornecedores_compativeis(\n'
                                          '    solicitacao_id: int,\n'
                                          '    banco: SessaoBanco,\n'
                                          ') -> list[FornecedorCompativelLeitura]:\n'
                                          '    try:\n'
                                          '        itens = '
                                          'ServicoCompatibilidade(banco).listar_fornecedores_compativeis(\n'
                                          '            solicitacao_id\n'
                                          '        )\n'
                                          '    except SolicitacaoNaoEncontrada as exc:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                          '            detail="solicitacao_nao_encontrada",\n'
                                          '        ) from exc\n'
                                          '\n'
                                          '    solicitacao = banco.get(SolicitacaoServico, solicitacao_id)\n'
                                          '    if solicitacao is None:\n'
                                          '        raise HTTPException(\n'
                                          '            status_code=status.HTTP_404_NOT_FOUND,\n'
                                          '            detail="solicitacao_nao_encontrada",\n'
                                          '        )\n'
                                          '\n'
                                          '    return [\n'
                                          '        FornecedorCompativelLeitura(\n'
                                          '            empresa_id=empresa.id,\n'
                                          '            razao_social=empresa.razao_social,\n'
                                          '            tipo_empresa=empresa.tipo_empresa,\n'
                                          '            capacidade_id=capacidade.id,\n'
                                          '            processo_id=capacidade.processo_id,\n'
                                          '            material_id=solicitacao.material_id,\n'
                                          '            dimensao_x_maxima_mm=capacidade.dimensao_x_maxima_mm,\n'
                                          '            dimensao_y_maxima_mm=capacidade.dimensao_y_maxima_mm,\n'
                                          '            dimensao_z_maxima_mm=capacidade.dimensao_z_maxima_mm,\n'
                                          '            tolerancia_minima_mm=capacidade.tolerancia_minima_mm,\n'
                                          '        )\n'
                                          '        for empresa, capacidade in itens\n'
                                          '    ]\n',
 'backend/app/models/solicitacao.py': 'from __future__ import annotations\n'
                                      '\n'
                                      'from datetime import datetime\n'
                                      'from decimal import Decimal\n'
                                      '\n'
                                      'from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, '
                                      'String, Text, func\n'
                                      'from sqlalchemy.orm import Mapped, mapped_column\n'
                                      '\n'
                                      'from backend.app.database.base import Base\n'
                                      '\n'
                                      '\n'
                                      'class SolicitacaoServico(Base):\n'
                                      '    __tablename__ = "solicitacoes_servico"\n'
                                      '    __table_args__ = (\n'
                                      '        CheckConstraint(\n'
                                      '            "dimensao_x_maxima_mm > 0",\n'
                                      '            name="ck_solicitacoes_dimensao_x",\n'
                                      '        ),\n'
                                      '        CheckConstraint(\n'
                                      '            "dimensao_y_maxima_mm > 0",\n'
                                      '            name="ck_solicitacoes_dimensao_y",\n'
                                      '        ),\n'
                                      '        CheckConstraint(\n'
                                      '            "dimensao_z_maxima_mm > 0",\n'
                                      '            name="ck_solicitacoes_dimensao_z",\n'
                                      '        ),\n'
                                      '        CheckConstraint(\n'
                                      '            "tolerancia_requerida_mm > 0",\n'
                                      '            name="ck_solicitacoes_tolerancia",\n'
                                      '        ),\n'
                                      '        CheckConstraint(\n'
                                      '            "quantidade > 0",\n'
                                      '            name="ck_solicitacoes_quantidade",\n'
                                      '        ),\n'
                                      '        CheckConstraint(\n'
                                      '            "status IN (\'aberta\', \'encerrada\', \'cancelada\')",\n'
                                      '            name="ck_solicitacoes_status",\n'
                                      '        ),\n'
                                      '    )\n'
                                      '\n'
                                      '    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)\n'
                                      '    empresa_cliente_id: Mapped[int] = mapped_column(\n'
                                      '        ForeignKey("empresas.id", ondelete="RESTRICT"),\n'
                                      '        nullable=False,\n'
                                      '        index=True,\n'
                                      '    )\n'
                                      '    processo_id: Mapped[int] = mapped_column(\n'
                                      '        ForeignKey("processos_fabricacao.id", ondelete="RESTRICT"),\n'
                                      '        nullable=False,\n'
                                      '        index=True,\n'
                                      '    )\n'
                                      '    material_id: Mapped[int] = mapped_column(\n'
                                      '        ForeignKey("materiais.id", ondelete="RESTRICT"),\n'
                                      '        nullable=False,\n'
                                      '        index=True,\n'
                                      '    )\n'
                                      '    dimensao_x_maxima_mm: Mapped[Decimal] = mapped_column(\n'
                                      '        Numeric(12, 3),\n'
                                      '        nullable=False,\n'
                                      '    )\n'
                                      '    dimensao_y_maxima_mm: Mapped[Decimal] = mapped_column(\n'
                                      '        Numeric(12, 3),\n'
                                      '        nullable=False,\n'
                                      '    )\n'
                                      '    dimensao_z_maxima_mm: Mapped[Decimal] = mapped_column(\n'
                                      '        Numeric(12, 3),\n'
                                      '        nullable=False,\n'
                                      '    )\n'
                                      '    tolerancia_requerida_mm: Mapped[Decimal] = mapped_column(\n'
                                      '        Numeric(12, 4),\n'
                                      '        nullable=False,\n'
                                      '    )\n'
                                      '    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)\n'
                                      '    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)\n'
                                      '    status: Mapped[str] = mapped_column(\n'
                                      '        String(16),\n'
                                      '        nullable=False,\n'
                                      '        default="aberta",\n'
                                      '        server_default="aberta",\n'
                                      '    )\n'
                                      '    criada_em: Mapped[datetime] = mapped_column(\n'
                                      '        DateTime(timezone=True),\n'
                                      '        server_default=func.now(),\n'
                                      '        nullable=False,\n'
                                      '    )\n',
 'backend/app/repositories/compatibilidade.py': 'from __future__ import annotations\n'
                                                '\n'
                                                'from sqlalchemy import select\n'
                                                'from sqlalchemy.orm import Session\n'
                                                '\n'
                                                'from backend.app.models.capacidade import CapacidadeFornecedor\n'
                                                'from backend.app.models.empresa import Empresa\n'
                                                'from backend.app.models.material_fornecedor import '
                                                'MaterialFornecedor\n'
                                                'from backend.app.models.solicitacao import SolicitacaoServico\n'
                                                '\n'
                                                '\n'
                                                'class RepositorioCompatibilidade:\n'
                                                '    def __init__(self, banco: Session) -> None:\n'
                                                '        self.banco = banco\n'
                                                '\n'
                                                '    def obter_solicitacao(self, solicitacao_id: int) -> '
                                                'SolicitacaoServico | None:\n'
                                                '        return self.banco.get(SolicitacaoServico, solicitacao_id)\n'
                                                '\n'
                                                '    def criar_solicitacao(self, solicitacao: SolicitacaoServico) -> '
                                                'SolicitacaoServico:\n'
                                                '        self.banco.add(solicitacao)\n'
                                                '        self.banco.commit()\n'
                                                '        self.banco.refresh(solicitacao)\n'
                                                '        return solicitacao\n'
                                                '\n'
                                                '    def listar_fornecedores_compativeis(\n'
                                                '        self,\n'
                                                '        solicitacao: SolicitacaoServico,\n'
                                                '    ) -> list[tuple[Empresa, CapacidadeFornecedor]]:\n'
                                                '        consulta = (\n'
                                                '            select(Empresa, CapacidadeFornecedor)\n'
                                                '            .join(\n'
                                                '                CapacidadeFornecedor,\n'
                                                '                CapacidadeFornecedor.empresa_id == Empresa.id,\n'
                                                '            )\n'
                                                '            .join(\n'
                                                '                MaterialFornecedor,\n'
                                                '                MaterialFornecedor.empresa_id == Empresa.id,\n'
                                                '            )\n'
                                                '            .where(\n'
                                                '                Empresa.tipo_empresa.in_(("fornecedor", "ambos")),\n'
                                                '                CapacidadeFornecedor.processo_id == '
                                                'solicitacao.processo_id,\n'
                                                '                MaterialFornecedor.material_id == '
                                                'solicitacao.material_id,\n'
                                                '                CapacidadeFornecedor.dimensao_x_maxima_mm\n'
                                                '                >= solicitacao.dimensao_x_maxima_mm,\n'
                                                '                CapacidadeFornecedor.dimensao_y_maxima_mm\n'
                                                '                >= solicitacao.dimensao_y_maxima_mm,\n'
                                                '                CapacidadeFornecedor.dimensao_z_maxima_mm\n'
                                                '                >= solicitacao.dimensao_z_maxima_mm,\n'
                                                '                CapacidadeFornecedor.tolerancia_minima_mm\n'
                                                '                <= solicitacao.tolerancia_requerida_mm,\n'
                                                '            )\n'
                                                '            .order_by(Empresa.id)\n'
                                                '        )\n'
                                                '        return list(self.banco.execute(consulta).all())\n',
 'backend/app/schemas/solicitacao.py': 'from __future__ import annotations\n'
                                       '\n'
                                       'from datetime import datetime\n'
                                       'from decimal import Decimal\n'
                                       '\n'
                                       'from pydantic import BaseModel, ConfigDict, Field\n'
                                       '\n'
                                       '\n'
                                       'class SolicitacaoServicoCriacao(BaseModel):\n'
                                       '    empresa_cliente_id: int = Field(gt=0)\n'
                                       '    processo_id: int = Field(gt=0)\n'
                                       '    material_id: int = Field(gt=0)\n'
                                       '    dimensao_x_maxima_mm: Decimal = Field(gt=0, max_digits=12, '
                                       'decimal_places=3)\n'
                                       '    dimensao_y_maxima_mm: Decimal = Field(gt=0, max_digits=12, '
                                       'decimal_places=3)\n'
                                       '    dimensao_z_maxima_mm: Decimal = Field(gt=0, max_digits=12, '
                                       'decimal_places=3)\n'
                                       '    tolerancia_requerida_mm: Decimal = Field(gt=0, max_digits=12, '
                                       'decimal_places=4)\n'
                                       '    quantidade: int = Field(gt=0, le=10_000_000)\n'
                                       '    observacoes: str | None = Field(default=None, max_length=5000)\n'
                                       '\n'
                                       '\n'
                                       'class SolicitacaoServicoLeitura(BaseModel):\n'
                                       '    model_config = ConfigDict(from_attributes=True)\n'
                                       '\n'
                                       '    id: int\n'
                                       '    empresa_cliente_id: int\n'
                                       '    processo_id: int\n'
                                       '    material_id: int\n'
                                       '    dimensao_x_maxima_mm: Decimal\n'
                                       '    dimensao_y_maxima_mm: Decimal\n'
                                       '    dimensao_z_maxima_mm: Decimal\n'
                                       '    tolerancia_requerida_mm: Decimal\n'
                                       '    quantidade: int\n'
                                       '    observacoes: str | None\n'
                                       '    status: str\n'
                                       '    criada_em: datetime\n'
                                       '\n'
                                       '\n'
                                       'class FornecedorCompativelLeitura(BaseModel):\n'
                                       '    empresa_id: int\n'
                                       '    razao_social: str\n'
                                       '    tipo_empresa: str\n'
                                       '    capacidade_id: int\n'
                                       '    processo_id: int\n'
                                       '    material_id: int\n'
                                       '    dimensao_x_maxima_mm: Decimal\n'
                                       '    dimensao_y_maxima_mm: Decimal\n'
                                       '    dimensao_z_maxima_mm: Decimal\n'
                                       '    tolerancia_minima_mm: Decimal\n',
 'backend/app/services/compatibilidade.py': 'from __future__ import annotations\n'
                                            '\n'
                                            'from sqlalchemy.exc import IntegrityError\n'
                                            'from sqlalchemy.orm import Session\n'
                                            '\n'
                                            'from backend.app.models.empresa import Empresa\n'
                                            'from backend.app.models.solicitacao import SolicitacaoServico\n'
                                            'from backend.app.repositories.compatibilidade import '
                                            'RepositorioCompatibilidade\n'
                                            'from backend.app.schemas.solicitacao import SolicitacaoServicoCriacao\n'
                                            '\n'
                                            '\n'
                                            'class EmpresaNaoCliente(ValueError):\n'
                                            '    pass\n'
                                            '\n'
                                            '\n'
                                            'class ProcessoSolicitacaoNaoEncontrado(LookupError):\n'
                                            '    pass\n'
                                            '\n'
                                            '\n'
                                            'class MaterialSolicitacaoNaoEncontrado(LookupError):\n'
                                            '    pass\n'
                                            '\n'
                                            '\n'
                                            'class SolicitacaoNaoEncontrada(LookupError):\n'
                                            '    pass\n'
                                            '\n'
                                            '\n'
                                            'class ServicoCompatibilidade:\n'
                                            '    def __init__(self, banco: Session) -> None:\n'
                                            '        self.banco = banco\n'
                                            '        self.repositorio = RepositorioCompatibilidade(banco)\n'
                                            '\n'
                                            '    def criar_solicitacao(\n'
                                            '        self,\n'
                                            '        dados: SolicitacaoServicoCriacao,\n'
                                            '    ) -> SolicitacaoServico:\n'
                                            '        empresa = self.banco.get(Empresa, dados.empresa_cliente_id)\n'
                                            '        if empresa is None:\n'
                                            '            raise SolicitacaoNaoEncontrada(dados.empresa_cliente_id)\n'
                                            '\n'
                                            '        if empresa.tipo_empresa not in {"cliente", "ambos"}:\n'
                                            '            raise EmpresaNaoCliente(dados.empresa_cliente_id)\n'
                                            '\n'
                                            '        from backend.app.models.material import Material\n'
                                            '        from backend.app.models.processo import ProcessoFabricacao\n'
                                            '\n'
                                            '        if self.banco.get(ProcessoFabricacao, dados.processo_id) is '
                                            'None:\n'
                                            '            raise ProcessoSolicitacaoNaoEncontrado(dados.processo_id)\n'
                                            '\n'
                                            '        if self.banco.get(Material, dados.material_id) is None:\n'
                                            '            raise MaterialSolicitacaoNaoEncontrado(dados.material_id)\n'
                                            '\n'
                                            '        solicitacao = SolicitacaoServico(\n'
                                            '            empresa_cliente_id=dados.empresa_cliente_id,\n'
                                            '            processo_id=dados.processo_id,\n'
                                            '            material_id=dados.material_id,\n'
                                            '            dimensao_x_maxima_mm=dados.dimensao_x_maxima_mm,\n'
                                            '            dimensao_y_maxima_mm=dados.dimensao_y_maxima_mm,\n'
                                            '            dimensao_z_maxima_mm=dados.dimensao_z_maxima_mm,\n'
                                            '            tolerancia_requerida_mm=dados.tolerancia_requerida_mm,\n'
                                            '            quantidade=dados.quantidade,\n'
                                            '            observacoes=dados.observacoes,\n'
                                            '        )\n'
                                            '\n'
                                            '        try:\n'
                                            '            return self.repositorio.criar_solicitacao(solicitacao)\n'
                                            '        except IntegrityError:\n'
                                            '            self.banco.rollback()\n'
                                            '            raise\n'
                                            '\n'
                                            '    def obter_solicitacao(self, solicitacao_id: int) -> '
                                            'SolicitacaoServico:\n'
                                            '        solicitacao = self.repositorio.obter_solicitacao(solicitacao_id)\n'
                                            '        if solicitacao is None:\n'
                                            '            raise SolicitacaoNaoEncontrada(solicitacao_id)\n'
                                            '        return solicitacao\n'
                                            '\n'
                                            '    def listar_fornecedores_compativeis(\n'
                                            '        self,\n'
                                            '        solicitacao_id: int,\n'
                                            '    ) -> list[tuple[Empresa, object]]:\n'
                                            '        solicitacao = self.obter_solicitacao(solicitacao_id)\n'
                                            '        return '
                                            'self.repositorio.listar_fornecedores_compativeis(solicitacao)\n',
 'tests/test_compatibilidade_fornecedores.py': 'from collections.abc import Generator\n'
                                               '\n'
                                               'import pytest\n'
                                               'from fastapi.testclient import TestClient\n'
                                               'from sqlalchemy import create_engine\n'
                                               'from sqlalchemy.orm import Session, sessionmaker\n'
                                               'from sqlalchemy.pool import StaticPool\n'
                                               '\n'
                                               'from backend.app.database.base import Base\n'
                                               'from backend.app.database.sessao import obter_banco\n'
                                               'from backend.app.principal import app\n'
                                               '\n'
                                               '\n'
                                               '@pytest.fixture()\n'
                                               'def cliente() -> Generator[TestClient, None, None]:\n'
                                               '    engine = create_engine(\n'
                                               '        "sqlite://",\n'
                                               '        connect_args={"check_same_thread": False},\n'
                                               '        poolclass=StaticPool,\n'
                                               '    )\n'
                                               '    SessaoTeste = sessionmaker(\n'
                                               '        bind=engine,\n'
                                               '        autoflush=False,\n'
                                               '        expire_on_commit=False,\n'
                                               '        class_=Session,\n'
                                               '    )\n'
                                               '    Base.metadata.create_all(bind=engine)\n'
                                               '\n'
                                               '    def substituir_banco() -> Generator[Session, None, None]:\n'
                                               '        banco = SessaoTeste()\n'
                                               '        try:\n'
                                               '            yield banco\n'
                                               '        finally:\n'
                                               '            banco.close()\n'
                                               '\n'
                                               '    app.dependency_overrides[obter_banco] = substituir_banco\n'
                                               '\n'
                                               '    with TestClient(app) as test_client:\n'
                                               '        yield test_client\n'
                                               '\n'
                                               '    app.dependency_overrides.clear()\n'
                                               '    Base.metadata.drop_all(bind=engine)\n'
                                               '    engine.dispose()\n'
                                               '\n'
                                               '\n'
                                               'def cadastrar_empresa(cliente: TestClient, documento: str, tipo: str, '
                                               'nome: str) -> int:\n'
                                               '    resposta = cliente.post(\n'
                                               '        "/api/v1/empresas",\n'
                                               '        json={\n'
                                               '            "razao_social": nome,\n'
                                               '            "documento": documento,\n'
                                               '            "tipo_empresa": tipo,\n'
                                               '        },\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 201\n'
                                               '    return resposta.json()["id"]\n'
                                               '\n'
                                               '\n'
                                               'def cadastrar_catalogo(cliente: TestClient) -> tuple[int, int]:\n'
                                               '    processo = cliente.post(\n'
                                               '        "/api/v1/processos-fabricacao",\n'
                                               '        json={\n'
                                               '            "codigo": "usinagem_cnc",\n'
                                               '            "nome": "Usinagem CNC",\n'
                                               '        },\n'
                                               '    )\n'
                                               '    material = cliente.post(\n'
                                               '        "/api/v1/materiais",\n'
                                               '        json={\n'
                                               '            "codigo": "aluminio_6061",\n'
                                               '            "nome": "Alumínio 6061",\n'
                                               '            "familia": "alumínio",\n'
                                               '        },\n'
                                               '    )\n'
                                               '    assert processo.status_code == 201\n'
                                               '    assert material.status_code == 201\n'
                                               '    return processo.json()["id"], material.json()["id"]\n'
                                               '\n'
                                               '\n'
                                               'def cadastrar_capacidade_fornecedor(\n'
                                               '    cliente: TestClient,\n'
                                               '    fornecedor_id: int,\n'
                                               '    processo_id: int,\n'
                                               '    material_id: int,\n'
                                               ') -> None:\n'
                                               '    capacidade = cliente.post(\n'
                                               '        f"/api/v1/empresas/{fornecedor_id}/capacidades",\n'
                                               '        json={\n'
                                               '            "processo_id": processo_id,\n'
                                               '            "dimensao_x_maxima_mm": "800.000",\n'
                                               '            "dimensao_y_maxima_mm": "500.000",\n'
                                               '            "dimensao_z_maxima_mm": "450.000",\n'
                                               '            "tolerancia_minima_mm": "0.0200",\n'
                                               '        },\n'
                                               '    )\n'
                                               '    vinculo = cliente.post(\n'
                                               '        f"/api/v1/empresas/{fornecedor_id}/materiais",\n'
                                               '        json={"material_id": material_id},\n'
                                               '    )\n'
                                               '    assert capacidade.status_code == 201\n'
                                               '    assert vinculo.status_code == 201\n'
                                               '\n'
                                               '\n'
                                               'def criar_solicitacao(\n'
                                               '    cliente: TestClient,\n'
                                               '    cliente_id: int,\n'
                                               '    processo_id: int,\n'
                                               '    material_id: int,\n'
                                               '    *,\n'
                                               '    x: str = "600.000",\n'
                                               '    y: str = "400.000",\n'
                                               '    z: str = "300.000",\n'
                                               '    tolerancia: str = "0.0200",\n'
                                               ') -> int:\n'
                                               '    resposta = cliente.post(\n'
                                               '        "/api/v1/solicitacoes-servico",\n'
                                               '        json={\n'
                                               '            "empresa_cliente_id": cliente_id,\n'
                                               '            "processo_id": processo_id,\n'
                                               '            "material_id": material_id,\n'
                                               '            "dimensao_x_maxima_mm": x,\n'
                                               '            "dimensao_y_maxima_mm": y,\n'
                                               '            "dimensao_z_maxima_mm": z,\n'
                                               '            "tolerancia_requerida_mm": tolerancia,\n'
                                               '            "quantidade": 10,\n'
                                               '        },\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 201\n'
                                               '    return resposta.json()["id"]\n'
                                               '\n'
                                               '\n'
                                               'def '
                                               'test_fornecedor_compativel_por_processo_material_dimensoes_e_tolerancia(\n'
                                               '    cliente: TestClient,\n'
                                               ') -> None:\n'
                                               '    cliente_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "98765432000110",\n'
                                               '        "cliente",\n'
                                               '        "Cliente Mecânico Ltda",\n'
                                               '    )\n'
                                               '    fornecedor_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "12345678000190",\n'
                                               '        "fornecedor",\n'
                                               '        "Fornecedor CNC Ltda",\n'
                                               '    )\n'
                                               '    processo_id, material_id = cadastrar_catalogo(cliente)\n'
                                               '    cadastrar_capacidade_fornecedor(\n'
                                               '        cliente,\n'
                                               '        fornecedor_id,\n'
                                               '        processo_id,\n'
                                               '        material_id,\n'
                                               '    )\n'
                                               '\n'
                                               '    solicitacao_id = criar_solicitacao(\n'
                                               '        cliente,\n'
                                               '        cliente_id,\n'
                                               '        processo_id,\n'
                                               '        material_id,\n'
                                               '    )\n'
                                               '\n'
                                               '    resposta = cliente.get(\n'
                                               '        '
                                               'f"/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis"\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 200\n'
                                               '    itens = resposta.json()\n'
                                               '    assert len(itens) == 1\n'
                                               '    assert itens[0]["empresa_id"] == fornecedor_id\n'
                                               '    assert itens[0]["processo_id"] == processo_id\n'
                                               '    assert itens[0]["material_id"] == material_id\n'
                                               '\n'
                                               '\n'
                                               '@pytest.mark.parametrize(\n'
                                               '    "alteracoes",\n'
                                               '    [\n'
                                               '        {"x": "900.000"},\n'
                                               '        {"y": "600.000"},\n'
                                               '        {"z": "500.000"},\n'
                                               '        {"tolerancia": "0.0100"},\n'
                                               '    ],\n'
                                               ')\n'
                                               'def test_requisito_fora_da_capacidade_nao_encontra_fornecedor(\n'
                                               '    cliente: TestClient,\n'
                                               '    alteracoes: dict[str, str],\n'
                                               ') -> None:\n'
                                               '    cliente_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "98765432000110",\n'
                                               '        "cliente",\n'
                                               '        "Cliente Mecânico Ltda",\n'
                                               '    )\n'
                                               '    fornecedor_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "12345678000190",\n'
                                               '        "fornecedor",\n'
                                               '        "Fornecedor CNC Ltda",\n'
                                               '    )\n'
                                               '    processo_id, material_id = cadastrar_catalogo(cliente)\n'
                                               '    cadastrar_capacidade_fornecedor(\n'
                                               '        cliente,\n'
                                               '        fornecedor_id,\n'
                                               '        processo_id,\n'
                                               '        material_id,\n'
                                               '    )\n'
                                               '\n'
                                               '    solicitacao_id = criar_solicitacao(\n'
                                               '        cliente,\n'
                                               '        cliente_id,\n'
                                               '        processo_id,\n'
                                               '        material_id,\n'
                                               '        **alteracoes,\n'
                                               '    )\n'
                                               '\n'
                                               '    resposta = cliente.get(\n'
                                               '        '
                                               'f"/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis"\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 200\n'
                                               '    assert resposta.json() == []\n'
                                               '\n'
                                               '\n'
                                               'def test_material_incompativel_nao_encontra_fornecedor(cliente: '
                                               'TestClient) -> None:\n'
                                               '    cliente_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "98765432000110",\n'
                                               '        "cliente",\n'
                                               '        "Cliente Mecânico Ltda",\n'
                                               '    )\n'
                                               '    fornecedor_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "12345678000190",\n'
                                               '        "fornecedor",\n'
                                               '        "Fornecedor CNC Ltda",\n'
                                               '    )\n'
                                               '    processo_id, material_id = cadastrar_catalogo(cliente)\n'
                                               '    cadastrar_capacidade_fornecedor(\n'
                                               '        cliente,\n'
                                               '        fornecedor_id,\n'
                                               '        processo_id,\n'
                                               '        material_id,\n'
                                               '    )\n'
                                               '\n'
                                               '    outro_material = cliente.post(\n'
                                               '        "/api/v1/materiais",\n'
                                               '        json={"codigo": "aco_1045", "nome": "Aço 1045"},\n'
                                               '    )\n'
                                               '    assert outro_material.status_code == 201\n'
                                               '\n'
                                               '    solicitacao_id = criar_solicitacao(\n'
                                               '        cliente,\n'
                                               '        cliente_id,\n'
                                               '        processo_id,\n'
                                               '        outro_material.json()["id"],\n'
                                               '    )\n'
                                               '\n'
                                               '    resposta = cliente.get(\n'
                                               '        '
                                               'f"/api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis"\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 200\n'
                                               '    assert resposta.json() == []\n'
                                               '\n'
                                               '\n'
                                               'def test_empresa_fornecedora_nao_pode_criar_solicitacao_de_cliente(\n'
                                               '    cliente: TestClient,\n'
                                               ') -> None:\n'
                                               '    fornecedor_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "12345678000190",\n'
                                               '        "fornecedor",\n'
                                               '        "Fornecedor CNC Ltda",\n'
                                               '    )\n'
                                               '    processo_id, material_id = cadastrar_catalogo(cliente)\n'
                                               '\n'
                                               '    resposta = cliente.post(\n'
                                               '        "/api/v1/solicitacoes-servico",\n'
                                               '        json={\n'
                                               '            "empresa_cliente_id": fornecedor_id,\n'
                                               '            "processo_id": processo_id,\n'
                                               '            "material_id": material_id,\n'
                                               '            "dimensao_x_maxima_mm": "100.000",\n'
                                               '            "dimensao_y_maxima_mm": "100.000",\n'
                                               '            "dimensao_z_maxima_mm": "100.000",\n'
                                               '            "tolerancia_requerida_mm": "0.0500",\n'
                                               '            "quantidade": 1,\n'
                                               '        },\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 409\n'
                                               '    assert resposta.json()["detail"] == "empresa_nao_e_cliente"\n'
                                               '\n'
                                               '\n'
                                               'def test_solicitacao_com_dimensao_zero_e_rejeitada(cliente: '
                                               'TestClient) -> None:\n'
                                               '    cliente_id = cadastrar_empresa(\n'
                                               '        cliente,\n'
                                               '        "98765432000110",\n'
                                               '        "cliente",\n'
                                               '        "Cliente Mecânico Ltda",\n'
                                               '    )\n'
                                               '    processo_id, material_id = cadastrar_catalogo(cliente)\n'
                                               '\n'
                                               '    resposta = cliente.post(\n'
                                               '        "/api/v1/solicitacoes-servico",\n'
                                               '        json={\n'
                                               '            "empresa_cliente_id": cliente_id,\n'
                                               '            "processo_id": processo_id,\n'
                                               '            "material_id": material_id,\n'
                                               '            "dimensao_x_maxima_mm": "0",\n'
                                               '            "dimensao_y_maxima_mm": "100.000",\n'
                                               '            "dimensao_z_maxima_mm": "100.000",\n'
                                               '            "tolerancia_requerida_mm": "0.0500",\n'
                                               '            "quantidade": 1,\n'
                                               '        },\n'
                                               '    )\n'
                                               '    assert resposta.status_code == 422\n'}


def normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(normalize(content), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def is_cgx_root(root: Path) -> bool:
    return (root / "src" / "cgx").exists() or (root / "src" / "cgx_platform").exists()


def validate_ast(root: Path, rels: list[str]) -> list[str]:
    errors = []
    for rel in rels:
        if not rel.endswith(".py"):
            continue
        path = root / rel
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            errors.append(f"{rel}: {type(exc).__name__}: {exc}")
    return errors


def main() -> int:
    root = Path.cwd().resolve()
    print(f"{PROJECT_LABEL} — V0.1 D5 Requisitos Técnicos e Compatibilidade")
    print(f"REVISION= {REVISION}")
    print(f"ROOT= {root}")

    if is_cgx_root(root):
        print("ERRO: esta pasta parece ser a raiz do CGX Platform.")
        print("Execute este arquivo somente na raiz do projeto MEC-Servicos.")
        return 20

    conflicts = []
    for rel, expected_hash in EXPECTED_D4_HASHES.items():
        path = root / rel
        if not path.exists():
            conflicts.append(rel)
            continue
        try:
            current_hash = sha256_text(path.read_text(encoding="utf-8"))
        except Exception:
            conflicts.append(rel)
            continue
        if current_hash != expected_hash:
            target = UPDATED_FILES.get(rel)
            if target is not None and current_hash == sha256_text(target):
                continue
            conflicts.append(rel)

    already_target = []
    for rel, expected_content in NEW_FILES.items():
        path = root / rel
        if not path.exists():
            continue
        if normalize(path.read_text(encoding="utf-8")) == normalize(expected_content):
            already_target.append(rel)
        else:
            conflicts.append(rel)

    if conflicts:
        conflicts = sorted(set(conflicts))
        print("ERRO: foram encontrados arquivos divergentes da baseline D4.")
        print("Nenhum arquivo foi alterado.")
        for rel in conflicts:
            print(f"  CONFLICT: {rel}")
        atomic_write(
            root / REPORT_TXT,
            "\n".join([
                f"{PROJECT_LABEL} — V0.1 D5",
                f"REVISION={REVISION}",
                f"ROOT={root}",
                "STATUS=CONFLICT",
                "NO_FILES_CHANGED=True",
                "",
                "CONFLICTS:",
                *[f"  {item}" for item in conflicts],
                "",
            ]),
        )
        atomic_write(
            root / REPORT_JSON,
            json.dumps({
                "project": PROJECT_LABEL,
                "revision": REVISION,
                "status": "CONFLICT",
                "root": str(root),
                "conflicts": conflicts,
                "no_files_changed": True,
            }, indent=2, ensure_ascii=False) + "\n",
        )
        return 30

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = root / BACKUP_ROOT / f"V0_1_D5_REQUISITOS_COMPATIBILIDADE_{stamp}"
    backed_up = []
    changed = []
    created = []

    database_path = root / "data" / "mec_servicos.db"
    if database_path.exists():
        destination = backup_dir / "data" / database_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(database_path, destination)
        backed_up.append(str(database_path.relative_to(root)))

    for rel, content in UPDATED_FILES.items():
        path = root / rel
        destination = backup_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        atomic_write(path, content)
        changed.append(rel)
        backed_up.append(rel)

    for rel, content in NEW_FILES.items():
        path = root / rel
        if not path.exists():
            atomic_write(path, content)
            created.append(rel)

    targets = list(UPDATED_FILES) + list(NEW_FILES)
    missing = [rel for rel in targets if not (root / rel).exists()]
    mismatches = []
    for rel, expected in {**UPDATED_FILES, **NEW_FILES}.items():
        path = root / rel
        if path.exists() and normalize(path.read_text(encoding="utf-8")) != normalize(expected):
            mismatches.append(rel)

    ast_errors = validate_ast(root, targets)
    files_ok = not missing and not mismatches
    ast_ok = not ast_errors
    status = "OK" if files_ok and ast_ok else "FAILED"

    final_hashes = {}
    for rel in targets:
        path = root / rel
        if path.exists():
            final_hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))

    report = {
        "project": PROJECT_LABEL,
        "revision": REVISION,
        "script": SCRIPT_NAME,
        "timestamp_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "root": str(root),
        "status": status,
        "d4_baseline_verified": True,
        "files_ok": files_ok,
        "ast_ok": ast_ok,
        "changed": changed,
        "created": created,
        "already_target": already_target,
        "backed_up": backed_up,
        "backup_dir": str(backup_dir) if backed_up else None,
        "missing": missing,
        "content_mismatch": mismatches,
        "ast_errors": ast_errors,
        "database_changed_by_script": False,
        "database_backup_created": database_path.exists(),
        "new_table": "solicitacoes_servico",
        "new_endpoints": [
            "POST /api/v1/solicitacoes-servico",
            "GET /api/v1/solicitacoes-servico/{solicitacao_id}",
            "GET /api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis",
        ],
        "compatibility_rules": [
            "empresa fornecedora deve ser do tipo fornecedor ou ambos",
            "processo do fornecedor deve ser igual ao processo solicitado",
            "material deve estar vinculado ao fornecedor",
            "X requerido <= X máximo do fornecedor",
            "Y requerido <= Y máximo do fornecedor",
            "Z requerido <= Z máximo do fornecedor",
            "tolerância mínima do fornecedor <= tolerância requerida",
        ],
        "dimensional_rotation": "não implementada nesta etapa",
        "target_hashes_sha256": final_hashes,
    }

    atomic_write(
        root / REPORT_JSON,
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    )
    atomic_write(
        root / REPORT_TXT,
        "\n".join([
            f"{PROJECT_LABEL} — V0.1 D5",
            f"REVISION={REVISION}",
            f"ROOT={root}",
            "",
            f"STATUS={status}",
            "D4_BASELINE_VERIFIED=True",
            f"FILES_OK={files_ok}",
            f"AST_OK={ast_ok}",
            f"CHANGED={len(changed)}",
            f"CREATED={len(created)}",
            f"ALREADY_TARGET={len(already_target)}",
            f"BACKED_UP={len(backed_up)}",
            "DATABASE_CHANGED_BY_SCRIPT=False",
            "",
            "NOVA_TABELA:",
            "  solicitacoes_servico",
            "",
            "NOVOS_ENDPOINTS:",
            "  POST /api/v1/solicitacoes-servico",
            "  GET /api/v1/solicitacoes-servico/{solicitacao_id}",
            "  GET /api/v1/solicitacoes-servico/{solicitacao_id}/fornecedores-compativeis",
            "",
            "REGRAS_DE_COMPATIBILIDADE:",
            "  fornecedor = fornecedor ou ambos",
            "  processo = processo solicitado",
            "  material = material vinculado ao fornecedor",
            "  X requerido <= X máximo",
            "  Y requerido <= Y máximo",
            "  Z requerido <= Z máximo",
            "  tolerância mínima do fornecedor <= tolerância requerida",
            "",
            "REGRA_DIMENSIONAL:",
            "  correspondência direta dos eixos",
            "  rotação automática entre eixos = não implementada no D5",
            "",
            "PROXIMO:",
            "  1. python -m pytest",
            "  2. python -m uvicorn backend.app.principal:app --reload",
            "  3. validar o endpoint de compatibilidade com o banco real",
            "",
        ]),
    )

    print(f"FILES_OK= {files_ok}")
    print(f"AST_OK= {ast_ok}")
    print(f"CHANGED= {len(changed)}")
    print(f"CREATED= {len(created)}")
    print(f"ALREADY_TARGET= {len(already_target)}")
    print(f"BACKED_UP= {len(backed_up)}")
    print("DATABASE_CHANGED_BY_SCRIPT= False")
    if backed_up:
        print(f"BACKUP_DIR= {backup_dir}")
    print(f"REPORT= {root / REPORT_TXT}")
    print(f"JSON= {root / REPORT_JSON}")

    if not files_ok or not ast_ok:
        print("ERRO: a validação estática do D5 falhou.")
        return 40

    print("D5_REQUISITOS_COMPATIBILIDADE_APPLIED= True")
    print("SOLICITACAO_SERVICO_PREPARADA= True")
    print("MOTOR_COMPATIBILIDADE_PREPARADO= True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
