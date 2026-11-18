"""Scores for the writing team against the test set (evals/writing/). Code only, no AI.

Kept out of api/: the app never needs these. Imported by run_evals.py and run_analyst.py.
"""

from __future__ import annotations

import re

from writing import rules

# A fact "covers" a must-capture phrase when its quote contains the phrase (or the other
# way round), or holds at least this share of the phrase's words.
WORD_SHARE = 0.7


FILLER = {
    "the", "and", "for", "with", "that", "this", "was", "were", "are", "our", "its",
    "from", "into", "onto", "but", "all", "also", "just", "very", "then", "they", "them",
    "in", "on", "to", "of", "is", "it", "we", "as", "at", "by", "an", "or", "be", "so",
    "my", "me", "us", "up", "do", "did", "had", "has", "have", "got", "like",
}


def _words(text: str) -> set[str]:
    """The meaningful words of a text: no one-letter words (but "Go" stays) and no filler."""
    return {
        w for w in re.findall(r"[a-z0-9+#.%-]+", rules.normalize(text))
        if len(w) > 1 and w not in FILLER
    }


def covers(fact: dict, phrase: str) -> bool:
    quote, wanted = rules.normalize(fact.get("quote")), rules.normalize(phrase)
    if not quote or not wanted:
        return False
    if wanted in quote or quote in wanted:
        return True
    wanted_words = _words(wanted)
    return bool(wanted_words) and len(wanted_words & _words(quote)) / len(wanted_words) >= WORD_SHARE


def score_facts(case: dict, facts: list[dict], dropped: list[dict] | None = None) -> dict:
    """How well one story's facts match what a good analyst had to capture.

    recall      share of must-capture phrases covered by some fact
    ownerRight  of covered phrases whose owner is "me" or "team", the share where the
                matching fact has the same owner (this is the we-versus-I measure)
    dropped     facts the rules threw out (quote not in the story, invented number...)
    """
    captures = case["mustCapture"]
    captured, missed = [], []
    owner_checked = owner_right = 0
    for k in captures:
        match = [f for f in facts if covers(f, k["phrase"])]
        (captured if match else missed).append(k["id"])
        if match and k["owner"] in ("me", "team"):
            owner_checked += 1
            if any(f.get("owner") == k["owner"] for f in match):
                owner_right += 1
    return {
        "case": case["id"],
        "recall": round(len(captured) / len(captures), 3) if captures else 1.0,
        "captured": captured,
        "missed": missed,
        "ownerRight": round(owner_right / owner_checked, 3) if owner_checked else None,
        "factCount": len(facts),
        "dropped": len(dropped or []),
    }


def summarize(scores: list[dict]) -> dict:
    """Averages over many stories. Judge by rates over many cases, never one example."""
    recalls = [s["recall"] for s in scores]
    owners = [s["ownerRight"] for s in scores if s["ownerRight"] is not None]
    return {
        "stories": len(scores),
        "meanRecall": round(sum(recalls) / len(recalls), 3) if recalls else None,
        "worstRecall": min(recalls) if recalls else None,
        "meanOwnerRight": round(sum(owners) / len(owners), 3) if owners else None,
        "droppedFacts": sum(s["dropped"] for s in scores),
        "keptFacts": sum(s["factCount"] for s in scores),
    }


# --- the writer ------------------------------------------------------------------------

# The rule codes live in the app (api/writing/rules.py): the pipeline needs them too.
INVENTION_CODES = rules.INVENTION_CODES
STYLE_CODES = rules.STYLE_CODES


def ground_truth_facts(case: dict) -> list[dict]:
    """The facts a perfect analyst would give for a story. Lets the writer be tested alone."""
    return [
        {"id": f"gt_{k['id']}", "content": k["phrase"], "quote": k["phrase"],
         "kind": k["kind"], "owner": k["owner"], "storyId": case["story"][0]["id"]}
        for k in case["mustCapture"]
    ]


def forbidden_hits(case: dict, points: list[dict]) -> list[dict]:
    """Points that say something the story never said (the story's mustNotClaim list)."""
    hits = []
    for index, point in enumerate(points):
        text = rules.normalize(point.get("content"))
        for term in case["mustNotClaim"]:
            wanted = rules.normalize(term)
            pattern = rf"(?<![a-z0-9]){re.escape(wanted)}(?![a-z0-9])" if wanted[:1].isalnum() else re.escape(wanted)
            if re.search(pattern, text):
                hits.append({"point": index, "term": term})
    return hits


