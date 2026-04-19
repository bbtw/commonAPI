from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from yourco_observability import BoundContext, current_context, set_current_context
from yourco_observability.context import reset_current_context

REQUEST_ID_HEADER = "X-Request-ID"


def apply_request_id(app: FastAPI, *, header: str = REQUEST_ID_HEADER) -> None:
    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(header)
        request_id = incoming or uuid.uuid4().hex

        existing = current_context() or BoundContext()
        bound = BoundContext(
            request_id=request_id,
            trace_id=existing.trace_id,
            span_id=existing.span_id,
            user_id=existing.user_id,
            tenant_id=existing.tenant_id,
            attributes=dict(existing.attributes),
        )
        token = set_current_context(bound)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            reset_current_context(token)

        response.headers[header] = request_id
        return response
