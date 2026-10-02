"""Tests for Phase 4: SSRF Prevention and Safe Outbound Fetch."""

import pytest

from app.safe_fetch import is_safe_outbound_url, safe_get


def test_allowed_outbound_urls():
    assert is_safe_outbound_url("https://rdap.org/domain/google.com")[0] is True
    assert is_safe_outbound_url("https://client.rdap.org/domain/apple.com")[0] is True
    assert is_safe_outbound_url("https://safebrowsing.googleapis.com/v4/threatMatches:find")[0] is True


def test_blocked_ssrf_attacks():
    # Loopback / localhost
    assert is_safe_outbound_url("http://127.0.0.1/admin")[0] is False
    assert is_safe_outbound_url("http://localhost:8000/readyz")[0] is False

    # Cloud instance metadata service (AWS/GCP/Azure)
    assert is_safe_outbound_url("http://169.254.169.254/latest/meta-data/")[0] is False

    # Private internal corporate networks (RFC 1918)
    assert is_safe_outbound_url("http://10.0.0.1/secrets")[0] is False
    assert is_safe_outbound_url("http://192.168.1.1/router")[0] is False
    assert is_safe_outbound_url("http://172.16.0.5/api")[0] is False

    # Arbitrary user-supplied websites (SSRF rule: never fetch user URLs)
    assert is_safe_outbound_url("https://random-store.com/checkout")[0] is False
    assert is_safe_outbound_url("https://evil-hacker.xyz/steal")[0] is False

    # Forbidden protocols
    assert is_safe_outbound_url("ftp://rdap.org/test")[0] is False
    assert is_safe_outbound_url("file:///etc/passwd")[0] is False


@pytest.mark.asyncio
async def test_safe_get_blocks_unsafe_destination():
    with pytest.raises(PermissionError) as exc_info:
        await safe_get("http://169.254.169.254/latest/meta-data/")
    assert "SSRF Protection blocked" in str(exc_info.value)
