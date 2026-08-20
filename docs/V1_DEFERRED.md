# Deferred after v1

Things we **chose not to do in v1**, plus follow-ups that auth will need later.  
This is the memory file so they are not rediscovered as missing features.

**Last updated:** 18 Aug 2026

---

## Auth that *is* in v1 (done)

Shipped with verify/reset URLs **logged** (and returned as `devVerifyUrl` / `devResetUrl`) until SMTP exists. UI polish is a follow-up, not more auth features.

- Email + password
- Verify email before login or save
- Forgot-password / reset via emailed link (link is **logged** until SMTP exists)
- Guests may build **one** resume in the current session without logging in
- Guest work is **not durable**: leave without save login → data is gone; they start over
- Save prompts login/signup if there is no session cookie
- Guest draft is **claimed only** on that save login — not on a random later login
- Logged-in user: **exactly one resume** (no New resume, no list)
- Returning users stay logged in via httpOnly cookie and can open that one resume

**Not in v1:** SMTP, OAuth.

Until a mail provider is wired, **log verify/reset URLs in the API** (dev-only). Do not pretend mail was sent.

---

## Do not forget: real email (SMTP / provider)

**Status:** no SMTP. Not in v1.

Email verification and password reset are required in the product, but outbound mail is **not** set up. When you add it later:

- Pick a provider (Resend, Postmark, SES, or generic SMTP)
- Set env vars, for example:
  - `EMAIL_FROM`
  - `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD`  
    **or** a provider API key such as `RESEND_API_KEY`
  - `PUBLIC_APP_URL` so verify/reset links point at the real frontend
- Stop logging raw tokens once mail actually sends
- Use the same path for:
  1. Signup verification
  2. Password reset
- Keep local/dev able to print the link if mail env is unset

Until then, accounts can still be created and verified by opening the logged URL.

---

## Chosen not to do in v1 (auth / product)

| Item | Why it waited |
|------|----------------|
| **SMTP / hosted email** | No provider; log verify/reset links |
| **OAuth** (Google, etc.) | Email + password only; not in v1 |
| **More than one resume** | Guest and logged-in users each get **one** resume |
| **Drafts list / New resume / switcher** | One resume; no list |
| **Durable guest draft** | Unsaved guest work is discarded; next visit starts over |
| **Claim guest draft on any login** | Claim **only** when they log in from save/export |
| **Force login before building** | Guests may start; login on save/export (cookie if already logged in) |
| **PDF / file export** | Gate it when it exists; do not build export in the auth slice |

---

## Chosen not to do in v1 (hardening leftovers)

| Item | Notes |
|------|--------|
| Soft **archive** tool (`status: archived` + exclude) | Hide/show is enough |
| `.env.example` / env-doc sync | Optional cleanup |
| Guest session TTL as a product feature | Guest data is ephemeral unless claimed at save/export |

---

## Explicitly v2+ (not a v1 gap)

These are product expansions, not unfinished v1:

- Custom sections (`create_section`)
- Multiple resumes per user, or multiple **views** of one inventory
- Source matching (e.g. GitHub ↔ claims)
- Field **update** / bullet-edit tools after add
- Production marketing site
- AI editing of basics (basics stay manual-only)
- OAuth sign-in
- Real email delivery (SMTP / Resend / etc.)

---

## Related

- [V1_REMAINING.md](./V1_REMAINING.md) — what is still left to build in v1  
- [resume-payload.md](./resume-payload.md) — payload shape  
