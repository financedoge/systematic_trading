"""Signal-decay diagnostic and health projection."""
from decimal import Decimal

import pytest

from systematic_trading.research import signal_health
from systematic_trading.research.signal_decay import (
    block_bootstrap_mean, breakeven_ic, decay_status, forward_return, half_life, rank_ic,
    row_value, summarise_signal,
)


# --- rank IC -----------------------------------------------------------------

def test_rank_ic_perfect_agreement_and_reversal():
    signal = {f"S{i}": float(i) for i in range(10)}
    assert rank_ic(signal, {f"S{i}": float(i) for i in range(10)}) == pytest.approx(1.0)
    assert rank_ic(signal, {f"S{i}": -float(i) for i in range(10)}) == pytest.approx(-1.0)


def test_rank_ic_is_rank_based_not_linear():
    """A monotone transform must not change Spearman's rho."""
    signal = {f"S{i}": float(i) for i in range(8)}
    forward = {f"S{i}": float(i) ** 3 for i in range(8)}
    assert rank_ic(signal, forward) == pytest.approx(1.0)


def test_rank_ic_undefined_cases():
    forward = {f"S{i}": float(i) for i in range(10)}
    assert rank_ic({f"S{i}": 0.0 for i in range(10)}, forward) is None      # no signal dispersion
    assert rank_ic({"A": 1.0, "B": 2.0, "C": 3.0}, {"A": 1, "B": 2, "C": 3}) is None  # too few names
    assert rank_ic({}, {}) is None


def test_rank_ic_needs_both_series_observed():
    signal = {f"S{i}": float(i) for i in range(10)}
    forward = {f"S{i}": (None if i > 4 else float(i)) for i in range(10)}
    assert rank_ic(signal, forward) is not None  # five common names remain


# --- forward returns ---------------------------------------------------------

def _bars(prices):
    return [dict(trade_date=f"2026-01-{i + 1:02d}", open=str(p), close=str(p), volume=100)
            for i, p in enumerate(prices)]


def test_forward_return_uses_next_open_to_next_open():
    bars = _bars([100, 110, 121, 133.1])
    # decision at index 0 -> entry open[1]=110, 1-session exit open[2]=121 -> +10%
    assert forward_return(bars, 0, 1) == pytest.approx(0.10)
    assert forward_return(bars, 0, 2) == pytest.approx(0.21)


def test_forward_return_none_when_window_unobserved():
    bars = _bars([100, 110, 121])
    assert forward_return(bars, 0, 5) is None
    assert forward_return(bars, 2, 1) is None


def test_forward_return_reads_attributes_too():
    class Bar:
        def __init__(self, price, day):
            self.open, self.close, self.volume, self.trade_date = price, price, 100, day

    bars = [Bar(100, "2026-01-01"), Bar(110, "2026-01-02"), Bar(121, "2026-01-03")]
    assert forward_return(bars, 0, 1) == pytest.approx(0.10)
    assert row_value(bars[0], "open") == 100


# --- bootstrap ---------------------------------------------------------------

def test_block_bootstrap_mean_constant_series_is_degenerate():
    result = block_bootstrap_mean([0.05] * 40)
    assert result[6]["mean"] == pytest.approx(0.05)
    assert result[6]["ci95"] == pytest.approx([0.05, 0.05])


def test_block_bootstrap_mean_reports_insufficient_evidence():
    result = block_bootstrap_mean([0.05] * 5)
    assert result[6]["insufficient"] is True and result[6]["mean"] is None
    assert result[6]["n"] == 5


def test_block_bootstrap_mean_keeps_missing_dates_in_place():
    """Missing decisions must not silently shrink the sample."""
    series = [0.10] * 30 + [None] * 6 + [0.10] * 30
    result = block_bootstrap_mean(series)
    assert result[6]["n"] == 60
    assert result[6]["mean"] == pytest.approx(0.10)


# --- half-life and breakeven -------------------------------------------------

def test_half_life_recovers_a_known_decay_rate():
    curve = {h: 0.10 * (0.5 ** (h / 10)) for h in (1, 5, 10, 21, 63)}
    assert half_life(curve) == pytest.approx(10.0, abs=0.05)


