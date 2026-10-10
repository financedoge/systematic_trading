"""Canonical JSON payload hashing shared by market-data writers and verifiers.

Raw envelopes and normalized rows are hashed on write and re-verified on read,
audit and replay. One definition of the canonical form keeps those independent
checks comparable; two implementations could disagree on the non-JSON types
(``Decimal``, ``datetime``, ``date``) that market-data payloads do contain.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping


def json_default(value: object) -> object:
    """Encode the non-JSON types used by market-data payloads.

    Raises rather than stringifying an unknown type, so an unexpected object is
    reported instead of silently producing a hash that cannot be reproduced.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def canonical_payload_hash(payload: Mapping[str, Any]) -> str:
    """Return the stable ``sha256:<hex>`` digest of a market-data payload."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=json_default,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
