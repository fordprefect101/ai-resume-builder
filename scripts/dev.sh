#!/usr/bin/env bash
# One-command local start: Postgres (docker compose), the API and the website.
# Ctrl+C stops the API and the website (the database is stopped too unless KEEP_DB=1).
# The API creates any missing tables from api/db/*.sql on startup, so nothing to apply here.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

command -v docker >/dev/null || { echo "docker is needed for the database"; exit 1; }
[ -f api/.env ] || echo "Note: api/.env is missing; copy api/.env.example and add OPENAI_API_KEY."
[ -d api/.venv ] || { python3 -m venv api/.venv && api/.venv/bin/pip install -q -r api/requirements.txt; }
[ -d web/node_modules ] || (cd web && npm ci)

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo; echo "Stopping..."
  for pid in "${PIDS[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  [ "${KEEP_DB:-0}" = "1" ] || docker compose stop
}
trap cleanup INT TERM EXIT

docker compose up -d --wait

(cd api && exec .venv/bin/uvicorn main:app --reload --port 8081) & PIDS+=($!)
(cd web && exec npm run dev) & PIDS+=($!)

echo "API: http://localhost:8081   Website: see the address printed by Vite (usually http://localhost:5173)"
wait
