from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundContext:
    request_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


_current: ContextVar[BoundContext | None] = ContextVar("yourco_bound_context", default=None)


def current_context() -> BoundContext | None:
    return _current.get()


def set_current_context(ctx: BoundContext | None) -> Token[BoundContext | None]:
    return _current.set(ctx)


def reset_current_context(token: Token[BoundContext | None]) -> None:
    _current.reset(token)
