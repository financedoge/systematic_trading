"""Read-only audit of dated research verdicts; never reruns or rewrites a study."""
import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STUDIES = [
    ('cash-relative-momentum-20261017-v1', 'analysis.json', 'withheld', 'accepted_screen'),
    ('class-volatility-screen-20261016-v1', 'analysis.json', 'withheld', 'accepted_screen'),
    ('etf-expansion-20261014-v1', 'summary.json', 'mixed', 'accepted_screen'),
    ('alpha101-screen-20261011-v4', 'screen.json', 'withheld', 'canonical_corrected_screen'),
    ('alpha101-tilt-20261011-v3', 'tilt.json', 'screen_only', 'canonical_corrected_screen'),
    ('sleeve-construction-20261010-v2', 'gate.json', 'replayed', 'construction'),
    ('hierarchical-construction-20261011-v2', 'gate.json', 'replayed', 'construction'),
    ('alpha101-tilt-surface-20261011-v2', 'gate.json', 'replayed', 'superseded_grid'),
    ('alpha101-tilt-daily-20261011-v2', 'gate.json', 'replayed', 'superseded_grid'),
    ('alpha101-tilt-exit-20261011-v2', 'gate.json', 'replayed', 'superseded_grid'),
]


def classification(gate):
    if gate is None or gate.get('margin_test') is None:
        return 'insufficient'
    if gate.get('cost_test') is False:
        return 'cost_only' if gate['margin_test'] is True else 'cost_and_information'
    return 'information_only' if gate['margin_test'] is False else 'passed'


def verdicts(value, path=''):
    if isinstance(value, dict):
        if 'cost_test' in value and 'margin_test' in value:
            yield path, value
        else:
            for key, child in value.items():
                yield from verdicts(child, path+'/'+str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            identity = child.get('alpha', index) if isinstance(child, dict) else index
            if isinstance(child, dict) and 'alpha' in child and 'budget' in child:
                identity = str(identity)+'@'+str(child['budget'])
            yield from verdicts(child, path+'/'+str(identity))


def main():
    sources, studies = {}, []
    for name, file, replay_state, validity in STUDIES:
        root = REPO/'var/research'/name
        path = root/file
        raw = path.read_bytes()
        sources[path.relative_to(REPO).as_posix()] = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw)
        rows = []
        for label, gate in verdicts(data):
            replayed = (gate.get('may_replay') if file == 'gate.json' and validity == 'construction'
                        else label.endswith('/original14') if replay_state == 'mixed'
                        else replay_state == 'replayed')
            rows.append(dict(candidate=label, historical_classification=classification(gate),
                annual_cost_bps=gate.get('annual_cost_bps'), ic_margin=gate.get('ic_margin'),
                margin_test=gate.get('margin_test'), replayed=replayed,
                cost_only_replay_withheld=classification(gate) == 'cost_only' and not replayed))
        # One Alpha101 mapping has no valid information/gate at all.
        if file == 'screen.json':
            for row in data['rows']:
                if row.get('gate') is None:
                    rows.append(dict(candidate=str(row['alpha']), historical_classification='insufficient',
                        replayed=False, cost_only_replay_withheld=False))
        counts = {key:sum(row['historical_classification'] == key for row in rows)
                  for key in ('cost_only','cost_and_information','information_only','insufficient','passed')}
        studies.append(dict(study=name, evidence_status=validity, rows=rows, counts=counts,
            cost_only_withheld=sum(row['cost_only_replay_withheld'] for row in rows)))
    result = dict(version='research-cost-rejection-audit-20261017-v1', sources=sources,
        studies=studies, cost_only_withheld=sum(s['cost_only_withheld'] for s in studies),
        caveats=['Audit of archived verdicts, not a new profitability result.',
                 'Superseded Alpha101 grids establish that replays existed, not valid economic conclusions.',
                 'Information-margin failures remain diagnostics, not evidence of negative net returns.',
                 'P4.22/P4.23 and the corrected FR25/5% tilt and exposure-targeting studies already used net replays.'])
    out=REPO/'research/research-cost-policy-20261017-v1/audit.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({s['study']:dict(s['counts'],cost_only_withheld=s['cost_only_withheld']) for s in studies}))


if __name__ == '__main__':
    main()
