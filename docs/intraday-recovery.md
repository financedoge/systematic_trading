# Intraday outage recovery

The recorder now owns a durable historical acquisition worker. It starts with
the service, runs after hours and on weekends, and works alongside prospective
capture. Scope: the configured pilot (`SPY/QQQ/TLT/GLD/IWM`), US regular sessions,
IB `TRADES`, 5-second bars. True tick recovery is not enabled.

## OHLCV versus sampled quotes

The older `delayed-trades` channel buckets `reqMktData` last-price callbacks.
These are incomplete samples: its extrema, summed sizes and counts are not
the full interval's high/low, traded volume or trade count. October 4 inspection
found 32,917 of 32,923 such records contained a single observation and identical
OHLC values. They must not be treated as true five-second OHLCV. Their original
hashed evidence is preserved; new records also carry
`ib_sampled_quotes_incomplete_ohlcv` and `bar_source=ibapi_sampled_quotes`.

The audit API retains these records in `rows`, labels them `sampled_quotes`,
and excludes them from chart-ready `bars`. `bar_origin=ib_ohlcv` filters them
before applying the row limit; `bar_origin=sampled_quotes` inspects samples.
Recorded Bars defaults to historical IB OHLCV, shows candles without a close-line
overlay, and initially zooms to the latest 120 loaded observations. Full loaded
range and pan/zoom remain available. Capture dates label file reception dates;
the candles use original exchange timestamps in UTC. Flat *broker* OHLCV bars
remain valid source observations, including broker-returned zero-volume periods.

A fresh read-only Gateway request matched all OHLCV fields in 60 recovered SPY
bars. Evidence: `var/research/intraday-ohlcv-source-probe.json` and
`intraday-ohlcv-diagnostic.json`. The SDK also exposes historical VWAP as `wap`;
the adapter now reads that field with legacy `average` compatibility. Earlier
records with missing WAP remain unchanged; OHLCV was unaffected.

Actual OHLCV without the required realtime entitlement arrives through historical
recovery. Each fixed hourly window becomes eligible 20 minutes after its end;
bootstrap backlog and IB responses can add delay. Sampled quote capture is not
a replacement for a complete live feed. Recovery does not count sampled records
as completed coverage.

## Findings and repair

The old service recovered only after an unsuccessful in-memory capture chunk,
looked back one hour and skipped recovery while the exchange was closed. Restart
forgot the failure. Delayed quote/trade callbacks can produce sparse aggregates.

IB warning 2188 was incorrectly treated as a terminal request failure. An October
4 probe returned all 60 requested October 2 bars after the warning. The client now
retains it and a freshness-limitation flag, waits for `historicalDataEnd`, and
still fails on real errors, timeouts or write failures. The warning alone cannot
establish successful completion.

## Acquisition contract

- Bootstrap six calendar months and discover new closed hourly windows on every
  pass, respecting New York sessions, DST, holidays and early closes. The calendar
  is not an emergency-closure feed. Wait 20 minutes for delayed data to settle.
- Alternate recent gaps and oldest retrievable windows. Sparse stream samples
  cannot suppress a complete historical request.
- One request at a time, normally at least 30 seconds between starts, including
  restarts. Other clients share the same Gateway pacing allowance.
- Persist a claim before requesting; commit coverage only after acknowledged
  completion, validated symbol/timestamps, raw/catalog durability and outbox
  persistence. Complete means every expected 5-second slot was observed, not
  that IB provides a certified exchange tape.
- Empty/errors retry with backoff capped at five minutes; explicit entitlement
  errors wait an hour. Sparse completed responses retain missing-slot counts and
  retry daily. Other symbols continue. Expired gaps remain unresolved; never fill,
  interpolate or silently substitute sources.
- Crashes can repeat raw evidence for an uncommitted window. Deterministic event
  IDs prevent duplicate logical events; completed windows are skipped.
- PostgreSQL publishes each bounded event batch transactionally, after individually
  durable raw/catalog writes. Catalog appends serialize concurrent writers and
  recovery raw files have unique names.
- Respect the raw-spool free-space stop watermark. The parent restarts exited
  workers and stops workers with a heartbeat older than ten minutes. Explicit
  recorder stop also stops recovery and retains its checkpoint.

IB documents six-month retention for bars of 30 seconds or less, at most 60
small-bar requests per ten minutes and one-hour requests for 5-second bars.
Instrument availability and entitlements can limit recovery. See
[historical limits](https://interactivebrokers.github.io/tws-api/historical_limitations.html)
and [message codes](https://www.interactivebrokers.com/docs/tws-api/doc/error-handling/error-codes).

## Operation

Normal platform/recorder startup starts recovery automatically on separate
read-only market-data client ID **221**. Use `-RecorderRecoveryClientId` when
that ID is allocated elsewhere. `-DisableIntradayRecovery` pauses acquisition
for maintenance. `-RecorderRecoveryStartDate YYYY-MM-DD` narrows a new bootstrap;
an existing checkpoint retains its earlier scope. Legacy one-hour gap-fill flags
remain accepted for launcher compatibility but no longer control recovery.
A different bar-size/type contract requires disabling this recovery worker.

Standalone finite canary: `.venv/Scripts/python.exe scripts/recover_ib_intraday.py
--max-requests 2`. Do not run it against an active service checkpoint: an OS lock
allows only one writer. A full five-symbol bootstrap takes many hours; keep the
platform and authenticated Gateway running. It resumes automatically next startup.

- Coverage: `var/run/market_data_recorder.recovery.json`
- Append-only attempts: `var/run/market_data_recorder.recovery.attempts.jsonl`
- Status: `var/run/market_data_recorder.recovery.state.json`, also included in
  the parent recorder's health details.
- Operational log: `var/log/intraday_recovery.jsonl`
- Raw evidence: configured hot spool, original exchange timestamps, actual
  receive/availability timestamps. Reception-date partitions remain honest:
  an October capture may contain April observations.

Market Data / Recorded Bars reads this evidence. Catalog queries now stream
manifests and retain bounded result rows or compact symbol/date summaries.
Large manifest scans still take time; normalized intraday serving is future work.

Recovered bars carry historical/filtered-trade flags and unknown realtime/delayed
mode rather than inferring it from a request setting. They are raw evidence,
**not published audited strategy inputs**. Historical availability, adjustment and
source-completeness limitations remain. No strategy or trading authority changes.
