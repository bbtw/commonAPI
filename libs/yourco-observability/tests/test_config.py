from yourco_observability import ObservabilityConfig


def test_config_defaults() -> None:
    cfg = ObservabilityConfig(service_name="orders")

    assert cfg.service_name == "orders"
    assert cfg.version == "unknown"
    assert cfg.environment == "development"
    assert cfg.log_level == "INFO"
    assert cfg.log_format == "json"
    assert cfg.otlp_endpoint is None
    assert cfg.sample_rate == 1.0
    assert cfg.metrics_mode == "otlp"


def test_config_is_frozen() -> None:
    cfg = ObservabilityConfig(service_name="orders")

    try:
        cfg.service_name = "other"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("expected frozen dataclass to reject mutation")
