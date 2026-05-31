# Data Contracts

## Source precedence

1. Paid global end-of-day vendor for primary OHLCV and corporate actions.
2. Interactive Brokers for live and paper prices, account state, and execution feedback.
3. Structured filings and macro feeds such as SEC EDGAR, EDINET, DART, HKEX issuer documents, FRED, and OECD.
4. Yahoo Finance and Stooq only as reference fallbacks for reconciliation, never as the source of record.

## Normalized entities

- Instrument: symbol, exchange, country, asset class, quote currency, sector.
- Price bar: trade date, open, high, low, close, volume.
- Corporate action: dividend amount and split ratio by effective date.
- FX rate: one base currency unit translated into CNH.
- Fundamental snapshot: valuation, quality, balance-sheet, and revision fields keyed by symbol, period end, and availability date. Historical research must filter by `available_date <= rebalance_date`.
- Research artifact: filing, transcript, memo, or note with source metadata.
- Broker order record: local order id, proposal id, broker, environment, broker order id, status, order payload, timestamps, fill quantities, average fill price, and broker message.

## Currency policy

- CNH is the reporting currency for NAV, exposure, and risk.
- FX inputs are stored as `1 unit of base currency = X CNH`.
- Cross-currency conversion is derived through CNH.

## Validation rules

- Reject zero or negative FX rates.
- Reject missing FX rates when a non-CNH instrument must be valued.
- Reject proposal previews when a symbol is missing an instrument, price, or volatility input.
- Reject broker routing unless the proposal is approved, the route is paper, no duplicate broker order records exist, and the order environment matches the route environment.
- Keep source payloads and normalized tables both available for audit.
