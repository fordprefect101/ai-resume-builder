# Contact checks

Every contact detail climbs a ladder as far as it can. The person sees which rung each field reached.

| Rung | Meaning | How |
|------|---------|-----|
| 1 Looks right | The shape is valid | Instant, ordinary code (`api/contact/shape.py`) |
| 2 Exists | It is real and reachable | A quick lookup online, in the background |
| 3 Proven yours | Only the owner could have done it | **Not built yet** (emailed codes, "Sign in with GitHub") |

"Exists" is not "yours": a real GitHub account or a working email domain could belong to anyone.

## What each field reaches today

| Field | Rung 1 | Rung 2 |
|-------|--------|--------|
| Email | Valid shape; common typos suggested ("gmial.com", never blocks) | The domain can receive mail (it cannot tell if the mailbox exists) |
| Phone | Valid for its country when a `+` country code is given; otherwise a note | None (would need paid text messages) |
| GitHub | Valid username shape | The account exists (GitHub's public lookup) |
| LinkedIn | Valid profile link shape | None (LinkedIn blocks automatic lookups; the screen says so) |
| Portfolio | Valid web address | The page opens |
| Project link (Projects section) | Valid web address | A GitHub repository is public (languages recorded); any other link opens |

Every rung 2 lookup answers `exists`, `not_found` or `unavailable` ("couldn't check right now": a timeout, a rate limit or an outside service being down). `unavailable` is retried on the next save and never blames the person.

A GitHub repository we cannot see may be private or misspelled; GitHub answers the same for both. The person can tick "This repository is private", which shows "Private, not checked" instead of a warning.

## The gate

"Save and confirm" is refused only when a filled-in contact detail is plainly broken at rung 1 (for example an email with no "@", an invalid GitHub name, a `localhost` portfolio). Rung 2 results, typo suggestions and a phone number without a country code only warn. The gate is judged from the current values every time, never from stored results. A broken project link only warns.

## Where things live

| File | Job |
|------|-----|
| `api/contact/shape.py` | Rung 1 checks and tidying of what people type |
| `api/contact/safe_fetch.py` | The only code allowed to open a link someone typed (see below) |
| `api/contact/reach.py` | Email domain and web page lookups |
| `api/contact/github.py` | GitHub account, repository and languages lookups |
| `api/contact/status.py` | Stores results in `basics.contactChecks`, expires them when a field changes, builds the badges and the gate |
| `api/contact/lookups.py` | Runs the lookups for the personal details and merges the answers |
| `api/contact/project_links.py` | The same for each Projects item's link, stored as `linkCheck` |

Results are tied to a fingerprint of the exact text checked, so editing a field resets its badge, and an unchanged field keeps its result (which also means GitHub is not asked again on every page load).

## When checks run

- **Rung 1:** on every save. Contact details are checked in `update_basics`; project links in the single save door (`_save_payload` in `api/main.py`), so voice, chat, typed and imported saves all get it.
- **Rung 2:** in the background after the reply has gone out (`_run_background_lookups` in `api/main.py`). The slow lookups run with no database connection open. The answers are then written under a row lock, through the save door, as a "Contact details checked" or "Project links checked" history entry with no undo copy. An answer is kept only if its field still holds the text that was checked.
- **Check again:** `POST /resume/{id}/basics/check` and `POST /resume/{id}/links/check` re-run everything. `GET /resume/{id}/contact-status` returns the badges (`contactStatus`, `projectLinks`); the website asks it every 3 seconds, up to 7 times, until the lookups have answers.
- `POST /resume/{id}/tools/set_link_private` marks a project link private or not.

If the server restarts mid-lookup, that lookup is lost; "Check again" is the recovery.

## Opening links safely

`safe_fetch.py` refuses anything that is not an ordinary public website: non-web link types, links with a login inside, ports other than 80 and 443, `localhost` and `.local` names, and any address that is private, loopback or link-local (including numbers written in disguise such as `2130706433`). Every address a name resolves to must be public, the connection goes to the exact address that was checked, and every redirect is checked again. At most 3 redirects, 5 seconds, 64 KB. Being strict will occasionally refuse an unusual but honest site; that is the intended side to err on.

## Privacy

- Contact details are never sent to an AI model: `intake_context` passes only the full name, and the check `contact_on_save_and_privacy` searches everything the assistant receives for planted contact details.
- Lookups send only what they need: the part of the email after the "@" to DNS, the username or repository to GitHub, the link to the site itself.
- The badges are for the person; they are not printed on the resume. Project link results, including GitHub languages, are information only and never back or mark a point.

## Checks

All in `evals/run_evals.py`, with no internet: `contact_shape_rules`, `safe_fetch_refuses_dangerous_links`, `contact_exists_lookups` (recorded answers), `contact_status_and_gate`, `contact_on_save_and_privacy`, `contact_background_lookups`, `project_link_checks`, and the freshness check on the example record. The real database and background task are only proven by `evals/db_walkthrough.py`.
