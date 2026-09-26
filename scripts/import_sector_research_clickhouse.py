"""Publish frozen sector-research histories to ClickHouse with exact hash readback.

Uses the existing versioned analytics contract. No production daily-bar rows,
security classifications or trading inputs are overwritten.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.market_data.golden import _sql_string


class ResearchBatchAnalytics(AnalyticsStore):
    """Larger bounded inserts for bulk history, preserving the publication contract."""

    def publish_batch(self, sources):
        now = datetime.now(UTC).isoformat()
        rows, publications, expected = [], [], {}
        for source, version, observations, provenance in sources:
            for row in observations:
                identity = (source, version, row['point_key'])
                if identity in expected:
                    raise ValueError('Duplicate analytical batch identity')
                expected[identity] = digest(row['payload'])
                rows.append(dict(workspace=self.workspace, source_id=source, version=version, ingested_at=now, **row))
            publications.append(dict(workspace=self.workspace, source_id=source, version=version,
                published_at=now, observation_count=len(observations), document_count=0, provenance=encode(provenance)))
        for offset in range(0, len(rows), 10000):
            self.client.execute('INSERT INTO analytics.observations FORMAT JSONEachRow\n'+
                                '\n'.join(encode(r) for r in rows[offset:offset+10000]))
        identities = ','.join('('+_sql_string(s)+','+_sql_string(v)+')' for s, v, _, _ in sources)
        actual = self.query('SELECT source_id, version, point_key, lower(hex(SHA256(payload))) AS hash '
            'FROM analytics.observations FINAL WHERE workspace='+_sql_string(self.workspace)+
            ' AND (source_id,version) IN ('+identities+')')
        if {(r['source_id'], r['version'], r['point_key']): r['hash'] for r in actual} != expected:
            raise ValueError('Analytical batch readback mismatch')
        self.client.execute('INSERT INTO analytics.publications FORMAT JSONEachRow\n'+
                            '\n'.join(encode(r) for r in publications))
        return bool(sources)


def yahoo_rows(raw, symbol, raw_hash):
    result = json.loads(raw)['chart']['result'][0]
    quote = result['indicators']['quote'][0]
    adjusted = result['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
    rows = []
    for i, stamp in enumerate(result.get('timestamp', [])):
        day = datetime.fromtimestamp(stamp, UTC).date()
        payload = dict(symbol=symbol, date=day.isoformat(), provider_timestamp=stamp,
                       source_raw_sha256=raw_hash, instrument_type=result['meta'].get('instrumentType'),
                       currency=result['meta'].get('currency'), historical_available_at=None)
        flags = ['historical_vintage_uncertified', 'provider_adjustment_convention_uncertified']
        for field in ('open', 'high', 'low', 'close', 'volume'):
            values = quote.get(field, [])
            value = values[i] if i < len(values) else None
            payload[field] = value if value is None or math.isfinite(value) else None
        payload['adjusted_close'] = adjusted[i] if i < len(adjusted) else None
        if payload['adjusted_close'] is not None and not math.isfinite(payload['adjusted_close']):
            payload['adjusted_close'] = None
        if not is_us_trading_day(day):
            flags.append('non_session_observation')
        if any(payload[k] is None or payload[k] <= 0 for k in ('open', 'high', 'low', 'close', 'adjusted_close')):
            flags.append('missing_or_nonpositive_price')
        if payload['volume'] is None or payload['volume'] < 0:
            flags.append('missing_or_invalid_volume')
        elif payload['volume'] == 0:
            flags.append('observed_zero_volume')
        payload['quality_flags'] = flags
        rows.append(observation(str(stamp), 'research_equity_daily_bar', symbol, payload, day.isoformat(), None))
    if len({r['point_key'] for r in rows}) != len(rows):
        raise ValueError('Duplicate provider timestamps: '+symbol)
    return rows


def holding_rows(snapshot, aliases=None):
    aliases = aliases or {}
    return [observation(f'{i:05d}/{r["ticker"]}', 'research_sector_constituent', aliases.get(r['ticker'], r['yahoo']),
        dict(**r, snapshot_as_of=snapshot['as_of'], assumed_available=snapshot['assumed_available'],
             resolved_yahoo=aliases.get(r['ticker'], r['yahoo']),
             historical_available_at=None, retrieved_at=snapshot['retrieved_at'], source_raw_sha256=snapshot['raw_sha256'],
             quality_flags=['monthly_fund_sample', 'publication_lag_assumed_not_observed', 'historical_vintage_uncertified']),
        snapshot['as_of'], None) for i, r in enumerate(snapshot['rows'])]


def import_dataset(root, analytics):
    manifest_name = 'data_manifest.json' if (root/'data_manifest.json').exists() else 'manifest.json'
    manifest = json.loads((root/manifest_name).read_text())
    for name, expected in manifest.items():
        if digest((root/name).read_bytes()) != expected:
            raise ValueError('Frozen source mismatch: '+name)
    dataset = root.name
    prefix = 'sector-research/'+dataset+'/'
    extractor = digest(Path(__file__).read_bytes())
    version = digest(encode(dict(manifest=manifest, extractor=extractor)))
    current = analytics.publication_index(prefix)
    pending, total_rows, changed_sources = [], 0, 0

    def submit(source, rows, hashes, provenance):
        nonlocal total_rows, changed_sources
        total_rows += len(rows)
        v = digest(encode(dict(files=hashes, extractor=extractor)))
        if current.get(source, {}).get('version') != v:
            pending.append((source, v, rows, provenance))
            changed_sources += 1
        if len(pending) >= 20:
            analytics.publish_batch(pending)
            pending.clear()

    if (root/'bars_metadata').exists():
        alias_path = root/'symbol_aliases.json'
        alias_hash = digest(alias_path.read_bytes()) if alias_path.exists() else ''
        aliases = json.loads(alias_path.read_text())['aliases'] if alias_path.exists() else {}
        for i, path in enumerate(sorted((root/'bars_metadata').glob('*.json')), 1):
            meta = json.loads(path.read_text())
            symbol = path.stem
            source = prefix+'bars/'+symbol
            hashes = {str(path.name): digest(path.read_bytes())}
            rows = []
            raw_path = root/'bars_raw'/f'{symbol}.json'
            if meta['status'] == 'ok':
                raw = raw_path.read_bytes()
                hashes['raw'] = digest(raw)
                rows = yahoo_rows(raw, symbol, hashes['raw'])
            rows.append(observation('download_status', 'research_download_status', symbol, meta, meta['retrieved_at'], meta['retrieved_at']))
            submit(source, rows, hashes, dict(dataset=dataset, source_metadata=meta, raw_path=str(raw_path), research_only=True))
            if i % 500 == 0:
                print('ClickHouse source progress', dataset, i, 'rows', total_rows, flush=True)
        for path in sorted((root/'holdings').glob('*.json')):
            snapshot = json.loads(path.read_text())
            submit(prefix+'holdings/'+path.stem, holding_rows(snapshot, aliases), {path.name: digest(path.read_bytes()), 'aliases': alias_hash},
                   dict(dataset=dataset, source_url=snapshot['url'], retrieved_at=snapshot['retrieved_at'], research_only=True))
    else:
        provenance = json.loads((root/'provenance.json').read_text())
        for path in sorted((root/'raw').glob('*.json')):
            raw = path.read_bytes()
            submit(prefix+'bars/'+path.stem, yahoo_rows(raw, path.stem, digest(raw)), {path.name: digest(raw)},
                   dict(dataset=dataset, source_metadata=provenance[path.stem], research_only=True))
    if pending:
        analytics.publish_batch(pending)
        pending.clear()
    # Store exact UTF-8 raw source documents, including unsuccessful requests' metadata.
    # Chunking bounds query size; commit dataset metadata only after every group verifies.
    files = sorted(set(manifest) | {manifest_name})
    documents = 0
    changed_document_groups = 0
    for offset in range(0, len(files), 100):
        names = files[offset:offset+100]
        raws = {name: (root/name).read_bytes() for name in names}
        source = prefix+f'sources/{offset//100:04d}'
        v = digest(encode({name: digest(raw) for name, raw in raws.items()}))
        docs = [dict(point_key=name, media_type='application/json' if name.endswith('.json') else 'text/plain',
                     payload=raw.decode('utf-8')) for name, raw in raws.items()]
        documents += len(docs)
        changed_document_groups += analytics.publish(source, v, [], docs,
            provenance=dict(dataset=dataset, original_hashes={name: digest(raw) for name, raw in raws.items()}, exact_utf8_bytes=True))
    summary = dict(dataset=dataset, prefix=prefix, version=version, observation_count=total_rows,
                   source_document_count=documents, changed_sources=changed_sources,
                   changed_document_groups=changed_document_groups, research_only=True,
                   source_manifest=str(root/manifest_name), extractor_sha256=extractor,
                   verification='All imported row/document keys and SHA-256 payloads read back before publication',
                   schema='analytics.observations/documents/publications', available_at_semantics='Unknown original historical availability is NULL; retrieval and 45-day assumption stored separately')
    analytics.publish(prefix+'dataset', version, [],
        [dict(point_key='manifest', media_type='application/json', payload=encode(dict(manifest=manifest, summary={k: v for k, v in summary.items() if not k.startswith('changed_')})))],
        provenance=summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    store = ResearchBatchAnalytics.from_settings(AppSettings())
    store.client.timeout_seconds = 120
    store.initialize()
    result = import_dataset(args.root, store)
    result['workspace'] = store.workspace
    result['verified_at'] = datetime.now(UTC).isoformat()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