def score_points(case: dict, points: list[dict], per_point_issues: list[list[dict]]) -> dict:
    """How honest and tidy one story's points are.

    inventionRate   share of points the code rules flag as saying more than their facts
    stylePassRate   share of points with no style issue
    forbidden       points containing something the story never said
    """
    count = len(points)
    codes = [{i["code"] for i in issues} for issues in per_point_issues]
    invented = sum(bool(c & INVENTION_CODES) for c in codes)
    clean_style = sum(not (c & STYLE_CODES) for c in codes)
    hits = forbidden_hits(case, points)
    return {
        "case": case["id"],
        "points": count,
        "inventionRate": round(invented / count, 3) if count else 0.0,
        "stylePassRate": round(clean_style / count, 3) if count else 0.0,
        "forbidden": hits,
        "invented": invented,
    }


def story_evidence_issues(case: dict, points: list[str]) -> list[list[dict]]:
    """Issues per point when the whole story is the evidence. Lets the team and the old
    one-pass tidy-up (which has no facts) be judged by the same yardstick: is any number,
    tool or big word in a point missing from what the person said? Ownership claims are
    judged only by the story's must-not-claim list, because the old path has no owners."""
    story = " ".join(str(c.get("text", "")) for c in case["story"])
    evidence = {"id": "story", "content": story, "quote": story, "owner": "me"}
    terms = [str(case["entry"][k]) for k in ("company", "title", "name") if case["entry"].get(k)]
    return [
        rules.check_point({"content": text, "supportedBy": ["story"]}, [evidence], terms)
        for text in points
    ]


def load_traps(path) -> list[dict]:
    """The trap points, each with its facts filled in (a trap may borrow another's)."""
    import json

    traps = json.loads(path.read_text())["traps"]
    by_id = {t["id"]: t for t in traps}
    return [
        {**t, "facts": t.get("facts") or by_id[t["factsFrom"]]["facts"]} for t in traps
    ]


def trap_rows(traps: list[dict], check_fn) -> list[dict]:
    """Run the code rules and a checker over every trap point, one request per point.

    check_fn(points, facts, rule_issues) -> checker.Review. Each row says whether the
    rules flagged the point, whether the checker did, and whether either did.
    """
    rows = []
    for trap in traps:
        point = {"content": trap["point"], "supportedBy": trap["supportedBy"]}
        issues = rules.check_point(point, trap["facts"])
        review = check_fn([point], trap["facts"], [issues])
        rules_flag = bool(issues)
        checker_flag = (
            review.verdicts[0]["verdict"] != "backed" if review.ok and review.verdicts else None
        )
        rows.append({
            "id": trap["id"],
            "label": trap["label"],
            "rulesFlag": rules_flag,
            "checkerFlag": checker_flag,
            "eitherFlag": rules_flag or bool(checker_flag),
        })
    return rows


def score_checker(rows: list[dict]) -> dict:
    """False negatives (exaggerations let through) and false positives (honest points
    rejected), for the rules alone, the checker alone, and both together."""
    bad = [r for r in rows if r["label"] == "exaggerated"]
    good = [r for r in rows if r["label"] == "honest"]

    def rate(count: int, total: int) -> float | None:
        return round(count / total, 3) if total else None

    return {
        "exaggerated": len(bad),
        "caughtByRules": rate(sum(r["rulesFlag"] for r in bad), len(bad)),
        "caughtByChecker": rate(sum(bool(r["checkerFlag"]) for r in bad), len(bad)),
        "caughtByEither": rate(sum(r["eitherFlag"] for r in bad), len(bad)),
        "missedByBoth": [r["id"] for r in bad if not r["eitherFlag"]],
        "honest": len(good),
        "wronglyRejectedByRules": rate(sum(r["rulesFlag"] for r in good), len(good)),
        "wronglyRejectedByChecker": rate(sum(bool(r["checkerFlag"]) for r in good), len(good)),
        "wronglyRejectedByEither": rate(sum(r["eitherFlag"] for r in good), len(good)),
        "checkerFailedSteps": sum(r["checkerFlag"] is None for r in rows),
    }


def summarize_points(scores: list[dict]) -> dict:
    """Totals over many stories: rates are over all points, not averages of averages."""
    total = sum(s["points"] for s in scores)
    return {
        "stories": len(scores),
        "points": total,
        "inventionRate": round(sum(s["invented"] for s in scores) / total, 3) if total else None,
        "stylePassRate": round(
            sum(s["stylePassRate"] * s["points"] for s in scores) / total, 3
        ) if total else None,
        "forbiddenHits": sum(len(s["forbidden"]) for s in scores),
    }
