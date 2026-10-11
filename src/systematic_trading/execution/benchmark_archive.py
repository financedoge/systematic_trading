"""Immutable benchmark attempts, coverage audits and durable retry state."""
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from systematic_trading.runtime_io import atomic_json, exclusive_lock


def digest(payload):
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def state_path(root, key):
    return Path(root) / "execution_benchmark_state" / (key + ".json")


def retained_state(root, key):
    path = state_path(root, key)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def validate_ready(candidate, *, root, symbol, start, end):
    from systematic_trading.execution.twap_benchmark import calculate_twap
    if (candidate["status"], candidate["symbol"], candidate["window_start"], candidate["window_end"]) != (
        "ready", symbol, start.isoformat(), end.isoformat()
    ):
        raise ValueError("Retained benchmark identity does not match the requested window")
    observed = datetime.fromisoformat(candidate["observed_at"])
    if observed.tzinfo is None or observed < end:
        raise ValueError("Invalid benchmark observation timestamp")
    price, count = calculate_twap(candidate["bars"], start, end)
    if candidate.get("format_version") == 2:
        audit = candidate["audit"]
        if audit["bars_sha256"] != digest(candidate["bars"]):
            raise ValueError("Benchmark bars changed after audit")
        if (audit["bar_count"], audit["twap_price"]) != (count, str(price)):
            raise ValueError("Benchmark audit summary differs from retained observations")
        raw = (Path(root) / audit["raw_ref"]).resolve()
        if not raw.is_relative_to(Path(root).resolve()):
            raise ValueError("Benchmark raw reference leaves the evidence directory")
        if sha256(raw.read_bytes()).hexdigest() != audit["raw_sha256"]:
            raise ValueError("Benchmark raw capture changed after audit")
        captured = json.loads(raw.read_text(encoding="utf-8"))
        response = captured["response"]
        bars = response["bars"] if isinstance(response, dict) else response
        if digest(bars) != audit["bars_sha256"] or captured["observed_at"] != candidate["observed_at"]:
            raise ValueError("Benchmark differs from its original capture")
        requested = captured["request"]
        if (requested["symbol"], requested["window_start"], requested["window_end"]) != (
            symbol, start.isoformat(), end.isoformat()
        ):
            raise ValueError("Benchmark raw request identity mismatch")
        if candidate.get("contract") != (response.get("contract") if isinstance(response, dict) else None):
            raise ValueError("Benchmark contract differs from the source capture")
    return price, count


def capture(provider, *, root, key, path, symbol, start, end):
    """One read-only provider request. Preserve failed/partial responses before validation."""
    from systematic_trading.execution.twap_benchmark import calculate_twap
    root, path = Path(root), Path(path)
    with exclusive_lock(state_path(root, key).with_suffix(".lock")):
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            validate_ready(saved, root=root, symbol=symbol, start=start, end=end)
            return saved
        previous = retained_state(root, key) or {}
        now = datetime.now(UTC)
        if now.timestamp() < previous.get("next_retry_at", 0):
            return dict(status="unavailable", message=previous.get("message", "Retained retry cooldown"),
                        next_retry_at=previous["next_retry_at"])
        attempt = uuid4().hex
        count = previous.get("attempt_count", 0) + 1
        folder = root / "execution_benchmark_attempts" / key
        request = dict(attempt_id=attempt, symbol=symbol, window_start=start.isoformat(),
                       window_end=end.isoformat(), started_at=now.isoformat(), source="IB historical TRADES",
                       bar_size="1 min", use_rth=True, paper_data_connection=True)
        atomic_json(folder / (attempt + ".request.json"), request)
        state = dict(attempt_id=attempt, attempt_count=count, status="collecting", last_attempt_at=now.isoformat(),
                     next_retry_at=now.timestamp() + 300, message="Collection in progress or interrupted")
        atomic_json(state_path(root, key), state)
        response = None
        raw_path = folder / (attempt + ".response.json")
        try:
            response = provider.fetch(symbol, start, end)
            observed = datetime.now(UTC)
            atomic_json(raw_path, dict(request=request, observed_at=observed.isoformat(), response=response))
            bars = response["bars"] if isinstance(response, dict) else response
            price, bar_count = calculate_twap(bars, start, end)
            result = dict(format_version=2, status="ready", symbol=symbol, bars=bars,
                          window_start=start.isoformat(), window_end=end.isoformat(), observed_at=observed.isoformat(),
                          source="IB historical TRADES", contract=response.get("contract") if isinstance(response, dict) else None,
                          price_basis="Provider historical TRADES; trading-time raw basis not independently certified",
                          research_approved=False,
                          audit=dict(status="complete_observed_window", coverage="100%", bar_count=bar_count,
                                     twap_price=str(price), bars_sha256=digest(bars),
                                     raw_ref=raw_path.relative_to(root).as_posix(),
                                     raw_sha256=sha256(raw_path.read_bytes()).hexdigest()))
            validate_ready(result, root=root, symbol=symbol, start=start, end=end)
            # The per-key process lock prevents two writers; completed observations are never replaced.
            if path.exists():
                raise FileExistsError("A completed benchmark appeared during collection")
            atomic_json(path, result)
            state.update(status="ready", next_retry_at=0, message="Complete observed window retained",
                         observed_at=observed.isoformat(), benchmark_sha256=sha256(path.read_bytes()).hexdigest())
        except Exception as exc:
            if not raw_path.exists():
                atomic_json(raw_path, dict(request=request, observed_at=datetime.now(UTC).isoformat(),
                                          error=str(exc), response=getattr(exc, "evidence", response)))
            state.update(status="unavailable", message=str(exc),
                         next_retry_at=datetime.now(UTC).timestamp() + min(3600, 300 * 2 ** min(count - 1, 4)))
            result = dict(status="unavailable", message=str(exc), next_retry_at=state["next_retry_at"])
        atomic_json(folder / (attempt + ".audit.json"), state)
        atomic_json(state_path(root, key), state)
        return result
