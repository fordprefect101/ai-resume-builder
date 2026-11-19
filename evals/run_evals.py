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


def test_voice_can_end_call() -> bool:
    """Only the voice call gets end_voice_session, and its instructions say when to use it."""
    import chat_tools
    import realtime

    problems = []
    for label, payload in (
        ("intake", {"intake": {"status": "in_progress"}}),
        ("edit", load_raw_fixture("sample_career.json")),
    ):
        voice = {t["name"] for t in chat_tools.voice_tools_for_payload(payload)}
        chat = {t["name"] for t in chat_tools.tools_for_payload(payload)}
        if "end_voice_session" not in voice:
            problems.append(f"{label}: voice tools lack end_voice_session")
        if "end_voice_session" in chat:
            problems.append(f"{label}: text chat is offered end_voice_session")
    if "end_voice_session" in {t["name"] for t in chat_tools.TOOL_DEFINITIONS}:
        problems.append("end_voice_session is in the shared tool list")
    rule = realtime.END_CALL_RULE
    for needle in ("end_voice_session", "complete_intake", "goodbye", "done"):
        if needle not in rule:
            problems.append(f"end-call rule does not mention {needle!r}")
    src = (ROOT / "api" / "realtime.py").read_text()
    if src.count("END_CALL_RULE") < 3:
        problems.append("both modes' instructions must include END_CALL_RULE")
    ts = (ROOT / "web" / "src" / "voice" / "handleRealtimeTools.ts").read_text()
    if "toolsAreRunning" not in (ROOT / "web" / "src" / "App.tsx").read_text():
        problems.append("the app does not wait for running tool calls before hanging up")
    ok = not problems
    print(f"voice_can_end_call: {'PASS' if ok else 'FAIL'} (problems={problems})")
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


