"""The model switchboard: the one place that says which provider and model does which job.

A job's model is one line in api/.env, e.g. WRITER_MODEL=openai:gpt-4.1-mini. Changing a
model never needs a code change. A job with no line uses OPENAI_CHAT_MODEL, so nothing
breaks when nothing is configured.

Model replies are untrusted text. complete_json() checks the reply against a pydantic
shape, retries once if it does not fit, and then reports a failed step in the result
instead of raising: a bad reply from a model must never crash a request.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from writing import records

# One setting per job. Every name here must be listed in api/.env.example.
JOB_SETTINGS = {
    "analyst": "ANALYST_MODEL",
    "writer": "WRITER_MODEL",
    "checker": "CHECKER_MODEL",
}
DEFAULT_MODEL = "gpt-4.1-mini"
# Jobs that should give steady answers run at a low temperature (how much a model's
# output varies between runs). The writer is left at the model's own default.
DEFAULT_TEMPERATURE = {"analyst": 0.2, "checker": 0.0}
MAX_ATTEMPTS = 2  # the first try, plus one retry when the reply does not fit the shape


class ConfigError(ValueError):
    """A job's model setting names a provider this switchboard does not know."""


@dataclass
class Result:
    """What one switchboard call produced. `ok` False means a failed step, not a crash."""

    ok: bool
    data: BaseModel | None = None
    error: str = ""
    job: str = ""
    provider: str = ""
    model: str = ""
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    cost_usd: float | None = None  # None: the model has no listed price (see prices.json)
    replies: list[str] = field(default_factory=list)


class OpenAIAdapter:
    """Turns a request into OpenAI's format. The only code here that knows OpenAI."""

    def complete(self, model: str, messages: list[dict], temperature: float | None):
        from openai import OpenAI

        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        kwargs: dict = {"response_format": {"type": "json_object"}}
        if temperature is not None:  # some models reject the setting, so omit it by default
            kwargs["temperature"] = temperature
        response = OpenAI(api_key=key).chat.completions.create(
            model=model, messages=messages, **kwargs
        )
        usage = getattr(response, "usage", None)
        return (
            response.choices[0].message.content or "",
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
        )


# provider name -> adapter class. A new provider is a new adapter registered here.
ADAPTERS: dict[str, type] = {"openai": OpenAIAdapter}


def resolve(job: str) -> tuple[str, str]:
    """(provider, model) for a job, from its setting, else OPENAI_CHAT_MODEL."""
    if job not in JOB_SETTINGS:
        raise ConfigError(f"unknown job: {job}")
    setting = (os.getenv(JOB_SETTINGS[job]) or "").strip()
    if not setting:
        return "openai", os.getenv("OPENAI_CHAT_MODEL") or DEFAULT_MODEL
    provider, sep, model = setting.partition(":")
    if not sep:  # a bare model name means OpenAI
        provider, model = "openai", setting
    provider, model = provider.strip().lower(), model.strip()
    if provider not in ADAPTERS:
        raise ConfigError(
            f"{JOB_SETTINGS[job]} names an unknown provider: {provider!r}"
        )
    if not model:
        raise ConfigError(f"{JOB_SETTINGS[job]} has no model name")
    return provider, model


def _parse(text: str, shape: type[BaseModel]) -> BaseModel:
    cleaned = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    return shape.model_validate(json.loads(cleaned))


def complete_json(
    job: str,
    messages: list[dict],
    shape: type[BaseModel],
    *,
    temperature: float | None = None,
) -> Result:
    """Ask a job's model for a JSON reply in `shape`. Never raises for a bad reply."""
    provider, model = resolve(job)
    result = Result(ok=False, job=job, provider=provider, model=model)
    adapter = ADAPTERS[provider]()
    conversation = list(messages)
    if temperature is None:
        temperature = DEFAULT_TEMPERATURE.get(job)
    started = time.monotonic()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result.attempts = attempt
        try:
            try:
                text, tokens_in, tokens_out = adapter.complete(
                    model, conversation, temperature
                )
            except Exception as exc:
                # Some models reject the setting. Drop it and ask again, once, for free.
                if temperature is None or "temperature" not in str(exc).lower():
                    raise
                temperature = None
                text, tokens_in, tokens_out = adapter.complete(
                    model, conversation, temperature
                )
        except Exception as exc:  # outside service trouble: a failed step, not a retry
            result.error = f"{type(exc).__name__}: {exc}"
            break
        result.input_tokens += tokens_in
        result.output_tokens += tokens_out
        result.replies.append(text)
        try:
            result.data = _parse(text, shape)
            result.ok = True
            result.error = ""
            break
        except (ValueError, ValidationError) as exc:
            result.error = f"reply did not fit the required shape: {exc}"
            conversation = conversation + [
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": (
                        "Your reply did not match the required JSON shape "
                        f"({exc}). Reply again with only valid JSON."
                    ),
                },
            ]
    result.seconds = round(time.monotonic() - started, 3)
    result.cost_usd = records.cost_usd(
        provider, model, result.input_tokens, result.output_tokens
    )
    return result
