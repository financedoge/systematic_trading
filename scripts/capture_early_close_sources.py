"""Separate single-day scope, reusing the pinned five-case capture adapter."""
import argparse
import json
from pathlib import Path

import capture_large_volume_sources as base
from probe_alpaca_sip_source import ROOT, save, sha


STUDY = ROOT / "research/p421-crsp-early-close-20261107-v1"
PROTOCOL_HASH = "9f35d4d771173213b3fbbfd5170e6dcc81d451ce70c679b1cdf63c1dd1dd01f7"


def configure():
    base.STUDY = STUDY
    base.PROTOCOL_HASH = PROTOCOL_HASH
    base.configure()
    delegate = base.scoped_archive

    def archive(provider, resume, runner):
        if resume:
            m = json.loads((resume / "manifest.json").read_text())
            if m.get("calendar_scope_sha256") != sha(Path(__file__).read_bytes()):
                raise ValueError("Changed early-close scope adapter")
        root,m = delegate(provider,resume,runner)
        if resume is None:
            raw = Path(__file__).read_bytes()
            (root / Path(__file__).name).write_bytes(raw)
            m["files_sha256"][Path(__file__).name] = sha(raw)
            m["calendar_scope_sha256"] = sha(raw)
            save(root / "manifest.json",m)
        return root,m

    base.alpaca.archive = archive
    base.ibkr.archive = archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider",choices=("alpaca","ibkr"))
    parser.add_argument("--resume",type=Path)
    args = parser.parse_args()
    configure()
    root = (base.alpaca if args.provider == "alpaca" else base.ibkr).capture(args.resume)
    status = json.loads((root / "manifest.json").read_text())["status"]
    print(json.dumps(dict(archive=str(root),status=status)),flush=True)
    raise SystemExit(0 if status == "captured_pending_qualification" else 1)
