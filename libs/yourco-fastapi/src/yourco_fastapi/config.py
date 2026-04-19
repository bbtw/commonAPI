from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    service_name: str
    version: str = "unknown"
    environment: str = "development"
