"""The checker: reads points against the facts they cite and says what is not backed.

A separate job from the writer (its own model setting), so it can run on a different model
with different blind spots. It can only tighten, never loosen: ordinary code decides what
the rules already caught, and the model's output is checked before it is believed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from writing import models, rules

HERE = Path(__file__).parent
PROMPT = (HERE / "prompts" / "checker.md").read_text()
PROMPT_VERSION = hashlib.sha1(PROMPT.encode()).hexdigest()[:8]
VERDICTS = ("backed", "overstated", "unsupported")


class VerdictOut(BaseModel):
    index: int
    verdict: str
    offending: list[str] = []
    reason: str = ""


class CheckerOut(BaseModel):
    verdicts: list[VerdictOut]


@dataclass
class Review:
    ok: bool
    # One entry per point, in order: verdict (the checker's), final (after the code
    # rules), offending (only words really in the point), located, reason.
    verdicts: list[dict] = field(default_factory=list)
    result: models.Result | None = None
    messages: list[dict] = field(default_factory=list)
    prompt_version: str = PROMPT_VERSION
    error: str = ""


def build_messages(points: list[dict], facts: list[dict]) -> list[dict]:
    facts_text = "\n".join(
        f"[{f['id']}] (owner: {f.get('owner', 'unclear')}) {f['content']}" for f in facts
    )
    points_text = "\n".join(
        f"{i}: {p['content']}  (cites: {', '.join(p.get('supportedBy') or []) or 'nothing'})"
        for i, p in enumerate(points)
    )
    return [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": f"FACTS:\n{facts_text}\n\nPOINTS:\n{points_text}"},
    ]


def _fail(review: Review, message: str) -> Review:
    review.ok = False
    review.verdicts = []
    review.error = message
    return review


def check(
    points: list[dict],
    facts: list[dict],
    rule_issues: list[list[dict]] | None = None,
) -> Review:
    """A verdict for every point. Never raises for a bad reply: see Review.ok.

    rule_issues: the per-point issues from rules.check_points. A point the rules caught
    cannot come out as backed, whatever the model says.
    """
    messages = build_messages(points, facts)
    result = models.complete_json("checker", messages, CheckerOut)
    review = Review(ok=result.ok, result=result, messages=messages)
    if not result.ok or result.data is None:
        review.error = result.error
        return review

    by_index: dict[int, VerdictOut] = {}
    for verdict in result.data.verdicts:
        if verdict.index in by_index:
            return _fail(review, f"two verdicts for point {verdict.index}")
        by_index[verdict.index] = verdict
    if sorted(by_index) != list(range(len(points))):
        # A point without a verdict is never read as backed.
        return _fail(review, "verdicts do not cover every point exactly once")

    for index, point in enumerate(points):
        raw = by_index[index]
        verdict = raw.verdict.strip().lower()
        if verdict not in VERDICTS:
            return _fail(review, f"unknown verdict {raw.verdict!r} for point {index}")
        text = rules.normalize(point["content"])
        offending = [w.strip() for w in raw.offending if w.strip() and rules.normalize(w) in text]
        final, reason = verdict, raw.reason.strip()
        flagged = [
            i for i in (rule_issues[index] if rule_issues else []) if i["code"] in rules.INVENTION_CODES
        ]
        if flagged and verdict == "backed":
            final, reason = "overstated", flagged[0]["message"]
        review.verdicts.append({
            "verdict": verdict,
            "final": final,
            "offending": offending,
            "located": verdict == "backed" or bool(offending),
            "reason": reason,
        })
    return review
