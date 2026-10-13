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
from claims import new_point, points_for_item
from facts import add_fact, fact_by_id, sync_facts_from_item
from payload_normalize import normalize_payload
from op_validator import validate_operations
from op_executor import execute_operations


def load_raw_fixture(name: str) -> dict:
    path = ROOT / "evals" / "fixtures" / name
    return json.loads(path.read_text())


def load_fixture(name: str) -> dict:
    return normalize_payload(load_raw_fixture(name))


def _point_items(payload: dict):
    sections = payload["inventory"]["sections"]
    for section in ("experience", "projects"):
        for item in sections[section]["items"]:
            yield section, item


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


def test_v5_upgrade_keeps_points() -> bool:
    raw = load_raw_fixture("sample_career.json")
    payload = normalize_payload(raw)
    problems = []
    if raw.get("schemaVersion") != 4:
        problems.append("fixture is no longer a v4 record")
    if payload.get("schemaVersion") != 5:
        problems.append(f"schemaVersion={payload.get('schemaVersion')}")
    raw_items = dict(
        (item["id"], item)
        for _, item in _point_items(raw)
    )
    checked = 0
    for section, item in _point_items(payload):
        before = raw_items[item["id"]]["bullets"]
        checked += len(before)
        if item.get("bullets") != before:
            problems.append(f"{item['id']}: bullets changed")
        points = [p["content"] for p in points_for_item(payload, section, item["id"])]
        if points != before:
            problems.append(f"{item['id']}: points={points}")
        story = item.get("story") or []
        if [s["text"] for s in story] != before or any(
            s["source"] != "legacy" for s in story
        ):
            problems.append(f"{item['id']}: story={story}")
        if (item.get("writing") or {}).get("status") != "idle":
            problems.append(f"{item['id']}: writing={item.get('writing')}")
    ok = not problems and checked > 0
    print(
        f"v5_upgrade_keeps_points: {'PASS' if ok else 'FAIL'} "
        f"(points checked={checked}, problems={problems})"
    )
    return ok


def test_v5_upgrade_is_stable() -> bool:
    raw = load_raw_fixture("sample_career.json")
    once = normalize_payload(raw)
    again = normalize_payload(load_raw_fixture("sample_career.json"))
    twice = normalize_payload(once)
    same_ids = once == again
    settled = once == twice
    ok = same_ids and settled
    print(
        f"v5_upgrade_is_stable: {'PASS' if ok else 'FAIL'} "
        f"(same result each time={same_ids}, no change when repeated={settled})"
    )
    return ok


def test_v5_points_follow_bullets() -> bool:
    payload = load_fixture("sample_career.json")
    before = {p["content"]: p["id"] for p in payload["claims"] if p.get("itemId")}
    generated = {"id": "claim_keepme", "content": "Generated", "supportedBy": []}
    payload["claims"] = [generated] + payload["claims"]
    item = payload["inventory"]["sections"]["experience"]["items"][0]
    item["bullets"] = item["bullets"] + ["Added Redis caching"]
    after = normalize_payload(payload)
    after_points = {p["content"]: p["id"] for p in after["claims"] if p.get("itemId")}
    kept_ids = all(after_points.get(text) == pid for text, pid in before.items())
    added = "Added Redis caching" in after_points
    kept_generated = generated in after["claims"]
    ok = kept_ids and added and kept_generated
    print(
        f"v5_points_follow_bullets: {'PASS' if ok else 'FAIL'} "
        f"(old ids kept={kept_ids}, new point added={added}, "
        f"other claims kept={kept_generated})"
    )
    return ok


