"""Retry interrupted/transient native runs without rewriting immutable evidence."""
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from systematic_trading.lean.contracts import sha256
from systematic_trading.runtime_io import atomic_json


def retryable(error):
    return isinstance(error, (OSError, subprocess.SubprocessError))


def select_attempt(output, bundle, engine, *, now=None):
    now = now or datetime.now(UTC)
    state_path = output.with_name(output.name + ".retry.json")
    state = json.loads(state_path.read_text(encoding="utf8")) if state_path.exists() else {}
    selected = Path(state["attempt"]) if state.get("attempt") else output
    attempts = output.with_name(output.name + ".attempts")
    if selected.resolve() != output.resolve() and selected.resolve().parent != attempts.resolve():
        raise ValueError("Unsafe calculation attempt pointer")
    if not selected.exists():
        if state.get("complete_receipt_sha256"):
            raise ValueError("Recorded calculation attempt is missing")
        return selected, state_path, state
    receipt_path = selected / "run.json"
    if receipt_path.exists():
        # Corrupt or changed committed receipts must stay blocked, not be healed
        # by silently replacing their evidence with a fresh calculation.
        receipt = json.loads(receipt_path.read_text(encoding="utf8"))
        if state.get("complete_receipt_sha256") and sha256(receipt_path) != state["complete_receipt_sha256"]:
            raise ValueError("Completed calculation receipt changed")
        if receipt.get("manifest_sha256") != sha256(bundle / "manifest.json"):
            raise ValueError("Calculation attempt input manifest changed")
        if receipt.get("status") == "succeeded":
            return selected, state_path, state
        if receipt.get("status") == "failed":
            transient = receipt.get("retryable")
            if transient is None:  # Legacy timeout/process-exit receipts.
                transient = receipt.get("error", "").startswith(("TimeoutExpired:", "CalledProcessError:", "OSError:", "FileNotFoundError:"))
            if not transient:
                raise ValueError("Calculation requires review: " + receipt.get("error", "non-retryable failure"))
        elif receipt.get("status") != "running":
            raise ValueError("Unrecognized calculation attempt status")
        if engine == "lean" and receipt.get("run_id", "").startswith("st-lean-"):
            # The parent may have crashed while Docker was still computing.
            # Never delete an orphan container or reuse its writable directory.
            running = subprocess.run(["docker", "ps", "-q", "--filter", "name=^/"+receipt["run_id"]+"$"],
                capture_output=True, text=True, check=True, timeout=15)
            if running.stdout.strip():
                raise RuntimeError("Previous calculation container is still running; waiting before retry")
    elif any(selected.iterdir()):
        # No committed receipt: a process died while creating its output.
        pass
    retry_at = state.get("next_retry_at")
    if retry_at and now < datetime.fromisoformat(retry_at):
        raise RuntimeError("Calculation retry deferred until " + retry_at)
    attempt = attempts / uuid4().hex
    state = dict(attempt=str(attempt.resolve()), previous=str(selected.resolve()),
                 failures=state.get("failures", 0), started_at=now.isoformat())
    atomic_json(state_path, state)
    return attempt, state_path, state


def record_failure(state_path, state, output, error, *, now=None):
    now = now or datetime.now(UTC)
    failures = state.get("failures", 0) + 1
    atomic_json(state_path, dict(state, attempt=str(output.resolve()), failures=failures,
        error=f"{type(error).__name__}: {error}", retryable=retryable(error),
        next_retry_at=(now+timedelta(seconds=min(900, 30*2**min(failures-1, 5)))).isoformat()))
