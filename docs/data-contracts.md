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
- Fundamental snapshot: valuation and quality fields keyed by symbol and as-of date.
- Research artifact: filing, transcript, memo, or note with source metadata.

## Currency policy

- CNH is the reporting currency for NAV, exposure, and risk.
- FX inputs are stored as `1 unit of base currency = X CNH`.
- Cross-currency conversion is derived through CNH.

## Validation rules

- Reject zero or negative FX rates.
- Reject missing FX rates when a non-CNH instrument must be valued.
- Reject proposal previews when a symbol is missing an instrument, price, or volatility input.
- Keep source payloads and normalized tables both available for audit.
