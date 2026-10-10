"""Evidence-bound ETF admission holds shared by recorders and strategy inputs.

A hold recorded here is enforced in code. Removing the matching configuration key
cannot release it: lifting a hold requires new dated evidence that resolves the
recorded conflict, and an explicit code change that cites it.

Recorder, constituent-input and universe-control paths all consult
``admission_hold`` so one definition governs every admission check.
"""
from __future__ import annotations

ADMISSION_HOLDS: dict[str, dict[str, str]] = {
    "XOP": dict(
        reason="Issuer listing date is 2006-06-23 but the provider firstTradeDate and first observation are 2006-06-22.",
        conflict="issuer/provider listing-boundary disagreement",
        recorded="2026-10-09",
        evidence="var/governance/research-2026-10-08-f7edd995880b",
        release="Retain quarantine until independent dated evidence resolves the boundary; do not trim or relabel the source.",
    ),
}


def admission_hold(symbol: str, configured_reason: str | None = None) -> str | None:
    """Return the effective hold reason for ``symbol``, or None when admissible.

    The code-level registry takes precedence over the configuration so that a
    configuration edit alone cannot release a recorded hold.
    """
    hold = ADMISSION_HOLDS.get(symbol)
    if hold:
        return hold["reason"]
    return configured_reason or None


def hold_record(symbol: str) -> dict[str, str]:
    """Return the recorded evidence for a code-level hold, or an empty mapping."""
    return dict(ADMISSION_HOLDS.get(symbol) or {})
