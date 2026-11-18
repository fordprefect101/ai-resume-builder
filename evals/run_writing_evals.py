#!/usr/bin/env python3
"""Measure the whole writing team on the test set, side by side with today's tidy-up.

Uses the REAL model and costs money, so it prints an estimate and stops until you add
--yes. It reads OPENAI_API_KEY (and the model settings) from api/.env or your shell, and
only when actually run: importing this file reads nothing.

    python evals/run_writing_evals.py                      # estimate only
    python evals/run_writing_evals.py --yes                # 3 runs over every story
    python evals/run_writing_evals.py --yes --runs 1 --only no_numbers --show
    python evals/run_writing_evals.py --yes --save-baseline   # keep this report as the bar

Models answer differently each time, so every figure is a mean over --runs with its
worst case. A report is saved in evals/writing/reports/. The run exits with a failure if
the code-counted invention rate got worse than the saved baseline: that is the one rule
fixed from the start.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "evals"))

import writing_baseline
import writing_scoring
from writing import analyst, checker, models, pipeline, records, rules, writer

CASES = ROOT / "evals" / "writing" / "cases"
TRAPS = ROOT / "evals" / "writing" / "traps.json"
REPORTS = ROOT / "evals" / "writing" / "reports"
BASELINE = REPORTS / "baseline.json"


def load_cases(only: str | None = None) -> list[dict]:
    cases = [json.loads(p.read_text()) for p in sorted(CASES.glob("*.json"))]
    return [c for c in cases if not only or c["id"] == only]


def stats(values) -> dict | None:
    """Mean, lowest and highest of a figure over the runs. None entries are skipped."""
    values = [v for v in values if v is not None]
    if not values:
        return None
    # six places: a cost of a fraction of a cent per entry must not round away to zero
    return {"mean": round(sum(values) / len(values), 6), "min": min(values), "max": max(values)}


# --- one run ---------------------------------------------------------------------------

def run_entry(case: dict) -> dict:
    """The writing team on one story, scored."""
    result = pipeline.run_pipeline(case["story"], case["entry"])
    points = [{"content": p["content"], "supportedBy": p["supportedBy"]} for p in result.points]
    texts = [p["content"] for p in points]
    per_point = (
        rules.check_points(points, result.facts, writer.allowed_terms(case["entry"]))["perPoint"]
        if points else []
    )
    steps = result.run.steps if result.run else []
    return {
        "case": case["id"],
        "ok": result.ok,
        "stage": result.stage,
        "error": result.error,
        "facts": writing_scoring.score_facts(case, result.facts, result.dropped_facts),
        "team": writing_scoring.score_points(case, points, per_point),
        "teamVsStory": writing_scoring.score_points(
            case, points, writing_scoring.story_evidence_issues(case, texts)
        ),
        "statuses": dict(Counter(p["status"] for p in result.points)),
        "fallbackPoints": sum(p["fallback"] for p in result.points),
        "droppedPoints": len(result.dropped_points),
        "repairCalls": sum(s["step"].startswith("repair") for s in steps),
        "checkerCalls": sum(s["step"].startswith("checker") for s in steps),
        "totals": result.totals,
        "questions": result.missing,
        "points": result.points,
    }


def run_baseline(case: dict) -> dict:
    """Today's one-pass tidy-up on one story, judged by the same yardstick."""
    try:
        texts = writing_baseline.tidy(case)
    except Exception as exc:  # the old path has no failed-step handling of its own
        return {"case": case["id"], "failed": f"{type(exc).__name__}: {exc}", "score": None}
    issues = writing_scoring.story_evidence_issues(case, texts)
    return {"case": case["id"], "failed": "", "score": writing_scoring.score_points(
        case, [{"content": t} for t in texts], issues), "points": texts}


