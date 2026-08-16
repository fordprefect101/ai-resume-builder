# AI-first implementation plan

Phased plan to ship a **conversational resume operator** on structured state — inventory + resume views, soft exclude, enrichment on add, text chat + tools, then Realtime — **before** locking a production UI.

**Product north star:** [Resume_Builder_Product_and_Technical_Architecture.docx](../Resume_Builder_Product_and_Technical_Architecture.docx)  
**Current payload (v1, flat):** [resume-payload.md](./resume-payload.md)  
**Pickup status:** [PROGRESS.md](./PROGRESS.md)

**Last updated:** 16 Aug 2026

---

## Locked decisions

| Topic | Choice |
|--------|--------|
| API | FastAPI (`api/`) + Postgres |
| AI provider | OpenAI only (prefer realtime mini models where applicable) |
| Surfaces | Text chat + tools first; Realtime wired to the **same tools** in parallel |
| UI | Dev console only until AI/tools feel solid (current Load/Save JSON is enough) |
| Data (near-term) | One `sessionId` row; payload splits into **inventory** + **resume view** |
| Delete semantics | Soft exclude from resume by default; archive/hard-remove are separate tools |
| Add semantics | Persist → **analyze/categorize** → attach metadata → optionally include on resume |
| Differentiation | Career inventory + views + tool ops — not “AI rewrites a document” |

---

## Baseline (already done)

- [x] Postgres (`resume_snapshots`) via Docker  
- [x] FastAPI: `/health`, `GET`/`PUT /resume/{session_id}`, CORS  
- [x] Payload v1 example + docs  
- [x] Vite `web/` Load/Save JSON harness  

---

## Phase 0 — Docs & payload v2 (inventory + view)

**Goal:** Stop hard-mutating a flat list as the only truth.

### Deliverables

- [ ] Update [resume-payload.md](./resume-payload.md) to **v2** shape  
- [ ] Update `api/resume-schema.example.json`  
- [ ] Optional: `normalize_payload_v1_to_v2()` helper for existing `demo` rows  

### Target shape (conceptual)

```text
{
  "basics": { ... },
  "summary": "",
  "inventory": {
    "skills": [],
    "experience": [ { id, ..., categories[], skills[], status } ],
    "projects":    [ { id, ..., categories[], skills[], status } ],
    "education":   [ { id, ... } ],
    "achievements":[ { id, ... } ]
  },
  "resume": {
    "includedExperienceIds": [],
    "includedProjectIds": [],
    "includedEducationIds": [],
    "includedAchievementIds": [],
    "sectionOrder": ["experience", "projects", "education", "achievements"]
  }
}
```

### Item `status`

| Value | Meaning |
|--------|---------|
| `active` | In inventory; may appear on resumes |
| `archived` | Hidden from new resumes; not hard-deleted |

### Acceptance

- Example JSON validates mentally against docs  
- `PUT`/`GET` still work with a v2 payload saved via the existing UI  

---

## Phase 1 — Deterministic tool API (no LLM)

**Goal:** Backend owns mutations. Curl-testable. AI will only call these later.

### Tool naming (prefer clarity over “delete”)

| Tool | Behavior |
|------|----------|
| `exclude_project_from_resume` | Soft: remove id from `resume.includedProjectIds` |
| `include_project_on_resume` | Soft: add id if present in inventory |
| `archive_project` | Set `status: archived` + exclude from resume |
| `add_project` | Create inventory item (+ include); enrichment in Phase 2 |
| `update_project` | Patch fields on inventory item |
| Same pattern for `experience` | Parallel endpoints |

### Deliverables

- [ ] `api/tools/` (or `api/services/resume_ops.py`) — pure functions on payload dict  
- [ ] Routes e.g. `POST /resume/{session_id}/tools/{tool_name}`  
- [ ] Shared load → mutate → save → return `{ resume, appliedTool, ... }`  
- [ ] Curl scripts or a short `docs/tool-smoke.md`  

### Acceptance

- Soft exclude leaves project in `inventory.projects`  
- Include restores it on the resume view  
- Archive excludes + sets status  
- Unknown id → `404` / clear error  

---

## Phase 2 — Enrichment on add

**Goal:** Adding via backend is not a dumb append.

### Pipeline for `add_project` / `add_experience`

1. Validate required fields + generate stable `id`  
2. Insert into inventory (`status: active`)  
3. Include on current resume view  
4. **Analyze** (OpenAI): propose `categories[]`, `skills[]`, optional short normalized description  
5. Merge enrichment onto the item (never trust model for ids / inclusion lists blindly)  
6. Persist + return enriched item  

