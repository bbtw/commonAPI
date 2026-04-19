from __future__ import annotations

import io
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from yourco_observability.config import ObservabilityConfig
from yourco_observability.context import BoundContext, current_context


class Logger:
    def __init__(
        self,
        config: ObservabilityConfig,
        name: str | None = None,
        *,
        stream: io.TextIOBase | Any | None = None,
        bound: BoundContext | None = None,
    ) -> None:
        self._config = config
        self._name = name or config.service_name
        self._stream = stream if stream is not None else sys.stdout
        self._bound = bound
        self._level = logging.getLevelNamesMapping().get(config.log_level.upper(), logging.INFO)

    def bind_context(self, context: BoundContext) -> Logger:
        return Logger(self._config, self._name, stream=self._stream, bound=context)

    def debug(self, event: str, **fields: Any) -> None:
        self._emit(logging.DEBUG, event, fields, exc_info=None)

    def info(self, event: str, **fields: Any) -> None:
        self._emit(logging.INFO, event, fields, exc_info=None)

    def warning(self, event: str, **fields: Any) -> None:
        self._emit(logging.WARNING, event, fields, exc_info=None)

    def error(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, fields, exc_info=None)

    def exception(self, event: str, **fields: Any) -> None:
        self._emit(logging.ERROR, event, fields, exc_info=sys.exc_info())

    def _emit(
        self,
        level: int,
        event: str,
        fields: dict[str, Any],
        *,
        exc_info: Any,
    ) -> None:
        if level < self._level:
            return

        record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": logging.getLevelName(level),
            "logger": self._name,
            "event": event,
            "service": self._config.service_name,
            "version": self._config.version,
            "environment": self._config.environment,
        }

        ctx = self._bound if self._bound is not None else current_context()
        if ctx is not None:
            if ctx.request_id is not None:
                record["request_id"] = ctx.request_id
            if ctx.trace_id is not None:
                record["trace_id"] = ctx.trace_id
            if ctx.span_id is not None:
                record["span_id"] = ctx.span_id
            if ctx.user_id is not None:
                record["user_id"] = ctx.user_id
            if ctx.tenant_id is not None:
                record["tenant_id"] = ctx.tenant_id
            for key, value in ctx.attributes.items():
                record.setdefault(key, value)

        for key, value in fields.items():
            record[key] = value

        if exc_info is not None and exc_info[0] is not None:
            import traceback

            record["exception"] = {
                "type": exc_info[0].__name__,
                "message": str(exc_info[1]),
                "stack": "".join(traceback.format_exception(*exc_info)).rstrip(),
            }

        line = json.dumps(record, default=str)
        self._stream.write(line + "\n")
        self._stream.flush()