def run_once(cases: list[dict], traps: list[dict], *, with_baseline: bool = True) -> dict:
    entries = [run_entry(c) for c in cases]
    done = [e for e in entries if e["team"]["points"]]
    baselines = [run_baseline(c) for c in cases] if with_baseline else []
    rows = writing_scoring.trap_rows(traps, lambda p, f, i: checker.check(p, f, i)) if traps else []
    status_totals = Counter()
    for e in entries:
        status_totals.update(e["statuses"])
    points_total = sum(status_totals.values()) or None
    return {
        "entries": entries,
        "analyst": writing_scoring.summarize([e["facts"] for e in entries]),
        "team": writing_scoring.summarize_points([e["team"] for e in done]),
        "teamVsStory": writing_scoring.summarize_points([e["teamVsStory"] for e in done]),
        "baseline": writing_scoring.summarize_points(
            [b["score"] for b in baselines if b["score"] and b["score"]["points"]]
        ) if baselines else None,
        "baselineFailed": sum(bool(b["failed"]) for b in baselines),
        "checker": writing_scoring.score_checker(rows) if rows else None,
        "outcomes": {
            "failedStories": sum(not e["ok"] for e in entries),
            "emptyStories": sum(e["ok"] and not e["team"]["points"] for e in entries),
            "supportedRate": round(status_totals["supported"] / points_total, 3) if points_total else None,
            "needsReviewRate": round(status_totals["needs_review"] / points_total, 3) if points_total else None,
            "uncheckedRate": round(status_totals["unchecked"] / points_total, 3) if points_total else None,
            "fallbackRate": round(sum(e["fallbackPoints"] for e in entries) / points_total, 3) if points_total else None,
            "repairCallsPerStory": round(sum(e["repairCalls"] for e in entries) / len(entries), 3),
        },
        "cost": {
            "usdPerEntry": round(sum(e["totals"].get("costUsd", 0) for e in entries) / len(entries), 6),
            "secondsPerEntry": round(sum(e["totals"].get("seconds", 0) for e in entries) / len(entries), 3),
            "tokensPerEntry": round(sum(e["totals"].get("inputTokens", 0) + e["totals"].get("outputTokens", 0) for e in entries) / len(entries)),
            "unpricedSteps": sum(e["totals"].get("unpricedSteps", 0) for e in entries),
        },
    }


# --- many runs -------------------------------------------------------------------------

def per_story(case_id: str, results: list[dict]) -> dict:
    """One story's figures across all the runs."""
    entries = [next(e for e in r["entries"] if e["case"] == case_id) for r in results]
    return {
        "story": case_id,
        "recall": stats([e["facts"]["recall"] for e in entries]),
        # a run that wrote no points says nothing about invention, so it is skipped
        "inventionRate": stats([e["team"]["inventionRate"] if e["team"]["points"] else None for e in entries]),
        "forbidden": sum(len(e["team"]["forbidden"]) for e in entries),
    }


def evaluate(
    cases: list[dict], traps: list[dict], runs: int = 3, *, with_baseline: bool = True
) -> dict:
    """Run everything `runs` times and report each figure as mean / lowest / highest."""
    results = [run_once(cases, traps, with_baseline=with_baseline) for _ in range(runs)]

    def over(*path):
        values = []
        for r in results:
            node = r
            for key in path:
                node = node.get(key) if isinstance(node, dict) else None
            values.append(node)
        return stats(values)

    jobs = {job: "%s:%s" % models.resolve(job) for job in models.JOB_SETTINGS}
    report = {
        "meta": {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "runs": runs,
            "stories": [c["id"] for c in cases],
            "trapPoints": len(traps),
            "models": jobs,
            "promptVersions": {
                "analyst": analyst.PROMPT_VERSION,
                "writer": writer.PROMPT_VERSION,
                "checker": checker.PROMPT_VERSION,
            },
        },
        "analyst": {
            "recall": over("analyst", "meanRecall"),
            "worstStoryRecall": over("analyst", "worstRecall"),
            "ownerRight": over("analyst", "meanOwnerRight"),
        },
        "team": {
            "inventionRate": over("team", "inventionRate"),
            "inventionRateVsStory": over("teamVsStory", "inventionRate"),
            "stylePassRate": over("team", "stylePassRate"),
            "forbiddenHits": over("team", "forbiddenHits"),
            **{k: over("outcomes", k) for k in (
                "supportedRate", "needsReviewRate", "uncheckedRate", "fallbackRate",
                "repairCallsPerStory", "failedStories", "emptyStories")},
        },
        "baseline": None if not with_baseline else {
            "inventionRateVsStory": over("baseline", "inventionRate"),
            "stylePassRate": over("baseline", "stylePassRate"),
            "forbiddenHits": over("baseline", "forbiddenHits"),
            "failedStories": over("baselineFailed"),
            "cost": "not measured (the old path does not report its token use)",
        },
        "checker": None if not traps else {
            k: over("checker", k) for k in (
                "caughtByRules", "caughtByChecker", "caughtByEither",
                "wronglyRejectedByRules", "wronglyRejectedByChecker", "wronglyRejectedByEither",
                "checkerFailedSteps")
        } | {"missedByBoth": sorted({i for r in results for i in r["checker"]["missedByBoth"]})},
        "cost": {k: over("cost", k) for k in ("usdPerEntry", "secondsPerEntry", "tokensPerEntry", "unpricedSteps")},
        "followUps": [
            {"story": e["case"], "asked": e["questions"],
             "shouldAskAbout": next(c["missing"] for c in cases if c["id"] == e["case"])}
            for e in results[0]["entries"]
        ],
        "perStory": [per_story(c["id"], results) for c in cases],
        "samplePoints": {e["case"]: [p["content"] for p in e["points"]] for e in results[0]["entries"]},
    }
    return report


