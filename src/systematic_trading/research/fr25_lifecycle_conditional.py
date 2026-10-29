"""Verified historical USD replay of the conditional FR25 candidate.

The retained panel ends on 2026-10-12. It is not a current signal feed: extending it
requires app-owned FR25 and stable-breadth calculation on a new audited publication.
Internal *_cnh fields belong to the shared engine; this replay's declared currency
is USD, using USD=1 solely as a numeraire, never as a historical FX observation.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import json
from hashlib import sha256
from pathlib import Path

import numpy as np

from systematic_trading.research import range_lifecycle as rl

ROOT = Path(__file__).resolve().parents[3]
KEY = "fr25_lifecycle_conditional_v1"
VERSION = "1.1.0"
PARAMETERS_PATH = Path(__file__).with_name("fr25_lifecycle_conditional_parameters.json")
MANIFEST_PATH = Path(__file__).with_name("fr25_lifecycle_inputs.json")
INPUTS_PATH = ROOT / "var/research/range-breakout-20261018-v2/pool/inputs.npz"
RECIPE_PATH = ROOT / "var/research/range-breakout-20261018-v2/pool/recipe.json"
OOS_START = "2023-01-03"
WARMUP = 252


def verified_input_provenance():
    """Verify retained derived inputs and their original published price receipts."""
    from systematic_trading.research.governed_inputs import GovernedInputs
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Conditional candidate input changed: " + name)
    pin = manifest["price_pin"]
    source = GovernedInputs(Path(pin["root"]), pin["batch"])
    receipt = json.loads((INPUTS_PATH.parent.parent / "input_receipt.json").read_text(encoding="utf-8"))
    benchmark = json.loads((INPUTS_PATH.parent / "receipt.json").read_text(encoding="utf-8"))
    files = dict(receipt["files"], **benchmark["additional_benchmark_files"])
    for name, expected in files.items():
        if sha256(source.checked(name).read_bytes()).hexdigest() != expected:
            raise ValueError("Conditional published source changed: " + name)
    return dict(manifest_sha256=sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
                files=manifest["files"], batch=pin["batch"], governed_files=files,
                price_through=manifest["through"], valuation_through=manifest["through"],
                accounting_currency="USD", limitations=manifest["limitations"])


def frozen_parameters() -> dict:
    return json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))


def definition():
    """Registered strategy definition (candidate; never confers monitoring authority)."""
    from systematic_trading.research.strategy_catalog import OverlaySpec, fr25_definition
    base = fr25_definition()
    membership = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["universe_members"]
    return replace(
        base,
        key=KEY,
        name="FR25 80/20 + conditional short life-cycle sleeve",
        sleeve_name="fr25-lifecycle-conditional-v1",
        state="candidate",
        promoted_on=None,
        scheduler="dynamic_monthly",
        universe_key="lifecycle_supported52",
        universe_members=tuple(membership),
        description=("Frozen FR25 monthly targets scaled by 80% plus a 20% Rule A "
                     "short-only life-cycle sleeve when stable union breadth is at or above its "
                     "pre-2023 median; dynamic 10% L1 target-change including cash. "
                     "USD historical replay through 2026-10-12; current signal extension pending."),
        overlays=(*base.overlays, OverlaySpec(kind="lifecycle_conditional_sleeve",
                                              parameters={"version": VERSION})),
    )


def _load_panel():
    with np.load(INPUTS_PATH, allow_pickle=False) as data:
        panel = dict(data)
    params = frozen_parameters()
    if list(panel["days"]) != params["condition"]["sessions"]:
        raise ValueError("Frozen breadth dates do not match the price panel")
    if set(panel["symbols"]) != set(params["sleeve"]["short_parameters"]):
        raise ValueError("Frozen sleeve membership does not match the panel")
    if str(panel["days"][-1]) != "2026-10-12":
        raise ValueError("Frozen panel cutoff changed; register new inputs")
    return panel


def _sleeve_signals(panel, params):
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    order = [str(s) for s in panel["symbols"]]
    active = np.zeros((len(days), len(order)), bool)
    scores = np.zeros((len(days), len(order)))
    for j, symbol in enumerate(order):
        path = ROOT / "var/research/range-breakout-20261018-v2/assets" / f"{symbol}.npz"
        with np.load(path, allow_pickle=False) as asset:
            data = {k: np.asarray(asset[k]) for k in ("open", "high", "low", "close", "volume", "days")}
        # Rule A's frozen tie-break scores include both active horizons, even for
        # the short-only entry source. This reproduces the research scanner.
        for kind, spec in (("short", rl.SHORT_SPEC), ("long", rl.LONG_SPEC)):
            features = rl.Features.build(data, spec)
            vector = spec.canonical(params["sleeve"][kind + "_parameters"][symbol])
            prepared = rl.prepare(features, vector)
            sim = rl.simulate(features, prepared, start=WARMUP, cost_bp=5.0, trace=True)
            lookup = {str(np.datetime64(d, "D")): i for i, d in enumerate(features.days)}
            for i, day in enumerate(days):
                t = lookup.get(day)
                if t is None:
                    raise ValueError(f"Missing sleeve observation: {symbol} {day}")
                is_long = int(sim["state"][t]) == rl.STATE_LONG
                if kind == "short":
                    active[i, j] = is_long
                if is_long and np.isfinite(sim["level"][t]) and prepared["atr"][t] > 0:
                    # Historical signal files stored each horizon in float32.
                    scores[i, j] += float(np.float32(max(
                        0.0, (features.close[t] - sim["level"][t]) / prepared["atr"][t])))
    return active, scores


def _monthly_indices(panel):
    from systematic_trading.live.trading_calendar import next_us_trading_day
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    initial = int(np.flatnonzero(np.array(days) <= "2022-12-30")[-1])
    indices = [initial]
    for t in range(initial + 1, len(days)):
        day = date.fromisoformat(days[t])
        if next_us_trading_day(day).month != day.month:
            indices.append(t)
    return np.array(indices, dtype=int)


def target_distance(desired, adopted):
    """Full L1 distance: risky assets plus the residual cash weight."""
    return float(np.abs(desired - adopted).sum() + abs(desired.sum() - adopted.sum()))


def build_targets(panel, active, scores=None, *, params=None, clock="dynamic",
                  trigger=0.10, condition_override=None, return_theoretical=False):
    params = params or frozen_parameters()
    if clock not in {"dynamic", "monthly"} or not np.isfinite(trigger) or trigger < 0:
        raise ValueError("Invalid rebalance clock or threshold")
    if scores is None:
        raise ValueError("Rule A requires its frozen entry-ranking scores")
    threshold = params["condition"]["threshold"]
    breadth = params["condition"]["breadth_by_session"]
    n = panel["close"].shape[0]
    n_assets = panel["close"].shape[1]
    fr25 = np.column_stack([panel["fr25"], np.zeros(n)])
    monthly = _monthly_indices(panel)
    condition = {int(t): bool(breadth[t] >= threshold) for t in monthly}
    if condition_override is not None:
        condition = {int(t): bool(condition_override[int(t)]) for t in monthly}
    monthly_set = set(monthly)
    holdings: list[int] = []
    targets = np.zeros((n, n_assets + 1))
    theoretical = np.zeros_like(targets)
    indices: list[int] = []
    fr25_current = np.zeros(n_assets + 1)
    adopted = np.zeros(n_assets + 1)
    cash = list(panel["symbols"]).index("BIL")
    for day in range(int(monthly[0]), n):
        if day in monthly_set:
            fr25_current = fr25[day]
        for j in list(holdings):
            if not active[day, j]:
                holdings.remove(j)
        # Start flat: do not back-fill an entry before the evaluation window.
        new = [j for j in np.flatnonzero(active[day]) if active[day - 1, j] == 0
               and j not in holdings and j != cash] if day > monthly[0] else []
        new.sort(key=lambda j: (-scores[day, j], str(panel["symbols"][j])))
        room = 6 - len(holdings)
        if room > 0 and new:
            holdings.extend(new[:room])
        if condition.get(int(monthly[np.searchsorted(monthly, day, side="right") - 1]), False):
            sleeve = np.zeros(n_assets + 1)
            if holdings:
                sleeve[holdings] = 0.98 / len(holdings)
            else:
                sleeve[cash] = 0.98
            # Preserve FR25's defensive cash/cap; never lever it back to 98%.
            desired = 0.8 * fr25_current + 0.2 * sleeve
        else:
            desired = fr25_current.copy()
        desired = np.minimum(desired, 0.45)  # excess remains cash; no renormalization
        theoretical[day] = desired
        if day in monthly_set or (clock == "dynamic" and
                target_distance(desired, adopted) >= trigger - 1e-12):
            targets[day] = desired
            indices.append(day)
            adopted = desired.copy()
    result = targets, np.array(indices, dtype=int), condition
    return (*result, theoretical) if return_theoretical else result


class _Replay:
    """Minimal wrapper over the shared application accounting engine (no approximate ledger)."""

    def __init__(self, panel, recipe, start):
        from systematic_trading.domain.market import Instrument
        from systematic_trading.backtest.accounting import quantize_money
        self.a = panel
        self.symbols = panel["symbols"].tolist() + ["URTH"]
        self.indices = np.flatnonzero(panel["days"] >= start)
        self.days = [date.fromisoformat(str(panel["days"][i])) for i in self.indices]
        self.members = {r["symbol"]: Instrument.model_validate(r) for r in recipe["universeMembers"]}
        close = np.column_stack([panel["close"], panel["urth_close"]])
        opens = np.column_stack([panel["open"], panel["urth_open"]])
        self.close, self.open, self.reference = {}, {}, {}
        for i, day in zip(self.indices, self.days, strict=True):
            for target, values in ((self.close, close[i]), (self.open, opens[i]),
                                   (self.reference, close[i - 1])):
                target[day] = {s: quantize_money(D(str(x))) for s, x in zip(self.symbols, values, strict=True)}
        self.fx = {date.fromisoformat(str(day)): {"USD": D(1)} for day in panel["days"]}

    def decisions(self, weights, indices, delay):
        from systematic_trading.domain.portfolio import AllocationTarget
        result = {}
        for t in indices:
            execution = t + 1 + delay
            if execution >= len(self.a["days"]):
                continue
            day = date.fromisoformat(str(self.a["days"][execution]))
            result[day] = [AllocationTarget(symbol=s, target_weight=D(str(round(float(w), 12))),
                                            sleeve="fr25-lifecycle-conditional",
                                            rationale="Frozen FR25 + conditional life-cycle sleeve")
                           for s, w in zip(self.symbols, weights[t], strict=True) if w > 0]
        return result

    def run(self, weights, indices, cost, delay):
        result, fills = self.run_result(weights, indices, cost, delay)
        return np.array([float(r.nav_cnh) for r in result.nav_series]), fills

    def run_result(self, weights, indices, cost, delay):
        from systematic_trading.backtest.engine import DailyBacktestEngine
        from systematic_trading.backtest.accounting import quantize_money
        from systematic_trading.domain.portfolio import CashBalance
        from systematic_trading.domain.enums import Currency
        schedule = self.decisions(weights, indices, delay)
        if not isinstance(delay, (int, np.integer)) or delay < 0:
            raise ValueError("Execution delay must be a nonnegative integer")
        decision_dates = {}
        references = dict(self.reference)
        for t in indices:
            execution = t + 1 + delay
            if execution >= len(self.a["days"]):
                continue
            day = date.fromisoformat(str(self.a["days"][execution]))
            decision_dates[day] = date.fromisoformat(str(self.a["days"][t]))
            values = np.append(self.a["close"][t], self.a["urth_close"][t])
            references[day] = {s: quantize_money(D(str(v)))
                               for s, v in zip(self.symbols, values, strict=True)}
        order_days, fills = iter(sorted(schedule)), []
        class Engine(DailyBacktestEngine):
            def _apply_orders(self, **kw):
                day = next(order_days)
                before = {s: p.quantity for s, p in kw["positions"].items()}
                super()._apply_orders(**kw)
                after = {s: p.quantity for s, p in kw["positions"].items()}
                for s in sorted(before.keys() | after.keys()):
                    quantity = after.get(s, 0) - before.get(s, 0)
                    if quantity:
                        price = kw["execution_prices"][s]
                        fee = quantize_money(quantize_money(abs(quantity) * price) * D(str(cost)) / 10000)
                        fills.append(dict(date=str(day), symbol=s, quantity=quantity,
                                          price=str(price), fee=str(fee)))
        result = Engine().run(trade_dates=self.days, instruments=self.members,
                              initial_cash=[CashBalance(currency=Currency.USD, amount=D(1_000_000))],
                              daily_prices=self.close, daily_rebalance_prices=references,
                              daily_execution_prices=self.open, daily_fx_to_cnh=self.fx,
                              decision_dates_by_trade_date=decision_dates,
                              target_schedule=schedule, transaction_cost_bps=D(str(cost)))
        return result, fills


def calculate_tracked(cost_bp=5.0, delay=0, *, clock="dynamic", trigger=0.10):
    """Application-side calculation of the tracked artifact payload."""
    provenance = verified_input_provenance()
    panel = _load_panel()
    recipe = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
    params = frozen_parameters()
    active, scores = _sleeve_signals(panel, params)
    targets, indices, condition, theoretical = build_targets(
        panel, active, scores, clock=clock, trigger=trigger, return_theoretical=True)
    replay = _Replay(panel, recipe, OOS_START)
    result, fills = replay.run_result(targets, indices, cost_bp, delay)
    payload = report_payload(replay, result, fills)
    nav = np.array([float(r["nav_cnh"]) for r in payload["nav_series"]])
    latest = [dict(symbol=s, target_weight=str(round(float(w), 12)))
              for s, w in zip(replay.symbols, theoretical[-1], strict=True) if w > 0]
    if verified_input_provenance() != provenance:
        raise ValueError("Conditional inputs changed during calculation")
    return dict(**payload, accounting_currency="USD", input_provenance=provenance,
                latest_targets=latest, fills=fills,
                condition=dict(threshold=params["condition"]["threshold"],
                               true_in_window=float(np.mean(list(condition.values())))),
                metrics=dict(cagr=float((nav[-1] / nav[0]) ** (252 / (len(nav) - 1)) - 1),
                             final_nav=float(nav[-1]), sessions=len(result.nav_series),
                             rebalances=len(result.proposals)))


def report_payload(replay, result, fills):
    """Use actual fills, cash and final positions, including the initial cash anchor."""
    payload = result.model_dump(mode="json")
    anchor = str(replay.a["days"][replay.indices[0] - 1])
    payload["nav_series"].insert(0, dict(trade_date=anchor, nav_cnh="1000000",
                                       cash_cnh="1000000", gross_exposure_cnh="0"))
    by_day = {}
    for fill in fills:
        by_day.setdefault(fill["date"], []).append(dict(
            symbol=fill["symbol"], side="buy" if fill["quantity"] > 0 else "sell",
            quantity=abs(fill["quantity"]), price=fill["price"], fee=fill["fee"]))
    for proposal in payload["proposals"]:
        proposal["known_through"] = proposal["as_of"]
        proposal["orders"] = by_day.get(proposal["intended_trade_date"], [])
    return payload


def build_definition():
    return definition()
