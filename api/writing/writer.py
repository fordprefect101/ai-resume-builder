"""The writer: facts in, resume points out. It never judges its own work.

The model proposes points, each citing the facts it used. Ordinary code (rules.py) then
flags problems; the draft reports them and the pipeline decides what to do. repair_point
rewrites one point given the exact complaints about it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from writing import analyst, models, rules

HERE = Path(__file__).parent
PROMPT = (HERE / "prompts" / "writer.md").read_text()
PROMPT_VERSION = hashlib.sha1(
    (PROMPT + "".join(analyst.GUIDES[n] for n in sorted(analyst.GUIDES))).encode()
).hexdigest()[:8]


class PointOut(BaseModel):
    content: str
    supportedBy: list[str] = []


class WriterOut(BaseModel):
    points: list[PointOut]


@dataclass
class Draft:
    ok: bool
    points: list[dict] = field(default_factory=list)
    issues: dict = field(default_factory=lambda: {"perPoint": [], "listIssues": []})
    result: models.Result | None = None
    messages: list[dict] = field(default_factory=list)
    prompt_version: str = PROMPT_VERSION
    error: str = ""

    @property
    def clean(self) -> bool:
        return self.ok and not self.issues["listIssues"] and not any(self.issues["perPoint"])


def allowed_terms(entry: dict) -> list[str]:
    """Names that may appear in a point without a fact: the entry's own company, title, name."""
    return [str(entry[k]) for k in ("company", "title", "name") if entry.get(k)]


def _facts_text(facts: list[dict]) -> str:
    # Content and owner only. Quotes stay out so the writer works from the cleaned
    # facts and does not copy spoken wording.
    return "\n".join(
        f"[{f['id']}] ({f.get('kind', 'unsorted')}, owner: {f.get('owner', 'unclear')}) {f['content']}"
        for f in facts
    )


def _about(entry: dict) -> str:
    return ", ".join(f"{k}: {entry[k]}" for k in ("title", "company", "name") if entry.get(k)) or "not given"


def build_messages(facts: list[dict], entry: dict, guide: str) -> list[dict]:
    return [
        {"role": "system", "content": f"{PROMPT}\n\n{analyst.GUIDES[guide]}"},
        {
            "role": "user",
            "content": f"The work is described as: {_about(entry)}\n\nFACTS:\n{_facts_text(facts)}",
        },
    ]


def _tidy(points: list[PointOut]) -> list[dict]:
    tidy = []
    for p in points:
        content = p.content.strip().rstrip(".").strip()
        if content:
            tidy.append({"content": content, "supportedBy": [str(i) for i in p.supportedBy]})
    return tidy


def _run(facts: list[dict], entry: dict, messages: list[dict]) -> Draft:
    result = models.complete_json("writer", messages, WriterOut)
    draft = Draft(ok=result.ok, result=result, messages=messages)
    if not result.ok or result.data is None:
        draft.error = result.error
        return draft
    draft.points = _tidy(result.data.points)
    draft.issues = rules.check_points(draft.points, facts, allowed_terms(entry))
    return draft


def write(facts: list[dict], entry: dict | None = None) -> Draft:
    """Points for one entry, with the code-rule issues for each. Never raises for a bad reply."""
    entry = entry or {}
    return _run(facts, entry, build_messages(facts, entry, analyst.pick_guide(entry)))


def repair_point(
    point: dict, issues: list[dict], facts: list[dict], entry: dict | None = None
) -> Draft:
    """Ask for one corrected point, given the exact complaints about the old one."""
    entry = entry or {}
    messages = build_messages(facts, entry, analyst.pick_guide(entry))
    complaints = "\n".join(f"- {i['message']}" for i in issues)
    messages.append({
        "role": "user",
        "content": (
            "Fix this one point.\n"
            f"POINT: {json.dumps({'content': point['content'], 'supportedBy': point.get('supportedBy', [])})}\n"
            f"COMPLAINTS:\n{complaints}"
        ),
    })
    return _run(facts, entry, messages)
