# Autopilot

The work list for the scheduled Claude runs. Each run reads this file, does the next unfinished
task, and records what happened. Written 2026-11-19 from Parth's product decisions.

## How a run works

1. Work on branch `claude/autopilot`. Start with `git pull --rebase`.
2. Read **Decisions** and **Rules** below, then the **Log** (the last entry may be a task left half done).
3. Pick the first task that is not `[x]` or `[blocked]`. If it shows `Progress:` notes, continue from them.
   Before any other work, add a Log entry `- <date> <HH:MM> UTC — STARTED <task id> (<who: autopilot
   or interactive>)`, commit and push it. This tells Parth (and other runs) that work has begun.
4. Set up only what the task needs:
   - API: `python3 -m venv api/.venv && api/.venv/bin/pip install -r api/requirements.txt`
   - Web: `cd web && npm ci`
5. Build it. Read only the files the task needs; follow the code's existing style and comment density.
6. Check it (see **Checks**). All checks must pass before a task is ticked.
7. Commit after each meaningful step, not only at the end, and push. A run can be cut off at any
   moment when the usage limit runs out; anything not pushed is lost. Before stopping mid-task,
   write a `Progress:` line under the task saying exactly what is done and what is next.
8. When the task is done: tick it `[x]`, add a Log entry (date, task, what changed, check results),
   commit, push. If plenty of time is left, start the next task; otherwise stop.
9. If a push is rejected because the branch moved, `git pull --rebase` and push again.

## Rules

- Never push to `main` or `writing-team`. Never merge. Never deploy. Only `claude/autopilot`.
- Never call a paid AI model: no `--yes` on `evals/run_writing_evals.py`, no live OpenAI calls.
  Tests must use the existing offline/fake paths.
- Never create, read or change `api/.env`, keys or secrets. Never log a key.
- Do not rewrite `docs/V2.md`. Do not delete existing tests. Do not weaken an eval to make it pass.
- Keep the AI write path as it is: changes to a resume only through tools (see `docs/ORCHESTRATOR.md`).
- If a task is blocked (needs a key, a microphone, a browser, a decision), mark it `[blocked]` with
  the reason in one line, log it, and move to the next task. Do not guess at product decisions.
- Every behaviour that can be tested offline gets a new case in `evals/run_evals.py`, in the style
  of the existing cases.
- Update the docs a change affects (`docs/resume-payload.md`, `evals/README.md`, `.env.example`).

## Checks

All must pass before a task is ticked:

```bash
api/.venv/bin/python evals/run_evals.py      # every case passes (42 at the start)
cd web && npm run lint && npm run build
```

Things that need a microphone, a browser or a real key cannot be checked here: write them under
**Manual checks** at the bottom so they are done in the final local session.

## Decisions (from Parth — do not change)

1. Portfolio project for FDE roles, and it must work properly for real job seekers.
2. Voice saves the person's own words as each entry's `story`. The raw story is never shown in the UI.
3. The writing team runs automatically after an entry is captured, with a button to run it again.
4. The voice assistant asks the writing team's follow-up questions (at most 2 per entry), then the points are rewritten.
5. Points with status `needs_review` or `unchecked` show a warning only. They never block saving or downloading.
6. The career intelligence panel stays visible but must make sense to a normal user.
7. Tech professions only for now.
8. Online: Parth's key with strict limits per visitor; after the limit, the visitor can bring their own key.
9. The voice assistant must end the call by itself when its step is done.

## Tasks

### [x] T0. Make lint pass
At setup, `npm run lint` failed with 2 errors (build passed): `react-hooks/set-state-in-effect` at
`web/src/components/resume/BasicsEditor.tsx:85` and `web/src/components/resume/useContactStatus.ts:74`.
- Fix the cause (derive the value, or set it from the event/handler that starts the work); do not
  disable the rule. Behaviour must stay the same.
- Done when: all checks pass.

### [x] T1. Voice ends the call by itself
Today the call only ends when the person presses the button; `complete_intake` does not stop it.
- Add a voice-only tool `end_voice_session` (not offered to text chat). Tell the assistant in
  `api/realtime.py` instructions to say a short goodbye and call it when: intake is complete
  (after `complete_intake`), the person says they are done, or an edit-mode request is finished
  and the person has nothing more.
- In `web/src/voice/handleRealtimeTools.ts` / `realtimeSession.ts` / `App.tsx`: on that tool call,
  wait until the goodbye audio has finished playing, then call the same `stop()` the button uses,
  and move the person to the next step on screen. The button stays.
- Never end the call while a tool call is still running.
- Done when: offline eval checks the tool is in the voice tool list and not the chat one, and the
  instructions mention it; lint/build pass. Manual check added.

