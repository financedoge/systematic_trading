"""Read-only comparison of committed calculation inputs with an audited catalog.

This is diagnostic evidence, never permission to reuse a calculation or route an
order. It does not acquire data, mutate publications or infer unknown dependencies.
"""
import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research.governed_inputs import GovernedInputs


def row_changes(before, after):
    old = {r['trade_date']: r for r in before}
    new = {r['trade_date']: r for r in after}
    if len(old) != len(before) or len(new) != len(after):
        raise ValueError('Duplicate dates cannot establish equivalence')
    changed = sorted(d for d in old.keys() & new.keys() if old[d] != new[d])
    added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    fields = Counter(k for d in changed for k in old[d].keys() | new[d].keys()
                     if old[d].get(k) != new[d].get(k))
    kind = ('revised_or_removed' if changed or removed else
            'append_only' if added and old and min(added) > max(old) else
            'historical_insertion' if added else 'identical_rows')
    return dict(kind=kind, added=added, removed=removed, changed_dates=len(changed),
                first_changed=changed[0] if changed else None, changed_fields=dict(fields))


def input_scopes(value, name='base'):
    if not isinstance(value, dict):
        return
    if 'governed_files' in value:
        yield name, value
    for key, child in value.items():
        if isinstance(child, dict) and key != 'governed_files':
            yield from input_scopes(child, key if name == 'base' else name + '/' + key)


def audit(analytics, calculation, catalog):
    provenance = json.loads(calculation['provenance'])
    inputs = provenance['inputs']
    old = analytics.publication('governance/catalog', inputs['batch'])
    if old is None:
        raise ValueError('Original committed catalog is unavailable; impact is unknown')
    readers = [GovernedInputs(Path(json.loads(p['provenance'])['root']), p['version']) for p in (old, catalog)]
    scopes = {}
    for name, scope in input_scopes(inputs):
        if scope.get('batch', inputs['batch']) != inputs['batch']:
            scopes[name] = dict(source_batch=scope['batch'],
                               status='independently_pinned_scope_not_compared_to_current_catalog')
            continue
        unchanged, differences = 0, []
        for file, expected in scope['governed_files'].items():
            relative = file
            while relative.startswith('parent/'):
                relative = relative[len('parent/'):]
            if not relative.startswith(('bars/', 'audits/')):
                continue
            if sha256(readers[0].checked(relative)) != expected:
                raise ValueError('Original calculation artifact differs: ' + relative)
            actual = sha256(readers[1].checked(relative))
            if actual == expected:
                unchanged += 1
                continue
            item = dict(file=relative, old_hash=expected, new_hash=actual)
            if relative.startswith('bars/'):
                symbol = Path(relative).name.removesuffix('.jsonl.gz')
                # This is a conservative recorded-artifact comparison. Consumers
                # can have narrower date/field windows; do not guess those here.
                item['rows'] = row_changes(*(r.rows(symbol, '0001-01-01', '9999-12-31') for r in readers))
            differences.append(item)
        scopes[name] = dict(unchanged_files=unchanged, changed_files=differences)
    catalogs = [{r['symbol']: r for r in json.loads(reader.checked('catalog.json').read_text(encoding='utf8'))}
                for reader in readers]
    changed_symbols = sorted(s for s in catalogs[0].keys() | catalogs[1].keys()
                             if catalogs[0].get(s) != catalogs[1].get(s))
    return dict(checked_at=datetime.now(UTC).isoformat(), calculation=calculation['version'],
                old_batch=old['version'], new_batch=catalog['version'], scope_comparison=scopes,
                catalog_changed_symbols=changed_symbols,
                limitation='Recorded price/audit artifacts only; independent inputs, execution contracts and code require separate checks.',
                authority='diagnostic_only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calculation', help='Committed calculation version; default latest')
    parser.add_argument('--catalog', help='Committed audited catalog version; default latest')
    parser.add_argument('--output', type=Path, help='New local evidence file; refuses overwrite')
    args = parser.parse_args()
    store = AnalyticsStore.from_settings(AppSettings())
    calculation = (store.publication('tracked-strategies/calculations', args.calculation) if args.calculation
                   else store.latest('tracked-strategies/calculations'))
    catalog = store.publication('governance/catalog', args.catalog) if args.catalog else store.latest('governance/catalog')
    if calculation is None or catalog is None:
        raise ValueError('Requested committed publication is unavailable')
    report = audit(store, calculation, catalog)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf8') as stream:
            json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
