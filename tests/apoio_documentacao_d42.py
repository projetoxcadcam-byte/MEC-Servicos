"""Documentação revisada explícita para os cenários antigos de cotação."""
from hashlib import sha256
from uuid import uuid4

from backend.app.core.armazenamento_acesso import UsuarioAcesso
from backend.app.models.arquivo_tecnico import ArquivoTecnico
from backend.app.schemas.documentacao_cotacao import RegistroDocumentacao
from backend.app.services.arquivo_tecnico import ServicoArquivoTecnico
from backend.app.services.documentacao_cotacao import ServicoDocumentacaoCotacao


def liberar_arquivo_qa(banco, arquivo_id):
    item = banco.get(ArquivoTecnico, arquivo_id)
    return ServicoDocumentacaoCotacao(banco).registrar(arquivo_id, RegistroDocumentacao(
        acao="liberar", versao=0, sha256=item.sha256, registro_interno="Documento neutro conferido no cenário de teste",
        revisado_sem_contatos=True, chave_operacao=uuid4()),
        UsuarioAcesso(1, "Administrador de teste", "admin@teste.local", "admin", None, False))


def preparar_documentacao_qa(banco, solicitacao_id):
    raiz = ServicoArquivoTecnico(banco).storage_root
    raiz.mkdir(parents=True, exist_ok=True)
    caminho = raiz / (uuid4().hex + ".pdf")
    conteudo = b"%PDF-1.4\nDesenho tecnico neutro para teste de cotacao\n%%EOF"
    caminho.write_bytes(conteudo)
    item = ArquivoTecnico(solicitacao_id=solicitacao_id, nome_original="desenho.pdf", extensao=".pdf",
        content_type="application/pdf", tamanho_bytes=len(conteudo), sha256=sha256(conteudo).hexdigest(),
        caminho_arquivo=str(caminho), ativo=True)
    banco.add(item); banco.commit()
    liberar_arquivo_qa(banco, item.id)
    return item
