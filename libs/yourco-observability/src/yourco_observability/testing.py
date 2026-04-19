from __future__ import annotations

import io
import json
from types import TracebackType
from typing import Any

from yourco_observability.logger import Logger


class LogCapture:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self._buffer = io.StringIO()
        self._original_stream: Any = None

    def __enter__(self) -> LogCapture:
        self._original_stream = self._logger._stream
        self._logger._stream = self._buffer
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._logger._stream = self._original_stream

    @property
    def records(self) -> list[dict[str, Any]]:
        self._buffer.seek(0)
        return [json.loads(line) for line in self._buffer.getvalue().splitlines() if line]
