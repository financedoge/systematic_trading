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

## Event contracts

The initial versioned event contracts live in `systematic_trading.domain.events`. These models define the message-envelope shape before a queue is introduced, so producers and consumers can be implemented against stable contracts.

Current event families:

- Market data recorded.
- Feature computed.
- Proposal created and proposal decision recorded.
- Order intent created and order status changed.
- Fill recorded.
- Reconciliation completed.
- Alert raised.
- Incident recorded.

All events include an event id, event type, schema version, timezone-aware occurrence timestamp, source service, optional correlation and causation ids, and a typed payload. Queue subjects follow `systematic_trading.events.v{schema_version}.{event_type}`.

The active code-based schema registry lives in `systematic_trading.schemas`. The registry convention and compatibility rules are documented in `docs/schema-registry-convention.md`.

The current local durable outbox is implemented by `SQLiteStore` using the `platform_event_outbox` table. It stores each event once by `event_id`, lists unpublished events in append order, records publish attempts and last error, and marks successful publishes with `published_at`. The queue-agnostic dispatcher lives in `systematic_trading.messaging.outbox`; future NATS, Redpanda, or Kafka adapters should implement the same publisher protocol.

The initial queue adapter target is NATS JetStream. See `docs/queue-adapter-selection.md`.

The market-data raw-before-publish contract is `docs/market-data-recorder-contract.md`.
The recorder source and capacity plan is `docs/market-data-recorder-source-plan.md`, with machine-readable policy in `config/market-data-recorder-sources.json`.

The target transactional store design is `docs/postgres-transactional-store-design.md`.

The target columnar analytics design is `docs/columnar-store-target-design.md`.

The app and long-running services consume the transactional store through protocol contracts in `systematic_trading.storage.interfaces`.
`systematic_trading.storage.create_transactional_store` is the composition boundary; `ST_TRANSACTIONAL_STORE_BACKEND=sqlite`
is the only implemented backend today, and unsupported backends fail explicitly until the Postgres adapter is built.

Local dispatch command:

```powershell
.\.venv\Scripts\python.exe .\scripts\dispatch_event_outbox.py `
  --database var\systematic_trading.db `
  --output var\events\platform_events.jsonl
```

Use `--loop --interval-seconds 5` for a polling dispatcher. The JSONL publisher is a local operational sink, not the final message bus.

NATS dispatch command after Docker/NATS and `ST_EVENTS` are running:

```powershell
.\.venv\Scripts\python.exe .\scripts\dispatch_event_outbox.py `
  --database var\systematic_trading.db `
  --publisher nats `
  --nats-url nats://127.0.0.1:4222
```

Replay command:

```powershell
.\.venv\Scripts\python.exe .\scripts\replay_platform_events.py `
  --source jsonl `
  --jsonl var\events\platform_events.jsonl
```

Use `--source outbox --published all|published|pending` to replay directly from SQLite. Replay returns typed event records through `systematic_trading.messaging.replay` and can print either a summary or full event details.

Current transactional producers:

- `save_proposal` emits `proposal.created`.
- `apply_decision` emits `proposal.decision_recorded`.
- `save_broker_order_record` emits `order.status_changed`.
- `save_broker_order_record` also emits `fill.recorded` when a saved broker record contains filled quantity and average fill price.

## Service health contract

The normalized platform health contract lives in `systematic_trading.services.health` and is exposed by `GET /health`.

Each long-running service must report:

- `service_id`.
- `running`.
- `heartbeat_at`.
- `last_error`.
- Optional `started_at`, `message`, and operational `details`.

The platform health response contains an overall `status`, `checked_at`, and one record per service declared in `config/service-manifest.json`. State-file based services write compact JSON heartbeat files; the event outbox dispatcher writes `var/run/event_outbox_dispatcher.state.json`.

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
