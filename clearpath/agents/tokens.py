"""HMAC-SHA256 token issuing and verification for ClearPath-lite.

Token format: ``vehicle_id.nonce.ts.signature`` where ``signature`` is an
unpadded base64url HMAC-SHA256 over ``f"{vehicle_id}|{nonce}|{ts}"``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Dict, Tuple


def issue_token(vehicle_id: str, nonce: str, ts: float, secret: str) -> str:
    """Return a signed token string for the given vehicle, nonce and timestamp.

    Args:
        vehicle_id: Identifier of the requesting vehicle.
        nonce: Single-use value for replay protection.
        ts: Timestamp (seconds) being bound into the token.
        secret: Shared HMAC secret.

    Returns:
        Token of the form ``vehicle_id.nonce.ts.signature``.
    """
    ts_text = str(ts)
    payload = f"{vehicle_id}|{nonce}|{ts_text}"
    digest = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"{vehicle_id}.{nonce}.{ts_text}.{signature}"


def verify_token(token: str, secret: str) -> Tuple[bool, str, Dict[str, object]]:
    """Verify a token's HMAC signature.

    The token is split from the left on the first two dots and from the right on
    the last one, so a timestamp such as ``1234.5`` keeps its decimal point.

    Args:
        token: Token string produced by :func:`issue_token`.
        secret: Shared HMAC secret.

    Returns:
        ``(ok, reason, parsed_fields)`` where ``reason`` is ``"OK"``,
        ``"BAD_FORMAT"`` or ``"BAD_SIGNATURE"``. ``parsed_fields`` holds
        ``vehicle_id``, ``nonce`` and ``ts`` on success and is empty otherwise.
    """
    if not isinstance(token, str) or not token:
        return False, "BAD_FORMAT", {}

    head = token.split(".", 2)
    if len(head) != 3:
        return False, "BAD_FORMAT", {}

    vehicle_id, nonce, rest = head
    if not vehicle_id or not nonce or "." not in rest:
        return False, "BAD_FORMAT", {}

    ts_text, signature = rest.rsplit(".", 1)
    if not ts_text or not signature:
        return False, "BAD_FORMAT", {}

    try:
        ts_value = float(ts_text)
        provided = signature.encode("ascii")
    except (ValueError, UnicodeEncodeError):
        return False, "BAD_FORMAT", {}

    payload = f"{vehicle_id}|{nonce}|{ts_text}"
    digest = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    if not hmac.compare_digest(expected.encode("ascii"), provided):
        return False, "BAD_SIGNATURE", {}

    return True, "OK", {"vehicle_id": vehicle_id, "nonce": nonce, "ts": ts_value}
