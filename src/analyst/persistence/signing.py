"""HMAC token signing — stdlib only (no heavyweight auth deps).

Signs opaque values into ``value.signature`` tokens for the session cookie
and the OAuth ``state`` parameter. Constant-time verification.
"""

from __future__ import annotations

import hashlib
import hmac


def sign(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{digest}"


def unsign(token: str, secret: str) -> str | None:
    """Return the signed value, or None if the signature does not verify."""
    value, sep, digest = token.rpartition(".")
    if not sep or not value:
        return None
    expected = hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()
    return value if hmac.compare_digest(digest, expected) else None