def test_half_life_is_none_when_nothing_decays():
    assert half_life({1: 0.1, 5: 0.1, 10: 0.1}) is None          # flat
    assert half_life({1: 0.05, 5: 0.08, 10: 0.12}) is None       # rising
    assert half_life({1: 0.1, 5: 0.0999, 10: 0.0998, 21: 0.0995}) is None  # slower than the window
    assert half_life({1: 0.1, 5: 0.05}) is None                  # too few points


def test_breakeven_ic_scales_cost_to_the_signal_period():
    """Annual cost must be converted to the horizon before comparing with sigma."""
    # 8x annual turnover, 5bp, sigma 5% over 21 sessions
    expected = (5 / 10000.0) * 8 * (21 / 252.0) / 0.05
    assert breakeven_ic(8.0, 0.05, 5.0, 21) == pytest.approx(expected)
    # a 15x faster signal needs 15x the IC
    assert breakeven_ic(120.0, 0.05, 5.0, 21) == pytest.approx(15 * expected)


def test_breakeven_ic_undefined_without_dispersion():
    assert breakeven_ic(8.0, 0.0) is None
    assert breakeven_ic(8.0, None) is None


# --- status ------------------------------------------------------------------

def test_decay_status_branches():
    assert decay_status(0.01, 0.02, 0.02, observations=60)["status"] == "decayed"     # below breakeven
    assert decay_status(0.10, -0.01, 0.02, observations=60)["status"] == "decayed"    # recent non-positive
    assert decay_status(0.10, 0.03, 0.02, observations=60)["status"] == "weakening"   # retains < 50%
    assert decay_status(0.10, 0.09, 0.02, observations=60)["status"] == "healthy"
    assert decay_status(0.10, 0.09, 0.02, observations=3)["status"] == "insufficient"
    assert decay_status(None, 0.09, 0.02, observations=60)["status"] == "insufficient"


def test_summarise_signal_reports_the_decay_curve_and_interval():
    rising = [0.02 + 0.001 * i for i in range(40)]
    record = summarise_signal(name="s", label="S", ic_by_horizon={1: rising, 5: rising},
                              turnover=8.0, sigma=0.05)
    assert record["ic_curve"][1] == pytest.approx(sum(rising) / len(rising))
    assert record["observations"][1] == 40
    assert record["breakeven_ic"] is not None
    assert record["half_life_sessions"] is None
    assert "1" in record["ic_intervals"]


# --- health projection -------------------------------------------------------

REPORT = dict(
    decisions=130, first_decision="2016-01-04", last_decision="2026-10-01",
    batch="b" * 64, horizons=[1, 5],
    key_signals={"funded": ["good"], "unfunded": ["bad"], "mixed": ["good", "bad"]},
    coverage_gaps=[dict(name="gap", used_by=["funded"], reason="not published")],
    signals=[
        dict(name="good", label="Good", status="healthy", reason="recent 0.09",
             long_run_ic=0.09, recent_ic=0.09, ic_ir=0.2, hit_rate=0.55,
             half_life_sessions=None, breakeven_ic=0.003, ic_curve={1: 0.09}, observations={1: 130}),
        dict(name="bad", label="Bad", status="decayed", reason="recent non-positive",
             long_run_ic=0.01, recent_ic=-0.02, ic_ir=0.0, hit_rate=0.45,
             half_life_sessions=None, breakeven_ic=0.003, ic_curve={1: 0.01}, observations={1: 130}),
    ],
)

STATE = dict(sota_key="funded", active=dict(allocations=[
    dict(strategy_key="funded", weight="1"),
    dict(strategy_key="mixed", weight="0"),
]))


def test_health_flags_funding_and_worst_signal():
    rows = {r["strategy_key"]: r for r in signal_health.health(REPORT, STATE)}
    assert rows["funded"]["funded"] is True and rows["funded"]["is_sota"] is True
    assert rows["funded"]["status"] == "healthy"
    assert rows["unfunded"]["funded"] is False and rows["unfunded"]["status"] == "decayed"
    # worst-of across a strategy's key signals
    assert rows["mixed"]["status"] == "decayed"
    assert rows["mixed"]["funded"] is False  # zero weight is not funded


def test_health_sorts_by_severity_then_funding():
    rows = signal_health.health(REPORT, STATE)
    assert rows[0]["strategy_key"] in {"unfunded", "mixed"}  # decayed first
    assert rows[0]["status"] == "decayed"


