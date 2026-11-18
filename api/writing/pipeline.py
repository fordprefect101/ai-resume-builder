"""The writing team's pipeline: one entry's story in, checked facts and points out.

Fixed order, controlled by ordinary code:
  guards -> analyst -> rule check -> writer -> rule check -> checker
         -> repair (at most two rounds) -> safe fallback -> statuses

Nothing here saves anything: it returns a PipelineResult for the caller to store. It never
raises for a model problem; a failed stage is reported in the result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from writing import analyst, checker, records, rules, writer

MAX_STORY_CHARS = 6000
MAX_REPAIR_ROUNDS = 2
MAX_REWRITES_PER_HOUR = 10  # per resume; enforced where the run records are stored


@dataclass
class PipelineResult:
    ok: bool
    stage: str  # guard, analyst, no_facts, writer, or done
    error: str = ""
    facts: list[dict] = field(default_factory=list)
    dropped_facts: list[dict] = field(default_factory=list)
    # {content, supportedBy, status, issues, origin, fallback}; status is
    # supported (code rules and checker agree), needs_review (a plain safe point was
    # used instead) or unchecked (the checker was unavailable).
    points: list[dict] = field(default_factory=list)
    dropped_points: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    run: records.Run | None = None
    prompt_versions: dict = field(default_factory=dict)

    @property
    def totals(self) -> dict:
        return self.run.totals() if self.run else {}


def plain_point(fact: dict) -> str:
    """A safe point made from one fact: first person removed, capitalised, no final period."""
    text = re.sub(r"^(?:i|we)(?:'ve|'m)?\s+", "", str(fact.get("content", "")).strip(), flags=re.I)
    text = text.strip().rstrip(".").strip()
    return text[:1].upper() + text[1:]


def _problems(point_issues: list[dict], verdict: dict | None) -> list[dict]:
    """Everything wrong with one point: rule issues, plus the checker's complaint."""
    problems = list(point_issues)
    # Only the checker's own verdict adds a complaint. When a code rule overruled a
    # "backed" verdict, the rule's issue is already in the list.
    if verdict and verdict["verdict"] != "backed":
        words = f" Words: {', '.join(verdict['offending'])}." if verdict["offending"] else ""
        problems.append(rules.issue(
            f"checker_{verdict['verdict']}",
            f"The checker says this point is {verdict['verdict']}: {verdict['reason']}{words}",
        ))
    return problems


def _tidy_list(points: list[dict]) -> tuple[list[dict], list[dict]]:
    """Drop repeated points and anything past the limit. Plain code, no model."""
    kept, dropped, seen = [], [], set()
    for point in points:
        key = rules.normalize(point["content"])
        if key in seen:
            dropped.append({"content": point["content"], "reason": "repeated point"})
        elif len(kept) >= rules.MAX_POINTS:
            dropped.append({"content": point["content"], "reason": "more than the limit"})
        else:
            seen.add(key)
            kept.append(point)
    return kept, dropped


def run_pipeline(story: list[dict], entry: dict | None = None) -> PipelineResult:
    entry = entry or {}
    run = records.Run(f"writing team: {entry.get('title') or entry.get('name') or 'entry'}")
    result = PipelineResult(
        ok=False, stage="guard", run=run,
        prompt_versions={
            "analyst": analyst.PROMPT_VERSION, "writer": writer.PROMPT_VERSION,
            "checker": checker.PROMPT_VERSION,
        },
    )

    # --- guards: no model is called for these ---
    text = " ".join(str(c.get("text", "")) for c in story).strip()
    if not text:
        result.error = "There is nothing to write from: the story is empty."
        return result
    if len(text) > MAX_STORY_CHARS:
        result.error = (
            f"The story is {len(text)} characters; the limit is {MAX_STORY_CHARS}. "
            "Split it into separate entries."
        )
        return result

    # --- analyst ---
    analysis = analyst.analyse(story, entry)
    run.add(analysis.result, analysis.messages, name="analyst")
    result.facts, result.dropped_facts, result.missing = (
        analysis.facts, analysis.dropped, analysis.missing,
    )
    if not analysis.ok:
        result.stage, result.error = "analyst", analysis.error
        return result
    if not analysis.facts:
        result.ok, result.stage = True, "no_facts"
        return result
    facts = analysis.facts
    terms = writer.allowed_terms(entry)

    # --- writer ---
    draft = writer.write(facts, entry)
    run.add(draft.result, draft.messages, name="writer")
    if not draft.ok:
        result.stage, result.error = "writer", draft.error
        return result
    points, result.dropped_points = _tidy_list(draft.points)
    if not points:
        result.stage, result.error = "writer", "The writer produced no points."
        return result

    # --- checker, then repair rounds ---
    issues = rules.check_points(points, facts, terms)["perPoint"]
    review = checker.check(points, facts, issues)
    run.add(review.result, review.messages, name="checker")

    for round_number in range(1, MAX_REPAIR_ROUNDS + 1):
        verdicts = review.verdicts if review.ok else [None] * len(points)
        failing = [i for i in range(len(points)) if _problems(issues[i], verdicts[i])]
        if not failing:
            break
        for i in failing:
            fixed = writer.repair_point(
                points[i], _problems(issues[i], verdicts[i]), facts, entry
            )
            run.add(fixed.result, fixed.messages, name=f"repair {round_number}")
            if fixed.ok and fixed.points:
                points[i] = fixed.points[0]
        points, more_dropped = _tidy_list(points)
        result.dropped_points += more_dropped
        issues = rules.check_points(points, facts, terms)["perPoint"]
        review = checker.check(points, facts, issues)
        run.add(review.result, review.messages, name=f"checker {round_number + 1}")

    # --- statuses, and the safe fallback for points that never got fixed ---
    verdicts = review.verdicts if review.ok else [None] * len(points)
    by_id = {f["id"]: f for f in facts}
    for i, point in enumerate(points):
        problems = _problems(issues[i], verdicts[i])
        if not problems and review.ok:
            result.points.append({**point, "status": "supported", "issues": [],
                                  "origin": "ai", "fallback": False})
        elif not problems:
            result.points.append({
                **point, "status": "unchecked", "origin": "ai", "fallback": False,
                "issues": [rules.issue("checker_unavailable", "The checker could not run, so this point is not verified.")],
            })
        else:
            cited = next((by_id[f] for f in point["supportedBy"] if f in by_id), None)
            safe = {"content": plain_point(cited), "supportedBy": [cited["id"]]} if cited else None
            if safe and not rules.check_point(safe, facts, terms):
                result.points.append({**safe, "status": "needs_review", "issues": problems,
                                      "origin": "ai", "fallback": True})
            else:
                result.dropped_points.append({
                    "content": point["content"],
                    "reason": "no safe version could be built from its fact",
                })
    result.ok, result.stage = True, "done"
    return result
