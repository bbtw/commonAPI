from __future__ import annotations

from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from yourco_observability import Logger, current_context

DEFAULT_TYPE_URL_PREFIX = "https://errors.yourco.internal/"


@dataclass
class FieldError:
    field: str
    code: str
    detail: str | None = None


class AppError(Exception):
    status: int = 500
    title: str = "Internal Server Error"
    code: str = "internal_error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        errors: list[FieldError] | None = None,
        type_url: str | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.errors: list[FieldError] = list(errors) if errors else []
        self._type_url = type_url

    def resolve_type_url(self, prefix: str) -> str:
        return self._type_url or f"{prefix}{self.code}"


class BadRequestError(AppError):
    status = 400
    title = "Bad Request"
    code = "bad_request"


class UnauthorizedError(AppError):
    status = 401
    title = "Unauthorized"
    code = "unauthorized"


class ForbiddenError(AppError):
    status = 403
    title = "Forbidden"
    code = "forbidden"


class NotFoundError(AppError):
    status = 404
    title = "Not Found"
    code = "not_found"


class ConflictError(AppError):
    status = 409
    title = "Conflict"
    code = "conflict"


class UnprocessableEntityError(AppError):
    status = 422
    title = "Unprocessable Entity"
    code = "unprocessable_entity"


class UpstreamTimeoutError(AppError):
    status = 504
    title = "Gateway Timeout"
    code = "upstream_timeout"


@dataclass
class _Envelope:
    type: str
    title: str
    status: int
    detail: str | None
    instance: str
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = asdict(self)
        ctx = current_context()
        if ctx is not None:
            if ctx.request_id is not None:
                payload["request_id"] = ctx.request_id
            if ctx.trace_id is not None:
                payload["trace_id"] = ctx.trace_id
        return payload


def _envelope_from(
    *,
    type_url: str,
    title: str,
    status: int,
    detail: str | None,
    instance: str,
    errors: list[FieldError] | None = None,
) -> dict[str, Any]:
    return _Envelope(
        type=type_url,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        errors=[asdict(e) for e in (errors or [])],
    ).to_dict()


def apply_standard_errors(
    app: FastAPI,
    logger: Logger,
    *,
    type_url_prefix: str = DEFAULT_TYPE_URL_PREFIX,
) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        try:
            status = HTTPStatus(exc.status_code)
            title = status.phrase
            code = status.name.lower()
        except ValueError:
            title = "HTTP Error"
            code = f"http_{exc.status_code}"
        payload = _envelope_from(
            type_url=f"{type_url_prefix}{code}",
            title=title,
            status=exc.status_code,
            detail=str(exc.detail) if exc.detail is not None else None,
            instance=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            headers=exc.headers,
        )

    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        payload = _envelope_from(
            type_url=exc.resolve_type_url(type_url_prefix),
            title=exc.title,
            status=exc.status,
            detail=exc.detail,
            instance=request.url.path,
            errors=exc.errors,
        )
        return JSONResponse(status_code=exc.status, content=payload)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors = [
            FieldError(
                field=".".join(str(p) for p in err.get("loc", ())),
                code=str(err.get("type", "invalid")),
                detail=err.get("msg"),
            )
            for err in exc.errors()
        ]
        payload = _envelope_from(
            type_url=f"{type_url_prefix}unprocessable_entity",
            title="Unprocessable Entity",
            status=422,
            detail="Request validation failed.",
            instance=request.url.path,
            errors=field_errors,
        )
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(TimeoutError)
    async def _handle_timeout(
        request: Request, exc: TimeoutError
    ) -> JSONResponse:
        payload = _envelope_from(
            type_url=f"{type_url_prefix}upstream_timeout",
            title="Gateway Timeout",
            status=504,
            detail=None,
            instance=request.url.path,
        )
        return JSONResponse(status_code=504, content=payload)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "request.unhandled_exception",
            method=request.method,
            path=request.url.path,
        )
        payload = _envelope_from(
            type_url=f"{type_url_prefix}internal_error",
            title="Internal Server Error",
            status=500,
            detail=None,
            instance=request.url.path,
        )
        return JSONResponse(status_code=500, content=payload)
