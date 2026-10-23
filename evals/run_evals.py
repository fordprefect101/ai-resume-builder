#!/usr/bin/env python3
"""Run deterministic V2 evaluation cases (no LLM required)."""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

# These evals never reach a database or a model; placeholders let main.py import.
os.environ.setdefault("DATABASE_URL", "postgresql://unused-in-evals")
os.environ.setdefault("OPENAI_API_KEY", "unused-in-evals")

from context_selector import select_resume_context
from claim_verify import verify_claim
from claims import new_point, points_for_item
from facts import add_fact, fact_by_id, sync_facts_from_item
from payload_normalize import normalize_payload
from op_validator import validate_operations
from op_executor import execute_operations
from resume_ops import add_item, apply_item_enrichment, archive_item, update_item


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


def _copies_out_of_step(payload: dict) -> list[str]:
    """Items whose bullets (display copy) differ from their point records."""
    return [
        item["id"]
        for section, item in _point_items(payload)
        if item.get("bullets")
        != [p["content"] for p in points_for_item(payload, section, item["id"])]
    ]


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


def test_v5_bullets_follow_points() -> bool:
    payload = load_fixture("sample_career.json")
    generated = {"id": "claim_keepme", "content": "Generated", "supportedBy": []}
    payload["claims"] = [generated] + payload["claims"]
    items = payload["inventory"]["sections"]["experience"]["items"]
    original = list(items[0]["bullets"])

    # Tampering with the display copy is undone from the points.
    items[0]["bullets"] = ["Typed straight into the copy"]
    restored = normalize_payload(payload)
    restored_item = restored["inventory"]["sections"]["experience"]["items"][0]
    tamper_undone = restored_item["bullets"] == original

    # Changing the point records changes the display copy.
    edited = json.loads(json.dumps(restored))
    point = next(c for c in edited["claims"] if c.get("itemId") == items[0]["id"])
    point["content"] = "Rewritten point"
    after_edit = normalize_payload(edited)
    edit_shown = after_edit["inventory"]["sections"]["experience"]["items"][0][
        "bullets"
    ] == ["Rewritten point"]

    # A v5 item that has bullets but no point records adopts them.
    orphan = json.loads(json.dumps(restored))
    orphan["inventory"]["sections"]["projects"]["items"].append(
        {"id": "proj_adopt", "name": "Adopt me", "bullets": ["Kept point"]}
    )
    adopted = normalize_payload(orphan)
    adopted_points = [
        p["content"] for p in points_for_item(adopted, "projects", "proj_adopt")
    ]
    adoption = adopted_points == ["Kept point"]

    kept_generated = all(
        generated in p["claims"] for p in (restored, after_edit, adopted)
    )
    in_step = not any(
        _copies_out_of_step(p) for p in (restored, after_edit, adopted)
    )
    ok = tamper_undone and edit_shown and adoption and kept_generated and in_step
    print(
        f"v5_bullets_follow_points: {'PASS' if ok else 'FAIL'} "
        f"(tampering undone={tamper_undone}, point edit shown={edit_shown}, "
        f"bullets without points adopted={adoption}, "
        f"other claims kept={kept_generated}, copies match={in_step})"
    )
    return ok


