from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib

import pytest


def test_writer_and_normalizer_share_one_hash_definition():
    """Raw envelopes and normalized rows must hash through the same function."""
    from systematic_trading.market_data.golden import canonical_payload_hash as normalized
    from systematic_trading.recorders.market_data import canonical_payload_hash as recorded
    assert recorded is normalized


def test_canonical_form_matches_the_documented_encoding():
    """Pins sorted keys, compact separators and ASCII escaping against the digest."""
    from systematic_trading.canonical import canonical_payload_hash
    assert canonical_payload_hash({"b": 1, "a": "x"}) == "sha256:" + hashlib.sha256(b'{"a":"x","b":1}').hexdigest()


def test_canonical_hash_is_key_order_independent():
    from systematic_trading.canonical import canonical_payload_hash
    left = {"symbol": "SPY", "trade_date": "2026-08-04", "close": "756.5"}
    right = {"close": "756.5", "trade_date": "2026-08-04", "symbol": "SPY"}
    digest = canonical_payload_hash(left)
    assert digest == canonical_payload_hash(right)
    assert digest.startswith("sha256:") and len(digest) == 71


def test_canonical_hash_encodes_non_json_types_stably():
    from systematic_trading.canonical import canonical_payload_hash
    payload = {"amount": Decimal("1.50"), "at": datetime(2026, 8, 4, 22, tzinfo=UTC), "day": date(2026, 8, 4)}
    assert canonical_payload_hash(payload) == canonical_payload_hash({"day": date(2026, 8, 4),
        "at": datetime(2026, 8, 4, 22, tzinfo=UTC), "amount": Decimal("1.50")})


def test_naive_timestamps_are_treated_as_utc():
    """The recorder's original encoding treated naive timestamps as UTC; keep that."""
    from systematic_trading.canonical import canonical_payload_hash
    naive = canonical_payload_hash({"at": datetime(2026, 8, 4, 22)})
    assert naive == canonical_payload_hash({"at": datetime(2026, 8, 4, 22, tzinfo=UTC)})
    assert naive == canonical_payload_hash(
        {"at": datetime(2026, 8, 5, 6, tzinfo=timezone(timedelta(hours=8)))})


def test_unknown_types_raise_instead_of_hashing_silently():
    from systematic_trading.canonical import canonical_payload_hash
    with pytest.raises(TypeError, match="not JSON serializable"):
        canonical_payload_hash({"value": object()})
