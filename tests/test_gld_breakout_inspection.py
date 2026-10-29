"""Guard visual evidence against look-ahead and mislabeled stop/fill levels."""
from pathlib import Path
import json
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_gld_breakout_inspection as report  # noqa: E402


@pytest.fixture(scope="module", params=["short", "long"])
def fitted(request):
    declared = json.loads((report.audit.OUTPUT / "protocol.json").read_text())
    spec = report.rl.SHORT_SPEC if request.param == "short" else report.rl.LONG_SPEC
    data = report.audit.load_asset("GLD")
    features = report.rl.Features.build(data, spec)
    prepared = report.rl.prepare(features, declared["gld_anchors"][request.param + "_original"]["parameters"])
    return data, features, prepared


@pytest.mark.parametrize("delay", [0, 1])
def test_stop_components_reconcile_including_queued_exit_closes(fitted, delay):
    _, f, prepared = fitted
    sim = report.br.simulate(f, prepared, delay=delay)
    trace, episodes = report.stop_trace(f, prepared, sim)
    assert episodes
    np.testing.assert_allclose(trace["stop"], sim["stop"], atol=1e-12, rtol=0, equal_nan=True)
    for e in episodes:
        start, end = e["entry_index"], e["exit_index"] or len(f.close)
        assert start == e["confirmation"] + 1 + delay
        assert e["entry"] == f.open[start]
        assert e["atr"] == prepared["atr"][e["confirmation"]]
        assert np.all(np.diff(trace["stop"][start:end]) >= 0)
        before = e["first_arm"] or end
        np.testing.assert_allclose(trace["stop"][start:before], e["floor"])
        if e["exit_index"] is not None:
            assert e["exit_index"] == e["exit_signal"] + 1 + delay
            assert e["exit_price"] == f.open[e["exit_index"]]
        if delay and e.get("exit_signal") is not None:
            np.testing.assert_allclose(trace["stop"][e["exit_signal"]:end], trace["stop"][e["exit_signal"]])


def test_frozen_box_excludes_breakout_close_and_future_prices(fitted):
    data, f, prepared = fitted
    e = report.br.simulate(f, prepared)["episodes"][-2]
    t = e["crossing"]
    box = report.range_box(f, prepared, t)
    tail = f.spec.tails[int(prepared["parameters"][1])]
    expected = np.exp(np.quantile(np.log(f.close[box["start"]:t]), [tail, 1 - tail]))
    np.testing.assert_allclose([box["lower"], box["upper"]], expected, rtol=1e-12)
    assert box["end"] == t - 1
    assert box["start"] == t - box["length"]
    assert box["length"] == max(c["length"] for c in box["candidates"] if c["qualifies"])
    changed = {k: v.copy() for k, v in data.items()}
    for k in ("open", "high", "low", "close"):
        changed[k][t:] *= 3
    altered = report.rl.Features.build(changed, f.spec)
    assert report.clean(report.range_box(altered, report.rl.prepare(altered, prepared["parameters"]), t)) == report.clean(box)


def test_trace_refuses_a_changed_stop_instead_of_drawing_it(fitted):
    _, f, prepared = fitted
    sim = report.br.simulate(f, prepared)
    sim["stop"][sim["episodes"][0]["entry_index"]] += .01
    with pytest.raises(AssertionError):
        report.stop_trace(f, prepared, sim)
