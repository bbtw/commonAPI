from fastapi import FastAPI
from yourco_fastapi import (
    AppConfig,
    NotFoundError,
    apply_health_endpoints,
    apply_request_id,
    apply_standard_errors,
)
from yourco_observability import Logger, ObservabilityConfig

obs_config = ObservabilityConfig(
    service_name="demo-service",
    version="0.1.0",
    environment="development",
)
app_config = AppConfig(
    service_name=obs_config.service_name,
    version=obs_config.version,
    environment=obs_config.environment,
)

logger = Logger(obs_config, name="demo.service")

app = FastAPI(title="Demo Service", version=app_config.version)

apply_request_id(app)
apply_standard_errors(app, logger)
apply_health_endpoints(app, app_config)


@app.get("/hello")
async def hello(name: str = "world") -> dict[str, str]:
    logger.info("hello.called", name=name)
    return {"message": f"hello, {name}"}


@app.get("/boom-app-error")
async def boom_app_error() -> dict[str, str]:
    raise NotFoundError("this resource does not exist")


@app.get("/boom-unhandled")
async def boom_unhandled() -> dict[str, str]:
    raise RuntimeError("internal oh no")
