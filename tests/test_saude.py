from fastapi.testclient import TestClient

from backend.app.principal import app


def test_raiz() -> None:
    with TestClient(app) as cliente:
        resposta = cliente.get("/")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["status"] == "em_execucao"
    assert dados["versao"] == "0.1.0"


def test_saude() -> None:
    with TestClient(app) as cliente:
        resposta = cliente.get("/api/v1/saude")
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["status"] == "ok"
    assert dados["versao"] == "0.1.0"
