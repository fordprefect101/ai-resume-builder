# AI Resume Builder

**Rebuild from scratch.** Planning docs + a Vite frontend (`web/`) and a Python API home (`api/`).

**Where we are / what’s next:** [docs/PROGRESS.md](./docs/PROGRESS.md)

## Start here

| Doc | Purpose |
|-----|---------|
| [docs/PROGRESS.md](./docs/PROGRESS.md) | What we’ve done, decisions, next steps |
| [docs/AI_IMPLEMENTATION_PLAN.md](./docs/AI_IMPLEMENTATION_PLAN.md) | Phased AI-first plan (inventory, tools, chat, Realtime) |
| [DESIGN.md](./DESIGN.md) | Architecture north-star, voice/state, product intent |
| [docs/resume-payload.md](./docs/resume-payload.md) | Resume JSON payload shape (v1 → v2 in Phase 0) |
| [docs/IMPLEMENTATION_PHASES.md](./docs/IMPLEMENTATION_PHASES.md) | Phased scope — reference; partly outdated vs rebuild |
| [Resume_Builder_Product_and_Technical_Architecture.docx](./Resume_Builder_Product_and_Technical_Architecture.docx) | Product + technical architecture |

## Layout

```text
api/     FastAPI backend (in progress) — Postgres schema + env
web/     Vite + React + TypeScript frontend
docs/    Planning + payload contract
```

## Rebuild order (suggested)

See [docs/AI_IMPLEMENTATION_PLAN.md](./docs/AI_IMPLEMENTATION_PLAN.md). Short version:

1. ~~FastAPI CRUD + JSON Load/Save~~ (done)
2. Payload v2: inventory + resume view
3. Deterministic tools → enrichment on add → text chat → Realtime (same tools)
4. Product UI only after AI path is solid
