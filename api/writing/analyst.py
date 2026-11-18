"""The analyst: a person's story in, grounded facts out. It never writes resume points.

The model proposes facts, each with an exact quote. Ordinary code (rules.check_facts)
then throws out any fact whose quote is not really in the story, so the model cannot
introduce a claim the person did not make.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from writing import models, rules

HERE = Path(__file__).parent
PROMPT = (HERE / "prompts" / "analyst.md").read_text()
GUIDES = {name: (HERE / "guides" / f"{name}.md").read_text() for name in ("tech", "general")}
PROMPT_VERSION = hashlib.sha1(
    (PROMPT + "".join(GUIDES[n] for n in sorted(GUIDES))).encode()
).hexdigest()[:8]
MAX_QUESTIONS = 2

_TECH_WORDS = (
    "engineer", "developer", "software", "devops", "data", "backend", "back-end",
    "frontend", "front-end", "full-stack", "fullstack", "programmer", "sre", "machine learning",
    "ml ", "qa ", "architect", "mobile", "web", "cloud", "security", "platform", "tech lead",
)


class FactOut(BaseModel):
    content: str
    kind: str = "unsorted"
    owner: str = "unclear"
    quote: str


class AnalystOut(BaseModel):
    facts: list[FactOut]
    missing: list[str] = []


@dataclass
class Analysis:
    ok: bool
    facts: list[dict] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    guide: str = ""
    prompt_version: str = PROMPT_VERSION
    result: models.Result | None = None
    messages: list[dict] = field(default_factory=list)
    error: str = ""


def pick_guide(entry: dict) -> str:
    """Tech or general know-how, by simple keyword match. No AI."""
    title = f"{entry.get('title', '')} {entry.get('company', '')} ".lower()
    if entry.get("section") == "projects" or any(word in title for word in _TECH_WORDS):
        return "tech"
    return "general"


def build_messages(story: list[dict], entry: dict, guide: str) -> list[dict]:
    chunks = "\n".join(
        f"[{c.get('id')} | {c.get('source', 'typed')}] {c.get('text', '')}" for c in story
    )
    about = ", ".join(
        f"{k}: {entry[k]}" for k in ("title", "company", "name") if entry.get(k)
    ) or "not given"
    return [
        {"role": "system", "content": f"{PROMPT}\n\n{GUIDES[guide]}"},
        {"role": "user", "content": f"The work is described as: {about}\n\nSTORY:\n{chunks}"},
    ]


def _fact_id(fact: dict) -> str:
    key = "|".join(
        (fact["storyId"], rules.normalize(fact["quote"]), rules.normalize(fact["content"]))
    )
    return "fact_" + hashlib.sha1(key.encode()).hexdigest()[:10]


def analyse(story: list[dict], entry: dict | None = None) -> Analysis:
    """Facts for one entry's story. Never raises for a bad reply: see Analysis.ok."""
    entry = entry or {}
    guide = pick_guide(entry)
    messages = build_messages(story, entry, guide)
    result = models.complete_json("analyst", messages, AnalystOut)
    analysis = Analysis(ok=result.ok, guide=guide, result=result, messages=messages)
    if not result.ok or result.data is None:
        analysis.error = result.error
        return analysis

    proposed = [f.model_dump() for f in result.data.facts]
    kept, dropped = rules.check_facts(proposed, story)
    seen: set[str] = set()
    for fact in kept:
        fact["id"] = _fact_id(fact)
        if fact["id"] in seen:
            dropped.append({"fact": fact, "reason": "duplicate fact"})
            continue
        seen.add(fact["id"])
        analysis.facts.append(fact)
    analysis.dropped = dropped
    analysis.missing = [
        q.strip() for q in result.data.missing if str(q).strip()
    ][:MAX_QUESTIONS]
    return analysis
