# Evaluation Suite

Run the deterministic evals:

```bash
python evals/run_evals.py
```

No database or API key is needed. The script sets placeholder values for
`DATABASE_URL` and `OPENAI_API_KEY`, so it cannot reach either.

## What runs today

Everything lives in `run_evals.py` and uses `fixtures/sample_career.json`.

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
| `save_door` | `_save_payload` normalizes, keeps an undo copy, and records a version entry |
| `single_save_door` | No code outside `_save_payload` / `_create_snapshot` writes a stored resume |
| `example_record_is_current` | `api/resume-schema.example.json` is a valid, normalized v5 record |
| `env_example_lists_settings` | `api/.env.example` names every setting the API code reads |

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
