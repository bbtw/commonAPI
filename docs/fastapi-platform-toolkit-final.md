# Design Doc: `yourco-fastapi` and `yourco-observability`

**Status:** Final Draft  
**Audience:** Platform engineering, service owners  
**Philosophy:** Explicit intent, composability, and idiomatic Python  
**Scope:** Two foundational libraries for standardizing FastAPI services across the org without turning the platform into a framework

---

## 1. Context

Service teams repeatedly assemble the same HTTP service plumbing: request IDs, access logs, tracing, metrics, security headers, health endpoints, readiness checks, and error envelopes. Left entirely to each team, these basics drift in shape and quality. Over-standardized, they become a platform framework that fights normal FastAPI development.

This design chooses a middle path:

- **`yourco-observability`** provides structured logging, tracing, metrics, and request-scoped context.
- **`yourco-fastapi`** provides a set of **toolkit functions** that attach standard behavior to a normal `FastAPI` app.

The goal is to make the right thing easy without hiding how the app works.

---

## 2. Design principles

### 2.1 Toolkit, not framework

The platform standardizes the **edges** of services, not their internal architecture.

This means:

- No mandatory `create_app()` factory
- No required inheritance from platform base classes
- No custom decorators that hide control flow
- No replacement for normal FastAPI routing, dependencies, or lifespan
- No opinion on business-layer structure, repository patterns, or service boundaries

### 2.2 Explicit over implicit

Every meaningful behavior should be visible in code.

- Features are attached via explicit function calls
- Routers are explicitly registered
- Tracing scope is visible via context managers
- Threadpool context propagation happens at the call site
- FastAPI `dependency_overrides` remains the testing escape hatch

### 2.3 Native Python and FastAPI idioms

The libraries should feel like they belong in a Python codebase.

- Use `@dataclass` for library config models where practical
- Use `asynccontextmanager` for lifespan composition
- Use FastAPI `Depends` for request context access
- Use normal middleware and router registration patterns
- Prefer functions and protocols over class hierarchies unless the class adds real value

### 2.4 Escape hatches by design

Every platform abstraction must be skippable, replaceable, or locally wrapped.

Examples:

- A service may omit `apply_security_headers(app, ...)` if a special deployment path requires it
- A service may keep platform logging but use its own readiness checks
- A service may use `yourco-observability` without using `yourco-fastapi`

### 2.5 Standardize contracts, not service internals

The platform owns:

- HTTP ingress conventions
- observability shape
- request correlation
- health and readiness semantics
- error response shape

The platform does **not** own:

- database session lifecycle
- ORM patterns
- repository patterns
- domain/service layer structure
- outbound client choices beyond shared observability hooks

---

## 3. Goals and non-goals

### Goals

- Make it easy to build a production-ready FastAPI service with standard request correlation, structured logs, tracing, metrics, health endpoints, and error handling.
- Preserve normal FastAPI development patterns so service authors can read, debug, and test their services without learning a second framework.
- Keep adoption incremental: observability-only, selected HTTP standards, or the full toolkit.
- Ensure sync and async handlers both preserve request context correctly.
- Keep configuration explicit and easy to reason about.

### Non-goals

- Replacing FastAPI idioms with a platform-specific programming model
- Defining service-layer architecture
- Shipping database/session helpers
- Shipping message broker or cache client libraries as part of `yourco-fastapi`
- Solving external API exposure rules in v1 beyond reserving forward-compatible extension points

---

## 4. `yourco-observability`: the observability toolkit

`yourco-observability` is a standalone library usable in FastAPI apps, workers, CLIs, and batch jobs.

### 4.1 Surface area

```python
from yourco_observability import (
    ObservabilityConfig,
    Logger,
    Tracer,
    Metrics,
    BoundContext,
)
```

The runtime model is explicit:

- configuration is represented by config objects
- loggers, tracers, and metrics instances are created deliberately
- request context is bound explicitly for request-scoped work

### 4.2 Configuration

```python
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
    metrics_mode: str = "otlp"  # "otlp" | "prometheus"
```

The library may provide `from_env()` helpers, but env loading is a convenience, not the architectural center.

### 4.3 Logging

```python
logger = Logger(config, name="orders.service")

logger.info(
    "order.created",
    order_id=order.id,
    customer_id=order.customer_id,
    total_cents=order.total_cents,
)
```

