# Research ETF recorder and Treasury-bill parking

The app owns the daily research ETF recorder through its analytics research lane,
after the active ETF producer and before tracked strategy calculations. It has no
broker authority. The initial source is BIL, selected for its Treasury-bill
mandate and long history before inspecting strategy outcomes.

`config/research-etf-recorders.json` specifies issuer URL, identity tokens, ISIN,
inception, required historical start, purpose and source limitations. The
`research_etf_recorder_config_path` setting allows another explicit registry;
the normal governed-refresh switch also disables this recorder. A configured
fund is not admitted merely by appearing in the file.

Each completed US session can produce an immutable issuer HTML snapshot and
full provider price/action response. The recorder checks symbol, ETF type, USD
currency, issuer/provider name, listing boundary, required session coverage and
distribution adjustments. Existing histories also pass revision/overlap checks.
No interpolation, index substitution, current-yield backfill or automatic source
splice is performed. Single-provider audits do not certify original historical
publication availability. Today's issuer snapshot is not historical holdings.

The existing governance publisher verifies each analytical row and source
document before committing a complete catalog. State and quarantined evidence
remain under `var/governance/`; failures retry no sooner than five minutes.
Other analytics jobs continue after a research-recorder failure. Market Data's
Research data recorders section shows pending, acquiring, quarantined or
published status, dates, rows and limitations. Its status endpoint is
`/api/v1/market-data/governed/recorders`; charts use the existing published-series
endpoints. BIL is available at
`/platform/market-data-audit?view=history&series=BIL`.

Catalog inheritance retains a bounded parent chain. Before replacing a subset
of funds, verified delta files for unchanged symbols are carried forward with
an immutable origin receipt. Their original physical ClickHouse batch remains
in the catalog. This prevents the next active-universe refresh from dropping a
new research fund or reverting recently refreshed existing histories.

The initial publication is
`a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`:
4,870 BIL observations, May 30, 2007–October 6, 2026, zero internal gaps.
[State Street's issuer reference](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-bloomberg-1-3-month-t-bill-etf-bil)
identifies the May 25, 2007 inception, USD denomination, monthly distributions
and one-to-three-month US Treasury-bill mandate. Unsupported initial dates
remain absent. Reference bytes and their hash are retained in the publication.

The finite `bill-parking-v1` study consumes this published batch only, with
verified input hashes and exactly unchanged prior control prices/decisions.
F4 keeps final F1 weights and, when fewer than four original ETFs qualify, sets
`BIL = min(45%, max(0, 98% - final F1 gross))`. Normal monthly breadth targets
BIL at zero. BIL does not enter ranking, volatility sizing or model training.
The cap is a rebalance target, not an intramonth drift constraint. Adjusted fund
returns include distributions; remaining cash earns zero. Broker interest,
taxes, historical account eligibility and market impact remain unresolved.

One-time acquisition uses `scripts/run_research_etf_recorder.py`; recurring work
is the app's job. Finite research uses `scripts/run_parking_research.py` with
`prepare`, `calculate`, `native`, `analyze`, and `report` stages. Preparation
requires a new output directory and checks the operator-selected SOTA. Other
stages execute the frozen source. Use all logical CPUs for independent Python
jobs and memory-bounded native lanes. Preserve failed attempts and prior freezes.

Results and seven complete reports:
[Treasury-bill assessment](../research/bill-parking-2026-10-07/assessment.html).
No new monitored recipe, promotion or capital assignment is created by this study.
The next information workstreams are macro release vintages and prospective
issuer holdings/shares/NAV snapshots, then energy and sector fundamentals.

## Interactive Brokers requirement

User explicitly requires broker-executable strategies. The selected instrument
is **BIL**, the USD State Street SPDR Bloomberg 1-3 Month T-Bill ETF, issuer
listing NYSE Arca, ISIN `US78468R6633`. The public IBKR security listing includes
BIL. The app's existing mapper represents it as `STK / SMART / USD`; a regression
check verifies the actual IB API contract object without connecting or sending
an order. The internal NYSE exchange family is not incorrectly sent as the
primary venue: the ETF mapper leaves that field unset pending broker identity.
F4 is research-only and is not added to the current funded instrument universe.

For manual purchase, IBKR Client Portal's Trade → Order Ticket flow supports
symbol search, instrument selection, share quantity, order type/price and
preview. Select the BIL ETF in USD, not an option or another similarly named
instrument. A limit order lets the operator specify the maximum buy price;
the fund handles underlying bill holdings and rollovers. See
[IBKR order entry](https://www.interactivebrokers.com/campus/trading-lessons/client-portal-order-entry/)
and [trading permissions](https://www.ibkrguides.com/clientportal/tradingpermissions.htm).

The October 7 local paper API health check cannot connect to Gateway port 4002.
Thus account eligibility, resolved contract ID/venue, data access, order preview
and subsequent paper execution/reconciliation have not been verified. These are
required before any BIL strategy allocation; public product presence is not
account permission. Historical US ETF eligibility and broker interest also
remain distinct from price auditing. No purchase, promotion or permission change
was performed in this session.
