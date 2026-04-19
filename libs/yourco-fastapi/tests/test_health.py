from fastapi import FastAPI
from fastapi.testclient import TestClient
from yourco_fastapi import AppConfig, apply_health_endpoints


def test_health_returns_ok() -> None:
    app = FastAPI()
    apply_health_endpoints(app, AppConfig(service_name="orders"))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_returns_config_fields() -> None:
    app = FastAPI()
    apply_health_endpoints(
        app,
        AppConfig(service_name="orders", version="1.2.3", environment="staging"),
    )
    client = TestClient(app)

    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "service": "orders",
        "version": "1.2.3",
        "environment": "staging",
    }