### [x] T2. Save the person's own words as the story
Today the story is a copy of the bullets the voice assistant summarised (`legacy_story` in
`api/payload_normalize.py`), so the analyst never sees what the person really said.
- The Realtime session already transcribes speech (`gpt-4o-mini-transcribe` in `api/realtime.py`).
  Collect the person's transcribed turns in the browser while an entry is being discussed.
- When the assistant calls `add_item` / `add_project` (or a tool that adds to an existing entry),
  send the person's turns about that entry along, and store them on that entry (or project) as
  story chunks `{ id, text, source: "voice", at }`. Typed chat input is stored with `source: "typed"`.
- Only the person's words, never the assistant's. Cap the size (the pipeline refuses stories over
  6000 characters; keep well under that and keep the newest turns).
- Keep `legacy` chunks working for old resumes. The story is never displayed in the UI.
- Done when: offline evals cover storing chunks on an item and on a project inside a job, the cap,
  that assistant text is never stored, and that old resumes still load; docs updated.

### [x] T3. Writing team runs automatically, plus a re-run button
The backend `POST /resume/{id}/rewrite` exists and is tested; nothing in the website calls it.
- Add `rewriteEntry()` to `web/src/api/resumeApi.ts`.
- After an entry's story is saved or changed (T2), call it in the background for that entry. The
  person can keep working; show a small "Writing your points…" state on that entry.
- Handle its replies in plain words: `skipped` (no change), 409 (points the person edited: ask
  before replacing; entry changed meanwhile: run again once), 429 (too many this hour), 502 (the
  writing team failed: keep the old points, offer to try again).
- Add a "Rewrite points" button on each experience/project entry (and project inside a job). It
  sends `force: true`.
- Never run it from inside the live voice path (the endpoint is slow).
- Done when: lint/build pass; offline evals still pass; manual check added.

### [x] T4. Follow-up questions
The analyst returns up to 2 questions (`rewrite.questions`); nothing asks them.
- Store them on the entry (`writing.questions`, `followUpsAsked` already exist in the record shape).
- When a voice call is open or next opens for that entry, give the assistant the open questions
  (through the context it already receives) and tell it to ask them one at a time, at most 2 per
  entry, and to accept "I don't know" or "skip".
- Answers are added to the story with `source: "followup"`; then the entry is rewritten (T3).
- In text mode, show the questions under the entry with a box to answer.
- Done when: offline evals cover storing questions, the 2-question limit, and follow-up chunks
  joining the story; lint/build pass.

