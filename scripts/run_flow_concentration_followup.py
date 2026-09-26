"""Post-result implementation stresses for a fixed, previously tested candidate.

This is explicitly post-hoc follow-up, not fresh holdout evidence or another
parameter search. Parent runs and the original trial protocol remain immutable.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.runner import run_bundle
from systematic_trading.research.flow_concentration import FlowConcentrationSpec
from analyze_flow_concentration_research import metrics, WINDOWS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    root = args.root
    protocol = json.loads((root/'protocol.json').read_text())
    cfg = protocol['trials'][args.candidate]
    if cfg is None:
        raise ValueError('Choose a previously tested challenger')
    followup = root/'followups'/args.candidate
    followup.mkdir(parents=True, exist_ok=False)
    write_json(followup/'protocol.json', dict(parent_protocol_sha256=sha256(root/'protocol.json'),
        candidate=args.candidate, config=cfg, post_hoc=True, parameter_search=False,
        reason='Best full-period CAGR among the original fixed challengers; check matched implementation stresses only.',
        stresses=protocol['stresses'], fresh_holdout=False))
    snapshot = root/'snapshot'
    for name, digest in json.loads((snapshot/'manifest.json').read_text()).items():
        if sha256(snapshot/name) != digest:
            raise ValueError('Snapshot changed: '+name)
    bars, fx, provenance = [json.loads((snapshot/f'{n}.json').read_text()) for n in ('bars', 'fx', 'provenance')]
    results = {}
    for stress, values in protocol['stresses'].items():
        bundle, output = followup/'datasets'/stress, followup/'runs'/stress
        print('FREEZE FOLLOWUP '+stress, flush=True)
        freeze_bundle(root=bundle, bars=bars, fx=fx, provenance=provenance,
            spec_values=dict(start_date=protocol['start'], end_date=protocol['end'], warmup_start=protocol['warmup_start'],
                strategy='sota_flow', flow_overlay=FlowConcentrationSpec(**cfg).model_dump(), mode='targets',
                fx_policy='legacy_carry_max7', **values))
        receipt = run_bundle(bundle=bundle, output=output, image=protocol['image'])
        actual = json.loads((output/'economic.json').read_text())
        baseline = json.loads((root/'runs'/f'sota__{stress}'/'economic.json').read_text())
        if [r['date'] for r in actual['nav']] != [r['date'] for r in baseline['nav']]:
            raise ValueError('Mismatched comparison sessions')
        results[stress] = dict(receipt=receipt, windows={})
        for name, bounds in WINDOWS.items():
            a, b = metrics(actual, *bounds), metrics(baseline, *bounds)
            results[stress]['windows'][name] = dict(candidate=a, sota=b,
                cagr_delta=a['cagr']-b['cagr'], sharpe_delta=a['sharpe']-b['sharpe'],
                relative_wealth=(1+a['total_return'])/(1+b['total_return'])-1)
        write_json(followup/'results.json', dict(complete=False, post_hoc=True, results=results))
        print('PASS FOLLOWUP '+stress, flush=True)
    write_json(followup/'results.json', dict(complete=True, post_hoc=True, results=results))


if __name__ == '__main__':
    main()
