# AI Resume Builder

An **evaluation-driven AI career intelligence system** that converts natural language into validated structured career updates, retrieves relevant evidence, and generates job-specific resume content with traceable provenance.

**North star:** [docs/V2.md](./docs/V2.md)

## Start here

| Doc | Purpose |
|-----|---------|
| [docs/V2.md](./docs/V2.md) | Project direction — structured ops, versioning, provenance, eval |
| [docs/ORCHESTRATOR.md](./docs/ORCHESTRATOR.md) | Mutation pipeline — tools-only writes, policy |
| [docs/resume-payload.md](./docs/resume-payload.md) | Resume JSON payload shape (v5) |
| [evals/README.md](./evals/README.md) | Evaluation harness |

## Layout

```text
api/     FastAPI — mutation pipeline, versioning, JD analysis
web/     Vite + React — intelligence panel, variants, preview
evals/   Deterministic + LLM evaluation cases
docs/    Architecture and payload contract
```

## V2 pipeline

```text
Text (or voice→STT) → LLM proposes CareerOperations
                   → validate (schema, entities, ambiguity)
                   → execute (resume_ops)
                   → version log + facts/claims
                   → resume variant / preview
```

## Run locally

```bash
# Database (Postgres 16 in Docker, data kept in the resume-builder-db-data volume)
docker compose up -d

# API (needs the database and OPENAI_API_KEY in api/.env; see api/.env.example)
# Creates any missing tables on startup.
cd api && uvicorn main:app --reload --port 8081

# Frontend
cd web && npm run dev

# Evals (no database or API key needed)
python evals/run_evals.py

# Walkthrough against a real, separate test database (needs the database running;
# --no-ai skips the two paid AI calls)
python evals/db_walkthrough.py --no-ai
```

## Key API endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /resume/{id}/mutate` | NL → structured ops → validated mutation |
| `GET /resume/{id}/versions` | Version history |
| `POST /resume/{id}/versions/{n}/restore` | Restore snapshot |
| `POST /resume/{id}/analyze-jd` | JD analysis + job variant |
| `POST /resume/{id}/retrieve` | Structured evidence retrieval |
| `GET /resume/{id}/claims/{id}/provenance` | Claim → fact trace |