### Deliverables

- [ ] `OPENAI_API_KEY` in `api/.env` / `.env.example`  
- [ ] `api/services/enrichment.py` — structured JSON output from model  
- [ ] Feature flag or `enrich=true` query/body so local tests can skip LLM  
- [ ] Store enrichment metadata (`enrichedAt`, `enrichmentModel`) optionally  

### Acceptance

- Add without key fails clearly or skips enrichment when disabled  
- Add with key returns categories/skills  
- Re-add / update does not wipe user-edited bullets unless asked  

---

## Phase 3 — Text chat + tool loop

**Goal:** Natural language → tool selection → Phase 1 ops → updated state.

### Deliverables

- [ ] `POST /chat` body: `{ sessionId, message }`  
- [ ] System prompt: app owns truth; only listed tools; prefer soft exclude  
- [ ] OpenAI tool/function calling bound **only** to Phase 1–2 tools  
- [ ] Response: `{ assistantMessage, toolsCalled[], payload, version }`  
- [ ] Minimal chat box in `web/` (dev console — not product UI)  

### Acceptance

- “Remove my music project” → `exclude_project_from_resume` (not archive) unless user says permanently  
- “Add a project …” → add + enrichment  
- Model cannot invent SQL or bypass tools  

---

## Phase 4 — Versioning & undo

**Goal:** Reversible changes without asking the LLM to reconstruct state.

### Deliverables

- [ ] Table or jsonb history: e.g. `resume_versions (session_id, version, payload, created_at, cause)`  
- [ ] Snapshot before each successful tool apply  
- [ ] Tool: `restore_version`  
- [ ] Chat can say “undo” → restore previous version  

### Acceptance

- Exclude → undo restores inclusion  
- History bounded (e.g. last N versions)  

---

## Phase 5 — Context selection

**Goal:** Don’t send entire career history on every turn.

### Deliverables

- [ ] Retriever: given user message, select candidate entities (name match, categories, recent)  
- [ ] Chat prompt gets **slice** of inventory + current inclusion lists  
- [ ] Log what context was sent (debug)  

### Acceptance

- Bullet edit on one job does not require full inventory in the prompt  
- Still correct when names are ambiguous (ask clarifying question / list candidates)  

---

## Phase 6 — Realtime voice (parallel track)

**Goal:** Same tools, different interface. Prefer OpenAI Realtime mini models.

### Deliverables

- [ ] `GET /realtime/token` (ephemeral client secret)  
- [ ] Browser WebRTC session (thin harness page or extend `web/`)  
- [ ] Realtime tool calls → **same** Phase 1–2 Python ops  
- [ ] After tool: push updated payload to client (poll or SSE later)  

### Rules

- Realtime model **never** writes DB directly  
- Soft-exclude language in voice instructions matches chat  

### Acceptance

- Spoken “hide my music project” → same DB outcome as text chat  
- Text and voice remain interchangeable for core tools  

---

## Phase 7 — Multi-resume views (true master profile)

**Goal:** One inventory, many resumes.

### Deliverables

- [ ] `resumes` collection or table: `resume_id`, name, inclusion lists, section order  
- [ ] Tools: `create_resume`, `switch_resume`, copy inclusions from another  
- [ ] Chat/voice scoped to “current resume”  

### Acceptance

- Exclude on Resume A does not exclude on Resume B  
- Inventory item still shared  

---

## Phase 8 — Product UI (only after AI feels solid)

**Goal:** Lock UI once tools, chat, and voice share one mutation path.

### Deliverables

- [ ] `landing → voice → home` shell  
- [ ] Live preview driven by inventory + inclusion  
- [ ] Apply/reject or instant apply for tool results  
- [ ] PDF export from structured state (not source of truth)  

---

## Tonight — suggested order

If working a single evening, aim for:

1. **Phase 0** — payload v2 docs + example (+ normalize if needed)  
2. **Phase 1** — `exclude` / `include` / `add_project` (add without enrichment first)  
3. Stretch: **Phase 2** enrichment **or** stub **Phase 3** chat with one tool  

Defer Phase 4–8 unless 0–1 are green.

---

## Out of scope until later

- Supabase auth / multi-user ownership  
- JD tailoring & recruiter scoring (architecture “future”)  
- Worker/outbox from old Express design  
- Polished templates, dark marketing UI  

---

## How we work

- One phase slice at a time; say **done** / **next**  
- Prefer curl + JSON console over UI polish  
- Every AI path must terminate in a **named tool** on the backend  

**Immediate next slice when you say “next”:** Phase 0 — rewrite payload docs + example to inventory + resume view.