### [ ] T5. Warning badge on points that need a look
- In the editor, a point with status `needs_review` or `unchecked` shows a small warning with a
  one-line plain reason ("This line was simplified because the first version claimed more than
  you said" / "This line was not double-checked"). The person can edit or keep it.
- Never block saving or downloading. Never print the warning on the resume itself.
- Editing a point by hand clears its warning (it becomes the person's own point).
- Done when: offline eval covers that a hand edit clears the status; lint/build pass.

### [ ] T6. Download as PDF
- A "Download PDF" button in the workspace. Use a print stylesheet so only the resume page prints
  (no app chrome), selectable text (good for applicant tracking systems), A4 and US Letter both
  fitting, sensible page breaks between entries.
- Follow the earlier product rule: downloading asks a guest to log in or sign up first, like Save.
- Do not print warnings, story text or debug panels.
- Done when: lint/build pass; manual check added (print preview in Chrome and Safari).

### [ ] T7. Friendly career intelligence panel
- Rename and explain in plain words: "Tailor to a job" (paste a job description → a version for
  that job), "Why is this line here?" (shows the facts behind a line — fact content only, not the
  person's raw story), "History" (readable times and what changed, with restore).
- Move the JSON console and Realtime event log behind one "Developer tools" toggle, off by default.
- Done when: lint/build pass; manual check added.

### [ ] T8. Daily limits per visitor
- One place that counts AI use per visitor per day: logged-in user id, else session id. Store in
  Postgres (new table in `api/db/`, created like the others).
- Cover every endpoint that spends money: chat, Realtime token (count call minutes or sessions),
  rewrite, analyze-jd, mutate, PDF import, enrichment.
- Limits come from env settings with small defaults; list them in `api/.env.example`.
- Over the limit: a clear 429 message that says when it resets and that they can add their own key (T9).
- Done when: offline evals cover counting, the limit, the reset, and that every paid endpoint goes
  through the counter (like the existing `single_save_door` check).

### [ ] T9. Bring your own key
- After the limit, the person can paste their own OpenAI key. Keep it only in the browser
  (`sessionStorage`), send it with each AI request in a header, use it for that request only.
- The server never stores it, never logs it, never puts it in traces or error messages. Redact it
  everywhere. Realtime tokens are minted with their key.
- A request with their key does not count against the daily limit.
- Done when: offline evals cover that the key is used for the request, never stored in the
  database or traces, and is redacted from errors and logs; lint/build pass.

### [ ] T10. One-command local start
- `scripts/dev.sh`: start Postgres with `docker compose`, apply the SQL files in `api/db/` if
  needed, start the API and the website, stop everything on Ctrl+C.
- Done when: `bash -n scripts/dev.sh` passes; README run section uses it; manual check added.

### [ ] T11. README for the public
- Lead with what it does and why it is hard: voice in, an analyst → writer → checker team, every
  line traceable to the person's own words, nothing invented. A diagram (mermaid) of the pipeline.
- Eval results: the offline cases and what they prove; the writing test set and its hard cases.
- How to run (T10), limits and bring-your-own-key, tech stack.
- Leave clearly marked places for screenshots and a demo GIF (taken in the final local session).
- Done when: links in it resolve to real files.

### [ ] T12. Stop
When T0–T11 are all `[x]` or `[blocked]`, write `ALL DONE` as the last Log entry. Every later run
reads it and does nothing. The final local check, merging into `main` and going online are done
with Parth, not by autopilot.

## Manual checks

(Things to try in the final local session with a real key, a microphone and a browser.)

- T2: describe a job by voice, then check the saved entry's `story` holds your own spoken sentences (`source: "voice"`), none of the assistant's words, and that nothing shows them on screen.
- T1: finish an intake by voice: the assistant says goodbye, the call ends by itself after the goodbye
  audio (not mid-sentence), and the screen shows "All done". Also say "that's all" in edit mode. The
  stop button must still work. Check it never hangs up while a tool is running.
- T3: with a real key, finish describing a job by voice. When the call ends, the entry shows "Writing your points…" and then new checked points appear, without a page reload. While the call is open nothing is rewritten. "Rewrite points" re-runs it; after editing a point by hand it asks "Replace my points / Keep mine". Stop the API mid-run: the old points stay and "Try again" shows.
- T4: with a real key, finish a job by voice so the writing team returns questions. Open a new call: the assistant asks them one at a time (max 2 per entry), accepts "I don't know", and your spoken answer lands in the story (`source: "followup"`), then the points rewrite after the call. In text mode the questions show under the entry with Answer / Skip.

## Log

- 2026-11-19 — Autopilot set up from `writing-team`. Offline evals 42/42 pass; web build passes;
  web lint has 2 errors (task T0).
- 2026-11-19 — T0 done (interactive session). BasicsEditor edits now remember the saved details
  they started from; useContactStatus derives `checking` instead of setting it in an effect.
  Lint 0 errors, build passes, evals 42/42.
- 2026-11-19 06:14 UTC — STARTED T1 (autopilot)
- 2026-11-19 06:30 UTC — T1 done (autopilot). New voice-only tool `end_voice_session` (api/chat_tools.py `voice_tools_for_payload`, not in chat); instructions in api/realtime.py (`END_CALL_RULE`); browser waits for goodbye audio and running tools, then calls the button's stop. New eval `voice_can_end_call`. Evals 43/43, lint clean, build passes. Manual check added.
- 2026-11-19 06:58 UTC — STARTED T2 (autopilot)
- 2026-11-19 07:01 UTC — T2 done (autopilot). New api/story_chunks.py; add_item/add_project take storyTurns (voice) and the text chat stores the typed message (source typed); browser collects only the person's finished transcriptions and sends them with those two tools. Cap 4000 chars, newest kept; legacy chunks dropped once real words arrive. New eval `story_keeps_persons_words`. Evals 44/44, lint clean, build passes. Manual check added.
- 2026-11-19 07:58 UTC — STARTED T3 (autopilot)
- 2026-11-19 08:01 UTC — T3 done (autopilot). `rewriteEntry()` in web/src/api/resumeApi.ts; new hook web/src/components/resume/useAutoRewrite.ts runs the writing team in the background when an entry's story changes (waits while a voice call is open, never from the voice path); plain-words handling of skipped, 409 (ask before replacing edited points; changed meanwhile: run once more), 429, 502; "Rewrite points" button (force) on each experience/project entry and project inside a job. No new offline eval (browser-only change; backend already covered). Evals 44/44, lint clean, build passes. Manual check added.
- 2026-11-19 08:58 UTC — STARTED T4 (autopilot)
- 2026-11-19 09:01 UTC — T4 done (autopilot). Questions already stored by the writing store now respect the 2-per-entry cap; new `answer_follow_up` / `open_follow_ups` in api/story_chunks.py, endpoint `tools/answer_followup`, voice-only tool `answer_followup` (the person's own words are stored, skip adds nothing but counts), open questions and rules added to voice instructions (`followup_instructions`), Answer/Skip boxes under each entry in the editor; the answer changes the story so the auto-rewrite (T3) runs. New eval `follow_up_questions`. Evals 45/45, lint clean, build passes. Manual check added.
