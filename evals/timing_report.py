#!/usr/bin/env python3
"""
Summarize the server timing log: for each action, how often it ran, its typical
(median) and slow (95th percentile, slowest) times, and its typical reply size.

    python evals/timing_report.py                     # whole log
    python evals/timing_report.py --since 2026-10-20T14:00
    python evals/timing_report.py path/to/timing.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "api" / "logs" / "timing.jsonl"


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest value with pct% of values at or below it."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def load(path: Path, since: str | None) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since and str(record.get("at", "")) < since:
            continue
        records.append(record)
    return records


def summarize(records: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for record in records:
        key = (record.get("method"), record.get("route"))
        groups.setdefault(key, []).append(record)

    rows = []
    for (method, route), items in groups.items():
        ms = [float(r.get("ms") or 0) for r in items]
        sizes = [float(r.get("bytes") or 0) for r in items]
        tidy = [float((r.get("parts") or {}).get("tidy_up")) for r in items
                if (r.get("parts") or {}).get("tidy_up") is not None]
        rows.append(
            {
                "action": f"{method} {route}",
                "runs": len(items),
                "failed": sum(1 for r in items if int(r.get("status") or 0) >= 400),
                "median_ms": percentile(ms, 50),
                "p95_ms": percentile(ms, 95),
                "slowest_ms": max(ms),
                "median_bytes": percentile(sizes, 50),
                "median_tidy_ms": percentile(tidy, 50) if tidy else None,
            }
        )
    return sorted(rows, key=lambda row: -row["median_ms"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("log", nargs="?", default=str(DEFAULT_LOG))
    parser.add_argument("--since", help="only records at or after this ISO time (UTC)")
    args = parser.parse_args()

    path = Path(args.log)
    if not path.exists():
        print(f"No timing log at {path}. Start the API and use the app first.")
        return 1
    rows = summarize(load(path, args.since))
    if not rows:
        print("No matching records.")
        return 1

    header = (
        f"{'action':<52}{'runs':>5}{'failed':>7}{'median':>9}{'95th %':>9}"
        f"{'slowest':>9}{'reply size':>12}{'tidy-up':>9}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        tidy = f"{row['median_tidy_ms']:.0f}ms" if row["median_tidy_ms"] is not None else "-"
        print(
            f"{row['action'][:51]:<52}{row['runs']:>5}{row['failed']:>7}"
            f"{row['median_ms']:>7.0f}ms{row['p95_ms']:>7.0f}ms{row['slowest_ms']:>7.0f}ms"
            f"{row['median_bytes']:>10,.0f} B{tidy:>9}"
        )
    print("\nmedian = typical; 95th % = only the slowest 1 in 20 were slower.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
