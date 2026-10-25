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

# These evals never reach a database, a model or the internet. Placeholders are forced
# (not "set if missing"): a real key already in the shell must never be used here.
os.environ["DATABASE_URL"] = "postgresql://unused-in-evals"
os.environ["OPENAI_API_KEY"] = "unused-in-evals"


def _block_network() -> None:
    """Any accidental outside connection fails at once instead of reaching a service."""
    import socket

    def blocked(*_args, **_kwargs):
        raise OSError("the evals do not open network connections")

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked


_block_network()

from fastapi import BackgroundTasks

from context_selector import select_resume_context
from claim_verify import verify_claim
from claims import new_point, points_for_item, set_item_points
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
    """Items (and projects) whose bullets copy differs from their point records."""
    bad = []
    for section, item in _point_items(payload):
        job = [p["content"] for p in points_for_item(payload, section, item["id"])]
        if item.get("bullets") != job:
            bad.append(item["id"])
        for project in item.get("projects") or []:
            own = [
                p["content"]
                for p in points_for_item(payload, section, item["id"], project["id"])
            ]
            if project.get("bullets") != own:
                bad.append(f"{item['id']}/{project['id']}")
    return bad


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
        result = main.tool_add_item(
            "sess_1", body, request=None, background_tasks=BackgroundTasks()
        )
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
    items[0]["projects"] = [
        {"id": "wp_a", "name": "Alpha service", "bullets": ["Built the alpha service"]},
        {"id": "wp_b", "name": "Beta pipeline", "bullets": ["Built the beta pipeline"]},
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


def _voice_replies(
    payload: dict, *, enrich: bool = False, catch: bool = True
) -> dict[str, dict]:
    """
    Run the voice actions through the real server code on a stand-in database.
    enrich=True lets add_item run its AI tidy-up; catch=True (the default) records an
    action that raises as {"raised": "..."} so the checks report it instead of crashing.
    """
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
                    enrich=enrich,
                ),
                request=None,
                background_tasks=BackgroundTasks(),
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
            "add_project": lambda: main.tool_add_project(
                "s",
                main.AddProjectBody(
                    itemId="exp_0", name="Gamma tool", technologies=["Go"], bullets=["Built gamma"]
                ),
                request=None,
            ),
            "rename_project": lambda: main.tool_rename_project(
                "s",
                main.RenameProjectBody(itemId="exp_0", projectId="wp_a", name="Alpha renamed"),
                request=None,
            ),
            "archive_project": lambda: main.tool_archive_project(
                "s", main.ProjectRefBody(itemId="exp_0", projectId="wp_a"), request=None
            ),
            "reorder_projects": lambda: main.tool_reorder_projects(
                "s",
                main.ReorderProjectsBody(itemId="exp_0", projectIds=["wp_b", "wp_a"]),
                request=None,
            ),
            "search_resume_context": lambda: main.tool_search_context(
                "s", main.SearchContextBody(query="Company 1 Software Engineer"), request=None
            ),
        }
        for name, call in calls.items():
            main.psycopg.connect = lambda *a, **k: _FakeConnection(json.loads(json.dumps(payload)))
            if not catch:
                replies[name] = call()
                continue
            try:
                replies[name] = call()
            except Exception as err:  # recorded; the guard decides whether that is a problem
                replies[name] = {"raised": f"{type(err).__name__}: {err}"}
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
        "add_project", "rename_project", "archive_project", "reorder_projects",
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


# The live path may not call an AI model or any outside service, with ONE known
# exception: add_item's tidy-up (enrichment). It is removed in phase 4, when the
# tidy-up moves to the background; delete this entry then and the guard tightens.
LIVE_AI_ALLOWED = {"add_item": {"enrichment"}}

ASSISTANT_RESULT_FIELDS = {
    "ok", "tool", "message", "section", "itemId", "projectId", "progress",
    "candidates", "ambiguous", "error",
}


class _SpyClient:
    """Stands in for an OpenAI client: counts calls; only tidy-up gets a real-looking reply."""

    def __init__(self, module: str, log: list):
        self.module, self.log = module, log
        self.responses = self
        self.chat = self
        self.completions = self

    def create(self, **_kwargs):
        self.log.append(self.module)
        reply = {"categories": ["backend"], "skills": ["Python"], "bullets": ["Built it for customers"]}
        return type("Reply", (), {"output_text": json.dumps(reply)})()


def _live_run(payload: dict, *, enrich: bool) -> tuple[dict, list, list]:
    """
    Run the voice actions with every OpenAI client replaced by a spy and all network
    connections blocked. Returns (replies, AI calls as [(action, module)], network attempts).
    """
    import importlib
    import socket

    ai_calls: list[str] = []
    attempts: list[str] = []
    patched = []
    for path in sorted((ROOT / "api").glob("*.py")):
        module = importlib.import_module(path.stem)
        if hasattr(module, "client") and type(module.client).__name__ == "OpenAI":
            patched.append((module, module.client))
            module.client = _SpyClient(path.stem, ai_calls)

    def blocked(*args, **kwargs):
        attempts.append("network connection attempted")
        raise OSError("network is blocked during the live-path guard")

    saved_connect, saved_ex = socket.socket.connect, socket.socket.connect_ex
    socket.socket.connect, socket.socket.connect_ex = blocked, blocked
    try:
        replies = _voice_replies(payload, enrich=enrich, catch=True)
    finally:
        socket.socket.connect, socket.socket.connect_ex = saved_connect, saved_ex
        for module, original in patched:
            module.client = original
    return replies, ai_calls, attempts


def test_live_path_guard() -> bool:
    """Nothing the person waits on may call an AI model or an outside service."""
    import chat_tools

    problems = []
    payload = _resume_with_jobs(3, 3)

    # 1. Every action the assistant can call is covered.
    tools = {t["name"] for t in chat_tools.TOOL_DEFINITIONS} | {
        t["name"] for t in chat_tools.INTAKE_TOOL_DEFINITIONS
    }
    replies, ai_calls, attempts = _live_run(payload, enrich=False)
    uncovered = sorted(tools - set(replies))
    if uncovered:
        problems.append(f"voice tools not covered by the guard: {uncovered}")

    # 2. With the tidy-up off, no action calls any AI model or opens any connection.
    if ai_calls:
        problems.append(f"AI calls on the live path: {ai_calls}")
    if attempts:
        problems.append(f"{len(attempts)} network attempts on the live path")
    for name, reply in replies.items():
        if "raised" in reply:
            problems.append(f"{name} raised: {reply['raised']}")

    # 3. The one allowed exception is exactly that, and nothing more.
    _replies, tidy_calls, tidy_attempts = _live_run(payload, enrich=True)
    modules = set(tidy_calls)
    if modules != LIVE_AI_ALLOWED["add_item"]:
        problems.append(f"add_item with tidy-up called {sorted(modules)}, allowed {sorted(LIVE_AI_ALLOWED['add_item'])}")
    if len(tidy_calls) != 2:
        problems.append(f"tidy-up made {len(tidy_calls)} calls (expected 2)")
    if tidy_attempts:
        problems.append("network attempts during the tidy-up")

    # 4. Each short result keeps to the contract and never carries the record.
    for name, reply in replies.items():
        result = reply.get("assistantResult")
        if not isinstance(result, dict):
            problems.append(f"{name}: no assistantResult")
            continue
        extra = set(result) - ASSISTANT_RESULT_FIELDS
        if extra:
            problems.append(f"{name}: unexpected fields {sorted(extra)}")
        if len(json.dumps(result)) > 1800:
            problems.append(f"{name}: short result is {len(json.dumps(result))} characters")

    # 5. The browser sends the model only the short result.
    ts = (ROOT / "web" / "src" / "voice" / "handleRealtimeTools.ts").read_text()
    if ts.count("function_call_output") != 1:
        problems.append("browser sends tool results to the model in more than one place")
    if "const outputText = JSON.stringify(resultForAssistant(output))" not in ts:
        problems.append("browser no longer builds the model's tool result with resultForAssistant")
    if "output: outputText" not in ts:
        problems.append("browser sends something other than outputText to the model")

    ok = not problems
    print(
        f"live_path_guard: {'PASS' if ok else 'FAIL'} "
        f"(actions covered={len(replies)}/{len(tools)}, AI calls with tidy-up off={len(ai_calls)}, "
        f"network attempts={len(attempts)}, tidy-up calls={len(tidy_calls)}, problems={problems})"
    )
    return ok


