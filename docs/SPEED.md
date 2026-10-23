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

## The short result the assistant receives (step 1b.2)

Everything sent into a voice call stays in its memory, so after each action the browser
sends the model only `assistantResult` from the server's reply. The full reply (the whole
resume) goes to the screen only. Built in `api/assistant_result.py`; applied by
`resultForAssistant` in `web/src/voice/handleRealtimeTools.ts`. If a reply has no
`assistantResult`, the model gets `{"ok": true}`, never the full reply. Errors become
`{"ok": false, "error": "..."}`.

| Field | Meaning |
|---|---|
| `ok` | The action worked |
| `tool` | The action's name |
| `message` | One plain sentence, at most 200 characters |
| `section`, `itemId` | The section and entry touched or created, when there is one |
| `progress` | `setupComplete`, `detailsConfirmed`, `skills` (a count) and `sections` (a count per section). Counts only, never lists of ids |
| `candidates`, `ambiguous` | Search only: at most 6 short matches (section, itemId, onResume and a label), and whether several match about equally |
| `error` | Failures only |

Actions covered: add_item, set_skills, complete_intake, exclude_from_resume,
include_on_resume, reorder_sections, reorder_items, search_resume_context.

Measured on generated resumes through the real server code (characters):

| Resume | add_item full reply | add_item short result | search short result |
|---|---|---|---|
| 2 jobs x 2 points | 5,873 | 285 | 514 |
| 8 jobs x 5 points | 30,827 | 285 | 986 |
| 20 jobs x 5 points | 73,321 | 286 | 995 |

Action results stay the same size whatever the resume size; search is bounded by its 6-match cap.
Not covered yet: the typed-chat path still returns bulky results to its model.

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
