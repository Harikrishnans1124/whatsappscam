"""Safe Outbound Fetch and SSRF Prevention for TrustShop AI.

Rules:
1. Never fetch user-supplied URLs.
2. Only allowlisted outbound service domains (RDAP, Google Safe Browsing) may be contacted.
3. Block all loopback, private, link-local, and internal address ranges.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

ALLOWED_OUTBOUND_DOMAINS = {
    "rdap.org",
    "client.rdap.org",
    "safebrowsing.googleapis.com",
    # Test domains if mocked
    "testserver",
}


def is_safe_outbound_url(url: str) -> tuple[bool, str]:
    """Validate whether an outbound URL is safe to contact without SSRF risk."""
    if not url:
        return False, "Empty URL"

    try:
        parsed = urlparse(url)
    except ValueError as e:
        return False, f"Invalid URL parsing: {e}"

    # Only http and https
    if parsed.scheme not in ("http", "https"):
        return False, f"Forbidden scheme: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "Missing hostname"

    # Check for IP address literals
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_loopback:
            return False, "Loopback addresses forbidden"
        if ip.is_private:
            return False, "Private IP ranges forbidden"
        if ip.is_link_local:
            return False, "Link-local IP ranges forbidden"
        if ip.is_multicast:
            return False, "Multicast IP ranges forbidden"
        return False, "Direct IP outbound connections forbidden"
    except ValueError:
        # Hostname is a domain name, proceed
        pass

    # Check against allowlist
    if hostname in ALLOWED_OUTBOUND_DOMAINS:
        return True, "Allowed"

    # Check subdomains of allowlisted services
    for allowed in ALLOWED_OUTBOUND_DOMAINS:
        if hostname.endswith("." + allowed):
            return True, "Allowed"

    return False, f"Domain '{hostname}' is not on the outbound allowlist."


async def safe_get(
    url: str,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = 2.5,
    **kwargs,
) -> httpx.Response:
    """Execute a safe GET request verifying outbound destination against SSRF allowlist."""
    is_safe, reason = is_safe_outbound_url(url)
    if not is_safe:
        raise PermissionError(f"SSRF Protection blocked request to '{url}': {reason}")

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_s, follow_redirects=True)
        should_close = True

    try:
        return await client.get(url, **kwargs)
    finally:
        if should_close:
            await client.aclose()
