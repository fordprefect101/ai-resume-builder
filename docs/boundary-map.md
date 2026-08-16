# Logical Boundary Map

This map documents where current modules belong as the codebase transitions
from `backend/` centric layout to layered boundaries.

## API Runtime (currently `backend/server.js`)
- Transport, auth middleware, route registration.

## Application Services (`apps/api/src/services`)
- `resumeCapabilitiesService.js`:
  - orchestrates semantic resume use-cases (e.g. professional summary generation)
  - delegates business logic and persistence

## Capability schemas (`apps/api/src/schemas`)
- `capabilitySchemas.js`: Zod validation for capability inputs (shared with REST handlers).

## Domain Layer (`packages/domain/src`)
- `resume/summary.js`: deterministic summary logic

## Persistence Layer (`backend/repositories`)
- `persistence.js`: conversation + snapshot persistence
- `outbox.js`: event outbox and async job status persistence
- `resumeLoader.js`: snapshot loading strategy

## Worker Layer (`services/workers`)
- `outboxWorker.js`: event consumption and status updates

## Frontend resume rendering (`src/react/resume-engine`)

Internal subsystem for **print-oriented layouts**: shared date/bullet/content helpers, contact icons, `ResumePageShell` / `ResumeFold` section shells, and section entries (`ExperienceEntry`, `EducationEntry`, `ProjectEntry`). React templates under [`src/react/components/templates/`](../src/react/components/templates/) compose these primitives; product schema stays in [`ResumeContext`](../src/react/context/ResumeContext.tsx) / [`types.ts`](../src/react/types.ts).
