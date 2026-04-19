# Toolkit roadmap

What still needs to be built to fulfill `fastapi-platform-toolkit-final.md`. Each
item links to the design-doc section that specifies it. Check items off as they
land.

## `yourco-observability`

- [x] `ObservabilityConfig` — §4.2
- [x] `BoundContext` + contextvar — §4.6
- [x] `Logger` (JSON, structured, auto-injects bound context) — §4.3
- [ ] `Tracer` with context-manager spans, OTLP export, `sample_rate` honored — §4.4
- [ ] `Metrics` (counters + histograms), default OTLP push, optional Prometheus — §4.5
- [ ] `run_in_threadpool(context, fn, ...)` preserves request context across threadpool — §4.7
- [ ] Non-production diagnostic warning when a log is emitted without expected trace context — §4.7
- [x] `LogCapture` testing helper — §4.8
- [ ] `SpanCapture` testing helper — §4.8
- [ ] Field/cardinality policy enforcement (lint rule or non-prod warning) — §4.9

## `yourco-fastapi`

- [x] `AppConfig` (service_name/version/environment) — §5.2
- [x] `apply_request_id(app)` — §5.1
- [x] `apply_health_endpoints(app, config)` — `/health`, `/version` — §5.5
- [ ] `CorsConfig` + `SecurityConfig` on `AppConfig` — §5.2
- [ ] `apply_tracing(app, obs_config)` middleware — §5.1
- [ ] `apply_access_logging(app, obs_config)` — logs include final status after error translation — §5.3
- [x] `apply_standard_errors(app, logger)` — RFC 7807 envelope, `AppError` hierarchy, validation → 422 with `errors[]`, timeouts → 504, unexpected → 500 — §5.7–5.9
- [ ] `apply_security_headers(app, config)` — §5.1, §5.2
- [ ] Readiness: `/ready` endpoint, check registry, per-check timeouts, concurrent execution, brief success caching, stable 503 body shape — §5.6
- [ ] `compose_lifespans(*lifespans)` + `platform_telemetry_lifespan` — §5.4
- [ ] `RequestContext` + `get_request_context` FastAPI dependency — §5.10
- [ ] Middleware order + guarantees contract, enforced/tested — §5.3

## Cross-cutting

- [ ] Integration test: both `async def` and `def` handlers emit correlated logs with `trace_id`, `span_id`, `request_id` — §4.7
- [ ] Documentation of hazards that break context (`loop.run_in_executor`, bare `threading.Thread`, sync SDKs in async handlers) — §4.7
- [ ] Dependency/versioning strategy: compatible version ranges, lockfile-driven upgrades, CI tests min+latest bounds — §6.1
- [ ] External-API forward compatibility path for error envelope — §5.8

## Out of v1 scope (per design doc)

- Public-external error-envelope mode (doc §5.8 reserves the shape)
- `yourco-fastapi-versions` centralized pins package (only if fleet size justifies it) — §6.2
- Database/session helpers, message broker/cache clients — §3 non-goals
