from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


async def configure_stream(
    *,
    nats_url: str,
    stream_name: str,
    subjects: list[str],
) -> dict[str, object]:
    try:
        import nats
    except ImportError as exc:
        raise RuntimeError("NATS stream configuration requires the optional dependency: pip install -e .[queue]") from exc

    connection = await nats.connect(servers=[nats_url], name="systematic-trading-stream-config")
    try:
        jetstream = connection.jetstream()
        try:
            info = await jetstream.stream_info(stream_name)
        except Exception:
            await jetstream.add_stream(name=stream_name, subjects=subjects)
            return {"stream": stream_name, "subjects": subjects, "action": "created"}
        configured_subjects = list(getattr(getattr(info, "config", None), "subjects", []) or [])
        return {"stream": stream_name, "subjects": configured_subjects, "action": "exists"}
    finally:
        await connection.drain()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or verify the NATS JetStream stream for platform events.")
    parser.add_argument("--nats-url", default="nats://127.0.0.1:4222")
    parser.add_argument("--stream-name", default="ST_EVENTS")
    parser.add_argument("--subject", action="append", default=["systematic_trading.events.v1.>"])
    args = parser.parse_args(argv)

    result = asyncio.run(
        configure_stream(
            nats_url=args.nats_url,
            stream_name=args.stream_name,
            subjects=args.subject,
        )
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
