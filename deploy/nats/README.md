# NATS JetStream Local Runtime

This is the repo-managed local Docker Compose path for the platform event bus.

## Start

```powershell
.\scripts\start_nats_jetstream.ps1
```

Equivalent direct command:

```powershell
docker compose -f deploy\nats\docker-compose.yml up -d
```

## Stop

```powershell
.\scripts\stop_nats_jetstream.ps1
```

Equivalent direct command:

```powershell
docker compose -f deploy\nats\docker-compose.yml down
```

## Runtime

- Client URL: `nats://127.0.0.1:4222`
- Monitoring URL: `http://127.0.0.1:8222`
- JetStream store: Docker volume `nats_jetstream_data`
- Intended stream: `ST_EVENTS`
- Intended subjects: `systematic_trading.events.v1.>`

Create or verify the stream after NATS is running:

```powershell
.\.venv\Scripts\python.exe .\scripts\configure_nats_stream.py
```

The stream config script requires the queue optional dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[queue]"
```

Docker is not installed on the current machine yet, so live startup must be smoke-tested after Docker Desktop or a server Docker runtime is available.
