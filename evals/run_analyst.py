#!/usr/bin/env python3
"""Run the analyst over the writing test set with the REAL model and print the scores.

Costs a little money (see the estimate it prints). It does nothing until you confirm:

    python evals/run_analyst.py            # prints the estimate and stops
    python evals/run_analyst.py --yes      # runs it
    python evals/run_analyst.py --yes --only no_numbers --show

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
from writing import analyst, models, records


def load_cases(only: str | None) -> list[dict]:
    paths = sorted((ROOT / "evals" / "writing" / "cases").glob("*.json"))
    cases = [json.loads(p.read_text()) for p in paths]
    return [c for c in cases if not only or c["id"] == only]


def estimate(cases: list[dict]) -> str:
    provider, model = models.resolve("analyst")
    in_tokens = sum(
        len(m["content"]) for c in cases
        for m in analyst.build_messages(c["story"], c["entry"], analyst.pick_guide(c["entry"]))
    ) // 4
    out_tokens = 300 * len(cases)  # a rough guess; the real run reports the real numbers
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
    parser.add_argument("--show", action="store_true", help="print every fact and drop")
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

    run = records.Run("analyst over the test set")
    scores = []
    for case in cases:
        analysis = analyst.analyse(case["story"], case["entry"])
        run.add(analysis.result, analysis.messages, name=case["id"])
        if not analysis.ok:
            print(f"{case['id']:<22} FAILED: {analysis.error}")
            scores.append({**writing_scoring.score_facts(case, []), "failed": True})
            continue
        score = writing_scoring.score_facts(case, analysis.facts, analysis.dropped)
        scores.append(score)
        owner = "n/a" if score["ownerRight"] is None else f"{score['ownerRight']:.0%}"
        print(
            f"{case['id']:<22} recall {score['recall']:.0%}  owner right {owner:<4} "
            f"kept {score['factCount']}  dropped {score['dropped']}  "
            f"missed {score['missed'] or '-'}"
        )
        if args.show:
            for f in analysis.facts:
                print(f"    + [{f['kind']}/{f['owner']}] {f['content']}  <- \"{f['quote']}\"")
            for d in analysis.dropped:
                print(f"    - {d['reason']}: {d['fact'].get('content')}")
            for q in analysis.missing:
                print(f"    ? {q}")
    print()
    print(json.dumps(writing_scoring.summarize(scores), indent=2))
    print(json.dumps(run.totals(), indent=2))
    print(f"prompt version {analyst.PROMPT_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