def test_warnings_only_fire_for_funded_strategies():
    rows = signal_health.health(REPORT, STATE)
    assert signal_health.warnings(rows) == []  # the only decayed strategy is unfunded

    funded_decay = dict(STATE, active=dict(allocations=[dict(strategy_key="funded", weight="1"),
                                                        dict(strategy_key="unfunded", weight="0.25")]))
    flagged = signal_health.warnings(signal_health.health(REPORT, funded_decay))
    assert [w["strategy_key"] for w in flagged] == ["unfunded"]
    warning = flagged[0]
    assert warning["kind"] == "decayed"
    assert warning["allocation_pct"] == "25.0%"
    assert "25.0%" in warning["message"]


def test_warnings_cover_weakening_as_well_as_decayed():
    report = dict(REPORT)
    report["signals"] = [dict(REPORT["signals"][0], status="weakening", reason="retains 30%")]
    rows = signal_health.health(report, STATE)
    flagged = signal_health.warnings(rows)
    assert len(flagged) == 1 and flagged[0]["kind"] == "weakening"


def test_health_and_warnings_are_empty_without_a_publication():
    assert signal_health.health(None, STATE) == []
    assert signal_health.warnings([]) == []
    assert signal_health.headline(None, [])["available"] is False


def test_allocation_weights_are_summed_per_strategy():
    state = dict(sota_key=None, active=dict(allocations=[
        dict(strategy_key="funded", weight="0.4"), dict(strategy_key="funded", weight="0.35")]))
    rows = {r["strategy_key"]: r for r in signal_health.health(REPORT, state)}
    assert Decimal(rows["funded"]["allocation_weight"]) == Decimal("0.75")


def test_coverage_gaps_are_published_not_hidden():
    assert signal_health.coverage_gaps(REPORT)[0]["name"] == "gap"
    assert signal_health.headline(REPORT, [])["coverage_gap_count"] == 1


# --- wiring ------------------------------------------------------------------

def test_decay_route_is_registered_before_the_strategy_detail_route():
    """``/strategies/signal-decay`` must not be swallowed by ``/strategies/{id}``."""
    from systematic_trading.web import api
    paths = [route.path for route in api.router.routes]
    decay = "/api/v1/strategies/signal-decay"
    detail = "/api/v1/strategies/{strategy_id}"
    assert decay in paths and detail in paths
    assert paths.index(decay) < paths.index(detail)


def test_decay_job_is_registered_in_the_research_lane():
    import inspect
    from systematic_trading.research import analytics_service
    source = inspect.getsource(analytics_service.AnalyticsService.refresh)
    assert "signal-decay" in source
    assert "refresh_signal_decay" in source
    # the job must be classified in the research lane, not left unowned
    assert '"signal-decay"' in source.split("research = {", 1)[1].split("}", 1)[0]


def test_decay_panel_html_and_js_agree_on_element_ids():
    """Every id the panel script queries must exist in the panel markup."""
    import re
    from systematic_trading.web.signal_decay_ui import ALERT_HTML, ALERT_JS, HTML, JS
    for markup, script in ((HTML, JS), (ALERT_HTML, ALERT_JS)):
        declared = set(re.findall(r'id="([^"]+)"', markup))
        queried = set(re.findall(r"getElementById\('([^']+)'\)", script))
        assert queried, "the panel script must query at least one element"
        assert queried <= declared, f"missing markup for {sorted(queried - declared)}"


def test_decay_panel_defines_every_function_it_calls_at_load():
    from systematic_trading.web.signal_decay_ui import ALERT_JS, JS
    assert "function loadSignalDecay" in JS and "loadSignalDecay();" in JS
    assert "function loadDecayAlert" in ALERT_JS and "loadDecayAlert();" in ALERT_JS


def test_panel_never_claims_authority_to_change_an_allocation():
    """The surfaces are decision support and must say so."""
    from systematic_trading.web.signal_decay_ui import ALERT_JS, JS
    assert "Nothing has been changed" in ALERT_JS
    assert "changes nothing by itself" in JS or "decide through the normal allocation workflow" in JS


def test_job_skips_quietly_before_any_audited_batch_is_published():
    """A diagnostic must not raise into the research lane for missing prerequisites."""
    from systematic_trading.research import signal_decay_job

    class NoCatalog:
        def latest(self, source):
            return None

        def publish(self, *args, **kwargs):
            raise AssertionError("must not publish without inputs")

    class Settings:
        strategy_monitoring_config_path = None

    assert signal_decay_job.refresh_signal_decay(Settings(), NoCatalog()) is False
