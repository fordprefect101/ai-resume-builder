"""Bring your own key: a visitor's own OpenAI key, used for the one request that carries it.

The website sends the key in the `X-OpenAI-Key` header. It lives only in a context variable for
that request: never stored, never logged, never put in traces or error messages (`redact`).
A request with the person's key is not counted against the daily limit (see usage_limits).
"""

from __future__ import annotations

import contextvars
import logging
import os
import re

KEY_HEADER = "x-openai-key"
_KEY: contextvars.ContextVar[str | None] = contextvars.ContextVar("own_openai_key", default=None)

# Anything shaped like an OpenAI key, plus the current request's key whatever its shape.
_KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
HIDDEN = "[hidden key]"


def own_key() -> str | None:
    return _KEY.get()


def has_own_key() -> bool:
    return bool(_KEY.get())


def api_key() -> str | None:
    """The visitor's own key for this request, else the server's key."""
    return _KEY.get() or os.getenv("OPENAI_API_KEY") or None


def redact(text):
    """Hide any key in a piece of text. Non-text values come back unchanged."""
    if not isinstance(text, str):
        return text
    key = _KEY.get()
    if key:
        text = text.replace(key, HIDDEN)
    return _KEY_SHAPE.sub(HIDDEN, text)


def make_client():
    from openai import OpenAI

    return OpenAI(api_key=api_key())


class _RequestClient:
    """Stands in for an OpenAI client: each use builds one with this request's key."""

    def __getattr__(self, name):
        return getattr(make_client(), name)


client = _RequestClient()


class OwnKeyMiddleware:
    """Pure ASGI, so the key is set in the same context the endpoint runs in."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        value = None
        for name, raw in scope.get("headers", []):
            if name == KEY_HEADER.encode():
                value = raw.decode("latin-1").strip() or None
                break
        token = _KEY.set(value)
        try:
            return await self.app(scope, receive, send)
        finally:
            _KEY.reset(token)


class RedactFilter(logging.Filter):
    """Keeps keys out of every log line, including formatted exceptions."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = None
            if record.exc_info:
                import traceback

                record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)))
                record.exc_info = None
        except Exception:  # logging must never break a request
            pass
        return True


def install_log_redaction() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(RedactFilter())
    root.addFilter(RedactFilter())
    for name in ("contact", "uvicorn.error", "uvicorn"):
        logging.getLogger(name).addFilter(RedactFilter())
