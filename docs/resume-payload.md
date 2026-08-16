# Resume payload shape (v1)

Stored in `resume_snapshots.payload`. Example: `backend/resume-schema.example.json`.

## Top level

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `basics` | object | yes | Identity + contact |
| `summary` | string | no | Empty string OK |
| `skills` | string[] | yes | Use `[]` if none |
| `experience` | object[] | yes | Use `[]` if none |
| `projects` | object[] | yes | Use `[]` if none |
| `education` | object[] | yes | Use `[]` if none |
| `achievements` | object[] | yes | Use `[]` if none |

## `basics`

| Field | Type | Required |
|-------|------|----------|
| `fullName` | string | yes (can be `""`) |
| `email` | string | no |
| `phone` | string | no |
| `location` | string | no |
| `links` | `{ label, url }[]` | yes (`[]` OK) |

## `experience[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | **yes** — stable id for AI tools |
| `company` | string | yes |
| `title` | string | yes |
| `location` | string | no |
| `startDate` | string | no — prefer `YYYY-MM` |
| `endDate` | string | no — omit or `""` if current |
| `bullets` | string[] | yes (`[]` OK) |

## `projects[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | **yes** |
| `name` | string | yes |
| `description` | string | no |
| `technologies` | string[] | yes (`[]` OK) |
| `bullets` | string[] | yes (`[]` OK) |
| `url` | string | no |

## `education[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | **yes** |
| `institution` | string | yes |
| `degree` | string | yes |
| `location` | string | no |
| `startDate` | string | no |
| `endDate` | string | no |
| `details` | string[] | yes (`[]` OK) |

## `achievements[]`

| Field | Type | Required |
|-------|------|----------|
| `id` | string | **yes** |
| `title` | string | yes |
| `date` | string | no |
| `description` | string | no |

## Out of scope for v1

- Master profile vs multiple resumes
- Version history / undo ops
- Section ordering metadata
- Strict server-side validation (next optional step)