Log records are structured JSON by default and include:

- `timestamp`
- `level`
- `logger`
- `event`
- `service`
- `version`
- `environment`
- `trace_id`, `span_id`, `request_id` when a bound request context exists
- explicit structured fields from the call site

Rules:

- Event names use `snake.dot.case`
- The first positional argument is the event name
- Request correlation fields are injected from active request context
- `logger.exception(...)` records exception details in a standard shape

### 4.4 Tracing

Tracing is explicit and visible.

```python
tracer = Tracer(config)

with tracer.span("process_payment", attributes={"payment.amount": amount}):
    charge(card)
```

For async code:

```python
async def ship_order(order: Order) -> None:
    with tracer.span("ship_order", attributes={"order.id": order.id}):
        await courier_api.schedule_pickup(order)
```

The library should not encourage decorators for tracing in the default path. Span boundaries should be obvious when reading the function.

### 4.5 Metrics

```python
metrics = Metrics(config)

orders_created = metrics.counter("orders_created_total", unit="1")
payment_latency = metrics.histogram("payment_processing_seconds", unit="s")

orders_created.add(1, {"region": "us-east", "tier": "premium"})
payment_latency.record(0.237, {"provider": "stripe"})
```

Standard service labels such as `service`, `version`, and `environment` are added automatically.

Default metrics backend: **OTLP push to an OpenTelemetry collector**. Direct Prometheus exposition remains an opt-in mode for environments that still need it.

### 4.6 Request-scoped context

`BoundContext` carries request-scoped values such as:

- `request_id`
- `trace_id`
- `user_id`
- `tenant_id`
- optional additional attributes

```python
context = BoundContext(
    request_id=generate_uuid7(),
    trace_id=propagated_trace_id,
    user_id=user.id,
    tenant_id=user.tenant_id,
)

request_logger = logger.bind_context(context)
request_logger.info("request.started", method="GET", path_template="/orders/{id}")
```

The important rule is not “no implementation-level global state ever,” but rather: **no hidden mutable global configuration in the public API, and explicit request context at service boundaries**.

### 4.7 Context propagation and threadpools

This is a core operational concern and remains a blocking design requirement.

Context commonly breaks when work leaves the async request path and runs in a threadpool. The toolkit should provide an explicit helper:

```python
from yourco_observability.concurrency import run_in_threadpool

result = await run_in_threadpool(context, heavy_sync_function, payload)
```

Requirements:

1. The helper preserves request context for logs and traces.
2. The integration test suite must verify that both `async def` and `def` route handlers emit correlated logs with `trace_id`, `span_id`, and `request_id`.
3. Non-production diagnostic mode should warn loudly the first time a log is emitted during a request without expected trace context.
4. The docs must explicitly call out hazards:
   - `loop.run_in_executor(...)`
   - manually-created `threading.Thread`
   - libraries that spawn their own threads
   - sync SDKs called directly from `async def` handlers

### 4.8 Testing

```python
from yourco_observability.testing import LogCapture, SpanCapture

config = ObservabilityConfig(service_name="test")
logger = Logger(config)
tracer = Tracer(config)

with LogCapture(logger) as logs:
    with SpanCapture(tracer) as spans:
        service.create_order(...)
```

Tests should construct their own configured instances. Shared helpers are allowed, but the library should not require a global reset dance just to test a service.

### 4.9 Field and cardinality policy

The platform must keep a first-class policy document for what is safe to log or label.

**Allowed in logs:**

- request metadata such as `request_id`, `trace_id`, `method`, `path_template`, `status`, `duration_ms`
- service metadata such as `service`, `version`, `environment`, `region`
- bounded non-sensitive domain values such as `tenant_id`, `order_status`, `payment_method_type`

**Allowed in logs but not metric labels:**

- high-cardinality opaque internal IDs such as `order_id`, `customer_id`, `shipment_id`, `user_id`

**Forbidden in logs, traces, and metric labels:**

- email addresses, phone numbers, physical addresses, dates of birth, government IDs
- tokens, secrets, passwords, API keys, session IDs
- payment data
- raw request/response bodies by default
- raw query strings and raw concrete URLs where path templates should be used

Metric labels must come from a bounded set. High-cardinality values are never allowed as metric labels.

