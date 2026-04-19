from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from yourco_fastapi import (
    REQUEST_ID_HEADER,
    ConflictError,
    FieldError,
    NotFoundError,
    apply_request_id,
    apply_standard_errors,
)
from yourco_observability import Logger, ObservabilityConfig
from yourco_observability.testing import LogCapture


class _Item(BaseModel):
    name: str
    quantity: int


def _make_logger() -> Logger:
    return Logger(ObservabilityConfig(service_name="test-errors"))


def _make_app(logger: Logger) -> FastAPI:
    app = FastAPI()
    apply_request_id(app)
    apply_standard_errors(app, logger)

    @app.get("/not-found")
    async def not_found() -> dict[str, str]:
        raise NotFoundError("order not found")

    @app.get("/conflict")
    async def conflict() -> dict[str, str]:
        raise ConflictError(
            "inventory short",
            errors=[FieldError(field="items[0].quantity", code="exceeds_available")],
        )

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise ValueError("secret internal details")

    @app.get("/timeout")
    async def timeout() -> dict[str, str]:
        raise TimeoutError

    @app.post("/validate")
    async def validate(item: _Item) -> dict[str, str]:
        return {"name": item.name}

    return app


def _client(logger: Logger | None = None) -> tuple[TestClient, Logger]:
    log = logger or _make_logger()
    return TestClient(_make_app(log), raise_server_exceptions=False), log


def test_app_error_translated_to_envelope() -> None:
    client, _ = _client()

    response = client.get("/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert body["detail"] == "order not found"
    assert body["type"].endswith("/not_found")
    assert body["instance"] == "/not-found"
    assert body["errors"] == []
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_app_error_carries_field_errors() -> None:
    client, _ = _client()

    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json()["errors"] == [
        {"field": "items[0].quantity", "code": "exceeds_available", "detail": None},
    ]


def test_unhandled_exception_returns_500_without_leaking() -> None:
    client, logger = _client()

    with LogCapture(logger) as logs:
        response = client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["title"] == "Internal Server Error"
    assert body["status"] == 500
    assert body["detail"] is None
    assert body["errors"] == []
    assert "secret internal details" not in response.text

    matching = [r for r in logs.records if r["event"] == "request.unhandled_exception"]
    assert len(matching) == 1
    record = matching[0]
    assert record["exception"]["type"] == "ValueError"
    assert "secret internal details" in record["exception"]["message"]
    assert record["path"] == "/boom"
    assert record["method"] == "GET"


def test_asyncio_timeout_becomes_504() -> None:
    client, _ = _client()

    response = client.get("/timeout")

    assert response.status_code == 504
    body = response.json()
    assert body["title"] == "Gateway Timeout"
    assert body["status"] == 504


def test_validation_error_has_errors_list() -> None:
    client, _ = _client()

    response = client.post("/validate", json={"name": "x"})

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422
    assert body["title"] == "Unprocessable Entity"
    assert len(body["errors"]) >= 1
    assert any("quantity" in err["field"] for err in body["errors"])
    for err in body["errors"]:
        assert set(err) == {"field", "code", "detail"}


def test_errors_array_is_always_present_even_when_empty() -> None:
    client, _ = _client()

    response = client.get("/not-found")

    assert "errors" in response.json()
    assert response.json()["errors"] == []


def test_request_id_flows_into_envelope_even_when_supplied() -> None:
    client, _ = _client()

    response = client.get("/not-found", headers={REQUEST_ID_HEADER: "caller-supplied"})

    assert response.json()["request_id"] == "caller-supplied"


def test_custom_type_url_prefix_honored() -> None:
    app = FastAPI()
    logger = _make_logger()
    apply_standard_errors(
        app,
        logger,
        type_url_prefix="https://example.com/errors/",
    )

    @app.get("/x")
    async def x() -> None:
        raise NotFoundError("nope")

    response = TestClient(app, raise_server_exceptions=False).get("/x")

    assert response.json()["type"] == "https://example.com/errors/not_found"


def test_custom_type_url_on_instance_overrides_prefix() -> None:
    factory: Callable[[], FastAPI] = lambda: _make_app(_make_logger())  # noqa: E731
    app = factory()

    @app.get("/override")
    async def override() -> None:
        raise NotFoundError("nope", type_url="https://custom.example.com/thing")

    response = TestClient(app, raise_server_exceptions=False).get("/override")

    assert response.json()["type"] == "https://custom.example.com/thing"
