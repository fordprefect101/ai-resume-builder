"""The only code allowed to open a link someone typed.

Every link is resolved here, refused unless it points at a public website, and then
opened using the exact address that was checked (so a second lookup cannot return a
different, private answer). Redirects are re-checked hop by hop.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit

TIMEOUT_SECONDS = 5
MAX_REDIRECTS = 3
MAX_BYTES = 65536
ALLOWED_PORTS = {"http": 80, "https": 443}
USER_AGENT = "ResumeBuilder-LinkCheck/1.0"


class Refused(ValueError):
    """The link is not a normal public web address. Nothing was opened."""


class FetchFailed(Exception):
    """The link looked fine but could not be opened (down, too slow, too many hops)."""


class NameNotFound(FetchFailed):
    """The website name does not exist at all (as opposed to being down)."""


def _literal_ip(host: str):
    """An IP address written in any form the system would accept, or None.

    Catches tricks like 2130706433 or 0x7f.1, which all mean 127.0.0.1.
    """
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    try:
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except (OSError, ValueError):
        return None


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise NameNotFound("the address could not be found") from exc
    return [info[4][0] for info in infos]


def is_public(address) -> bool:
    ip = ipaddress.ip_address(address) if isinstance(address, str) else address
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def check_target(url: str) -> tuple[str, str, int, str, str]:
    """Return (scheme, host, port, request path, checked address) for a safe link."""
    parts = urlsplit(str(url or "").strip())
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_PORTS:
        raise Refused("only http and https links can be opened")
    try:
        host = (parts.hostname or "").rstrip(".").lower()
        port = parts.port or ALLOWED_PORTS[scheme]
    except ValueError as exc:
        raise Refused("the link is not valid") from exc
    if not host:
        raise Refused("the link has no website name")
    if parts.username is not None or parts.password is not None:
        raise Refused("links with a login inside them are not opened")
    if port != ALLOWED_PORTS[scheme]:
        raise Refused("only the standard web ports are used")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise Refused("this address is not a public website")
    literal = _literal_ip(host)
    addresses = [literal] if literal else _resolve(host)
    if not addresses:
        raise FetchFailed("the address could not be found")
    # Every answer must be public, not just the first one.
    for address in addresses:
        if not is_public(address):
            raise Refused("this address is not a public website")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return scheme, host, port, path, str(addresses[0])


class _PinnedConnection(http.client.HTTPConnection):
    """Connects to a fixed, already-checked address but still sends the real host name."""

    def __init__(self, host, ip, port, timeout, use_tls):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip
        self._use_tls = use_tls

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        if self._use_tls:
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=self.host
            )
        self.sock = sock


def _request(scheme, host, ip, port, path, method, timeout):
    """One request to a checked address. Returns (status, headers, up to MAX_BYTES of body)."""
    conn = _PinnedConnection(host, ip, port, timeout, scheme == "https")
    try:
        conn.request(
            method, path, headers={"Host": host, "User-Agent": USER_AGENT}
        )
        response = conn.getresponse()
        body = response.read(MAX_BYTES) if method == "GET" else b""
        headers = {key.lower(): value for key, value in response.getheaders()}
        return response.status, headers, body
    finally:
        conn.close()


def fetch(url: str, *, method: str = "HEAD", timeout: float = TIMEOUT_SECONDS) -> dict:
    """Open a public link. Returns {status, url, headers, body}.

    Raises Refused (not a public website, at any hop) or FetchFailed (could not open).
    """
    current = str(url or "").strip()
    for _ in range(MAX_REDIRECTS + 1):
        scheme, host, port, path, ip = check_target(current)
        try:
            status, headers, body = _request(
                scheme, host, ip, port, path, method, timeout
            )
        except (OSError, http.client.HTTPException) as exc:
            raise FetchFailed("the website did not answer in time") from exc
        if status in (301, 302, 303, 307, 308) and headers.get("location"):
            current = urljoin(current, headers["location"])
            continue
        return {"status": status, "url": current, "headers": headers, "body": body}
    raise FetchFailed("too many redirects")
