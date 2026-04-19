from yourco_observability import Logger, ObservabilityConfig
from yourco_observability.testing import LogCapture


def test_log_capture_captures_records() -> None:
    logger = Logger(ObservabilityConfig(service_name="test"))

    with LogCapture(logger) as logs:
        logger.info("hello", foo=1)
        logger.warning("bye", foo=2)

    events = [(r["event"], r["foo"]) for r in logs.records]
    assert events == [("hello", 1), ("bye", 2)]


def test_log_capture_restores_original_stream() -> None:
    logger = Logger(ObservabilityConfig(service_name="test"))
    original = logger._stream

    with LogCapture(logger):
        pass

    assert logger._stream is original


def test_log_capture_isolates_from_outside_writes() -> None:
    logger = Logger(ObservabilityConfig(service_name="test"))
    logger.info("before")

    with LogCapture(logger) as logs:
        logger.info("inside")

    assert [r["event"] for r in logs.records] == ["inside"]
