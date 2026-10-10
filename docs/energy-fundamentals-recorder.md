# EIA energy fundamentals recorder

Implemented October 8, 2026. The application research analytics lane owns
`recorders/energy.py`, using `config/energy-recorders.json`. It checks the free
official EIA files hourly while the application is running. Petroleum and gas
publish independently, so one failed source does not prevent the other capture.
Market Data → Energy Data exposes releases, captured versions, units, coverage,
revision flags and availability. The CLI `scripts/run_energy_recorder.py` invokes
the same capture/publication service. No account or API subscription is needed.

## Sources and interpretation

The [Weekly Petroleum Status Report](https://www.eia.gov/petroleum/supply/weekly/)
provides crude stocks excluding SPR, SPR stocks, gasoline and distillate stocks,
domestic crude production, imports, exports, refinery crude inputs, total/
gasoline/distillate products supplied, and refinery utilization. The recorder
reads `psw00.json`, `table1.csv` and `table9.csv` from the official `ir.eia.gov`
release links. Inventory units are million barrels; flows are thousand barrels
per day; utilization is percent. Exact row/column identity and common report
dates are required. Commercial crude stocks are cross-checked between the JSON
and CSV with an explicit 1,000-unit conversion. Published level differences can
differ from EIA's rounded change column; normalized `change` is the difference
of the displayed current/prior levels, and the full original row is retained.

The [Weekly Natural Gas Storage Report](https://ir.eia.gov/ngs/ngs.html) provides
Lower 48 working gas, net change, implied flow, five-year average and percent
deviation from that average. Values and revision/reclassification flags come
from `wngsr.json`. Its midnight `release_date` is a date placeholder, not a
release clock. The recorder requires a matching report period/date and explicit
time from the release HTML. Net change and implied flow remain separate.

These are timely physical-activity and inventory context, not automatically
leading indicators or identified economic shocks. Products supplied is apparent
demand; weekly production may be re-benchmarked. Gas storage also depends on
weather and reclassification. No analyst-consensus feed is available, so weekly
changes must not be labelled market surprises. Original-release EIA Short-Term
Energy Outlook forecasts are a possible subsequent leading-input source and
require their own vintage qualification.

## Availability and revision contract

Every response is saved before parsing under `var/governance/eia-energy/` with
its request URL, exact bytes, hash and response-completion timestamp. Config,
parser/recorder hashes, normalized snapshot and a file manifest establish the
capture. ClickHouse readback verifies observations/documents before the product
catalog commits. Failed attempts retain evidence; the prior publication remains
readable. Unchanged normalized reports retain their original capture boundary.
Revisions append captures, including revisions with the same nominal release
timestamp. No previous release is overwritten.

Source release times are read from source metadata, interpreted in New York
time with DST, and kept separate from actual first capture. There is no computed
Wednesday/Thursday release schedule: the official
[petroleum](https://www.eia.gov/petroleum/supply/weekly/schedule.php) and
[gas](https://ir.eia.gov/ngs/schedule.html) calendars include holiday exceptions,
and gas has [out-of-cycle revisions](https://ir.eia.gov/ngs/revisions.html).
Mixed release dates, unknown schemas/identities, future releases, regressing
releases, duplicate/gapped rolling history and non-finite values fail audit.
Recognized missing observations remain null; they are never filled.

`EnergyInputs(root, batch).snapshot(decision_at=...)` requires a pinned published
catalog and verifies all files for the selected capture. It selects only versions
first seen strictly before the timezone-aware decision timestamp, enforces a
14-day observation-age limit and rejects missing current indicators. A source
release timestamp never permits use before capture. Restoring state or fetching
an older file cannot backdate knowledge.

The petroleum JSON supplies a six-year rolling history in a **current release**.
All its rows share that release capture's availability. They may support a
lookback calculated after capture, but cannot be assigned to historical decisions.
The inspected October 7 archive page displayed September 30 metadata while its
table referred to October 2 observations; historical archive qualification is
therefore unresolved. A URL date alone is insufficient evidence. No energy
historical return backtest or performance claim accompanies this recorder.

## Initial evidence

Both products report the week ending October 2, 2026. Petroleum's source release
is October 7 at 14:30 UTC; first capture is October 8 at 15:44:22.128948 UTC.
Gas's source release is October 8 at 14:30 UTC; first capture is 15:44:30.583014 UTC.
There are 12 petroleum and five gas indicators. The petroleum snapshot also
contains 314 crude-stock observations from October 2, 2020 to October 2, 2026,
all usable only after its capture boundary.

Published catalog pins:

- Petroleum: `e9dc9194fb3da76491a7e63b47a17a7ed19bfab316485be86259538c45d87d91`.
- Natural gas: `f0654328d09b8bdf05b900e4cb512483ca5c78e6e4f705d2fcf4a4bc73b0d355`.

Publication/source qualification evidence is retained under
`var/research/energy-source-qualification-20261008/`. Test fixtures are shortened
official release excerpts: the crude history is restricted to three dates and
the gas file to the Lower 48 series. They are parser fixtures, not research inputs.

## Next research stage

First admit a small, economically distinct ETF set: broad energy equities,
exploration/production, and commodity exposures whose roll/collateral economics
are explicitly understood. Sector chemicals/materials require their own activity
and valuation sources. Each fund needs issuer identity, holdings/shares/NAV
records, audited adjusted prices and separately audited raw activity data, plus
IB contract and account eligibility. Public fund descriptions do not establish
account tradability. Keep single-stock trading outside the study.

Freeze the expanded-universe control before comparing fundamental signals.
Prespecify three small feature groups: inventory tightness/change, four-week
demand and refinery activity, and gas storage relative to the reported five-year
average. Use only the vintage available at each decision; seasonal transforms
and any internal forecast must fit on completed past observations. Treat
internally predicted residuals separately from unavailable consensus surprises.

Compare per-ETF linear and depth-two tree responses with unconstrained response
signs: the same energy condition can affect commodity exposure, producers and
energy-consuming sectors differently. Such estimates are predictive associations,
not causal shock identification. Include a matched expanded-universe control and
availability/sample control, net costs, delayed decisions, drawdowns, concentration,
turnover and finite-family uncertainty. Use all available cores for independent
backtests. Collect sufficient prospective observations or qualify original-release
archives before fitting; the initial recorder publication alone cannot train this
experiment. The monitored economic ridge remains frozen until that stage.