Primary enforcement is code review and documentation, with optional lint and non-production warnings as safety nets.

---

## 5. `yourco-fastapi`: the FastAPI toolkit

`yourco-fastapi` attaches standard behavior to a normal `FastAPI` app.

### 5.1 The apply pattern

```python
from fastapi import FastAPI
from yourco_fastapi import (
    AppConfig,
    apply_request_id,
    apply_tracing,
    apply_access_logging,
    apply_standard_errors,
    apply_security_headers,
    apply_health_endpoints,
)

obs_config = ObservabilityConfig.from_env()
app_config = AppConfig.from_env()

app = FastAPI(
    title="Order Service",
    version=app_config.version,
    docs_url=None if app_config.environment == "production" else "/docs",
)

apply_request_id(app)
apply_tracing(app, obs_config)
apply_access_logging(app, obs_config)
apply_standard_errors(app)
apply_security_headers(app, app_config)
apply_health_endpoints(app)

app.include_router(orders_router)
app.include_router(items_router)
```

This keeps ownership of the app with the service team while still making the platform standard path obvious.

### 5.2 App configuration

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class AppConfig:
    service_name: str
    version: str = "unknown"
    environment: str = "development"
    cors: CorsConfig = field(default_factory=CorsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
```

Config-loading helpers may exist, but service teams are free to load config their own way.

### 5.3 Middleware order and guarantees

The toolkit must document not just order, but what remains true across that order.

Recommended default order:

1. request ID
2. tracing
3. access logging
4. exception translation
5. security headers / CORS
6. user-added middleware where appropriate

Minimum guarantees:

- Access logs always include `request_id`.
- Tracing is active before access-log completion so the final request log can include correlation fields.
- Exception translation catches unhandled exceptions and produces the standard error envelope.
- Access logs record the **final** HTTP status after error translation.
- Startup failures prevent the process from binding the port.
- Shutdown failures are logged but do not block process termination.
- Platform auth and middleware do not consume the request body stream unless explicitly documented for a special use case.

This should be expressed as a short contract section, because a toolkit with no guarantees becomes ambiguous once teams mix platform pieces with normal Starlette middleware.

### 5.4 Lifespan

Use standard FastAPI lifespan with a composition helper.

```python
from contextlib import asynccontextmanager
from yourco_fastapi import compose_lifespans, platform_telemetry_lifespan

@asynccontextmanager
async def database_lifespan(app: FastAPI):
    app.state.engine = create_async_engine(config.database_url)
    await app.state.engine.connect()
    yield
    await app.state.engine.dispose()

app = FastAPI(
    lifespan=compose_lifespans(
        database_lifespan,
        platform_telemetry_lifespan,
    )
)
```

The platform should not introduce class-based startup/shutdown abstractions where native async context managers are sufficient.

### 5.5 Standard endpoints

The toolkit should offer an explicit helper to register:

- `GET /health` — liveness, always 200 if the process is up
- `GET /ready` — readiness, runs registered checks and returns 200 or 503
- `GET /version` — service/version/build metadata
- `GET /openapi.json` — standard FastAPI behavior
- `GET /docs`, `/redoc` — enabled outside production by default

### 5.6 Readiness policy

Readiness needs both a technical hook and a platform policy.

Appropriate readiness checks:

- dependencies that must be available for the pod to serve correctly
- local process prerequisites that indicate the service is ready to receive traffic

Usually inappropriate readiness checks:

- downstream HTTP services whose outages should be handled via retries, timeouts, or circuit breakers rather than taking the pod out of rotation
- optional systems that do not block core serving behavior

Requirements:

- checks run concurrently
- each check has a timeout
- success may be cached briefly to avoid hammering dependencies
- failures should not be cached
- the 503 response body should have a stable, human-debuggable shape

Example failure response:

```json
{
  "status": "unhealthy",
  "checks": [
    {"name": "database", "status": "ok", "duration_ms": 12},
    {"name": "redis", "status": "failed", "reason": "connection refused", "duration_ms": 2000}
  ]
}
```

### 5.7 Error envelope

The default error model is RFC 7807-style Problem Details, scoped for **internal service APIs**.

```json
{
  "type": "https://errors.yourco.internal/orders/insufficient-inventory",
  "title": "Insufficient Inventory",
  "status": 409,
  "detail": "Only 2 units of SKU-ABC available; requested 5.",
  "instance": "/orders/ord_7K2M",
  "request_id": "01HW2X...",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [
    {"field": "items[0].quantity", "code": "exceeds_available", "detail": null}
  ]
}
```

Translation rules:

- platform `AppError` subclasses map directly
- validation errors produce 422 with field-level `errors[]`
- timeouts translate to 504 where appropriate
- unexpected exceptions produce a 500 with generic title/body and full details in logs

### 5.8 Internal API scope and forward compatibility

The v1 design targets **internal APIs**, not public external APIs.

That means:

- `detail` may contain implementation-useful context for trusted internal callers
- internal error type URLs are acceptable
- request correlation fields may appear in the response body

It does **not** mean:

- PII is allowed in error responses
- tokens or secrets may leak into `detail`
- stack traces belong in response bodies

The shape should be forward-compatible with a future external mode where:

- `detail` is more sanitized
- type URLs may point to a public error directory
- correlation IDs may move to headers instead of body content

### 5.9 `errors[]` contract

`errors[]` should be a stable API contract, not an incidental field.

Rules:

- always present, even if empty
- each item has `field`, `code`, and optional `detail`
- `field` points to the input location that failed
- `code` is a stable programmatic identifier
- clients should use `code` for logic and `detail` for display

### 5.10 Request context via `Depends`

FastAPI dependencies remain the standard access path for request-scoped platform data.

```python
from fastapi import Depends
from yourco_fastapi import RequestContext, get_request_context

@app.get("/orders")
async def list_orders(ctx: RequestContext = Depends(get_request_context)):
    ctx.logger.info("orders.listing")
    return await service.list_orders(ctx)
```

This keeps the platform aligned with FastAPI rather than inventing a new context-access mechanism.

### 5.11 Testing

The default testing path should stay close to normal FastAPI practice.

```python
from fastapi.testclient import TestClient

app.dependency_overrides[get_db] = lambda: fake_db
app.dependency_overrides[get_current_user] = lambda: test_user

client = TestClient(app)
response = client.post("/orders", json={...})
```

The toolkit may provide examples and helpers, but it should not hide `dependency_overrides` behind a platform-specific test abstraction unless there is a very strong reason.

Observability assertions should remain easy:

```python
with LogCapture(logger) as logs:
    response = client.post("/orders", json={...})
```

---

## 6. Dependency and versioning strategy

The dependency strategy should match fleet size and operational maturity.

### 6.1 Small to medium fleet

For a smaller fleet, the simplest workable model is:

- `yourco-fastapi` and `yourco-observability` declare compatible version ranges
- the service template ships with a pinned lockfile or requirements set
- platform CI tests minimum and latest supported bounds
- teams upgrade in a controlled way by updating lockfiles

This avoids introducing release and publishing ceremony before it is justified.

### 6.2 Larger fleet

When fleet size and operational needs justify it, introduce a separate opt-in package containing centralized pins, such as `yourco-fastapi-versions`.

That package exists to solve:

- fleet-wide consistency
- faster rollout of security patches
- centralized compatibility testing

It should be introduced when the fleet complexity justifies it, not before.

---

## 7. Adoption model

The toolkit should support incremental adoption tiers.

### Tier 1: observability only

A team uses `yourco-observability` for logs, tracing, and metrics in an existing app or worker.

### Tier 2: selected FastAPI standards

A team adopts only the relevant `apply_*` pieces, such as request IDs, access logging, and standard errors.

### Tier 3: standard platform path

A team adopts the full recommended service setup: request IDs, tracing, access logs, security headers, health endpoints, and the standard error envelope.

This keeps the design flexible while preserving a preferred standard path.

---

## 8. Summary

This design deliberately recasts the platform offering as a **toolkit**.

It standardizes the parts of service construction that benefit from consistency:

- observability
- request correlation
- readiness and liveness conventions
- error response shape
- a small set of HTTP edge behaviors

It avoids overreach by keeping service authors inside normal FastAPI and Python patterns:

- `FastAPI(...)` remains theirs
- routers are still registered explicitly
- lifespan uses `asynccontextmanager`
- request context uses `Depends`
- tracing uses context managers
- tests use `TestClient` and `dependency_overrides`

The result should feel like a set of sharp, well-documented tools that help Python developers move faster without making them surrender control of how their service works.
