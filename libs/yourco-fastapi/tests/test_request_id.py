from fastapi import FastAPI
from fastapi.testclient import TestClient
from yourco_fastapi import REQUEST_ID_HEADER, apply_request_id
from yourco_observability import current_context


def _make_app() -> FastAPI:
    app = FastAPI()
    apply_request_id(app)

    @app.get("/ping")
    async def ping() -> dict[str, str | None]:
        ctx = current_context()
        return {"request_id": ctx.request_id if ctx else None}

    return app


def test_request_id_is_generated_when_missing() -> None:
    client = TestClient(_make_app())

    response = client.get("/ping")

    assert response.status_code == 200
    header_value = response.headers[REQUEST_ID_HEADER]
    assert header_value
    assert response.json()["request_id"] == header_value


def test_request_id_is_echoed_when_supplied() -> None:
    client = TestClient(_make_app())

    response = client.get("/ping", headers={REQUEST_ID_HEADER: "supplied-id"})

    assert response.headers[REQUEST_ID_HEADER] == "supplied-id"
    assert response.json()["request_id"] == "supplied-id"


def test_request_ids_differ_across_requests() -> None:
    client = TestClient(_make_app())

    first = client.get("/ping").headers[REQUEST_ID_HEADER]
    second = client.get("/ping").headers[REQUEST_ID_HEADER]

    assert first != second
