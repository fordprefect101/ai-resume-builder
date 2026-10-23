"""Request timing for the speed baseline: one JSON line per request, no identifiers."""

from __future__ import annotations

import contextvars
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logs" / "timing.jsonl"

# Named durations measured inside the current request (e.g. the AI tidy-up).
_parts: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "timing_parts", default=None
)


@contextmanager
def timed(name: str):
    """Add the duration of the block to the current request's timing line."""
    start = time.perf_counter()
    try:
        yield
    finally:
        parts = _parts.get()
        if parts is not None:
            elapsed = (time.perf_counter() - start) * 1000
            parts[name] = round(parts.get(name, 0) + elapsed, 1)


def write_line(record: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass  # Timing must never break a request.


class TimingMiddleware:
    """
    Times every HTTP request. Logs the route template (never the real path, so
    session ids are not written), status, duration, response size and parts.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        parts: dict = {}
        token = _parts.set(parts)
        start = time.perf_counter()
        status = 500
        size = 0

        async def send_and_measure(message):
            nonlocal status, size
            if message["type"] == "http.response.start":
                status = message.get("status", status)
            elif message["type"] == "http.response.body":
                size += len(message.get("body") or b"")
            await send(message)

        try:
            await self.app(scope, receive, send_and_measure)
        finally:
            _parts.reset(token)
            route = scope.get("route")
            endpoint = scope.get("endpoint")
            write_line(
                {
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "method": scope.get("method"),
                    "route": getattr(route, "path", None) or "(unmatched)",
                    "action": getattr(endpoint, "__name__", None),
                    "status": status,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                    "bytes": size,
                    "parts": parts,
                }
            )
