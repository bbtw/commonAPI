from dataclasses import dataclass


@dataclass(frozen=True)
class ObservabilityConfig:
    service_name: str
    version: str = "unknown"
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "json"
    otlp_endpoint: str | None = None
    sample_rate: float = 1.0
    metrics_mode: str = "otlp"
