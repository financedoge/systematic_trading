import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("adaptive_study", ROOT / "scripts/retest_adaptive_breakout.py")
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)


def test_sealing_preserves_parameter_and_score_precision(tmp_path):
    values = dict(parameters=np.array([.14702169907934162, 11.584649722491534]), score=np.float64(.0000000123456789123))
    target = tmp_path / "fit.json"
    study.write(target, values)
    restored = json.loads(target.read_text())
    assert restored["parameters"] == values["parameters"].tolist()
    assert restored["score"] == values["score"]


def test_component_ablation_includes_unchanged_control_and_only_named_change():
    for domain in ("short", "long"):
        grid = study.grid(domain)
        assert len(grid) == 90
        assert grid[0] == dict(range="legacy", trend="none", exit="legacy")
        counts = {family: sum(study.subset(r, family) for r in grid) for family in study.FAMILIES}
        assert counts == dict(exit_fit=6, trend_fit=3, range_fit=5, joint_fit=90)