def compare(report: dict, baseline: dict, tolerance: float = 0.0) -> list[str]:
    """What got worse than the saved baseline. Only invention is a hard rule; the quality
    bar for everything else is set from real measurements, not fixed up front."""
    worse = []
    for label, path in (
        ("invention rate (against the facts)", ("team", "inventionRate")),
        ("invention rate (against the story)", ("team", "inventionRateVsStory")),
        ("words the story never said", ("team", "forbiddenHits")),
    ):
        new, old = report, baseline
        for key in path:
            new = (new or {}).get(key)
            old = (old or {}).get(key)
        if new and old and new["mean"] > old["mean"] + tolerance:
            worse.append(f"{label}: {old['mean']} -> {new['mean']}")
    return worse


# --- cost estimate and output ----------------------------------------------------------

def estimate(cases: list[dict], traps: list[dict], runs: int, with_baseline: bool = True) -> dict:
    """A rough cost before spending anything. The real run reports the real figures."""
    tokens = {"analyst": [0, 0], "writer": [0, 0], "checker": [0, 0]}
    calls = 0
    guess = [{"content": "x" * 120, "supportedBy": []}] * 3
    for c in cases:
        facts = writing_scoring.ground_truth_facts(c)
        size = lambda msgs: sum(len(m["content"]) for m in msgs) // 4
        tokens["analyst"][0] += size(analyst.build_messages(c["story"], c["entry"], analyst.pick_guide(c["entry"])))
        tokens["analyst"][1] += 300
        tokens["writer"][0] += size(writer.build_messages(facts, c["entry"], analyst.pick_guide(c["entry"])))
        tokens["writer"][1] += 250
        # one check plus about one more after repairs, and about one repair
        tokens["checker"][0] += 2 * size(checker.build_messages(guess, facts))
        tokens["writer"][0] += size(writer.build_messages(facts, c["entry"], analyst.pick_guide(c["entry"])))
        tokens["checker"][1] += 2 * 150
        calls += 5 + (1 if with_baseline else 0)
    for trap in traps:
        tokens["checker"][0] += size(checker.build_messages([{"content": trap["point"], "supportedBy": trap["supportedBy"]}], trap["facts"]))
        tokens["checker"][1] += 100
        calls += 1
    total, priced = 0.0, True
    for job, (tin, tout) in tokens.items():
        cost = records.cost_usd(*models.resolve(job), tin * runs, tout * runs)
        priced, total = priced and cost is not None, total + (cost or 0)
    if with_baseline:  # one tidy-up call per story, about 700 in and 150 out
        base = records.cost_usd(*models.resolve("writer"), 700 * len(cases) * runs, 150 * len(cases) * runs)
        priced, total = priced and base is not None, total + (base or 0)
    return {"calls": calls * runs, "costUsd": round(total, 4) if priced else None,
            "models": {job: "%s:%s" % models.resolve(job) for job in tokens}}


def _fmt(stat, places: int = 3) -> str:
    if not stat:
        return "n/a"
    return f"{stat['mean']:.{places}f} [{stat['min']:.{places}f} to {stat['max']:.{places}f}]"


