"""Archive computed sector aggregates and research reports in ClickHouse."""
import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    manifest = json.loads((root/'analysis_manifest.json').read_text())
    for name, expected in manifest.items():
        if digest((root/name).read_bytes()) != expected:
            raise ValueError('Frozen analysis changed: '+name)
    store = AnalyticsStore.from_settings(AppSettings())
    store.client.timeout_seconds = 120
    rows = []
    with (root/'sector_observations.csv').open(newline='', encoding='utf-8') as stream:
        for item in csv.DictReader(stream):
            features = {k: v if v != '' else None for k, v in item.items() if not k.startswith('forward_')}
            rows.append(observation(item['date']+'/'+item['sector'], 'research_sector_aggregate', item['sector'], features, item['date']))
            for key in ('forward_20', 'forward_60', 'forward_120'):
                # These are descriptive labels, deliberately isolated from feature records.
                rows.append(observation(item['date']+'/'+item['sector']+'/'+key, 'research_forward_return_label', item['sector'],
                    dict(signal_date=item['date'], horizon_sessions=int(key.split('_')[1]),
                         return_usd=float(item[key]) if item[key] else None,
                         role='future_label_not_a_signal_feature'), item['date']))
    documents = []
    for name in ('report.md', 'correlations.json', 'coverage.json', 'analysis_manifest.json'):
        documents.append(dict(point_key=name, media_type='application/json' if name.endswith('.json') else 'text/markdown',
                              payload=(root/name).read_bytes().decode('utf-8')))
    version = digest(encode(dict(manifest=manifest, importer=digest(Path(__file__).read_bytes()))))
    source = 'sector-research/'+root.name+'/analysis'
    changed = store.publish(source, version, rows, documents, provenance=dict(root=str(root),
        research_only=True, labels_are_not_features=True, unknown_historical_availability_is_null=True))
    receipt = dict(source=source, version=version, rows=len(rows), documents=len(documents), changed=changed,
                   verification='Exact per-record and per-document payload SHA-256 readback', workspace=store.workspace)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
