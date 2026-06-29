param(
    [string]$ContainerName = "systematic-trading-clickhouse"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Install Docker Desktop or run this on a server with Docker."
}

$Database = if ($env:ST_CLICKHOUSE_DATABASE) { $env:ST_CLICKHOUSE_DATABASE } else { "systematic_trading" }
$User = if ($env:ST_CLICKHOUSE_USER) { $env:ST_CLICKHOUSE_USER } else { "st_app" }
$Password = if ($env:ST_CLICKHOUSE_PASSWORD) { $env:ST_CLICKHOUSE_PASSWORD } else { "local-dev-change-me" }

$Query = @"
CREATE TABLE IF NOT EXISTS smoke_p2_8
(
    event_date Date,
    symbol LowCardinality(String),
    received_at DateTime64(3, 'UTC'),
    available_at DateTime64(3, 'UTC'),
    price Float64,
    schema_version UInt16
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (symbol, event_date, received_at);

INSERT INTO smoke_p2_8
VALUES (today(), 'SMOKE', now64(3, 'UTC'), now64(3, 'UTC'), 1.23, 1);

SELECT concat('smoke_rows=', toString(count()))
FROM smoke_p2_8
WHERE symbol = 'SMOKE';
"@

$DockerArgs = @(
    "exec",
    $ContainerName,
    "clickhouse-client",
    "--database",
    $Database,
    "--user",
    $User,
    "--password",
    $Password,
    "--multiquery",
    "--query",
    $Query
)

& docker @DockerArgs
if ($LASTEXITCODE -ne 0) {
    throw "ClickHouse smoke query failed with exit code $LASTEXITCODE"
}
