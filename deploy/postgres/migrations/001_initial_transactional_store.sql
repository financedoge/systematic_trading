CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS strategy;
CREATE SCHEMA IF NOT EXISTS portfolio;
CREATE SCHEMA IF NOT EXISTS execution;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS events;

CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    migration_id text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.instruments (
    symbol text PRIMARY KEY,
    name text NOT NULL,
    asset_class text NOT NULL,
    exchange text NOT NULL,
    quote_currency text NOT NULL,
    country text NOT NULL,
    sector text,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.theses (
    symbol text PRIMARY KEY,
    status text NOT NULL,
    summary text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.fundamental_snapshots (
    symbol text NOT NULL,
    period_end date NOT NULL,
    available_date date NOT NULL,
    filing_date date,
    source text,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, period_end, available_date)
);

CREATE INDEX IF NOT EXISTS idx_fundamental_snapshots_symbol_available
    ON core.fundamental_snapshots(symbol, available_date);

CREATE TABLE IF NOT EXISTS portfolio.proposals (
    proposal_id text PRIMARY KEY,
    status text NOT NULL,
    environment text NOT NULL,
    sleeve text NOT NULL,
    as_of date NOT NULL,
    intended_trade_date date,
    base_currency text NOT NULL,
    summary text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proposals_status_as_of
    ON portfolio.proposals(status, as_of DESC);

CREATE INDEX IF NOT EXISTS idx_proposals_environment_trade_date
    ON portfolio.proposals(environment, intended_trade_date);

CREATE TABLE IF NOT EXISTS portfolio.proposal_targets (
    proposal_id text NOT NULL REFERENCES portfolio.proposals(proposal_id) ON DELETE CASCADE,
    symbol text NOT NULL,
    target_weight numeric(18, 10) NOT NULL,
    sleeve text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (proposal_id, symbol)
);

CREATE TABLE IF NOT EXISTS portfolio.proposal_orders (
    proposal_id text NOT NULL REFERENCES portfolio.proposals(proposal_id) ON DELETE CASCADE,
    order_index integer NOT NULL,
    symbol text NOT NULL,
    side text NOT NULL,
    order_type text NOT NULL,
    quantity numeric(24, 8) NOT NULL,
    reference_price numeric(24, 10) NOT NULL,
    currency text NOT NULL,
    environment text NOT NULL,
    notional_cnh numeric(24, 6) NOT NULL,
    intended_trade_date date,
    payload jsonb NOT NULL,
    PRIMARY KEY (proposal_id, order_index)
);

CREATE TABLE IF NOT EXISTS portfolio.approval_decisions (
    approval_id bigserial PRIMARY KEY,
    proposal_id text NOT NULL REFERENCES portfolio.proposals(proposal_id) ON DELETE CASCADE,
    status text NOT NULL,
    decided_at timestamptz NOT NULL,
    decided_by text,
    comment text,
    payload jsonb NOT NULL,
    event_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approval_decisions_proposal
    ON portfolio.approval_decisions(proposal_id, decided_at DESC);

CREATE INDEX IF NOT EXISTS idx_approval_decisions_status
    ON portfolio.approval_decisions(status, decided_at DESC);

CREATE TABLE IF NOT EXISTS execution.broker_orders (
    local_order_id text PRIMARY KEY,
    proposal_id text NOT NULL REFERENCES portfolio.proposals(proposal_id) ON DELETE CASCADE,
    order_index integer NOT NULL,
    environment text NOT NULL,
    broker text NOT NULL,
    broker_order_id bigint,
    order_ref text NOT NULL,
    symbol text NOT NULL,
    side text NOT NULL,
    order_type text NOT NULL,
    quantity numeric(24, 8) NOT NULL,
    status text NOT NULL,
    submitted_at timestamptz,
    updated_at timestamptz NOT NULL,
    filled_quantity numeric(24, 8) NOT NULL DEFAULT 0,
    remaining_quantity numeric(24, 8),
    average_fill_price numeric(24, 10),
    message text,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (environment, order_ref),
    UNIQUE (proposal_id, order_index, order_ref)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_broker_orders_broker_order_id
    ON execution.broker_orders(environment, broker, broker_order_id)
    WHERE broker_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_broker_orders_proposal
    ON execution.broker_orders(proposal_id);

CREATE TABLE IF NOT EXISTS execution.broker_order_status_history (
    status_event_id text PRIMARY KEY,
    local_order_id text NOT NULL REFERENCES execution.broker_orders(local_order_id) ON DELETE CASCADE,
    status text NOT NULL,
    broker_order_id bigint,
    message text,
    observed_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    event_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution.fills (
    fill_id text PRIMARY KEY,
    local_order_id text REFERENCES execution.broker_orders(local_order_id) ON DELETE SET NULL,
    proposal_id text REFERENCES portfolio.proposals(proposal_id) ON DELETE SET NULL,
    environment text NOT NULL,
    broker text NOT NULL,
    broker_order_id bigint,
    order_ref text,
    symbol text NOT NULL,
    side text NOT NULL,
    quantity numeric(24, 8) NOT NULL,
    average_price numeric(24, 10) NOT NULL,
    currency text NOT NULL,
    filled_at timestamptz NOT NULL,
    commission numeric(24, 10),
    commission_currency text,
    payload jsonb NOT NULL,
    event_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fills_symbol_filled_at
    ON execution.fills(symbol, filled_at DESC);

CREATE INDEX IF NOT EXISTS idx_fills_proposal_filled_at
    ON execution.fills(proposal_id, filled_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.pnl_snapshots (
    snapshot_id text PRIMARY KEY,
    as_of timestamptz NOT NULL,
    source text NOT NULL,
    baseline_id text,
    total_pnl_cnh numeric(24, 6) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pnl_snapshots_as_of
    ON portfolio.pnl_snapshots(as_of DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio.pnl_baselines (
    baseline_id text PRIMARY KEY,
    cutoff_at timestamptz NOT NULL,
    source text NOT NULL,
    realized_pnl_cnh numeric(24, 6) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pnl_baselines_cutoff_at
    ON portfolio.pnl_baselines(cutoff_at DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS events.platform_event_outbox (
    event_id text PRIMARY KEY,
    event_type text NOT NULL,
    schema_version integer NOT NULL,
    subject text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    publish_attempts integer NOT NULL DEFAULT 0,
    last_error text,
    locked_by text,
    locked_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_pending
    ON events.platform_event_outbox(published_at, created_at, event_id);

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_type
    ON events.platform_event_outbox(event_type, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_subject
    ON events.platform_event_outbox(subject, created_at DESC);
