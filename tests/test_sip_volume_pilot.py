"""Incomplete histories, calendar boundaries and retrospective-use guards."""
from datetime import datetime
import gzip
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from systematic_trading.research.sip_volume_pilot import audit_bars, audit_pair, eligible_at


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("sip_pilot_runner", SCRIPTS / "p421_sip_volume_pilot.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)
sys.path.pop(0)


def bar(**updates):
    return dict(symbol="CSL", t="2024-03-11T04:00:00Z", o=99, h=101, l=98, c=100, v=1001, n=10, **updates)


def test_dst_daily_boundary_uses_new_york_calendar_and_missing_is_not_filled():
    rows = [bar(), dict(bar(), t="2024-11-04T05:00:00Z")]
    assert len(audit_bars(rows, ["CSL"], ["2024-03-11", "2024-11-04"])) == 2
    with pytest.raises(ValueError, match="New York midnight"):
        audit_bars([dict(bar(), t="2024-03-11T05:00:00Z")], ["CSL"], ["2024-03-11"])
    with pytest.raises(ValueError, match="missing"):
        audit_bars(rows[:1], ["CSL"], ["2024-03-11", "2024-11-04"])


@pytest.mark.parametrize("change", [{"v": 1.5}, {"v": True}, {"c": float("nan")}, {"h": 97}, {"n": -1}])
def test_invalid_activity_is_rejected_without_rounding(change):
    with pytest.raises(ValueError):
        audit_bars([dict(bar(), **change)], ["CSL"], ["2024-03-11"])


def test_duplicates_and_out_of_order_rows_fail():
    with pytest.raises(ValueError, match="duplicate"):
        audit_bars([bar(), bar()], ["CSL"], ["2024-03-11"])
    with pytest.raises(ValueError, match="ordered"):
        audit_bars([dict(bar(), t="2024-11-04T05:00:00Z"), bar()], ["CSL"], ["2024-03-11", "2024-11-04"])


def paired():
    return audit_pair(bar(), dict(symbol="CSL", trade_date="2024-03-11", raw_close=100.01,
        raw_volume=900, split_multiplier=1, source_id="pinned", source_hash="pinned-hash"),
        dict(date="2024-03-11", broker_trade_close=100),
        dict(captured_at="2026-11-07T12:00:00+00:00"), dict(symbol="CSL", broker_conid=6120),
        dict(status="review"))


def test_residuals_remain_exact_and_do_not_repair_published_fields():
    row = paired()
    assert row["sip_raw_volume"] == 1001 and row["published_raw_volume"] == 900
    assert row["volume_delta_shares"] == 101
    assert row["paired_published_raw_close"] == 100.01
    assert row["close_delta_usd"] == -0.01
    assert row["close_delta_vs_ibkr_usd"] == 0
    assert "prior_series_review_retained" in row["flags"]
    assert "close_difference_requires_review" in row["flags"]
    assert row["historical_published_at"] is None


def test_historical_read_rejects_later_capture_even_if_flags_are_removed():
    row = paired()
    assert not eligible_at(row, "2025-02-28T16:00:00-05:00", "2026-11-07T13:00:00+00:00")
    forged = dict(row, flags=[], historical_strategy_eligible=True,
                  historical_published_at="2024-03-12T06:00:00+00:00")
    assert not eligible_at(forged, "2025-02-28T16:00:00-05:00", "2026-11-07T13:00:00+00:00")
    assert not eligible_at(forged, "2026-11-08", "2026-11-07T13:00:00+00:00")


def test_full_day_cannot_be_available_at_same_close():
    row = paired()
    forged = dict(row, flags=[], historical_strategy_eligible=True,
                  historical_published_at="2024-03-11T20:00:00+00:00",
                  first_captured_at="2024-03-11T20:00:01+00:00")
    assert not eligible_at(forged, "2024-03-11T20:02:00+00:00", "2024-03-11T20:01:00+00:00")
    assert datetime.fromisoformat(row["session_end_exclusive"]).date().isoformat() == "2024-03-12"


def archive(tmp_path, *, second_token=None, corrupt_token=False):
    p = runner.protocol()
    (tmp_path / "protocol.json").write_bytes((runner.STUDY / "protocol.json").read_bytes())
    requests = []
    for i, token in enumerate(("next", second_token)):
        payload = dict(bars={"CSL": [dict(bar(), t=f"2024-02-{27+i}T05:00:00Z")]}, next_page_token=token)
        raw = json.dumps(payload).encode()
        blob = gzip.compress(raw, mtime=0)
        name = f"{i}.gz"
        (tmp_path / name).write_bytes(blob)
        params = runner.parameters(p, None if i == 0 else ("wrong" if corrupt_token else "next"))
        requests.append(dict(path=name, sha256=runner.sha(blob), response_sha256=runner.sha(raw),
            parameters=params, status="ok", http_status=200, row_count=1, captured_at="2026-11-07T12:00:00+00:00"))
    runner.save(tmp_path / "manifest.json", dict(protocol_sha256=runner.PROTOCOL_HASH, runners={},
        status="captured_pending_audit", requests=requests))
    return p


def test_short_page_requires_following_the_token_and_preserves_hashes(tmp_path):
    p = archive(tmp_path)
    assert len(runner.replay_new(tmp_path, p)[1]) == 2
    (tmp_path / "0.gz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Changed pinned"):
        runner.replay_new(tmp_path, p)


def test_page_token_chain_and_terminal_page_are_required(tmp_path):
    p = archive(tmp_path, corrupt_token=True)
    with pytest.raises(ValueError, match="token chain"):
        runner.replay_new(tmp_path, p)
    p = archive(tmp_path, second_token="more")
    with pytest.raises(ValueError, match="Incomplete capture"):
        runner.replay_new(tmp_path, p)


def test_failed_request_is_retained_without_advancing_token(tmp_path):
    p = archive(tmp_path)
    m = runner.read(tmp_path / "manifest.json")
    m["requests"].insert(1, dict(parameters=runner.parameters(p, "next"), status="transport_failed"))
    runner.save(tmp_path / "manifest.json", m)
    assert len(runner.replay_new(tmp_path, p)[1]) == 2
