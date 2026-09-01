# Orchestrator — thicken the conductor, keep the instrument

**Idea:** we already own the resume (schema + tools + Postgres). More intelligence should not rewrite that. It should **conduct** flow and smart checks while **only** mutating through tools.

**Last updated:** 21 Aug 2026

---

## One-line rule

> Tools + schema = source of truth.  
> Orchestrator = plan, gates, and which intelligence step runs next.  
> The model never gets the keys to the house (no freeform full-payload rewrite).

---

## What we have today (the instrument)

| Layer | Role |
|--------|------|
| **Payload v3** | `inventory` = career truth; `resume` = view (`includedIds`, `sectionOrder`, summary) |
| **Tools** | Only write path: `add_item`, include/exclude, reorder, `set_skills`, `complete_intake`, … |
| **Gates** | Basics are UI-only; `intake.basicsVerified` before voice/list tools |
| **Modes** | Intake vs edit instructions on Realtime / chat |
| **Context** | Sliced / searched context — not the whole resume in every prompt |

Realtime and chat already act as a **thin** conductor: prompts + tool loop. That is intentional and incomplete.

---

## What an orchestrator adds (the conductor)

A layer **above** tools that:

1. Knows **stage** (e.g. basics → skills → experience → projects → education → achievements → polish → export)
2. Chooses the **next question**, **next tool**, or **when to stop**
3. Enforces **policy** (no basics edits, confirm blank optionals, one question at a time)
4. Runs **named intelligence jobs** as steps (gap check, bullet quality, role tailor) — then applies results **only** via tools

```text
User speech / UI
      │
      ▼
┌─────────────┐
│ Orchestrator │  stage · policy · next step · smart checks
└──────┬──────┘
       │ calls
       ▼
┌─────────────┐
│    Tools     │  only mutators
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Payload DB  │  inventory + resume view
└─────────────┘
```

Orchestrator does **not** unlock control of the resume. Control already lives in tools + schema. Orchestrator decides **how intelligence uses** that control.

---

## How to proceed (build order)

1. **Keep tools as the only write path** — never accept a model-produced full resume JSON as truth.
2. **Make the state machine explicit** — formalize intake/edit stages beyond today’s flags (`intake.status`, `basicsVerified`). Persist stage so reconnect / chat / voice share one conductor.
3. **Add intelligence as named jobs**, one at a time, e.g.:
   - suggest missing bullets for an item  
   - tighten / polish bullets (already partly enrichment)  
   - tailor view for a job description (change `includedIds` / order / summary via tools)  
   - “one page” density check (advisory first; mutations still via tools)  
4. **Later expansions** still orchestrator → tools on the same inventory: multi-view / role resumes, version history, JD tailoring with provenance — see [V2.md](./V2.md).

---

## Intelligence jobs (contract shape)

Each job should be boring and inspectable:

| Field | Meaning |
|--------|---------|
| `name` | e.g. `suggest_bullets`, `tailor_for_jd` |
| `input` | session id, optional item/section, optional JD text |
| `output` | structured proposals (not applied yet) **or** a list of tool calls |
| `apply` | only through existing tool endpoints / tool runner |

Prefer: **propose → user or policy confirms → tool apply**.  
Auto-apply only for low-risk polish already covered by enrichment flags.

---

## Policy the conductor must own

- Never mutate basics via AI (name, email, phone, location, LinkedIn, GitHub)
- Confirm blank optional fields before `add_item`
- Soft exclude over hard delete
- Intake: one question at a time; `complete_intake` only when skills + all sections addressed
- Edit: `search_resume_context` before mutating an existing item when ambiguous
- Voice hang-up is client-owned (`stop()`); optional `end_voice_session` tool may *request* it — button remains required

---

## Traps to avoid

| Trap | Why it hurts |
|------|----------------|
| Mega-orchestrator that “understands everything” and mutates freely | Hallucinations; loses inventory/view split |
| Model dumps a full resume blob | Bypasses tools, undo, validation, enrich |
| Mixing product chrome with resume paper | Export/templates become messy |
| Building memory/embeddings before a clear state machine | Retrieval without a conductor is noise |
| Claiming five template galleries before export | Skin without a file to send |

---

## Success criteria

- Every resume change is explainable as **tool X with args Y**
- Intake/edit can resume after refresh because **stage is persisted**
- New “smart” features land as **jobs + tool apply**, not new write APIs that skip the registry
- Voice and text chat share the **same** conductor rules

---

## Related

- [V2.md](./V2.md) — project direction and target architecture  
- [resume-payload.md](./resume-payload.md) — inventory vs view  
- [boundary-map.md](./boundary-map.md) — code layout
