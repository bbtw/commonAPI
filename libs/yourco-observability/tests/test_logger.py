import io
import json
from typing import Any

from yourco_observability import BoundContext, Logger, ObservabilityConfig, set_current_context
from yourco_observability.context import reset_current_context


def _read_records(stream: io.StringIO) -> list[dict[str, Any]]:
    stream.seek(0)
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


def test_logger_emits_structured_json() -> None:
    stream = io.StringIO()
    cfg = ObservabilityConfig(service_name="orders", version="1.2.3", environment="test")
    logger = Logger(cfg, name="orders.service", stream=stream)

    logger.info("order.created", order_id="ord_1", total_cents=4200)

    [record] = _read_records(stream)
    assert record["event"] == "order.created"
    assert record["level"] == "INFO"
    assert record["logger"] == "orders.service"
    assert record["service"] == "orders"
    assert record["version"] == "1.2.3"
    assert record["environment"] == "test"
    assert record["order_id"] == "ord_1"
    assert record["total_cents"] == 4200
    assert "timestamp" in record


def test_logger_injects_current_context() -> None:
    stream = io.StringIO()
    cfg = ObservabilityConfig(service_name="orders")
    logger = Logger(cfg, stream=stream)

    ctx = BoundContext(request_id="req-1", trace_id="trace-1", user_id="u-1")
    token = set_current_context(ctx)
    try:
        logger.info("request.started")
    finally:
        reset_current_context(token)

    [record] = _read_records(stream)
    assert record["request_id"] == "req-1"
    assert record["trace_id"] == "trace-1"
    assert record["user_id"] == "u-1"


def test_bind_context_overrides_ambient() -> None:
    stream = io.StringIO()
    cfg = ObservabilityConfig(service_name="orders")
    bound_logger = Logger(cfg, stream=stream).bind_context(
        BoundContext(request_id="explicit-req")
    )

    bound_logger.info("work.done")

    [record] = _read_records(stream)
    assert record["request_id"] == "explicit-req"


def test_log_level_filters_lower_levels() -> None:
    stream = io.StringIO()
    cfg = ObservabilityConfig(service_name="orders", log_level="WARNING")
    logger = Logger(cfg, stream=stream)

    logger.debug("debug.event")
    logger.info("info.event")
    logger.warning("warn.event")

    events = [r["event"] for r in _read_records(stream)]
    assert events == ["warn.event"]


def test_exception_includes_details() -> None:
    stream = io.StringIO()
    cfg = ObservabilityConfig(service_name="orders")
    logger = Logger(cfg, stream=stream)

    try:
        raise ValueError("bad input")
    except ValueError:
        logger.exception("order.failed")

    [record] = _read_records(stream)
    assert record["exception"]["type"] == "ValueError"
    assert record["exception"]["message"] == "bad input"
    assert "ValueError" in record["exception"]["stack"]
