# Evaluation Suite

Run the deterministic evals:

```bash
python evals/run_evals.py
```

No database or API key is needed. The script forces placeholder values for
`DATABASE_URL` and `OPENAI_API_KEY` (a real key in your shell is replaced, not used) and
blocks all network connections, so it cannot reach a database, a model or the internet.

## What runs today

Everything lives in `run_evals.py` and uses `fixtures/sample_career.json`.
The contact checks (shape rules, the safe link opener, lookups replayed from recorded
answers, the gate, privacy, background lookups and project links) are described in
`docs/CONTACT-CHECKS.md`; none of them touches the internet.
`timing_report.py` is not a check: it summarizes the server's timing log (see `docs/SPEED.md`).

## Website render check

```bash
cd web && npm run check:render
```

`web/render-check.mjs` loads the real `ResumePreview` and `ResumeEditor` components with
Vite, renders them to HTML in memory (no browser), and checks that a job's projects are
drawn: active projects with their technologies and points on the paper, projects with no
points or archived ones left off the paper, the editor listing every project (archived
ones dimmed), and a job without projects looking exactly as before. It proves the right
text is drawn, not that it looks good.

## Walkthrough against a real database

```bash
docker compose up -d
python evals/db_walkthrough.py          # includes two small paid AI calls
python evals/db_walkthrough.py --no-ai  # skips them
```

`db_walkthrough.py` creates a fresh `resume_builder_test` database on the same
server (real data is never touched), starts the API on it, and drives it with real
requests: start a resume, confirm details, set skills, add entries, hide and show,
reorder, undo, history, restore, raw save, finish setup. After each step it checks
the stored record. It also confirms the server can start on an empty database, and exercises add, rename, reorder and archive of a job's projects.

| Check | What it proves |
|-------|----------------|
| `entity_resolution` | A company name resolves to the right inventory item |
| `skill_delete` | A validated DELETE operation removes a skill |
| `claim_verification` | An inflated claim with no supporting facts is `unsupported` |
| `v5_upgrade_keeps_points` | Upgrading a v4 record keeps every bullet, as a point and as a story chunk |
| `v5_upgrade_is_stable` | Normalizing twice gives the same result (stable ids) |
| `v5_bullets_follow_points` | Points are the source: edits to `bullets` are undone, edits to points show |
| `v5_writers_keep_copies_in_step` | After add / update / enrich / typed request / archive, `bullets` equals the points |
| `v5_blank_record` | A blank or invalid payload normalizes to an empty v5 record |
| `v5_label_defaults` | Older facts and points get default labels without losing text or ids |
| `v5_labels_survive_reload` | Labels that were set are kept across a reload |
| `v5_rejects_unknown_labels` | Unknown fact kinds/owners and point statuses/origins are refused |
| `projects_upgrade_changes_nothing` | Existing records gain empty `projects`; every point keeps its text, copy and its pre-project id |
| `project_points_stay_separate` | Job-level and project-level points never mix, keep their labels, and the bullets copies match at both levels |
| `projects_tolerate_bad_data` | Malformed projects and points of a deleted project are handled deterministically; no point is lost |
| `project_operations` | Adding, renaming, archiving and reordering a job's projects follow the rules (names, uniqueness, permutation, soft removal) and leave the record tidy |
| `project_search_and_facts` | Search finds a job by its projects and lists them (capped); archived projects stop matching; project facts carry the project; voice and typed chat share the tools |
| `save_door` | `_save_payload` normalizes, keeps an undo copy, and records a version entry |
| `voice_add_entry_end_to_end` | The voice add-entry request runs through the real code (stand-in database and OpenAI) and saves the entry |
| `assistant_result_is_small_and_constant` | The 8 voice actions return a short `assistantResult` with the agreed fields; its size does not grow from a 2-job to a 20-job resume (search is capped) |
| `live_path_guard` | No voice action calls an AI model or opens a connection (except add-entry's allowed tidy-up); every voice tool is covered; the browser sends only the short result |
| `single_save_door` | No code outside `_save_payload` / `_create_snapshot` writes a stored resume |
| `example_record_is_current` | `api/resume-schema.example.json` is a valid, normalized v5 record with no duplicate keys and a project inside a job whose points are recorded as its own |
| `env_example_lists_settings` | `api/.env.example` names every setting the API code reads |
| `timing_log` | The timing wrapper is installed, records duration, size and tidy-up time, and never writes a session id |

## Planned (not built yet)

These directories do not exist yet. They are the categories from
[docs/V2.md](../docs/V2.md).

| Directory | Tests |
|-----------|-------|
| `operations/` | NL → operation accuracy (LLM — run manually) |
| `entity_resolution/` | Ambiguity and candidate matching |
| `retrieval/` | Structured vs semantic retrieval |
| `grounding/` | Claim → fact linkage |
| `claim_verification/` | Unsupported claim detection |
| `job_matching/` | JD requirement evidence levels |

Only report metrics from actual test runs.
