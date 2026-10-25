"""Rung 1 of the contact ladder: does the value look right? No network, no AI."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import phonenumbers

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# GitHub names: letters, digits and single hyphens, no hyphen at either end, up to 39.
GITHUB_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)

# Common mistyped email domains and what they were probably meant to be.
DOMAIN_TYPOS = {
    "gmial.com": "gmail.com",
    "gmai.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.con": "gmail.com",
    "gnail.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "hotmail.con": "hotmail.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yahoo.con": "yahoo.com",
    "outlok.com": "outlook.com",
    "outlook.con": "outlook.com",
    "iclould.com": "icloud.com",
    "icloud.con": "icloud.com",
}


def result(status: str, value: str = "", message: str = "", suggestion: str = "") -> dict:
    """status: "empty" (nothing entered), "ok" (looks right) or "broken" (plainly wrong)."""
    return {
        "status": status,
        "value": value,
        "message": message,
        "suggestion": suggestion,
    }


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def normalize_github_url(value: str) -> str:
    username = str(value or "").strip().lstrip("@")
    if "github.com/" in username:
        username = username.split("github.com/", 1)[1].split("/", 1)[0]
    username = username.strip("/")
    if not username:
        return ""
    return f"https://github.com/{username}"


def normalize_linkedin_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "linkedin.com/" in raw.lower():
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        return f"https://{raw.lstrip('/')}"
    handle = raw.lstrip("@").strip("/")
    if handle.lower().startswith("in/"):
        handle = handle[3:]
    if not handle:
        return ""
    return f"https://www.linkedin.com/in/{handle}"


def normalize_web_url(value: str) -> str:
    """Add https:// when the person typed a bare address like example.com/me."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw.lstrip('/')}"
    return raw


def check_email(value: str) -> dict:
    email = normalize_email(value)
    if not email:
        return result("empty")
    if not EMAIL_RE.match(email) or ".." in email:
        return result("broken", email, "This doesn't look like an email address.")
    domain = email.rsplit("@", 1)[1]
    fixed = DOMAIN_TYPOS.get(domain)
    if fixed:
        guess = email.rsplit("@", 1)[0] + "@" + fixed
        return result("ok", email, f"Did you mean {guess}?", guess)
    return result("ok", email)


def check_phone(value: str, default_region: str | None = None) -> dict:
    """A number with +country code is checked fully. Without one, the country is needed."""
    raw = str(value or "").strip()
    if not raw:
        return result("empty")
    region = None if raw.startswith("+") else default_region
    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        if not raw.startswith("+") and default_region is None:
            return result(
                "ok", raw, "Add the country code (like +1) so this can be checked."
            )
        return result("broken", raw, "This doesn't look like a phone number.")
    if not phonenumbers.is_valid_number(number):
        return result("broken", raw, "This isn't a valid phone number for its country.")
    return result(
        "ok", phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    )


def check_github(value: str) -> dict:
    url = normalize_github_url(value)
    if not url:
        return result("empty")
    username = url.rsplit("/", 1)[1]
    if not GITHUB_NAME_RE.match(username):
        return result("broken", url, "This isn't a valid GitHub username.")
    return result("ok", url)


def check_linkedin(value: str) -> dict:
    raw = str(value or "").strip()
    if "://" in raw:
        # Normalising would wrap a foreign address inside a LinkedIn one, so the
        # host of what was actually typed is checked first.
        raw_host = (urlsplit(raw).hostname or "").lower()
        if raw_host != "linkedin.com" and not raw_host.endswith(".linkedin.com"):
            return result("broken", raw, "This isn't a LinkedIn address.")
    url = normalize_linkedin_url(raw)
    if not url:
        return result("empty")
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        return result("broken", url, "This isn't a LinkedIn address.")
    path = [part for part in parts.path.split("/") if part]
    if len(path) < 2 or path[0].lower() not in ("in", "pub", "company"):
        return result("broken", url, "This isn't a LinkedIn profile link.")
    return result("ok", url)


def check_web_url(value: str) -> dict:
    """Portfolio and project links: a normal http(s) address with a real-looking host."""
    url = normalize_web_url(value)
    if not url:
        return result("empty")
    if re.search(r"\s", url):
        return result("broken", url, "A web address can't contain spaces.")
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        parts.port  # raises ValueError on a bad port
    except ValueError:
        return result("broken", url, "This isn't a valid web address.")
    if parts.scheme not in ("http", "https"):
        return result("broken", url, "Use a web address starting with http or https.")
    if not HOST_RE.match(host) and not _looks_like_ip(host):
        return result("broken", url, "This isn't a valid web address.")
    return result("ok", url)


def _looks_like_ip(host: str) -> bool:
    return bool(re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host)) or ":" in host
