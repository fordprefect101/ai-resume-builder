# Rebuild progress

Current status of this project after a from-scratch reset. Use this file to pick up after a break. Specs live in [IMPLEMENTATION_PHASES.md](./IMPLEMENTATION_PHASES.md), [boundary-map.md](./boundary-map.md), and [DESIGN.md](../DESIGN.md).

**Last updated:** 16 Aug 2026

---

## Where we are

We are **early in a rebuild**. There is no frontend, no resume API, and no database wiring yet.

The API can start and answer **`GET /health`**. Next work is **local Postgres + `DATABASE_URL`**, then persist resumes in the DB.

---

## What we did

1. Deleted the previous implementation (React app, backend routes, worker, templates, auth, etc.).
2. Kept planning docs: `DESIGN.md`, `IMPLEMENTATION_PHASES.md`, `boundary-map.md`, `HOSTING.md`, `async-failure-playbook.md`, `phase-memory-intelligence.md`.
3. Agreed to rebuild **one step at a time** (not a full roadmap dump each turn).
4. Scaffolded a minimal Express API:
   - `backend/package.json` (`type: module`, `npm start`)
   - `backend/server.js` — listen on `PORT` (default **8081**), `GET /health` → `{ ok: true }`
5. Chose **Postgres** for persistence (not in-memory `Map`, not Supabase).
6. Chose **run Postgres locally** (Docker or Homebrew). Setup was explained; it is **not finished** in the repo (no `.env`, no schema, no `pg`).

---

## Decisions (locked for this rebuild)

| Topic | Choice |
|--------|--------|
| Database | PostgreSQL |
| Auth for now | None (anonymous `sessionId` later). Not using Supabase. |
| Persistence | DB from the start — skip in-memory resume store |
| Product shell (later) | `landing → voice → home` as in IMPLEMENTATION_PHASES |
| Voice auto-end (later) | Keyword match on assistant transcript; **Done** is the reliable path |
| Step style | One small step at a time |

---

## What exists in the repo

```text
backend/server.js          health check only
backend/package.json       Express
docs/                       planning docs
DESIGN.md, README.md
```

Not yet: `backend/.env`, `pg`, schema, resume routes, React app.

---

## What to do next (in order)

### Now — local Postgres

1. Run Postgres locally (Docker is fine): user `resume`, password `resume`, database `resume_builder`, port `5432`.
2. Confirm `SELECT 1`.
3. Add `backend/.env` (gitignored) with:

   ```env
   PORT=8081
   DATABASE_URL=postgresql://resume:resume@localhost:5432/resume_builder
   ```

4. Add `backend/.env.example` with placeholder values (no real secrets).

### Then — wire the API to Postgres

5. Add `pg` + `dotenv` to the backend.
6. Minimal schema (e.g. `resume_snapshots`: `session_id`, `payload` jsonb, version).
7. `GET /resume/:sessionId` from the DB (404 if missing).
8. `PUT /resume/:sessionId` to insert/update.

### After that (not this week’s blocking work)

9. Resume JSON schema + types + normalize.
10. `POST /extract-resume` (OpenAI).
11. Vite React app + `ResumeContext`.
12. Voice (`GET /token`, WebRTC Realtime).
13. Deploy using HOSTING.md (treat Supabase sections as optional; this rebuild uses plain Postgres).

Do **not** start yet: worker, outbox, memory/RAG, full template engine, GitHub dual-account setup (unrelated).

---

## How to continue in chat

Say **“done”** after each small step, or **“next step”** to get only the following slice.

**Immediate next slice:** Postgres running locally + `SELECT 1` + `backend/.env`.
