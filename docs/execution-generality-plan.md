# Execution generality — routing any admitted IB contract

Registered 2026-10-10 at the user's direction. The execution path must not have to
be rebuilt each time a new underlying joins a strategy. Today it effectively does:
adding an instrument means editing hand-written universe dicts, and adding a
*strategy* means making a hand-coded allocation decision.

This is a **platform** workstream. The research programme in
[the signal decay and alpha plan](signal-decay-and-alpha-plan.md) continues in
parallel and is not blocked by it.

## The principle: capability is not admission

Two things are fused today and must be separated.

- **Capability** — the engine can route any contract whose identity and market
  rules are verified. This should be **general** and require no code change per
  instrument.
- **Admission** — which contracts are permitted to trade *now*. This should be
  **narrow, explicit and evidence-bound**, and reviewed like any other gate.

The current design fuses them: `universe_key` selects a hand-written Python dict,
and `strategy_lifecycle.py` hard-codes which strategies may be allocated. So
capability is as narrow as admission, and every widening is a code change.

Lifting admission to "everything IB lists" is **not** the goal and would be
unsafe. The goal is that widening admission costs *evidence and a registry entry*,
not a rebuild.

## What actually constrains the universe today

| Constraint | Where | Effect |
| --- | --- | --- |
| Universes are hand-written `Instrument` dicts selected by `universe_key` | `research/etf_universe.py`, `all_weather_universe.py`, `stock_universe.py` | A new underlying is a code edit plus a new `universe_key` branch |
| Any symbol outside the passed-in `instruments` mapping is rejected | `execution/broker.py:299-302`, `:345` | The route universe is whatever the caller hard-coded |
| `IBContractSpec` carries only symbol, security type, exchange, currency, primary exchange | `execution/broker.py:54-59` | No `conId`, no ISIN, no local symbol, no multiplier — identity is a ticker guess |
| Two strategies are hard-coded as not allocation-supported | `research/strategy_lifecycle.py:113` | This is the "Catching up" the user saw; opening it needs a code edit, not evidence |
| Audited price lane requires `currency == "USD"` and `instrumentType == "ETF"` | `research/governed_refresh.py:144` | No non-USD or non-ETF series can ever be admitted |
| Routing assumes US sessions and a US/Eastern window | `live/sota.py:113,281`; `execution/window.py` | A Tokyo or Hong Kong leg has no defined execution window |
| No lot size, board lot, or contract multiplier anywhere | verified absent | HKEX board lots and TSE 100-share lots would be ordered in wrong quantities |

## Target design

### 1. Contract identity registry (the foundation)

Resolve every instrument through IB `reqContractDetails`, not through a ticker
string. Retain the raw response, audit it, and publish an immutable
hash-versioned registry exactly like the existing governed-data lane. The registry
is the single source of contract truth: `conId`, `secType`, `symbol`,
`localSymbol`, `exchange`, `primaryExchange`, `currency`, `multiplier`,
`minTick`, `marketRuleIds`, `tradingClass`, `validExchanges`.

**Ambiguity is the hard part, and it must be designed for now.** `BHP` is an ADR
on NYSE, a listing on LSE and one on ASX; `7203` in Tokyo is not the same string
as its ADR. Resolution therefore requires disambiguation keys — at minimum an
ISIN, optionally an exchange and currency hint — and must **fail closed** on
ambiguity rather than silently picking the first match. A ticker-only lookup is
the failure mode this replaces, so it must not be reintroduced as the new
default.

### 2. Universe becomes a query, not a literal

`universe_key` stops meaning "one of three Python dicts". A universe becomes a
declared **selector over the registry** (asset class, admission state, currency
set, listing venue) plus an explicit membership list where a strategy needs a
frozen set. Strategy definitions keep naming their members; the engine resolves
them through the registry.

### 3. Admission gate

A contract is tradable only when all of the following hold, each with retained
evidence:

1. identity verified against the registry (ISIN or `conId` match, no ambiguity);
2. an audited price history exists on a supported basis, under the existing
   audit and publication process;
3. a CNH FX path exists for its currency, with point-in-time discipline;
4. IB reports it as tradable for this account (`reqContractDetails` plus account
   permission), not merely as listed;
5. the market's trading rules are registered (calendar, lot size, tick).

Admission is a state, not a flag in code: granting it produces an immutable
event, and the platform can answer "why is this not tradable" for every
instrument.

### 4. Capability check replaces the hard-coded strategy gate

`strategy_lifecycle.py`'s literal set is replaced by a computation: a strategy is
allocation-supported when **every** instrument in its resolved universe is
admitted for execution *and* the strategy's execution contract is registered.
Then FR25 and M1/14 become allocatable the moment XLE and XLB are admitted, with
**no code edit** — which is the property the user is asking for.

### 5. FX as a first-class requirement

Every instrument carries a quote currency; every portfolio value is CNH. The FX
path is currently an unresolved input class, so this is a genuine prerequisite
rather than a detail. Required: per-currency CNH rates with the same
point-in-time and audit discipline as prices, and a declared policy for which
source is authoritative per pair. Without it, "any IB tradable" silently means
"any USD tradable".

