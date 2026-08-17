# Resume payload shape (v3)

Stored in `resume_snapshots.payload`. Example: `api/resume-schema.example.json`.

**Idea:** `inventory` is the career truth. `resume` is a view (what to show + order). Soft remove = drop an id from `resume.includedIds[section]`; do not delete the inventory item.

List sections live under `inventory.sections` so built-ins and future custom sections share one shape. Tool calls take `section` + `itemId` (or `section` + `fields` for add), not per-section tool names.

Section field rules (required fields, enrich/polish flags) live in `api/section_registry.py`.

## Top level

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schemaVersion` | number | yes | Use `3` |
| `intake` | object | yes | Intake status + confirmation flags |
| `inventory` | object | yes | Canonical career data |
| `resume` | object | yes | Current resume view |

`intake.status` is `not_started`, `in_progress`, or `complete`. Basics and
skills confirmation flags let intake complete only after those steps and all
built-in sections have been explicitly addressed.

## `inventory`

| Field | Type | Required |
|-------|------|----------|
| `basics` | object | yes |
| `skills` | string[] | yes (`[]` OK) |
| `sections` | object | yes | Map of section key → `{ title, items }` |

`basics` and flat `skills` are **not** list sections for soft-exclude tools. Basics are intake-only.

### `inventory.basics`

| Field | Type | Required |
|-------|------|----------|
| `fullName` | string | yes (can be `""`) |
| `email` | string | no |
| `phone` | string | no |
| `location` | string | no |
| `links` | `{ label, url }[]` | yes (`[]` OK) |

### `inventory.sections[sectionKey]`

| Field | Type | Notes |
|-------|------|-------|
| `title` | string | Display label (e.g. `"Education"`) |
| `items` | object[] | Entries with stable `id` |

Built-in keys: `experience`, `projects`, `education`, `achievements`. Custom keys may be added later; same bag shape.

### Shared item fields

Most section items include:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | **Required**, stable (for tools) |
| `status` | `"active"` \| `"archived"` | Default `active` |

Experience/projects may also have `categories[]`, `skills[]`, `bullets[]` (enrichment / polish). Education stays a credential line (degree, institution, dates) — research/awards belong in other sections.

### `sections.experience.items[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | yes |
| `company` | string | yes |
| `title` | string | yes |
| `location` | string | no |
| `startDate` | string | no (`YYYY-MM`) |
| `endDate` | string | no |
| `bullets` | string[] | yes |
| `categories` | string[] | yes (`[]` OK) |
| `skills` | string[] | yes (`[]` OK) |
| `status` | string | yes |

### `sections.projects.items[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | yes |
| `name` | string | yes |
| `description` | string | no |
| `technologies` | string[] | yes |
| `bullets` | string[] | yes |
| `url` | string | no |
| `categories` | string[] | yes |
| `skills` | string[] | yes |
| `status` | string | yes |

### `sections.education.items[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | yes |
| `institution` | string | yes |
| `degree` | string | yes |
| `location` | string | no |
| `startDate` | string | no |
| `endDate` | string | no |
| `details` | string[] | no — prefer empty; do not store research here |
| `status` | string | yes |

### `sections.achievements.items[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | yes |
| `title` | string | yes |
| `date` | string | no |
| `description` | string | no |
| `status` | string | yes |

## `resume` (view)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `title` | string | yes | e.g. "General Resume" |
| `summary` | string | no | Per-resume blurb |
| `includedIds` | object | yes | Map `sectionKey` → `string[]` of item ids |
| `sectionOrder` | string[] | yes | Order of section keys on this resume |

Example: `includedIds.projects = ["proj_music"]`. Soft hide = remove that id from the list for that section.

## Soft vs hard removal

| Intent | Action |
|--------|--------|
| Hide from this resume | Remove id from `resume.includedIds[section]` |
| Keep but retire | Set `status: "archived"` and exclude from view |
| Truly erase | Rare; separate hard-delete tool later |

## Legacy v2

Older payloads used top-level `inventory.experience` / `projects` / … arrays and camelCase `includedExperienceIds`, `includedProjectIds`, etc.

`api/payload_normalize.py` upgrades those to v3 (`sections` + `includedIds`) on read. Do not write new v2 shapes.

## Intake

- **Voice cold start** and **PDF import** should produce **v3**.
- First resume view usually includes all `active` item ids per section.

## Out of scope here

- Multi-resume rows in DB
- Field-update tools (add + show/hide only for list sections)
