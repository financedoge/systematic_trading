"""Reproduce the frozen FR25 study with the registered app recipe and fresh fits."""
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files, freeze_usd_bundle, run_usd_reference
from systematic_trading.research import fr25_tracking as f
from systematic_trading.recorders.economics import EconomicInputs
from systematic_trading.research.strategy_catalog import fr25_definition
from systematic_trading.research.usd_monitored import worker_init, targets_worker


def main():
    parent=Path('var/research/selection-blend-20261010-v1').resolve()
    root=Path(sys.argv[1]).resolve()
    if root.exists():raise FileExistsError('Preserve validation attempts')
    checked_files(parent,'input_manifest.json');checked_files(parent,'decision_manifest.json')
    bars,raw=read_json(parent/'bars.json'),read_json(parent/'raw.json')
    models,macro=read_json(parent/'xgb_usd.json'),read_json(parent/'macro.json')
    receipt=read_json(parent/'data_receipt.json');reader=EconomicInputs(**receipt['economic_pin'])
    original=read_json(parent/'decisions/FR25.json')
    known={d:r['known_through'] for d,r in original.items()}
    vintages={str(date.fromisoformat(k)-timedelta(days=1)) for k in known.values()}
    entries=[r for r in reader.catalog['snapshots'] if r['series'] in f.SERIES and r['vintage'] in vintages]
    inputs=dict(pin=receipt['economic_pin'],entries=entries,known=known,monthly_decisions=sorted(known),
        provenance=dict(validation='pinned_research_reproduction',price_batch=receipt['price_batch']))
    schedule=f.prepare_schedule(inputs,bars)
    for day,model in schedule['models'].items():
        for key,value in macro[day]['financial'].items():
            if model[key]!=value:raise ValueError('Refitted financial model changed: '+day+'/'+key)
    print('Exact financial fit parity:',len(schedule['models']),flush=True)
    root.mkdir(parents=True)
    shutil.copytree(Path('src/systematic_trading'),root/'source/systematic_trading',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    write_json(root/'protocol.json',dict(initial_cash_usd='1000000',limitations=['Pinned audited research parity; not prospective evidence.']))
    definition=fr25_definition()
    write_json(root/'worker.json',dict(bars=bars,raw_bars=raw,rolling=models['rolling'],base_models={},usd=models['usd'],
        economic=schedule,definitions=[definition.to_dict()]))
    write_json(root/'input_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()})
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 1,initializer=worker_init,initargs=(str(root),)) as pool:
        rows=dict(pool.map(targets_worker,sorted(known)))
    decisions={d:rows[d][f.KEY] for d in sorted(rows)}
    for day,row in decisions.items():
        for field in ('signal_session','known_through'):
            assert row[field]==original[day][field]
        weights=lambda r:{t['symbol']:Decimal(t['target_weight']) for t in r['targets']}
        assert weights(row)==weights(original[day]),day
    from systematic_trading.research.momentum_calculation import quotes_for_data
    quotes,sessions=quotes_for_data(bars,[r['trade_date'] for r in bars['SPY']],'2016-01-04')
    freeze_usd_bundle(root/'bundle',root,definition.to_dict(),decisions,quotes,sessions,5)
    result=run_usd_reference(root/'bundle')
    expected=read_json(parent/'python/FR25-cost5-delay0-full.json')
    for key in ('nav','fills','final_positions'):
        assert result[key]==expected[key],key
    write_json(root/'economic.json',result)
    write_json(root/'acceptance.json',dict(status='passed',model_fits=len(schedule['models']),decisions=len(decisions),
        fills=len(result['fills']),nav=len(result['nav']),final_positions=True,
        protocol_sha256=sha256(parent/'protocol.json'),bundle_sha256=sha256(root/'bundle/manifest.json')))
    print(read_json(root/'acceptance.json'),flush=True)


if __name__=='__main__':main()