### 6. Calendars and execution windows

Each listing venue needs its own session calendar (the `exchange-calendars`
dependency is already present) and an execution window expressed in that venue's
timezone. The rebalance convention must be defined for asynchronous sessions:
a decision taken on the primary calendar's close, with each leg executing in its
own market's next eligible window, and the strategy's valuation date defined
explicitly rather than assumed. Holidays, half-days and venue closures all flow
from the same registry entry.

### 7. Market rules: lot size, tick, minimum

Board lots (HKEX), hundred-share lots (TSE) and venue tick regimes must be
enforced at sizing time. Whole-unit accounting already exists; lot multiples do
not, and without them quantities are wrong in a way that would only surface as
broker rejections or unintended exposure.

### 8. Reconciliation, monitoring and reporting

Reconciliation matches on `order_ref` and compares positions, so it is already
symbol-agnostic and should need little change. What must generalise: the FX and
staleness checks keyed on the universe, the country/currency exposure
aggregation, and the reports' assumption of a single trading calendar.

### 9. Multi-currency data lane

The governed recorder's USD-ETF-only restriction must widen with its own audit
path — source per venue, retention rights, adjusted/raw basis per market, and
corporate-action coverage. This is the largest genuinely unknown piece and
depends on source and licence decisions that are not engineering.

## Work items

| ID | Item | Acceptance |
| --- | --- | --- |
| P8.1 | Contract identity registry with raw-retained, audited, published IB `reqContractDetails` | Registry publishes immutably with verified hashes; ambiguity fails closed; re-derivable from retained raw evidence |
| P8.2 | Symbol → contract resolution with explicit disambiguation keys | Ambiguous tickers are rejected, not guessed; resolution is deterministic and recorded |
| P8.3 | Registry-backed universe selectors replacing literal dicts | Existing universes resolve identically to today's dicts; a new instrument needs a registry entry, not a code edit |
| P8.4 | Instrument admission gate with immutable events | Every instrument can answer "why is this tradable / not tradable" with evidence |
| P8.5 | Capability check replacing the hard-coded allocation gate | FR25 and M1/14 become allocation-supported by admitting their members, with no code change |
| P8.6 | Per-currency CNH FX path with point-in-time discipline | Non-USD instruments can be valued and reconciled in CNH |
| P8.7 | Per-venue calendars and execution windows | A non-US leg has a defined, tested execution window and valuation date |
| P8.8 | Lot size, tick and minimum-size enforcement at sizing | HKEX and TSE style lots cannot produce an invalid quantity |
| P8.9 | Multi-currency governed price lane | Non-USD, non-ETF series admitted through the existing audit and publication process |
| P8.10 | Generalised exposure, staleness and reporting | Country/currency aggregation and reports correct across venues and calendars |

## First customer: XLE and XLB

Deliberately narrow, and it is the whole point. The **only** allocation blocked
today is the 14-ETF pair, and it needs exactly two more instruments admitted.
Rather than admit them by extending a literal dict — which is the pattern being
retired — build P8.1–P8.5 and use XLE and XLB as their first entries.

That opens the 14-ETF execution gate through the general mechanism and proves it
on a real case, instead of building a general mechanism speculatively and hoping a
future asset exercises it. It also removes the hard-coded strategy set, so the
next strategy needs no code edit at all.

## Explicit non-goals

- **Not "trade everything IB lists."** Options, futures, CFDs, bonds, warrants,
  crypto and short selling stay out of scope. `docs/live-rollout.md` fixes v1 at
  long-only stocks and ETFs; this plan generalises *identity and venue handling*,
  not the instrument scope.
- **No weakening of any gate.** Approval, reconciliation, broker-environment,
  live-disabled and execution-window checks keep their current strength. The
  capability check is a *replacement* for a hard-coded list, not a relaxation.
- **No speculative rewrite of research universes.** Research definitions keep
  their frozen membership; only the resolution mechanism changes.
- **No admission by convenience.** An instrument that cannot satisfy all five
  admission conditions stays untradable, and says why.

## Blockers that cannot be engineered around

- **FX is an unresolved input class.** Until per-currency CNH rates have audited,
  point-in-time histories, every non-USD instrument is blocked regardless of code.
- **No security master.** Identity certification for a wide universe shares the
  access gap recorded for CRSP under P3.7 and P3.8. IB's own contract details are
  a partial substitute for *tradability*, not for *historical identity*.
- **Source and licence decisions** for non-US price history, which are commercial
  rather than technical.

## Sequencing

P8.1 → P8.2 → P8.3 → P8.4 → P8.5 is the critical path to the user's actual
complaint, and none of it needs FX, calendars or data widening, because XLE and
XLB are US-listed USD ETFs. That is why the first customer is narrow.

P8.6 onward is what makes the path genuinely general, and P8.6 and P8.9 are
blocked on data and source decisions rather than on engineering. They should be
sequenced behind the research programme, not ahead of it.

Research is not blocked by any of this and continues in parallel.
