#!/usr/bin/env python3
"""Run deterministic V2 evaluation cases (no LLM required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from context_selector import select_resume_context
from claim_verify import verify_claim
from payload_normalize import normalize_payload
from op_validator import validate_operations
from op_executor import execute_operations


def load_fixture(name: str) -> dict:
    path = ROOT / "evals" / "fixtures" / name
    return normalize_payload(json.loads(path.read_text()))


def test_entity_resolution() -> bool:
    payload = load_fixture("sample_career.json")
    ctx = select_resume_context(payload, "ChaiShots")
    ids = [c.get("id") for c in ctx.get("candidates") or []]
    ok = "exp_chaishots" in ids
    print(f"entity_resolution: {'PASS' if ok else 'FAIL'} (candidates={ids})")
    return ok


def test_skill_delete_op() -> bool:
    payload = load_fixture("sample_career.json")
    ops = [
        {
            "type": "DELETE",
            "target": {"entityType": "skill", "query": "PHP"},
            "changes": {"skill": "PHP"},
        }
    ]
    validated = validate_operations(payload, ops)
    new_payload, applied, diffs = execute_operations(payload, validated)
    skills = new_payload.get("inventory", {}).get("skills") or []
    ok = "PHP" not in skills and len(applied) == 1
    print(f"skill_delete: {'PASS' if ok else 'FAIL'} (skills={skills})")
    return ok


def test_claim_verification() -> bool:
    payload = load_fixture("sample_career.json")
    result = verify_claim(
        payload,
        "Designed scalable distributed systems serving millions of users.",
        [],
    )
    ok = result.get("status") == "unsupported"
    print(f"claim_verification: {'PASS' if ok else 'FAIL'} ({result})")
    return ok


def main() -> int:
    tests = [test_entity_resolution, test_skill_delete_op, test_claim_verification]
    results = [t() for t in tests]
    passed = sum(results)
    print(f"\n{passed}/{len(tests)} eval cases passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
