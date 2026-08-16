# Hosting guide — AI Resume Builder

This document describes how to host each part of the stack in production. It matches the repo layout today: **React SPA** (Vite), **Express API** (`backend/`), **outbox worker** (`services/workers/outboxWorker.js` via `npm --prefix backend run worker`), and **Supabase + Postgres** (optional but recommended for persistence and auth).

---

## 1. What you are deploying

| Component | Source | Role |
|-----------|--------|------|
| **Frontend** | Root: `npm run build:react` → `dist-react/` | Browser UI; calls API via `VITE_API_BASE_URL` |
| **API** | `backend/` — `npm start` → `node server.js` | REST routes (`/resume`, `/extract-resume`, `/token`, etc.), OpenAI, PDF import |
| **Worker** | Started as `npm --prefix backend run worker` | Processes outbox jobs when `DATABASE_URL` is set (requires Postgres) |
| **Database** | Supabase Postgres (or any Postgres) | Snapshots, sessions, outbox tables when migrations run |
| **Auth (optional)** | Supabase Auth | SPA: `VITE_SUPABASE_*`; API verifies JWT via JWKS |

Local dev proxies API paths to `localhost:8081` (`vite.react.config.ts`). **Production build has no proxy** — the SPA must use an absolute API URL.

---

## 2. Prerequisites

1. **Domain (optional)** — e.g. `app.example.com` (frontend), `api.example.com` (API).  
2. **HTTPS** — required for mic / voice (browser APIs).  
3. **Secrets** — OpenAI key, Supabase keys, `DATABASE_URL` if using DB features.  
4. **CORS** — `backend/server.js` uses `cors()` with default permissive settings; for stricter production CORS, configure allowed origins explicitly later.

---

## 3. Supabase (database + auth)

Use one Supabase project for Postgres and (if you want signed-in users) Auth.

### 3.1 Create project

