# Resume payload shape (v2)

Stored in `resume_snapshots.payload`. Example: `api/resume-schema.example.json`.

**Idea:** `inventory` is the career truth. `resume` is a view (what to show + order). Soft remove = drop an id from an inclusion list; do not delete the inventory item.

## Top level

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schemaVersion` | number | yes | Use `2` |
| `inventory` | object | yes | Canonical career data |
| `resume` | object | yes | Current resume view |

## `inventory`

| Field | Type | Required |
|-------|------|----------|
| `basics` | object | yes |
| `skills` | string[] | yes (`[]` OK) |
| `experience` | object[] | yes |
| `projects` | object[] | yes |
| `education` | object[] | yes |
| `achievements` | object[] | yes |

### `inventory.basics`

| Field | Type | Required |
|-------|------|----------|
| `fullName` | string | yes (can be `""`) |
| `email` | string | no |
| `phone` | string | no |
| `location` | string | no |
| `links` | `{ label, url }[]` | yes (`[]` OK) |

### Shared item fields

Most inventory items include:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | **Required**, stable (for tools) |
| `status` | `"active"` \| `"archived"` | Default `active` |
| `categories` | string[] | Enrichment (Phase 2); `[]` OK |
| `skills` | string[] | Enrichment; `[]` OK |

### `inventory.experience[]`

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

### `inventory.projects[]`

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

### `inventory.education[]` / `achievements[]`

Same pattern: stable `id`, content fields, `status`. Enrichment optional.

## `resume` (view)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `title` | string | yes | e.g. "General Resume" |
| `summary` | string | no | Per-resume blurb |
| `includedExperienceIds` | string[] | yes | Subset of inventory ids |
| `includedProjectIds` | string[] | yes | |
| `includedEducationIds` | string[] | yes | |
| `includedAchievementIds` | string[] | yes | |
| `sectionOrder` | string[] | yes | e.g. `experience`, `projects`, … |

## Soft vs hard removal

| Intent | Action |
|--------|--------|
| Hide from this resume | Remove id from the matching `included*Ids` |
| Keep but retire | Set `status: "archived"` and exclude from view |
| Truly erase | Rare; separate hard-delete tool later |

## Intake (later)

- **Voice cold start** and **PDF import** both produce this v2 shape.
- First resume view usually includes all `active` inventory ids.

## Out of scope for Phase 0

- Multi-resume rows in DB (Phase 7)
- Server validation / tools / enrichment