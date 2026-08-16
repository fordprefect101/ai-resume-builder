# Async Failure Playbook (V1)

## 1) DB unavailable
- Symptom: API returns dependency/transient failures, worker startup fails.
- Check: `DATABASE_URL` and DB connectivity.
- Action: restore DB, rerun migration, restart API/worker.

## 2) Outbox stuck in `pending`
- Symptom: rows accumulate in `event_outbox` with no worker progress.
- Check: worker process running and polling interval.
- Action: start `npm run worker`, inspect worker logs.

## 3) Repeated event failures
- Symptom: `event_outbox.status = failed`.
- Check: `last_error`, payload shape, handler assumptions.
- Action: fix handler bug, reset failed rows to pending only after fix.

## 4) Missing async status in UI/API
- Symptom: `/async-jobs/:correlationId` returns 404.
- Check: request correlation propagation and outbox write path.
- Action: ensure `correlationMiddleware` runs and capability routes that publish outbox events pass `correlationId`.

## 5) REST capability validation errors
- Symptom: `400` with `{ error: ... }` from capability routes (e.g. professional summary).
- Check: `sessionId` format (UUID) and route params vs [`apps/api/src/schemas/capabilitySchemas.js`](../apps/api/src/schemas/capabilitySchemas.js).
- Action: align caller payload with the schema for that route.

