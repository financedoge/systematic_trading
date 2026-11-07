"""Pinned scope adapter for five large residuals; prior capture recipes unchanged."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import capture_volume_exception_trades as alpaca
import capture_volume_exception_ibkr as ibkr
import reconcile_volume_exceptions as reconcile
from probe_alpaca_sip_source import ROOT, save, sha


STUDY = ROOT / "research/p421-large-volume-20261107-v1"
PROTOCOL_HASH = "2cf73c9f70f7a5f116176392c1fa469455da0031622f15b2715b98b94c071007"
ORIGINAL_ARCHIVE = alpaca.archive


def protocol():
    raw = (STUDY / "protocol.json").read_bytes()
    if sha(raw) != PROTOCOL_HASH:
        raise ValueError("Changed five-case scope")
    p = json.loads(raw)
    for name, expected in p["pinned_helpers"].items():
        if sha((ROOT / "scripts" / name).read_bytes()) != expected:
            raise ValueError("Changed reusable recipe: " + name)
    return p


def scoped_archive(provider, resume, runner):
    # The unchanged archive helper now reads the explicitly selected scope in
    # this isolated process. Store the adapter as part of the executed recipe.
    p = protocol()
    if resume:
        m = json.loads((resume / "manifest.json").read_text())
        for name, expected in m["files_sha256"].items():
            if sha((resume / name).read_bytes()) != expected:
                raise ValueError("Changed archived recipe")
        if m.get("scope_adapter_sha256") != sha(Path(__file__).read_bytes()):
            raise ValueError("Changed scope adapter")
    root, manifest = ORIGINAL_ARCHIVE(provider, resume, runner)
    if resume is None:
        files = [Path(__file__), *[ROOT / "scripts" / n for n in p["pinned_helpers"]]]
        for source in files:
            raw = source.read_bytes()
            (root / source.name).write_bytes(raw)
            manifest["files_sha256"][source.name] = sha(raw)
        manifest.update(scope_adapter_sha256=sha(Path(__file__).read_bytes()), study=p["version"])
        save(root / "manifest.json", manifest)
    return root, manifest


def configure():
    protocol()
    alpaca.STUDY = STUDY
    alpaca.protocol = protocol
    alpaca.archive = scoped_archive
    ibkr.protocol = protocol
    ibkr.archive = scoped_archive
    reconcile.STUDY = STUDY
    reconcile.protocol = protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("alpaca", "ibkr"))
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    configure()
    root = (alpaca if args.provider == "alpaca" else ibkr).capture(args.resume)
    status = json.loads((root / "manifest.json").read_text())["status"]
    print(json.dumps(dict(archive=str(root), status=status)), flush=True)
    return 0 if status == "captured_pending_qualification" else 1


if __name__ == "__main__":
    raise SystemExit(main())
