"""App-owned tracked candidate: FR25 + conditional short life-cycle sleeve.

This module freezes the strategy inputs and provides an application-side calculation of the
candidate's daily targets, NAV, proposals and final snapshot. It is registered as a versioned
strategy definition but is NOT in the monitored membership: the tracked-strategy runtime still
requires a LEAN bundle/native calculation path and an operator-approved monitoring config
change before it can publish this candidate as a monitored strategy.

Research/paper candidate only. No broker, approval, allocation or live authority.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path

import numpy as np

from systematic_trading.research import range_lifecycle as rl

ROOT = Path(__file__).resolve().parents[3]
KEY = "fr25_lifecycle_conditional_v1"
VERSION = "1.0.0"
PARAMETERS_PATH = Path(__file__).with_name("fr25_lifecycle_conditional_parameters.json")
INPUTS_PATH = ROOT / "var/research/range-breakout-20261018-v2/pool/inputs.npz"
RECIPE_PATH = ROOT / "var/research/range-breakout-20261018-v2/pool/recipe.json"
OOS_START = "2023-01-03"
WARMUP = 252


def frozen_parameters() -> dict:
    return json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))


def definition():
    """Registered strategy definition (candidate; never confers monitoring authority)."""
    from systematic_trading.research.strategy_catalog import OverlaySpec, fr25_definition
    base = fr25_definition()
    return replace(
        base,
        key=KEY,
        name="FR25 80/20 + conditional short life-cycle sleeve",
        sleeve_name="fr25-lifecycle-conditional-v1",
        state="candidate",
        promoted_on=None,
        scheduler="dynamic_monthly",
        description=("Frozen FR25 SOTA monthly targets at 80% of the budget plus a 20% Rule A "
                     "short-only life-cycle sleeve when stable union breadth is at or above its "
                     "pre-2023 median; dynamic 10% L1 target-change rebalancing. Candidate only: "
                     "not in the monitored membership."),
        overlays=(*base.overlays, OverlaySpec(kind="lifecycle_conditional_sleeve",
                                              parameters={"version": VERSION})),
    )


def _load_panel():
    return dict(np.load(INPUTS_PATH, allow_pickle=True))


def _sleeve_signals(panel, params):
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    order = [str(s) for s in panel["symbols"]]
    active = np.zeros((len(days), len(order)), bool)
    for j, symbol in enumerate(order):
        path = ROOT / "var/research/range-breakout-20261018-v2/assets" / f"{symbol}.npz"
        data = {k: np.asarray(np.load(path, allow_pickle=True)[k])
                for k in ("open", "high", "low", "close", "volume", "days")}
        features = rl.Features.build(data, rl.SHORT_SPEC)
        vector = rl.SHORT_SPEC.canonical(params["sleeve"]["short_parameters"][symbol])
        prepared = rl.prepare(features, vector)
        sim = rl.simulate(features, prepared, start=WARMUP, cost_bp=5.0, trace=True)
        lookup = {str(np.datetime64(d, "D")): i for i, d in enumerate(features.days)}
        for i, day in enumerate(days):
            t = lookup.get(day)
            if t is not None:
                active[i, j] = int(sim["state"][t]) == rl.STATE_LONG
    return active


def _monthly_indices(panel):
    days = [str(np.datetime64(d, "D")) for d in panel["days"]]
    initial = int(np.flatnonzero(np.array(days) <= "2022-12-30")[-1])
    indices, previous = [initial], days[initial][:7]
    for t in range(initial + 1, len(days)):
        month = days[t][:7]
        if month != previous:
            indices.append(t - 1)
            previous = month
    return np.array(indices, dtype=int)


def build_targets(panel, active):
    params = frozen_parameters()
    threshold = params["condition"]["threshold"]
    breadth = params["condition"]["breadth_by_session"]
    n = panel["close"].shape[0]
    n_assets = panel["close"].shape[1]
    fr25 = np.column_stack([panel["fr25"], np.zeros(n)])
    monthly = _monthly_indices(panel)
    condition = {int(t): bool(breadth[t] >= threshold) for t in monthly}
    holdings: list[int] = []
    targets = np.zeros((n, n_assets + 1))
    indices: list[int] = []
    fr25_current = np.zeros(n_assets + 1)
    adopted = np.zeros(n_assets + 1)
    cash = len(panel["symbols"])  # URTH column; candidate holds no URTH
    for day in range(int(monthly[0]), n):
        if day in set(int(t) for t in monthly):
            fr25_current = fr25[day]
        for j in list(holdings):
            if not active[day, j]:
                holdings.remove(j)
        new = [j for j in np.flatnonzero(active[day]) if active[day - 1, j] == 0
               and j not in holdings and j != cash]
        room = 6 - len(holdings)
        if room > 0 and new:
            holdings.extend(new[:room])
        if condition.get(int(monthly[np.searchsorted(monthly, day, side="right") - 1]), False):
            sleeve = np.zeros(n_assets + 1)
            if holdings:
                sleeve[holdings] = 0.2 * 0.98 / len(holdings)
            desired = 0.8 * 0.98 / max(1e-9, fr25_current[:-1].sum()) * fr25_current + sleeve \
                if fr25_current[:-1].sum() > 0 else sleeve
        else:
            desired = fr25_current.copy()
        if day in set(int(t) for t in monthly) or np.abs(desired - adopted).sum() >= 0.10:
            targets[day] = desired
            indices.append(day)
            adopted = desired.copy()
    return targets, np.array(indices, dtype=int), condition


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
        self.fx = {day: {"USD": D(1)} for day in self.days}

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
        from systematic_trading.backtest.engine import DailyBacktestEngine
        from systematic_trading.backtest.accounting import quantize_money
        from systematic_trading.domain.portfolio import CashBalance
        from systematic_trading.domain.enums import Currency
        schedule = self.decisions(weights, indices, delay)
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
                              daily_prices=self.close, daily_rebalance_prices=self.reference,
                              daily_execution_prices=self.open, daily_fx_to_cnh=self.fx,
                              target_schedule=schedule, transaction_cost_bps=D(str(cost)))
        nav = np.array([float(r.nav_cnh) for r in result.nav_series])
        return nav, fills


def calculate_tracked(cost_bp=5.0, delay=0):
    """Application-side calculation of the tracked artifact payload."""
    panel = _load_panel()
    recipe = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
    params = frozen_parameters()
    active = _sleeve_signals(panel, params)
    targets, indices, condition = build_targets(panel, active)
    replay = _Replay(panel, recipe, OOS_START)
    nav, fills = replay.run(targets, indices, cost_bp, delay)
    days = replay.days
    proposals = []
    for t in indices:
        execution = t + 1 + delay
        if execution >= len(panel["days"]):
            continue
        scheduled = date.fromisoformat(str(panel["days"][execution]))
        held = [dict(symbol=replay.symbols[j], target_weight=str(round(float(w), 12)))
                for j, w in enumerate(targets[t]) if w > 0]
        proposals.append(dict(as_of=str(panel["days"][t]), intended_trade_date=str(scheduled),
                              known_through=str(panel["days"][t]),
                              targets=held, orders=[]))
    day = days[-1]
    positions = []
    for j, symbol in enumerate(replay.symbols):
        if symbol == "URTH":
            continue
        price = float(replay.close[day][symbol])
        nav_value = nav[-1] * targets[indices[-1]][j]
        if nav_value > 1 and price > 0:
            positions.append(dict(symbol=symbol, quantity=int(nav_value / price),
                                  market_price=price))
    return dict(nav_series=[dict(trade_date=str(d), nav_cnh=str(nav[i]),
                                cash_cnh=str(nav[i] * 0.02), gross_exposure_cnh=str(nav[i] * 0.98))
                            for i, d in enumerate(days)],
                proposals=proposals, final_snapshot=dict(nav_cnh=str(nav[-1]), positions=positions),
                condition=dict(threshold=params["condition"]["threshold"],
                               true_in_window=float(np.mean(list(condition.values())))),
                metrics=dict(cagr=float((nav[-1] / nav[0]) ** (252 / (len(nav) - 1)) - 1),
                             final_nav=float(nav[-1]), sessions=int(len(nav)),
                             rebalances=int(len(indices))))


def build_definition():
    return definition()