def test_projects_upgrade_changes_nothing() -> bool:
    """Existing records gain empty projects and keep every point, id and copy."""
    import hashlib

    raw = load_raw_fixture("sample_career.json")
    payload = normalize_payload(raw)
    problems = []
    checked = 0
    for section, item in _point_items(payload):
        if section == "experience":
            if item.get("projects") != []:
                problems.append(f"{item['id']}: projects={item.get('projects')}")
        elif "projects" in item:
            problems.append(f"{item['id']}: an independent project gained a projects list")
        before = next(
            i for i in raw["inventory"]["sections"][section]["items"] if i["id"] == item["id"]
        )["bullets"]
        if item["bullets"] != before:
            problems.append(f"{item['id']}: bullets changed")
        for occurrence, text in enumerate(before):
            # The id formula as it was before projects existed.
            expected = "pt_" + hashlib.sha1(
                f"{section}|{item['id']}|{occurrence}|{text}".encode()
            ).hexdigest()[:10]
            point = next(
                (p for p in points_for_item(payload, section, item["id"]) if p["content"] == text),
                None,
            )
            checked += 1
            if not point or point["id"] != expected or point.get("projectId") is not None:
                problems.append(f"{item['id']}: point id or projectId changed for {text!r}")
    if normalize_payload(json.loads(json.dumps(payload))) != payload:
        problems.append("second upgrade changed the record")
    ok = not problems and checked > 0
    print(
        f"projects_upgrade_changes_nothing: {'PASS' if ok else 'FAIL'} "
        f"(points checked={checked}, problems={problems})"
    )
    return ok


def _with_project(payload: dict) -> dict:
    """The sample resume with one project inside the ChaiShots job, normalized."""
    payload = json.loads(json.dumps(payload))
    job = next(
        i for i in payload["inventory"]["sections"]["experience"]["items"] if i["id"] == "exp_chaishots"
    )
    job["projects"] = [{"id": "wp_rec", "name": "Recommendation engine"}]
    return normalize_payload(payload)


