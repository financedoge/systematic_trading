"""Isolated CPU-bound bundle preparation from application-pinned input files."""
import json
from pathlib import Path
import sys

from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, verify_bundle


def checked_input(reference):
    path = Path(reference["path"])
    if sha256(path) != reference["sha256"]:
        raise ValueError("Calculation preparation input changed: " + str(path))
    return json.loads(path.read_text(encoding="utf8"))


def prepare(request_path):
    request = json.loads(request_path.read_text(encoding="utf8"))
    inputs = checked_input(request["inputs"])
    models = checked_input(request["models"]) if request["models"] else None
    bundle = Path(request["bundle"])
    if not bundle.exists():
        freeze_bundle(root=bundle, bars=inputs["bars"], fx=inputs["fx"], provenance=inputs["provenance"],
            base_tree_models=models, spec_values=request["spec"])
    verify_bundle(bundle)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
