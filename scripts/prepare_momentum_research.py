"""Freeze published inputs and the finite registration before viewing returns."""
import argparse
import json
from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json, verify_bundle
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
from systematic_trading.research.momentum_protocol import protocol


def prepare(root):
    if root.exists():
        raise FileExistsError('Research freezes are immutable: '+str(root))
    p = protocol()
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    publication = analytics.latest('governance/catalog')
    tracked = analytics.latest('tracked-strategies/calculations')
    tracked_provenance = json.loads(tracked['provenance'])
    if publication['version'] != tracked_provenance['inputs']['batch']:
        raise ValueError('Baseline and latest published input batch differ')
    source = GovernedInputs(Path(json.loads(publication['provenance'])['root']), publication['version'])
    symbols = list(instruments_for_definition(current_sota_definition()))
    rows = {s: source.rows(s, p['warmup_start'], p['end']) for s in [*symbols, 'URTH']}
    bars = {s: [etf_bar(r) for r in rows[s]] for s in symbols}
    from datetime import date, timedelta
    first, last = date.fromisoformat(p['warmup_start']), date.fromisoformat(p['end'])
    calendar = [str(first+timedelta(days=i)) for i in range((last-first).days+1) if is_us_trading_day(first+timedelta(days=i))]
    if any([r['trade_date'] for r in v] != calendar for v in bars.values()):
        raise ValueError('Missing or different ETF sessions; no fill or splice permitted')
    urth = [dict(trade_date=r['trade_date'], open=str(r['adjusted_open']), close=str(r['adjusted_close'])) for r in rows['URTH']]
    expected = [d for d in calendar if d >= '2015-12-31']
    if [r['trade_date'] for r in urth if r['trade_date'] >= expected[0]] != expected:
        raise ValueError('Missing benchmark session')
    cfg = tracked_provenance['config']['calculation']
    models_path = Path(cfg['base_models_path'])
    if sha256(models_path) != cfg['base_models_sha256']:
        raise ValueError('Changed base models')
    baseline = settings.data_dir/'tracked_strategies'/tracked['version']/'datasets'/current_sota_definition().key
    verify_bundle(baseline)
    base_provenance = json.loads((baseline/'provenance.json').read_text())
    if base_provenance['batch'] != publication['version']:
        raise ValueError('Different baseline batch')
    rolling_artifact = tracked_provenance['model_training']['rolling-xgboost-1y-v1']
    rolling = Path(rolling_artifact['artifact_path'])/'schedule.json'
    if sha256(rolling) != rolling_artifact['files']['schedule.json']:
        raise ValueError('Changed rolling models')
    root.mkdir(parents=True)
    # Registration is the first durable artifact; no candidate returns calculated here.
    write_json(root/'protocol.json', p)
    for name, value in [('bars.json', bars), ('urth.json', urth),
                        ('base_models.json', json.loads(models_path.read_text())),
                        ('rolling_models.json', json.loads(rolling.read_text())),
                        ('baseline_decisions.json', json.loads((baseline/'decisions.json').read_text()))]:
        write_json(root/name, value)
    write_json(root/'data_receipt.json', dict(publication=publication, tracked_publication=tracked,
        governed_root=str(source.root), batch=publication['version'], files=source.used,
        input_coverage={s: dict(rows=len(v), first=v[0]['trade_date'], last=v[-1]['trade_date'],
            missing_raw=sum(r.get('raw_close') is None or r.get('raw_volume') is None for r in v),
            raw_vs_split_adjusted_volume_differences=sum(r.get('raw_volume') != r.get('source_volume') for r in v)) for s,v in rows.items()},
        base_models_sha256=sha256(models_path), rolling_models_sha256=sha256(rolling), baseline_manifest_sha256=sha256(baseline/'manifest.json'),
        usd=dict(status='unavailable', reason='No release/vintage-audited broad USD source in published governance catalog',
                 checked_sources=list(analytics.publication_index('governance/')),
                 release_information='https://www.federalreserve.gov/releases/h10/about.htm',
                 revisions='https://www.federalreserve.gov/releases/h10/Summary/'),
        fx_bridge=dict(status='unavailable', reason='Historical USD/CNH input is explicitly uncertified; excluded from new historical research under AGENTS.md. USD results only.'),
        limitations=p['limitations'], image=cfg['image']))
    write_json(root/'input_manifest.json', {f.name: sha256(f) for f in root.iterdir() if f.is_file()})
    print(json.dumps(dict(root=str(root.resolve()), batch=publication['version'], recipes=len(p['recipes']), comparisons=p['family_size'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    prepare(parser.parse_args().root)
