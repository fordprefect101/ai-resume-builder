# Conversation speed baseline

The rule: nothing the person hears waits on the background. This file records how
fast the live conversation is, so later changes can be compared against real numbers.

## What is measured

| Measurement | Where it is recorded | Why |
|---|---|---|
| Duration of every server request | `api/logs/timing.jsonl` (one line per request; not in git) | Our part of each save |
| Time spent in the AI tidy-up during a save | Same line, `parts.tidy_up` | The one AI call currently inside a save |
| Size of each server reply | Same line, `bytes` | Grows with the resume |
| Round trip of each voice tool call, and characters handed to the voice model | Browser console (`[timing] tool`) and the on-screen voice log | What the voice model must read after each save |
| Gap between the person stopping talking and the first sound of the reply | Browser console and the on-screen voice log (`timing: reply started …`) | The delay the person actually feels |

The timing log stores the route template (for example `/resume/{session_id}/tools/add_item`), never the real address, so no session id is written.

## How to record a baseline

1. Start Postgres, the API (`cd api && uvicorn main:app --reload --port 8081`) and the website (`cd web && npm run dev`).
2. Note the time (UTC). Open the browser console.
3. Start a new resume, confirm the personal details, start voice, and follow the script below.
4. Stop voice. Run `python evals/timing_report.py --since <the time from step 2>`.
5. Copy the `[timing]` lines from the browser console.
6. Add the results under "Recorded baselines".

### Session script (use the same one every time)

1. Skills: "I mainly work with Python, Redis and AWS."
2. First job: company, title and dates, then about three sentences on what you did there.
3. Second job: the same.
4. One project: its name and two or three sentences on it.
5. One edit: ask to move a section up, or to hide one of the jobs.
6. Stop voice.

Use the same script, the same kind of content and the same network each time; otherwise the numbers are not comparable.

## Recorded baselines

### 2026-10-14: size of what the voice model reads after one save (measured in code, no live session)

Generated resumes, run through the real upgrade code; "after phase 1" is the current shape.

| Resume size | Before phase 1 | After phase 1 | With a short result instead |
|---|---|---|---|
| 2 jobs, 2 points each | 2,488 characters | 4,712 | 716 |
| 4 jobs, 4 points each | 4,598 | 13,030 | 734 |
| 8 jobs, 5 points each | 8,818 | 29,666 | 770 |

Each reply stays in the call's memory, so these add up over a session.

### Live session

Not recorded yet: the database was not running when the measuring tools were added (2026-10-19). The first live run should also confirm the voice event names used for "first sound" (`output_audio_buffer.started` and others); the browser console lists every event type it sees (`[timing] voice event type seen`).