def test_project_points_stay_separate() -> bool:
    payload = _with_project(load_fixture("sample_career.json"))
    problems = []
    job_points = [p["content"] for p in points_for_item(payload, "experience", "exp_chaishots")]
    job_ids = {p["id"] for p in points_for_item(payload, "experience", "exp_chaishots")}

    payload = set_item_points(
        payload, "experience", "exp_chaishots",
        ["Added Redis caching", "Built personalization pipeline"],
        project_id="wp_rec",
    )
    project = next(
        pr for i in payload["inventory"]["sections"]["experience"]["items"]
        if i["id"] == "exp_chaishots" for pr in i["projects"]
    )
    job = next(i for i in payload["inventory"]["sections"]["experience"]["items"] if i["id"] == "exp_chaishots")
    if project["bullets"] != ["Added Redis caching", "Built personalization pipeline"]:
        problems.append(f"project bullets={project['bullets']}")
    if job["bullets"] != job_points:
        problems.append(f"job bullets changed: {job['bullets']}")
    if {p["id"] for p in points_for_item(payload, "experience", "exp_chaishots")} != job_ids:
        problems.append("setting project points changed the job's points")
    if payload["inventory"]["sections"]["projects"]["items"] != load_fixture("sample_career.json")["inventory"]["sections"]["projects"]["items"]:
        problems.append("independent Projects section changed")

    # The same sentence at both levels is two different points.
    same_job = next(p for p in points_for_item(payload, "experience", "exp_chaishots"))
    same_project = next(
        p for p in points_for_item(payload, "experience", "exp_chaishots", "wp_rec")
        if p["content"] == "Built personalization pipeline"
    )
    if same_job["content"] == same_project["content"] and same_job["id"] == same_project["id"]:
        problems.append("job-level and project-level point share an id")

    # Labels survive changes at either level, and changes at one level never touch the other.
    marked = next(p for p in payload["claims"] if p["id"] == same_project["id"])
    marked.update({"status": "supported", "supportedBy": ["fact_lambda"]})
    marked_id = marked["id"]
    payload = set_item_points(
        payload, "experience", "exp_chaishots",
        ["Added Redis caching", "Built personalization pipeline", "Cut latency"],
        project_id="wp_rec",
    )
    kept = next(p for p in payload["claims"] if p["id"] == marked_id)
    if (kept["status"], kept["supportedBy"]) != ("supported", ["fact_lambda"]):
        problems.append("project point lost its labels when another was added")
    payload = set_item_points(payload, "experience", "exp_chaishots", ["Mentored two interns"])
    after_job = next(
        pr for i in payload["inventory"]["sections"]["experience"]["items"]
        if i["id"] == "exp_chaishots" for pr in i["projects"]
    )
    if len(after_job["bullets"]) != 3:
        problems.append("changing the job's points changed the project's")
    if _copies_out_of_step(payload):
        problems.append(f"bullets copies out of step: {_copies_out_of_step(payload)}")
    # A reload may reorder the claims list (the upgrade writes it in item order) but must
    # keep every claim exactly, and one more pass must change nothing.
    reloaded = normalize_payload(json.loads(json.dumps(payload)))
    by_id = lambda record: sorted(record["claims"], key=lambda c: c["id"])
    if by_id(reloaded) != by_id(payload):
        problems.append("a reload changed or lost a claim")
    if {k: v for k, v in reloaded.items() if k != "claims"} != {
        k: v for k, v in payload.items() if k != "claims"
    }:
        problems.append("a reload changed something other than the claims order")
    if normalize_payload(json.loads(json.dumps(reloaded))) != reloaded:
        problems.append("repeating the upgrade changed the record")

    for label, call in {
        "unknown project": lambda: set_item_points(payload, "experience", "exp_chaishots", ["x"], project_id="nope"),
        "project on an independent project": lambda: set_item_points(payload, "projects", "proj_x", ["x"], project_id="wp_rec"),
    }.items():
        try:
            call()
            problems.append(f"{label} was accepted")
        except KeyError:
            pass

    # Facts remember the project they belong to and are not merged across levels.
    with_facts = add_fact(payload, "Used Redis", section="experience", item_id="exp_chaishots")
    with_facts = add_fact(
        with_facts, "Used Redis", section="experience", item_id="exp_chaishots", project_id="wp_rec"
    )
    redis = [f for f in with_facts["facts"] if f["content"] == "Used Redis"]
    if sorted(str(f["context"].get("projectId")) for f in redis) != ["None", "wp_rec"]:
        problems.append(f"fact contexts={[f['context'] for f in redis]}")

    ok = not problems
    print(f"project_points_stay_separate: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_projects_tolerate_bad_data() -> bool:
    raw = _with_project(load_fixture("sample_career.json"))
    job = next(i for i in raw["inventory"]["sections"]["experience"]["items"] if i["id"] == "exp_chaishots")
    job["projects"] = [
        "not an object",
        {"id": "wp_rec", "name": "Recommendation engine"},
        {"id": "wp_rec", "name": "Same id again"},
        {"name": "No id", "technologies": "not a list"},
        {"name": "No id"},
    ]
    orphan = new_point("experience", "exp_chaishots", "Point of a deleted project", 0, project_id="wp_gone")
    raw["claims"].append(orphan)
    total_before = len([c for c in raw["claims"] if c.get("itemId")])

    first = normalize_payload(json.loads(json.dumps(raw)))
    second = normalize_payload(json.loads(json.dumps(raw)))
    problems = []
    if first != second:
        problems.append("the same bad record normalized differently twice")
    if normalize_payload(json.loads(json.dumps(first))) != first:
        problems.append("a second upgrade changed the result")
    projects = next(
        i for i in first["inventory"]["sections"]["experience"]["items"] if i["id"] == "exp_chaishots"
    )["projects"]
    ids = [pr["id"] for pr in projects]
    if len(projects) != 4:
        problems.append(f"expected 4 projects (the non-object dropped), got {len(projects)}")
    if len(set(ids)) != len(ids):
        problems.append(f"project ids not unique: {ids}")
    if not all(isinstance(pr["technologies"], list) and pr.get("story") is not None and pr.get("writing") for pr in projects):
        problems.append("a project is missing technologies, story or writing")
    moved = [p for p in first["claims"] if p["content"] == "Point of a deleted project"]
    if len(moved) != 1 or moved[0].get("projectId") is not None or moved[0]["id"] != orphan["id"]:
        problems.append(f"orphan point not kept at job level: {moved}")
    if len([c for c in first["claims"] if c.get("itemId")]) != total_before:
        problems.append("a point was lost or duplicated")
    if _copies_out_of_step(first):
        problems.append(f"bullets copies out of step: {_copies_out_of_step(first)}")
    ok = not problems
    print(f"projects_tolerate_bad_data: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def _raises(call, kind) -> bool:
    try:
        call()
    except kind:
        return True
    except Exception:
        return False
    return False


def test_project_operations() -> bool:
    import work_projects as wp

    problems = []
    base = load_fixture("sample_career.json")
    job = ("experience", "exp_chaishots")

    # Adding: name rules, technologies cleaned, first points, facts, story and writing.
    payload, pid = wp.add_project(
        base, *job, "  Recommendation   engine ",
        technologies=["Redis", "redis", "", "Python"], bullets=["Added Redis caching", "  "],
    )
    project = wp.get_project(payload, *job, pid)
    if project["name"] != "Recommendation engine":
        problems.append(f"name not tidied: {project['name']!r}")
    if project["technologies"] != ["Redis", "Python"]:
        problems.append(f"technologies={project['technologies']}")
    if project["bullets"] != ["Added Redis caching"] or project["status"] != "active":
        problems.append(f"bullets/status wrong: {project}")
    if not project["story"] or project["writing"]["status"] != "idle":
        problems.append("new project has no story or writing marker")
    if [c["content"] for c in points_for_item(payload, *job, pid)] != ["Added Redis caching"]:
        problems.append("project points not created")
    if [c["content"] for c in points_for_item(payload, *job)] != [
        c["content"] for c in points_for_item(base, *job)
    ]:
        problems.append("adding a project changed the job's own points")

    rejected = {
        "empty name": lambda: wp.add_project(base, *job, "   "),
        "name too long": lambda: wp.add_project(base, *job, "x" * 121),
        "duplicate name, different capitals": lambda: wp.add_project(
            payload, *job, "RECOMMENDATION ENGINE"
        ),
    }
    for label, call in rejected.items():
        if not _raises(call, ValueError):
            problems.append(f"{label} was accepted")
    for label, call, kind in (
        ("unknown job", lambda: wp.add_project(base, "experience", "exp_nope", "X"), KeyError),
        ("independent Projects section", lambda: wp.add_project(base, "projects", "p", "X"), ValueError),
        ("education section", lambda: wp.add_project(base, "education", "e", "X"), ValueError),
        ("unknown project", lambda: wp.rename_project(payload, *job, "wp_nope", "Y"), KeyError),
    ):
        if not _raises(call, kind):
            problems.append(f"{label} was not refused")
    unverified = json.loads(json.dumps(base))
    unverified["intake"]["basicsVerified"] = False
    unverified["intake"]["basicsConfirmed"] = False
    if not _raises(lambda: wp.add_project(unverified, *job, "X"), ValueError):
        problems.append("a project was added before details were confirmed")

    # Renaming: same-name rule, but renaming to its own name is fine.
    payload, second = wp.add_project(payload, *job, "Event pipeline")
    if not _raises(lambda: wp.rename_project(payload, *job, second, "recommendation engine"), ValueError):
        problems.append("renamed onto another project's name")
    payload = wp.rename_project(payload, *job, second, "Event workflows")
    payload = wp.rename_project(payload, *job, second, "Event workflows")
    if wp.get_project(payload, *job, second)["name"] != "Event workflows":
        problems.append("rename did not apply")

    # Reordering: every active project exactly once.
    for label, ids in (("missing one", [second]), ("unknown id", [second, pid, "wp_nope"]), ("empty", [])):
        if not _raises(lambda ids=ids: wp.reorder_projects(payload, *job, ids), (ValueError, KeyError)):
            problems.append(f"reorder with {label} was accepted")
    payload = wp.reorder_projects(payload, *job, [second, pid, second])
    names = [x["name"] for x in payload["inventory"]["sections"]["experience"]["items"][0]["projects"]]
    if names != ["Event workflows", "Recommendation engine"]:
        problems.append(f"order after reorder={names}")

    # Archiving keeps the points, frees the name, and is refused twice.
    payload = wp.archive_project(payload, *job, pid)
    if not _raises(lambda: wp.archive_project(payload, *job, pid), ValueError):
        problems.append("archived the same project twice")
    if [c["content"] for c in points_for_item(payload, *job, pid)] != ["Added Redis caching"]:
        problems.append("archiving lost the project's points")
    payload, reused = wp.add_project(payload, *job, "Recommendation engine")
    payload = wp.reorder_projects(payload, *job, [reused, second])
    ordered = [
        (x["name"], x["status"])
        for x in payload["inventory"]["sections"]["experience"]["items"][0]["projects"]
    ]
    if ordered != [("Recommendation engine", "active"), ("Event workflows", "active"),
                   ("Recommendation engine", "archived")]:
        problems.append(f"archived project not kept after the active ones: {ordered}")

    # Whatever the sequence, the record is tidy and the copies match.
    if _copies_out_of_step(payload):
        problems.append(f"bullets copies out of step: {_copies_out_of_step(payload)}")
    again = normalize_payload(json.loads(json.dumps(payload)))
    if normalize_payload(json.loads(json.dumps(again))) != again:
        problems.append("repeating the upgrade changed the record")
    if normalize_payload(json.loads(json.dumps(payload)))["inventory"] != payload["inventory"]:
        problems.append("the upgrade changed the inventory the operations produced")

    ok = not problems
    print(f"project_operations: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_project_search_and_facts() -> bool:
    import assistant_result
    import work_projects as wp
    from context_selector import select_resume_context
    from facts import sync_facts_from_item

    problems = []
    base = load_fixture("sample_career.json")
    job = ("experience", "exp_chaishots")
    payload, pid = wp.add_project(
        base, *job, "Quasar ledger", technologies=["Zig"], bullets=["Reconciled the quasar accounts"]
    )

    # A phrase only the project contains finds the job, and the project is listed.
    context = select_resume_context(payload, "quasar ledger")
    top = context["candidates"][0] if context["candidates"] else {}
    if top.get("id") != "exp_chaishots" or [p["id"] for p in top.get("projects", [])] != [pid]:
        problems.append(f"search did not surface the project: {top.get('id')}, {top.get('projects')}")
    short_candidates = assistant_result.from_search(payload, context)["candidates"]
    short = short_candidates[0] if short_candidates else {}
    if short.get("projects") != [{"projectId": pid, "name": "Quasar ledger"}]:
        problems.append(f"short search result projects={short.get('projects')}")

    # Archived projects stop matching and stop being listed.
    archived = wp.archive_project(payload, *job, pid)
    after = select_resume_context(archived, "quasar ledger zig")["candidates"]
    if any(c.get("projects") for c in after):
        problems.append("an archived project is still listed")
    if select_resume_context(archived, "quasar")["candidates"] and any(
        c["id"] == "exp_chaishots" and c.get("score", 0) > 1
        for c in select_resume_context(archived, "quasar")["candidates"]
    ):
        problems.append("an archived project still adds to the job's match score")

    # The listing is capped however many projects there are.
    many = payload
    for n in range(8):
        many, _ = wp.add_project(many, *job, f"Extra {n}")
    capped = assistant_result.from_search(many, select_resume_context(many, "chaishots extra"))["candidates"]
    listed = max((len(c.get("projects", [])) for c in capped), default=0)
    if listed > assistant_result.PROJECT_CAP:
        problems.append(f"{listed} projects listed for one match")

    # Facts from a project's points carry the project; the job's facts are separate.
    jobs = get_item_for_test(payload, *job)
    project = wp.get_project(payload, *job, pid)
    with_facts = sync_facts_from_item(payload, "experience", jobs, project=project)
    mine = [f for f in with_facts["facts"] if (f["context"].get("projectId") or None) == pid]
    if sorted(f["content"] for f in mine) != ["Reconciled the quasar accounts", "Used Zig"]:
        problems.append(f"project facts={[f['content'] for f in mine]}")
    if any(f["kind"] != "tool" for f in mine if f["content"] == "Used Zig"):
        problems.append("a project technology fact is not marked as a tool")

    # Typed chat and voice share the same tools.
    import chat_tools
    new_payload, summary = chat_tools.execute_tool(
        base, "add_project", {"itemId": "exp_chaishots", "name": "Chat project", "bullets": ["Did a thing"]}
    )
    if not summary.get("projectId") or not any(
        f["context"].get("projectId") == summary["projectId"] for f in new_payload["facts"]
    ):
        problems.append("add_project through typed chat did not create the project and its facts")
    setup = {t["name"] for t in chat_tools.INTAKE_TOOL_DEFINITIONS}
    edit = {t["name"] for t in chat_tools.TOOL_DEFINITIONS}
    if "add_project" not in setup or {"rename_project", "archive_project", "reorder_projects"} & setup:
        problems.append(f"setup tools wrong: {sorted(setup)}")
    if not {"add_project", "rename_project", "archive_project", "reorder_projects"} <= edit:
        problems.append(f"edit tools wrong: {sorted(edit)}")

    ok = not problems
    print(f"project_search_and_facts: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def get_item_for_test(payload: dict, section: str, item_id: str) -> dict:
    return next(i for i in payload["inventory"]["sections"][section]["items"] if i["id"] == item_id)


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

    def reject_duplicate_keys(pairs):
        keys = [key for key, _ in pairs]
        repeated = sorted({key for key in keys if keys.count(key) > 1})
        if repeated:
            raise ValueError(f"duplicate keys {repeated}")
        return dict(pairs)

    problems = []
    try:
        # A repeated key would be silently resolved to its last value by json.loads.
        example = json.loads(path.read_text(), object_pairs_hook=reject_duplicate_keys)
    except ValueError as err:
        print(f"example_record_is_current: FAIL (problems=['{err}'])")
        return False
    if example.get("schemaVersion") != 5:
        problems.append(f"schemaVersion={example.get('schemaVersion')}")
    # The example should show a project inside a job, with a point owned by that project.
    projects = [
        (item["id"], project)
        for item in example["inventory"]["sections"]["experience"]["items"]
        for project in item.get("projects") or []
    ]
    if not projects:
        problems.append("the example has no project inside a job")
    for item_id, project in projects:
        owned = [
            c for c in example["claims"]
            if c.get("itemId") == item_id and c.get("projectId") == project["id"]
        ]
        if not owned or [c["content"] for c in owned] != project.get("bullets"):
            problems.append(f"project {project['id']}: its points are not recorded as its own")
    if normalize_payload(json.loads(path.read_text())) != example:
        problems.append("normalizing it changes it; regenerate the file")
    if _copies_out_of_step(example):
        problems.append(f"bullets differ from points: {_copies_out_of_step(example)}")
    # The example shows stored contact checks and a project link check. Each result must
    # still match the value it checked, or the example has gone stale.
    from contact import project_links, status as contact_status

    basics = example["inventory"]["basics"]
    if not basics.get("contactChecks"):
        problems.append("the example shows no contact checks")
    if contact_status.prune_stale(basics) != basics:
        problems.append("a contact check in the example no longer matches its field")
    if contact_status.gate(basics)["blocked"]:
        problems.append(f"the example's own details fail the gate: {contact_status.gate(basics)}")
    linked = [
        item for item in example["inventory"]["sections"]["projects"]["items"]
        if item.get("linkCheck")
    ]
    if not linked:
        problems.append("the example shows no project link check")
    for item in linked:
        if project_links.refresh_item(item) != item:
            problems.append(f"project {item['id']}: its link check no longer matches its link")
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


def test_contact_shape_rules() -> bool:
    from contact.shape import (
        check_email,
        check_github,
        check_linkedin,
        check_phone,
        check_web_url,
        normalize_github_url,
        normalize_linkedin_url,
    )

    def status(check, value, *args) -> str:
        return check(value, *args)["status"]

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    for good in ("a@b.co", "  Parth.Rana+cv@Example.COM "):
        expect(f"email {good!r}", status(check_email, good), "ok")
    for bad in ("no-at-sign", "a@b", "a b@c.com", "a@@b.com", "a@b..com", "@b.com"):
        expect(f"email {bad!r}", status(check_email, bad), "broken")
    expect("email empty", status(check_email, "  "), "empty")
    typo = check_email("sam@gmial.com")
    expect("email typo stays ok", typo["status"], "ok")
    expect("email typo suggestion", typo["suggestion"], "sam@gmail.com")
    expect("email no false suggestion", check_email("sam@gmail.com")["suggestion"], "")

    for good in ("parth", "@parth-rana", "https://github.com/parth/repo", "a1"):
        expect(f"github {good!r}", status(check_github, good), "ok")
    for bad in ("-parth", "parth-", "pa--rth", "pa rth", "a" * 40, "git hub!"):
        expect(f"github {bad!r}", status(check_github, bad), "broken")
    expect(
        "github normalised",
        normalize_github_url("github.com/parth/repo"),
        "https://github.com/parth",
    )

    for good in ("linkedin.com/in/parth-rana", "in/parth", "https://www.linkedin.com/in/x"):
        expect(f"linkedin {good!r}", status(check_linkedin, good), "ok")
    for bad in ("https://evil.com/in/parth", "https://linkedin.com.evil.com/in/x",
                "https://www.linkedin.com/"):
        expect(f"linkedin {bad!r}", status(check_linkedin, bad), "broken")
    expect(
        "linkedin normalised",
        normalize_linkedin_url("@parth"),
        "https://www.linkedin.com/in/parth",
    )

    for good in ("example.com", "https://me.dev/portfolio?x=1", "http://sub.site.io:8080/a"):
        expect(f"url {good!r}", status(check_web_url, good), "ok")
    for bad in ("localhost", "ftp://example.com", "javascript:alert(1)",
                "http://exa mple.com", "https://", "nodots", "http://a.b.c:99999"):
        expect(f"url {bad!r}", status(check_web_url, bad), "broken")

    expect("phone valid +44", status(check_phone, "+44 20 7946 0958"), "ok")
    expect("phone E164", check_phone("+44 20 7946 0958")["value"], "+442079460958")
    expect("phone too short", status(check_phone, "+1 555 0100"), "broken")
    expect("phone letters", status(check_phone, "+44 abc"), "broken")
    expect("phone needs country", status(check_phone, "07700 900123"), "ok")
    expect(
        "phone with default region",
        check_phone("020 7946 0958", "GB")["value"],
        "+442079460958",
    )
    expect("phone empty", status(check_phone, ""), "empty")

    ok = not problems
    print(
        f"contact_shape_rules: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_safe_fetch_refuses_dangerous_links() -> bool:
    from contact import safe_fetch

    names = {
        "example.com": ["93.184.216.34"],
        "mixed.example": ["93.184.216.34", "10.0.0.5"],
        "sneaky.example": ["127.0.0.1"],
        "mapped.example": ["::ffff:127.0.0.1"],
        "redirector.example": ["93.184.216.35"],
    }
    opened: list[str] = []

    def fake_resolve(host: str) -> list[str]:
        if host not in names:
            raise safe_fetch.FetchFailed("the address could not be found")
        return names[host]

    def fake_request(scheme, host, ip, port, path, method, timeout):
        opened.append(f"{host}@{ip}")
        if host == "redirector.example":
            return 302, {"location": "http://169.254.169.254/latest/meta-data"}, b""
        return 200, {}, b"ok"

    real_resolve, real_request = safe_fetch._resolve, safe_fetch._request
    safe_fetch._resolve, safe_fetch._request = fake_resolve, fake_request
    problems: list[str] = []
    try:
        dangerous = [
            "http://localhost",
            "http://localhost:8081/admin",
            "http://127.0.0.1",
            "http://127.1",
            "http://2130706433",
            "http://0x7f.0.0.1",
            "http://0.0.0.0",
            "http://10.0.0.1",
            "http://172.16.5.5",
            "http://192.168.1.5",
            "http://169.254.169.254/latest/meta-data",
            "http://[::1]",
            "http://[::ffff:127.0.0.1]",
            "http://[fe80::1]",
            "http://printer.local",
            "http://sneaky.example",
            "http://mapped.example",
            "http://mixed.example",
            "file:///etc/passwd",
            "ftp://example.com",
            "gopher://example.com",
            "javascript:alert(1)",
            "http://user:pass@example.com",
            "http://example.com:22",
            "http://example.com:8081",
            "https://",
            "",
        ]
        for link in dangerous:
            try:
                safe_fetch.fetch(link)
                problems.append(f"not refused: {link!r}")
            except safe_fetch.Refused:
                pass
            except Exception as exc:
                problems.append(f"{link!r} failed another way: {exc!r}")
        if opened:
            problems.append(f"connection attempted for refused links: {opened}")

        good = safe_fetch.fetch("https://example.com/me")
        if good["status"] != 200 or opened != ["example.com@93.184.216.34"]:
            problems.append(f"public link not opened at the checked address: {opened}")

        del opened[:]
        try:
            safe_fetch.fetch("http://redirector.example/start")
            problems.append("redirect to a private address was followed")
        except safe_fetch.Refused:
            pass
        if opened != ["redirector.example@93.184.216.35"]:
            problems.append(f"redirect hop opened something else: {opened}")
    finally:
        safe_fetch._resolve, safe_fetch._request = real_resolve, real_request

    ok = not problems
    print(
        f"safe_fetch_refuses_dangerous_links: {'PASS' if ok else 'FAIL'} "
        f"(links tried={len(dangerous)}, problems={problems})"
    )
    return ok


def test_contact_exists_lookups() -> bool:
    """Rung 2 answers, replayed from recorded responses (no internet)."""
    import json as _json

    import dns.exception
    import dns.resolver

    from contact import github, reach, safe_fetch

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    # --- email provider (recorded DNS answers) ---
    dns_answers = {
        ("ok.example", "MX"): ["10 mail.ok.example."],
        ("nomx.example", "MX"): dns.resolver.NoAnswer(),
        ("nomx.example", "A"): ["93.184.216.34"],
        ("nullmx.example", "MX"): ["0 ."],
        ("nomail.example", "MX"): dns.resolver.NoAnswer(),
        ("nomail.example", "A"): dns.resolver.NoAnswer(),
        ("gone.example", "MX"): dns.resolver.NXDOMAIN(),
        ("slow.example", "MX"): dns.exception.Timeout(),
    }

    def fake_dns(domain, record_type):
        answer = dns_answers[(domain, record_type)]
        if isinstance(answer, Exception):
            raise answer
        return answer

    real_dns = reach._dns_query
    reach._dns_query = fake_dns
    try:
        for email, want in (
            ("a@ok.example", "exists"),
            ("a@nomx.example", "exists"),
            ("a@nullmx.example", "not_found"),
            ("a@nomail.example", "not_found"),
            ("a@gone.example", "not_found"),
            ("a@slow.example", "unavailable"),
            ("not-an-email", "not_found"),
        ):
            expect(f"email {email}", reach.check_email_domain(email)["status"], want)
    finally:
        reach._dns_query = real_dns

    # --- web pages and GitHub (recorded HTTP answers) ---
    calls: list[tuple[str, str]] = []
    recorded: dict[tuple[str, str], object] = {}

    def reply(status, body=b"", headers=None):
        return {"status": status, "url": "", "headers": headers or {}, "body": body}

    def fake_fetch(url, *, method="HEAD", timeout=5):
        calls.append((method, url))
        answer = recorded[(method, url)]
        if isinstance(answer, Exception):
            raise answer
        return answer

    real_fetch = safe_fetch.fetch
    safe_fetch.fetch = fake_fetch
    try:
        recorded.update({
            ("HEAD", "https://up.example/"): reply(200),
            ("HEAD", "https://picky.example/"): reply(405),
            ("GET", "https://picky.example/"): reply(200),
            ("HEAD", "https://missing.example/"): reply(404),
            ("HEAD", "https://broken.example/"): reply(500),
            ("HEAD", "https://slow.example/"): safe_fetch.FetchFailed("slow"),
            ("HEAD", "https://nxdomain.example/"): safe_fetch.NameNotFound("none"),
            ("HEAD", "http://127.0.0.1/"): safe_fetch.Refused("private"),
        })
        for url, want in (
            ("https://up.example/", "exists"),
            ("https://picky.example/", "exists"),
            ("https://missing.example/", "not_found"),
            ("https://broken.example/", "unavailable"),
            ("https://slow.example/", "unavailable"),
            ("https://nxdomain.example/", "not_found"),
            ("http://127.0.0.1/", "not_found"),
        ):
            expect(f"page {url}", reach.check_page(url)["status"], want)

        api = "https://api.github.com"
        limited = {"x-ratelimit-remaining": "0"}
        recorded.update({
            ("GET", f"{api}/users/octocat"): reply(200, _json.dumps({"login": "octocat"}).encode()),
            ("GET", f"{api}/users/ghost-user-xyz"): reply(404),
            ("GET", f"{api}/users/busy"): reply(403, headers=limited),
            ("GET", f"{api}/users/flaky"): safe_fetch.FetchFailed("slow"),
            ("GET", f"{api}/repos/octocat/hello"): reply(200, _json.dumps({"private": False}).encode()),
            ("GET", f"{api}/repos/octocat/hello/languages"): reply(
                200, _json.dumps({"Python": 100, "TypeScript": 900, "CSS": 5}).encode()
            ),
            ("GET", f"{api}/repos/octocat/secret"): reply(404),
            ("GET", f"{api}/repos/octocat/limited"): reply(429),
        })
        user = github.lookup_user("octocat")
        expect("github user exists", (user["status"], user["login"]), ("exists", "octocat"))
        expect("github user missing", github.lookup_user("ghost-user-xyz")["status"], "not_found")
        expect("github rate limited", github.lookup_user("busy")["status"], "unavailable")
        expect("github down", github.lookup_user("flaky")["status"], "unavailable")
        before = len(calls)
        expect("bad name never sent", github.lookup_user("../etc")["status"], "not_found")
        expect("bad name made no call", len(calls), before)

        repo = github.lookup_repo("https://github.com/octocat/hello.git")
        expect("repo exists", repo["status"], "exists")
        expect("repo languages by size", repo.get("languages"), ["TypeScript", "Python", "CSS"])
        secret = github.lookup_repo("https://github.com/octocat/secret")
        expect("private repo not found", secret["status"], "not_found")
        expect("private repo no languages", "languages" in secret, False)
        expect("private repo wording", "private" in secret["message"], True)
        expect("repo rate limited", github.lookup_repo("github.com/octocat/limited")["status"], "unavailable")
        expect("non-repo link", github.lookup_repo("https://example.com/a/b")["status"], "not_found")
        expect("user-only link", github.lookup_repo("https://github.com/octocat")["status"], "not_found")
        expect("parse trailing path", github.parse_repo_link("https://github.com/o/r/tree/main"), ("o", "r"))
        outside = [url for _m, url in calls if not url.startswith(api) and "example" not in url and "127.0.0.1" not in url]
        expect("only expected hosts called", outside, [])
    finally:
        safe_fetch.fetch = real_fetch

    ok = not problems
    print(
        f"contact_exists_lookups: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_contact_status_and_gate() -> bool:
    from datetime import datetime, timezone

    from contact import shape, status
    from payload_normalize import normalize_payload

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    basics = {
        "fullName": "Sam",
        "email": "sam@example.com",
        "phone": "",
        "location": "",
        "links": [{"label": "GitHub", "url": "https://github.com/sam"}],
    }
    when = datetime(2026, 10, 25, tzinfo=timezone.utc)

    expect("never checked", status.field_view(basics, "github")["level"], "unchecked")
    expect("empty field", status.field_view(basics, "phone")["level"], "empty")

    checked = status.record_check(
        basics,
        "github",
        shape.check_github("https://github.com/sam"),
        {"status": "exists", "message": "This GitHub account exists."},
        now=when,
    )
    expect("exists after check", status.field_view(checked, "github")["level"], "exists")
    expect("input not changed", "contactChecks" in basics, False)
    expect("time recorded", checked["contactChecks"]["github"]["checkedAt"], when.isoformat())

    # Editing the value drops the badge; leaving it alone keeps it.
    edited = {**checked, "links": [{"label": "GitHub", "url": "https://github.com/sam2"}]}
    expect("edit resets badge", status.field_view(edited, "github")["level"], "unchecked")
    expect("edit pruned", "github" in status.prune_stale(edited).get("contactChecks", {}), False)
    expect("unchanged kept", status.prune_stale(checked), checked)
    other_field = {**checked, "email": "new@example.com"}
    expect("other field edit keeps github", status.field_view(other_field, "github")["level"], "exists")

    # Warnings versus looks-right.
    for reach_status, want in (
        ("not_found", "warning"),
        ("unavailable", "warning"),
        (None, "looks_right"),
    ):
        reach = {"status": reach_status, "message": "m"} if reach_status else None
        state = status.record_check(basics, "github", shape.check_github("sam"), reach, now=when)
        expect(f"view for {reach_status}", status.field_view(state, "github")["level"], want)
    broken_state = status.record_check(basics, "email", {"status": "broken", "message": "bad"}, now=when)
    expect("broken view", status.field_view(broken_state, "email")["level"], "broken")

    # Bad stored data never crashes.
    for junk in ("text", 5, ["x"], {"github": "oops"}, {"nonsense": {}}):
        try:
            status.field_view({**basics, "contactChecks": junk}, "github")
            status.prune_stale({**basics, "contactChecks": junk})
        except Exception as exc:
            problems.append(f"junk {junk!r} crashed: {exc!r}")

    # The gate: only plainly broken filled-in fields block.
    expect("clean basics pass", status.gate(basics)["blocked"], False)
    expect("empty basics pass", status.gate({})["blocked"], False)
    bad_email = status.gate({**basics, "email": "no-at-sign"})
    expect("broken email blocks", (bad_email["blocked"], bad_email["blockers"][0]["field"]), (True, "email"))
    bad_link = status.gate({**basics, "links": [{"label": "GitHub", "url": "https://github.com/-bad-"}]})
    expect("broken github blocks", bad_link["blocked"], True)
    # A missing account is a warning, never a block, whatever was stored.
    missing = status.record_check(
        basics, "github", shape.check_github("sam"),
        {"status": "not_found", "message": "No account."}, now=when,
    )
    expect("not found does not block", status.gate(missing)["blocked"], False)
    expect("unavailable does not block", status.gate(
        status.record_check(basics, "github", shape.check_github("sam"),
                            {"status": "unavailable", "message": "later"}, now=when)
    )["blocked"], False)
    expect("typo suggestion does not block", status.gate({**basics, "email": "sam@gmial.com"})["blocked"], False)
    expect("phone without country does not block", status.gate({**basics, "phone": "07700 900123"})["blocked"], False)

    # Old and new saved resumes keep or lack the section harmlessly.
    saved = normalize_payload(
        {"schemaVersion": 5, "inventory": {"sections": {}, "basics": checked}}
    )
    expect(
        "checks survive upgrade",
        (saved["inventory"]["basics"].get("contactChecks") or {}).get("github", {}).get("reach"),
        "exists",
    )
    old = normalize_payload({"schemaVersion": 5, "inventory": {"sections": {}, "basics": basics}})
    expect("old record unchecked", status.field_view(old["inventory"]["basics"], "github")["level"], "unchecked")

    ok = not problems
    print(
        f"contact_status_and_gate: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_contact_on_save_and_privacy() -> bool:
    from context_selector import resume_context_summary, select_resume_context
    from contact import status
    from resume_ops import intake_context, update_basics

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    def raises(call) -> str:
        try:
            call()
        except ValueError as exc:
            return str(exc)
        return ""

    base = normalize_payload(load_raw_fixture("sample_career.json"))
    details = {
        "fullName": "Sam Example",
        "email": "sam@example.com",
        "phone": "+44 20 7946 0958",
        "location": "12 Secret Street, London",
    }

    saved = update_basics(base, details, github="sam", linkedin="in/sam", verify=True)
    basics = saved["inventory"]["basics"]
    expect("checks stored on save", sorted(basics["contactChecks"]), ["email", "github", "linkedin", "phone"])
    expect("gate open", status.gate(basics)["blocked"], False)
    expect("verified", saved["intake"]["basicsVerified"], True)

    # A held "exists" result survives a re-save of an unchanged field.
    held = status.record_check(
        basics, "github", {"status": "ok", "message": ""},
        {"status": "exists", "message": "This GitHub account exists."},
    )
    resaved = update_basics(
        {**saved, "inventory": {**saved["inventory"], "basics": held}},
        {**details, "email": "other@example.com"},
        github="sam",
        linkedin="in/sam",
    )
    new_basics = resaved["inventory"]["basics"]
    expect("unchanged field keeps lookup", status.field_view(new_basics, "github")["level"], "exists")
    expect("edited field re-checked", new_basics["contactChecks"]["email"]["fingerprint"], status.fingerprint("other@example.com"))
    expect("edited field not exists", status.field_view(new_basics, "email")["level"], "looks_right")
    # Editing the GitHub name drops its held result.
    renamed = update_basics(
        {**saved, "inventory": {**saved["inventory"], "basics": held}},
        details, github="sam2", linkedin="in/sam",
    )
    expect("renamed github reset", status.field_view(renamed["inventory"]["basics"], "github")["level"], "looks_right")

    # Portfolio is stored as a "Portfolio" link and checked like the others.
    with_site = update_basics(base, details, portfolio="sam.dev/work", verify=True)
    site_basics = with_site["inventory"]["basics"]
    expect("portfolio normalised", status.field_value(site_basics, "portfolio"), "https://sam.dev/work")
    expect("portfolio checked", "portfolio" in site_basics["contactChecks"], True)
    expect("portfolio left alone when not sent", status.field_value(
        update_basics(with_site, details)["inventory"]["basics"], "portfolio"), "https://sam.dev/work")
    expect("portfolio cleared when sent empty", status.field_value(
        update_basics(with_site, details, portfolio="")["inventory"]["basics"], "portfolio"), "")
    local = raises(lambda: update_basics(base, details, portfolio="http://localhost", verify=True))
    expect("localhost portfolio blocks confirm", "portfolio" in local, True)

    # The gate stops confirmation, not saving, for plainly broken fields.
    message = raises(lambda: update_basics(base, details, github="-bad-", verify=True))
    expect("broken github blocks confirm", "github" in message, True)
    draft = update_basics(base, details, github="-bad-", verify=False)
    expect("broken github can be saved as draft", draft["intake"]["basicsVerified"], False)
    expect("email without @ still refused", raises(lambda: update_basics(base, {**details, "email": "nope"})), "email must contain @")
    # Warnings never block.
    typo = update_basics(base, {**details, "email": "sam@gmial.com"}, verify=True)
    expect("typo does not block", typo["intake"]["basicsVerified"], True)
    summary = status.summary(typo["inventory"]["basics"])
    expect("summary has every field", sorted(summary["fields"]), sorted(status.FIELDS))
    expect("summary gate open", summary["gate"]["blocked"], False)

    # Contact details never reach an AI model.
    for payload in (saved,):
        shown = _json_text(intake_context(payload)) + _json_text(resume_context_summary(payload))
        shown += _json_text(select_resume_context(payload, "experience", section=None))
        for secret in ("sam@example.com", "7946", "Secret Street", "github.com/sam", "linkedin.com"):
            if secret in shown:
                problems.append(f"{secret!r} reached the assistant's context")
    expect("name still given", intake_context(saved)["basics"], {"fullName": "Sam Example"})

    ok = not problems
    print(
        f"contact_on_save_and_privacy: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_contact_background_lookups() -> bool:
    import main
    from contact import github, lookups, reach, status
    from resume_ops import update_basics

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    base = normalize_payload(load_raw_fixture("sample_career.json"))
    details = {"fullName": "Sam", "email": "sam@example.com", "phone": "+44 20 7946 0958", "location": ""}
    saved = update_basics(base, details, github="sam", linkedin="in/sam")
    saved_basics = saved["inventory"]["basics"]
    saved_basics = {**saved_basics, "links": saved_basics["links"] + [{"label": "Portfolio", "url": "https://sam.dev"}]}
    saved_basics = status.refresh_shape(saved_basics)
    saved = {**saved, "inventory": {**saved["inventory"], "basics": saved_basics}}

    calls: list[str] = []
    open_connections = [0]
    answers = {"email": "exists", "github": "exists", "portfolio": "unavailable"}

    def fake_email(value):
        calls.append("email")
        if open_connections[0]:
            problems.append("a database connection was open during a lookup")
        return {"status": answers["email"], "message": "m"}

    def fake_user(name):
        calls.append(f"github:{name}")
        return {"status": answers["github"], "message": "m"}

    def fake_page(url):
        calls.append(f"page:{url}")
        return {"status": answers["portfolio"], "message": "later"}

    real = (reach.check_email_domain, github.lookup_user, reach.check_page)
    reach.check_email_domain, github.lookup_user, reach.check_page = fake_email, fake_user, fake_page
    try:
        results = lookups.run_lookups(saved_basics)
        expect("fields looked up", sorted(results), ["email", "github", "portfolio"])
        expect("linkedin and phone never looked up", [c for c in calls if "linkedin" in c], [])
        expect("github sent only the username", "github:sam" in calls, True)

        merged = lookups.apply_results(saved_basics, results)
        expect("exists stored", status.field_view(merged, "github")["level"], "exists")
        expect("unavailable is a warning", status.field_view(merged, "portfolio")["level"], "warning")

        del calls[:]
        again = lookups.run_lookups(merged)
        expect("held 'exists' not re-asked, 'unavailable' retried", sorted(again), ["portfolio"])
        del calls[:]
        expect("force re-runs everything", sorted(lookups.run_lookups(merged, force=True)), ["email", "github", "portfolio"])

        broken = update_basics(base, details, github="-bad-")["inventory"]["basics"]
        expect("broken shape never looked up", "github" in lookups.run_lookups(broken), False)

        # An edit made while the lookup ran: the old answer must be dropped.
        edited = {**saved_basics, "links": [
            {"label": "GitHub", "url": "https://github.com/someone-else"},
            {"label": "Portfolio", "url": "https://sam.dev"},
        ]}
        landed = lookups.apply_results(edited, results)
        expect("answer for edited field dropped", status.field_view(landed, "github")["level"], "unchecked")
        expect("answer for unchanged field kept", status.field_view(landed, "email")["level"], "exists")

        # The background task end to end, against a scripted database.
        class Conn:
            def __init__(self, script):
                self.script = script
            def __enter__(self):
                open_connections[0] += 1
                return self
            def __exit__(self, *_):
                open_connections[0] -= 1
            def cursor(self):
                return self.script
            def commit(self):
                self.script.committed = True

        class Script(_FakeCursor):
            def __init__(self, first, second):
                super().__init__(version=5)
                self.first, self.second, self.committed = first, second, False
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def execute(self, sql, params=()):
                text = " ".join(sql.split())
                if text.startswith("SELECT payload"):
                    self.statements.append((text, params))
                    self._row = (self.first,)
                elif text.startswith("SELECT session_id, payload"):
                    self.statements.append((text, params))
                    self._row = ("sess_1", self.second, 5)
                else:
                    super().execute(sql, params)

        def run(first, second):
            script = Script(first, second)
            real_connect = main.psycopg.connect
            main.psycopg.connect = lambda *_a, **_k: Conn(script)
            try:
                main._run_contact_lookups("sess_1", False)
            finally:
                main.psycopg.connect = real_connect
            return script

        script = run(saved, saved)
        select_for_update = [t for t, _ in script.statements if t.endswith("FOR UPDATE")]
        expect("row locked before writing", len(select_for_update), 1)
        door = script.ran("UPDATE resume_snapshots")
        expect("written through the save door", len(door), 1)
        expect("no undo copy for background checks", script.ran("INSERT INTO resume_undo"), [])
        history = script.ran("INSERT INTO career_versions")
        expect("history entry", history[0][4] if history else None, "Contact details checked")
        stored_basics = json.loads(door[0][0])["inventory"]["basics"]
        expect("stored result", status.field_view(stored_basics, "github")["level"], "exists")
        expect("person's details untouched", stored_basics["email"], "sam@example.com")
        expect("committed", script.committed, True)

        changed_between = {**saved, "inventory": {**saved["inventory"], "basics": edited}}
        script = run(saved, changed_between)
        landed = json.loads(script.ran("UPDATE resume_snapshots")[0][0])["inventory"]["basics"]
        expect("edit during lookup not overwritten", status.field_view(landed, "github")["level"], "unchecked")

        # Nothing new to say: nothing is written.
        answers["portfolio"] = "exists"
        settled = lookups.apply_results(saved_basics, lookups.run_lookups(saved_basics))
        done = {**saved, "inventory": {**saved["inventory"], "basics": settled}}
        script = run(done, done)
        expect("unchanged result writes nothing", script.ran("UPDATE resume_snapshots"), [])

        # A lookup that blows up is swallowed and logged, never raised.
        def boom(_value):
            raise RuntimeError("outside service exploded")
        reach.check_email_domain = boom
        import logging

        logging.disable(logging.CRITICAL)  # the failure is logged on purpose
        try:
            run(saved, saved)
        except Exception as exc:
            problems.append(f"background failure escaped: {exc!r}")
        finally:
            logging.disable(logging.NOTSET)
    finally:
        reach.check_email_domain, github.lookup_user, reach.check_page = real

    ok = not problems
    print(
        f"contact_background_lookups: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_project_link_checks() -> bool:
    import main
    from contact import github, project_links, reach
    from resume_ops import add_item, update_basics, update_item

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    base = update_basics(
        normalize_payload(load_raw_fixture("sample_career.json")),
        {"fullName": "Sam", "email": "sam@example.com", "phone": "", "location": ""},
        verify=True,
    )

    def project(payload, link, name="Tool"):
        return add_item(
            payload, "projects",
            {"name": name, "url": link, "bullets": ["Built it"]},
        )

    def item_of(payload, item_id):
        return get_item_for_test(payload, "projects", item_id)

    def without_checks(payload):
        text = json.dumps(payload, sort_keys=True)
        return re.sub(r'"linkCheck": \{[^{}]*(\[[^\]]*\])?[^{}]*\}', '"linkCheck": null', text)

    # --- instant check, through the single save door ---
    drafted, repo_id = project(base, "https://github.com/octocat/hello")
    drafted, site_id = project(drafted, "https://sam.dev/tool", "Site")
    drafted, bad_id = project(drafted, "not a link!", "Bad")
    drafted, none_id = project(drafted, "", "No link")
    cur = _FakeCursor(version=1)
    saved = main._save_payload(
        cur, "s", base, drafted, operations=[{"type": "TOOL", "tool": "add_item"}], summary="x"
    )[1]
    expect("repo link checked on save", project_links.view(item_of(saved, repo_id))["level"], "looks_right")
    expect("broken link flagged", project_links.view(item_of(saved, bad_id))["level"], "broken")
    expect("no link, no record", "linkCheck" in item_of(saved, none_id), False)
    expect("record survives reload", normalize_payload(saved), saved)
    expect("pending lookups seen", project_links.pending(saved), True)

    # --- lookups pick the right check; broken, held and private links are skipped ---
    calls: list[str] = []
    real = (github.lookup_repo, reach.check_page)
    github.lookup_repo = lambda url: (calls.append(f"repo:{url}") or
        {"status": "exists", "message": "ok", "languages": ["TypeScript", "Python"]})
    reach.check_page = lambda url: (calls.append(f"page:{url}") or
        {"status": "not_found", "message": "The page wasn't found."})
    try:
        results = project_links.run_lookups(saved)
        expect("repo and page looked up, broken skipped", sorted(calls),
               ["page:https://sam.dev/tool", "repo:https://github.com/octocat/hello"])
        landed = project_links.apply_results(saved, results)
        repo_view = project_links.view(item_of(landed, repo_id))
        expect("repo exists with languages", (repo_view["level"], repo_view["languages"]),
               ("exists", ["TypeScript", "Python"]))
        expect("missing page is a warning", project_links.view(item_of(landed, site_id))["level"], "warning")
        expect("points and statuses untouched",
               without_checks(landed), without_checks(saved))
        expect("claims identical", landed["claims"], saved["claims"])
        expect("facts identical", landed["facts"], saved["facts"])
        expect("bullets identical", item_of(landed, repo_id)["bullets"], item_of(saved, repo_id)["bullets"])

        del calls[:]
        expect("held 'exists' and 'not found' not re-asked", project_links.run_lookups(landed), {})
        expect("force re-asks both", sorted(project_links.run_lookups(landed, force=True)),
               sorted([repo_id, site_id]))

        # --- an edit while the lookup ran: the old answer is dropped ---
        edited = update_item(saved, "projects", repo_id, {"url": "https://github.com/octocat/other"})
        stale = project_links.apply_results(edited, results)
        expect("answer for edited link dropped",
               project_links.view(item_of(stale, repo_id))["level"], "unchecked")
        resaved = main._save_payload(
            _FakeCursor(version=2), "s", landed,
            update_item(landed, "projects", repo_id, {"url": "https://github.com/octocat/other"}),
            operations=[{"type": "TOOL", "tool": "update_item"}], summary="x",
        )[1]
        expect("edited link re-checked on save",
               project_links.view(item_of(resaved, repo_id))["level"], "looks_right")
        expect("unchanged link keeps its answer",
               project_links.view(item_of(resaved, site_id))["level"], "warning")

        # --- private repositories ---
        flagged = project_links.set_private(landed, repo_id, True)
        view = project_links.view(item_of(flagged, repo_id))
        expect("private view", (view["level"], view["message"], view["languages"]),
               ("private", "Private, not checked.", []))
        expect("private never looked up",
               repo_id in project_links.run_lookups(flagged, force=True), False)
        expect("private survives a late answer",
               project_links.view(item_of(project_links.apply_results(flagged, results), repo_id))["level"],
               "private")
        expect("unmarking asks again", repo_id in project_links.run_lookups(
            project_links.set_private(flagged, repo_id, False)), True)
        expect("no link cannot be private",
               "no link" in str(_raises_text(lambda: project_links.set_private(saved, none_id, True))), True)
        expect("unknown entry", _raises(lambda: project_links.set_private(saved, "nope", True), KeyError), True)
    finally:
        github.lookup_repo, reach.check_page = real

    # --- the background task, against a scripted database ---
    class Conn:
        def __init__(self, script):
            self.script = script
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def cursor(self):
            return self.script
        def commit(self):
            self.script.committed = True

    class Script(_FakeCursor):
        def __init__(self, first, second):
            super().__init__(version=5)
            self.first, self.second, self.committed = first, second, False
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def execute(self, sql, params=()):
            text = " ".join(sql.split())
            if text.startswith("SELECT payload"):
                self.statements.append((text, params))
                self._row = (self.first,)
            elif text.startswith("SELECT session_id, payload"):
                self.statements.append((text, params))
                self._row = ("s", self.second, 5)
            else:
                super().execute(sql, params)

    real_lookup = (github.lookup_repo, reach.check_page)
    github.lookup_repo = lambda url: {"status": "exists", "message": "ok", "languages": ["Go"]}
    reach.check_page = lambda url: {"status": "exists", "message": "The page opens."}
    real_connect = main.psycopg.connect
    script = Script(saved, saved)
    main.psycopg.connect = lambda *_a, **_k: Conn(script)
    try:
        main._run_link_lookups("s", False)
    finally:
        main.psycopg.connect = real_connect
        github.lookup_repo, reach.check_page = real_lookup
    door = script.ran("UPDATE resume_snapshots")
    expect("row locked", len([t for t, _ in script.statements if t.endswith("FOR UPDATE")]), 1)
    expect("written once through the door", len(door), 1)
    expect("no undo copy", script.ran("INSERT INTO resume_undo"), [])
    history = script.ran("INSERT INTO career_versions")
    expect("history label", history[0][4] if history else None, "Project links checked")
    if door:
        stored = json.loads(door[0][0])
        expect("languages stored", project_links.view(item_of(stored, repo_id))["languages"], ["Go"])
    expect("committed", script.committed, True)

    ok = not problems
    print(
        f"project_link_checks: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def _raises_text(call) -> str:
    try:
        call()
    except Exception as exc:
        return str(exc)
    return ""


def _json_text(value) -> str:
    return json.dumps(value, default=str)


def main() -> int:
    tests = [
        test_contact_shape_rules,
        test_contact_on_save_and_privacy,
        test_contact_background_lookups,
        test_project_link_checks,
        test_contact_status_and_gate,
        test_contact_exists_lookups,
        test_safe_fetch_refuses_dangerous_links,
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
        test_projects_upgrade_changes_nothing,
        test_project_points_stay_separate,
        test_projects_tolerate_bad_data,
        test_project_operations,
        test_project_search_and_facts,
        test_save_door,
        test_voice_add_entry_end_to_end,
        test_assistant_result_is_small_and_constant,
        test_live_path_guard,
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