def test_v5_writers_keep_copies_in_step() -> bool:
    payload = load_fixture("sample_career.json")
    problems = []

    def check(label: str, current: dict) -> None:
        bad = _copies_out_of_step(current)
        if bad:
            problems.append(f"{label}: out of step {bad}")
        if normalize_payload(json.loads(json.dumps(current))) != normalize_payload(
            normalize_payload(json.loads(json.dumps(current)))
        ):
            problems.append(f"{label}: not stable on reload")

    # Mark an existing point so we can see its labels survive later changes.
    first = points_for_item(payload, "experience", "exp_chaishots")[0]
    first.update({"status": "supported", "supportedBy": ["fact_lambda"]})

    payload, new_id = add_item(
        payload,
        "experience",
        {"company": "NewCo", "title": "Engineer", "bullets": ["Built A", "Built B"]},
    )
    check("add_item", payload)
    if [p["content"] for p in points_for_item(payload, "experience", new_id)] != [
        "Built A",
        "Built B",
    ]:
        problems.append("add_item: points not created from supplied bullets")

    payload = update_item(
        payload, "experience", "exp_chaishots", {"bullets": {"add": ["Added Redis"]}}
    )
    check("update add", payload)
    kept = points_for_item(payload, "experience", "exp_chaishots")[0]
    if (kept["id"], kept["status"], kept["supportedBy"]) != (
        first["id"],
        "supported",
        ["fact_lambda"],
    ):
        problems.append("update add: unchanged point lost its id or labels")

    payload = update_item(
        payload, "experience", new_id, {"bullets": {"remove": ["Built A"]}}
    )
    check("update remove", payload)
    payload = update_item(
        payload, "experience", new_id, {"bullets": {"set": ["Only this", "And this"]}}
    )
    check("update set", payload)
    payload = update_item(payload, "experience", new_id, {"bullets": ["Plain list"]})
    check("update plain list", payload)

    payload = apply_item_enrichment(
        payload,
        "experience",
        "exp_hyrefox",
        {"bullets": ["Polished ML pipelines"], "skills": ["Python"]},
    )
    check("enrichment", payload)

    ops = validate_operations(
        payload,
        [
            {
                "type": "UPDATE",
                "target": {"section": "experience", "entityId": "exp_hyrefox"},
                "changes": {"bullets": {"add": ["Typed request point"]}},
            }
        ],
    )
    payload, _applied, _diffs = execute_operations(payload, ops)
    check("typed request", payload)

    payload = archive_item(payload, "experience", new_id)
    check("archive", payload)

    final = {
        item["id"]: item["bullets"] for _, item in _point_items(payload)
    }
    expected = {
        "exp_chaishots": ["Built personalization pipeline", "Added Redis"],
        "exp_hyrefox": ["Polished ML pipelines", "Typed request point"],
        new_id: ["Plain list"],
    }
    if final != expected:
        problems.append(f"final bullets={final}")

    ok = not problems
    print(
        f"v5_writers_keep_copies_in_step: {'PASS' if ok else 'FAIL'} "
        f"(problems={problems})"
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


class _FakeCursor:
    """Stands in for a database cursor: records statements, returns saved rows."""

    def __init__(self, version: int = 1):
        self.statements: list[tuple[str, tuple]] = []
        self.version = version
        self._row = None

    def execute(self, sql: str, params: tuple = ()) -> None:
        text = " ".join(sql.split())
        self.statements.append((text, params))
        if text.startswith("UPDATE resume_snapshots"):
            self.version += 1
            self._row = (params[1], json.loads(params[0]), self.version)
        elif text.startswith("INSERT INTO resume_snapshots"):
            self._row = (params[0], json.loads(params[1]), self.version)
        else:
            self._row = None

    def fetchone(self):
        return self._row

    def ran(self, prefix: str) -> list[tuple]:
        return [params for text, params in self.statements if text.startswith(prefix)]


def test_save_door() -> bool:
    import main

    problems = []
    previous = load_fixture("sample_career.json")
    # add_item leaves the new item without a story/writing marker until normalized.
    untidy, new_id = add_item(
        previous, "projects", {"name": "Side project", "bullets": ["Built it"]}
    )

    cur = _FakeCursor(version=7)
    saved = main._save_payload(
        cur,
        "sess_1",
        previous,
        untidy,
        operations=[{"type": "TOOL", "tool": "add_item"}],
        summary="Added an entry to projects",
    )
    stored = saved[1]
    if stored != normalize_payload(stored) or _copies_out_of_step(stored):
        problems.append("stored record was not tidied before saving")
    new_item = next(
        i for i in stored["inventory"]["sections"]["projects"]["items"] if i["id"] == new_id
    )
    if "story" not in new_item or "writing" not in new_item:
        problems.append("new entry saved without story/writing")
    undo = cur.ran("INSERT INTO resume_undo")
    if len(undo) != 1 or json.loads(undo[0][1]) != previous:
        problems.append("undo copy of the previous record not kept")
    history = cur.ran("INSERT INTO career_versions")
    if len(history) != 1:
        problems.append(f"history entries written={len(history)}")
    else:
        _sid, version_num, operations, snapshot, summary = history[0]
        if (version_num, summary) != (8, "Added an entry to projects"):
            problems.append(f"history entry={version_num, summary}")
        if json.loads(snapshot) != stored or not json.loads(operations):
            problems.append("history entry does not match what was stored")

    cur = _FakeCursor(version=3)
    main._save_payload(
        cur,
        "sess_1",
        None,
        previous,
        operations=[{"type": "UNDO"}],
        summary="Undid last change",
        undoable=False,
    )
    if cur.ran("INSERT INTO resume_undo"):
        problems.append("undo added itself to the undo list")
    if len(cur.ran("INSERT INTO career_versions")) != 1:
        problems.append("undo was not recorded in history")

    cur = _FakeCursor(version=1)
    created = main._create_snapshot(
        cur, "sess_new", {}, None, summary="Resume created"
    )
    first = cur.ran("INSERT INTO career_versions")
    if created[1].get("schemaVersion") != 5:
        problems.append("new record not created in the current shape")
    if len(first) != 1 or (first[0][1], first[0][4]) != (1, "Resume created"):
        problems.append("new record has no first history entry")

    ok = not problems
    print(f"save_door: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


class _FakeConnection:
    """A stand-in database connection that serves one stored resume."""

    def __init__(self, payload: dict, version: int = 3):
        self.cursor_obj = _FakeCursor(version=version)
        self.payload = payload
        original_execute = self.cursor_obj.execute

        def execute(sql: str, params: tuple = ()) -> None:
            text = " ".join(sql.split())
            if text.startswith("SELECT session_id, payload, version, user_id"):
                self.cursor_obj.statements.append((text, params))
                self.cursor_obj._row = (params[0], self.payload, version, None)
            else:
                original_execute(sql, params)

        self.cursor_obj.execute = execute

    def cursor(self):
        return self

    def commit(self) -> None:
        pass

    # The same object serves as connection and cursor context managers.
    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.cursor_obj.execute(sql, params)

    def fetchone(self):
        return self.cursor_obj.fetchone()


class _FakeOpenAI:
    """Stands in for the OpenAI client: returns a fixed tidy-up result, counts calls."""

    def __init__(self):
        self.calls = 0
        self.responses = self

    def create(self, **_kwargs):
        self.calls += 1
        reply = {
            "categories": ["backend"],
            "skills": ["Python"],
            "bullets": ["Built a thing for customers"],
        }
        return type("Reply", (), {"output_text": json.dumps(reply)})()


def test_voice_add_entry_end_to_end() -> bool:
    """The voice assistant's add-entry request, run through the real code path."""
    import enrichment
    import main

    payload = load_fixture("sample_career.json")
    connection = _FakeConnection(payload)
    fake_ai = _FakeOpenAI()
    saved_connect = main.psycopg.connect
    saved_user = main.get_current_user
    saved_client = enrichment.client
    problems = []
    try:
        main.psycopg.connect = lambda *a, **k: connection
        main.get_current_user = lambda request: None
        enrichment.client = fake_ai
        body = main.AddItemBody(
            section="experience",
            fields={"company": "NewCo", "title": "Engineer", "bullets": ["Built a thing"]},
        )
        result = main.tool_add_item("sess_1", body, request=None)
    except Exception as err:
        result = None
        problems.append(f"request failed: {type(err).__name__}: {err}")
    finally:
        main.psycopg.connect = saved_connect
        main.get_current_user = saved_user
        enrichment.client = saved_client

    if result is not None:
        stored = result["payload"]
        new_id = result.get("itemId")
        points = [p["content"] for p in points_for_item(stored, "experience", new_id)]
        if points != ["Built a thing for customers"]:
            problems.append(f"saved points={points}")
        if _copies_out_of_step(stored):
            problems.append("bullets out of step with points")
        if fake_ai.calls != 2:
            problems.append(f"tidy-up model calls={fake_ai.calls} (expected 2)")
        cur = connection.cursor_obj
        history = cur.ran("INSERT INTO career_versions")
        if len(history) != 1 or history[0][4] != "Added an entry to experience":
            problems.append("no history entry for the new entry")
        if len(cur.ran("INSERT INTO resume_undo")) != 1:
            problems.append("no undo copy kept")
    ok = not problems
    print(f"voice_add_entry_end_to_end: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


async def _asgi_post(app, path: str) -> int:
    """Send one POST request straight into an ASGI app, with no network involved."""
    messages: list[dict] = []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "client": ("test", 1),
        "server": ("test", 80),
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        messages.append(message)

    await app(scope, receive, send)
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


def test_timing_log() -> bool:
    import asyncio
    import tempfile
    import time

    from fastapi import FastAPI

    import main
    import timing

    problems = []
    if not any(m.cls is timing.TimingMiddleware for m in main.app.user_middleware):
        problems.append("timing wrapper is not installed on the server")

    app = FastAPI()

    @app.post("/resume/{session_id}/tools/add_item")
    def tool_add_item(session_id: str) -> dict:
        with timing.timed("tidy_up"):
            time.sleep(0.02)
        return {"ok": True}

    saved_path = timing.LOG_PATH
    with tempfile.TemporaryDirectory() as tmp:
        timing.LOG_PATH = Path(tmp) / "timing.jsonl"
        try:
            status = asyncio.run(
                _asgi_post(
                    timing.TimingMiddleware(app), "/resume/intake_secret123/tools/add_item"
                )
            )
            lines = timing.LOG_PATH.read_text().splitlines()
        finally:
            timing.LOG_PATH = saved_path

    if status != 200:
        problems.append(f"request status={status}")
    if len(lines) != 1:
        problems.append(f"timing lines written={len(lines)}")
    else:
        record = json.loads(lines[0])
        if "intake_secret123" in lines[0]:
            problems.append("session id written to the timing log")
        if record.get("route") != "/resume/{session_id}/tools/add_item":
            problems.append(f"route={record.get('route')}")
        if record.get("action") != "tool_add_item":
            problems.append(f"action={record.get('action')}")
        tidy = (record.get("parts") or {}).get("tidy_up") or 0
        if tidy < 15 or record.get("ms", 0) < tidy:
            problems.append(f"tidy-up time not recorded properly: {record}")
        if not record.get("bytes"):
            problems.append("reply size not recorded")
    ok = not problems
    print(f"timing_log: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def _resume_with_jobs(jobs: int, points_each: int) -> dict:
    """A realistic-size resume: `jobs` experience entries of `points_each` long points."""
    raw = load_raw_fixture("sample_career.json")
    items = [
        {
            "id": f"exp_{n}",
            "company": f"Company {n}",
            "title": "Software Engineer",
            "startDate": "2023-01",
            "endDate": "2024-01",
            "location": "Bengaluru",
            "bullets": [
                f"Built and shipped feature {n}-{k} using Python, Redis and AWS Lambda, "
                "cutting response time for the recommendations service noticeably"
                for k in range(points_each)
            ],
            "categories": ["backend"],
            "skills": ["Python", "Redis"],
            "status": "active",
        }
        for n in range(jobs)
    ]
    raw["inventory"]["sections"]["experience"]["items"] = items
    raw["resume"]["includedIds"]["experience"] = [i["id"] for i in items]
    raw["facts"] = []
    # Voice setup is in progress, with skills already confirmed.
    raw["intake"] = {
        "status": "in_progress",
        "basicsVerified": True,
        "skillsConfirmed": True,
    }
    return normalize_payload(raw)


def _voice_replies(payload: dict) -> dict[str, dict]:
    """Run the voice actions through the real server code on a stand-in database."""
    import main

    saved_connect, saved_user = main.psycopg.connect, main.get_current_user
    replies: dict[str, dict] = {}
    try:
        main.get_current_user = lambda request: None
        calls = {
            "add_item": lambda: main.tool_add_item(
                "s",
                main.AddItemBody(
                    section="experience",
                    fields={
                        "company": "NewCo",
                        "title": "Engineer",
                        "location": "Remote",
                        "startDate": "2025-01",
                        "endDate": "2025-12",
                        "bullets": ["Built it"],
                    },
                    enrich=False,
                ),
                request=None,
            ),
            "complete_intake": lambda: main.tool_complete_intake(
                "s",
                main.CompleteIntakeBody(
                    confirmedSkippedSections=["projects", "education", "achievements"]
                ),
                request=None,
            ),
            "set_skills": lambda: main.tool_set_skills(
                "s", main.SetSkillsBody(skills=["Python", "Redis"]), request=None
            ),
            "exclude_from_resume": lambda: main.tool_exclude_from_resume(
                "s", main.SectionItemBody(section="experience", itemId="exp_0"), request=None
            ),
            "include_on_resume": lambda: main.tool_include_on_resume(
                "s", main.SectionItemBody(section="experience", itemId="exp_0"), request=None
            ),
            "reorder_sections": lambda: main.tool_reorder_sections(
                "s",
                main.ReorderSectionsBody(
                    sectionOrder=["projects", "experience", "education", "achievements"]
                ),
                request=None,
            ),
            "reorder_items": lambda: main.tool_reorder_items(
                "s",
                main.ReorderItemsBody(
                    section="experience",
                    itemIds=[i["id"] for i in payload["inventory"]["sections"]["experience"]["items"]][::-1],
                ),
                request=None,
            ),
            "search_resume_context": lambda: main.tool_search_context(
                "s", main.SearchContextBody(query="Company 1 Software Engineer"), request=None
            ),
        }
        for name, call in calls.items():
            main.psycopg.connect = lambda *a, **k: _FakeConnection(json.loads(json.dumps(payload)))
            replies[name] = call()
    finally:
        main.psycopg.connect, main.get_current_user = saved_connect, saved_user
    return replies


def test_assistant_result_is_small_and_constant() -> bool:
    import assistant_result

    problems = []
    small = _voice_replies(_resume_with_jobs(2, 2))
    large = _voice_replies(_resume_with_jobs(20, 5))
    expected_tools = {
        "add_item", "set_skills", "complete_intake", "exclude_from_resume", "include_on_resume",
        "reorder_sections", "reorder_items", "search_resume_context",
    }
    if set(small) != expected_tools:
        problems.append(f"actions covered={sorted(small)}")

    sizes = {}
    for name in sorted(expected_tools):
        a, b = small[name].get("assistantResult"), large[name].get("assistantResult")
        if not a or not b:
            problems.append(f"{name}: no assistantResult")
            continue
        for label, result in (("small", a), ("large", b)):
            if result.get("ok") is not True or result.get("tool") != name:
                problems.append(f"{name} ({label}): ok/tool fields wrong")
            if len(result.get("message", "")) > assistant_result.MESSAGE_CAP:
                problems.append(f"{name} ({label}): message too long")
            if "progress" not in result or "payload" in result or "inventory" in result:
                problems.append(f"{name} ({label}): progress missing or record leaked")
        size_a, size_b = len(json.dumps(a)), len(json.dumps(b))
        full_b = len(json.dumps(large[name]))
        sizes[name] = (size_a, size_b, full_b)
        # Actions report counts, so the 20-job result may differ only by a few digits.
        # Search returns up to CANDIDATE_CAP matches, so it is bounded, not identical.
        if name != "search_resume_context" and size_b > size_a + 40:
            problems.append(f"{name}: grew {size_a} -> {size_b} characters")
        if size_b > 1800:
            problems.append(f"{name}: {size_b} characters is too large")
        if name != "search_resume_context" and size_b * 4 > full_b:
            problems.append(f"{name}: short result {size_b} is not much smaller than full reply {full_b}")

    search = large["search_resume_context"]["assistantResult"]
    if len(search.get("candidates", [])) > assistant_result.CANDIDATE_CAP:
        problems.append("search: too many candidates")
    if search.get("candidates") and not all(c.get("itemId") and c.get("section") for c in search["candidates"]):
        problems.append("search: candidates missing itemId/section")
    if not isinstance(search.get("ambiguous"), bool):
        problems.append("search: ambiguous flag missing")
    added = large["add_item"]["assistantResult"]
    if not added.get("itemId") or added.get("section") != "experience":
        problems.append("add_item: itemId/section not reported")

    failed = assistant_result.failure("add_item", "x" * 500)
    if failed.get("ok") is not False or len(failed["error"]) > assistant_result.MESSAGE_CAP:
        problems.append("failure result malformed")

    ok = not problems
    biggest = max((b for _, b, _ in sizes.values()), default=0)
    print(
        f"assistant_result_is_small_and_constant: {'PASS' if ok else 'FAIL'} "
        f"(largest short result={biggest} characters, "
        f"add_item full reply on 20 jobs={sizes.get('add_item', (0, 0, 0))[2]}, problems={problems})"
    )
    return ok


def test_single_save_door() -> bool:
    """No code outside the two shared functions may write a stored resume."""
    allowed = {
        "UPDATE resume_snapshots SET payload": {"_save_payload"},
        "INSERT INTO resume_snapshots": {"_create_snapshot"},
        "push_undo(": {"_save_payload"},
        "record_version(": {"_save_payload", "_create_snapshot"},
    }
    offenders = []
    endpoints = 0
    for path in sorted((ROOT / "api").glob("*.py")):
        source = path.read_text()
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = " ".join((ast.get_source_segment(source, node) or "").split())
            if path.name == "main.py" and "_save_payload(" in body:
                endpoints += 1
            for needle, owners in allowed.items():
                defining = needle.rstrip("(") in ("push_undo", "record_version") and (
                    node.name == needle.rstrip("(")
                )
                if needle in body and node.name not in owners and not defining:
                    offenders.append(f"{path.name}:{node.name} uses {needle!r}")
    ok = not offenders and endpoints >= 12
    print(
        f"single_save_door: {'PASS' if ok else 'FAIL'} "
        f"(functions saving through the door={endpoints}, offenders={offenders})"
    )
    return ok


def test_example_record_is_current() -> bool:
    path = ROOT / "api" / "resume-schema.example.json"
    example = json.loads(path.read_text())
    problems = []
    if example.get("schemaVersion") != 5:
        problems.append(f"schemaVersion={example.get('schemaVersion')}")
    if normalize_payload(json.loads(path.read_text())) != example:
        problems.append("normalizing it changes it; regenerate the file")
    if _copies_out_of_step(example):
        problems.append(f"bullets differ from points: {_copies_out_of_step(example)}")
    ok = not problems
    print(f"example_record_is_current: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_env_example_lists_settings() -> bool:
    read_by_code: set[str] = set()
    for path in (ROOT / "api").glob("*.py"):
        read_by_code |= set(re.findall(r'os\.getenv\(\s*"([A-Z0-9_]+)"', path.read_text()))
    listed = set(
        re.findall(
            r"^#?\s*([A-Z0-9_]+)=",
            (ROOT / "api" / ".env.example").read_text(),
            flags=re.MULTILINE,
        )
    )
    missing = sorted(read_by_code - listed)
    ok = not missing and len(read_by_code) > 0
    print(
        f"env_example_lists_settings: {'PASS' if ok else 'FAIL'} "
        f"(settings read by code={len(read_by_code)}, missing from example={missing})"
    )
    return ok


def main() -> int:
    tests = [
        test_entity_resolution,
        test_skill_delete_op,
        test_claim_verification,
        test_v5_upgrade_keeps_points,
        test_v5_upgrade_is_stable,
        test_v5_bullets_follow_points,
        test_v5_writers_keep_copies_in_step,
        test_v5_blank_record,
        test_v5_label_defaults,
        test_v5_labels_survive_reload,
        test_v5_rejects_unknown_labels,
        test_save_door,
        test_voice_add_entry_end_to_end,
        test_assistant_result_is_small_and_constant,
        test_single_save_door,
        test_example_record_is_current,
        test_env_example_lists_settings,
        test_timing_log,
    ]
    results = [t() for t in tests]
    passed = sum(results)
    print(f"\n{passed}/{len(tests)} eval cases passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
