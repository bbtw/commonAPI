from demo_service.main import app
from fastapi.testclient import TestClient
from yourco_fastapi import REQUEST_ID_HEADER

client = TestClient(app, raise_server_exceptions=False)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers[REQUEST_ID_HEADER]


def test_version() -> None:
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "demo-service"
    assert body["version"] == "0.1.0"


def test_hello_route_with_supplied_request_id() -> None:
    response = client.get(
        "/hello",
        params={"name": "brian"},
        headers={REQUEST_ID_HEADER: "smoke-test-id"},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "hello, brian"}
    assert response.headers[REQUEST_ID_HEADER] == "smoke-test-id"


def test_app_error_route_produces_envelope() -> None:
    response = client.get("/boom-app-error")
    assert response.status_code == 404
    body = response.json()
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert body["detail"] == "this resource does not exist"
    assert body["instance"] == "/boom-app-error"
    assert body["errors"] == []


def test_unhandled_error_becomes_500_generic_body() -> None:
    response = client.get("/boom-unhandled")
    assert response.status_code == 500
    body = response.json()
    assert body["title"] == "Internal Server Error"
    assert body["detail"] is None
    assert "internal oh no" not in response.text