1. Go to [supabase.com](https://supabase.com) → New project → choose region → set a database password.

### 3.2 Connection string (`DATABASE_URL`)

1. **Project Settings → Database → Connection string → URI** (use **Transaction** pooler or direct URI as recommended for your host).  
2. Format: `postgresql://USER:PASSWORD@HOST:5432/postgres`  
3. Set this as **`DATABASE_URL`** on the **API** and **worker** (same value).

### 3.3 Auth keys (frontend + API verification)

1. **Project Settings → API**  
   - **`URL`** → use as `VITE_SUPABASE_URL` (frontend) and optionally `SUPABASE_URL` (backend JWKS).  
   - **`anon` `public`** key → `VITE_SUPABASE_ANON_KEY` (frontend only; safe to expose in the browser).  

2. **Backend JWT verification** (`backend/auth/supabaseJwt.js`): set either  
   - `SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co`, or  
   - `SUPABASE_PROJECT_REF=YOUR_PROJECT_REF`  

   Do **not** put the service role key in the frontend.

### 3.4 Schema migrations

From your machine (with `DATABASE_URL` pointing at the same DB):

```bash
cd backend && npm install && npm run migrate
```

Run this once per environment (staging/production) before relying on durable resume storage or the worker.

---

## 4. Environment variables (reference)

### 4.1 Frontend (build-time — Vite)

Set in the **static host** (Vercel / Netlify / Cloudflare) as **build** environment variables.

| Variable | Required | Purpose |
|----------|----------|---------|
| `VITE_API_BASE_URL` | **Yes** in prod | Full origin of API, no trailing slash. Example: `https://api.example.com` |
| `VITE_SUPABASE_URL` | If using auth | Same as Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | If using auth | Supabase anon key |

`src/react/utils/apiBase.ts` uses `VITE_API_BASE_URL`; if unset, requests use relative URLs (only OK behind dev proxy).

### 4.2 Backend API (`backend/.env` locally; platform env in prod)

| Variable | Required | Purpose |
|----------|----------|---------|
| `PORT` | Auto on PaaS | Host injects `PORT`; locally defaults to **8081** (`server.js`) |
| `OPENAI_API_KEY` | Yes for AI/voice flows | OpenAI |
| `DATABASE_URL` | For durable DB + worker | Postgres URI |
| `SUPABASE_URL` or `SUPABASE_PROJECT_REF` | If verifying JWT | JWKS URL for token verification |

See `backend/.env.example` for a minimal template.

### 4.3 Worker

Same as backend for **`DATABASE_URL`** (and anything `outboxWorker` / shared code reads via `backend/.env`). Locally the worker loads `backend/.env`. On platforms, set variables in the **worker service** dashboard.

Optional: `OUTBOX_POLL_MS` (default `3000`).

**Note:** If `DATABASE_URL` is unset, the API can still run with in-memory behavior for some paths; the **worker exits** if DB is disabled (`outboxWorker.js`).

---

## 5. Frontend — static hosting

**Build command (repo root):**

```bash
npm install && npm run build:react
```

**Output directory:** `dist-react/` (see `vite.react.config.ts`).

**SPA routing:** If you add client-side routes later, configure “single-page app” fallback to `index.html`. Below includes that where relevant.

---

### 5.1 Vercel

1. Import Git repo → **New Project**.  
2. **Framework preset:** Vite (or “Other”).  
3. **Root Directory:** repository root (where root `package.json` lives).  
4. **Build Command:** `npm run build:react`  
5. **Output Directory:** `dist-react`  
6. **Environment Variables:** add `VITE_API_BASE_URL`, and optionally `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.  
7. Deploy.

**SPA fallback (if needed):** add `vercel.json` at repo root:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

(Only if you use deep links that must hit the SPA.)

**Custom domain:** Project → Settings → Domains → add `app.example.com`.

---

### 5.2 Netlify

1. **New site from Git** → pick repo.  
2. **Base directory:** leave blank (root).  
3. **Build command:** `npm run build:react`  
4. **Publish directory:** `dist-react`  
5. **Environment variables:** same `VITE_*` as above.  
6. Deploy.

**SPA fallback:** `public/_redirects` is not used by this Vite root (`src/react`); for Netlify add a **`dist-react`-time** file via Vite `public` if you add one, or use **Netlify** `_redirects` in **publish dir**:

Create `src/react/public/_redirects` (if you add `public` under react root) or configure in **netlify.toml**:

```toml
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

---

### 5.3 Cloudflare Pages

1. Connect repo → **Build configuration:**  
   - Build command: `npm run build:react`  
   - Build output directory: `dist-react`  
2. **Environment variables** (Production + Preview): `VITE_*` as above.  
3. **SPA:** Settings → **Functions / Redirects** or add `_routes.json` / Pages redirect rule: serve `index.html` for non-file routes if you introduce deep linking.

---

## 6. Backend API — Node / Express

**Working directory:** `backend/`  
**Install:** `npm install`  
**Start:** `npm start` → `node server.js`  
**Port:** bind to `process.env.PORT` (platforms set this automatically).

---

### 6.1 Railway

1. **New Project → Deploy from GitHub** → select repo.  
2. Add a **service** → set **Root Directory** to `backend`.  
3. **Start Command:** `npm start` (default if `package.json` has `start`).  
4. **Variables:** `OPENAI_API_KEY`, `DATABASE_URL`, `SUPABASE_URL` (or `SUPABASE_PROJECT_REF`), etc.  
5. Deploy → Railway assigns a URL like `https://your-service.up.railway.app`.  
6. Use that origin as **`VITE_API_BASE_URL`** on the frontend (rebuild frontend after API URL is stable).  
7. **Custom domain:** Service → Settings → Networking → generate domain or add `api.example.com`.

Repeat **migrations** against production DB from CI or your laptop:

`cd backend && DATABASE_URL=... npm run migrate`

---

### 6.2 Render

1. **New → Web Service** → connect repo.  
2. **Root Directory:** `backend`  
3. **Build Command:** `npm install`  
4. **Start Command:** `npm start`  
5. **Environment:** same variables as Railway.  
6. Render provides `https://your-service.onrender.com`.  
7. Cold starts on free tier — OK for demos; use paid instance for voice latency-sensitive demos.

**Custom domain:** Service → **Custom Domains**.

---

### 6.3 Fly.io (outline)

1. Install `flyctl`, run `fly launch` in `backend/` (or use a Dockerfile).  
2. Set secrets: `fly secrets set OPENAI_API_KEY=... DATABASE_URL=...`  
3. Ensure `internal_port` matches `PORT` Fly sets.  
4. Attach custom domain in Fly dashboard.

(Fly is flexible but more manual than Railway/Render for a simple Express app.)

---

## 7. Worker (outbox)

The worker is **a separate long-running process**. It must share **`DATABASE_URL`** (and any env required by `ensureSchema` / outbox code) with the API.

**Start command (from repo root):**

```bash
npm --prefix backend install && npm --prefix backend run worker
```

Or with working directory `backend`:

```bash
npm install && npm run worker
```

### 7.1 Railway — second service

1. Same repo → **New Service** → **Empty service** or duplicate from Git.  
2. **Root Directory:** `backend`  
3. **Start Command:** `npm run worker`  
4. **Variables:** copy `DATABASE_URL` (and Supabase vars if ever needed by shared modules).  
5. No HTTP port required — disable public networking if the platform allows.

### 7.2 Render — Background Worker

1. **New → Background Worker**  
2. **Root Directory:** `backend`  
3. **Build:** `npm install`  
4. **Start:** `npm run worker`  
5. Same env as API for DB.

---

## 8. Wire frontend ↔ API

1. Deploy API → note **HTTPS origin** (no trailing slash).  
2. Set **`VITE_API_BASE_URL`** to that origin on Vercel/Netlify/Cloudflare.  
3. **Redeploy frontend** (Vite bakes env at build time).  
4. Smoke-test in browser: open DevTools → Network — requests should go to `https://api.../resume/...`, not relative `/resume`.

---

## 9. Voice / WebRTC checklist

- Site served over **HTTPS**.  
- User grants **microphone** permission.  
- Browser can reach **OpenAI Realtime** endpoints (your backend issues tokens — keep `OPENAI_API_KEY` on server only).  
- If something fails only on mobile: check mixed content (HTTP page calling HTTPS API) and corporate VPN/firewalls.

---

## 10. Post-deploy smoke test

| Step | Action |
|------|--------|
| 1 | Open SPA URL — landing loads, no console errors about missing env |
| 2 | Anonymous flow — create or load resume if supported without login |
| 3 | Auth flow — sign in if Supabase configured; API calls include `Authorization` (`authFetch`) |
| 4 | Save resume — `PUT /resume/:sessionId` returns OK |
| 5 | Voice — short session; transcript → extract if you use that path |
| 6 | Worker — if using DB/outbox, confirm worker logs show ticks / no crash |

---

## 11. Optional: one VPS (Docker-style mental model)

If you prefer a single machine:

- **Reverse proxy** (Caddy or nginx): TLS termination.  
- **Static files:** serve `dist-react` from `/`.  
- **Node:** `pm2` or systemd for `backend` (`npm start`) and second process for `npm run worker`.  
- **Postgres:** local install or managed Supabase still recommended.

This repo does not ship a production Dockerfile by default; add one if you standardize on containers.

---

## 12. Quick reference — suggested split

| Platform | Good for |
|----------|----------|
| **Vercel** | React SPA (`dist-react`) |
| **Railway** or **Render** | Express API + worker (two services) |
| **Supabase** | Postgres + Auth + JWKS |

You can swap vendors (e.g. Netlify + Fly) as long as **build output**, **env vars**, and **HTTPS** rules above stay satisfied.
