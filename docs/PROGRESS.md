# Rebuild progress

**Last updated:** 16 Aug 2026

**Canonical plan:** [AI_IMPLEMENTATION_PLAN.md](./AI_IMPLEMENTATION_PLAN.md)

---

## Where we are

End-to-end **persistence + JSON console** works. Next focus is **AI tools / inventory model**, not product UI.

- FastAPI (`api/`): `/health`, `GET`/`PUT /resume/{session_id}`, CORS  
- Postgres Docker: `resume_snapshots`  
- `web/`: Load/Save JSON by session id  
- Decisions: OpenAI only, text+tools then Realtime on same tools, soft exclude, enrich on add  

---

## Decisions (locked)

| Topic | Choice |
|--------|--------|
| API | FastAPI (Python) |
| Database | PostgreSQL (Docker) |
| AI | OpenAI; realtime mini where applicable |
| Mutation model | Inventory + resume inclusion; soft exclude by default |
| UI | Dev console until AI path is solid |
| Auth | None yet (anonymous `sessionId`) |

---

## What exists

```text
api/main.py                  health + resume CRUD
api/db/schema.sql
api/resume-schema.example.json   (still flat v1 — Phase 0 upgrades this)
web/                         Vite Load/Save harness
docs/AI_IMPLEMENTATION_PLAN.md
docs/resume-payload.md
```

---

## Tonight

Follow phases in [AI_IMPLEMENTATION_PLAN.md](./AI_IMPLEMENTATION_PLAN.md):

1. Phase 0 — payload v2 (inventory + resume view)  
2. Phase 1 — tool API (exclude / include / add)  
3. Stretch — enrichment or chat stub  

Say **next** to start Phase 0.
