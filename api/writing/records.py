"""Cost accounting and run records for the writing team.

Every AI request becomes a step record (which model, how many tokens, how long, what it
cost). A Run collects the steps of one piece of work and totals them. Records are built
to be stored with log_trace (api/traces.py), so a bad point can be traced to the step
that caused it. Text in records is redacted first: contact details never reach the log.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PRICES_FILE = Path(__file__).with_name("prices.json")
MAX_TEXT = 4000  # characters kept per logged text


def load_prices(path: Path = PRICES_FILE) -> dict:
    data = json.loads(path.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


PRICES = load_prices()


def cost_usd(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float | None:
    """Dollars for one request, or None when the model has no listed price."""
    price = (PRICES.get(provider) or {}).get(model)
    if not isinstance(price, dict):
        return None
    try:
        per_input, per_output = float(price["input"]), float(price["output"])
    except (KeyError, TypeError, ValueError):
        return None
    return round(
        input_tokens / 1_000_000 * per_input + output_tokens / 1_000_000 * per_output, 6
    )


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LINK = re.compile(r"(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|io|dev|co|ai|app)\b\S*", re.I)
PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{5,}\d")


def _phone_or_keep(match: re.Match) -> str:
    text = match.group(0)
    digits = sum(ch.isdigit() for ch in text)
    # Dates and ranges like "2019-2023" stay; long digit runs and +country numbers go.
    return "[phone]" if digits >= 9 or (text.startswith("+") and digits >= 7) else text


def redact(text: str) -> str:
    """Replace emails, links and phone numbers, so logs never hold contact details."""
    text = EMAIL.sub("[email]", str(text or ""))
    text = LINK.sub("[link]", text)
    return PHONE.sub(_phone_or_keep, text)


def _clip(text: str) -> str:
    text = redact(text)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "…"


def step_record(result, messages: list[dict] | None = None, *, name: str = "") -> dict:
    """One AI request as a plain record (json-safe). `result` is a models.Result."""
    record = {
        "step": name or result.job,
        "job": result.job,
        "provider": result.provider,
        "model": result.model,
        "ok": result.ok,
        "attempts": result.attempts,
        "inputTokens": result.input_tokens,
        "outputTokens": result.output_tokens,
        "seconds": result.seconds,
        "costUsd": result.cost_usd,
        "error": _clip(result.error)[:300],
    }
    if messages is not None:
        record["input"] = [
            {"role": m.get("role", ""), "content": _clip(m.get("content", ""))}
            for m in messages
        ]
    record["output"] = [_clip(reply) for reply in result.replies]
    return record


class Run:
    """The steps of one piece of work, with totals."""

    def __init__(self, label: str):
        self.label = label
        self.steps: list[dict] = []

    def add(self, result, messages: list[dict] | None = None, *, name: str = "") -> dict:
        record = step_record(result, messages, name=name)
        self.steps.append(record)
        return record

    def totals(self) -> dict:
        priced = [s["costUsd"] for s in self.steps if s["costUsd"] is not None]
        return {
            "steps": len(self.steps),
            "failedSteps": sum(not s["ok"] for s in self.steps),
            "inputTokens": sum(s["inputTokens"] for s in self.steps),
            "outputTokens": sum(s["outputTokens"] for s in self.steps),
            "seconds": round(sum(s["seconds"] for s in self.steps), 3),
            "costUsd": round(sum(priced), 6),
            # A total that leaves out unpriced steps must say so.
            "unpricedSteps": len(self.steps) - len(priced),
        }

    def as_trace(self) -> dict:
        return {"label": self.label, "steps": self.steps, "totals": self.totals()}
