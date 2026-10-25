"""Rung 2 of the contact ladder: does it exist? Needs the internet; never blocks anyone.

Every check answers one of three things:
  exists       it is real and reachable
  not_found    it is plainly not there
  unavailable  we could not tell (timeout, rate limit, outside service down)
"""

from __future__ import annotations

import dns.exception
import dns.resolver

from contact import safe_fetch

DNS_TIMEOUT_SECONDS = 5
UNAVAILABLE = "Couldn't check right now."


def outcome(status: str, message: str = "", **extra) -> dict:
    return {"status": status, "message": message, **extra}


def _dns_query(domain: str, record_type: str) -> list[str]:
    """Seam for tests. Raises the dns.* exceptions handled below."""
    answers = dns.resolver.resolve(domain, record_type, lifetime=DNS_TIMEOUT_SECONDS)
    return [answer.to_text() for answer in answers]


def check_email_domain(email: str) -> dict:
    """Can the email's domain receive mail? (Says nothing about the mailbox itself.)"""
    value = str(email or "").strip().lower()
    if "@" not in value:
        return outcome("not_found", "This doesn't look like an email address.")
    domain = value.rsplit("@", 1)[1].rstrip(".")
    try:
        try:
            hosts = _dns_query(domain, "MX")
        except dns.resolver.NoAnswer:
            # With no MX record, mail servers fall back to the domain's own address.
            hosts = _dns_query(domain, "A")
    except dns.resolver.NXDOMAIN:
        return outcome("not_found", f"The domain {domain} doesn't exist.")
    except dns.resolver.NoAnswer:
        return outcome("not_found", f"{domain} can't receive email.")
    except (dns.exception.DNSException, OSError):
        return outcome("unavailable", UNAVAILABLE)
    # A single "." mail server is the standard way a domain says it takes no mail.
    if not hosts or all(host.split()[-1] == "." for host in hosts):
        return outcome("not_found", f"{domain} can't receive email.")
    return outcome("exists", f"{domain} can receive email.")


def check_page(url: str) -> dict:
    """Does a portfolio or project link open?"""
    try:
        reply = safe_fetch.fetch(url, method="HEAD")
        if reply["status"] in (403, 405, 501):
            # Some sites refuse the lightweight request but allow a normal one.
            reply = safe_fetch.fetch(url, method="GET")
    except safe_fetch.Refused:
        return outcome("not_found", "This isn't a public website.")
    except safe_fetch.NameNotFound:
        return outcome("not_found", "This website name doesn't exist.")
    except safe_fetch.FetchFailed:
        return outcome("unavailable", UNAVAILABLE)
    status = reply["status"]
    if status < 400:
        return outcome("exists", "The page opens.")
    if status in (404, 410):
        return outcome("not_found", "The page wasn't found.")
    return outcome("unavailable", UNAVAILABLE)
