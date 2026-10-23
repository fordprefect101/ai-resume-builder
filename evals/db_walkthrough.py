#!/usr/bin/env python3
"""
Walk through phase 1 against a real Postgres.

It creates a fresh, separate database (resume_builder_test) on the same server as
DATABASE_URL in api/.env, so real data is never touched. It then starts the API
in-process on that database and drives it with real requests: create a resume,
confirm details, set skills, add entries, hide/show, reorder, undo, history,
restore, raw save, finish setup. After each step it checks the stored record.

Needs the database from docker-compose.yml running. Makes two small paid AI calls
(the tidy-up on one add-entry, as the voice assistant does) unless --no-ai.

    python evals/db_walkthrough.py [--no-ai]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
TEST_DB = "resume_builder_test"
EXPECTED_TABLES = {
    "resume_snapshots",
    "resume_undo",
    "users",
    "auth_sessions",
    "email_tokens",
    "career_versions",
    "ai_traces",
}

results: list[tuple[str, bool, str]] = []
requests_sent = 0


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    return ok


def database_urls() -> tuple[str, str]:
    """(test database URL, maintenance database URL) on the server in api/.env."""
    from dotenv import dotenv_values

    real = dotenv_values(API / ".env").get("DATABASE_URL") or ""
    parsed = urlparse(real)
    if not parsed.hostname:
        sys.exit("DATABASE_URL is missing from api/.env")
    if parsed.path.lstrip("/") == TEST_DB:
        sys.exit(f"api/.env already points at {TEST_DB}; refusing to drop it")
    test = parsed._replace(path=f"/{TEST_DB}").geturl()
    maintenance = parsed._replace(path="/postgres").geturl()
    return test, maintenance


def recreate_test_database(maintenance_url: str) -> None:
    import psycopg

    with psycopg.connect(maintenance_url, autocommit=True, connect_timeout=5) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB}")


async def request(app, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """One request straight into the ASGI app (no network), JSON in and out."""
    global requests_sent
    requests_sent += 1
    raw = json.dumps(body).encode() if body is not None else b""
    headers = [(b"content-type", b"application/json")] if body is not None else []
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers,
        "client": ("walkthrough", 1),
        "server": ("walkthrough", 80),
    }
    sent = False
    messages: list[dict] = []

    async def receive() -> dict:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message: dict) -> None:
        messages.append(message)

    try:
        await app(scope, receive, send)
    except Exception as err:  # the server already answered 500; record it, keep going
        if not any(m["type"] == "http.response.start" for m in messages):
            return 500, {"detail": f"{type(err).__name__}: {err}"}
        print(f"      server error during {method} {path}: {type(err).__name__}")
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    data = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    try:
        return status, json.loads(data or b"{}")
    except json.JSONDecodeError:
        return status, {"raw": data.decode(errors="replace")}


def copies_in_step(payload: dict) -> bool:
    from claims import points_for_item

    for section in ("experience", "projects"):
        for item in payload["inventory"]["sections"][section]["items"]:
            points = [p["content"] for p in points_for_item(payload, section, item["id"])]
            if item.get("bullets") != points:
                return False
    return True


async def walkthrough(use_ai: bool, test_url: str, timing_log: Path) -> None:
    import psycopg

    import main
    from payload_normalize import normalize_payload

    def stored(sid: str) -> dict:
        with psycopg.connect(test_url) as conn:
            row = conn.execute(
                "SELECT payload FROM resume_snapshots WHERE session_id = %s", (sid,)
            ).fetchone()
        return row[0]

    def history(sid: str) -> list[str]:
        with psycopg.connect(test_url) as conn:
            rows = conn.execute(
                "SELECT summary FROM career_versions WHERE session_id = %s ORDER BY version_num",
                (sid,),
            ).fetchall()
        return [r[0] for r in rows]

    async with main.lifespan(main.app):
        app = main.app

        with psycopg.connect(test_url) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
                ).fetchall()
            }
        check(
            "server starts on an empty database and creates every table",
            EXPECTED_TABLES <= tables,
            f"missing={sorted(EXPECTED_TABLES - tables)}",
        )

        status, data = await request(app, "POST", "/intake/start")
        sid = data.get("sessionId", "")
        base = f"/resume/{sid}"
        check(
            "start a resume",
            status == 200 and data.get("payload", {}).get("schemaVersion") == 5,
            f"status={status}",
        )
        check("first history entry is 'Resume created'", history(sid) == ["Resume created"], str(history(sid)))

        status, data = await request(
            app, "PATCH", f"{base}/basics",
            {"fullName": "Test Person", "email": "test@example.com", "verify": True},
        )
        check("confirm personal details", status == 200 and data.get("basicsVerified") is True, f"status={status}")

        status, _ = await request(
            app, "POST", f"{base}/tools/set_skills", {"skills": ["Python", "Redis"], "confirmedEmpty": False}
        )
        check("set skills", status == 200, f"status={status}")

        status, data = await request(
            app, "POST", f"{base}/tools/add_item",
            {
                "section": "experience",
                "fields": {
                    "company": "ExampleCo", "title": "Engineer", "location": "Remote",
                    "startDate": "2025-01", "endDate": "2025-12",
                    "bullets": ["Built an internal reporting tool used by the support team"],
                },
                "enrich": use_ai,
            },
        )
        first_id = data.get("itemId")
        record = stored(sid)
        item = next(
            (i for i in record["inventory"]["sections"]["experience"]["items"] if i["id"] == first_id),
            {},
        )
        check(
            "add an entry the way the voice assistant does" + (" (with AI tidy-up)" if use_ai else ""),
            status == 200 and bool(item.get("bullets")) and "story" in item and copies_in_step(record),
            f"status={status} detail={data.get('detail', '')}",
        )

        status, data = await request(
            app, "POST", f"{base}/tools/add_item",
            {
                "section": "experience",
                "fields": {
                    "company": "OtherCo", "title": "Intern", "location": "Bengaluru",
                    "startDate": "2024-06", "endDate": "2024-12", "bullets": ["Wrote test scripts"],
                },
                "enrich": False,
            },
        )
        second_id = data.get("itemId")
        status_p, _ = await request(
            app, "POST", f"{base}/tools/add_item",
            {
                "section": "projects",
                "fields": {
                    "name": "Side project", "description": "A small app",
                    "technologies": ["Python"], "bullets": ["Shipped a demo"],
                },
                "confirmedEmptyFields": ["url"],
                "enrich": False,
            },
        )
        check("add a second entry and a project", status == 200 and status_p == 200, f"status={status}, {status_p}")

        status, _ = await request(
            app, "POST", f"{base}/tools/exclude_from_resume", {"section": "experience", "itemId": first_id}
        )
        hidden = first_id not in stored(sid)["resume"]["includedIds"]["experience"]
        status2, _ = await request(
            app, "POST", f"{base}/tools/include_on_resume", {"section": "experience", "itemId": first_id}
        )
        shown = first_id in stored(sid)["resume"]["includedIds"]["experience"]
        check("hide then show an entry", status == 200 and status2 == 200 and hidden and shown)

        order = ["projects", "experience", "education", "achievements"]
        status, _ = await request(app, "POST", f"{base}/tools/reorder_sections", {"sectionOrder": order})
        check("reorder sections", status == 200 and stored(sid)["resume"]["sectionOrder"] == order)

        before_reorder = stored(sid)
        status, _ = await request(
            app, "POST", f"{base}/tools/reorder_items",
            {"section": "experience", "itemIds": [second_id, first_id]},
        )
        ids = [i["id"] for i in stored(sid)["inventory"]["sections"]["experience"]["items"]]
        check("reorder entries", status == 200 and ids == [second_id, first_id], str(ids))

        status, _ = await request(app, "POST", f"{base}/tools/undo")
        after_undo = stored(sid)
        undo_ok = [i["id"] for i in after_undo["inventory"]["sections"]["experience"]["items"]] == [
            i["id"] for i in before_reorder["inventory"]["sections"]["experience"]["items"]
        ]
        check("undo puts back the previous order", status == 200 and undo_ok)

        expected = [
            "Resume created",
            "Contact details updated",
            "Skills updated",
            "Added an entry to experience",
            "Added an entry to experience",
            "Added an entry to projects",
            "Hid an entry in experience",
            "Showed an entry in experience",
            "Sections reordered",
            "Entries reordered in experience",
            "Undid last change",
        ]
        check("every action is in the history, with its label", history(sid) == expected, str(history(sid)))

        status, data = await request(app, "GET", f"{base}/versions")
        listed = [v["summary"] for v in data.get("versions", [])]
        check("history list returned by the server matches", status == 200 and listed == list(reversed(expected)))

        target = 4  # the version saved right after the first entry was added
        status, _ = await request(app, "POST", f"{base}/versions/{target}/restore")
        restored = stored(sid)
        one_job = len(restored["inventory"]["sections"]["experience"]["items"]) == 1
        check(
            "restore an old version",
            status == 200 and one_job and history(sid)[-1] == f"Restored version {target}",
            f"status={status}",
        )

        status, data = await request(app, "GET", base)
        current = data.get("payload", {})
        current["resume"]["summary"] = "Replaced through the raw data route"
        status_put, _ = await request(app, "PUT", base, {"payload": current})
        replaced = stored(sid)["resume"]["summary"] == "Replaced through the raw data route"
        await request(app, "POST", f"{base}/tools/undo")
        undone = stored(sid)["resume"]["summary"] != "Replaced through the raw data route"
        check(
            "raw data save is recorded and can be undone",
            status_put == 200 and replaced and undone and "Record replaced" in history(sid),
        )

        # The restore went back to before the project was added, so confirm every
        # section that is empty now, as the person would.
        empty = [
            key
            for key, bag in stored(sid)["inventory"]["sections"].items()
            if not bag.get("items")
        ]
        status, data = await request(
            app, "POST", f"{base}/tools/complete_intake", {"confirmedSkippedSections": empty}
        )
        check(
            "finish setup",
            status == 200 and stored(sid)["intake"]["status"] == "complete",
            f"status={status} skipped={empty} detail={data.get('detail', '')}",
        )

        final = stored(sid)
        check(
            "stored record is version 5, tidy, and its two copies of points match",
            final.get("schemaVersion") == 5 and normalize_payload(final) == final and copies_in_step(final),
        )

        with psycopg.connect(test_url) as conn:
            undo_rows = conn.execute(
                "SELECT count(*) FROM resume_undo WHERE session_id = %s", (sid,)
            ).fetchone()[0]
        check("undo copies are being kept", undo_rows > 0, f"rows={undo_rows}")

    lines = timing_log.read_text().splitlines() if timing_log.exists() else []
    leaked = any(sid in line for line in lines)
    tidy = [json.loads(l) for l in lines if "tidy_up" in (json.loads(l).get("parts") or {})]
    check(
        "timing log written for every request, without session ids",
        len(lines) == requests_sent and not leaked and (bool(tidy) or not use_ai),
        f"lines={len(lines)} for {requests_sent} requests, session id leaked={leaked}, "
        f"tidy-up timed={bool(tidy)}",
    )


def main_cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-ai", action="store_true", help="skip the paid AI tidy-up call")
    args = parser.parse_args()

    test_url, maintenance_url = database_urls()
    try:
        recreate_test_database(maintenance_url)
    except Exception as err:
        print(f"Could not reach the database ({type(err).__name__}). Is `docker compose up -d` running?")
        return 1

    # Point the API at the test database before it is imported.
    os.environ["DATABASE_URL"] = test_url
    sys.path.insert(0, str(API))
    import timing

    with tempfile.TemporaryDirectory() as tmp:
        timing.LOG_PATH = Path(tmp) / "timing.jsonl"  # keep the real baseline log clean
        asyncio.run(walkthrough(not args.no_ai, test_url, timing.LOG_PATH))

    passed = sum(ok for _, ok, _ in results)
    print(f"\n{passed}/{len(results)} walkthrough checks passed")
    print(f"The test database '{TEST_DB}' is left in place for inspection; the next run recreates it.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