def test_v5_blank_record() -> bool:
    problems = []
    for label, source in (("empty", {}), ("not a record", None)):
        blank = normalize_payload(source)
        if blank.get("schemaVersion") != 5:
            problems.append(f"{label}: schemaVersion={blank.get('schemaVersion')}")
        if blank.get("claims") != [] or blank.get("facts") != []:
            problems.append(f"{label}: claims/facts not empty")
        if any(True for _ in _point_items(blank)):
            problems.append(f"{label}: has items")
    ok = not problems
    print(f"v5_blank_record: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_v5_label_defaults() -> bool:
    raw = load_raw_fixture("sample_career.json")
    raw["facts"].append(
        {
            "id": "fact_old_tech",
            "content": "Used Redis",
            "context": {
                "section": "experience",
                "itemId": "exp_chaishots",
                "field": "technologies",
            },
            "source": "user",
        }
    )
    payload = normalize_payload(raw)
    problems = []

    old = fact_by_id(payload, "fact_lambda") or {}
    if old.get("content") != "Built AWS Lambda functions.":
        problems.append(f"old fact text changed: {old.get('content')}")
    labels = (old.get("kind"), old.get("owner"), old.get("quote"), old.get("storyId"))
    if labels != ("unsorted", "unclear", None, None):
        problems.append(f"old fact labels={labels}")
    if (fact_by_id(payload, "fact_old_tech") or {}).get("kind") != "tool":
        problems.append("old technology fact not marked as a tool")

    points = [c for c in payload["claims"] if c.get("itemId")]
    for point in points:
        labels = (point.get("status"), point.get("issues"), point.get("origin"))
        if labels != ("unchecked", [], "legacy"):
            problems.append(f"point {point['id']} labels={labels}")

    item = {"id": "proj_new", "bullets": ["Shipped it"], "technologies": ["Go"]}
    synced = sync_facts_from_item(payload, "projects", item)
    new_kinds = {
        f["content"]: f.get("kind")
        for f in synced["facts"]
        if (f.get("context") or {}).get("itemId") == "proj_new"
    }
    if new_kinds != {"Shipped it": "unsorted", "Used Go": "tool"}:
        problems.append(f"new fact kinds={new_kinds}")

    ok = not problems and len(points) > 0
    print(
        f"v5_label_defaults: {'PASS' if ok else 'FAIL'} "
        f"(points checked={len(points)}, problems={problems})"
    )
    return ok


def test_v5_labels_survive_reload() -> bool:
    payload = load_fixture("sample_career.json")
    fact = fact_by_id(payload, "fact_lambda")
    fact.update(
        {"kind": "action", "owner": "me", "quote": "built lambda functions"}
    )
    point = next(c for c in payload["claims"] if c.get("itemId"))
    point.update(
        {
            "status": "supported",
            "origin": "ai",
            "issues": ["example issue"],
            "supportedBy": ["fact_lambda"],
        }
    )
    expected_fact = dict(fact)
    expected_point = dict(point)
    reloaded = normalize_payload(json.loads(json.dumps(payload)))
    fact_kept = fact_by_id(reloaded, "fact_lambda") == expected_fact
    point_kept = (
        next(c for c in reloaded["claims"] if c.get("id") == point["id"])
        == expected_point
    )
    ok = fact_kept and point_kept
    print(
        f"v5_labels_survive_reload: {'PASS' if ok else 'FAIL'} "
        f"(fact labels kept={fact_kept}, point labels kept={point_kept})"
    )
    return ok


def test_v5_rejects_unknown_labels() -> bool:
    payload = load_fixture("sample_career.json")
    attempts = {
        "fact kind": lambda: add_fact(payload, "Some fact", kind="banana"),
        "fact owner": lambda: add_fact(payload, "Some fact", owner="nobody"),
        "point status": lambda: new_point("experience", "x", "A point", 0, status="fine"),
        "point origin": lambda: new_point("experience", "x", "A point", 0, origin="robot"),
    }
    accepted = []
    for label, attempt in attempts.items():
        try:
            attempt()
            accepted.append(label)
        except ValueError:
            pass
    valid = add_fact(payload, "Cut latency", kind="result", owner="me", quote="cut latency")
    stored = valid["facts"][-1]
    valid_ok = (stored.get("kind"), stored.get("owner"), stored.get("quote")) == (
        "result",
        "me",
        "cut latency",
    )
    ok = not accepted and valid_ok
    print(
        f"v5_rejects_unknown_labels: {'PASS' if ok else 'FAIL'} "
        f"(wrongly accepted={accepted}, valid labels stored={valid_ok})"
    )
    return ok


def main() -> int:
    tests = [
        test_entity_resolution,
        test_skill_delete_op,
        test_claim_verification,
        test_v5_upgrade_keeps_points,
        test_v5_upgrade_is_stable,
        test_v5_points_follow_bullets,
        test_v5_blank_record,
        test_v5_label_defaults,
        test_v5_labels_survive_reload,
        test_v5_rejects_unknown_labels,
    ]
    results = [t() for t in tests]
    passed = sum(results)
    print(f"\n{passed}/{len(tests)} eval cases passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
