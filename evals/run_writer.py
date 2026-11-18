#!/usr/bin/env python3
"""Run the writer ALONE over the writing test set with the REAL model and print scores.

The writer is given the PERFECT facts for each story (its must-capture phrases), so a bad
point cannot be blamed on a missed fact. Costs a little money; does nothing until you
confirm:

    python evals/run_writer.py            # prints the estimate and stops
    python evals/run_writer.py --yes      # runs it
    python evals/run_writer.py --yes --only we_versus_i_team --show

Needs OPENAI_API_KEY in api/.env. The offline checks (run_evals.py) never use the key.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "evals"))

from dotenv import load_dotenv

load_dotenv(ROOT / "api" / ".env")

import writing_scoring
from writing import analyst, models, records, writer


def load_cases(only: str | None) -> list[dict]:
    paths = sorted((ROOT / "evals" / "writing" / "cases").glob("*.json"))
    cases = [json.loads(p.read_text()) for p in paths]
    return [c for c in cases if not only or c["id"] == only]


def estimate(cases: list[dict]) -> str:
    provider, model = models.resolve("writer")
    in_tokens = sum(
        len(m["content"]) for c in cases
        for m in writer.build_messages(
            writing_scoring.ground_truth_facts(c), c["entry"], analyst.pick_guide(c["entry"])
        )
    ) // 4
    out_tokens = 250 * len(cases)  # a rough guess; the real run reports the real numbers
    cost = records.cost_usd(provider, model, in_tokens, out_tokens)
    price = f"about ${cost:.4f}" if cost is not None else "unpriced model (add it to prices.json)"
    return (
        f"{len(cases)} stories on {provider}:{model}: roughly {in_tokens} input and "
        f"{out_tokens} output tokens, {price}."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="really run (costs money)")
    parser.add_argument("--only", help="run one story by id")
    parser.add_argument("--show", action="store_true", help="print every point and issue")
    args = parser.parse_args()

    cases = load_cases(args.only)
    if not cases:
        print("no such story")
        return 1
    print(estimate(cases))
    if not args.yes:
        print("Not run. Add --yes to run it.")
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set in api/.env")
        return 1

    run = records.Run("writer over the test set, perfect facts")
    scores = []
    for case in cases:
        facts = writing_scoring.ground_truth_facts(case)
        draft = writer.write(facts, case["entry"])
        run.add(draft.result, draft.messages, name=case["id"])
        if not draft.ok:
            print(f"{case['id']:<22} FAILED: {draft.error}")
            continue
        score = writing_scoring.score_points(case, draft.points, draft.issues["perPoint"])
        scores.append(score)
        print(
            f"{case['id']:<22} points {score['points']}  invented {score['invented']}  "
            f"style ok {score['stylePassRate']:.0%}  forbidden {len(score['forbidden'])}"
        )
        if args.show:
            for point, issues in zip(draft.points, draft.issues["perPoint"]):
                flag = ", ".join(i["code"] for i in issues) or "clean"
                print(f"    • {point['content']}  [{flag}]  <- {point['supportedBy']}")
            for i in draft.issues["listIssues"]:
                print(f"    ! {i['message']}")
            for hit in score["forbidden"]:
                print(f"    ✗ says {hit['term']!r} (point {hit['point'] + 1})")
    print()
    print(json.dumps(writing_scoring.summarize_points(scores), indent=2))
    print(json.dumps(run.totals(), indent=2))
    print(f"prompt version {writer.PROMPT_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
