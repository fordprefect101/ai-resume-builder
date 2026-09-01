# V2 Evaluation Suite

Run deterministic evals (no API key required):

```bash
python evals/run_evals.py
```

## Categories

| Directory | Tests |
|-----------|-------|
| `fixtures/` | Sample career payloads |
| `operations/` | NL → operation accuracy (LLM — run manually) |
| `entity_resolution/` | Ambiguity and candidate matching |
| `retrieval/` | Structured vs semantic retrieval |
| `grounding/` | Claim → fact linkage |
| `claim_verification/` | Unsupported claim detection |
| `job_matching/` | JD requirement evidence levels |

Only report metrics from actual test runs.