def test_model_switchboard() -> bool:
    from pydantic import BaseModel

    from writing import models

    class Facts(BaseModel):
        facts: list[str]

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    saved_env = {k: os.environ.get(k) for k in (*models.JOB_SETTINGS.values(), "OPENAI_CHAT_MODEL")}

    def configure(**values):
        for key in saved_env:
            os.environ.pop(key, None)
        os.environ.update(values)

    class Script:
        """Stands in for OpenAI: replays scripted replies and records each request."""

        replies: list = []
        seen: list = []

        def complete(self, model, messages, temperature):
            Script.seen.append((model, messages, temperature))
            reply = Script.replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply, 10, 5

    def script(*replies):
        Script.replies, Script.seen = list(replies), []

    real_adapter = models.ADAPTERS["openai"]
    models.ADAPTERS["openai"] = Script
    try:
        # --- which model does which job ---
        configure()
        expect("nothing set", models.resolve("writer"), ("openai", "gpt-4.1-mini"))
        configure(OPENAI_CHAT_MODEL="gpt-x")
        expect("falls back to the chat model", models.resolve("checker"), ("openai", "gpt-x"))
        configure(WRITER_MODEL="openai:big-model", OPENAI_CHAT_MODEL="gpt-x")
        expect("job setting wins", models.resolve("writer"), ("openai", "big-model"))
        expect("other jobs unaffected", models.resolve("analyst"), ("openai", "gpt-x"))
        configure(WRITER_MODEL="  OpenAI : spaced-model ")
        expect("tidy parsing", models.resolve("writer"), ("openai", "spaced-model"))
        configure(WRITER_MODEL="bare-model")
        expect("bare name means openai", models.resolve("writer"), ("openai", "bare-model"))
        for bad in ("martian:model", "openai:"):
            configure(WRITER_MODEL=bad)
            try:
                models.resolve("writer")
                problems.append(f"{bad!r} accepted")
            except models.ConfigError:
                pass
        configure()
        try:
            models.resolve("barista")
            problems.append("unknown job accepted")
        except models.ConfigError:
            pass

        # --- a good reply ---
        configure()
        script('{"facts": ["built a thing"]}')
        good = models.complete_json("writer", [{"role": "user", "content": "go"}], Facts)
        expect("good reply", (good.ok, good.data.facts if good.data else None, good.attempts),
               (True, ["built a thing"], 1))
        expect("tokens counted", (good.input_tokens, good.output_tokens), (10, 5))
        expect("model recorded", (good.provider, good.model, good.job), ("openai", "gpt-4.1-mini", "writer"))
        expect("temperature omitted by default", Script.seen[0][2], None)

        script('```json\n{"facts": []}\n```')
        expect("fenced reply accepted", models.complete_json("writer", [], Facts).ok, True)

        # --- a reply that does not fit is retried once, with the complaint ---
        script("not json at all", '{"facts": ["ok"]}')
        retried = models.complete_json("writer", [{"role": "user", "content": "go"}], Facts)
        expect("retry fixes it", (retried.ok, retried.attempts), (True, 2))
        expect("tokens add up over both tries", retried.input_tokens, 20)
        second_request = Script.seen[1][1]
        expect("complaint sent back", "did not match the required JSON shape" in second_request[-1]["content"], True)
        expect("bad reply shown to the model", second_request[-2], {"role": "assistant", "content": "not json at all"})

        script('{"wrong": 1}', '{"facts": "not a list"}')
        failed = models.complete_json("writer", [], Facts)
        expect("two bad replies fail the step", (failed.ok, failed.attempts, failed.data), (False, 2, None))
        expect("failure explained", "required shape" in failed.error, True)

        # --- outside trouble is a failed step, never a crash or a retry ---
        script(RuntimeError("service down"))
        down = models.complete_json("writer", [], Facts)
        expect("outage is a failed step", (down.ok, down.attempts), (False, 1))
        expect("outage explained", "service down" in down.error, True)

        # --- the real adapter without a key fails the step cleanly (no network) ---
        models.ADAPTERS["openai"] = real_adapter
        saved_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            nokey = models.complete_json("writer", [], Facts)
            expect("no key", (nokey.ok, "OPENAI_API_KEY" in nokey.error), (False, True))
        finally:
            if saved_key is not None:
                os.environ["OPENAI_API_KEY"] = saved_key
    finally:
        models.ADAPTERS["openai"] = real_adapter
        for key, value in saved_env.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value

    # --- every job setting is listed in the example settings file ---
    example = (ROOT / "api" / ".env.example").read_text()
    for setting in models.JOB_SETTINGS.values():
        if f"{setting}=" not in example:
            problems.append(f"{setting} missing from .env.example")

    ok = not problems
    print(
        f"model_switchboard: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_cost_and_run_records() -> bool:
    from pydantic import BaseModel

    from writing import models, records

    class Facts(BaseModel):
        facts: list[str]

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    # --- the hand-kept price list is well formed ---
    listed = records.load_prices()
    for provider, table in listed.items():
        for model, price in table.items():
            if not (isinstance(price, dict) and all(
                isinstance(price.get(k), (int, float)) and price[k] >= 0 for k in ("input", "output")
            )):
                problems.append(f"bad price entry {provider}:{model}")
    raw = json.loads(records.PRICES_FILE.read_text())
    if not (raw.get("_source", "").startswith("https://") and raw.get("_copiedOn")):
        problems.append("prices.json does not say where and when the prices were copied")

    # --- cost arithmetic ---
    real_prices = records.PRICES
    records.PRICES = {"openai": {"cheap": {"input": 0.5, "output": 2.0}, "broken": None}}
    try:
        expect("cost", records.cost_usd("openai", "cheap", 1_000_000, 500_000), 1.5)
        expect("small cost", records.cost_usd("openai", "cheap", 1000, 200), 0.0009)
        expect("zero tokens", records.cost_usd("openai", "cheap", 0, 0), 0.0)
        expect("unlisted model is unpriced", records.cost_usd("openai", "mystery", 10, 10), None)
        expect("null price is unpriced", records.cost_usd("openai", "broken", 10, 10), None)
        expect("unknown provider is unpriced", records.cost_usd("other", "cheap", 10, 10), None)

        # --- the switchboard fills cost in; a Run totals steps and admits unpriced ones ---
        class Script:
            def complete(self, model, messages, temperature):
                return '{"facts": ["a"]}', 2000, 400

        real_adapter = models.ADAPTERS["openai"]
        models.ADAPTERS["openai"] = Script
        saved_env = os.environ.get("WRITER_MODEL"), os.environ.get("CHECKER_MODEL")
        os.environ["WRITER_MODEL"] = "openai:cheap"
        os.environ["CHECKER_MODEL"] = "openai:mystery"
        try:
            asked = [{"role": "user", "content": "Reach me at sam@example.com or +44 20 7946 0958"}]
            priced = models.complete_json("writer", asked, Facts)
            unpriced = models.complete_json("checker", asked, Facts)
        finally:
            models.ADAPTERS["openai"] = real_adapter
            for name, value in zip(("WRITER_MODEL", "CHECKER_MODEL"), saved_env):
                os.environ.pop(name, None)
                if value is not None:
                    os.environ[name] = value
        expect("switchboard prices a call", priced.cost_usd, 0.0018)
        expect("switchboard leaves unpriced as None", unpriced.cost_usd, None)

        run = records.Run("entry exp_1")
        run.add(priced, asked, name="writer")
        run.add(unpriced, asked, name="checker")
        totals = run.totals()
        expect("totals", (totals["steps"], totals["inputTokens"], totals["outputTokens"]), (2, 4000, 800))
        expect("total cost counts only priced steps", totals["costUsd"], 0.0018)
        expect("unpriced steps are admitted", totals["unpricedSteps"], 1)

        # --- the stored trace is json-safe and holds no contact details ---
        trace = run.as_trace()
        text = json.dumps(trace)
        for secret in ("sam@example.com", "7946 0958"):
            if secret in text:
                problems.append(f"{secret!r} reached the run record")
        expect("redaction marks left", "[email]" in text and "[phone]" in text, True)
        expect("record has the step name and model", (trace["steps"][0]["step"], trace["steps"][0]["model"]), ("writer", "cheap"))
        failure = models.Result(ok=False, job="writer", error="x" * 1000)
        expect("long errors are clipped", len(records.step_record(failure)["error"]) <= 300, True)
    finally:
        records.PRICES = real_prices

    # --- redaction keeps ordinary resume text ---
    for kept in ("Cut load time by 40% in 2019-2023", "Served 10,000 users and 1.2M requests",
                 "Led a team of 5 from 2021 to 2024", "Used Python 3.12 and Node.js"):
        expect(f"kept {kept!r}", records.redact(kept), kept)
    expect("link redacted", records.redact("see https://github.com/sam/x and www.sam.dev"), "see [link] and [link]")
    expect("country number redacted", records.redact("call +1 415 555 0100 now"), "call [phone] now")
    expect("long number redacted", records.redact("tel 020 7946 0958"), "tel [phone]")
    clipped = records.step_record(
        models.Result(ok=True, job="writer"), [{"role": "user", "content": "y" * 9000}]
    )["input"][0]["content"]
    expect("long text is clipped", len(clipped) <= records.MAX_TEXT + 1, True)

    ok = not problems
    print(
        f"cost_and_run_records: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_writing_rules() -> bool:
    import claim_verify
    from writing import rules

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    # --- reading numbers the way a person writes them ---
    for text, want in (
        ("cut load time by 40%", {40.0}),
        ("about forty percent faster", {40.0}),
        ("twenty five engineers", {25.0}),
        ("two hundred users", {200.0}),
        ("three thousand requests", {3000.0}),
        ("10,000 users", {10000.0}),
        ("handled 10k requests", {10000.0}),
        ("1.2M rows", {1_200_000.0}),
        ("3 million rows", {3_000_000.0}),
        ("1.5 thousand users", {1500.0}),
        ("12 months and 5 bugs", {12.0, 5.0}),
        ("420 ms and 1.8 s", {420.0, 1.8}),
        ("Python 3.12", {3.12}),
        ("from 2019-2023", {2019.0, 2023.0}),
        ("no numbers here", set()),
        ("one of the team", {1.0}),
    ):
        expect(f"numbers in {text!r}", rules.numbers_in(text), want)

    # --- step 3: facts must be quoted from the story ---
    story = [
        {"id": "s1", "text": "So we built the dashboard with React and Redis. It cut the load time by like forty percent!"},
        {"id": "s2", "text": "I led\n the migration   to Postgres, “the hard part”, for our team of five."},
    ]

    def fact(content, quote, **extra):
        return {"content": content, "quote": quote, **extra}

    facts = [
        fact("Built a dashboard with React and Redis", "built the dashboard with React and Redis", kind="tool", owner="team"),
        fact("Cut load time by 40%", "cut the load time by like forty percent", kind="result", owner="me"),
        fact("Led the Postgres migration", "I led the migration to Postgres", kind="action", owner="me"),
        fact("Said a thing", "we shipped to a million users"),
        fact("Cut costs by 60%", "cut the load time by like forty percent"),
        fact("No quote at all", ""),
        fact("Skips words", "built the dashboard ... cut the load time", kind="made-up-kind", owner="boss"),
        fact("Wrong order", "cut the load time ... built the dashboard"),
        fact("Spans two chunks", "forty percent! I led"),
        fact("Curly quotes", "\"the hard part\""),
        fact("", "built the dashboard"),
    ]
    kept, dropped = rules.check_facts(facts, story)
    kept_names = [f["content"] for f in kept]
    expect("kept facts", kept_names, [
        "Built a dashboard with React and Redis", "Cut load time by 40%",
        "Led the Postgres migration", "Skips words", "Curly quotes"])
    reasons = {d["fact"].get("content"): d["reason"] for d in dropped}
    expect("invented quote dropped", reasons.get("Said a thing"), "quote is not in the story")
    expect("invented number dropped", reasons.get("Cut costs by 60%", "")[:23], "number not in its quote")
    expect("missing quote dropped", reasons.get("No quote at all"), "no usable quote")
    expect("out-of-order pieces dropped", reasons.get("Wrong order"), "quote is not in the story")
    expect("quote spanning chunks dropped", reasons.get("Spans two chunks"), "quote is not in the story")
    expect("empty fact dropped", reasons.get(""), "empty fact")
    by_content = {f["content"]: f for f in kept}
    expect("source chunk recorded", by_content["Led the Postgres migration"]["storyId"], "s2")
    expect("unknown labels become safe defaults",
           (by_content["Skips words"]["kind"], by_content["Skips words"]["owner"]), ("unsorted", "unclear"))
    expect("known labels kept", by_content["Cut load time by 40%"]["owner"], "me")

    # --- step 5: points against their facts ---
    f_build = {"id": "f1", "content": "Built a dashboard with React and Redis", "quote": "built the dashboard with React and Redis", "kind": "tool", "owner": "team"}
    f_speed = {"id": "f2", "content": "Cut load time by 40%", "quote": "cut the load time by like forty percent", "kind": "result", "owner": "me"}
    f_lead = {"id": "f3", "content": "Led the Postgres migration", "quote": "I led the migration to Postgres", "kind": "action", "owner": "me"}
    facts5 = [f_build, f_speed, f_lead]

    def codes(content, cites, terms=()):
        return sorted(i["code"] for i in rules.check_point({"content": content, "supportedBy": cites}, facts5, terms))

    expect("clean point", codes("Cut dashboard load time by 40% with React and Redis", ["f1", "f2"]), [])
    expect("number words match digits", codes("Reduced load time by forty percent after the rebuild", ["f2"]), [])
    expect("invented number", codes("Cut dashboard load time by 70% with React", ["f1", "f2"]), ["number_not_in_facts"])
    expect("number from an uncited fact", codes("Cut load time by 40% using React", ["f1"]), ["number_not_in_facts"])
    expect("invented tool", codes("Built a dashboard with React and Kafka", ["f1"]), ["tool_not_in_facts"])
    expect("cited tool passes", codes("Built a dashboard with React and Redis", ["f1"]), [])
    expect("company allowed without a fact", codes("Built a dashboard for ChaiShots with React", ["f1"], ["ChaiShots"]), [])
    expect("company not allowed otherwise", codes("Built a dashboard for ChaiShots with React", ["f1"]), ["tool_not_in_facts"])
    expect("acronym not in facts", codes("Deployed the dashboard to AWS", ["f1"]), ["tool_not_in_facts"])
    expect("first word is not a tool", codes("Rebuilt the dashboard using React", ["f1"]), [])
    expect("first person", "first_person" in codes("Built the dashboard that we use with React", ["f1"]), True)
    expect("I/O alone is not first person", "first_person" in codes("Tuned I/O for the React dashboard", ["f1"]), False)
    for opener in ("Responsible for the dashboard in React", "Worked on the React dashboard", "Building the React dashboard", "The dashboard was built in React"):
        expect(f"weak start {opener!r}", "weak_start" in codes(opener, ["f1"]), True)
    expect("short point", "too_short" in codes("Built it", ["f1"]), True)
    expect("long point", "too_long" in codes(" ".join(["Built"] + ["react"] * 40), ["f1"]), True)
    expect("no citation", "no_supporting_fact" in codes("Built a dashboard with React", []), True)
    expect("unknown citation", "unknown_fact" in codes("Built a dashboard with React", ["nope"]), True)
    expect("boastful word not in facts", "boastful_term" in codes("Built an enterprise dashboard with React", ["f1"]), True)
    backed = {"id": "g", "content": "Built an enterprise dashboard with React", "quote": "enterprise dashboard", "owner": "me"}
    backed_issues = rules.check_point(
        {"content": "Built an enterprise dashboard with React", "supportedBy": ["g"]}, [backed]
    )
    expect("boastful word backed by its fact passes", [i["code"] for i in backed_issues], [])

    # "we built X" must not become "led X"
    expect("leadership claimed from a team fact", "ownership_not_in_facts" in codes("Led the dashboard build in React", ["f1"]), True)
    expect("leadership backed by a me fact", "ownership_not_in_facts" in codes("Led the Postgres migration", ["f3"]), False)
    expect("team work stated plainly is fine", "ownership_not_in_facts" in codes("Built a dashboard with React and Redis", ["f1"]), False)
    expect("sole credit from a team fact", "ownership_not_in_facts" in codes("Single-handedly built the dashboard in React", ["f1"]), True)

    # --- the list of points ---
    good = [{"content": "Built a dashboard with React and Redis", "supportedBy": ["f1"]},
            {"content": "Cut load time by 40% on the dashboard", "supportedBy": ["f2"]}]
    expect("good list", rules.check_points(good, facts5)["listIssues"], [])
    expect("duplicates", [i["code"] for i in rules.check_points(good + [good[0]], facts5)["listIssues"]], ["duplicate"])
    expect("none written", [i["code"] for i in rules.check_points([], facts5)["listIssues"]], ["no_points"])
    six = [{"content": f"Built dashboard number {n} with React", "supportedBy": ["f1"]} for n in range(6)]
    expect("too many", "too_many_points" in [i["code"] for i in rules.check_points(six, facts5)["listIssues"]], True)
    expect("per-point issues align", len(rules.check_points(good, facts5)["perPoint"]), 2)

    # --- the shared boastful-word list, and no AI inside the rules ---
    expect("claim_verify shares the list", claim_verify.BOASTFUL_WORDS, rules.BOASTFUL_WORDS)
    imports = {
        (n.module or "").split(".")[0] if isinstance(n, ast.ImportFrom) else a.name.split(".")[0]
        for n in ast.walk(ast.parse((ROOT / "api" / "writing" / "rules.py").read_text()))
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in (n.names if isinstance(n, ast.Import) else [n])
    }
    expect("rules.py stays code-only", imports <= {"__future__", "re"}, True)

    ok = not problems
    print(
        f"writing_rules: {'PASS' if ok else 'FAIL'} "
        f"({len(problems)} problems{': ' + '; '.join(problems) if problems else ''})"
    )
    return ok


def test_writing_cases_valid() -> bool:
    from writing import rules

    cases_dir = ROOT / "evals" / "writing" / "cases"
    problems: list[str] = []
    core = {
        "rambling product description", "we versus I", "no numbers", "lots of numbers",
        "two projects mixed", "very short answer", "imperfect English",
    }
    sources = {"voice", "typed", "followup", "imported"}
    covered: set[str] = set()
    ids: set[str] = set()
    phrases = 0

    cases = [json.loads(p.read_text()) for p in sorted(cases_dir.glob("*.json"))]
    if len(cases) < 10:
        problems.append(f"only {len(cases)} stories")
    for case in cases:
        cid = case.get("id", "?")
        for key in ("id", "profession", "hardCase", "entry", "story", "mustCapture", "mustNotClaim", "missing"):
            if key not in case:
                problems.append(f"{cid}: missing {key}")
        if cid in ids:
            problems.append(f"{cid}: duplicate id")
        ids.add(cid)
        covered.add(case.get("hardCase", ""))
        chunks = case.get("story") or []
        chunk_ids = [c.get("id") for c in chunks]
        if len(set(chunk_ids)) != len(chunk_ids) or not chunks:
            problems.append(f"{cid}: story chunk ids are not unique")
        if any(c.get("source") not in sources for c in chunks):
            problems.append(f"{cid}: unknown story source")
        story_text = " ".join(rules.normalize(c.get("text")) for c in chunks)
        captures = case.get("mustCapture") or []
        if len({k.get("id") for k in captures}) != len(captures) or not captures:
            problems.append(f"{cid}: mustCapture ids are not unique")
        for k in captures:
            phrases += 1
            if not any(rules.normalize(k["phrase"]) in rules.normalize(c["text"]) for c in chunks):
                problems.append(f"{cid}/{k['id']}: phrase is not in the story")
            if k.get("kind") not in rules.FACT_KINDS or k.get("owner") not in rules.FACT_OWNERS:
                problems.append(f"{cid}/{k['id']}: bad kind or owner")
        for term in case.get("mustNotClaim") or []:
            pattern = rf"(?<![a-z0-9]){re.escape(rules.normalize(term))}(?![a-z0-9])" if term[:1].isalnum() else re.escape(term)
            if re.search(pattern, story_text):
                problems.append(f"{cid}: story contains forbidden term {term!r}")
        # With perfect facts built from the phrases, the rules must keep every one.
        perfect = [{"content": k["phrase"], "quote": k["phrase"], "kind": k["kind"], "owner": k["owner"]} for k in captures]
        kept, dropped = rules.check_facts(perfect, chunks)
        if dropped:
            problems.append(f"{cid}: rules dropped true facts: {[d['reason'] for d in dropped]}")
    missing = sorted(core - covered)
    if missing:
        problems.append(f"hard cases not covered: {missing}")

    # --- traps ---
    traps = json.loads((ROOT / "evals" / "writing" / "traps.json").read_text())["traps"]
    by_id = {t["id"]: t for t in traps}
    honest = exaggerated = caught = gaps = 0
    for trap in traps:
        facts = trap.get("facts") or by_id.get(trap.get("factsFrom"), {}).get("facts")
        if not facts:
            problems.append(f"{trap['id']}: no facts")
            continue
        found = [i["code"] for i in rules.check_point(
            {"content": trap["point"], "supportedBy": trap["supportedBy"]}, facts)]
        if trap["label"] == "honest":
            honest += 1
            if found:
                problems.append(f"{trap['id']}: honest point flagged {found}")
        else:
            exaggerated += 1
            if trap["codeShouldCatch"]:
                caught += 1
                if not set(trap["expectedCodes"]) <= set(found):
                    problems.append(f"{trap['id']}: expected {trap['expectedCodes']}, got {found}")
            else:
                gaps += 1  # a known gap; if the rules ever catch it, relabel it
    if honest != exaggerated or honest < 6:
        problems.append(f"traps: {honest} honest vs {exaggerated} exaggerated")

    ok = not problems
    print(
        f"writing_cases_valid: {'PASS' if ok else 'FAIL'} "
        f"(stories={len(cases)}, phrases={phrases}, trap pairs={honest}, "
        f"rules catch {caught}, known gaps for the AI checker={gaps}, problems={problems})"
    )
    return ok


def test_analyst() -> bool:
    import writing_scoring
    from writing import analyst, models

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    cases = {
        p.stem: json.loads(p.read_text())
        for p in sorted((ROOT / "evals" / "writing" / "cases").glob("*.json"))
    }

    # --- which guide, and what the model is shown ---
    expect("engineer gets tech", analyst.pick_guide({"title": "Backend Engineer"}), "tech")
    expect("project gets tech", analyst.pick_guide({"section": "projects", "title": "My thing"}), "tech")
    expect("manager gets general", analyst.pick_guide({"title": "Marketing Manager"}), "general")
    expect("nothing known gets general", analyst.pick_guide({}), "general")
    case = cases["rambling_product"]
    messages = analyst.build_messages(case["story"], case["entry"], "tech")
    expect("system holds the instructions and the guide",
           ("You are the analyst" in messages[0]["content"], "What matters in tech work" in messages[0]["content"]),
           (True, True))
    expect("user holds the chunks with ids", "[c1 | voice] So at the startup" in messages[1]["content"], True)
    expect("prompt version is short and stable", (len(analyst.PROMPT_VERSION), analyst.PROMPT_VERSION), (8, analyst.PROMPT_VERSION))

    class Script:
        replies: list = []

        def complete(self, model, messages, temperature):
            reply = Script.replies.pop(0) if Script.replies else Script.fallback
            return (json.dumps(reply) if not isinstance(reply, str) else reply), 100, 50

        fallback: object = {}

    def reply_for(case, picks=None, *, owner=None):
        picks = case["mustCapture"] if picks is None else picks
        return {"facts": [
            {"content": k["phrase"], "kind": k["kind"], "owner": owner or k["owner"], "quote": k["phrase"]}
            for k in picks
        ], "missing": []}

    real_adapter = models.ADAPTERS["openai"]
    models.ADAPTERS["openai"] = Script
    try:
        # --- one realistic mixed reply: good, invented, mislabelled, duplicated ---
        good = reply_for(case)
        mixed = {
            "facts": good["facts"] + [
                {"content": "Served 5000 salons", "kind": "scale", "owner": "me", "quote": "we serve five thousand salons"},
                {"content": good["facts"][0]["content"], "kind": "action", "owner": "me", "quote": good["facts"][0]["quote"]},
                {"content": "Wrote it all", "kind": "heroics", "owner": "boss", "quote": "I fixed it by locking the slot"},
            ],
            "missing": ["How many salons?", "What was the result?", "A third question", "  "],
        }
        Script.replies = [mixed]
        analysis = analyst.analyse(case["story"], case["entry"])
        expect("reply accepted", analysis.ok, True)
        expect("invented quote dropped", [d["reason"] for d in analysis.dropped if d["fact"]["content"] == "Served 5000 salons"], ["quote is not in the story"])
        expect("duplicate dropped", "duplicate fact" in [d["reason"] for d in analysis.dropped], True)
        expect("true facts kept", len(analysis.facts), 5)
        wrote = next(f for f in analysis.facts if f["content"] == "Wrote it all")
        expect("odd labels become safe defaults", (wrote["kind"], wrote["owner"]), ("unsorted", "unclear"))
        expect("facts get ids and sources", all(f["id"].startswith("fact_") and f["storyId"] in ("c1", "c2") for f in analysis.facts), True)
        expect("ids are unique", len({f["id"] for f in analysis.facts}), len(analysis.facts))
        expect("source chunk found", next(f for f in analysis.facts if "locking the slot" in f["quote"] and f["content"] != "Wrote it all")["storyId"], "c2")
        expect("questions capped and tidied", analysis.missing, ["How many salons?", "What was the result?"])
        expect("guide and version recorded", (analysis.guide, analysis.prompt_version), ("tech", analyst.PROMPT_VERSION))

        # --- an unusable reply is a failed step, not a crash ---
        Script.replies = ["not json", "still not json"]
        broken = analyst.analyse(case["story"], case["entry"])
        expect("broken reply", (broken.ok, broken.facts, bool(broken.error)), (False, [], True))
        Script.replies = [{"nothing": "useful"}, {"facts": "no"}]
        expect("wrong shape", analyst.analyse(case["story"], case["entry"]).ok, False)

        # --- the whole path on all ten stories: story -> model -> rules -> score ---
        scores = {"perfect": [], "lazy": [], "paraphrasing": [], "claims me": []}
        for c in cases.values():
            Script.replies = [reply_for(c)]
            scores["perfect"].append(writing_scoring.score_facts(c, (a := analyst.analyse(c["story"], c["entry"])).facts, a.dropped))
            Script.replies = [reply_for(c, c["mustCapture"][:1])]
            scores["lazy"].append(writing_scoring.score_facts(c, (a := analyst.analyse(c["story"], c["entry"])).facts, a.dropped))
            paraphrased = reply_for(c)
            for f in paraphrased["facts"]:
                f["quote"] = "basically " + f["quote"] + " and so on forever"
            Script.replies = [paraphrased]
            scores["paraphrasing"].append(writing_scoring.score_facts(c, (a := analyst.analyse(c["story"], c["entry"])).facts, a.dropped))
            Script.replies = [reply_for(c, owner="me")]
            scores["claims me"].append(writing_scoring.score_facts(c, (a := analyst.analyse(c["story"], c["entry"])).facts, a.dropped))
    finally:
        models.ADAPTERS["openai"] = real_adapter

    perfect = writing_scoring.summarize(scores["perfect"])
    expect("perfect analyst recall", (perfect["meanRecall"], perfect["worstRecall"]), (1.0, 1.0))
    expect("perfect analyst owners", perfect["meanOwnerRight"], 1.0)
    expect("perfect analyst loses nothing", perfect["droppedFacts"], 0)
    lazy = writing_scoring.summarize(scores["lazy"])
    expect("lazy analyst scores low", lazy["meanRecall"] < 0.5 and lazy["worstRecall"] < 0.5, True)
    expect("single-fact story cannot be lazy", scores["lazy"][[c["id"] for c in cases.values()].index("very_short")]["recall"], 1.0)
    para = writing_scoring.summarize(scores["paraphrasing"])
    expect("padded quotes are dropped and found out",
           para["keptFacts"] < perfect["keptFacts"] and para["meanRecall"] < 1.0, True)
    greedy = writing_scoring.summarize(scores["claims me"])
    expect("turning we into me is measured", greedy["meanOwnerRight"] < 1.0, True)

    # --- covers(): what counts as capturing a phrase ---
    f = {"quote": "I built the booking page in React"}
    expect("same words", writing_scoring.covers(f, "I built the booking page in React"), True)
    expect("quote inside phrase", writing_scoring.covers({"quote": "booking page in React"}, "I built the booking page in React"), True)
    expect("most words shared", writing_scoring.covers({"quote": "built booking page React"}, "I built the booking page in React"), True)
    expect("unrelated", writing_scoring.covers({"quote": "stopped getting angry emails"}, "I built the booking page in React"), False)
    expect("empty quote", writing_scoring.covers({"quote": ""}, "anything"), False)

    ok = not problems
    print(
        f"analyst: {'PASS' if ok else 'FAIL'} "
        f"(stories={len(cases)}, problems={problems})"
    )
    return ok


def test_writer() -> bool:
    import writing_scoring
    from writing import models, writer

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    cases = {
        p.stem: json.loads(p.read_text())
        for p in sorted((ROOT / "evals" / "writing" / "cases").glob("*.json"))
    }
    booking = cases["rambling_product"]
    team = cases["we_versus_i_team"]
    booking_facts = writing_scoring.ground_truth_facts(booking)
    team_facts = writing_scoring.ground_truth_facts(team)

    class Script:
        replies: list = []
        seen: list = []

        def complete(self, model, messages, temperature):
            Script.seen.append(messages)
            reply = Script.replies.pop(0)
            return (json.dumps(reply) if not isinstance(reply, str) else reply), 80, 40

    def point(content, *cites):
        return {"content": content, "supportedBy": list(cites)}

    real_adapter = models.ADAPTERS["openai"]
    models.ADAPTERS["openai"] = Script
    try:
        # --- what the model is shown ---
        Script.replies, Script.seen = [{"points": [point("Built the booking page in React", "gt_k1")]}], []
        shown_facts = [{**booking_facts[0], "content": "Built the booking page in React", "quote": "WORDS ONLY IN THE QUOTE"}]
        writer.write(shown_facts, booking["entry"])
        user = Script.seen[0][1]["content"]
        expect("fact id, kind, owner and content shown", "[gt_k1] (action, owner: me) Built the booking page in React" in user, True)
        expect("quotes are not shown", "WORDS ONLY IN THE QUOTE" in user, False)
        expect("instructions and guide shown", ("You are the writer" in Script.seen[0][0]["content"], "What matters in tech work" in Script.seen[0][0]["content"]), (True, True))

        # --- a clean draft ---
        clean = {"points": [
            point("Built the booking page in React", "gt_k1"),
            point("Fixed double bookings by locking the slot during checkout", "gt_k3"),
            point("Stopped the angry emails about double bookings.", "gt_k4"),
        ]}
        Script.replies = [clean]
        draft = writer.write(booking_facts, booking["entry"])
        expect("clean draft", (draft.ok, draft.clean, len(draft.points)), (True, True, 3))
        expect("final period tidied", draft.points[2]["content"], "Stopped the angry emails about double bookings")
        score = writing_scoring.score_points(booking, draft.points, draft.issues["perPoint"])
        expect("clean draft scores", (score["inventionRate"], score["stylePassRate"], score["forbidden"]), (0.0, 1.0, []))

        # --- the rules flag what the writer got wrong, point by point ---
        Script.replies = [{"points": [
            point("Cut double bookings by 90%", "gt_k4"),
            point("Built the booking page in React and Redis", "gt_k1"),
            point("Responsible for the booking page", "gt_k1"),
            point("Built the booking page in React", "gt_missing"),
            point("Built the booking page in React", "gt_k1"),
        ]}]
        bad = writer.write(booking_facts, booking["entry"])
        found = [sorted(i["code"] for i in issues) for issues in bad.issues["perPoint"]]
        expect("invented number", "number_not_in_facts" in found[0], True)
        expect("invented tool", "tool_not_in_facts" in found[1], True)
        expect("weak opener", "weak_start" in found[2], True)
        expect("unknown fact", "unknown_fact" in found[3], True)
        expect("clean point among bad ones", found[4], [])
        expect("duplicate flagged in the list", "duplicate" in [i["code"] for i in bad.issues["listIssues"]], True)
        expect("not clean", bad.clean, False)
        bad_score = writing_scoring.score_points(booking, bad.points, bad.issues["perPoint"])
        expect("invention counted by code", (bad_score["invented"], bad_score["inventionRate"]), (3, 0.6))
        expect("style counted separately", bad_score["stylePassRate"], 0.8)

        # --- "we built it" must not become "led it" ---
        Script.replies = [{"points": [point("Led the Flutter rebuild of the mobile app", "gt_k1")]}]
        grabbed = writer.write(team_facts, team["entry"])
        expect("leadership from a team fact is flagged", "ownership_not_in_facts" in [i["code"] for i in grabbed.issues["perPoint"][0]], True)
        hits = writing_scoring.score_points(team, grabbed.points, grabbed.issues["perPoint"])["forbidden"]
        expect("and counted against the story", hits, [{"point": 0, "term": "led"}])
        Script.replies = [{"points": [point("Rebuilt the mobile app in Flutter as part of a six-person team", "gt_k1", "gt_k2")]}]
        honest = writer.write(team_facts, team["entry"])
        expect("team phrasing passes", honest.clean, True)

        # --- repair: the model sees the exact complaint, only that point is rewritten ---
        Script.replies, Script.seen = [{"points": [point("Reduced double bookings after locking slots", "gt_k3", "gt_k4")]}], []
        complaint = [{"code": "number_not_in_facts", "message": "Number not in the cited facts: 90."}]
        fixed = writer.repair_point(point("Cut double bookings by 90%", "gt_k4"), complaint, booking_facts, booking["entry"])
        sent = Script.seen[0][-1]["content"]
        expect("repair shows the point and the complaint", ("Cut double bookings by 90%" in sent, "Number not in the cited facts: 90." in sent), (True, True))
        expect("repair also gets the facts", "[gt_k4]" in Script.seen[0][1]["content"], True)
        expect("repaired point is clean", (fixed.ok, fixed.clean, len(fixed.points)), (True, True, 1))

        # --- unusable replies are failed steps ---
        Script.replies = ["not json", "still not json"]
        failed = writer.write(booking_facts, booking["entry"])
        expect("garbage reply", (failed.ok, failed.points, bool(failed.error), failed.clean), (False, [], True, False))
        Script.replies = [{"points": [{"content": "   ", "supportedBy": ["gt_k1"]}]}]
        blank = writer.write(booking_facts, booking["entry"])
        expect("blank points are dropped, an empty draft is flagged",
               (blank.points, [i["code"] for i in blank.issues["listIssues"]]), ([], ["no_points"]))
    finally:
        models.ADAPTERS["openai"] = real_adapter

    # --- ground truth facts and the summary maths ---
    expect("one ground-truth fact per phrase", len(booking_facts), len(booking["mustCapture"]))
    expect("ground-truth facts are grounded", rules_kept_all(booking), True)
    mixed = writing_scoring.summarize_points([
        {"points": 3, "invented": 0, "stylePassRate": 1.0, "forbidden": []},
        {"points": 1, "invented": 1, "stylePassRate": 0.0, "forbidden": [{"point": 0, "term": "x"}]},
    ])
    expect("rates are over all points", (mixed["points"], mixed["inventionRate"], mixed["stylePassRate"], mixed["forbiddenHits"]), (4, 0.25, 0.75, 1))
    expect("prompt version", len(writer.PROMPT_VERSION), 8)

    ok = not problems
    print(f"writer: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_checker() -> bool:
    import writing_scoring
    from writing import checker, models

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    facts = [
        {"id": "f1", "content": "Added a cache in front of the search endpoint", "owner": "me"},
        {"id": "f2", "content": "The team migrated the database to Postgres", "owner": "team"},
    ]
    points = [
        {"content": "Added a cache in front of the search endpoint", "supportedBy": ["f1"]},
        {"content": "Added a cache in front of the search endpoint, improving search performance for all users", "supportedBy": ["f1"]},
        {"content": "Moved the database to MySQL", "supportedBy": ["f2"]},
    ]

    class Script:
        replies: list = []
        seen: list = []
        failures: list = []

        def complete(self, model, messages, temperature):
            Script.seen.append((messages, temperature))
            if Script.failures:
                raise Script.failures.pop(0)
            reply = Script.replies.pop(0)
            return (json.dumps(reply) if not isinstance(reply, str) else reply), 90, 60

    def verdict(index, kind, offending=(), reason="r"):
        return {"index": index, "verdict": kind, "offending": list(offending), "reason": reason}

    saved_env = {k: os.environ.pop(k, None) for k in ("CHECKER_MODEL", "ANALYST_MODEL", "WRITER_MODEL")}
    real_adapter = models.ADAPTERS["openai"]
    models.ADAPTERS["openai"] = Script
    try:
        # --- what the model is shown, and the low temperature ---
        Script.replies, Script.seen = [{"verdicts": [verdict(0, "backed"), verdict(1, "overstated", ["for all users"]), verdict(2, "unsupported", ["MySQL"])]}], []
        review = checker.check(points, facts)
        messages, temperature = Script.seen[0]
        expect("instructions", "You are the checker" in messages[0]["content"], True)
        expect("facts and points shown with citations",
               ("[f1] (owner: me) Added a cache" in messages[1]["content"], "1: Added a cache in front of the search endpoint, improving search performance for all users  (cites: f1)" in messages[1]["content"]),
               (True, True))
        expect("checker runs at temperature 0", temperature, 0.0)

        # --- a normal review ---
        expect("review ok", (review.ok, [v["verdict"] for v in review.verdicts]), (True, ["backed", "overstated", "unsupported"]))
        expect("offending words kept", [v["offending"] for v in review.verdicts], [[], ["for all users"], ["MySQL"]])
        expect("all located", all(v["located"] for v in review.verdicts), True)
        expect("one request for all points", len(Script.seen), 1)

        # --- the model's words are checked before they are believed ---
        Script.replies = [{"verdicts": [verdict(0, "backed"), verdict(1, "overstated", ["enterprise scale", "FOR ALL USERS"]), verdict(2, "OVERSTATED", ["Postgres is wrong"])]}]
        careful = checker.check(points, facts)
        expect("invented offending words are ignored", [v["offending"] for v in careful.verdicts], [[], ["FOR ALL USERS"], []])
        expect("verdict kept but marked as not located", [v["located"] for v in careful.verdicts], [True, True, False])
        expect("verdict words are tidied", careful.verdicts[2]["verdict"], "overstated")

        # --- a reply that does not cover the points is a failed step ---
        for label, bad in (
            ("missing verdict", {"verdicts": [verdict(0, "backed"), verdict(1, "backed")]}),
            ("repeated index", {"verdicts": [verdict(0, "backed"), verdict(0, "backed"), verdict(1, "backed"), verdict(2, "backed")]}),
            ("index out of range", {"verdicts": [verdict(0, "backed"), verdict(1, "backed"), verdict(5, "backed")]}),
            ("unknown verdict", {"verdicts": [verdict(0, "backed"), verdict(1, "great"), verdict(2, "backed")]}),
            ("wrong shape", {"nothing": 1}),
        ):
            Script.replies = [bad, bad]
            failed = checker.check(points, facts)
            expect(label, (failed.ok, failed.verdicts, bool(failed.error)), (False, [], True))
        Script.replies = ["not json", "not json"]
        expect("garbage", checker.check(points, facts).ok, False)

        # --- the checker can only tighten ---
        flagged = [[], [], [{"code": "tool_not_in_facts", "message": "\"MySQL\" is not in the cited facts."}]]
        Script.replies = [{"verdicts": [verdict(0, "backed"), verdict(1, "backed"), verdict(2, "backed")]}]
        floor = checker.check(points, facts, flagged)
        expect("a rule-flagged point cannot be cleared", [v["final"] for v in floor.verdicts], ["backed", "backed", "overstated"])
        expect("the checker's own verdict is kept visible", floor.verdicts[2]["verdict"], "backed")
        expect("the reason comes from the rule", floor.verdicts[2]["reason"], "\"MySQL\" is not in the cited facts.")
        Script.replies = [{"verdicts": [verdict(0, "backed"), verdict(1, "overstated", ["for all users"]), verdict(2, "backed")]}]
        style_only = checker.check(points, facts, [[{"code": "weak_start", "message": "m"}], [], []])
        expect("a style issue does not stop a backed verdict", style_only.verdicts[0]["final"], "backed")
        expect("checker can still add a problem", style_only.verdicts[1]["final"], "overstated")

        # --- temperature: set for steady jobs, dropped automatically if a model refuses it ---
        Script.replies, Script.seen = [{"facts": []}], []
        models.complete_json("analyst", [], analyst_shape())
        expect("analyst at a low temperature", Script.seen[0][1], 0.2)
        Script.replies, Script.seen = [{"facts": []}], []
        models.complete_json("writer", [], analyst_shape())
        expect("writer at the model default", Script.seen[0][1], None)
        Script.replies, Script.seen = [{"facts": []}], []
        Script.failures = [RuntimeError("Unsupported value: 'temperature' does not support 0.2")]
        refused = models.complete_json("analyst", [], analyst_shape())
        expect("refused temperature is dropped and asked again", (refused.ok, refused.attempts, [t for _m, t in Script.seen]), (True, 1, [0.2, None]))
        Script.replies, Script.seen = [{"facts": []}], []
        Script.failures = [RuntimeError("service down")]
        expect("other errors still fail the step", models.complete_json("analyst", [], analyst_shape()).ok, False)

        # --- scoring the checker on the real trap set, with three fake checkers ---
        traps = writing_scoring.load_traps(ROOT / "evals" / "writing" / "traps.json")
        label_of = {t["point"]: t["label"] for t in traps}

        def fake(decide):
            def check_fn(pts, fcts, issues):
                kind = decide(label_of[pts[0]["content"]])
                return checker.Review(ok=True, verdicts=[{"verdict": kind}])
            return check_fn

        blind = writing_scoring.score_checker(writing_scoring.trap_rows(traps, fake(lambda l: "backed")))
        expect("rules alone catch 4 of 6", (blind["exaggerated"], blind["caughtByRules"], blind["caughtByEither"]), (6, 0.667, 0.667))
        expect("blind checker adds nothing", blind["caughtByChecker"], 0.0)
        expect("the two known gaps get through", sorted(blind["missedByBoth"]), ["t5_overstated_scope", "t6_unstated_result"])
        expect("rules wrongly reject no honest point", blind["wronglyRejectedByRules"], 0.0)
        sharp = writing_scoring.score_checker(writing_scoring.trap_rows(traps, fake(lambda l: "backed" if l == "honest" else "overstated")))
        expect("sharp checker closes the gaps", (sharp["caughtByChecker"], sharp["caughtByEither"], sharp["missedByBoth"], sharp["wronglyRejectedByEither"]), (1.0, 1.0, [], 0.0))
        paranoid = writing_scoring.score_checker(writing_scoring.trap_rows(traps, fake(lambda l: "overstated")))
        expect("paranoid checker catches all but rejects honest points", (paranoid["caughtByEither"], paranoid["wronglyRejectedByChecker"], paranoid["wronglyRejectedByEither"]), (1.0, 1.0, 1.0))
        broken = writing_scoring.score_checker(writing_scoring.trap_rows(traps, lambda p, f, i: checker.Review(ok=False)))
        expect("failed checker steps are counted", broken["checkerFailedSteps"], 12)
        expect("and the rules still stand alone", broken["caughtByEither"], 0.667)
    finally:
        models.ADAPTERS["openai"] = real_adapter
        for key, value in saved_env.items():
            if value is not None:
                os.environ[key] = value

    expect("prompt version", len(checker.PROMPT_VERSION), 8)
    ok = not problems
    print(f"checker: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_pipeline() -> bool:
    import writing_scoring
    from writing import models, pipeline

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    case = json.loads((ROOT / "evals" / "writing" / "cases" / "rambling_product.json").read_text())
    story, entry = case["story"], case["entry"]

    class Team:
        """A fake model that tells the three jobs apart and replays scripted replies."""

        analyst: list = []
        writer: list = []
        repair: list = []
        checker: list = []
        calls: list = []

        def complete(self, model, messages, temperature):
            system, user = messages[0]["content"], messages[-1]["content"]
            job = ("analyst" if "You are the analyst" in system else
                   "checker" if "You are the checker" in system else "writer")
            if job == "writer" and user.startswith("Fix this one point."):
                job = "repair"
            Team.calls.append(job)
            queue = getattr(Team, job)
            reply = queue.pop(0) if queue else Team.default(job, messages)
            return (json.dumps(reply) if not isinstance(reply, str) else reply), 100, 50

        @staticmethod
        def default(job, messages):
            if job == "checker":
                count = len(re.findall(r"^\d+:", messages[-1]["content"], flags=re.M))
                return {"verdicts": [{"index": i, "verdict": "backed", "offending": [], "reason": "ok"} for i in range(count)]}
            raise AssertionError(f"no scripted reply for {job}")

    def analyst_reply(picks=None):
        picks = case["mustCapture"] if picks is None else picks
        return {"facts": [{"content": k["phrase"], "kind": k["kind"], "owner": k["owner"], "quote": k["phrase"]} for k in picks], "missing": ["How many salons?"]}

    def fact_ids():
        # The analyst's fact ids come from the story and the quotes, so they are known in
        # advance. Scripted writer replies cite them.
        from writing import analyst as analyst_module
        from writing import rules

        kept, _ = rules.check_facts(analyst_reply()["facts"], story)
        return [analyst_module._fact_id(f) for f in kept]

    def run(**scripts):
        for name in ("analyst", "writer", "repair", "checker"):
            setattr(Team, name, list(scripts.get(name, [])))
        Team.calls = []
        return pipeline.run_pipeline(story, entry)

    def pt(content, *indexes):
        return {"content": content, "supportedBy": [Team.last_ids[i] for i in indexes]}

    def ok_verdicts(count, overrides=None):
        overrides = overrides or {}
        return {"verdicts": [
            overrides.get(i, {"index": i, "verdict": "backed", "offending": [], "reason": "ok"})
            for i in range(count)
        ]}

    def counts():
        return {job: Team.calls.count(job) for job in ("analyst", "writer", "repair", "checker")}

    real_adapter = models.ADAPTERS["openai"]
    models.ADAPTERS["openai"] = Team
    try:
        Team.last_ids = fact_ids()
        clean_points = lambda: [pt("Built the booking page in React", 0), pt("Fixed double bookings by locking the slot during checkout", 2), pt("Stopped the angry emails about double bookings", 3)]

        # --- a clean run: three calls, everything supported ---
        r = run(analyst=[analyst_reply()], writer=[{"points": clean_points()}])
        expect("clean run", (r.ok, r.stage, [p["status"] for p in r.points]), (True, "done", ["supported"] * 3))
        expect("clean run uses one call per job", counts(), {"analyst": 1, "writer": 1, "repair": 0, "checker": 1})
        expect("points cite real fact ids", all(f in {x["id"] for x in r.facts} for p in r.points for f in p["supportedBy"]), True)
        expect("follow-up question passed along", r.missing, ["How many salons?"])
        expect("run record totals", (r.totals["steps"], r.totals["inputTokens"], r.totals["unpricedSteps"]), (3, 300, 0))
        expect("cost is counted", r.totals["costUsd"] > 0, True)
        expect("prompt versions recorded", sorted(r.prompt_versions), ["analyst", "checker", "writer"])
        expect("points have no ids yet and are marked ai", all("id" not in p and p["origin"] == "ai" and not p["fallback"] for p in r.points), True)

        # --- the rules catch an invented number; one repair fixes it ---
        bad = clean_points(); bad[2] = pt("Cut double bookings by 90%", 3)
        r = run(analyst=[analyst_reply()], writer=[{"points": bad}],
                repair=[{"points": [pt("Stopped the angry emails about double bookings", 3)]}])
        expect("repaired", [p["status"] for p in r.points], ["supported"] * 3)
        expect("one repair, two checker calls", counts(), {"analyst": 1, "writer": 1, "repair": 1, "checker": 2})

        # --- the checker catches what code cannot; repair fixes it ---
        gap = clean_points(); gap[1] = pt("Fixed double bookings, improving booking performance for all users", 2)
        r = run(analyst=[analyst_reply()], writer=[{"points": gap}],
                checker=[ok_verdicts(3, {1: {"index": 1, "verdict": "overstated", "offending": ["for all users"], "reason": "no result stated"}})],
                repair=[{"points": [pt("Fixed double bookings by locking the slot during checkout", 2)]}])
        expect("checker complaint repaired", [p["status"] for p in r.points], ["supported"] * 3)
        expect("repair prompt carried the checker's complaint", counts()["repair"], 1)

        # --- never fixed: two repair rounds, then a plain safe point marked for review ---
        stubborn = [{"points": [pt("Built the booking page in React and Kafka", 0)]}] * 2
        r = run(analyst=[analyst_reply()], writer=[{"points": [pt("Built the booking page in React and Kafka", 0), pt("Fixed double bookings by locking the slot during checkout", 2)]}], repair=stubborn)
        expect("fallback point", [(p["content"], p["status"], p["fallback"]) for p in r.points],
               [("Built the booking page in React", "needs_review", True), ("Fixed double bookings by locking the slot during checkout", "supported", False)])
        expect("fallback keeps the original complaint", [i["code"] for i in r.points[0]["issues"]], ["tool_not_in_facts"])
        expect("at most two repair rounds", (counts()["repair"], counts()["checker"]), (2, 3))

        # --- no safe version possible: the point is left out and recorded ---
        r = run(analyst=[analyst_reply()], writer=[{"points": [pt("Built the whole stack with Kafka", 1)]}],
                repair=[{"points": [pt("Built the whole stack with Kafka", 1)]}] * 2)
        expect("unfixable point is dropped", (r.points, [d["reason"] for d in r.dropped_points]), ([], ["no safe version could be built from its fact"]))

        # --- the checker is down: points are unchecked, never supported ---
        r = run(analyst=[analyst_reply()], writer=[{"points": clean_points()}], checker=["garbage", "garbage"])
        expect("unchecked", [p["status"] for p in r.points], ["unchecked"] * 3)
        expect("and says why", r.points[0]["issues"][0]["code"], "checker_unavailable")
        expect("a failed checker does not trigger repairs", counts()["repair"], 0)

        # --- earlier stages failing ---
        r = run(analyst=["garbage", "garbage"])
        expect("analyst fails", (r.ok, r.stage, r.points, counts()["writer"]), (False, "analyst", [], 0))
        r = run(analyst=[{"facts": [], "missing": ["What did you build?", "Who used it?"]}])
        expect("nothing to write from", (r.ok, r.stage, counts()["writer"], r.missing), (True, "no_facts", 0, ["What did you build?", "Who used it?"]))
        r = run(analyst=[analyst_reply()], writer=["garbage", "garbage"])
        expect("writer fails", (r.ok, r.stage, counts()["checker"]), (False, "writer", 0))
        r = run(analyst=[analyst_reply()], writer=[{"points": []}])
        expect("writer writes nothing", (r.ok, r.stage), (False, "writer"))

        # --- the list is tidied by code: repeats and extras never reach the checker ---
        many = [pt(f"Built booking page number {n} in React", 0) for n in range(7)] + [pt("Built booking page number 0 in React", 0)]
        r = run(analyst=[analyst_reply()], writer=[{"points": many}])
        expect("capped at five", len(r.points), 5)
        expect("repeats and extras recorded", sorted(d["reason"] for d in r.dropped_points), ["more than the limit", "more than the limit", "repeated point"])

        # --- guards: refused before any model is called ---
        for label, text in (("empty story", "   "), ("too long", "x" * (pipeline.MAX_STORY_CHARS + 1))):
            Team.calls = []
            r = pipeline.run_pipeline([{"id": "c1", "text": text}], entry)
            expect(label, (r.ok, r.stage, Team.calls, bool(r.error)), (False, "guard", [], True))

        # --- the number of calls is bounded however badly the model behaves ---
        worst_writer = {"points": [pt(f"Built booking page number {n} in React and Kafka", 0) for n in range(5)]}
        r = run(analyst=[analyst_reply()], writer=[worst_writer],
                repair=[{"points": [pt("Built booking page again in React and Kafka", 0)]}] * 10,
                checker=[ok_verdicts(5, {i: {"index": i, "verdict": "overstated", "offending": [], "reason": "x"} for i in range(5)})] * 3)
        calls = counts()
        expect("bounded calls", (calls["analyst"], calls["writer"], calls["checker"] <= 3, calls["repair"] <= 5 * pipeline.MAX_REPAIR_ROUNDS), (1, 1, True, True))
        expect("worst case still ends cleanly", r.ok, True)

        # --- plain points ---
        expect("plain point", (pipeline.plain_point({"content": "I built the booking page in React."}), pipeline.plain_point({"content": "We've moved to Postgres"})), ("Built the booking page in React", "Moved to Postgres"))
    finally:
        models.ADAPTERS["openai"] = real_adapter

    ok = not problems
    print(f"pipeline: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def test_writing_report() -> bool:
    import run_writing_evals as report_tool
    import writing_baseline
    import writing_scoring
    from writing import analyst as analyst_module
    from writing import models, rules

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    cases = {c["id"]: c for c in report_tool.load_cases()}
    two = [cases["rambling_product"], cases["we_versus_i_team"]]
    traps = writing_scoring.load_traps(ROOT / "evals" / "writing" / "traps.json")
    label_of = {t["point"]: t["label"] for t in traps}

    # What each fake team writes: hand-made honest points for the two stories.
    def ids(case):
        kept, _ = rules.check_facts(
            [{"content": k["phrase"], "kind": k["kind"], "owner": k["owner"], "quote": k["phrase"]} for k in case["mustCapture"]],
            case["story"])
        return [analyst_module._fact_id(f) for f in kept]

    honest = {
        "rambling_product": [
            ("Built the booking page in React", [0]),
            ("Fixed double bookings by locking the slot during checkout", [2]),
            ("Stopped the angry emails about double bookings", [3]),
        ],
        "we_versus_i_team": [
            ("Rebuilt the mobile app in Flutter as part of a six-person team", [0, 1]),
            ("Developed the login and onboarding screens", [2]),
            ("Wrote the tests for the login and onboarding screens", [3]),
        ],
    }

    class Team:
        mode = "honest"  # or "inventive"

        def complete(self, model, messages, temperature):
            system, user = messages[0]["content"], messages[-1]["content"]
            case = next(c for c in two if c["story"][0]["text"][:40] in messages[1]["content"]) if "STORY:" in messages[1]["content"] else Team.current
            Team.current = case
            if "You are the analyst" in system:
                reply = {"facts": [{"content": k["phrase"], "kind": k["kind"], "owner": k["owner"], "quote": k["phrase"]} for k in case["mustCapture"]], "missing": ["How big was it?"]}
            elif "You are the checker" in system:
                count = len(re.findall(r"^\d+:", user, flags=re.M))
                reply = {"verdicts": [{"index": i, "verdict": "backed", "offending": [], "reason": "ok"} for i in range(count)]}
                if "FACTS:" in user and count == 1 and user.count("\n") < 6 and Team.trap:
                    kind = "backed" if label_of.get(Team.trap_point(user)) == "honest" else "overstated"
                    reply["verdicts"][0]["verdict"] = kind
                    if kind != "backed":
                        reply["verdicts"][0]["offending"] = []
            else:  # writer or repair
                if Team.mode == "inventive":
                    texts = [(p + " with Kafka", c) for p, c in honest[case["id"]]]
                else:
                    texts = honest[case["id"]]
                fact_ids = ids(case)
                reply = {"points": [{"content": t, "supportedBy": [fact_ids[i] for i in cites]} for t, cites in texts]}
                if user.startswith("Fix this one point."):
                    reply = {"points": reply["points"][:1]}
            return json.dumps(reply), 100, 50

        current = None
        trap = False

        @staticmethod
        def trap_point(user):
            # An honest trap point is a prefix of its exaggerated twin, so take the longest match.
            return max((p for p in label_of if p in user), key=len, default="")

    class Tidy:
        """A fake of today's one-pass tidy-up that sometimes invents."""
        class responses:
            @staticmethod
            def create(**_kwargs):
                class Out:
                    output_text = json.dumps({"bullets": ["Built the booking page in React", "Cut double bookings by 90% using Redis"]})
                return Out()

    import enrichment
    real_adapter, real_client = models.ADAPTERS["openai"], enrichment.client
    models.ADAPTERS["openai"] = Team
    enrichment.client = Tidy
    saved_env = {k: os.environ.pop(k, None) for k in ("ANALYST_MODEL", "WRITER_MODEL", "CHECKER_MODEL")}
    try:
        # --- nothing is read at import; main() is what loads settings ---
        source = (ROOT / "evals" / "run_writing_evals.py").read_text()
        inside_main = ast.get_source_segment(source, next(
            n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "main"))
        outside_main = source.replace(inside_main, "")
        expect("settings are loaded only inside main()", ("load_dotenv(" in inside_main, "load_dotenv(" in outside_main.replace("`", "")), (True, False))
        expect("estimate-only by default", (report_tool.parse_args([]).yes, report_tool.parse_args(["--yes"]).yes), (False, True))
        try:
            report_tool.parse_args(["--runs", "0"])
            problems.append("zero runs accepted")
        except SystemExit:
            pass

        # --- a whole honest run, three times over ---
        Team.mode = "honest"
        report = report_tool.evaluate(two, [], runs=3)
        json.dumps(report)  # must be storable
        expect("stories and runs recorded", (report["meta"]["runs"], report["meta"]["stories"]), (3, ["rambling_product", "we_versus_i_team"]))
        expect("models and prompt versions recorded", (sorted(report["meta"]["models"]), sorted(report["meta"]["promptVersions"])), (["analyst", "checker", "writer"], ["analyst", "checker", "writer"]))
        expect("analyst finds everything", (report["analyst"]["recall"]["mean"], report["analyst"]["ownerRight"]["mean"]), (1.0, 1.0))
        expect("honest team invents nothing", (report["team"]["inventionRate"]["mean"], report["team"]["inventionRateVsStory"]["mean"], report["team"]["forbiddenHits"]["mean"]), (0.0, 0.0, 0.0))
        expect("all points supported, none fell back", (report["team"]["supportedRate"]["mean"], report["team"]["fallbackRate"]["mean"], report["team"]["failedStories"]["mean"]), (1.0, 0.0, 0))
        expect("mean, lowest and highest", sorted(report["team"]["supportedRate"]), ["max", "mean", "min"])
        expect("cost per entry is priced", (report["cost"]["usdPerEntry"]["mean"] > 0, report["cost"]["unpricedSteps"]["mean"]), (True, 0))
        expect("follow-up questions laid beside what was expected", report["followUps"][0], {"story": "rambling_product", "asked": ["How big was it?"], "shouldAskAbout": cases["rambling_product"]["missing"]})
        expect("per-story figures", [s["story"] for s in report["perStory"]], ["rambling_product", "we_versus_i_team"])
        expect("sample points kept", report["samplePoints"]["we_versus_i_team"][0], "Rebuilt the mobile app in Flutter as part of a six-person team")

        # --- today's tidy-up, judged by the same yardstick, invents ---
        base = report["baseline"]
        # The fake tidy-up gives both stories the same two bullets. On the booking story one of
        # them invents "90%" and "Redis"; on the Flutter story neither bullet comes from the story.
        expect("baseline invents (3 of 4 points have words the story never said)", base["inventionRateVsStory"]["mean"], 0.75)
        expect("baseline is not costed", "not measured" in base["cost"], True)
        expect("baseline can be skipped", report_tool.evaluate(two, [], runs=1, with_baseline=False)["baseline"], None)
        expect("baseline sentences", writing_baseline.sentences(cases["very_short"]["story"]), ["Built a REST API in Django."])

        # --- an inventive writer: repairs fail, the plain fallback keeps the stored points honest ---
        Team.mode = "inventive"
        sloppy = report_tool.evaluate(two, [], runs=1, with_baseline=False)
        expect("fallback used", sloppy["team"]["fallbackRate"]["mean"] > 0, True)
        expect("final points still invent nothing", sloppy["team"]["inventionRate"]["mean"], 0.0)
        expect("but they need review", sloppy["team"]["needsReviewRate"]["mean"] > 0, True)
        expect("repairs happen", sloppy["team"]["repairCallsPerStory"]["mean"] > 0, True)
        Team.mode = "honest"

        # --- the checker on the traps, through the same code ---
        Team.trap = True
        with_traps = report_tool.evaluate(two, traps, runs=2, with_baseline=False)
        Team.trap = False
        chk = with_traps["checker"]
        expect("rules alone catch 4 of 6", chk["caughtByRules"]["mean"], 0.667)
        expect("a checker that spots the rest closes the gap", (chk["caughtByEither"]["mean"], chk["wronglyRejectedByEither"]["mean"]), (1.0, 0.0))
        expect("no honest point wrongly rejected", chk["wronglyRejectedByChecker"]["mean"], 0.0)
        expect("nothing missed", chk["missedByBoth"], [])

        # --- the regression gate ---
        a = {"team": {"inventionRate": {"mean": 0.0}, "inventionRateVsStory": {"mean": 0.0}, "forbiddenHits": {"mean": 0.0}}}
        b = {"team": {"inventionRate": {"mean": 0.1}, "inventionRateVsStory": {"mean": 0.0}, "forbiddenHits": {"mean": 1.0}}}
        expect("worse invention is flagged", len(report_tool.compare(b, a)), 2)
        expect("same is fine", report_tool.compare(a, a), [])
        expect("better is fine", report_tool.compare(a, b), [])
        expect("tolerance allows noise", report_tool.compare({"team": {**b["team"], "forbiddenHits": {"mean": 0.0}}}, a, tolerance=0.1), [])
        expect("missing figures are not a regression", report_tool.compare({"team": {}}, a), [])

        # --- the estimate says what a run would cost before it is made ---
        plan = report_tool.estimate(list(cases.values()), traps, runs=3)
        expect("estimate", (plan["calls"] > 0, plan["costUsd"] is not None and 0 < plan["costUsd"] < 5), (True, True))
        unpriced = os.environ.get("WRITER_MODEL")
        os.environ["WRITER_MODEL"] = "openai:model-with-no-price"
        try:
            expect("an unpriced model is admitted", report_tool.estimate(two, traps, 1)["costUsd"], None)
        finally:
            os.environ.pop("WRITER_MODEL", None)
            if unpriced:
                os.environ["WRITER_MODEL"] = unpriced
        expect("stats ignore missing figures", report_tool.stats([1.0, None, 3.0]), {"mean": 2.0, "min": 1.0, "max": 3.0})
        expect("stats of nothing", report_tool.stats([None]), None)
    finally:
        models.ADAPTERS["openai"] = real_adapter
        enrichment.client = real_client
        for key, value in saved_env.items():
            if value is not None:
                os.environ[key] = value

    ok = not problems
    print(f"writing_report: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def _written_result(second_status="needs_review", missing=()):
    """A finished PipelineResult, as the writing team would hand it to be stored."""
    from writing import models, pipeline, records

    run = records.Run("writing team: test")
    run.add(
        models.Result(ok=True, job="writer", provider="openai", model="gpt-4.1-mini",
                      input_tokens=10, output_tokens=5, replies=["write to sam@example.com"]),
        [{"role": "user", "content": "mail sam@example.com"}], name="writer",
    )
    return pipeline.PipelineResult(
        ok=True, stage="done", run=run, missing=list(missing),
        prompt_versions={"analyst": "a", "writer": "w", "checker": "c"},
        facts=[{"id": "fact_a", "content": "Built the booking page in React",
                "kind": "action", "owner": "me",
                "quote": "I built the booking page in React", "storyId": "s1"}],
        points=[
            {"content": "Built the booking page in React", "supportedBy": ["fact_a"],
             "status": "supported", "issues": [], "origin": "ai", "fallback": False},
            {"content": "Fixed double bookings", "supportedBy": ["fact_a"],
             "status": second_status,
             "issues": [] if second_status == "supported" else [{"code": "x", "message": "m"}],
             "origin": "ai", "fallback": second_status != "supported"},
        ],
    )


def _with_story(payload: dict, text: str, item_id: str = "exp_chaishots") -> dict:
    payload = json.loads(json.dumps(payload))
    for item in payload["inventory"]["sections"]["experience"]["items"]:
        if item["id"] == item_id:
            item["story"] = [{"id": "s1", "text": text, "source": "typed", "at": None}]
    return payload


def test_rewrite_storing() -> bool:
    from datetime import datetime, timezone

    from claims import points_for_item, set_item_points
    from facts import add_fact
    from writing import store

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    when = datetime(2026, 10, 27, tzinfo=timezone.utc)
    base = update_basics_verified(_with_project(load_fixture("sample_career.json")))
    base = _with_story(base, "I built the booking page in React. Fixed the double bookings.")
    base = add_fact(base, "A fact the person typed", section="experience", item_id="exp_chaishots")
    other_before = [p for p in base["claims"] if p.get("itemId") == "exp_hyrefox"]

    result = _written_result()
    stored = store.apply_result(base, "experience", "exp_chaishots", result, now=when)
    points = points_for_item(stored, "experience", "exp_chaishots")
    expect("points replaced by the checked ones", [(p["content"], p["status"], p["origin"]) for p in points],
           [("Built the booking page in React", "supported", "ai"), ("Fixed double bookings", "needs_review", "ai")])
    expect("points cite their facts", [p["supportedBy"] for p in points], [["fact_a"], ["fact_a"]])
    expect("issues kept on the point", [i["code"] for i in points[1]["issues"]], ["x"])
    expect("bullets copy follows the points", _copies_out_of_step(stored), [])
    ai_facts = [f for f in stored["facts"] if f["source"] == "ai"]
    expect("ai fact stored with labels", [(f["id"], f["kind"], f["owner"], f["quote"], f["storyId"]) for f in ai_facts],
           [("fact_a", "action", "me", "I built the booking page in React", "s1")])
    expect("the person's own fact is kept", any(f["content"] == "A fact the person typed" for f in stored["facts"]), True)
    expect("other entries untouched", [p for p in stored["claims"] if p.get("itemId") == "exp_hyrefox"], other_before)
    item = next(i for i in stored["inventory"]["sections"]["experience"]["items"] if i["id"] == "exp_chaishots")
    expect("writing marker", (item["writing"]["status"], item["writing"]["storyFingerprint"], item["writing"]["lastRunAt"]),
           ("needs_review", store.story_fingerprint(item["story"]), when.isoformat()))
    # The save door normalizes before storing, so a stored record is a normalized one.
    saved_form = normalize_payload(stored)
    expect("stable once saved and reloaded", normalize_payload(saved_form), saved_form)
    expect("saving loses no point", sorted(p["id"] for p in saved_form["claims"]), sorted(p["id"] for p in stored["claims"]))

    again = store.apply_result(stored, "experience", "exp_chaishots", result, now=when)
    expect("applying twice changes nothing", again, stored)
    expect("no duplicate facts", len([f for f in again["facts"] if f["source"] == "ai"]), 1)

    questioned = store.apply_result(base, "experience", "exp_chaishots", _written_result("supported", ["How many bookings?"]), now=when)
    qitem = next(i for i in questioned["inventory"]["sections"]["experience"]["items"] if i["id"] == "exp_chaishots")
    expect("all supported means ready", qitem["writing"]["status"], "ready")
    expect("questions stored", [q["text"] for q in qitem["writing"]["questions"]], ["How many bookings?"])

    # --- already written, and when the story changes ---
    _item, level = store.find_level(stored, "experience", "exp_chaishots")
    expect("unchanged story is already written", store.already_written(stored, "experience", "exp_chaishots", level), True)
    edited = _with_story(stored, "A completely different story")
    _item, level2 = store.find_level(edited, "experience", "exp_chaishots")
    expect("changed story is not", store.already_written(edited, "experience", "exp_chaishots", level2), False)
    _item, level0 = store.find_level(base, "experience", "exp_chaishots")
    expect("never written is not", store.already_written(base, "experience", "exp_chaishots", level0), False)

    # --- the person's own points are protected ---
    mine = set_item_points(base, "experience", "exp_chaishots", ["I wrote this myself"], origin="user")
    expect("user points detected", len(store.user_edited_points(mine, "experience", "exp_chaishots")), 1)
    expect("ai points are not", store.user_edited_points(stored, "experience", "exp_chaishots"), [])

    # --- a project inside a job is written on its own ---
    inside = store.apply_result(base, "experience", "exp_chaishots", result, project_id="wp_rec", now=when)
    expect("project points", [p["content"] for p in points_for_item(inside, "experience", "exp_chaishots", "wp_rec")],
           ["Built the booking page in React", "Fixed double bookings"])
    expect("job-level points untouched", [p["content"] for p in points_for_item(inside, "experience", "exp_chaishots")],
           [p["content"] for p in points_for_item(base, "experience", "exp_chaishots")])
    expect("project facts are the project's", [f["context"]["projectId"] for f in inside["facts"] if f["source"] == "ai"], ["wp_rec"])
    expect("project copies in step", _copies_out_of_step(inside), [])

    # --- bad requests and bad results ---
    for label, call, kind in (
        ("unknown section", lambda: store.find_level(base, "nope", "x"), KeyError),
        ("unknown item", lambda: store.find_level(base, "experience", "nope"), KeyError),
        ("unknown project", lambda: store.find_level(base, "experience", "exp_chaishots", "nope"), KeyError),
        ("section without points", lambda: store.find_level(base, "education", "x"), ValueError),
        ("details length", lambda: set_item_points(base, "experience", "exp_chaishots", ["a", "b"], details=[{}]), ValueError),
        ("details status", lambda: set_item_points(base, "experience", "exp_chaishots", ["a"], details=[{"status": "great"}]), ValueError),
    ):
        expect(label, _raises(call, kind), True)
    failed = _written_result(); failed.ok = False
    expect("a failed result stores nothing", store.apply_result(base, "experience", "exp_chaishots", failed), base)
    empty = _written_result(); empty.points = []
    expect("a result without points stores nothing", store.apply_result(base, "experience", "exp_chaishots", empty), base)

    ok = not problems
    print(f"rewrite_storing: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def update_basics_verified(payload: dict) -> dict:
    from resume_ops import update_basics

    return update_basics(payload, {"fullName": "Sam", "email": "sam@example.com", "phone": "", "location": ""}, verify=True)


def test_rewrite_endpoint() -> bool:
    import main
    from fastapi import HTTPException
    from writing import pipeline, store

    problems: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            problems.append(f"{label}: got {got!r}, wanted {want!r}")

    class Db(_FakeCursor):
        """A scripted database: answers the endpoint's queries and records its writes."""

        def __init__(self, payload, latest=None, traces=0):
            super().__init__(version=4)
            self.payload, self.latest, self.traces = payload, latest, traces
            self.committed = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def cursor(self):
            return self

        def commit(self):
            self.committed += 1

        def execute(self, sql, params=()):
            text = " ".join(sql.split())
            if text.startswith("SELECT session_id, payload, version, user_id"):
                self.statements.append((text, params))
                self._row = ("s", self.payload, 4, None)
            elif text.startswith("SELECT count(*) FROM ai_traces"):
                self.statements.append((text, params))
                self._row = (self.traces,)
            elif text.startswith("INSERT INTO ai_traces"):
                self.statements.append((text, params))
                self._row = (7,)
            elif text.endswith("FOR UPDATE"):
                self.statements.append((text, params))
                self._row = ("s", self.latest or self.payload, 4)
            else:
                super().execute(sql, params)

    base = _with_story(
        update_basics_verified(_with_project(load_fixture("sample_career.json"))),
        "I built the booking page in React. Reach me at sam@example.com",
    )
    called: list = []

    def attempt(payload, result, latest=None, traces=0, **body):
        db = Db(payload, latest, traces)
        called.clear()

        def fake_pipeline(story, entry):
            called.append((story, entry))
            return result

        real = (main.psycopg.connect, main.get_current_user, main.writing_pipeline.run_pipeline)
        main.psycopg.connect = lambda *_a, **_k: db
        main.get_current_user = lambda request: None
        main.writing_pipeline.run_pipeline = fake_pipeline
        try:
            request = {"section": "experience", "itemId": "exp_chaishots", **body}
            try:
                return main.rewrite_entry("s", main.RewriteBody(**request), request=None), db
            except HTTPException as err:
                return err, db
        finally:
            main.psycopg.connect, main.get_current_user, main.writing_pipeline.run_pipeline = real

    def wrote(db):
        return len(db.ran("UPDATE resume_snapshots"))

    def traced(db):
        return db.ran("INSERT INTO ai_traces")

    # --- a normal rewrite ---
    out, db = attempt(base, _written_result())
    expect("success", (isinstance(out, dict), out.get("version") if isinstance(out, dict) else out), (True, 5))
    expect("model never got more than the entry's story and names",
           (called[0][0][0]["text"].startswith("I built"), called[0][1].get("company")), (True, "ChaiShots"))
    expect("saved once, through the door, with history", (wrote(db), [h[4] for h in db.ran("INSERT INTO career_versions")]),
           (1, ["Entry rewritten by the writing team"]))
    expect("undo copy kept", len(db.ran("INSERT INTO resume_undo")), 1)
    expect("row locked before writing", len([t for t, _ in db.statements if t.endswith("FOR UPDATE")]), 1)
    stored = json.loads(db.ran("UPDATE resume_snapshots")[0][0])
    expect("stored points", [(p["content"], p["status"]) for p in points_for_item(stored, "experience", "exp_chaishots")],
           [("Built the booking page in React", "supported"), ("Fixed double bookings", "needs_review")])
    expect("reply summarises", (out["rewrite"]["stage"], [p["status"] for p in out["rewrite"]["points"]]), ("done", ["supported", "needs_review"]))
    expect("one run record", len(traced(db)), 1)
    record = traced(db)[0]
    expect("run record type", record[1], "rewrite")
    expect("no contact details in the run record", "sam@example.com" in (record[2] or "") + record[3], False)
    expect("committed", db.committed >= 1, True)

    # --- unchanged story is skipped; force and a changed story run again ---
    written = store.apply_result(base, "experience", "exp_chaishots", _written_result())
    out, db = attempt(written, _written_result())
    expect("unchanged story skipped", (out.get("skipped"), called, traced(db), wrote(db)), (True, [], [], 0))
    out, db = attempt(written, _written_result(), force=True)
    expect("force runs again", (len(called), wrote(db)), (1, 1))

    # --- limits and refusals ---
    out, db = attempt(base, _written_result(), traces=pipeline.MAX_REWRITES_PER_HOUR)
    expect("hourly limit", (getattr(out, "status_code", None), called, wrote(db)), (429, [], 0))
    out, db = attempt(base, _written_result(), traces=pipeline.MAX_REWRITES_PER_HOUR - 1)
    expect("just under the limit runs", isinstance(out, dict), True)
    guard = pipeline.PipelineResult(ok=False, stage="guard", error="The story is empty.", run=_written_result().run)
    out, db = attempt(base, guard)
    expect("guard refusal: 400 and nothing recorded", (out.status_code, out.detail, traced(db), wrote(db)), (400, "The story is empty.", [], 0))
    mine = set_item_points_user(base)
    out, db = attempt(mine, _written_result())
    expect("the person's own points are protected", (out.status_code, called, wrote(db)), (409, [], 0))
    out, db = attempt(mine, _written_result(), replaceEdited=True)
    expect("unless they agree", (isinstance(out, dict), wrote(db)), (True, 1))
    out, db = attempt(base, _written_result(), itemId="nope")
    expect("unknown entry", out.status_code, 404)
    out, db = attempt(base, _written_result(), projectId="nope")
    expect("unknown project", out.status_code, 404)
    unverified = json.loads(json.dumps(base)); unverified["intake"]["basicsVerified"] = False; unverified["intake"]["basicsConfirmed"] = False
    out, db = attempt(unverified, _written_result())
    expect("details not confirmed", (out.status_code, called), (400, []))

    # --- the team fails, or has nothing to write ---
    failed = _written_result(); failed.ok, failed.stage, failed.error, failed.points = False, "analyst", "no key", []
    out, db = attempt(base, failed)
    expect("team failure: 502, spend recorded, nothing stored", (out.status_code, len(traced(db)), wrote(db), db.committed >= 1), (502, 1, 0, True))
    nothing = _written_result(missing=["What did you build?"]); nothing.stage, nothing.points, nothing.facts = "no_facts", [], []
    out, db = attempt(base, nothing)
    expect("no facts: questions returned, nothing stored", (out["rewrite"]["questions"], wrote(db), len(traced(db))), (["What did you build?"], 0, 1))

    # --- the entry changes while the team is writing ---
    out, db = attempt(base, _written_result(), latest=_with_story(base, "A different story, typed meanwhile"))
    expect("story changed meanwhile", (out.status_code, wrote(db), len(traced(db))), (409, 0, 1))
    out, db = attempt(base, _written_result(), latest=set_item_points_user(base))
    expect("person edited points meanwhile", (out.status_code, wrote(db)), (409, 0))

    ok = not problems
    print(f"rewrite_endpoint: {'PASS' if ok else 'FAIL'} (problems={problems})")
    return ok


def set_item_points_user(payload: dict) -> dict:
    from claims import set_item_points

    return set_item_points(payload, "experience", "exp_chaishots", ["I wrote this myself"], origin="user")


def analyst_shape():
    from pydantic import BaseModel

    class Shape(BaseModel):
        facts: list[dict]

    return Shape


def rules_kept_all(case: dict) -> bool:
    import writing_scoring
    from writing import rules

    kept, dropped = rules.check_facts(writing_scoring.ground_truth_facts(case), case["story"])
    return len(kept) == len(case["mustCapture"]) and not dropped


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
        test_model_switchboard,
        test_cost_and_run_records,
        test_writing_rules,
        test_writing_cases_valid,
        test_analyst,
        test_writer,
        test_checker,
        test_pipeline,
        test_writing_report,
        test_rewrite_storing,
        test_rewrite_endpoint,
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
        test_voice_can_end_call,
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
