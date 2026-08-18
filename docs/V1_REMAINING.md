# V1 remaining work

What is left to ship a **conversational resume editor** (not a full product platform).  
Custom sections, multi-resume views, GitHub matching, and field-update tools are **out of scope for v1** (see v2+ below).

**Last updated:** 17 Aug 2026

---

## Already in place (baseline)

- Persistence (`resume_snapshots`) + short undo stack  
- Payload **v3**: `inventory.sections` + `resume.includedIds` + `sectionOrder`  
- `normalize_payload` for older shapes on read/write  
- Generic tools: `add_item`, `exclude_from_resume`, `include_on_resume`, `reorder_sections`  
- Registry-driven enrich / bullet polish (`section_registry` + `enrich_section_item`)  
- Text chat tool loop + Realtime voice harness (**edit** mode)  
- PDF import endpoint (output may still be older shape; normalize upgrades it)

---

## V1 remaining

### 1. Intake mode (voice + PDF) — ✅ complete

Cold start when the user has **no** resume yet.

- Separate mode-aware Realtime / chat instructions from **edit** mode  
- Intake-only `set_basics` / `set_skills` / `complete_intake` tools  
- Explicit confirmation required before optional fields are saved blank  
- Adaptive skills questions; technical users are asked for GitHub username only  
- Progressive context returned after every successful intake tool call  
- Walk list sections (experience, projects, education, achievements) via `add_item`  
- Dual entry: **voice cold start** vs **PDF upload**, then continue in edit mode  

### 2. Live resume preview — ✅ complete

- Side-by-side structured editor + resume document (desktop)
- Render the current view from `sectionOrder` + `includedIds` + section items  
- Section reorder and item show/hide controls persist through generic tools
- Preview refreshes after editor, voice, load, PDF, and JSON save results
- Responsive stacked layout on smaller screens
- JSON console retained under developer tools only

### 3. Dual-intake UI shell — ✅ complete

- Landing / first screen: “I have a PDF” vs “Start from voice”  
- Wired to `/import-resume-pdf` and Realtime intake session  
- New guest session ids are created by `POST /intake/start`

### 4. PDF import → native v3 — ✅ complete

- LLM extraction contract requests schemaVersion 3 directly
- Deterministic importer emits `sections` + `includedIds` without a v2 intermediate
- Flat/legacy-like model output is still accepted and normalized into v3
- Keep `normalize_payload` as a safety net for legacy rows

### 5. Item order within a section (optional but common)

- Tool: `reorder_items(section, itemIds)`  
- Persist order as list order in `inventory.sections[section].items` (or an explicit order field if preferred)

### 6. Basics at intake only (policy lock)

- Capture `inventory.basics` during intake  
- Confirm no chat/voice tools mutate basics after intake  
- Document this in prompts so the model does not invent update tools

### 7. Hardening

- Guest session TTL / cleanup  
- Clearer API errors for unknown section / missing required fields  
- Optional: soft **archive** tool (status + exclude) if users need “retire” vs hide  
- Env / `.env.example` kept accurate for chat, enrich, realtime models

### 8. Context slicing (chat + Realtime) — ✅ complete

- Text chat receives a bounded, query-aware candidate slice
- Deterministic matching uses ids, labels, section hints, categories, skills, and bullets
- Ambiguous close matches are flagged so the model asks instead of guessing
- Realtime starts with section counts and uses read-only `search_resume_context`
- Context search does not create undo snapshots or increment resume versions
- Chat responses expose `contextUsed` for debugging without server-side PII logging

---

## Suggested v1 build order

1. ~~Live preview (makes every tool change visible)~~ ✅
2. ~~Intake mode (voice) + dual-intake UI~~ ✅
3. ~~PDF → native v3~~ ✅
4. ~~Context slicing~~ ✅
5. Hardening + optional `reorder_items`  

Preview first is recommended so intake and edit both have something to show.

---

## Explicitly v2+ (not v1)

- Custom sections (`create_section`)  
- Multi-resume views (one inventory, many resumes)  
- Source matching (e.g. GitHub ↔ claims)  
- Field **update** / bullet-edit tools after add  
- Auth, multi-user, production marketing site  

---

## Related docs

- [resume-payload.md](./resume-payload.md) — v3 payload shape  
- [AI_IMPLEMENTATION_PLAN.md](./AI_IMPLEMENTATION_PLAN.md) — original phased plan (partially superseded by generic tools)  
- [PROGRESS.md](./PROGRESS.md) — rebuild status notes  
