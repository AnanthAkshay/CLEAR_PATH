"""Tests for the ClearPath-lite HMAC token helpers."""

from __future__ import annotations

from clearpath.agents.tokens import issue_token, verify_token

SECRET = "test-secret"


def test_valid_token_verifies() -> None:
    """A freshly issued token verifies and returns its parsed fields."""
    token = issue_token("AMB_1", "nonce-1", 1234.5, SECRET)

    ok, reason, fields = verify_token(token, SECRET)

    assert ok is True
    assert reason == "OK"
    assert fields == {"vehicle_id": "AMB_1", "nonce": "nonce-1", "ts": 1234.5}


def test_tampered_signature_fails() -> None:
    """Flipping one signature character invalidates the token."""
    token = issue_token("AMB_1", "nonce-1", 1234.5, SECRET)
    head, signature = token.rsplit(".", 1)
    tampered = head + "." + ("A" if signature[-1] != "A" else "B")

    ok, reason, fields = verify_token(tampered, SECRET)

    assert ok is False
    assert reason == "BAD_SIGNATURE"
    assert fields == {}


def test_malformed_token_fails() -> None:
    """A string that is not a token is rejected as bad format."""
    ok, reason, fields = verify_token("not-a-token", SECRET)

    assert ok is False
    assert reason == "BAD_FORMAT"
    assert fields == {}
