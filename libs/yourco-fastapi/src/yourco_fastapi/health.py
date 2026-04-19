from __future__ import annotations

from fastapi import FastAPI

from yourco_fastapi.config import AppConfig


def apply_health_endpoints(app: FastAPI, config: AppConfig) -> None:
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/version", include_in_schema=False)
    async def version() -> dict[str, str]:
        return {
            "service": config.service_name,
            "version": config.version,
            "environment": config.environment,
        }
