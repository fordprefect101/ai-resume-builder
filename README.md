# AI Resume Builder

**Rebuild from scratch.** Implementation code was cleared; planning and architecture docs remain.

**Where we are / what’s next:** [docs/PROGRESS.md](./docs/PROGRESS.md)

## Start here

| Doc | Purpose |
|-----|---------|
| [docs/PROGRESS.md](./docs/PROGRESS.md) | What we’ve done, decisions, next steps |
| [DESIGN.md](./DESIGN.md) | Architecture north-star, voice/state, product intent |
| [docs/IMPLEMENTATION_PHASES.md](./docs/IMPLEMENTATION_PHASES.md) | Phased scope — shipped vs deferred, routes, file map |
| [docs/boundary-map.md](./docs/boundary-map.md) | Layer boundaries (API, services, domain, persistence, worker, frontend) |
| [docs/HOSTING.md](./docs/HOSTING.md) | Deploy frontend, API, worker, Supabase |
| [docs/async-failure-playbook.md](./docs/async-failure-playbook.md) | Async/outbox failure handling |
| [docs/phase-memory-intelligence.md](./docs/phase-memory-intelligence.md) | Future memory / retrieval design (not shipped) |

## Rebuild order (suggested)

1. Read **DESIGN.md** + **IMPLEMENTATION_PHASES.md**
2. Scaffold backend (`Express`, env, core routes) per phase matrix
3. Scaffold React app under `src/react/` per navigation sketch in phases doc
4. Add persistence + auth when P2/P3 milestones need them
5. Deploy using **HOSTING.md**
