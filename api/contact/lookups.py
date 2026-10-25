"""Runs the rung 2 "exists" lookups for saved contact details, and merges the answers.

run_lookups does the slow outside calls and touches no database. apply_results puts the
answers into the latest saved details, keeping only those whose field still holds the
exact text that was checked.
"""

from __future__ import annotations

from datetime import datetime

from contact import github, reach, status

# LinkedIn blocks automatic lookups and phone numbers cannot be proven without text
# messages, so neither has a rung 2 lookup.
LOOKUP_FIELDS = ("email", "github", "portfolio")


def _lookup(field: str, value: str) -> dict:
    if field == "email":
        return reach.check_email_domain(value)
    if field == "github":
        return github.lookup_user(value.rstrip("/").rsplit("/", 1)[-1])
    return reach.check_page(value)


def run_lookups(basics: dict, *, force: bool = False) -> dict:
    """{field: {"fingerprint", "reach"}} for every field that needs a lookup.

    A field needs one when it is filled in, looks right, and has no settled answer yet
    ("couldn't check right now" is retried). force=True ignores held answers.
    """
    results = {}
    for field in LOOKUP_FIELDS:
        value = status.field_value(basics, field)
        if not value or status.SHAPE_CHECKS[field](value)["status"] != "ok":
            continue
        if not force and status.has_lookup(basics, field):
            continue
        results[field] = {
            "fingerprint": status.fingerprint(value),
            "reach": _lookup(field, value),
        }
    return results


def apply_results(
    basics: dict, results: dict, *, now: datetime | None = None
) -> dict:
    """Store each answer only if its field is unchanged since it was checked."""
    out = basics
    for field, result in results.items():
        value = status.field_value(out, field)
        if not value or status.fingerprint(value) != result["fingerprint"]:
            continue
        out = status.record_check(
            out, field, status.SHAPE_CHECKS[field](value), result["reach"], now=now
        )
    return out