def print_report(report: dict, show: bool = False) -> None:
    meta, team, base, chk = report["meta"], report["team"], report["baseline"], report["checker"]
    print(f"\n{len(meta['stories'])} stories x {meta['runs']} runs   models {meta['models']}")
    print(f"prompt versions {meta['promptVersions']}\n")
    print("Analyst (finding the facts)")
    print(f"  recall            {_fmt(report['analyst']['recall'])}   weakest story {_fmt(report['analyst']['worstStoryRecall'])}")
    print(f"  owner right       {_fmt(report['analyst']['ownerRight'])}   (we stays team, I stays me)")
    print("\nTeam vs today's one-pass tidy-up (same yardstick: is anything in a point missing from the story?)")
    print(f"  invention rate    team {_fmt(team['inventionRateVsStory'])}   today {_fmt(base and base['inventionRateVsStory'])}")
    print(f"  said what the story never said   team {_fmt(team['forbiddenHits'])}   today {_fmt(base and base['forbiddenHits'])}")
    print(f"  style pass rate   team {_fmt(team['stylePassRate'])}   today {_fmt(base and base['stylePassRate'])}")
    print(f"\nTeam, strict yardstick (every number and tool must be in the cited facts)")
    print(f"  invention rate    {_fmt(team['inventionRate'])}")
    print(f"  supported {_fmt(team['supportedRate'])}   needs review {_fmt(team['needsReviewRate'])}   unchecked {_fmt(team['uncheckedRate'])}")
    print(f"  plain fallback points {_fmt(team['fallbackRate'])}   repairs per story {_fmt(team['repairCallsPerStory'])}   failed stories {_fmt(team['failedStories'])}")
    if chk:
        print("\nChecker on the trap points (exaggerations caught / honest points wrongly rejected)")
        print(f"  rules alone   {_fmt(chk['caughtByRules'])} / {_fmt(chk['wronglyRejectedByRules'])}")
        print(f"  checker alone {_fmt(chk['caughtByChecker'])} / {_fmt(chk['wronglyRejectedByChecker'])}")
        print(f"  both          {_fmt(chk['caughtByEither'])} / {_fmt(chk['wronglyRejectedByEither'])}   missed by both: {chk['missedByBoth'] or 'none'}")
    cost = report["cost"]
    print(f"\nCost per entry    ${_fmt(cost['usdPerEntry'], 5)}   {_fmt(cost['secondsPerEntry'], 1)} s   {_fmt(cost['tokensPerEntry'], 0)} tokens   unpriced steps {_fmt(cost['unpricedSteps'], 0)}")
    print("\nPer story")
    for s in report["perStory"]:
        print(f"  {s['story']:<22} recall {_fmt(s['recall'])}   invention {_fmt(s['inventionRate'])}   forbidden {s['forbidden']}")
    print("\nFollow-up questions (read these yourself: do they ask about what is really missing?)")
    for f in report["followUps"]:
        print(f"  {f['story']:<22} asked {f['asked'] or '-'}   should ask about {f['shouldAskAbout']}")
    if show:
        print("\nSample points (first run)")
        for story, texts in report["samplePoints"].items():
            print(f"  {story}")
            for text in texts:
                print(f"    - {text}")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="really run (costs money)")
    parser.add_argument("--runs", type=int, default=3, help="repeat everything this many times")
    parser.add_argument("--only", help="one story by id")
    parser.add_argument("--no-baseline", action="store_true", help="skip today's tidy-up")
    parser.add_argument("--no-traps", action="store_true", help="skip the checker trap points")
    parser.add_argument("--show", action="store_true", help="also print the points written")
    parser.add_argument("--save-baseline", action="store_true", help="keep this report as the bar")
    parser.add_argument("--tolerance", type=float, default=0.0, help="slack allowed on invention rates")
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    # Settings and the key are read here, when the command is actually run: never on import.
    from dotenv import load_dotenv

    load_dotenv(ROOT / "api" / ".env")

    cases = load_cases(args.only)
    if not cases:
        print("no such story")
        return 1
    traps = [] if args.no_traps else writing_scoring.load_traps(TRAPS)
    plan = estimate(cases, traps, args.runs, not args.no_baseline)
    price = f"about ${plan['costUsd']:.3f}" if plan["costUsd"] is not None else "a model has no listed price (prices.json)"
    print(f"{len(cases)} stories, {len(traps)} trap points, {args.runs} run(s): roughly {plan['calls']} model calls, {price}.")
    print(f"models: {plan['models']}")
    if not args.yes:
        print("Not run. Add --yes to run it.")
        return 0
    import os

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set (api/.env or your shell).")
        return 1

    report = evaluate(cases, traps, args.runs, with_baseline=not args.no_baseline)
    print_report(report, args.show)
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    saved = REPORTS / f"report-{stamp}.json"
    saved.write_text(json.dumps(report, indent=2))
    print(f"\nreport saved: {saved}")
    status = 0
    if BASELINE.exists() and not args.save_baseline:
        worse = compare(report, json.loads(BASELINE.read_text()), args.tolerance)
        if worse:
            print("\nWORSE THAN THE BASELINE:")
            for line in worse:
                print(f"  {line}")
            status = 1
        else:
            print("\nNothing got worse than the baseline.")
    if args.save_baseline:
        BASELINE.write_text(json.dumps(report, indent=2))
        print(f"baseline saved: {BASELINE}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
