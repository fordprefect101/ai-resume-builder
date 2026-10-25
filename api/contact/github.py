"""GitHub's public lookups (no sign-in): does an account or repository exist?

Only public information is visible. GitHub answers "not found" for a private
repository exactly as it does for one that does not exist, so the two cannot be
told apart here.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from contact import safe_fetch
from contact.reach import UNAVAILABLE, outcome
from contact.shape import GITHUB_NAME_RE, normalize_web_url

API = "https://api.github.com"
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def parse_repo_link(url: str) -> tuple[str, str] | None:
    """(owner, repo) for a link like https://github.com/owner/repo, else None."""
    parts = urlsplit(normalize_web_url(url))
    if (parts.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) < 2:
        return None
    owner, repo = segments[0], segments[1].removesuffix(".git")
    if not GITHUB_NAME_RE.match(owner) or repo in (".", "..") or not REPO_NAME_RE.match(repo):
        return None
    return owner, repo


def _get(path: str) -> tuple[int, dict | list | None, bool]:
    """(status, parsed JSON or None, rate_limited). Raises safe_fetch.FetchFailed."""
    reply = safe_fetch.fetch(f"{API}{path}", method="GET")
    status, headers = reply["status"], reply["headers"]
    limited = status == 429 or (
        status == 403 and headers.get("x-ratelimit-remaining") == "0"
    )
    try:
        data = json.loads(reply["body"]) if status == 200 else None
    except ValueError:
        data = None
    return status, data, limited


def lookup_user(username: str) -> dict:
    """Does this GitHub account exist? The name is shape-checked before it is used."""
    name = str(username or "").strip()
    if not GITHUB_NAME_RE.match(name):
        return outcome("not_found", "This isn't a valid GitHub username.")
    try:
        status, data, limited = _get(f"/users/{name}")
    except safe_fetch.FetchFailed:
        return outcome("unavailable", UNAVAILABLE)
    if limited:
        return outcome("unavailable", UNAVAILABLE)
    if status == 404:
        return outcome("not_found", "No GitHub account has this username.")
    if status == 200 and isinstance(data, dict):
        return outcome(
            "exists",
            "This GitHub account exists.",
            login=str(data.get("login") or name),
        )
    return outcome("unavailable", UNAVAILABLE)


def lookup_repo(url: str) -> dict:
    """Is this a public repository, and which languages does GitHub report for it?"""
    parsed = parse_repo_link(url)
    if parsed is None:
        return outcome("not_found", "This isn't a link to a GitHub repository.")
    owner, repo = parsed
    try:
        status, data, limited = _get(f"/repos/{owner}/{repo}")
        if limited:
            return outcome("unavailable", UNAVAILABLE)
        if status == 404:
            return outcome(
                "not_found",
                "We can't see this repository. It may be private, "
                "or the name may be wrong.",
            )
        if status != 200 or not isinstance(data, dict):
            return outcome("unavailable", UNAVAILABLE)
        if data.get("private"):
            return outcome("not_found", "We can't see this repository.")
        languages: list[str] = []
        lang_status, lang_data, lang_limited = _get(f"/repos/{owner}/{repo}/languages")
        if lang_status == 200 and isinstance(lang_data, dict):
            ranked = sorted(lang_data.items(), key=lambda pair: -int(pair[1] or 0))
            languages = [name for name, _size in ranked]
        elif lang_limited:
            return outcome("unavailable", UNAVAILABLE)
    except safe_fetch.FetchFailed:
        return outcome("unavailable", UNAVAILABLE)
    return outcome(
        "exists", "This public repository exists.", languages=languages
    )
